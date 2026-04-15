"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/behavior_analysis.py
  Purpose : All behavioral event detection in one module.

  MODULES:
    1. AmbulanceDetector   — color + shape heuristic, no OCR
    2. AccidentDetector    — IoU overlap + velocity + duration
    3. DwellTracker        — loitering / abandoned vehicle
    4. ZoneManager         — configurable polygon zones
    5. CrowdAnalyzer       — person count threshold + heatmap
    6. TrafficAnalyzer     — rolling vehicle count → state

  DESIGN:
    Each detector is stateless except for the minimum history
    it needs. All detectors share the ALERT_SYSTEM singleton.
    Called from camera_processor.py once per frame.

  AMBULANCE WITHOUT OCR:
    White/yellow + van-height aspect ratio + large bbox area
    → candidate. Confirmed after 2 consecutive frames.
    Accuracy is lower than OCR but costs zero extra CPU.
    False positive rate is acceptable for an alert system
    (operator verifies on live feed).
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
    """
    Detects ambulances by color + shape without OCR.

    Logic:
      - Object must be a vehicle (car/truck/bus class)
      - Dominant color must be white or yellow
      - Aspect ratio: wider than tall (ratio 1.4–3.5) → van-like
      - Minimum area: large enough to be a real vehicle
      - Confirmed after CONFIRM_FRAMES consecutive candidates

    Generates AMBULANCE_DETECTED alert.
    """

    CONFIRM_FRAMES = 2
    MIN_AREA       = 4000   # px² at 480×360 — filters tiny detections
    RATIO_MIN      = 1.3
    RATIO_MAX      = 3.8

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        # track_id → consecutive candidate frame count
        self._candidates: Dict[str, int] = {}
        self._alerted:    set             = set()   # already alerted IDs

    def update(self, tracked: list, frame: np.ndarray):
        """Call once per frame with current tracks."""
        current_ids = set()

        for t in tracked:
            if t.class_id not in VEHICLE_CLASS_IDS:
                continue
            x1,y1,x2,y2 = t.bbox
            w = x2-x1; h = y2-y1
            if w*h < self.MIN_AREA: continue

            ratio = w / max(h, 1)
            if not (self.RATIO_MIN <= ratio <= self.RATIO_MAX):
                continue

            # Check color
            if not self._is_white_or_yellow(frame, t.bbox):
                continue

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
                logger.warning(f"[Ambulance] Cam{self.camera_id} ID={did}")

        # Reset counter for tracks that are no longer candidates
        gone = set(self._candidates) - current_ids
        for did in gone:
            self._candidates.pop(did, None)
            self._alerted.discard(did)   # allow re-alert if it leaves + returns

    @staticmethod
    def _is_white_or_yellow(frame: np.ndarray, bbox: Tuple) -> bool:
        x1,y1,x2,y2 = bbox
        h,w = frame.shape[:2]
        x1,y1 = max(0,x1), max(0,y1)
        x2,y2 = min(w,x2), min(h,y2)
        if x2<=x1 or y2<=y1: return False
        crop  = cv2.resize(frame[y1:y2,x1:x2], (32,32))
        hsv   = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        # White: low saturation, high value
        white_mask  = cv2.inRange(hsv, (0,0,180), (180,50,255))
        # Yellow: hue 20–40
        yellow_mask = cv2.inRange(hsv, (20,100,100),(40,255,255))
        total  = 32*32
        w_pct  = cv2.countNonZero(white_mask)  / total
        y_pct  = cv2.countNonZero(yellow_mask) / total
        return w_pct > 0.40 or y_pct > 0.25


# ─────────────────────────────────────────────────────────────
#  2. ACCIDENT DETECTOR
# ─────────────────────────────────────────────────────────────

