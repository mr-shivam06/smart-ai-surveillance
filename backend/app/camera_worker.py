import cv2
from app.stream_bridge import STREAM_BRIDGE

def start_camera(camera_id, source=0):
    # 🔥 AUTO-DETECT SOURCE TYPE
    if isinstance(source, int) or str(source).isdigit():
        # Webcam
        cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
    else:
        # IP cam / DroidCam / RTSP
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[ERROR] Camera {camera_id} not opened (source={source})")
        return

    print(f"[INFO] Camera {camera_id} started (source={source})")

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"[ERROR] Camera {camera_id} frame failed")
            break

        STREAM_BRIDGE.put_frame(camera_id, frame)