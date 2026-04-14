import cv2
from app.stream_bridge import STREAM_BRIDGE

def start_camera(camera_id, source=0):
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[ERROR] Camera {camera_id} not opened")
        return

    print(f"[INFO] Camera {camera_id} started")

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"[ERROR] Camera {camera_id} frame failed")
            break

        # 🔥 THIS IS THE MOST IMPORTANT LINE
        STREAM_BRIDGE.put_frame(camera_id, frame)