class AccidentDetector:
    """
    3-gate accident detection:
      Gate 1: IoU between two vehicle bboxes > IOU_THRESH
      Gate 2: Both vehicles had velocity > MIN_VELOCITY recently,
              now near zero (sudden stop)
      Gate 3: Gates 1+2 held for at least CONFIRM_SECONDS

    Snapshot saved automatically on confirmed accident.
    """

    IOU_THRESH       = 0.12   # slight overlap counts
    MIN_VELOCITY     = 8.0    # px/frame — was moving
    STOPPED_VELOCITY = 2.5    # px/frame — now stopped
    CONFIRM_SECONDS  = 1.8    # gates must hold this long
    SNAPSHOT_DIR     = "backend/snapshots"

    def __init__(self, camera_id: int, tracker=None):
        self.camera_id = camera_id
        self._tracker  = tracker    # PersonTracker ref for velocity
        # (id_a, id_b) → first_time_gates_held
        self._gate_start: Dict[Tuple,float] = {}
        self._alerted  : set = set()
        os.makedirs(self.SNAPSHOT_DIR, exist_ok=True)

    def set_tracker(self, tracker):
        self._tracker = tracker

    def update(self, tracked: list, frame: np.ndarray):
        vehicles = [t for t in tracked if t.class_id in VEHICLE_CLASS_IDS]
        if len(vehicles) < 2: return

        now = time.time()
        active_pairs = set()

        for i in range(len(vehicles)):
            for j in range(i+1, len(vehicles)):
                a = vehicles[i]; b = vehicles[j]
                pair = tuple(sorted([a.global_id or a.id,
                                     b.global_id or b.id]))

                # Gate 1: IoU
                if self._iou(a.bbox, b.bbox) < self.IOU_THRESH:
                    self._gate_start.pop(pair, None)
                    continue

                # Gate 2: velocity
                va = self._vel(a)
                vb = self._vel(b)
                # At least one was moving, now both stopped
                was_moving = (va > self.MIN_VELOCITY or
                              vb > self.MIN_VELOCITY)
                both_stopped = (va < self.STOPPED_VELOCITY and
                                vb < self.STOPPED_VELOCITY)

                if not (was_moving and both_stopped):
                    self._gate_start.pop(pair, None)
                    continue

                # Both gates held — start or check timer
                active_pairs.add(pair)
                if pair not in self._gate_start:
                    self._gate_start[pair] = now
                elif (now - self._gate_start[pair] >= self.CONFIRM_SECONDS
                      and pair not in self._alerted):
                    self._alerted.add(pair)
                    self._fire_alert(pair, a, b, frame)

        # Clean up old gate timers
        gone = set(self._gate_start) - active_pairs
        for p in gone:
            self._gate_start.pop(p, None)

    def _fire_alert(self, pair, a, b, frame):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        snap = os.path.join(self.SNAPSHOT_DIR, f"accident_{ts}.jpg")
        cv2.imwrite(snap, frame)

        ALERT_SYSTEM.fire(
            alert_type = "ACCIDENT_DETECTED",
            camera_id  = self.camera_id,
            message    = f"Accident: {pair[0]} ↔ {pair[1]}",
            metadata   = {
                "vehicles": list(pair),
                "snapshot": snap,
                "bbox_a"  : a.bbox,
                "bbox_b"  : b.bbox,
            },
        )
        logger.warning(
            f"[Accident] Cam{self.camera_id} "
            f"{pair[0]} ↔ {pair[1]} — snapshot: {snap}"
        )

    def _vel(self, track) -> float:
        if self._tracker is None: return 0.0
        return self._tracker.get_velocity(track.id)

    @staticmethod
    def _iou(a: Tuple, b: Tuple) -> float:
        ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
        ix1,iy1 = max(ax1,bx1), max(ay1,by1)
        ix2,iy2 = min(ax2,bx2), min(ay2,by2)
        inter   = max(0,ix2-ix1)*max(0,iy2-iy1)
        if inter == 0: return 0.0
        ua = (ax2-ax1)*(ay2-ay1); ub = (bx2-bx1)*(by2-by1)
        union = ua+ub-inter
        return inter/union if union > 0 else 0.0


# ─────────────────────────────────────────────────────────────
#  3. DWELL TRACKER  (loitering + abandoned vehicle)
# ─────────────────────────────────────────────────────────────

