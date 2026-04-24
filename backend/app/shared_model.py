"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/shared_model.py
  Purpose : Single YOLOv8n model shared across ALL cameras.

  WHY THIS MATTERS:
    Before: Each camera loaded its own YOLOv8n model.
    With 2 cameras: 2 × ~50MB model in RAM, 2 × model.fuse()
    calls, and most critically — 2 concurrent YOLO inferences
    fighting over the same CPU cores = heavy thrashing.

    After: One model instance. One model.fuse(). Cameras share
    it via a thread-safe queue system (round-robin scheduling).
    Memory: 50MB instead of N×50MB.
    CPU:    Inferences are serialized not concurrent.
            Each camera gets its turn via a work queue.

  ARCHITECTURE:
    SharedDetector (singleton):
      - Holds one YOLO model
      - Runs one DetectionWorker thread
      - Per-camera FrameQueue (maxsize=2) — always fresh frames
      - Round-robin pull: cam1→cam2→cam1→cam2...
      - Result posted back via per-camera ResultQueue

    Each CameraProcessor:
      - No longer has self.detector (removed)
      - Calls SharedDetector.detect(camera_id, frame)
        which posts to queue and blocks briefly for result
      - OR uses async mode: submit_frame() then get_result()

  STAGGERED OFFSETS:
    cam1 processes frames 0, 3, 6, 9 ...
    cam2 processes frames 1, 4, 7, 10 ...
    cam3 processes frames 2, 5, 8, 11 ...
    This distributes load evenly and prevents cam1 always
    getting priority while cam2 starves.
