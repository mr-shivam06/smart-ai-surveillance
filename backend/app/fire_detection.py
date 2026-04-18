"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/fire_detection.py
  Purpose : Real-time fire and smoke detection.

  TWO-TIER DETECTION STRATEGY:

  Tier 1 — YOLOv8 fine-tuned model (if available):
    Uses a YOLOv8n model fine-tuned on the D-Fire dataset
    (21k images, fire + smoke classes). Place the model at:
      backend/fire_model.pt
    If present, used automatically. Classes: 0=fire, 1=smoke.
    Download from: https://github.com/gaiasd/DFireDataset
    or train on Colab: 50 epochs, yolov8n base, 320px input.

  Tier 2 — HSV color heuristic (always available, no model):
    Detects fire-colored regions (red/orange/yellow HSV ranges)
    and smoke-colored regions (gray, low-saturation, large area).
    Runs on every 3rd frame. Fast (~2ms), CPU-only.
    Higher false positive rate than ML but catches obvious fires.

  INTEGRATION:
    Called from BehaviorAnalyzer.update() → fires FIRE_DETECTED
    or SMOKE_DETECTED alert via ALERT_SYSTEM.
    camera_processor.py applies red tint overlay when active.

  ALERTS:
    SMOKE_DETECTED — HIGH severity (early warning)
    FIRE_DETECTED  — CRITICAL severity, auto-saves snapshot

  VISUAL:
    camera_processor draws:
      - Orange bbox around fire region
      - Gray bbox around smoke region
      - Red tint on entire frame when fire confirmed (toggle)
