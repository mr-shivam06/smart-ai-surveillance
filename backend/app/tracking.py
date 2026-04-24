"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/tracking.py
  Purpose : DeepSORT per-camera tracker — all 80 COCO classes.

  GHOST BOX + FPS FIX (THE MAIN CULPRIT):
    max_age was 100 — DeepSort kept 100 dead/ghost tracks alive
    every frame, running Kalman prediction on each one.
    At 5 people visible × 2 cameras, that's ~190 ghost track
    predictions every frame eating CPU and producing boxes.

    max_age=25  → ghost tracks die in ~1s at 25fps ✓
    n_init=2    → tracks confirmed after 2 frames (was 5 — meant
                  objects were invisible for 5 frames before appearing) ✓
    max_iou_distance=0.65 → tighter matching, fewer ID switches ✓
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
    Supports: track.id  track["id"]  track.get("id", default)
    """

    __slots__ = (
        "id", "global_id", "bbox", "class_id", "class_name",
        "confidence", "age", "centroid", "face_id",
    )

    def __init__(
        self,
        track_id   : str,
        bbox       : Tuple[int, int, int, int],
        class_id   : int   = -1,
        class_name : str   = "object",
        confidence : float = 0.0,
        age        : int   = 0,
    ):
        self.id         = track_id
        self.global_id  = None
        self.bbox       = bbox
        self.class_id   = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.age        = age
        self.face_id    = None
        x1, y1, x2, y2 = bbox
        self.centroid: Tuple[int, int] = ((x1+x2)//2, (y1+y2)//2)

    def __getitem__(self, key):          return getattr(self, key)
    def __contains__(self, key):         return hasattr(self, key)
    def get(self, key, default=None):    return getattr(self, key, default)

    @property
    def display_id(self) -> str:
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
    DeepSORT wrapper — tracks ALL 80 COCO classes.

    KEY FIXES for ghost boxes and FPS:
      max_age=25   — was 100. Ghost tracks now clear in ~1s.
                     100 caused ~75+ dead track predictions/frame.
      n_init=2     — was 5. Objects appear after 2 frames not 5.
      MIN_CONF=0.40 — pre-filter before DeepSort entry.
    """

    MIN_CONF = 0.40   # filter before DeepSort — main ghost box source

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._build_tracker()
        self._class_names   : Dict[int, str]         = {}
        self._active_tracks : Dict[str, TrackResult] = {}
        self._hist          : Dict[str, deque]        = {}
        logger.info(
            f"[Camera-{camera_id}] PersonTracker ready "
            f"(max_age=25, n_init=2, CPU)"
        )

    def _build_tracker(self):
        self.tracker = DeepSort(
            max_age          = 25,    # FIX: was 100 — huge CPU waste + ghost boxes
            n_init           = 2,     # FIX: was 5 — 5-frame invisible period
            max_iou_distance = 0.65,  # slightly tighter — fewer ID switches
            embedder         = "mobilenet",
            half             = False, # CPU mode
            bgr              = True,
        )

    def update_tracks(
        self,
        detections : list,
        frame      : np.ndarray,
    ) -> List[TrackResult]:

        # Pre-filter — stops weak detections entering tracker
        dets = [d for d in detections if d[1] >= self.MIN_CONF]
        raw  = self.tracker.update_tracks(
            dets if dets else [], frame=frame
        )

        results : List[TrackResult] = []
        now     = time.time()

        for track in raw:
            if not track.is_confirmed():
                continue

            try:
                l, t, r, b = track.to_ltrb()
                bbox = (max(0, int(l)), max(0, int(t)), int(r), int(b))
            except Exception:
                continue

            x1, y1, x2, y2 = bbox
            if (x2-x1) < 10 or (y2-y1) < 10:
                continue

            local_id = f"C{self.camera_id}-ID{track.track_id}"

            # Robust class extraction
            class_id = -1
            raw_cls  = (getattr(track, "det_class", None) or
                        getattr(track, "cls", None))
            if raw_cls is not None:
                try: class_id = int(raw_cls)
                except: pass

            confidence = 0.0
            raw_conf   = (getattr(track, "det_conf", None) or
                          getattr(track, "conf", None))
            if raw_conf is not None:
                try: confidence = float(raw_conf)
                except: pass

            class_name = (
                self._class_names.get(class_id, f"cls_{class_id}")
                if class_id >= 0 and self._class_names else "object"
            )

            age = int(getattr(track, "age", 0) or 0)

            tr = TrackResult(local_id, bbox, class_id, class_name,
                             confidence, age)
            results.append(tr)

            # Centroid history for velocity (accident detection)
            if local_id not in self._hist:
                self._hist[local_id] = deque(maxlen=30)
            self._hist[local_id].append((now, tr.centroid[0], tr.centroid[1]))

        # Prune dead history immediately
        alive = {r.id for r in results}
        for tid in list(self._hist):
            if tid not in alive:
                del self._hist[tid]

        self._active_tracks = {r.id: r for r in results}
        return results

    def get_velocity(self, local_id: str) -> float:
        """Pixels/second. Used for accident detection."""
        hist = self._hist.get(local_id)
        if not hist or len(hist) < 2: return 0.0
        s = list(hist)[-10:]
        if len(s) < 2: return 0.0
        t0, x0, y0 = s[0]; t1, x1, y1 = s[-1]
        dt = t1 - t0
        if dt < 1e-6: return 0.0
        return ((x1-x0)**2 + (y1-y0)**2)**0.5 / dt

    def set_class_names(self, names: Dict[int, str]):
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