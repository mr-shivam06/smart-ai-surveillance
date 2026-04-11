"""
=============================================================
  File : backend/app/api/routes_tracking.py
  Purpose : Live tracking state + cross-camera ReID endpoints

  Endpoints:
    GET  /tracking/status       → live tracking summary
    GET  /tracking/cross-camera → all cross-camera matches
    POST /tracking/reset        → reset all trackers
=============================================================
"""

from fastapi import APIRouter, Depends
from typing import List

from app.core.security import get_current_user
from app.schemas.schemas import TrackingStatus, GlobalIDInfo

router = APIRouter()


@router.get("/status", response_model=TrackingStatus)
def tracking_status(current_user: dict = Depends(get_current_user)):
    """
    Live tracking summary.
    Reads directly from GLOBAL_TRACKER singleton.
    """
    from app.cross_camera_tracker import GLOBAL_TRACKER

    status = GLOBAL_TRACKER.get_status()
    return {
        "is_running"        : True,
        "active_camera_ids" : [],          # populated by camera threads
        "total_identities"  : status["total_identities"],
        "cross_cam_matches" : status["cross_camera_matches"],
        "reid_backend"      : status["backend"],
    }


@router.get("/cross-camera", response_model=List[GlobalIDInfo])
def cross_camera_matches(current_user: dict = Depends(get_current_user)):
    """All identities currently seen on more than one camera."""
    from app.cross_camera_tracker import GLOBAL_TRACKER
    return GLOBAL_TRACKER.get_cross_camera_list()


@router.post("/reset", status_code=200)
def reset_tracking(current_user: dict = Depends(get_current_user)):
    """
    Reset cross-camera gallery.
    Individual camera trackers are reset via main.py 'R' key.
    """
    from app.cross_camera_tracker import GLOBAL_TRACKER
    with GLOBAL_TRACKER._lock:
        GLOBAL_TRACKER._gallery.clear()
        GLOBAL_TRACKER._local_map.clear()
        GLOBAL_TRACKER._counter = 0
    return {"message": "Cross-camera gallery reset."}