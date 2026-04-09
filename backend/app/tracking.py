"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/tracking.py
  Purpose : DeepSORT per-camera tracker — all 80 COCO classes.

  FIXES:
    - max_age=30 restored (was 12 — killed IDs too fast, main
      cause of flickering/re-assigning IDs every few seconds)
    - n_init=2 restored (was 3 — delayed track confirmation,
      objects appeared without boxes for first 3 frames)
    - global_id declared properly in __init__ (not set externally)
    - Robust class/conf extraction across all DeepSort versions
    - TrackResult.get() added so target_manager dict access works
    - centroid property added for trail drawing and velocity
=============================================================
"""

import logging, time
from collections import deque
from typing import List, Optional, Dict, Tuple
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

logger = logging.getLogger("Tracking")


class TrackResult:
    """
    One confirmed tracked object.
    Supports: track.id, track["id"], track.get("id", default)
    global_id is set by cross_camera_tracker after tracking.
    """

    def __init__(
        self,
        track_id   : str,
        bbox       : Tuple[int,int,int,int],
        class_id   : int   = -1,
        class_name : str   = "object",
        confidence : float = 0.0,
        age        : int   = 0,
    ):
        self.id         = track_id      # local: "C1-ID3"
        self.global_id  = None         # set by CrossCameraTracker
        self.bbox       = bbox
        self.class_id   = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.age        = age

        x1, y1, x2, y2 = bbox
        self.centroid: Tuple[int,int] = ((x1+x2)//2, (y1+y2)//2)

    # ── Access patterns ───────────────────────────────────────

    def __getitem__(self, key):
        return getattr(self, key)

    def __contains__(self, key):
        return hasattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    @property
    def display_id(self) -> str:
        """What to show on screen — global if available, else local."""
        return self.global_id if self.global_id else self.id

    def to_dict(self) -> dict:
        return {
            "id": self.id, "global_id": self.global_id,
            "bbox": self.bbox, "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "age": self.age, "centroid": self.centroid,
        }

    def __repr__(self):
        gid = f"|G={self.global_id}" if self.global_id else ""
        return f"Track({self.id}{gid}|{self.class_name}|age={self.age})"


class PersonTracker:
    """
    DeepSORT wrapper tracking ALL classes.
    Name kept for backward compatibility.

    Config rationale:
      max_age=30  — keep track alive 30 frames (~1s at 30fps)
                    prevents ID loss on brief occlusions
      n_init=2    — confirm track after 2 consecutive frames
                    faster confirmation = fewer missed detections
      max_iou_distance=0.7 — standard, works well for pedestrians
    """

    MIN_CONF = 0.45   # filter weak detections before DeepSORT

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._build_tracker()
        self._class_names  : Dict[int,str]        = {}
        self._active_tracks: Dict[str,TrackResult] = {}
        # centroid history for velocity: track_id → deque[(t,cx,cy)]
        self._hist: Dict[str, deque] = {}
        logger.info(f"[Camera-{camera_id}] PersonTracker ready (max_age=30)")

    def _build_tracker(self):
        self.tracker = DeepSort(
            max_age=30, n_init=2, max_iou_distance=0.7,
            embedder="mobilenet", half=False, bgr=True,
        )

    def update_tracks(self, detections: list, frame: np.ndarray) -> List[TrackResult]:
        # Filter weak detections
        dets = [d for d in detections if d[1] >= self.MIN_CONF]
        raw  = self.tracker.update_tracks(dets if dets else [], frame=frame)

        results: List[TrackResult] = []
        now = time.time()

        for track in raw:
            if not track.is_confirmed():
                continue

            try:
                l,t,r,b = track.to_ltrb()
                bbox = (max(0,int(l)), max(0,int(t)), int(r), int(b))
            except Exception:
                continue

            x1,y1,x2,y2 = bbox
            if (x2-x1) < 10 or (y2-y1) < 10:
                continue

            local_id = f"C{self.camera_id}-ID{track.track_id}"

            # Robust class extraction across DeepSort versions
            class_id = -1
            for attr in ("det_class","class_id","cls","det_cls"):
                v = getattr(track, attr, None)
                if v is not None:
                    try: class_id = int(v); break
                    except: pass

            confidence = 0.0
            for attr in ("det_conf","conf","confidence","det_confidence"):
                v = getattr(track, attr, None)
                if v is not None:
                    try: confidence = float(v); break
                    except: pass

            class_name = (
                self._class_names.get(class_id, f"cls_{class_id}")
                if class_id >= 0 and self._class_names else "object"
            )

            age = int(getattr(track,"age",0) or 0)

            tr = TrackResult(local_id, bbox, class_id, class_name, confidence, age)
            results.append(tr)

            # Centroid history
            if local_id not in self._hist:
                self._hist[local_id] = deque(maxlen=30)
            self._hist[local_id].append((now, tr.centroid[0], tr.centroid[1]))

        # Prune dead tracks from history
        alive = {r.id for r in results}
        for tid in set(self._hist) - alive:
            del self._hist[tid]

        self._active_tracks = {r.id: r for r in results}
        return results

    def get_velocity(self, local_id: str) -> float:
        """Pixels/second over last 10 samples. Used for accident detection."""
        hist = self._hist.get(local_id)
        if not hist or len(hist) < 2: return 0.0
        s = list(hist)[-10:]
        if len(s) < 2: return 0.0
        t0,x0,y0 = s[0]; t1,x1,y1 = s[-1]
        dt = t1-t0
        if dt < 1e-6: return 0.0
        return ((x1-x0)**2+(y1-y0)**2)**0.5 / dt

    def set_class_names(self, names: Dict[int,str]):
        self._class_names = names
        logger.info(f"[Camera-{self.camera_id}] {len(names)} class names loaded")

    def get_track_by_id(self, tid: str) -> Optional[TrackResult]:
        return self._active_tracks.get(tid)

    def reset(self):
        self._build_tracker()
        self._active_tracks.clear()
        self._hist.clear()
        logger.info(f"[Camera-{self.camera_id}] Tracker reset.")

    @property
    def active_count(self): return len(self._active_tracks)
    @property
    def active_tracks(self): return list(self._active_tracks.values())