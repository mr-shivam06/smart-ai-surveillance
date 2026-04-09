"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/vehicle_analysis.py
  Purpose : Lightweight vehicle intelligence.
            Color + shape type only — NO plate OCR.

  WHY NO OCR:
    EasyOCR costs ~200ms per vehicle crop on CPU.
    With 4 cameras × 3 vehicles per frame × every 15 frames,
    that's a 600ms spike every half-second — kills everything.
    Removed permanently. Plate OCR is a Day 14+ feature
    using a dedicated background process if needed.

  WHAT THIS DOES (fast):
    1. Color extraction   — k-means on 50×50 crop → ~3ms
    2. Shape type         — aspect ratio → sedan/SUV/truck/moto
                          → ~0.1ms, no model needed
    3. Vehicle registry   — SQLite persistence per global_id

  CALL ORDER FIX:
    camera_processor must call vehicle_analyzer.update()
    AFTER cross_camera_tracker.assign_global_ids() so that
    global_id is already set on each TrackResult.
    The update() method uses track.global_id (not track.id).
=============================================================
"""

import cv2, logging, os, sqlite3, time, threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("VehicleAnalysis")

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
COLOR_EVERY       = 10    # extract color every N frames per track
DB_PATH           = "backend/vehicle_registry.db"
VEHICLE_CLASS_IDS = {1,2,3,5,7}   # bicycle,car,moto,bus,truck


# ─────────────────────────────────────────────────────────────
#  SHAPE TYPE  (aspect ratio heuristic — zero CPU cost)
# ─────────────────────────────────────────────────────────────

def _infer_shape_type(class_id: int, bbox: Tuple) -> str:
    """
    Rough vehicle type from COCO class + bbox aspect ratio.
    No model, no compute, just geometry.
    """
    x1,y1,x2,y2 = bbox
    w = max(1, x2-x1); h = max(1, y2-y1)
    ratio = w / h   # width/height

    if class_id == 3:  return "motorcycle"
    if class_id == 1:  return "bicycle"
    if class_id == 5:  return "bus"
    if class_id == 7:  return "truck"

    # class_id == 2 (car) — refine by aspect ratio
    if ratio > 2.2:    return "van/truck"
    if ratio > 1.6:    return "sedan"
    if ratio > 1.2:    return "suv/hatchback"
    return "compact"


# ─────────────────────────────────────────────────────────────
#  COLOR  (HSV lookup table)
# ─────────────────────────────────────────────────────────────

_COLORS = [
    # (name, BGR-for-drawing, H-lo, H-hi, S-lo, V-lo)
    ("red",    (0,  0,  200), 0,   10,  120, 70),
    ("red",    (0,  0,  200), 170, 180, 120, 70),
    ("orange", (0, 130, 255), 11,  25,  120, 70),
    ("yellow", (0, 220, 255), 26,  35,  120, 70),
    ("green",  (0, 200, 0  ), 36,  89,  80,  70),
    ("blue",   (200,80, 0  ), 90,  128, 80,  70),
    ("purple", (180, 0, 180), 129, 158, 60,  70),
    ("white",  (240,240,240), 0,   180, 0,   200),
    ("silver", (180,180,180), 0,   180, 0,   130),
    ("black",  (30, 30, 30 ), 0,   180, 255, 0  ),
]


def _bgr_to_name(bgr: Tuple) -> Tuple[str, Tuple]:
    px  = np.uint8([[list(bgr)]])
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])

    # Black check first (low value)
    if v < 50:  return "black",  (30,30,30)
    # White check (low saturation, high value)
    if v > 200 and s < 40: return "white", (240,240,240)
    # Silver (low-mid saturation)
    if v > 130 and s < 50: return "silver", (180,180,180)

    for name, draw, hlo, hhi, slo, vlo in _COLORS:
        if hlo <= h <= hhi and s >= slo and v >= vlo:
            return name, draw

    return "gray", (160,160,160)


class ColorExtractor:
    """
    Dominant color via k-means on 50×50 crop.
    Falls back to mean color if sklearn not installed.
    Total cost: ~3ms per call.
    """
    def __init__(self):
        try:
            from sklearn.cluster import MiniBatchKMeans
            self._has_sk = True
        except ImportError:
            self._has_sk = False
            logger.warning("[Color] pip install scikit-learn (using mean fallback)")

    def extract(self, crop: np.ndarray) -> Tuple[str, Tuple]:
        if crop is None or crop.size == 0:
            return "unknown", (128,128,128)
        small = cv2.resize(crop, (50,50))
        if self._has_sk:
            from sklearn.cluster import MiniBatchKMeans
            px = small.reshape(-1,3).astype(np.float32)
            km = MiniBatchKMeans(n_clusters=3, n_init=3, random_state=0)
            km.fit(px)
            _, counts = np.unique(km.labels_, return_counts=True)
            dom = km.cluster_centers_[np.argmax(counts)]
            return _bgr_to_name(tuple(int(c) for c in dom))
        else:
            mean = tuple(int(c) for c in small.reshape(-1,3).mean(0))
            return _bgr_to_name(mean)


# ─────────────────────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────────────────────

@dataclass
class VehicleInfo:
    global_id  : str
    class_name : str        = "vehicle"
    shape_type : str        = ""        # sedan, suv, truck, etc.
    color_name : str        = ""
    color_bgr  : Tuple      = (160,160,160)
    cameras    : List[int]  = field(default_factory=list)
    first_seen : float      = field(default_factory=time.time)
    last_seen  : float      = field(default_factory=time.time)
    frame_count: int        = 0

    def label(self) -> str:
        """Short display label for overlay."""
        parts = []
        if self.shape_type: parts.append(self.shape_type)
        if self.color_name: parts.append(self.color_name)
        return " | ".join(parts) if parts else ""

    def to_dict(self):
        return {
            "global_id": self.global_id, "class_name": self.class_name,
            "shape_type": self.shape_type, "color": self.color_name,
            "cameras": self.cameras, "first_seen": self.first_seen,
            "last_seen": self.last_seen, "frame_count": self.frame_count,
        }


# ─────────────────────────────────────────────────────────────
#  VEHICLE REGISTRY  (in-memory + SQLite)
# ─────────────────────────────────────────────────────────────

class VehicleRegistry:
    def __init__(self):
        self._records: Dict[str, VehicleInfo] = {}
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        self._db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                global_id  TEXT PRIMARY KEY,
                class_name TEXT, shape_type TEXT, color TEXT,
                cameras TEXT, first_seen REAL, last_seen REAL,
                frame_count INTEGER
            )""")
        self._db.commit()

    def upsert(self, info: VehicleInfo):
        with self._lock:
            self._records[info.global_id] = info
            cams = ",".join(str(c) for c in info.cameras)
            self._db.execute("""
                INSERT INTO vehicles VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(global_id) DO UPDATE SET
                    shape_type=excluded.shape_type,
                    color=excluded.color, cameras=excluded.cameras,
                    last_seen=excluded.last_seen,
                    frame_count=excluded.frame_count
            """, (info.global_id, info.class_name, info.shape_type,
                  info.color_name, cams,
                  info.first_seen, info.last_seen, info.frame_count))
            self._db.commit()

    def get(self, gid: str) -> Optional[VehicleInfo]:
        with self._lock: return self._records.get(gid)

    def search(self, color="", shape_type="") -> List[dict]:
        q = "SELECT * FROM vehicles WHERE 1=1"; p = []
        if color:      q += " AND color=?";      p.append(color.lower())
        if shape_type: q += " AND shape_type=?"; p.append(shape_type.lower())
        q += " ORDER BY last_seen DESC LIMIT 200"
        with self._lock:
            rows = self._db.execute(q, p).fetchall()
        cols = ["global_id","class_name","shape_type","color",
                "cameras","first_seen","last_seen","frame_count"]
        return [dict(zip(cols,r)) for r in rows]


