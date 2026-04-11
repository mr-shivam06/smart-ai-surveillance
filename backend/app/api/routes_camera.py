"""
=============================================================
  File : backend/app/api/routes_camera.py
  Purpose : Camera CRUD endpoints

  Endpoints:
    GET    /cameras         → list all cameras
    POST   /cameras         → add a camera
    DELETE /cameras/{id}    → remove a camera
    PATCH  /cameras/{id}    → toggle active/inactive
=============================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.camera_model import Camera
from app.core.security import get_current_user
from app.schemas.schemas import CameraCreate, CameraOut
from typing import List

router = APIRouter()


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
    """Add a new camera source."""
    cam = Camera(name=req.name, source=req.source)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id    : int,
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """Remove a camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    db.delete(cam)
    db.commit()


@router.patch("/{camera_id}/toggle", response_model=CameraOut)
def toggle_camera(
    camera_id    : int,
    db           : Session = Depends(get_db),
    current_user : dict    = Depends(get_current_user),
):
    """Toggle camera active/inactive."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam.is_active = not cam.is_active
    db.commit()
    db.refresh(cam)
    return cam