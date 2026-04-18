"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/behavior_analysis.py
  Purpose : All behavioral event detection in one module.

  DAY 12 ADDITION:
    FireDetector wired into BehaviorAnalyzer.
    self.fire.update(frame) called every frame in update().
    camera_processor reads self.behavior.fire.has_fire
    to apply red tint overlay.
=============================================================
"""

import cv2, json, logging, math, os, time
import numpy as np
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple

from app.alert_system import ALERT_SYSTEM
from app.vehicle_analysis import VEHICLE_CLASS_IDS

logger = logging.getLogger("BehaviorAnalysis")

ZONES_CONFIG = "backend/zones.json"


# ─────────────────────────────────────────────────────────────
#  1. AMBULANCE DETECTOR
# ─────────────────────────────────────────────────────────────

class AmbulanceDetector:
    CONFIRM_FRAMES = 2
    MIN_AREA       = 4000
    RATIO_MIN      = 1.3
    RATIO_MAX      = 3.8

    def __init__(self, camera_id: int):
        self.camera_id   = camera_id
        self._candidates : Dict[str, int] = {}
        self._alerted    : set            = set()

    def update(self, tracked: list, frame: np.ndarray):
        current_ids = set()
        for t in tracked:
            if t.class_id not in VEHICLE_CLASS_IDS: continue
            x1,y1,x2,y2 = t.bbox
            w = x2-x1; h = y2-y1
            if w*h < self.MIN_AREA: continue
            ratio = w / max(h, 1)
            if not (self.RATIO_MIN <= ratio <= self.RATIO_MAX): continue
            if not self._is_white_or_yellow(frame, t.bbox): continue
            did = t.global_id or t.id
            current_ids.add(did)
            self._candidates[did] = self._candidates.get(did, 0) + 1
            if (self._candidates[did] >= self.CONFIRM_FRAMES
                    and did not in self._alerted):
                self._alerted.add(did)
                ALERT_SYSTEM.fire(
                    alert_type = "AMBULANCE_DETECTED",
                    camera_id  = self.camera_id,
                    message    = f"Ambulance detected — ID {did}",
                    metadata   = {"track_id": did, "bbox": t.bbox},
                )
        gone = set(self._candidates) - current_ids
        for did in gone:
            self._candidates.pop(did, None)
            self._alerted.discard(did)

    @staticmethod
    def _is_white_or_yellow(frame, bbox):
        x1,y1,x2,y2 = bbox
        h,w = frame.shape[:2]
        x1,y1 = max(0,x1),max(0,y1); x2,y2 = min(w,x2),min(h,y2)
        if x2<=x1 or y2<=y1: return False
        crop  = cv2.resize(frame[y1:y2,x1:x2], (32,32))
        hsv   = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        white  = cv2.inRange(hsv,(0,0,180),(180,50,255))
        yellow = cv2.inRange(hsv,(20,100,100),(40,255,255))
        total  = 32*32
        return cv2.countNonZero(white)/total > 0.40 or \
               cv2.countNonZero(yellow)/total > 0.25


# ─────────────────────────────────────────────────────────────
#  2. ACCIDENT DETECTOR
# ─────────────────────────────────────────────────────────────

class AccidentDetector:
    IOU_THRESH       = 0.12
    MIN_VELOCITY     = 8.0
    STOPPED_VELOCITY = 2.5
    CONFIRM_SECONDS  = 1.8
    SNAPSHOT_DIR     = "backend/snapshots"

    def __init__(self, camera_id: int, tracker=None):
        self.camera_id   = camera_id
        self._tracker    = tracker
        self._gate_start : Dict[Tuple,float] = {}
        self._alerted    : set               = set()
        os.makedirs(self.SNAPSHOT_DIR, exist_ok=True)

    def set_tracker(self, tracker): self._tracker = tracker

    def update(self, tracked: list, frame: np.ndarray):
        vehicles = [t for t in tracked if t.class_id in VEHICLE_CLASS_IDS]
        if len(vehicles) < 2: return
        now = time.time(); active_pairs = set()
        for i in range(len(vehicles)):
            for j in range(i+1, len(vehicles)):
                a = vehicles[i]; b = vehicles[j]
                pair = tuple(sorted([a.global_id or a.id, b.global_id or b.id]))
                if self._iou(a.bbox, b.bbox) < self.IOU_THRESH:
                    self._gate_start.pop(pair, None); continue
                va = self._vel(a); vb = self._vel(b)
                if not ((va > self.MIN_VELOCITY or vb > self.MIN_VELOCITY) and
                        (va < self.STOPPED_VELOCITY and vb < self.STOPPED_VELOCITY)):
                    self._gate_start.pop(pair, None); continue
                active_pairs.add(pair)
                if pair not in self._gate_start:
                    self._gate_start[pair] = now
                elif (now - self._gate_start[pair] >= self.CONFIRM_SECONDS
                      and pair not in self._alerted):
                    self._alerted.add(pair)
                    self._fire_alert(pair, a, b, frame)
        gone = set(self._gate_start) - active_pairs
        for p in gone: self._gate_start.pop(p, None)

    def _fire_alert(self, pair, a, b, frame):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        snap = os.path.join(self.SNAPSHOT_DIR, f"accident_{ts}.jpg")
        cv2.imwrite(snap, frame)
        ALERT_SYSTEM.fire(
            alert_type = "ACCIDENT_DETECTED",
            camera_id  = self.camera_id,
            message    = f"Accident: {pair[0]} ↔ {pair[1]}",
            metadata   = {"vehicles": list(pair), "snapshot": snap,
                          "bbox_a": a.bbox, "bbox_b": b.bbox},
        )
        logger.warning(f"[Accident] Cam{self.camera_id} {pair[0]} ↔ {pair[1]}")

    def _vel(self, track) -> float:
        if self._tracker is None: return 0.0
        return self._tracker.get_velocity(track.id)

    @staticmethod
    def _iou(a, b) -> float:
        ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
        ix1,iy1 = max(ax1,bx1),max(ay1,by1)
        ix2,iy2 = min(ax2,bx2),min(ay2,by2)
        inter   = max(0,ix2-ix1)*max(0,iy2-iy1)
        if inter == 0: return 0.0
        ua = (ax2-ax1)*(ay2-ay1); ub = (bx2-bx1)*(by2-by1)
        union = ua+ub-inter
        return inter/union if union > 0 else 0.0


# ─────────────────────────────────────────────────────────────
#  3. DWELL TRACKER
# ─────────────────────────────────────────────────────────────

class DwellTracker:
    PERSON_THRESHOLD  = 60.0
    VEHICLE_THRESHOLD = 300.0
    MOVEMENT_THRESH   = 30.0

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._state: Dict[str, dict] = {}

    def update(self, tracked: list):
        now = time.time(); active_ids = set()
        for t in tracked:
            did = t.global_id or t.id
            active_ids.add(did)
            cx, cy = t.centroid
            if did not in self._state:
                self._state[did] = {
                    "first_seen": now, "last_centroid": (cx,cy),
                    "total_move": 0.0, "alerted": False,
                }
            else:
                s  = self._state[did]
                lx,ly = s["last_centroid"]
                s["total_move"]   += math.hypot(cx-lx, cy-ly)
                s["last_centroid"] = (cx, cy)
                dwell   = now - s["first_seen"]
                avg_move = s["total_move"] / max(1, dwell)
                if avg_move > self.MOVEMENT_THRESH: continue
                is_vehicle = t.class_id in VEHICLE_CLASS_IDS
                threshold  = self.VEHICLE_THRESHOLD if is_vehicle else self.PERSON_THRESHOLD
                if dwell >= threshold and not s["alerted"]:
                    s["alerted"] = True
                    obj_type = "vehicle" if is_vehicle else "person"
                    ALERT_SYSTEM.fire(
                        alert_type = "LOITERING",
                        camera_id  = self.camera_id,
                        message    = f"Stationary {obj_type} {did} for {dwell:.0f}s",
                        metadata   = {"track_id": did, "dwell_s": round(dwell,1),
                                      "obj_type": obj_type},
                    )
        for did in set(self._state) - active_ids:
            del self._state[did]

    def get_dwell(self, display_id: str) -> float:
        s = self._state.get(display_id)
        return time.time() - s["first_seen"] if s else 0.0


# ─────────────────────────────────────────────────────────────
#  4. ZONE MANAGER
# ─────────────────────────────────────────────────────────────

class ZoneManager:
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._zones    = self._load_zones()
        self._inside  : Dict[Tuple[str,str], bool] = {}
        logger.info(f"[Zones] Cam{camera_id} — {len(self._zones)} zone(s)")

    def _load_zones(self) -> List[dict]:
        if not os.path.exists(ZONES_CONFIG):
            defaults = [
                {"name":"zone_A","type":"monitored","points":[[10,10],[230,10],[230,170],[10,170]]},
                {"name":"zone_B","type":"restricted","points":[[250,10],[470,10],[470,170],[250,170]]},
            ]
            os.makedirs(os.path.dirname(ZONES_CONFIG) or ".", exist_ok=True)
            with open(ZONES_CONFIG,"w") as f: json.dump(defaults, f, indent=2)
            return defaults
        with open(ZONES_CONFIG) as f: return json.load(f)

    def update(self, tracked: list):
        active_keys = set()
        for t in tracked:
            did = t.global_id or t.id
            cx, cy = t.centroid
            for zone in self._zones:
                pts = np.array(zone["points"], dtype=np.float32)
                key = (did, zone["name"]); active_keys.add(key)
                inside_now = cv2.pointPolygonTest(pts,(float(cx),float(cy)),False) >= 0
                was_inside = self._inside.get(key, False)
                if inside_now and not was_inside:
                    self._inside[key] = True
                    ALERT_SYSTEM.fire(
                        alert_type="ZONE_ENTER", camera_id=self.camera_id,
                        message=f"{t.class_name} {did} entered {zone['name']}",
                        metadata={"track_id":did,"zone_name":zone["name"],
                                  "zone_type":zone.get("type","")},
                    )
                elif not inside_now and was_inside:
                    self._inside[key] = False
                    ALERT_SYSTEM.fire(
                        alert_type="ZONE_EXIT", camera_id=self.camera_id,
                        message=f"{t.class_name} {did} left {zone['name']}",
                        metadata={"track_id":did,"zone_name":zone["name"]},
                    )
        gone = {k for k in self._inside
                if k[0] not in {(t.global_id or t.id) for t in tracked}}
        for k in gone: del self._inside[k]

    def draw_zones(self, frame: np.ndarray) -> np.ndarray:
        for zone in self._zones:
            pts   = np.array(zone["points"], dtype=np.int32)
            color = (0,80,200) if zone.get("type")=="restricted" else (0,160,80)
            cv2.polylines(frame,[pts],True,color,1,cv2.LINE_AA)
            M = cv2.moments(pts)
            if M["m00"] > 0:
                cx = int(M["m10"]/M["m00"]); cy = int(M["m01"]/M["m00"])
                cv2.putText(frame,zone["name"],(cx-20,cy),
                            cv2.FONT_HERSHEY_SIMPLEX,0.35,color,1,cv2.LINE_AA)
        return frame

    def reload(self): self._zones = self._load_zones()


# ─────────────────────────────────────────────────────────────
#  5. CROWD ANALYZER
# ─────────────────────────────────────────────────────────────

class CrowdAnalyzer:
    THRESHOLD     = 8
    HEATMAP_DECAY = 0.97

    def __init__(self, camera_id: int, frame_h=360, frame_w=480):
        self.camera_id   = camera_id
        self._heatmap    = np.zeros((frame_h, frame_w), dtype=np.float32)
        self._person_cnt = 0

    def update(self, tracked: list) -> int:
        persons = [t for t in tracked if t.class_id == 0]
        self._person_cnt = len(persons)
        self._heatmap   *= self.HEATMAP_DECAY
        for t in persons:
            cx, cy = t.centroid
            h, w   = self._heatmap.shape
            if 0 <= cx < w and 0 <= cy < h:
                cv2.circle(self._heatmap, (cx,cy), 20, 1.0, -1)
        if self._person_cnt >= self.THRESHOLD:
            ALERT_SYSTEM.fire(
                alert_type="CROWD_DETECTED", camera_id=self.camera_id,
                message=f"Crowd: {self._person_cnt} persons",
                metadata={"count": self._person_cnt},
            )
        return self._person_cnt

    def get_heatmap_overlay(self, frame: np.ndarray) -> np.ndarray:
        if self._heatmap.max() < 1e-3: return frame
        norm    = cv2.normalize(self._heatmap, None, 0, 255, cv2.NORM_MINMAX)
        colored = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_JET)
        mask    = (norm > 10).astype(np.uint8)[:,:,None]
        blended = cv2.addWeighted(frame, 0.6, colored, 0.4, 0)
        return np.where(mask, blended, frame)

    @property
    def person_count(self) -> int: return self._person_cnt


# ─────────────────────────────────────────────────────────────
#  6. TRAFFIC ANALYZER
# ─────────────────────────────────────────────────────────────

class TrafficAnalyzer:
    WINDOW     = 150
    NORMAL_MAX = 4
    HEAVY_MAX  = 9

    def __init__(self, camera_id: int):
        self.camera_id   = camera_id
        self._history    = deque(maxlen=self.WINDOW)
        self._state      = "NORMAL"
        self._prev_state = "NORMAL"

    def update(self, tracked: list) -> str:
        vc = sum(1 for t in tracked if t.class_id in VEHICLE_CLASS_IDS)
        self._history.append(vc)
        avg = sum(self._history) / max(1, len(self._history))
        new_state = ("CONGESTION" if avg > self.HEAVY_MAX else
                     "HEAVY"      if avg > self.NORMAL_MAX else "NORMAL")
        if new_state != self._prev_state:
            self._prev_state = new_state; self._state = new_state
            if new_state in ("HEAVY","CONGESTION"):
                ALERT_SYSTEM.fire(
                    alert_type = "HEAVY_TRAFFIC" if new_state=="HEAVY" else "CONGESTION",
                    camera_id  = self.camera_id,
                    message    = f"Traffic: {new_state} ({avg:.1f} vehicles avg)",
                    metadata   = {"state": new_state, "avg_vehicles": round(avg,1)},
                )
        else:
            self._state = new_state
        return self._state

    @property
    def state(self) -> str: return self._state

    @property
    def state_color(self) -> Tuple[int,int,int]:
        return {
            "NORMAL":     (0, 200, 80),
            "HEAVY":      (0, 180, 255),
            "CONGESTION": (0, 60,  220),
        }.get(self._state, (200,200,200))


# ─────────────────────────────────────────────────────────────
#  BEHAVIOR ANALYZER — facade
# ─────────────────────────────────────────────────────────────

class BehaviorAnalyzer:
    """
    Single entry point for all behavioral analysis.
    One instance per camera.

    DAY 12: FireDetector added.
    camera_processor checks self.behavior.fire.has_fire
    to apply red tint overlay on the camera feed.
    """

    def __init__(self, camera_id: int, tracker=None):
        self.camera_id = camera_id
        self.ambulance = AmbulanceDetector(camera_id)
        self.accident  = AccidentDetector(camera_id, tracker)
        self.dwell     = DwellTracker(camera_id)
        self.zones     = ZoneManager(camera_id)
        self.crowd     = CrowdAnalyzer(camera_id)
        self.traffic   = TrafficAnalyzer(camera_id)

        # DAY 12 — Fire & smoke detection
        from app.fire_detection import FireDetector
        self.fire = FireDetector(camera_id)

        logger.info(f"[BehaviorAnalyzer] Camera {camera_id} ready (with fire detection).")

    def set_tracker(self, tracker):
        self.accident.set_tracker(tracker)

    def update(self, tracked: list, frame: np.ndarray):
        """Run all detectors. Call every frame."""
        self.ambulance.update(tracked, frame)
        self.accident.update(tracked, frame)
        self.dwell.update(tracked)
        self.zones.update(tracked)
        self.crowd.update(tracked)
        self.traffic.update(tracked)
        # Fire detection runs on raw frame (not tracked objects)
        self.fire.update(frame)