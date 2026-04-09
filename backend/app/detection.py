"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/detection.py
  Purpose : Pure YOLOv8 detection — all 80 COCO classes.
=============================================================
"""

import cv2, time, os, logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque
import numpy as np
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Detection")

DEFAULT_MODEL_PATH = "backend/yolov8n.pt"
DEFAULT_CONFIDENCE = 0.50
DEFAULT_IMG_SIZE   = 416

_PALETTE = [
    (255, 56, 56),(255,157,151),(255,178,29),(207,210,49),
    (72,249,10),(146,234,43),(61,219,134),(26,147,52),
    (0,212,187),(44,153,168),(0,194,255),(52,69,147),
    (100,115,255),(0,24,236),(132,56,255),(82,0,133),
    (203,56,255),(255,149,200),
]

def _get_color(class_id: int) -> Tuple[int,int,int]:
    return _PALETTE[class_id % len(_PALETTE)]


@dataclass
class BoundingBox:
    x1: int; y1: int; x2: int; y2: int

    @property
    def width(self):  return max(0, self.x2 - self.x1)
    @property
    def height(self): return max(0, self.y2 - self.y1)
    @property
    def center(self): return ((self.x1+self.x2)//2, (self.y1+self.y2)//2)
    @property
    def area(self):   return self.width * self.height

    def to_deepsort(self): return [self.x1, self.y1, self.width, self.height]

    def iou(self, other: "BoundingBox") -> float:
        ix1 = max(self.x1, other.x1); iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2); iy2 = min(self.y2, other.y2)
        inter = max(0, ix2-ix1) * max(0, iy2-iy1)
        if inter == 0: return 0.0
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass
class Detection:
    class_id   : int
    class_name : str
    confidence : float
    box        : BoundingBox
    track_id   : Optional[int] = None

    @property
    def is_person(self):  return self.class_id == 0
    @property
    def is_vehicle(self): return self.class_id in {1,2,3,5,7}

    def to_deepsort_tuple(self):
        return (self.box.to_deepsort(), self.confidence, self.class_id)

    def to_dict(self):
        return {
            "class_id": self.class_id, "class_name": self.class_name,
            "confidence": round(self.confidence,3), "track_id": self.track_id,
            "box": {"x1":self.box.x1,"y1":self.box.y1,"x2":self.box.x2,"y2":self.box.y2},
            "center": self.box.center,
        }


@dataclass
class FrameResult:
    detections      : List[Detection]      = field(default_factory=list)
    fps             : float                = 0.0
    inference_ms    : float                = 0.0
    frame_index     : int                  = 0
    annotated_frame : Optional[np.ndarray] = None

    @property
    def count(self): return len(self.detections)
    @property
    def class_counts(self):
        c = {}
        for d in self.detections: c[d.class_name] = c.get(d.class_name,0)+1
        return c

    def persons(self):  return [d for d in self.detections if d.is_person]
    def vehicles(self): return [d for d in self.detections if d.is_vehicle]

    def to_deepsort_format(self):
        MIN_AREA = 400
        return [d.to_deepsort_tuple() for d in self.detections
                if d.box.area >= MIN_AREA]


class ObjectDetector:

    def __init__(self, camera_id=0, model_path=DEFAULT_MODEL_PATH,
                 confidence=DEFAULT_CONFIDENCE, img_size=DEFAULT_IMG_SIZE):
        self.camera_id  = camera_id
        self.confidence = confidence
        self.img_size   = img_size
        self.frame_count     = 0
        self.inference_count = 0
        self.detection_interval = 3
        self.last_result = FrameResult()
        self.prev_time   = time.time()
        self.fps_queue   = deque(maxlen=10)
        self.avg_fps     = 0.0
        self.logger      = logging.getLogger(f"Camera-{camera_id}")
        self._load_model(model_path)

    def _load_model(self, path):
        if not os.path.exists(path):
            self.logger.warning(f"Model not at '{path}' — downloading...")
            self.model = YOLO("yolov8n.pt")
        else:
            self.model = YOLO(path)
        self.model.fuse()
        self.class_names = self.model.names
        self.logger.info(f"Detector ready — {len(self.class_names)} classes")

    def detect(self, frame: np.ndarray) -> FrameResult:
        self.frame_count += 1
        now = time.time(); diff = now - self.prev_time
        if diff > 0:
            self.fps_queue.append(1.0/diff)
            self.avg_fps = sum(self.fps_queue)/len(self.fps_queue)
        self.prev_time = now

        if self.frame_count % self.detection_interval != 0:
            self.last_result.fps = round(self.avg_fps, 1)
            return self.last_result

        self.inference_count += 1
        t0 = time.time()
        res = self.model(frame, imgsz=self.img_size,
                         conf=self.confidence, verbose=False)[0]
        ms = (time.time()-t0)*1000

        dets = []
        for box in res.boxes:
            cid = int(box.cls[0]); cn = self.class_names.get(cid, f"cls_{cid}")
            cf  = float(box.conf[0])
            x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
            if x2<=x1 or y2<=y1: continue
            dets.append(Detection(cid, cn, cf, BoundingBox(x1,y1,x2,y2)))

        self.last_result = FrameResult(
            detections=dets, fps=round(self.avg_fps,1),
            inference_ms=round(ms,1), frame_index=self.inference_count
        )
        return self.last_result

    def annotate(self, frame, result, show_hud=False):
        out = frame.copy()
        for d in result.detections: out = self._draw_box(out, d)
        if show_hud: out = self._draw_hud(out, result)
        return out

    def _draw_box(self, frame, d):
        c = _get_color(d.class_id); b = d.box
        cv2.rectangle(frame,(b.x1,b.y1),(b.x2,b.y2),c,2)
        lbl = f"{d.class_name} {d.confidence:.0%}"
        font = cv2.FONT_HERSHEY_SIMPLEX; fs=0.45
        (tw,th),_ = cv2.getTextSize(lbl,font,fs,1)
        by1=max(b.y1-th-8,0); by2=by1+th+6
        cv2.rectangle(frame,(b.x1,by1),(b.x1+tw+8,by2),c,-1)
        cv2.putText(frame,lbl,(b.x1+4,by2-3),font,fs,(255,255,255),1,cv2.LINE_AA)
        return frame

    def _draw_hud(self, frame, result):
        h,w = frame.shape[:2]; ov = frame.copy()
        cv2.rectangle(ov,(0,0),(w,36),(0,0,0),-1)
        cv2.addWeighted(ov,0.55,frame,0.45,0,frame)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame,f"FPS:{int(result.fps)}",(8,24),font,0.58,(0,255,200),2,cv2.LINE_AA)
        cv2.putText(frame,f"Obj:{result.count}",(95,24),font,0.55,(255,255,255),1,cv2.LINE_AA)
        return frame

    def set_confidence(self, v): self.confidence = max(0.0,min(1.0,v))
    def set_detection_interval(self, n): self.detection_interval = max(1,n)
    @property
    def fps(self): return round(self.avg_fps,1)