"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/camera_worker.py
  Purpose : Proper AI pipeline camera worker used by
            routes_camera.py when cameras are added/enabled
            via the dashboard.

  THE BUG THIS FIXES:
    The old camera_worker.py read raw frames directly from
    cv2.VideoCapture and sent them to STREAM_BRIDGE with zero
    processing — completely bypassing YOLO detection, DeepSORT
    tracking, Re-ID, vehicle analysis, behavior analysis, and
    all drawing. The dashboard showed a plain raw feed with
    nothing on it.

  NOW:
    start_camera() creates a full CameraProcessor (same one
    main.py uses) and sends its annotated output to
    STREAM_BRIDGE. Every frame shown in the dashboard has
    full detection boxes, tracking IDs, vehicle info,
    dwell timers, zone overlays, and the HUD.

  USED BY:
    routes_camera.py — called when a camera is added or
    toggled active via the dashboard UI.
=============================================================
"""

import threading
import time
import logging

logger = logging.getLogger("CameraWorker")

# Global registry: camera_id → thread
_running_cameras: dict = {}
_lock = threading.Lock()


def start_camera(camera_id: int, source):
    """
    Start a full AI pipeline thread for this camera.
    Safe to call multiple times — stops any existing thread first.
    Called by routes_camera.py when a camera is added or enabled.
    """
    # Convert source to int if it's a digit string (e.g. "0" → 0)
    if isinstance(source, str) and source.strip().isdigit():
        source = int(source.strip())

    with _lock:
        # Stop existing thread for this camera if running
        existing = _running_cameras.get(camera_id)
        if existing and existing.get("running"):
            existing["running"] = False
            logger.info(f"[CameraWorker] Stopping existing thread for Cam {camera_id}")
            time.sleep(0.3)

        state = {"running": True}
        _running_cameras[camera_id] = state

    t = threading.Thread(
        target=_camera_loop,
        args=(camera_id, source, state),
        daemon=True,
        name=f"CamWorker-{camera_id}",
    )
    t.start()
    logger.info(f"[CameraWorker] Started AI pipeline for Cam {camera_id} (source={source!r})")


def stop_camera(camera_id: int):
    """Stop the camera thread for this ID."""
    with _lock:
        state = _running_cameras.get(camera_id)
        if state:
            state["running"] = False
            logger.info(f"[CameraWorker] Stop requested for Cam {camera_id}")


def _camera_loop(camera_id: int, source, state: dict):
    """
    Main camera thread. Creates CameraProcessor and sends
    every annotated frame to STREAM_BRIDGE.
    """
    from app.camera_processor import CameraProcessor
    from app.stream_bridge import STREAM_BRIDGE

    logger.info(f"[CameraWorker] Cam {camera_id} thread starting...")

    try:
        cam = CameraProcessor(camera_id=camera_id, source=source)
        state["processor"] = cam
        from app.camera_registry import CAMERA_PROCESSORS
        CAMERA_PROCESSORS[camera_id] = cam
    except Exception as e:
        logger.error(f"[CameraWorker] Cam {camera_id} failed to init: {e}")
        state["running"] = False
        return

    logger.info(f"[CameraWorker] Cam {camera_id} CameraProcessor ready")

    while state["running"]:
        try:
            frame = cam.get_frame()          # full AI pipeline
            STREAM_BRIDGE.put_frame(camera_id, frame)   # push to WS
        except Exception as e:
            logger.error(f"[CameraWorker] Cam {camera_id} frame error: {e}")
            time.sleep(0.1)

    cam.release()
    from app.camera_registry import CAMERA_PROCESSORS
    CAMERA_PROCESSORS.pop(camera_id, None)
    logger.info(f"[CameraWorker] Cam {camera_id} thread stopped")


def select_camera_target(camera_id: int, track_id: str) -> bool:
    with _lock:
        state = _running_cameras.get(camera_id)
        cam = state.get("processor") if state else None

    if not cam:
        return False

    cam.target_manager.select_target(track_id)
    return True
