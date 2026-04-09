"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/cross_camera_tracker.py
  Purpose : Cross-camera Re-ID — same person/vehicle gets the
            same global ID ("G-001") on every camera.

  FIXES:
    - _best_match() now filters by class FAMILY — persons only
      match persons, vehicles only match vehicles. Prevents a
      red-shirted person matching a red car.
    - assign_global_ids() now called AFTER vehicle_analysis in
      camera_processor, so global_id is set when needed.
    - Gallery entry EMA weight corrected: 0.3*new + 0.7*old
      (was inverted — caused embedding drift toward noise)
    - Cleanup loop now also removes stale local_map entries

  ARCHITECTURE NOTE:
    This is a SINGLETON. All camera threads share one instance.
    Import GLOBAL_TRACKER wherever needed.
=============================================================
"""

import cv2, logging, threading, time
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("CrossCamTracker")

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
GALLERY_TTL      = 60.0   # seconds to keep lost identity
MIN_CROP_PX      = 900    # min crop area to attempt embedding
CLEANUP_INTERVAL = 10.0

_THRESH_OSNET = 0.72
_THRESH_HIST  = 0.55

# Class families for matching guard
_PERSONS  = {0}                # person
_VEHICLES = {1,2,3,5,7}       # bicycle,car,moto,bus,truck


def _family(class_id: int) -> str:
    if class_id in _PERSONS:  return "person"
    if class_id in _VEHICLES: return "vehicle"
    return f"other_{class_id}"


# ─────────────────────────────────────────────────────────────
#  EMBEDDING BACKENDS
# ─────────────────────────────────────────────────────────────

def _try_osnet():
    try:
        import torchreid, torch
        m = torchreid.models.build_model(
            name="osnet_x0_25", num_classes=1000, pretrained=True
        )
        m.eval()
        if torch.cuda.is_available(): m = m.cuda()
        logger.info("[ReID] OSNet-x0.25 loaded")
        return m, True
    except Exception as e:
        logger.info(f"[ReID] OSNet unavailable ({e}) — histogram fallback")
        return None, False


_OSNET, _USE_OSNET = _try_osnet()
MATCH_THRESHOLD   = _THRESH_OSNET if _USE_OSNET else _THRESH_HIST


def extract_embedding(crop: np.ndarray) -> Optional[np.ndarray]:
    if crop is None or crop.size == 0: return None
    if crop.shape[0] * crop.shape[1] < MIN_CROP_PX: return None
    if crop.shape[0] < 10 or crop.shape[1] < 10: return None
    return _osnet_embed(crop) if _USE_OSNET else _hist_embed(crop)


def _osnet_embed(crop):
    try:
        import torch, torchvision.transforms as T
        tf = T.Compose([
            T.ToPILImage(), T.Resize((256,128)), T.ToTensor(),
            T.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
        ])
        t = tf(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).unsqueeze(0)
        if torch.cuda.is_available(): t = t.cuda()
        with torch.no_grad():
            v = _OSNET(t).cpu().numpy().flatten().astype(np.float32)
        n = np.linalg.norm(v)
        return v/n if n > 1e-6 else None
    except Exception:
        return _hist_embed(crop)


def _hist_embed(crop):
    try:
        r   = cv2.resize(crop, (64,128))
        hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV)
        parts = [cv2.calcHist([hsv],[ch],None,[128],[0,256]).flatten()
                 for ch in range(3)]
        v = np.concatenate(parts).astype(np.float32)
        n = np.linalg.norm(v)
        return v/n if n > 1e-6 else None
    except Exception:
        return None


def _cosine(a, b) -> float:
    return float(np.dot(a, b))


# ─────────────────────────────────────────────────────────────
#  GALLERY ENTRY
# ─────────────────────────────────────────────────────────────

class GalleryEntry:
    def __init__(self, gid, emb, cam, local_id, class_id, class_name):
        self.global_id  = gid
        self.embedding  = emb.copy()
        self.camera_id  = cam
        self.local_id   = local_id
        self.class_id   = class_id
        self.class_name = class_name
        self.is_active  = True
        self.created_at = time.time()
        self.last_seen  = time.time()
        self.sightings: List[Tuple[float,int]] = [(self.created_at, cam)]

    def refresh(self, emb, cam, local_id):
        # EMA: 70% old + 30% new — stable but adapts
        self.embedding = 0.7 * self.embedding + 0.3 * emb
        n = np.linalg.norm(self.embedding)
        if n > 1e-6: self.embedding /= n
        self.camera_id = cam; self.local_id = local_id
        self.last_seen = time.time(); self.is_active = True
        self.sightings.append((self.last_seen, cam))

    def touch(self):
        self.last_seen = time.time(); self.is_active = True

    def mark_lost(self):
        self.is_active = False; self.last_seen = time.time()

    def is_expired(self):
        return not self.is_active and (time.time()-self.last_seen) > GALLERY_TTL

    def is_cross_camera(self):
        return len({c for _,c in self.sightings}) > 1

    @property
    def camera_list(self):
        return list({c for _,c in self.sightings})


# ─────────────────────────────────────────────────────────────
#  CROSS CAMERA TRACKER  (singleton)
# ─────────────────────────────────────────────────────────────

class CrossCameraTracker:
    """
    Singleton. All camera threads share this instance.
    Maps (camera_id, local_id) → stable global_id "G-001".
    """

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
        self._gallery  : Dict[str, GalleryEntry] = {}
        self._local_map: Dict[str, str]           = {}
        self._counter   = 0
        self._lock      = threading.RLock()
        threading.Thread(target=self._cleanup_loop,
                         daemon=True, name="ReID-Cleanup").start()
        logger.info(f"[CrossCameraTracker] Ready | "
                    f"backend={'OSNet' if _USE_OSNET else 'histogram'} | "
                    f"threshold={MATCH_THRESHOLD:.2f}")

    # ── Primary interface ─────────────────────────────────────

    def assign_global_ids(
        self,
        camera_id      : int,
        tracked_objects: list,   # List[TrackResult]
        frame          : np.ndarray,
    ):
        """
        Crops each track, extracts embedding, resolves global ID.
        Sets track.global_id in-place on each TrackResult.
        Call this AFTER all analysis that uses track.id (local ID).
        """
        h, w = frame.shape[:2]
        for track in tracked_objects:
            x1,y1,x2,y2 = track.bbox
            x1c,y1c = max(0,x1),max(0,y1)
            x2c,y2c = min(w,x2),min(h,y2)

            crop = None
            if x2c > x1c and y2c > y1c:
                crop = frame[y1c:y2c, x1c:x2c]

            emb = extract_embedding(crop)

            gid = self.resolve(
                camera_id  = camera_id,
                local_id   = track.id,
                embedding  = emb,
                class_id   = track.class_id,
                class_name = track.class_name,
            )
            track.global_id = gid

    def resolve(
        self,
        camera_id  : int,
        local_id   : str,
        embedding  : Optional[np.ndarray],
        class_id   : int = -1,
        class_name : str = "object",
    ) -> str:
        key = f"{camera_id}::{local_id}"
        with self._lock:
            # Fast path
            if key in self._local_map:
                gid = self._local_map[key]
                e   = self._gallery.get(gid)
                if e:
                    if embedding is not None: e.refresh(embedding, camera_id, local_id)
                    else: e.touch()
                return gid

            # Try to match gallery
            gid = None
            if embedding is not None:
                gid = self._best_match(embedding, camera_id, class_id)

            if gid is None:
                self._counter += 1
                gid = f"G-{self._counter:03d}"
                emb_stored = (embedding if embedding is not None
                              else np.zeros(384, dtype=np.float32))
                self._gallery[gid] = GalleryEntry(
                    gid, emb_stored, camera_id, local_id, class_id, class_name
                )
            else:
                e = self._gallery[gid]
                if embedding is not None: e.refresh(embedding, camera_id, local_id)
                else: e.touch()
                if e.is_cross_camera():
                    logger.info(f"[ReID] CROSS-CAM {gid} ({class_name}) Cam{camera_id}")

            self._local_map[key] = gid
            return gid

    def mark_lost(self, camera_id: int, local_id: str):
        key = f"{camera_id}::{local_id}"
        with self._lock:
            gid = self._local_map.get(key)
            if gid and gid in self._gallery:
                self._gallery[gid].mark_lost()

    # ── Matching ──────────────────────────────────────────────

    def _best_match(self, emb, camera_id, class_id) -> Optional[str]:
        """
        FIX: Only match within the same class FAMILY.
        Persons only match persons. Vehicles only match vehicles.
        This prevents red-shirt person matching red car.
        """
        qfam     = _family(class_id)
        best_gid = None
        best_sim = MATCH_THRESHOLD - 1e-9

        for gid, e in self._gallery.items():
            if e.is_expired(): continue
            # Class family guard
            if _family(e.class_id) != qfam: continue
            # Don't steal active same-camera tracks
            if e.is_active and e.camera_id == camera_id: continue
            if e.embedding is None: continue
            sim = _cosine(emb, e.embedding)
            if sim > best_sim:
                best_sim = sim; best_gid = gid

        return best_gid

    # ── Status ────────────────────────────────────────────────

    @property
    def multicamera_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._gallery.values() if e.is_cross_camera())

    @property
    def active_count(self) -> int:
        with self._lock: return len(self._gallery)

    def get_cross_camera_list(self) -> List[dict]:
        with self._lock:
            return [
                {"global_id": e.global_id, "cameras": e.camera_list,
                 "class_name": e.class_name}
                for e in self._gallery.values() if e.is_cross_camera()
            ]

    def get_status(self) -> dict:
        return {
            "backend": "OSNet" if _USE_OSNET else "histogram",
            "threshold": MATCH_THRESHOLD,
            "total_identities": self.active_count,
            "cross_camera_matches": self.multicamera_count,
        }

    # ── Cleanup ───────────────────────────────────────────────

    def _cleanup_loop(self):
        while True:
            time.sleep(CLEANUP_INTERVAL)
            with self._lock:
                expired = [g for g,e in self._gallery.items() if e.is_expired()]
                for g in expired: del self._gallery[g]
                self._local_map = {k:v for k,v in self._local_map.items()
                                   if v not in expired}
            if expired:
                logger.debug(f"[ReID] Pruned {len(expired)} expired entries")


# Process-wide singleton
GLOBAL_TRACKER = CrossCameraTracker()