class DwellTracker:
    """
    Tracks how long each object has been in the scene.
    Fires LOITERING alert when threshold exceeded.

    Person threshold:  60s  (configurable)
    Vehicle threshold: 300s (parked too long)
    """

    PERSON_THRESHOLD  = 60.0
    VEHICLE_THRESHOLD = 300.0
    # Only alert if the object hasn't moved much (stationary)
    MOVEMENT_THRESH   = 30.0  # px — max centroid displacement to count as stationary

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        # display_id → {"first_seen", "last_centroid", "alerted"}
        self._state: Dict[str, dict] = {}

    def update(self, tracked: list):
        now = time.time()
        active_ids = set()

        for t in tracked:
            did = t.global_id or t.id
            active_ids.add(did)
            cx, cy = t.centroid

            if did not in self._state:
                self._state[did] = {
                    "first_seen"    : now,
                    "last_centroid" : (cx, cy),
                    "total_move"    : 0.0,
                    "alerted"       : False,
                }
            else:
                s  = self._state[did]
                lx, ly = s["last_centroid"]
                move   = math.hypot(cx-lx, cy-ly)
                s["total_move"]    += move
                s["last_centroid"]  = (cx, cy)

                dwell   = now - s["first_seen"]
                avg_move = s["total_move"] / max(1, dwell)

                # Only alert if mostly stationary
                if avg_move > self.MOVEMENT_THRESH:
                    continue

                is_vehicle = t.class_id in VEHICLE_CLASS_IDS
                threshold  = (self.VEHICLE_THRESHOLD if is_vehicle
                              else self.PERSON_THRESHOLD)

                if dwell >= threshold and not s["alerted"]:
                    s["alerted"] = True
                    obj_type = "vehicle" if is_vehicle else "person"
                    ALERT_SYSTEM.fire(
                        alert_type = "LOITERING",
                        camera_id  = self.camera_id,
                        message    = (
                            f"Stationary {obj_type} {did} "
                            f"for {dwell:.0f}s"
                        ),
                        metadata   = {
                            "track_id" : did,
                            "dwell_s"  : round(dwell, 1),
                            "obj_type" : obj_type,
                        },
                    )

        # Purge lost tracks
        for did in set(self._state) - active_ids:
            del self._state[did]

    def get_dwell(self, display_id: str) -> float:
        """Seconds this ID has been in scene. 0 if not tracked."""
        s = self._state.get(display_id)
        return time.time() - s["first_seen"] if s else 0.0


# ─────────────────────────────────────────────────────────────
#  4. ZONE MANAGER
# ─────────────────────────────────────────────────────────────

