"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/target_manager.py
  Purpose : Click-to-lock target — highlights selected object.

  FIXES:
    1. Vehicle click broken — two separate fields (active_target
       and target_id) caused mismatch in camera_processor._draw_all.
       Now ONE canonical field: target_id is the source of truth.
       active_target is a property alias for compatibility.

    2. Vehicle ID drift — when a vehicle's global_id changed
       between frames (ReID re-resolve), the lock was lost.
       Fix: store BOTH the global_id AND the local_id at click
       time. update() matches against either one. This means
       clicking a vehicle stays locked even if its G-ID changes.

    3. Click miss on vehicles — large vehicle bboxes were being
       skipped because _try_select_target sorted by order of
       iteration, not by which object is "on top" visually.
       Fix: try smallest-area bbox first (topmost visually).

    4. Info panel now shows vehicle-specific info (color, shape)
       when target is a vehicle class.

    5. Draw panel moved to bottom-left instead of top-right —
       doesn't overlap with camera HUD tag.

    6. SEARCHING grace period: 8s (was 5s) before auto-clear.
       Vehicles often pass behind occluders briefly.
=============================================================
"""

import cv2
import numpy as np
import logging
import time
from typing import Optional, Tuple, List

logger = logging.getLogger("TargetManager")

VEHICLE_CLASS_IDS = {1, 2, 3, 5, 7}


class TargetManager:

    TARGET_LOST_TIMEOUT = 8.0   # seconds before auto-clear (was 5)
    BLINK_INTERVAL      = 0.5

    def __init__(self, camera_id: int):
        self.camera_id = camera_id

        # ── Target state ───────────────────────────────────────
        # target_id: the ID we locked onto (global or local)
        # _local_id: the local DeepSort ID at click time (fallback)
        # Both used for matching — whichever works
        self.target_id   : Optional[str]   = None
        self._local_id   : Optional[str]   = None   # backup match
        self.target_bbox : Optional[Tuple] = None
        self.target_class: Optional[str]   = None
        self.target_conf : float           = 0.0
        self.target_age  : int             = 0

        self._pending_click : Optional[Tuple[int, int]] = None
        self._last_seen     = time.time()
        self._blink_state   = True
        self._blink_timer   = time.time()

        # Extra info for panel
        self._target_color : Optional[str]  = None
        self._target_shape : Optional[str]  = None

        logger.info(f"[Camera-{camera_id}] TargetManager ready.")

    # ── Compat property ───────────────────────────────────────
    @property
    def active_target(self) -> Optional[str]:
        """Alias kept for camera_processor._draw_all compatibility."""
        return self.target_id

    # ── Mouse callback ────────────────────────────────────────

    def on_mouse_click(self, event, x: int, y: int, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._pending_click = (x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.clear_target()
            logger.info(f"[Cam{self.camera_id}] Target cleared by right-click.")

    # ── Update ────────────────────────────────────────────────

    def update(self, tracked_objects: list, frame: np.ndarray):
        # Handle pending click
        if self._pending_click is not None:
            cx, cy = self._pending_click
            self._pending_click = None
            self._try_select_target(cx, cy, tracked_objects)

        # Refresh if locked
        if self.target_id is not None:
            found = False
            for obj in tracked_objects:
                obj_global = obj.get("global_id")
                obj_local  = obj["id"]

                # Match against global ID OR local ID (vehicle fix)
                matched = (
                    str(obj_global) == str(self.target_id) or
                    str(obj_local)  == str(self.target_id) or
                    (self._local_id and str(obj_local) == str(self._local_id))
                )

                if matched:
                    self.target_bbox  = obj["bbox"]
                    self.target_class = obj.get("class_name", "object")
                    self.target_conf  = float(obj.get("confidence", 0.0))
                    self.target_age   = int(obj.get("age", 0))
                    # Keep target_id as global if now available
                    if obj_global and obj_global != self.target_id:
                        self.target_id = obj_global
                    self._last_seen = time.time()
                    found = True
                    break

            if not found:
                elapsed = time.time() - self._last_seen
                if elapsed > self.TARGET_LOST_TIMEOUT:
                    logger.info(
                        f"[Cam{self.camera_id}] Target {self.target_id} "
                        f"lost after {elapsed:.0f}s — cleared."
                    )
                    self.clear_target()

        # Blink
        if time.time() - self._blink_timer > self.BLINK_INTERVAL:
            self._blink_state = not self._blink_state
            self._blink_timer = time.time()

    # ── Draw ──────────────────────────────────────────────────

    def draw(self, frame: np.ndarray) -> np.ndarray:
        if self.target_id is None or self.target_bbox is None:
            return frame

        x1, y1, x2, y2 = self.target_bbox
        elapsed = time.time() - self._last_seen
        is_lost = elapsed > 1.0

        # Color scheme
        if is_lost:
            box_col   = (0, 140, 255)   # orange = searching
            label_col = (0, 100, 200)
        else:
            is_vehicle = self.target_class in (
                "car", "truck", "bus", "motorcycle", "bicycle"
            )
            if is_vehicle:
                box_col   = (0, 100, 255)   # deep orange for vehicle target
                label_col = (0, 60, 180)
            else:
                box_col   = (0, 0, 255)     # red for person target
                label_col = (0, 0, 200)

        # Outer box
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 2)

        # Corner brackets — the "locked" visual
        L = 18; TH = 3
        corners = [
            ((x1, y1), (x1+L, y1), (x1, y1+L)),
            ((x2, y1), (x2-L, y1), (x2, y1+L)),
            ((x1, y2), (x1+L, y2), (x1, y2-L)),
            ((x2, y2), (x2-L, y2), (x2, y2-L)),
        ]
        for origin, hpt, vpt in corners:
            cv2.line(frame, origin, hpt, box_col, TH)
            cv2.line(frame, origin, vpt, box_col, TH)

        # Blinking label above box
        if self._blink_state:
            if is_lost:
                lbl = f"SEARCHING {self.target_id} ({elapsed:.1f}s)"
            else:
                lbl = f"TARGET: {self.target_id}"
            font = cv2.FONT_HERSHEY_SIMPLEX; fs = 0.50
            (tw, th), _ = cv2.getTextSize(lbl, font, fs, 1)
            by1 = max(y1 - th - 12, 0); by2 = by1 + th + 8
            cv2.rectangle(frame, (x1, by1), (x1+tw+10, by2), label_col, -1)
            cv2.putText(frame, lbl, (x1+5, by2-4),
                        font, fs, (255, 255, 255), 1, cv2.LINE_AA)

        # Info panel (bottom-left, avoids HUD overlap)
        if not is_lost and self.target_class:
            self._draw_panel(frame)

        return frame

    def _draw_panel(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX; fs = 0.38

        is_vehicle = self.target_class in (
            "car", "truck", "bus", "motorcycle", "bicycle"
        )

        lines = [f"ID: {self.target_id}"]
        if is_vehicle:
            lines.append(f"Type: {self.target_class}")
            if self._target_color:
                lines.append(f"Color: {self._target_color}")
            if self._target_shape:
                lines.append(f"Shape: {self._target_shape}")
        else:
            lines.append(f"Class: {self.target_class or 'unknown'}")
        lines.append(f"Conf: {self.target_conf:.0%}")
        lines.append(f"Age: {self.target_age} fr")

        max_w = max(cv2.getTextSize(l, font, fs, 1)[0][0] for l in lines)
        lh = 16; pad = 6
        pw  = max_w + pad * 2
        ph  = lh * len(lines) + pad * 2

        # Position: bottom-left
        px1 = 6
        py1 = h - ph - 34   # above HUD bar (28px) + gap
        px2 = px1 + pw
        py2 = py1 + ph

        if py1 < 0: py1 = 6; py2 = py1 + ph   # clamp to top

        overlay = frame.copy()
        cv2.rectangle(overlay, (px1, py1), (px2, py2), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

        border_color = (0, 100, 255) if is_vehicle else (0, 0, 200)
        cv2.rectangle(frame, (px1, py1), (px2, py2), border_color, 1)

        for i, line in enumerate(lines):
            cy = py1 + pad + (i + 1) * lh - 3
            color = (180, 220, 255) if (i == 0) else (200, 200, 200)
            cv2.putText(frame, line, (px1 + pad, cy),
                        font, fs, color, 1, cv2.LINE_AA)

    # ── Selection ─────────────────────────────────────────────

    def _try_select_target(self, cx: int, cy: int, tracked_objects: list):
        """
        Find which tracked object was clicked.

        FIX: Sort by bbox area (smallest first) so topmost/smallest
        objects are preferred when bboxes overlap. This fixes
        clicking a car when a person is on top of it — you get
        the person (smaller box, visually on top).

        FIX: Store BOTH global_id and local_id at click time
        so vehicle tracking stays locked even if global_id
        re-resolves to a different value next frame.
        """
        # Sort by area ascending — smallest bbox = visually on top
        sorted_objects = sorted(
            tracked_objects,
            key=lambda o: (
                (o["bbox"][2] - o["bbox"][0]) * (o["bbox"][3] - o["bbox"][1])
            )
        )

        for obj in sorted_objects:
            x1, y1, x2, y2 = obj["bbox"]

            # Expand click zone slightly for vehicles (easier to click)
            is_veh = obj.get("class_id", -1) in VEHICLE_CLASS_IDS
            margin = 6 if is_veh else 2

            if (x1 - margin) <= cx <= (x2 + margin) and \
               (y1 - margin) <= cy <= (y2 + margin):

                # Lock: use global_id if available, else local
                global_id = obj.get("global_id")
                local_id  = obj["id"]

                self.target_id    = global_id if global_id else local_id
                self._local_id    = local_id   # backup for re-match
                self.target_bbox  = obj["bbox"]
                self.target_class = obj.get("class_name", "object")
                self.target_conf  = float(obj.get("confidence", 0.0))
                self.target_age   = int(obj.get("age", 0))
                self._last_seen   = time.time()
                self._target_color = None
                self._target_shape = None

                logger.info(
                    f"[Cam{self.camera_id}] Locked: {self.target_id} "
                    f"({self.target_class}) local={local_id}"
                )
                return  # return INSIDE if block — correct

        # Click missed all objects — clear lock
        logger.info(
            f"[Cam{self.camera_id}] Click ({cx},{cy}) missed — cleared."
        )
        self.clear_target()

    def update_vehicle_info(self, color: str, shape: str):
        """Called by camera_processor to update panel info for vehicle target."""
        self._target_color = color
        self._target_shape = shape

    def clear_target(self):
        self.target_id    = None
        self._local_id    = None
        self.target_bbox  = None
        self.target_class = None
        self.target_conf  = 0.0
        self.target_age   = 0
        self._target_color = None
        self._target_shape = None

    def select_target(self, track_id: str):
        """Programmatic selection (e.g. from API)."""
        self.target_id = track_id

    @property
    def has_target(self) -> bool:
        return self.target_id is not None

    def get_target_info(self) -> Optional[dict]:
        if not self.has_target: return None
        return {
            "camera_id"  : self.camera_id,
            "target_id"  : self.target_id,
            "bbox"       : self.target_bbox,
            "class_name" : self.target_class,
            "confidence" : self.target_conf,
        }