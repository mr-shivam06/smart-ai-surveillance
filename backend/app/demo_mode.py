"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/demo_mode.py
  Purpose : Demo mode for interviews and presentations.

  WHAT DEMO MODE DOES:
    Replaces live camera feeds with pre-recorded video files.
    Injects hardcoded alert events at specific timestamps so
    the demo always looks impressive regardless of live scene.

  HOW TO USE:
    1. Place video files at:
         backend/videos/demo_cam1.mp4
         backend/videos/demo_cam2.mp4
       (any .mp4 works — use your own recordings)

    2. Set DEMO_MODE = True in backend/.env
       or set environment variable: set DEMO_MODE=1

    3. Run normally:
         python app/main.py
       → Uses video files instead of cameras.
       → Events fire automatically at scheduled timestamps.

  INJECTED EVENTS (hardcoded timeline):
    t=10s  → Loitering alert (person stationary)
    t=20s  → Ambulance detected (white vehicle)
    t=30s  → Crowd detected (8+ persons)
    t=45s  → Accident detected (2 vehicles overlapping)
    t=60s  → Fire detected (critical alert + red tint)
    t=75s  → Zone intrusion (restricted area)
    t=90s  → Video loops → events repeat

  DEMO VIDEO SOURCES (free):
    https://www.pexels.com/search/videos/traffic/
    https://www.videvo.net/video/traffic-camera/
    Download any traffic/street footage as demo_cam1.mp4
=============================================================
"""

import os
import time
import threading
import logging
from typing import List, Dict

logger = logging.getLogger("DemoMode")

# ── Config ────────────────────────────────────────────────────
DEMO_VIDEO_DIR = "videos"
DEMO_VIDEOS    = {
    1: os.path.join(DEMO_VIDEO_DIR, "demo_cam2.mp4"),
    2: os.path.join(DEMO_VIDEO_DIR, "demo_cam8.mp4"),
}

# Check if demo mode is enabled
DEMO_MODE = (
    os.getenv("DEMO_MODE", "0").strip().lower()
    in ("1", "true", "yes", "on")
)


# ── Event timeline ────────────────────────────────────────────

DEMO_EVENTS: List[Dict] = [
    {
        "time"      : 10,
        "alert_type": "LOITERING",
        "camera_id" : 1,
        "message"   : "[DEMO] Stationary person detected for 60s",
        "metadata"  : {"track_id": "G-001", "dwell_s": 60, "obj_type": "person"},
    },
    {
        "time"      : 20,
        "alert_type": "AMBULANCE_DETECTED",
        "camera_id" : 2,
        "message"   : "[DEMO] Ambulance detected — ID G-005",
        "metadata"  : {"track_id": "G-005"},
    },
    {
        "time"      : 30,
        "alert_type": "CROWD_DETECTED",
        "camera_id" : 1,
        "message"   : "[DEMO] Crowd: 9 persons detected",
        "metadata"  : {"count": 9},
    },
    {
        "time"      : 45,
        "alert_type": "ACCIDENT_DETECTED",
        "camera_id" : 1,
        "message"   : "[DEMO] Accident: G-003 ↔ G-004",
        "metadata"  : {"vehicles": ["G-003", "G-004"], "snapshot": "demo"},
    },
    {
        "time"      : 60,
        "alert_type": "FIRE_DETECTED",
        "camera_id" : 1,
        "message"   : "[DEMO] FIRE detected on Camera 1",
        "metadata"  : {"camera_id": 1, "method": "Demo"},
    },
    {
        "time"      : 75,
        "alert_type": "ZONE_ENTER",
        "camera_id" : 2,
        "message"   : "[DEMO] Person G-007 entered restricted zone_B",
        "metadata"  : {"track_id": "G-007", "zone_name": "zone_B", "zone_type": "restricted"},
    },
]


class DemoEventInjector:
    """
    Fires demo alerts at scheduled timestamps.
    Loops every 90s so demo keeps running.
    """

    def __init__(self):
        self._start_time = None
        self._fired      = set()

    def start(self):
        self._start_time = time.time()
        self._fired.clear()
        t = threading.Thread(target=self._loop, daemon=True, name="DemoEvents")
        t.start()
        logger.info("[DemoMode] Event injector started.")

    def _loop(self):
        from app.alert_system import ALERT_SYSTEM
        LOOP_DURATION = 90

        while True:
            elapsed = (time.time() - self._start_time) % LOOP_DURATION
            cycle   = int((time.time() - self._start_time) // LOOP_DURATION)

            for event in DEMO_EVENTS:
                key = (cycle, event["alert_type"])
                if elapsed >= event["time"] and key not in self._fired:
                    self._fired.add(key)
                    ALERT_SYSTEM.fire(
                        alert_type = event["alert_type"],
                        camera_id  = event["camera_id"],
                        message    = event["message"],
                        metadata   = event.get("metadata", {}),
                    )
                    logger.info(
                        f"[DemoMode] Injected: {event['alert_type']} "
                        f"at t={elapsed:.0f}s"
                    )

            time.sleep(0.5)


def get_demo_source(camera_id: int):
    """
    Returns the demo video path for a camera ID.
    Falls back to webcam if video file doesn't exist.
    """
    path = DEMO_VIDEOS.get(camera_id)
    if path and os.path.exists(path):
        logger.info(f"[DemoMode] Cam {camera_id} using video: {path}")
        return path

    logger.warning(
        f"[DemoMode] Demo video not found for Cam {camera_id} at {path}. "
        f"Falling back to webcam. "
        f"Place a video file at: {path}"
    )
    return camera_id - 1   # fallback: webcam 0, 1, 2...


# ── Singleton injector ────────────────────────────────────────
DEMO_INJECTOR = DemoEventInjector()