class ZoneManager:
    """
    Configurable polygon zones from backend/zones.json.

    zones.json format:
    [
      {
        "name": "restricted",
        "type": "restricted",
        "points": [[10,10],[200,10],[200,180],[10,180]]
      },
      ...
    ]

    Fires ZONE_ENTER / ZONE_EXIT per track per zone.
    Point-in-polygon via cv2.pointPolygonTest — fast.
    """

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._zones    = self._load_zones()
        # (display_id, zone_name) → True if currently inside
        self._inside: Dict[Tuple[str,str], bool] = {}
        logger.info(
            f"[Zones] Cam{camera_id} — "
            f"{len(self._zones)} zone(s) loaded"
        )

    def _load_zones(self) -> List[dict]:
        if not os.path.exists(ZONES_CONFIG):
            # Create default example zones.json
            defaults = [
                {"name":"zone_A","type":"monitored",
                 "points":[[10,10],[230,10],[230,170],[10,170]]},
                {"name":"zone_B","type":"restricted",
                 "points":[[250,10],[470,10],[470,170],[250,170]]},
            ]
            os.makedirs(os.path.dirname(ZONES_CONFIG), exist_ok=True)
            with open(ZONES_CONFIG,"w") as f:
                json.dump(defaults, f, indent=2)
            logger.info(f"[Zones] Created default {ZONES_CONFIG}")
            return defaults
        with open(ZONES_CONFIG) as f:
            return json.load(f)

    def update(self, tracked: list):
        active_keys = set()

        for t in tracked:
            did = t.global_id or t.id
            cx, cy = t.centroid

            for zone in self._zones:
                pts  = np.array(zone["points"], dtype=np.float32)
                key  = (did, zone["name"])
                active_keys.add(key)

                inside_now = (
                    cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0
                )
                was_inside = self._inside.get(key, False)

                if inside_now and not was_inside:
                    self._inside[key] = True
                    ALERT_SYSTEM.fire(
                        alert_type = "ZONE_ENTER",
                        camera_id  = self.camera_id,
                        message    = (
                            f"{t.class_name} {did} "
                            f"entered {zone['name']}"
                        ),
                        metadata   = {
                            "track_id"  : did,
                            "zone_name" : zone["name"],
                            "zone_type" : zone.get("type",""),
                        },
                    )
                elif not inside_now and was_inside:
                    self._inside[key] = False
                    ALERT_SYSTEM.fire(
                        alert_type = "ZONE_EXIT",
                        camera_id  = self.camera_id,
                        message    = (
                            f"{t.class_name} {did} "
                            f"left {zone['name']}"
                        ),
                        metadata   = {
                            "track_id"  : did,
                            "zone_name" : zone["name"],
                        },
                    )

        # Clean up lost tracks
        gone = {k for k in self._inside if k[0] not in
                {(t.global_id or t.id) for t in tracked}}
        for k in gone:
            del self._inside[k]

    def draw_zones(self, frame: np.ndarray) -> np.ndarray:
        """Draw zone polygons on frame. Call from camera_processor."""
        for zone in self._zones:
            pts   = np.array(zone["points"], dtype=np.int32)
            color = (0,80,200) if zone.get("type")=="restricted" else (0,160,80)
            cv2.polylines(frame, [pts], True, color, 1, cv2.LINE_AA)
            # Zone name at centroid
            M = cv2.moments(pts)
            if M["m00"] > 0:
                cx = int(M["m10"]/M["m00"])
                cy = int(M["m01"]/M["m00"])
                cv2.putText(frame, zone["name"], (cx-20, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            color, 1, cv2.LINE_AA)
        return frame

    def reload(self):
        """Reload zones.json at runtime."""
        self._zones = self._load_zones()


# ─────────────────────────────────────────────────────────────
#  5. CROWD ANALYZER
# ─────────────────────────────────────────────────────────────

class CrowdAnalyzer:
    """
    Counts persons per frame.
    Fires CROWD_DETECTED when count > threshold.
    Builds a heatmap of person centroid positions.
    """

    THRESHOLD      = 8    # persons to trigger CROWD alert
    HEATMAP_DECAY  = 0.97 # older positions fade

    def __init__(self, camera_id: int, frame_h=360, frame_w=480):
        self.camera_id   = camera_id
        self._heatmap    = np.zeros((frame_h, frame_w), dtype=np.float32)
        self._person_cnt = 0

    def update(self, tracked: list) -> int:
        """Returns current person count."""
        persons = [t for t in tracked if t.class_id == 0]
        self._person_cnt = len(persons)

        # Decay heatmap
        self._heatmap *= self.HEATMAP_DECAY

        # Add centroids
        for t in persons:
            cx, cy = t.centroid
            h, w   = self._heatmap.shape
            if 0 <= cx < w and 0 <= cy < h:
                cv2.circle(self._heatmap, (cx,cy), 20, 1.0, -1)

        # Alert
        if self._person_cnt >= self.THRESHOLD:
            ALERT_SYSTEM.fire(
                alert_type = "CROWD_DETECTED",
                camera_id  = self.camera_id,
                message    = f"Crowd: {self._person_cnt} persons",
                metadata   = {"count": self._person_cnt},
            )

        return self._person_cnt

    def get_heatmap_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Returns frame with translucent heatmap blended on top.
        Called only when heatmap toggle is active.
        """
        if self._heatmap.max() < 1e-3:
            return frame
        norm = cv2.normalize(self._heatmap, None, 0, 255, cv2.NORM_MINMAX)
        colored = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_JET)
        mask = (norm > 10).astype(np.uint8)[:,:,None]
        blended = cv2.addWeighted(frame, 0.6, colored, 0.4, 0)
        return np.where(mask, blended, frame)

    @property
    def person_count(self) -> int:
        return self._person_cnt


# ─────────────────────────────────────────────────────────────
#  6. TRAFFIC ANALYZER
# ─────────────────────────────────────────────────────────────

class TrafficAnalyzer:
    """
    Rolling-average vehicle count → traffic state.

    States: NORMAL / HEAVY / CONGESTION
    Optional: virtual counting line (defined in config)
    """

    WINDOW       = 150    # frames for rolling average
    NORMAL_MAX   = 4
    HEAVY_MAX    = 9
    # CONGESTION  > 9

    def __init__(self, camera_id: int):
        self.camera_id   = camera_id
        self._history    = deque(maxlen=self.WINDOW)
        self._state      = "NORMAL"
        self._prev_state = "NORMAL"

    def update(self, tracked: list) -> str:
        """Returns current traffic state string."""
        vc = sum(1 for t in tracked if t.class_id in VEHICLE_CLASS_IDS)
        self._history.append(vc)

        avg = sum(self._history) / max(1, len(self._history))

        if avg > self.HEAVY_MAX:
            new_state = "CONGESTION"
        elif avg > self.NORMAL_MAX:
            new_state = "HEAVY"
        else:
            new_state = "NORMAL"

        # Fire alert on state change (not on every frame)
        if new_state != self._prev_state:
            self._prev_state = new_state
            self._state      = new_state
            if new_state in ("HEAVY", "CONGESTION"):
                ALERT_SYSTEM.fire(
                    alert_type = new_state.replace(" ","_") if new_state != "HEAVY"
                                 else "HEAVY_TRAFFIC",
                    camera_id  = self.camera_id,
                    message    = f"Traffic: {new_state} ({avg:.1f} vehicles avg)",
                    metadata   = {"state": new_state, "avg_vehicles": round(avg,1)},
                )
        else:
            self._state = new_state

        return self._state

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_color(self) -> Tuple[int,int,int]:
        """BGR color for HUD display."""
        return {
            "NORMAL"    : (0, 200, 80),
            "HEAVY"     : (0, 180, 255),
            "CONGESTION": (0, 60,  220),
        }.get(self._state, (200,200,200))


# ─────────────────────────────────────────────────────────────
#  BEHAVIOR ANALYZER  (per-camera facade)
# ─────────────────────────────────────────────────────────────

class BehaviorAnalyzer:
    """
    Single entry point for all behavioral analysis.
    One instance per camera. All detectors share ALERT_SYSTEM.

    Usage in camera_processor.py:
        self.behavior = BehaviorAnalyzer(camera_id, self.tracker)

        # In get_frame(), after assign_global_ids:
        self.behavior.update(tracked, frame)

        # Optional overlays:
        if self.show_heatmap:
            out = self.behavior.crowd.get_heatmap_overlay(out)
        if self.show_zones:
            out = self.behavior.zones.draw_zones(out)
    """

    def __init__(self, camera_id: int, tracker=None):
        self.camera_id = camera_id
        self.ambulance = AmbulanceDetector(camera_id)
        self.accident  = AccidentDetector(camera_id, tracker)
        self.dwell     = DwellTracker(camera_id)
        self.zones     = ZoneManager(camera_id)
        self.crowd     = CrowdAnalyzer(camera_id)
        self.traffic   = TrafficAnalyzer(camera_id)
        logger.info(f"[BehaviorAnalyzer] Camera {camera_id} ready.")

    def set_tracker(self, tracker):
        """Call after tracker is created in camera_processor."""
        self.accident.set_tracker(tracker)

    def update(self, tracked: list, frame: np.ndarray):
        """Run all detectors. Call every frame."""
        self.ambulance.update(tracked, frame)
        self.accident.update(tracked, frame)
        self.dwell.update(tracked)
        self.zones.update(tracked)
        self.crowd.update(tracked)
        self.traffic.update(tracked)