"""
=============================================================
  File : backend/app/api/routes_camera.py
  Purpose : Camera CRUD endpoints
=============================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import threading

from app.db.database import get_db
from app.models.camera_model import Camera
from app.core.security import get_current_user
from app.schemas.schemas import CameraCreate, CameraOut

# ✅ IMPORT CAMERA WORKER
from app.camera_worker import start_camera

router = APIRouter()


@router.get("", response_model=List[CameraOut])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all registered cameras."""
    return db.query(Camera).all()


@router.post("", response_model=CameraOut, status_code=201)
def add_camera(
    req: CameraCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a new camera source + START it immediately."""

    cam = Camera(
        name=req.name,
        source=req.source,
        is_active=True   # ✅ IMPORTANT
    )

    db.add(cam)
    db.commit()
    db.refresh(cam)

    # 🔥 START CAMERA THREAD
    threading.Thread(
        target=start_camera,
        args=(cam.id, req.source),
        daemon=True
    ).start()

    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    db.delete(cam)
    db.commit()


@router.patch("/{camera_id}/toggle", response_model=CameraOut)
def toggle_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Toggle camera active/inactive + start if activated."""

    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    cam.is_active = not cam.is_active
    db.commit()
    db.refresh(cam)

    # 🔥 IF TURNED ON → START CAMERA
    if cam.is_active:
        threading.Thread(
            target=start_camera,
            args=(cam.id, cam.source),
            daemon=True
        ).start()

    return cam