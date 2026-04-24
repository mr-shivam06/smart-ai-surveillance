"""
=============================================================
  File : backend/app/schemas/schemas.py
  Purpose : All Pydantic request/response models
=============================================================
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username : str
    email    : EmailStr
    password : str

class LoginRequest(BaseModel):
    username : str
    password : str

class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"

class UserOut(BaseModel):
    id        : int
    username  : str
    email     : str
    is_active : bool
    is_admin  : bool

    class Config:
        from_attributes = True


# ── Camera ────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name   : str
    source : str   # "0" for webcam, URL for IP cam

class CameraOut(BaseModel):
    id        : int
    name      : str
    source    : str
    is_active : bool

    class Config:
        from_attributes = True


# ── Tracking ──────────────────────────────────────────────────

class TrackingStatus(BaseModel):
    is_running         : bool
    active_camera_ids  : List[int]
    total_identities   : int
    cross_cam_matches  : int
    reid_backend       : str

class GlobalIDInfo(BaseModel):
    global_id  : str
    cameras    : List[int]
    class_name : str


# ── Alerts ────────────────────────────────────────────────────

class AlertOut(BaseModel):
    alert_id     : int
    type         : str
    severity     : str
    camera_id    : int
    timestamp    : float
    message      : str
    metadata     : dict
    acknowledged : bool

class AcknowledgeRequest(BaseModel):
    alert_id : int


# ── Vehicles ──────────────────────────────────────────────────

class VehicleSearchRequest(BaseModel):
    color      : Optional[str] = ""
    shape_type : Optional[str] = ""

class VehicleOut(BaseModel):
    global_id   : str
    class_name  : str
    shape_type  : str
    color       : str
    cameras     : List[int]
    first_seen  : float
    last_seen   : float
    frame_count : int