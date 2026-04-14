"""
=============================================================
  File : backend/app/api/routes_tracking.py
  Purpose : Live tracking state + cross-camera ReID endpoints
=============================================================
"""

from fastapi import APIRouter, Depends
from typing import List

from app.core.security import get_current_user
from app.schemas.schemas import TrackingStatus, GlobalIDInfo

router = APIRouter()


# ── Tracking Status ────────────────────────────────────────
@router.get("/status", response_model=TrackingStatus)
def tracking_status(current_user: dict = Depends(get_current_user)):
    """
    Live tracking summary.
    """
    from app.cross_camera_tracker import GLOBAL_TRACKER
    from app.stream_bridge import STREAM_BRIDGE

    try:
        status = GLOBAL_TRACKER.get_status()
    except Exception:
        status = {
            "total_identities": 0,
            "cross_camera_matches": 0,
            "backend": "unknown",
        }

    return {
        "is_running"        : True,
        "active_camera_ids" : STREAM_BRIDGE.active_camera_ids(),  # ✅ FIX
        "total_identities"  : status.get("total_identities", 0),
        "cross_cam_matches" : status.get("cross_camera_matches", 0),
        "reid_backend"      : status.get("backend", "unknown"),
    }


# ── Cross-camera matches ───────────────────────────────────
@router.get("/cross-camera", response_model=List[GlobalIDInfo])
def cross_camera_matches(current_user: dict = Depends(get_current_user)):
    from app.cross_camera_tracker import GLOBAL_TRACKER

    try:
        return GLOBAL_TRACKER.get_cross_camera_list()
    except Exception:
        return []


# ── Reset tracking ─────────────────────────────────────────
@router.post("/reset", status_code=200)
def reset_tracking(current_user: dict = Depends(get_current_user)):
    from app.cross_camera_tracker import GLOBAL_TRACKER

    with GLOBAL_TRACKER._lock:
        GLOBAL_TRACKER._gallery.clear()
        GLOBAL_TRACKER._local_map.clear()
        GLOBAL_TRACKER._counter = 0

    return {"message": "Cross-camera gallery reset."}