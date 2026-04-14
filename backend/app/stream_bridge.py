"""
=============================================================
  File : backend/app/stream_bridge.py
  Purpose : Thread → AsyncIO frame bridge for WebSocket stream.

  BUG FIXED:
    Old code used asyncio.get_event_loop() inside a sync thread
    and stored _loop on the Event object. On Python 3.10+ this
    returns a NEW loop (not the running one), so
    call_soon_threadsafe() never fired — frames never reached
    the WebSocket.

  FIX:
    Store the running loop at subscribe() time (in the async
    context where the loop IS running), then use it from the
    sync put_frame() thread. This is the correct pattern.
=============================================================
"""

import asyncio
import threading
import time
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import cv2


class CameraStreamBridge:

    _instance  = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    o = super().__new__(cls)
                    o._setup()
                    cls._instance = o
        return cls._instance

    def _setup(self):
        self._frames      : Dict[int, Optional[bytes]]                 = {}
        self._timestamps  : Dict[int, float]                           = {}
        # Each subscriber is (asyncio.Event, asyncio.AbstractEventLoop)
        self._subscribers : Dict[int, Set[Tuple[asyncio.Event, object]]] = {}
        self._lock        = threading.Lock()

    # ── Camera thread → write frame ──────────────────────────
    def put_frame(self, camera_id: int, frame: np.ndarray):
        """
        Called from camera thread every frame.
        Encodes to JPEG and notifies all WebSocket subscribers.
        """
        try:
            ok, buf = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, 75]
            )
            if not ok:
                return
            jpeg = buf.tobytes()
        except Exception:
            return

        with self._lock:
            self._frames[camera_id]     = jpeg
            self._timestamps[camera_id] = time.time()

            # Notify all subscribers for this camera
            subs = self._subscribers.get(camera_id, set())
            for ev, loop in list(subs):
                try:
                    # FIX: use the loop stored at subscribe time (correct loop)
                    loop.call_soon_threadsafe(ev.set)
                except Exception:
                    pass

    def get_latest(self, camera_id: int) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(camera_id)

    def active_camera_ids(self) -> List[int]:
        cutoff = time.time() - 5.0
        with self._lock:
            return [
                cid for cid, ts in self._timestamps.items()
                if ts > cutoff
            ]

    def is_active(self, camera_id: int) -> bool:
        cutoff = time.time() - 5.0
        with self._lock:
            return self._timestamps.get(camera_id, 0) > cutoff

    # ── WebSocket → subscribe ────────────────────────────────
    async def subscribe(self, camera_id: int):
        """
        Async generator — yields JPEG bytes as frames arrive.
        Yields b"" as keepalive every 3s if no frame received.

        FIX: capture the running loop HERE (in async context)
        and store it alongside the Event so put_frame() (a sync
        thread) can call call_soon_threadsafe() on the CORRECT loop.
        """
        # ✅ Get the loop while we ARE in the async context
        loop = asyncio.get_running_loop()
        ev   = asyncio.Event()
        sub  = (ev, loop)

        with self._lock:
            if camera_id not in self._subscribers:
                self._subscribers[camera_id] = set()
            self._subscribers[camera_id].add(sub)

        try:
            # Send the latest frame immediately if one exists
            latest = self.get_latest(camera_id)
            if latest:
                yield latest

            while True:
                try:
                    await asyncio.wait_for(ev.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    # keepalive — keeps WebSocket alive when no new frames
                    yield b""
                    continue

                ev.clear()

                jpeg = self.get_latest(camera_id)
                if jpeg:
                    yield jpeg
                else:
                    yield b""

        except Exception as e:
            print(f"[STREAM_BRIDGE] Cam{camera_id} error: {e}")

        finally:
            with self._lock:
                subs = self._subscribers.get(camera_id, set())
                subs.discard(sub)


# ── Singleton ─────────────────────────────────────────────────
STREAM_BRIDGE = CameraStreamBridge()