"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/target_manager.py
  Purpose : Click-to-lock target — highlights selected object.

  FIXES:
    - _try_select_target: `return` was outside the `if` block
      — caused it to exit after checking only the first object
      regardless of whether it matched. Fixed: return is now
      correctly inside the `if x1<=cx<=x2` block.
    - Uses track.display_id (global if available, else local)
      so the info panel shows the correct ID.
    - get() method on TrackResult now used safely everywhere.
=============================================================
"""

import cv2, numpy as np, logging, time
from typing import Optional, Tuple

logger = logging.getLogger("TargetManager")


class TargetManager:

    TARGET_LOST_TIMEOUT = 5.0
    BLINK_INTERVAL      = 0.5

    def __init__(self, camera_id: int):
        self.camera_id    = camera_id
        self.target_id    : Optional[str]   = None
        self.target_bbox  : Optional[Tuple] = None
        self.target_class : Optional[str]   = None
        self.target_conf  : float           = 0.0
        self.target_age   : int             = 0
        self._pending_click: Optional[Tuple[int,int]] = None
        self._last_seen    = time.time()
        self._blink_state  = True
        self._blink_timer  = time.time()
        logger.info(f"[Camera-{camera_id}] TargetManager ready.")

    # ── Mouse callback ────────────────────────────────────────

    def on_mouse_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._pending_click = (x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.clear_target()

    # ── Update ────────────────────────────────────────────────

    def update(self, tracked_objects: list, frame: np.ndarray):
        if self._pending_click:
            cx, cy = self._pending_click
            self._pending_click = None
            self._try_select_target(cx, cy, tracked_objects)

        if self.target_id is not None:
            found = False
            for obj in tracked_objects:
                # Match against both local and global ID
                obj_display = obj.get("global_id") or obj["id"]
                if str(obj_display) == str(self.target_id) or \
                   str(obj["id"]) == str(self.target_id):
                    self.target_bbox  = obj["bbox"]
                    self.target_class = obj.get("class_name", "object")
                    self.target_conf  = float(obj.get("confidence", 0.0))
                    self.target_age   = int(obj.get("age", 0))
                    self._last_seen   = time.time()
                    found = True
                    break

            if not found:
                if time.time() - self._last_seen > self.TARGET_LOST_TIMEOUT:
                    logger.info(f"[Cam{self.camera_id}] Target {self.target_id} lost — cleared.")
                    self.clear_target()

        if time.time() - self._blink_timer > self.BLINK_INTERVAL:
            self._blink_state = not self._blink_state
            self._blink_timer  = time.time()

    # ── Draw ──────────────────────────────────────────────────

    def draw(self, frame: np.ndarray) -> np.ndarray:
        if self.target_id is None or self.target_bbox is None:
            return frame

        x1,y1,x2,y2 = self.target_bbox
        elapsed      = time.time() - self._last_seen
        is_lost      = elapsed > 1.0

        box_col   = (0,140,255) if is_lost else (0,0,255)
        label_col = (0,100,200) if is_lost else (0,0,200)

        cv2.rectangle(frame,(x1,y1),(x2,y2),box_col,2)

        # Corner brackets
        L=16; TH=3
        for ox,oy,hx,hy,vx,vy in [
            (x1,y1, x1+L,y1, x1,y1+L),
            (x2,y1, x2-L,y1, x2,y1+L),
            (x1,y2, x1+L,y2, x1,y2-L),
            (x2,y2, x2-L,y2, x2,y2-L),
        ]:
            cv2.line(frame,(ox,oy),(hx,hy),box_col,TH)
            cv2.line(frame,(ox,oy),(vx,vy),box_col,TH)

        if self._blink_state:
            lbl = (f"SEARCHING {self.target_id} ({elapsed:.1f}s)"
                   if is_lost else f"TARGET: {self.target_id}")
            font = cv2.FONT_HERSHEY_SIMPLEX; fs=0.50
            (tw,th),_ = cv2.getTextSize(lbl,font,fs,1)
            by1=max(y1-th-12,0); by2=by1+th+8
            cv2.rectangle(frame,(x1,by1),(x1+tw+10,by2),label_col,-1)
            cv2.putText(frame,lbl,(x1+5,by2-4),font,fs,
                        (255,255,255),1,cv2.LINE_AA)

        if not is_lost and self.target_class:
            self._draw_panel(frame)

        return frame

    def _draw_panel(self, frame):
        h,w = frame.shape[:2]; font=cv2.FONT_HERSHEY_SIMPLEX; fs=0.38
        lines = [f"ID: {self.target_id}",
                 f"Class: {self.target_class or 'unknown'}",
                 f"Conf: {self.target_conf:.0%}",
                 f"Age: {self.target_age} fr"]
        max_w = max(cv2.getTextSize(l,font,fs,1)[0][0] for l in lines)
        lh=16; pad=6; pw=max_w+pad*2; ph=lh*len(lines)+pad*2
        px1=w-pw-6; py1=6; px2=w-6; py2=py1+ph
        ov=frame.copy()
        cv2.rectangle(ov,(px1,py1),(px2,py2),(20,20,20),-1)
        cv2.addWeighted(ov,0.75,frame,0.25,0,frame)
        cv2.rectangle(frame,(px1,py1),(px2,py2),(0,0,200),1)
        for i,line in enumerate(lines):
            cy = py1+pad+(i+1)*lh-3
            cv2.putText(frame,line,(px1+pad,cy),font,fs,
                        (200,200,200),1,cv2.LINE_AA)

    # ── Helpers ───────────────────────────────────────────────

    def _try_select_target(self, cx, cy, tracked_objects):
        for obj in tracked_objects:
            x1,y1,x2,y2 = obj["bbox"]
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                # Use global_id as target ID if available
                self.target_id    = obj.get("global_id") or obj["id"]
                self.target_bbox  = obj["bbox"]
                self.target_class = obj.get("class_name","object")
                self.target_conf  = float(obj.get("confidence",0.0))
                self.target_age   = int(obj.get("age",0))
                self._last_seen   = time.time()
                logger.info(f"[Cam{self.camera_id}] Target: {self.target_id}")
                return  # ← FIX: return is INSIDE the if block

        # Only reached if no object contained the click
        self.clear_target()

    def clear_target(self):
        self.target_id=None; self.target_bbox=None
        self.target_class=None; self.target_conf=0.0; self.target_age=0

    @property
    def has_target(self): return self.target_id is not None

    def get_target_info(self):
        if not self.has_target: return None
        return {"camera_id": self.camera_id, "target_id": self.target_id,
                "bbox": self.target_bbox, "class_name": self.target_class,
                "confidence": self.target_conf}