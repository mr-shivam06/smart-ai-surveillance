"""
=============================================================
  File : backend/app/api/routes_stream.py
  Purpose : WebSocket endpoint for live camera JPEG streams.

  FIX: /active route must come BEFORE /{camera_id} route —
  otherwise FastAPI matches "active" as a camera_id integer
  and throws a validation error.
=============================================================
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import Response

from app.stream_bridge import STREAM_BRIDGE
from app.core.security import decode_token

logger = logging.getLogger("StreamRoutes")
router = APIRouter()


def _verify_ws_token(token: str) -> bool:
    if not token:
        return False
    try:
        payload = decode_token(token)
        return bool(payload.get("sub"))
    except Exception:
        return False


# ── IMPORTANT: /active MUST be before /{camera_id} ───────────
@router.get("/active")
async def active_streams(token: str = Query("")):
    """List camera IDs currently streaming."""
    if not _verify_ws_token(token):
        raise HTTPException(401, "Unauthorized")
    return {"active_cameras": STREAM_BRIDGE.active_camera_ids()}


@router.get("/{camera_id}/snapshot")
async def snapshot(camera_id: int, token: str = Query("")):
    """Latest JPEG frame for a camera."""
    if not _verify_ws_token(token):
        raise HTTPException(401, "Unauthorized")
    jpeg = STREAM_BRIDGE.get_latest(camera_id)
    if not jpeg:
        raise HTTPException(404, f"No frame available for camera {camera_id}")
    return Response(content=jpeg, media_type="image/jpeg")


@router.websocket("/{camera_id}")
async def camera_stream(
    websocket : WebSocket,
    camera_id : int,
    token     : str = Query(""),
):
    """
    Live JPEG stream for one camera.
    Frontend usage:
      const ws = new WebSocket('ws://localhost:5173/stream/1?token=<jwt>')
      ws.binaryType = 'blob'
      ws.onmessage = e => {
        if (e.data.size === 0) return   // keepalive — skip
        img.src = URL.createObjectURL(e.data)
      }
    """
    # Accept first — required before any auth rejection
    await websocket.accept()

    if not _verify_ws_token(token):
        logger.warning(f"[Stream] Unauthorized → Cam {camera_id}")
        await websocket.close(code=4001)
        return

    logger.info(f"[Stream] Client connected → Cam {camera_id}")

    try:
        async for jpeg in STREAM_BRIDGE.subscribe(camera_id):
            try:
                await websocket.send_bytes(jpeg if jpeg else b"")
            except Exception:
                break

    except WebSocketDisconnect:
        logger.info(f"[Stream] Disconnected ← Cam {camera_id}")

    except Exception as e:
        logger.error(f"[Stream] Cam {camera_id} error: {e}")

    finally:
        logger.info(f"[Stream] Cleanup Cam {camera_id}")