=============================================================
"""

import cv2
import logging
import os
import time
import numpy as np
from typing import List, Optional, Tuple

from app.alert_system import ALERT_SYSTEM

logger = logging.getLogger("FireDetection")

FIRE_MODEL_PATH = "backend/fire_model.pt"
SNAPSHOT_DIR    = "backend/snapshots"
PROCESS_EVERY   = 3    # run every N frames
MIN_FIRE_AREA   = 800  # px² — ignore tiny sparks/reflections
MIN_SMOKE_AREA  = 3000 # px² — smoke patches must be larger


# ── HSV color ranges ──────────────────────────────────────────
# Fire: red-orange-yellow hues, high value, medium-high saturation
_FIRE_RANGES = [
    ((0,   120, 180), (15,  255, 255)),   # red-orange
    ((15,  120, 180), (35,  255, 255)),   # orange-yellow
    ((165, 120, 180), (180, 255, 255)),   # red wrap-around
]

# Smoke: low saturation, mid-high value (gray cloud)
_SMOKE_LOW  = (0,   0,  80)
_SMOKE_HIGH = (180, 60, 220)


def _load_fire_model():
    """Try to load fine-tuned fire/smoke model. Returns (model, True) or (None, False)."""
    if not os.path.exists(FIRE_MODEL_PATH):
        logger.info(
            f"[FireDetection] No fine-tuned model at {FIRE_MODEL_PATH}. "
            f"Using HSV heuristic only. "
            f"Place a D-Fire-trained YOLOv8n at {FIRE_MODEL_PATH} for ML detection."
        )
        return None, False
    try:
        from ultralytics import YOLO
        model = YOLO(FIRE_MODEL_PATH)
        model.fuse()
        logger.info(f"[FireDetection] Fine-tuned fire model loaded from {FIRE_MODEL_PATH}")
        return model, True
    except Exception as e:
        logger.warning(f"[FireDetection] Failed to load fire model: {e}. Using HSV fallback.")
        return None, False


_FIRE_MODEL, _USE_ML = _load_fire_model()


# ── Result dataclass ──────────────────────────────────────────

class FireEvent:
    def __init__(
        self,
        event_type  : str,    # "fire" or "smoke"
        bbox        : Tuple,  # (x1, y1, x2, y2) in frame coords
        confidence  : float,
        camera_id   : int,
    ):
        self.event_type = event_type
        self.bbox       = bbox
        self.confidence = confidence
        self.camera_id  = camera_id
        self.timestamp  = time.time()


# ── Fire Detector ─────────────────────────────────────────────

class FireDetector:
    """
    Per-camera fire and smoke detector.
    Integrated into BehaviorAnalyzer — call update() each frame.
    Results available via .active_fire and .active_smoke properties.
    """

    CONFIRM_FRAMES = 2   # consecutive detections to confirm

    def __init__(self, camera_id: int):
        self.camera_id     = camera_id
        self._frame_count  = 0
        self._fire_count   = 0    # consecutive fire frames
        self._smoke_count  = 0    # consecutive smoke frames
        self._alerted_fire = False
        self._alerted_smoke= False
        self._active_events: List[FireEvent] = []
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # ── Public ────────────────────────────────────────────────

    def update(self, frame: np.ndarray) -> List[FireEvent]:
        """
        Run fire/smoke detection. Returns list of active events.
        Call every frame — internally skips frames for performance.
        """
        self._frame_count += 1
        if self._frame_count % PROCESS_EVERY != 0:
            return self._active_events

        if _USE_ML:
            events = self._detect_ml(frame)
        else:
            events = self._detect_hsv(frame)

        self._process_events(events, frame)
        self._active_events = events
        return events

    @property
    def has_fire(self) -> bool:
        return any(e.event_type == "fire" for e in self._active_events)

    @property
    def has_smoke(self) -> bool:
        return any(e.event_type == "smoke" for e in self._active_events)

    @property
    def is_alert_active(self) -> bool:
        return self.has_fire or self.has_smoke

    # ── ML detection ──────────────────────────────────────────

    def _detect_ml(self, frame: np.ndarray) -> List[FireEvent]:
        try:
            small = cv2.resize(frame, (320, 320))
            results = _FIRE_MODEL(small, imgsz=320, conf=0.45, verbose=False)[0]
            events = []
            h, w = frame.shape[:2]
            sx = w / 320; sy = h / 320

            for box in results.boxes:
                cls  = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                # Scale back to original frame coords
                bbox = (int(x1*sx), int(y1*sy), int(x2*sx), int(y2*sy))
                area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])

                if cls == 0 and area >= MIN_FIRE_AREA:
                    events.append(FireEvent("fire", bbox, conf, self.camera_id))
                elif cls == 1 and area >= MIN_SMOKE_AREA:
                    events.append(FireEvent("smoke", bbox, conf, self.camera_id))

            return events
        except Exception as e:
            logger.debug(f"[Fire ML] {e}")
            return self._detect_hsv(frame)

    # ── HSV heuristic ─────────────────────────────────────────

    def _detect_hsv(self, frame: np.ndarray) -> List[FireEvent]:
        """
        Color-based fire/smoke detection.
        Fire: red/orange/yellow pixels clustered in region.
        Smoke: gray low-saturation region of significant area.
        """
        events = []
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (240, 180))
        hsv   = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        sx    = w / 240; sy = h / 180

        # ── Fire mask ─────────────────────────────────────────
        fire_mask = np.zeros(small.shape[:2], dtype=np.uint8)
        for lo, hi in _FIRE_RANGES:
            fire_mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_CLOSE, kernel)
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN,  kernel)

        fire_contours, _ = cv2.findContours(
            fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in fire_contours:
            area = cv2.contourArea(cnt)
            if area < (MIN_FIRE_AREA / (sx * sy)):
                continue
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Scale back to original resolution
            bbox = (int(x*sx), int(y*sy), int((x+cw)*sx), int((y+ch)*sy))
            conf = min(0.9, area / (240 * 180) * 15)   # rough confidence
            events.append(FireEvent("fire", bbox, conf, self.camera_id))

        # ── Smoke mask ────────────────────────────────────────
        smoke_mask = cv2.inRange(hsv,
                                 np.array(_SMOKE_LOW),
                                 np.array(_SMOKE_HIGH))

        # Smoke should be large and diffuse — erode small regions
        smoke_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, smoke_kernel)

        smoke_contours, _ = cv2.findContours(
            smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in smoke_contours:
            area = cv2.contourArea(cnt)
            if area < (MIN_SMOKE_AREA / (sx * sy)):
                continue
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Only flag smoke if there's also fire nearby (reduces false positives)
            if not events:
                continue
            bbox = (int(x*sx), int(y*sy), int((x+cw)*sx), int((y+ch)*sy))
            conf = min(0.7, area / (240 * 180) * 8)
            events.append(FireEvent("smoke", bbox, conf, self.camera_id))

        return events

    # ── Alert processing ──────────────────────────────────────

    def _process_events(self, events: List[FireEvent], frame: np.ndarray):
        has_fire  = any(e.event_type == "fire"  for e in events)
        has_smoke = any(e.event_type == "smoke" for e in events)

        # Fire confirmation
        if has_fire:
            self._fire_count += 1
            if self._fire_count >= self.CONFIRM_FRAMES and not self._alerted_fire:
                self._alerted_fire = True
                self._save_snapshot(frame, "fire")
                ALERT_SYSTEM.fire(
                    alert_type = "FIRE_DETECTED",
                    camera_id  = self.camera_id,
                    message    = f"FIRE detected on Camera {self.camera_id}",
                    metadata   = {
                        "camera_id"  : self.camera_id,
                        "method"     : "OSNet" if _USE_ML else "HSV",
                        "confidence" : max(e.confidence for e in events
                                          if e.event_type == "fire"),
                    },
                )
                logger.warning(
                    f"[FireDetection] 🔥 FIRE CONFIRMED Cam{self.camera_id}"
                )
        else:
            self._fire_count  = max(0, self._fire_count - 1)
            if self._fire_count == 0:
                self._alerted_fire = False

        # Smoke confirmation
        if has_smoke:
            self._smoke_count += 1
            if self._smoke_count >= self.CONFIRM_FRAMES and not self._alerted_smoke:
                self._alerted_smoke = True
                ALERT_SYSTEM.fire(
                    alert_type = "SMOKE_DETECTED",
                    camera_id  = self.camera_id,
                    message    = f"Smoke detected on Camera {self.camera_id}",
                    metadata   = {
                        "camera_id": self.camera_id,
                        "method"   : "HSV",
                    },
                )
                logger.warning(
                    f"[FireDetection] 💨 SMOKE DETECTED Cam{self.camera_id}"
                )
        else:
            self._smoke_count  = max(0, self._smoke_count - 1)
            if self._smoke_count == 0:
                self._alerted_smoke = False

    def _save_snapshot(self, frame: np.ndarray, event_type: str):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            SNAPSHOT_DIR, f"{event_type}_cam{self.camera_id}_{ts}.jpg"
        )
        try:
            cv2.imwrite(path, frame)
            logger.info(f"[FireDetection] Snapshot saved: {path}")
        except Exception as e:
            logger.error(f"[FireDetection] Snapshot failed: {e}")

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw fire/smoke bboxes on frame.
        Called from camera_processor._draw_all().
        """
        for event in self._active_events:
            x1, y1, x2, y2 = event.bbox

            if event.event_type == "fire":
                color = (0, 60, 255)    # red-orange for fire
                label = f"FIRE {event.confidence:.0%}"
            else:
                color = (160, 160, 160)  # gray for smoke
                label = f"SMOKE {event.confidence:.0%}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            font = cv2.FONT_HERSHEY_SIMPLEX; fs = 0.45
            (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
            by1 = max(y1 - th - 8, 0); by2 = by1 + th + 6
            cv2.rectangle(frame, (x1, by1), (x1+tw+8, by2), color, -1)
            cv2.putText(frame, label, (x1+4, by2-3),
                        font, fs, (255, 255, 255), 1, cv2.LINE_AA)

        return frame