# ─────────────────────────────────────────────────────────────
#  SHARED SINGLETONS
# ─────────────────────────────────────────────────────────────
_registry  = VehicleRegistry()
_color_ext = ColorExtractor()
_cnt: Dict[str,int] = {}
_cnt_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
#  VEHICLE ANALYZER  (per-camera interface)
# ─────────────────────────────────────────────────────────────

class VehicleAnalyzer:
    """
    Call update() AFTER cross_camera_tracker.assign_global_ids()
    so that track.global_id is already set.
    """

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        logger.info(f"[Camera-{camera_id}] VehicleAnalyzer ready (no OCR)")

    def update(self, tracked: list, frame: np.ndarray, camera_id: int):
        """
        Process all vehicle tracks in this frame.
        Uses global_id as the stable key.
        """
        h, w = frame.shape[:2]
        for t in tracked:
            if t.class_id not in VEHICLE_CLASS_IDS:
                continue

            # Use global_id if set, else fall back to local id
            gid = t.global_id if t.global_id else t.id

            x1,y1,x2,y2 = t.bbox
            x1,y1 = max(0,x1), max(0,y1)
            x2,y2 = min(w,x2), min(h,y2)
            if x2<=x1 or y2<=y1: continue
            crop = frame[y1:y2, x1:x2]

            with _cnt_lock:
                cc = _cnt.get(gid, 0) + 1
                _cnt[gid] = cc

            info = _registry.get(gid) or VehicleInfo(
                global_id=gid, class_name=t.class_name,
                first_seen=time.time()
            )
            info.last_seen    = time.time()
            info.frame_count += 1
            if camera_id not in info.cameras:
                info.cameras.append(camera_id)

            dirty = False

            # Shape type on first sighting (free — pure math)
            if not info.shape_type:
                info.shape_type = _infer_shape_type(t.class_id, t.bbox)
                dirty = True

            # Color every COLOR_EVERY frames
            if cc % COLOR_EVERY == 0:
                name, bgr = _color_ext.extract(crop)
                if name and name != "unknown":
                    info.color_name = name
                    info.color_bgr  = bgr
                    dirty = True

            if dirty or info.frame_count == 1:
                _registry.upsert(info)

    def get_info(self, gid: str) -> Optional[VehicleInfo]:
        return _registry.get(gid)

    @staticmethod
    def get_registry() -> VehicleRegistry:
        return _registry

    @staticmethod
    def search(color="", shape_type="") -> List[dict]:
        return _registry.search(color=color, shape_type=shape_type)