=============================================================
"""

import cv2
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("SharedModel")

MODEL_PATH  = "backend/yolov8n.pt"
CONFIDENCE  = 0.45
IMG_SIZE    = 320
QUEUE_SIZE  = 2      # per-camera frame queue depth — always freshest frame


@dataclass
class DetectionRequest:
    camera_id   : int
    frame       : np.ndarray
    frame_index : int


@dataclass
class DetectionResult:
    camera_id    : int
    detections   : list          # List[Detection] from detection.py
    inference_ms : float
    frame_index  : int


class SharedDetector:
    """
    Singleton — one YOLO model, one inference thread, N cameras.

    Usage in CameraProcessor:
        from app.shared_model import SHARED_DETECTOR
        result = SHARED_DETECTOR.infer(camera_id, frame)
        # result is a DetectionResult with .detections list
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
        from ultralytics import YOLO

        if not os.path.exists(MODEL_PATH):
            logger.warning(f"Model not at {MODEL_PATH} — downloading yolov8n...")
            self.model = YOLO("yolov8n.pt")
        else:
            self.model = YOLO(MODEL_PATH)

        self.model.fuse()
        self.class_names: dict = self.model.names

        logger.info(
            f"[SharedDetector] Model loaded — {len(self.class_names)} classes | "
            f"imgsz={IMG_SIZE} | conf={CONFIDENCE}"
        )

        # Per-camera frame queues (input) and result queues (output)
        self._frame_queues  : Dict[int, queue.Queue]      = {}
        self._result_queues : Dict[int, queue.Queue]      = {}
        self._last_result   : Dict[int, DetectionResult]  = {}
        self._frame_counts  : Dict[int, int]              = {}
        self._lock          = threading.Lock()

        # Single inference thread — serializes YOLO calls
        self._inference_thread = threading.Thread(
            target=self._inference_loop,
            daemon=True,
            name="YOLO-Inference",
        )
        self._inference_thread.start()

        # Warmup
        try:
            dummy = np.zeros((360, 480, 3), dtype=np.uint8)
            self.model(dummy, imgsz=IMG_SIZE, conf=CONFIDENCE, verbose=False)
            logger.info("[SharedDetector] Warmup done.")
        except Exception as e:
            logger.warning(f"[SharedDetector] Warmup failed: {e}")

    def register_camera(self, camera_id: int):
        """Call once per camera on startup."""
        with self._lock:
            if camera_id not in self._frame_queues:
                self._frame_queues[camera_id]  = queue.Queue(maxsize=QUEUE_SIZE)
                self._result_queues[camera_id] = queue.Queue(maxsize=1)
                self._frame_counts[camera_id]  = 0
                logger.info(f"[SharedDetector] Camera {camera_id} registered.")

    def infer(
        self,
        camera_id : int,
        frame     : np.ndarray,
    ) -> "DetectionResult":
        """
        Submit a frame for inference and return the result.
        Blocks until result is ready (usually < 30ms).
        Returns cached last result if queue is full (camera runs
        faster than inference — just skip this frame).
        """
        with self._lock:
            self._frame_counts[camera_id] = self._frame_counts.get(camera_id, 0) + 1
            frame_idx = self._frame_counts[camera_id]

        fq = self._frame_queues.get(camera_id)
        rq = self._result_queues.get(camera_id)

        if fq is None:
            self.register_camera(camera_id)
            return self._empty_result(camera_id)

        # Drop stale frame if queue full — always keep freshest
        if fq.full():
            try: fq.get_nowait()
            except queue.Empty: pass

        req = DetectionRequest(camera_id=camera_id, frame=frame, frame_index=frame_idx)
        fq.put(req)

        # Wait for result (timeout = 100ms)
        try:
            result = rq.get(timeout=0.1)
            with self._lock:
                self._last_result[camera_id] = result
            return result
        except queue.Empty:
            # Inference thread busy — return last cached result
            with self._lock:
                return self._last_result.get(camera_id, self._empty_result(camera_id))

    def get_last_result(self, camera_id: int) -> "DetectionResult":
        """Return cached result without waiting."""
        with self._lock:
            return self._last_result.get(camera_id, self._empty_result(camera_id))

    def _empty_result(self, camera_id: int) -> "DetectionResult":
        return DetectionResult(
            camera_id    = camera_id,
            detections   = [],
            inference_ms = 0.0,
            frame_index  = 0,
        )

    # ── Inference loop ────────────────────────────────────────

    def _inference_loop(self):
        """
        Single thread that owns all YOLO inference.
        Round-robins across registered cameras.
        """
        logger.info("[SharedDetector] Inference loop started.")

        while True:
            processed = False

            with self._lock:
                camera_ids = list(self._frame_queues.keys())

            for cam_id in camera_ids:
                fq = self._frame_queues.get(cam_id)
                rq = self._result_queues.get(cam_id)
                if fq is None or rq is None:
                    continue

                try:
                    req = fq.get_nowait()
                except queue.Empty:
                    continue

                # Run YOLO inference
                t0 = time.time()
                try:
                    yolo_out = self.model(
                        req.frame,
                        imgsz   = IMG_SIZE,
                        conf    = CONFIDENCE,
                        verbose = False,
                    )[0]
                    ms = (time.time() - t0) * 1000

                    detections = self._parse_detections(yolo_out, req.frame)

                except Exception as e:
                    logger.error(f"[SharedDetector] Inference error cam{cam_id}: {e}")
                    detections = []
                    ms         = 0.0

                result = DetectionResult(
                    camera_id    = cam_id,
                    detections   = detections,
                    inference_ms = round(ms, 1),
                    frame_index  = req.frame_index,
                )

                # Post result — drop old result if consumer is slow
                if rq.full():
                    try: rq.get_nowait()
                    except queue.Empty: pass
                rq.put(result)

                processed = True

            if not processed:
                time.sleep(0.002)   # 2ms sleep when no work — prevents busy loop

    def _parse_detections(self, yolo_out, frame: np.ndarray) -> list:
        """Convert YOLO output to Detection objects."""
        from app.detection import Detection, BoundingBox

        MIN_AREA = 1200
        dets = []

        for box in yolo_out.boxes:
            cid = int(box.cls[0])
            cn  = self.class_names.get(cid, f"cls_{cid}")
            cf  = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            if x2 <= x1 or y2 <= y1:
                continue

            bb = BoundingBox(x1, y1, x2, y2)
            if bb.area < MIN_AREA:
                continue

            dets.append(Detection(cid, cn, cf, bb))

        return dets


# ── Singleton ─────────────────────────────────────────────────
SHARED_DETECTOR = SharedDetector()