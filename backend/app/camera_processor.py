"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/camera_processor.py
  Purpose : Per-camera orchestrator — single draw authority.

  DAY 7-9 ADDITIONS:
    - BehaviorAnalyzer wired in (ambulance, accident, dwell,
      zones, crowd, traffic)
    - show_heatmap toggle ('H' key) — crowd density overlay
    - show_zones toggle ('Z' key) — zone polygon outlines
    - Traffic state shown in HUD (NORMAL/HEAVY/CONGESTION)
    - Dwell time shown on track label if > 10s
    - Alert count badge in HUD (unacknowledged count)

  FULL PIPELINE ORDER:
    capture → resize → detect → track →
    assign_global_ids →
    vehicle_analyzer.update →
    behavior_analyzer.update →   ← NEW
    target_manager.update →
    draw →
    heatmap overlay (optional) →
    zone overlay (optional) →
    face_recognizer.annotate
=============================================================
"""

import cv2, numpy as np, logging, time
from collections import deque
from typing import List, Tuple

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
    inter = max(0,ix2-ix1)*max(0,iy2-iy1)
    if inter == 0: return 0.0
    union = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/union if union > 0 else 0.0


class CameraProcessor:

    DEDUP_IOU = 0.20

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
            camera_id=camera_id, model_path="backend/yolov8n.pt",
            confidence=0.50, img_size=416,
        )
        self.detector.detection_interval = 2 if self.is_ip else 3

        self.tracker         = PersonTracker(camera_id)
        self.tracker.set_class_names(self.detector.class_names)
        self.target_manager  = TargetManager(camera_id)
        self.vehicle_analyzer = VehicleAnalyzer(camera_id)
        self.behavior         = BehaviorAnalyzer(camera_id, self.tracker)

        from app.face_recognition_module import FaceRecognizer
        self.face_recognizer = FaceRecognizer(camera_id)
        self.face_recognizer.process_every = 6

        # Display toggles
        self._trails: dict        = {}
        self.last_seen: dict      = {}
        self.show_trails: bool    = True
        self.show_debug_id: bool  = False
        self.show_heatmap: bool   = False
        self.show_zones: bool     = True

        self.prev_time = time.time()
        self.fps_queue = deque(maxlen=10)
        self.avg_fps   = 0.0

        self.logger.info(f"CameraProcessor ready cam={camera_id}")

    # ── Public ────────────────────────────────────────────────

    def get_frame(self) -> np.ndarray:
        if self.cap is None or not self.cap.isOpened():
            return self._no_signal()

        if self.is_ip:
            self.cap.grab(); self.cap.grab()

        ret, frame = self.cap.read()
        if not ret:
            self.logger.warning("Camera lost. Reconnecting...")
            if self.cap is not None:
                self.cap.release()
            time.sleep(1)
            self.cap = cv2.VideoCapture(self.source)
            if self.cap is not None:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return self._no_signal()

        frame = cv2.resize(frame, (self.frame_width, self.frame_height))

        now = time.time(); diff = now - self.prev_time
        if diff > 0:
            self.fps_queue.append(1.0/diff)
            self.avg_fps = sum(self.fps_queue)/len(self.fps_queue)
        self.prev_time = now

        # 1 — Detect
        result = self.detector.detect(frame)

        # 2 — Track
        tracked: List[TrackResult] = self.tracker.update_tracks(
            result.to_deepsort_format(), frame
        )

        face_res = self.face_recognizer.recognize_in_frame(
            frame, result.persons()
        )
        self._attach_face_ids(face_res, tracked)

        # 3 — Global IDs (must be before all analysis)
        GLOBAL_TRACKER.assign_global_ids(
            camera_id=self.camera_id,
            tracked_objects=tracked,
            frame=frame,
        )
        if not hasattr(self, "last_seen"):
            self.last_seen = {}
        seen_now = time.time()
        for track in tracked:
            if track.global_id:
                self.last_seen[track.global_id] = seen_now
        for gid, last_seen in list(self.last_seen.items()):
            if seen_now - last_seen >= 2:
                del self.last_seen[gid]

        # 4 — Vehicle analysis
        self.vehicle_analyzer.update(tracked, frame, self.camera_id)

        # 5 — Behavioral analysis
        self.behavior.update(tracked, frame)

        # 6 — Attach local IDs to detections for face hints
        self._attach_track_ids(result, tracked)

        # 7 — Trails
        self._update_trails(tracked)

        # 8 — Target
        self.target_manager.update(tracked, frame)

        # 9 — Draw
        out = frame.copy()
        out = self._draw_all(out, result, tracked)
        if self.show_trails:
            out = self._draw_trails(out, tracked)
        if self.show_zones:
            out = self.behavior.zones.draw_zones(out)
        if self.show_heatmap:
            out = self.behavior.crowd.get_heatmap_overlay(out)
        out = self._draw_hud(out, tracked)
        out = self.target_manager.draw(out)

        out = self.face_recognizer.annotate(out, face_res)

        return out

    def release(self):
        if self.cap is not None and self.cap.isOpened(): self.cap.release()

    # ── Draw ──────────────────────────────────────────────────

    def _draw_all(self, frame, result, tracked):
        font = cv2.FONT_HERSHEY_SIMPLEX; fs = 0.42
        confirmed = [t.bbox for t in tracked]

        for t in tracked:
            x1,y1,x2,y2 = t.bbox
            is_vehicle   = t.class_id in VEHICLE_CLASS_IDS
            is_cross_cam = (
                t.global_id is not None and
                GLOBAL_TRACKER._gallery.get(
                    t.global_id,
                    type("",(),{"is_cross_camera":lambda s:False})()
                ).is_cross_camera()
            )
            display_id = t.global_id if t.global_id else t.id

            if is_vehicle:
                box_col, badge_col = (0,180,255), (0,110,180)
            elif is_cross_cam:
                box_col, badge_col = (0,220,220), (0,130,130)
            else:
                box_col, badge_col = (0,210,0),   (0,130,0)

            thickness = 2
            if str(display_id) == str(self.target_manager.active_target) or \
               str(t.id) == str(self.target_manager.active_target):
                box_col = (0,0,255)
                thickness = 4

            cv2.rectangle(frame,(x1,y1),(x2,y2),box_col,thickness)

            # Dwell time annotation
            dwell = self.behavior.dwell.get_dwell(display_id)
            dwell_tag = f" {int(dwell)}s" if dwell >= 10 else ""

            label = f"{t.class_name}  {t.global_id}{dwell_tag}" if t.global_id else f"{t.class_name}  {display_id}{dwell_tag}"
            (tw,th),_ = cv2.getTextSize(label,font,fs,1)
            by1=max(y1-th-8,0); by2=by1+th+6
            cv2.rectangle(frame,(x1,by1),(x1+tw+8,by2),badge_col,-1)
            cv2.putText(frame,label,(x1+4,by2-3),font,fs,
                        (255,255,255),1,cv2.LINE_AA)

            # Cross-cam pill
            if is_cross_cam:
                pill=" CROSS "
                (pw,ph),_=cv2.getTextSize(pill,font,0.35,1)
                py1=by1-ph-4; py2=by1-1
                if py1>=0:
                    cv2.rectangle(frame,(x1,py1),(x1+pw+4,py2),(180,120,0),-1)
                    cv2.putText(frame,pill,(x1+2,py2-2),font,0.35,
                                (255,255,255),1,cv2.LINE_AA)

            # Vehicle info row
            if is_vehicle:
                vinfo = self.vehicle_analyzer.get_info(display_id)
                if vinfo and (vinfo.color_name or vinfo.shape_type):
                    row_y = by2+1; x_cur = x1
                    if vinfo.color_name:
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+12,row_y+12),
                                      vinfo.color_bgr,-1)
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+12,row_y+12),
                                      (200,200,200),1)
                        cn=vinfo.color_name
                        (cnw,_),_=cv2.getTextSize(cn,font,0.34,1)
                        cx2=x_cur+15
                        cv2.rectangle(frame,(cx2-1,row_y),(cx2+cnw+3,row_y+12),
                                      (30,30,30),-1)
                        cv2.putText(frame,cn,(cx2,row_y+10),font,0.34,
                                    (220,220,220),1,cv2.LINE_AA)
                        x_cur += 15+cnw+6
                    if vinfo.shape_type:
                        st=vinfo.shape_type
                        (stw,_),_=cv2.getTextSize(st,font,0.34,1)
                        cv2.rectangle(frame,(x_cur,row_y),(x_cur+stw+6,row_y+12),
                                      (60,60,100),-1)
                        cv2.putText(frame,st,(x_cur+3,row_y+10),font,0.34,
                                    (180,180,255),1,cv2.LINE_AA)

            if self.show_debug_id:
                dbg=t.id
                (dw,dh),_=cv2.getTextSize(dbg,font,0.32,1)
                cv2.rectangle(frame,(x1,y2),(x1+dw+6,y2+dh+4),(40,40,40),-1)
                cv2.putText(frame,dbg,(x1+3,y2+dh+1),font,0.32,
                            (160,160,160),1,cv2.LINE_AA)

        for d in result.detections:
            db=(d.box.x1,d.box.y1,d.box.x2,d.box.y2)
            if any(_iou(db,tb)>self.DEDUP_IOU for tb in confirmed): continue
            color=_get_color(d.class_id); b=d.box
            cv2.rectangle(frame,(b.x1,b.y1),(b.x2,b.y2),color,1)
            lbl=f"{d.class_name} {d.confidence:.0%}"
            (tw,th),_=cv2.getTextSize(lbl,font,0.38,1)
            by1=max(b.y1-th-6,0); by2=by1+th+4
            cv2.rectangle(frame,(b.x1,by1),(b.x1+tw+6,by2),color,-1)
            cv2.putText(frame,lbl,(b.x1+3,by2-2),font,0.38,
                        (255,255,255),1,cv2.LINE_AA)

        return frame

    def _draw_trails(self, frame, tracked):
        for t in tracked:
            did=t.global_id if t.global_id else t.id
            pts=list(self._trails.get(did,[]))
            if len(pts)<2: continue
            n=len(pts)
            for i in range(1,n):
                a=i/n; th=max(1,int(a*3)); iv=int(80+140*a)
                color=(0,iv//2,iv) if t.class_id in VEHICLE_CLASS_IDS else (0,iv,0)
                cv2.line(frame,pts[i-1],pts[i],color,th,cv2.LINE_AA)
        return frame

    def _draw_hud(self, frame, tracked):
        h,w=frame.shape[:2]; font=cv2.FONT_HERSHEY_SIMPLEX
        bar_y=h-28; ov=frame.copy()
        cv2.rectangle(ov,(0,bar_y),(w,h),(0,0,0),-1)
        cv2.addWeighted(ov,0.65,frame,0.35,0,frame)
        cv2.line(frame,(0,bar_y),(w,bar_y),(60,60,60),1)
        ty=h-8

        pc=sum(1 for t in tracked if t.class_id not in VEHICLE_CLASS_IDS)
        vc=sum(1 for t in tracked if t.class_id in VEHICLE_CLASS_IDS)
        ts = self.behavior.traffic.state
        tc = self.behavior.traffic.state_color

        cv2.putText(frame,f"Cam{self.camera_id}",(4,ty),font,0.42,
                    (255,255,255),1,cv2.LINE_AA)
        ct="IP" if self.is_ip else "CAM"
        cv2.putText(frame,f"{ct} {int(self.avg_fps)}",(56,ty),font,0.42,
                    (0,220,220),1,cv2.LINE_AA)
        cv2.putText(frame,f"P:{pc}",(112,ty),font,0.42,(0,220,80),1,cv2.LINE_AA)
        cv2.putText(frame,f"V:{vc}",(144,ty),font,0.42,(0,180,255),1,cv2.LINE_AA)
        cv2.putText(frame,ts,(178,ty),font,0.40,tc,1,cv2.LINE_AA)

        # Unacknowledged alert badge
        ua = ALERT_SYSTEM.unacknowledged_count()
        if ua > 0:
            badge=f"!{ua}"
            (bw,bh),_=cv2.getTextSize(badge,font,0.40,1)
            bx=w-bw-26; by_top=bar_y+3
            cv2.rectangle(frame,(bx-3,by_top),(bx+bw+3,by_top+bh+4),(0,0,180),-1)
            cv2.putText(frame,badge,(bx,by_top+bh+1),font,0.40,
                        (255,255,255),1,cv2.LINE_AA)

        ms=f"{self.detector.last_result.inference_ms:.0f}ms"
        (mw,_),_=cv2.getTextSize(ms,font,0.38,1)
        cv2.putText(frame,ms,(w-mw-4,ty),font,0.38,(130,130,130),1,cv2.LINE_AA)

        tag=f" Cam{self.camera_id} "
        (tw,th),_=cv2.getTextSize(tag,font,0.38,1)
        cv2.rectangle(frame,(0,0),(tw+4,th+6),(30,30,30),-1)
        cv2.putText(frame,tag,(2,th+2),font,0.38,(160,160,160),1,cv2.LINE_AA)
        return frame

    # ── Private ───────────────────────────────────────────────

    def _update_trails(self, tracked):
        active=set()
        for t in tracked:
            did=t.global_id if t.global_id else t.id
            active.add(did)
            if did not in self._trails: self._trails[did]=deque(maxlen=20)
            self._trails[did].append(t.centroid)
        for tid in set(self._trails)-active:
            if tid not in self.last_seen: del self._trails[tid]

    def _attach_track_ids(self, result, tracked):
        for track in tracked:
            tx1,ty1,tx2,ty2=track.bbox
            tcx=(tx1+tx2)//2; tcy=(ty1+ty2)//2
            best_det=None; best_d=float("inf")
            for det in result.detections:
                dx,dy=det.box.center; d=abs(dx-tcx)+abs(dy-tcy)
                if d<best_d: best_d=d; best_det=det
            if best_det and best_d<60:
                try: best_det.track_id=int(track.id.split("ID")[-1])
                except: best_det.track_id=None

    def _attach_face_ids(self, face_res, tracked):
        for face in face_res.known_faces:
            best_track=None; best_iou=0.0
            for track in tracked:
                score = _iou(face.box_cv2, track.bbox)
                if score > best_iou:
                    best_iou=score; best_track=track
            if best_track and best_iou > 0.2:
                best_track.face_id = face.name
                best_track.global_id = face.name
                face.track_id = best_track.id

    def _no_signal(self):
        frame=np.zeros((self.frame_height,self.frame_width,3),dtype=np.uint8)
        cx=self.frame_width//2; cy=self.frame_height//2-20
        cv2.circle(frame,(cx,cy),30,(0,0,180),-1)
        cv2.circle(frame,(cx,cy),30,(0,0,100),2)
        cv2.line(frame,(cx-16,cy-16),(cx+16,cy+16),(255,255,255),3)
        cv2.line(frame,(cx+16,cy-16),(cx-16,cy+16),(255,255,255),3)
        font=cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame,f"Camera {self.camera_id}",(cx-62,cy+52),
                    font,0.60,(200,200,200),1,cv2.LINE_AA)
        cv2.putText(frame,"NO SIGNAL",(cx-60,cy+80),font,0.70,
                    (0,60,220),2,cv2.LINE_AA)
        cv2.putText(frame,"Check connection",(cx-72,cy+108),
                    font,0.40,(100,100,100),1,cv2.LINE_AA)
        return frame
