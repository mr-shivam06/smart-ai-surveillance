"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/camera_processor.py
  Purpose : Per-camera orchestrator — single draw authority.

  BUGS FIXED:
    1. CRITICAL — indentation in _draw_all():
       The original file had the label, badge drawing, vehicle
       info, and the entire unconfirmed-detections loop ALL
       outside the `for obj in tracked_objects:` loop.
       Only the first object's bbox was being used for all
       subsequent draws. Fixed — everything is correctly
       indented inside its respective loop.

    2. CRITICAL — call order:
       vehicle_analyzer.update() was called BEFORE
       assign_global_ids(), meaning global_id was always None
       when vehicle_analysis tried to use it. Fixed:
         track → assign_global_ids → vehicle_analyzer.update

    3. Face recognition was silently dropped. Restored.

    4. Deduplication: replaced (center//20) grid cells with
       IoU > 0.20 check — accurate regardless of YOLO/DeepSORT
       bbox drift.

    5. IP camera buffer drain: restored grab()+grab() before
       read() for IP streams only.

  PIPELINE (correct order):
    capture → resize → detect → track →
    assign_global_ids(frame) →          ← global IDs set here
    vehicle_analyzer.update(frame) →    ← uses global IDs
    target_manager.update() →
    draw (one pass, no overlap) →
    face_recognizer.annotate()
=============================================================
"""

import cv2, numpy as np, logging, time
from collections import deque
from typing import List, Tuple

from detection import ObjectDetector, FrameResult, _get_color
from tracking import PersonTracker, TrackResult
from target_manager import TargetManager
from cross_camera_tracker import GLOBAL_TRACKER
from vehicle_analysis import VehicleAnalyzer, VEHICLE_CLASS_IDS

logging.basicConfig(level=logging.INFO)


def _iou(a: Tuple, b: Tuple) -> float:
    ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
    ix1,iy1 = max(ax1,bx1), max(ay1,by1)
    ix2,iy2 = min(ax2,bx2), min(ay2,by2)
    inter = max(0,ix2-ix1)*max(0,iy2-iy1)
    if inter == 0: return 0.0
    union = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/union if union > 0 else 0.0


class CameraProcessor:

    DEDUP_IOU = 0.20  # suppress raw detection if IoU > this with any track

    def __init__(self, camera_id: int, source=0):
        self.camera_id    = camera_id   # set FIRST
        self.source       = source
        self.logger       = logging.getLogger(f"Camera-{camera_id}")
        self.frame_width  = 480
        self.frame_height = 360

        self.is_ip = isinstance(source, str) and source.startswith("http")

        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            self.logger.warning(f"Camera {camera_id} — no signal.")

        self.detector = ObjectDetector(
            camera_id=camera_id, model_path="backend/yolov8n.pt",
            confidence=0.50, img_size=416,
        )
        # IP cameras benefit from slightly faster inference cycle
        self.detector.detection_interval = 2 if self.is_ip else 3

        self.tracker        = PersonTracker(camera_id)
        self.tracker.set_class_names(self.detector.class_names)
        self.target_manager  = TargetManager(camera_id)
        self.vehicle_analyzer = VehicleAnalyzer(camera_id)

        # Face recognizer — after camera_id is set
        from face_recognition_module import FaceRecognizer
        self.face_recognizer = FaceRecognizer(camera_id)
        self.face_recognizer.process_every = 6

        # Trails: display_id → deque of (cx, cy)
        self._trails: dict        = {}
        self.show_trails: bool    = True
        self.show_debug_id: bool  = False  # 'D' key: show local DeepSORT ID

        self.prev_time = time.time()
        self.fps_queue = deque(maxlen=10)
        self.avg_fps   = 0.0

        self.logger.info(
            f"CameraProcessor ready cam={camera_id} "
            f"src={source!r} ip={self.is_ip}"
        )

    # ──────────────────────────────────────────────────────────
    #  PUBLIC
    # ──────────────────────────────────────────────────────────

    def get_frame(self) -> np.ndarray:
        if not self.cap.isOpened():
            return self._no_signal()

        # Drain IP camera buffer — prevents stale frame lag
        if self.is_ip:
            self.cap.grab()
            self.cap.grab()

        ret, frame = self.cap.read()
        if not ret:
            return self._no_signal()

        frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        now = time.time(); diff = now - self.prev_time
        if diff > 0:
            self.fps_queue.append(1.0/diff)
            self.avg_fps = sum(self.fps_queue)/len(self.fps_queue)
        self.prev_time = now

        # 1 — Detect
        result: FrameResult = self.detector.detect(frame)

        # 2 — Track (local IDs only at this point)
        tracked: List[TrackResult] = self.tracker.update_tracks(
            result.to_deepsort_format(), frame
        )

        # 3 — Assign global IDs via cross-camera Re-ID
        #     MUST be before vehicle_analyzer and face recognition
        GLOBAL_TRACKER.assign_global_ids(
            camera_id=self.camera_id,
            tracked_objects=tracked,
            frame=frame,
        )

        # 4 — Vehicle analysis (uses global_id now set above)
        self.vehicle_analyzer.update(tracked, frame, self.camera_id)

        # 5 — Attach local IDs to Detection objects (for face hints)
        self._attach_track_ids(result, tracked)

        # 6 — Update centroid trails
        self._update_trails(tracked)

        # 7 — Target manager
        self.target_manager.update(tracked, frame)

        # 8 — Draw (one pass, strict order, no overlap)
        out = frame.copy()
        out = self._draw_all(out, result, tracked)
        if self.show_trails:
            out = self._draw_trails(out, tracked)
        out = self._draw_hud(out, tracked)
        out = self.target_manager.draw(out)

        # 9 — Face recognition (last — draws on top)
        face_res = self.face_recognizer.recognize_in_frame(
            frame, result.persons()
        )
        out = self.face_recognizer.annotate(out, face_res)

        return out

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
        self.logger.info(f"Camera {self.camera_id} released.")

    # ──────────────────────────────────────────────────────────
    #  DRAW — single authority, no double boxes
    # ──────────────────────────────────────────────────────────

    def _draw_all(
        self,
        frame  : np.ndarray,
        result : FrameResult,
        tracked: List[TrackResult],
    ) -> np.ndarray:
        """
        FIX: Every draw statement is now INSIDE its for loop.
        The original file had massive indentation errors here
        that caused all labels to draw using the last object's
        coordinates only.
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs   = 0.42

        confirmed_bboxes = [t.bbox for t in tracked]

        # ── Confirmed tracks ──────────────────────────────────
        for t in tracked:                        # ← ALL of this is inside the loop
            x1, y1, x2, y2 = t.bbox
            is_vehicle   = t.class_id in VEHICLE_CLASS_IDS
            is_cross_cam = (t.global_id is not None
                            and GLOBAL_TRACKER._gallery.get(t.global_id,
                                type("",(),{"is_cross_camera":lambda s:False})()
                            ).is_cross_camera())
            display_id = t.global_id if t.global_id else t.id

            # Box color
            if is_vehicle:
                box_col, badge_col = (0,180,255), (0,110,180)  # orange
            elif is_cross_cam:
                box_col, badge_col = (0,220,220), (0,130,130)  # cyan
            else:
                box_col, badge_col = (0,210,0),   (0,130,0)    # green

            cv2.rectangle(frame, (x1,y1), (x2,y2), box_col, 2)

            # Main label badge
            label = f"{t.class_name}  {display_id}"
            (tw,th),_ = cv2.getTextSize(label, font, fs, 1)
            by1 = max(y1-th-8, 0); by2 = by1+th+6
            cv2.rectangle(frame, (x1,by1), (x1+tw+8,by2), badge_col, -1)
            cv2.putText(frame, label, (x1+4,by2-3),
                        font, fs, (255,255,255), 1, cv2.LINE_AA)

            # Cross-cam pill
            if is_cross_cam:
                pill = " CROSS "
                (pw,ph),_ = cv2.getTextSize(pill,font,0.35,1)
                py1 = by1-ph-4; py2 = by1-1
                if py1 >= 0:
                    cv2.rectangle(frame,(x1,py1),(x1+pw+4,py2),(180,120,0),-1)
                    cv2.putText(frame,pill,(x1+2,py2-2),font,0.35,
                                (255,255,255),1,cv2.LINE_AA)

            # Vehicle info row (color chip + shape type)
            if is_vehicle:
                vinfo = self.vehicle_analyzer.get_info(display_id)
                if vinfo and (vinfo.color_name or vinfo.shape_type):
                    row_y = by2 + 1
                    x_cur = x1

                    # Color chip
                    if vinfo.color_name:
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+12,row_y+12),
                                      vinfo.color_bgr,-1)
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+12,row_y+12),
                                      (200,200,200),1)
                        cn = vinfo.color_name
                        (cnw,_),_ = cv2.getTextSize(cn,font,0.34,1)
                        cx2 = x_cur+15
                        cv2.rectangle(frame,(cx2-1,row_y),(cx2+cnw+3,row_y+12),
                                      (30,30,30),-1)
                        cv2.putText(frame,cn,(cx2,row_y+10),font,0.34,
                                    (220,220,220),1,cv2.LINE_AA)
                        x_cur += 15 + cnw + 6

                    # Shape type badge
                    if vinfo.shape_type:
                        st = vinfo.shape_type
                        (stw,sth),_ = cv2.getTextSize(st,font,0.34,1)
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+stw+6,row_y+12),
                                      (60,60,100),-1)
                        cv2.putText(frame,st,(x_cur+3,row_y+10),font,0.34,
                                    (180,180,255),1,cv2.LINE_AA)

            # Debug: show local DeepSORT ID below box
            if self.show_debug_id:
                dbg = t.id
                (dw,dh),_ = cv2.getTextSize(dbg,font,0.32,1)
                cv2.rectangle(frame,(x1,y2),(x1+dw+6,y2+dh+4),(40,40,40),-1)
                cv2.putText(frame,dbg,(x1+3,y2+dh+1),font,0.32,
                            (160,160,160),1,cv2.LINE_AA)

        # ── Unconfirmed raw detections — thin colored ──────────
        for d in result.detections:              # ← separate loop, correct indent
            det_bbox = (d.box.x1,d.box.y1,d.box.x2,d.box.y2)
            if any(_iou(det_bbox,tb) > self.DEDUP_IOU for tb in confirmed_bboxes):
                continue
            color = _get_color(d.class_id); b = d.box
            cv2.rectangle(frame,(b.x1,b.y1),(b.x2,b.y2),color,1)
            lbl = f"{d.class_name} {d.confidence:.0%}"
            (tw,th),_ = cv2.getTextSize(lbl,font,0.38,1)
            by1=max(b.y1-th-6,0); by2=by1+th+4
            cv2.rectangle(frame,(b.x1,by1),(b.x1+tw+6,by2),color,-1)
            cv2.putText(frame,lbl,(b.x1+3,by2-2),font,0.38,
                        (255,255,255),1,cv2.LINE_AA)

        return frame

    def _draw_trails(self, frame, tracked):
        for t in tracked:
            display_id = t.global_id if t.global_id else t.id
            pts = list(self._trails.get(display_id, []))
            if len(pts) < 2: continue
            is_veh = t.class_id in VEHICLE_CLASS_IDS
            n = len(pts)
            for i in range(1, n):
                a  = i/n; th = max(1,int(a*3)); iv = int(80+140*a)
                if is_veh:   color = (0, iv//2, iv)    # orange trail
                else:        color = (0, iv,    0)     # green trail
                cv2.line(frame, pts[i-1], pts[i], color, th, cv2.LINE_AA)
        return frame

    def _draw_hud(self, frame, tracked):
        h, w = frame.shape[:2]; font = cv2.FONT_HERSHEY_SIMPLEX
        bar_y = h-28; ov = frame.copy()
        cv2.rectangle(ov,(0,bar_y),(w,h),(0,0,0),-1)
        cv2.addWeighted(ov,0.65,frame,0.35,0,frame)
        cv2.line(frame,(0,bar_y),(w,bar_y),(60,60,60),1)
        ty = h-8

        pc = sum(1 for t in tracked if t.class_id not in VEHICLE_CLASS_IDS)
        vc = sum(1 for t in tracked if t.class_id in VEHICLE_CLASS_IDS)

        cv2.putText(frame,f"Cam {self.camera_id}",(6,ty),font,0.44,
                    (255,255,255),1,cv2.LINE_AA)
        cam_type = "IP" if self.is_ip else "CAM"
        cv2.putText(frame,f"{cam_type} FPS:{int(self.avg_fps)}",(68,ty),
                    font,0.44,(0,220,220),1,cv2.LINE_AA)
        cv2.putText(frame,f"P:{pc}",(175,ty),font,0.44,(0,220,80),1,cv2.LINE_AA)
        cv2.putText(frame,f"V:{vc}",(207,ty),font,0.44,(0,180,255),1,cv2.LINE_AA)

        mc = GLOBAL_TRACKER.multicamera_count
        if mc > 0:
            cv2.putText(frame,f"X:{mc}",(242,ty),font,0.44,
                        (0,220,220),1,cv2.LINE_AA)

        ms = f"{self.detector.last_result.inference_ms:.0f}ms"
        (mw,_),_ = cv2.getTextSize(ms,font,0.38,1)
        cv2.putText(frame,ms,(w-mw-6,ty),font,0.38,(130,130,130),1,cv2.LINE_AA)

        tag = f" Cam {self.camera_id} "
        (tw,th),_ = cv2.getTextSize(tag,font,0.38,1)
        cv2.rectangle(frame,(0,0),(tw+4,th+6),(30,30,30),-1)
        cv2.putText(frame,tag,(2,th+2),font,0.38,(160,160,160),1,cv2.LINE_AA)
        return frame

    # ──────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────

    def _update_trails(self, tracked: List[TrackResult]):
        active = set()
        for t in tracked:
            did = t.global_id if t.global_id else t.id
            active.add(did)
            if did not in self._trails:
                self._trails[did] = deque(maxlen=20)
            self._trails[did].append(t.centroid)
        for tid in set(self._trails) - active:
            del self._trails[tid]

    def _attach_track_ids(self, result: FrameResult, tracked: List[TrackResult]):
        """Write local track int to Detection.track_id for face recognition hints."""
        for track in tracked:
            tx1,ty1,tx2,ty2 = track.bbox
            tcx=(tx1+tx2)//2; tcy=(ty1+ty2)//2
            best_det=None; best_d=float("inf")
            for det in result.detections:
                dx,dy = det.box.center
                d = abs(dx-tcx)+abs(dy-tcy)
                if d < best_d: best_d=d; best_det=det
            if best_det and best_d < 60:
                try: best_det.track_id = int(track.id.split("ID")[-1])
                except: best_det.track_id = None

    def _no_signal(self) -> np.ndarray:
        frame = np.zeros((self.frame_height,self.frame_width,3),dtype=np.uint8)
        cx=self.frame_width//2; cy=self.frame_height//2-20
        cv2.circle(frame,(cx,cy),30,(0,0,180),-1)
        cv2.circle(frame,(cx,cy),30,(0,0,100),2)
        cv2.line(frame,(cx-16,cy-16),(cx+16,cy+16),(255,255,255),3)
        cv2.line(frame,(cx+16,cy-16),(cx-16,cy+16),(255,255,255),3)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame,f"Camera {self.camera_id}",(cx-62,cy+52),
                    font,0.60,(200,200,200),1,cv2.LINE_AA)
        cv2.putText(frame,"NO SIGNAL",(cx-60,cy+80),font,0.70,
                    (0,60,220),2,cv2.LINE_AA)
        cv2.putText(frame,"Check connection or source",(cx-98,cy+108),
                    font,0.40,(100,100,100),1,cv2.LINE_AA)
        return frame