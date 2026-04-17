"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/camera_processor.py
  Purpose : Per-camera orchestrator — single draw authority.

  GHOST BOX / IRRELEVANT BOX FIXES:

  FIX 1 — Higher MIN_AREA (400 → 900)
    Tiny detections (< 30×30 px) are almost always noise —
    shadows, reflections, partial objects at frame edges.
    Filtering them before DeepSort stops ghost tracks forming.

  FIX 2 — Higher DEDUP_IOU (0.20 → 0.45)
    Unconfirmed raw detections were drawing thin boxes on top
    of confirmed tracks because IoU threshold was too low.
    Now only truly separate objects draw an unconfirmed box.

  FIX 3 — Unconfirmed boxes only shown if conf > 0.55
    Extra guard: only draw unconfirmed detection if it's
    high-confidence enough to be a real object. Eliminates
    the faint green boxes around noise detections.

  FIX 4 — Vehicle target info fed to target panel
    VehicleAnalyzer info (color, shape) now passed to
    TargetManager so the info panel shows vehicle details.

  FIX 5 — Target highlighting unified
    _draw_all no longer tries to highlight the target — this
    caused double-highlighting. TargetManager.draw() is the
    sole draw authority for the locked target.
=============================================================
"""

import cv2, numpy as np, logging, time, threading
from collections import deque
from typing import List, Tuple, Optional

from app.detection import ObjectDetector, FrameResult, _get_color
from app.tracking import PersonTracker, TrackResult
from app.target_manager import TargetManager
from app.cross_camera_tracker import GLOBAL_TRACKER
from app.vehicle_analysis import VehicleAnalyzer, VEHICLE_CLASS_IDS
from app.behavior_analysis import BehaviorAnalyzer
from app.alert_system import ALERT_SYSTEM

logging.basicConfig(level=logging.INFO)


def _iou(a: Tuple, b: Tuple) -> float:
    ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
    ix1,iy1 = max(ax1,bx1), max(ay1,by1)
    ix2,iy2 = min(ax2,bx2), min(ay2,by2)
    inter = max(0,ix2-ix1) * max(0,iy2-iy1)
    if inter == 0: return 0.0
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / union if union > 0 else 0.0


class CameraProcessor:

    # FIX 1: was 0.20 — too permissive, drew boxes on tracked objects
    DEDUP_IOU          = 0.45

    # FIX 2: only show unconfirmed boxes above this confidence
    UNCONFIRMED_MIN_CONF = 0.55

    def __init__(self, camera_id: int, source=0):
        self.camera_id    = camera_id
        self.source       = source
        self.logger       = logging.getLogger(f"Camera-{camera_id}")
        self.frame_width  = 480
        self.frame_height = 360

        self.is_ip = isinstance(source, str) and source.startswith("http")

        self.cap = cv2.VideoCapture(source)
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if self.cap is None or not self.cap.isOpened():
            self.logger.warning(f"Camera {camera_id} — no signal.")

        self.detector = ObjectDetector(
            camera_id  = camera_id,
            model_path = "backend/yolov8n.pt",
            confidence = 0.45,
            img_size   = 320,
        )
        self.detector.detection_interval = 2 if self.is_ip else 3

        self.tracker          = PersonTracker(camera_id)
        self.tracker.set_class_names(self.detector.class_names)
        self.target_manager   = TargetManager(camera_id)
        self.vehicle_analyzer = VehicleAnalyzer(camera_id)
        self.behavior         = BehaviorAnalyzer(camera_id, self.tracker)

        # ── Face recognition — background thread ──────────────
        from app.face_recognition_module import FaceRecognizer
        self.face_recognizer  = FaceRecognizer(camera_id)
        self.face_recognizer.process_every = 10

        self._face_result     = None
        self._face_lock       = threading.Lock()
        self._face_frame_buf  = None
        self._face_frame_lock = threading.Lock()
        self._face_thread     = threading.Thread(
            target=self._face_worker, daemon=True,
            name=f"FaceWorker-{camera_id}"
        )
        self._face_thread.start()

        # Display toggles
        self._trails      : dict = {}
        self.last_seen    : dict = {}
        self.show_trails  : bool = True
        self.show_debug_id: bool = False
        self.show_heatmap : bool = False
        self.show_zones   : bool = True

        self._behavior_frame = 0

        self.prev_time = time.time()
        self.fps_queue = deque(maxlen=10)
        self.avg_fps   = 0.0

        self.logger.info(
            f"CameraProcessor ready cam={camera_id} ip={self.is_ip}"
        )

    # ── Background face worker ────────────────────────────────

    def _face_worker(self):
        frame_counter = 0
        while True:
            try:
                with self._face_frame_lock:
                    frame = self._face_frame_buf
                if frame is None:
                    time.sleep(0.01); continue

                frame_counter += 1
                if frame_counter % self.face_recognizer.process_every != 0:
                    time.sleep(0.005); continue

                result = self.face_recognizer.recognize_in_frame(frame, [])
                with self._face_lock:
                    self._face_result = result
                with self._face_frame_lock:
                    self._face_frame_buf = None

            except Exception as e:
                self.logger.debug(f"[FaceWorker] {e}")
                time.sleep(0.05)

    # ── Public ────────────────────────────────────────────────

    def get_frame(self) -> np.ndarray:
        if self.cap is None or not self.cap.isOpened():
            return self._no_signal()

        # Drain IP camera buffer
        if self.is_ip:
            for _ in range(4): self.cap.grab()

        ret, frame = self.cap.read()
        if not ret:
            self.logger.warning("Camera lost — reconnecting...")
            if self.cap is not None: self.cap.release()
            time.sleep(1)
            self.cap = cv2.VideoCapture(self.source)
            if self.cap is not None:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return self._no_signal()

        frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        now  = time.time(); diff = now - self.prev_time
        if diff > 0:
            self.fps_queue.append(1.0 / diff)
            self.avg_fps = sum(self.fps_queue) / len(self.fps_queue)
        self.prev_time = now

        # Feed frame to face background worker
        with self._face_frame_lock:
            self._face_frame_buf = frame.copy()

        # 1 — Detect
        result = self.detector.detect(frame)

        # 2 — Track
        tracked: List[TrackResult] = self.tracker.update_tracks(
            result.to_deepsort_format(), frame
        )

        # 3 — Apply face results from background thread
        with self._face_lock:
            face_res = self._face_result
        if face_res is not None:
            self._attach_face_ids(face_res, tracked)

        # 4 — Global IDs
        GLOBAL_TRACKER.assign_global_ids(
            camera_id       = self.camera_id,
            tracked_objects = tracked,
            frame           = frame,
        )

        # Update last-seen (for trail persistence)
        seen_now = time.time()
        for track in tracked:
            if track.global_id:
                self.last_seen[track.global_id] = seen_now
        for gid in list(self.last_seen):
            if seen_now - self.last_seen[gid] >= 2:
                del self.last_seen[gid]

        # 5 — Vehicle analysis
        self.vehicle_analyzer.update(tracked, frame, self.camera_id)

        # 6 — Feed vehicle info to target panel if target is a vehicle
        if self.target_manager.has_target:
            tid = self.target_manager.target_id
            vinfo = self.vehicle_analyzer.get_info(tid)
            if vinfo:
                self.target_manager.update_vehicle_info(
                    vinfo.color_name, vinfo.shape_type
                )

        # 7 — Behavior analysis (every 2nd frame)
        self._behavior_frame += 1
        if self._behavior_frame % 2 == 0:
            self.behavior.update(tracked, frame)

        # 8 — Trails
        self._attach_track_ids(result, tracked)
        self._update_trails(tracked)

        # 9 — Target manager
        self.target_manager.update(tracked, frame)

        # 10 — Draw
        out = frame.copy()
        out = self._draw_all(out, result, tracked)
        if self.show_trails:
            out = self._draw_trails(out, tracked)
        if self.show_zones:
            out = self.behavior.zones.draw_zones(out)
        if self.show_heatmap:
            out = self.behavior.crowd.get_heatmap_overlay(out)
        out = self._draw_hud(out, tracked)
        out = self.target_manager.draw(out)   # target overlay LAST

        if face_res is not None:
            out = self.face_recognizer.annotate(out, face_res)

        return out

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    # ── Draw ──────────────────────────────────────────────────

    def _draw_all(self, frame, result, tracked):
        font = cv2.FONT_HERSHEY_SIMPLEX; fs = 0.42
        confirmed_bboxes = [t.bbox for t in tracked]

        # ── Confirmed tracks ───────────────────────────────────
        for t in tracked:
            x1, y1, x2, y2 = t.bbox
            is_vehicle  = t.class_id in VEHICLE_CLASS_IDS
            display_id  = t.global_id if t.global_id else t.id
            target_id   = self.target_manager.target_id

            # Is this the locked target? TargetManager.draw() will
            # highlight it — we just draw a slightly different box
            is_target = (
                target_id and (
                    str(display_id) == str(target_id) or
                    str(t.id) == str(target_id)
                )
            )
            if is_target:
                # Let TargetManager.draw() handle the full highlight
                # Just draw a dim box so the label still appears
                box_col   = (60, 60, 60)
                badge_col = (40, 40, 40)
            elif is_vehicle:
                is_cross = (
                    t.global_id is not None and
                    GLOBAL_TRACKER._gallery.get(
                        t.global_id,
                        type("", (), {"is_cross_camera": lambda s: False})()
                    ).is_cross_camera()
                )
                if is_cross:
                    box_col, badge_col = (0, 200, 255), (0, 120, 180)  # cyan
                else:
                    box_col, badge_col = (0, 180, 255), (0, 110, 180)  # orange
            else:
                is_cross = (
                    t.global_id is not None and
                    GLOBAL_TRACKER._gallery.get(
                        t.global_id,
                        type("", (), {"is_cross_camera": lambda s: False})()
                    ).is_cross_camera()
                )
                if is_cross:
                    box_col, badge_col = (0, 220, 220), (0, 130, 130)  # cyan
                else:
                    box_col, badge_col = (0, 210, 0),   (0, 130, 0)    # green

            cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 2)

            # Label
            dwell     = self.behavior.dwell.get_dwell(display_id)
            dwell_tag = f" {int(dwell)}s" if dwell >= 10 else ""
            label     = f"{t.class_name}  {display_id}{dwell_tag}"

            (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
            by1 = max(y1 - th - 8, 0); by2 = by1 + th + 6
            cv2.rectangle(frame, (x1, by1), (x1+tw+8, by2), badge_col, -1)
            cv2.putText(frame, label, (x1+4, by2-3),
                        font, fs, (255, 255, 255), 1, cv2.LINE_AA)

            # Cross-cam pill
            is_cross_final = (
                t.global_id is not None and
                GLOBAL_TRACKER._gallery.get(
                    t.global_id,
                    type("", (), {"is_cross_camera": lambda s: False})()
                ).is_cross_camera()
            )
            if is_cross_final:
                pill = " CROSS "
                (pw, ph), _ = cv2.getTextSize(pill, font, 0.35, 1)
                py1 = by1 - ph - 4; py2 = by1 - 1
                if py1 >= 0:
                    cv2.rectangle(frame, (x1, py1), (x1+pw+4, py2),
                                  (180, 120, 0), -1)
                    cv2.putText(frame, pill, (x1+2, py2-2),
                                font, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

            # Vehicle info row
            if is_vehicle:
                vinfo = self.vehicle_analyzer.get_info(display_id)
                if vinfo and (vinfo.color_name or vinfo.shape_type):
                    row_y = by2 + 1; x_cur = x1
                    if vinfo.color_name:
                        cv2.rectangle(frame, (x_cur, row_y),
                                      (x_cur+12, row_y+12), vinfo.color_bgr, -1)
                        cv2.rectangle(frame, (x_cur, row_y),
                                      (x_cur+12, row_y+12), (200, 200, 200), 1)
                        cn = vinfo.color_name
                        (cnw, _), _ = cv2.getTextSize(cn, font, 0.34, 1)
                        cx2 = x_cur + 15
                        cv2.rectangle(frame, (cx2-1, row_y),
                                      (cx2+cnw+3, row_y+12), (30, 30, 30), -1)
                        cv2.putText(frame, cn, (cx2, row_y+10),
                                    font, 0.34, (220, 220, 220), 1, cv2.LINE_AA)
                        x_cur += 15 + cnw + 6
                    if vinfo.shape_type:
                        st = vinfo.shape_type
                        (stw, _), _ = cv2.getTextSize(st, font, 0.34, 1)
                        cv2.rectangle(frame, (x_cur, row_y),
                                      (x_cur+stw+6, row_y+12), (60, 60, 100), -1)
                        cv2.putText(frame, st, (x_cur+3, row_y+10),
                                    font, 0.34, (180, 180, 255), 1, cv2.LINE_AA)

            if self.show_debug_id:
                dbg = t.id
                (dw, dh), _ = cv2.getTextSize(dbg, font, 0.32, 1)
                cv2.rectangle(frame, (x1, y2), (x1+dw+6, y2+dh+4),
                              (40, 40, 40), -1)
                cv2.putText(frame, dbg, (x1+3, y2+dh+1),
                            font, 0.32, (160, 160, 160), 1, cv2.LINE_AA)

        # ── Unconfirmed detections ─────────────────────────────
        # FIX: only draw if (1) not overlapping a confirmed track
        #      AND (2) confidence is high enough to be real
        for d in result.detections:
            if d.confidence < self.UNCONFIRMED_MIN_CONF:
                continue  # FIX: skip low-confidence noise
            db = (d.box.x1, d.box.y1, d.box.x2, d.box.y2)
            if any(_iou(db, tb) > self.DEDUP_IOU for tb in confirmed_bboxes):
                continue  # FIX: already tracked — skip

            color = _get_color(d.class_id); b = d.box
            cv2.rectangle(frame, (b.x1, b.y1), (b.x2, b.y2), color, 1)
            lbl = f"{d.class_name} {d.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(lbl, font, 0.38, 1)
            by1 = max(b.y1-th-6, 0); by2 = by1 + th + 4
            cv2.rectangle(frame, (b.x1, by1), (b.x1+tw+6, by2), color, -1)
            cv2.putText(frame, lbl, (b.x1+3, by2-2),
                        font, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def _draw_trails(self, frame, tracked):
        for t in tracked:
            did = t.global_id if t.global_id else t.id
            pts = list(self._trails.get(did, []))
            if len(pts) < 2: continue
            n = len(pts)
            for i in range(1, n):
                a  = i / n; th = max(1, int(a*3)); iv = int(80+140*a)
                color = (0, iv//2, iv) if t.class_id in VEHICLE_CLASS_IDS \
                        else (0, iv, 0)
                cv2.line(frame, pts[i-1], pts[i], color, th, cv2.LINE_AA)
        return frame

    def _draw_hud(self, frame, tracked):
        h, w = frame.shape[:2]; font = cv2.FONT_HERSHEY_SIMPLEX
        bar_y = h - 28; ov = frame.copy()
        cv2.rectangle(ov, (0, bar_y), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)
        cv2.line(frame, (0, bar_y), (w, bar_y), (60, 60, 60), 1)
        ty = h - 8

        pc = sum(1 for t in tracked if t.class_id not in VEHICLE_CLASS_IDS)
        vc = sum(1 for t in tracked if t.class_id in VEHICLE_CLASS_IDS)
        ts = self.behavior.traffic.state
        tc = self.behavior.traffic.state_color

        cv2.putText(frame, f"Cam{self.camera_id}",
                    (4, ty), font, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        ct = "IP" if self.is_ip else "CAM"
        cv2.putText(frame, f"{ct} {int(self.avg_fps)}",
                    (56, ty), font, 0.42, (0, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(frame, f"P:{pc}",
                    (112, ty), font, 0.42, (0, 220, 80), 1, cv2.LINE_AA)
        cv2.putText(frame, f"V:{vc}",
                    (144, ty), font, 0.42, (0, 180, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, ts,
                    (178, ty), font, 0.40, tc, 1, cv2.LINE_AA)

        ua = ALERT_SYSTEM.unacknowledged_count()
        if ua > 0:
            badge = f"!{ua}"
            (bw, bh), _ = cv2.getTextSize(badge, font, 0.40, 1)
            bx = w - bw - 26; by_top = bar_y + 3
            cv2.rectangle(frame, (bx-3, by_top), (bx+bw+3, by_top+bh+4),
                          (0, 0, 180), -1)
            cv2.putText(frame, badge, (bx, by_top+bh+1),
                        font, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

        ms = f"{self.detector.last_result.inference_ms:.0f}ms"
        (mw, _), _ = cv2.getTextSize(ms, font, 0.38, 1)
        cv2.putText(frame, ms, (w-mw-4, ty),
                    font, 0.38, (130, 130, 130), 1, cv2.LINE_AA)

        tag = f" Cam{self.camera_id} "
        (tw, th), _ = cv2.getTextSize(tag, font, 0.38, 1)
        cv2.rectangle(frame, (0, 0), (tw+4, th+6), (30, 30, 30), -1)
        cv2.putText(frame, tag, (2, th+2),
                    font, 0.38, (160, 160, 160), 1, cv2.LINE_AA)
        return frame

    # ── Helpers ───────────────────────────────────────────────

    def _update_trails(self, tracked):
        active = set()
        for t in tracked:
            did = t.global_id if t.global_id else t.id
            active.add(did)
            if did not in self._trails:
                self._trails[did] = deque(maxlen=20)
            self._trails[did].append(t.centroid)
        for tid in list(self._trails):
            if tid not in active and tid not in self.last_seen:
                del self._trails[tid]

    def _attach_track_ids(self, result, tracked):
        for track in tracked:
            tx1, ty1, tx2, ty2 = track.bbox
            tcx = (tx1+tx2)//2; tcy = (ty1+ty2)//2
            best_det = None; best_d = float("inf")
            for det in result.detections:
                dx, dy = det.box.center
                d = abs(dx-tcx) + abs(dy-tcy)
                if d < best_d: best_d = d; best_det = det
            if best_det and best_d < 60:
                try:
                    best_det.track_id = int(track.id.split("ID")[-1])
                except Exception:
                    best_det.track_id = None

    def _attach_face_ids(self, face_res, tracked):
        for face in face_res.known_faces:
            best_track = None; best_iou = 0.0
            for track in tracked:
                score = _iou(face.box_cv2, track.bbox)
                if score > best_iou:
                    best_iou = score; best_track = track
            if best_track and best_iou > 0.2:
                best_track.face_id   = face.name
                best_track.global_id = face.name
                face.track_id        = best_track.id

    def _no_signal(self):
        frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        cx = self.frame_width//2; cy = self.frame_height//2 - 20
        cv2.circle(frame, (cx, cy), 30, (0, 0, 180), -1)
        cv2.circle(frame, (cx, cy), 30, (0, 0, 100), 2)
        cv2.line(frame, (cx-16, cy-16), (cx+16, cy+16), (255, 255, 255), 3)
        cv2.line(frame, (cx+16, cy-16), (cx-16, cy+16), (255, 255, 255), 3)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"Camera {self.camera_id}",
                    (cx-62, cy+52), font, 0.60, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, "NO SIGNAL",
                    (cx-60, cy+80), font, 0.70, (0, 60, 220), 2, cv2.LINE_AA)
        cv2.putText(frame, "Check connection",
                    (cx-72, cy+108), font, 0.40, (100, 100, 100), 1, cv2.LINE_AA)
        return frame