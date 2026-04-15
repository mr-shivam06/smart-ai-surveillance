"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/api/routes_camera.py
  Purpose : Camera CRUD — add, list, delete, toggle.
            Auto-starts AI pipeline when camera is added
            or toggled active.

  ENDPOINTS:
    GET    /cameras              → list all cameras
    POST   /cameras              → add + auto-start camera
    DELETE /cameras/{id}         → remove + stop camera
    PATCH  /cameras/{id}/toggle  → enable/disable + start/stop
=============================================================
"""

from fastapi import APIRouter, Depends, HTTPException
import cv2
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.camera_model import Camera
from app.core.security import get_current_user
from app.schemas.schemas import CameraCreate, CameraOut
from app.camera_worker import start_camera, stop_camera

router = APIRouter()
refresh_router = APIRouter()


@refresh_router.post("/camera/{camera_id}/refresh")
def refresh_camera(camera_id: int):
    from app.camera_registry import CAMERA_PROCESSORS

    if camera_id not in CAMERA_PROCESSORS:
        return {"error": "Camera not found"}

    processor = CAMERA_PROCESSORS[camera_id]

    if processor.cap is not None and processor.cap.isOpened():
        processor.cap.release()

    processor.cap = cv2.VideoCapture(processor.source)

    return {"status": "refreshed"}


@router.get("", response_model=List[CameraOut])
def list_cameras(
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """List all registered cameras."""
    return db.query(Camera).all()


@router.post("", response_model=CameraOut, status_code=201)
def add_camera(
    req          : CameraCreate,
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """
    Add a new camera and immediately start its AI pipeline.
    The full CameraProcessor (YOLO + tracking + drawing) runs
    in a background thread and pushes annotated frames to
    STREAM_BRIDGE so the dashboard shows the live feed.
    """
    cam = Camera(name=req.name, source=req.source, is_active=True)
    db.add(cam)
    db.commit()
    db.refresh(cam)

    # Start full AI pipeline for this camera
    start_camera(cam.id, req.source)

    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id    : int,
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """Remove a camera and stop its thread."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    stop_camera(camera_id)
    db.delete(cam)
    db.commit()


@router.patch("/{camera_id}/toggle", response_model=CameraOut)
def toggle_camera(
    camera_id    : int,
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """
    Toggle active/inactive.
    Activating starts the AI pipeline; deactivating stops it.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    cam.is_active = not cam.is_active
    db.commit()
    db.refresh(cam)

    if cam.is_active:
        start_camera(cam.id, cam.source)
    else:
        stop_camera(cam.id)

    return cam
