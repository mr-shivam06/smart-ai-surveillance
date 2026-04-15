"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/register_face.py
  Purpose : Register known faces into the database.

  Two modes:
    1. From photo  — put image in face_db/images/ and rebuild
    2. Live webcam — look at camera, press SPACE to capture

  Usage:
    python backend/app/register_face.py --mode photo
    python backend/app/register_face.py --mode live --name "John Doe"
=============================================================
"""

import sys, os, cv2, time, argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.face_recognition_module import FaceRecognizer, FaceDatabase, IMAGES_DIR


def register_from_photos():
    print("\n[Register] Photo mode — scanning face_db/images/\n")
    print(f"  Folder: {os.path.abspath(IMAGES_DIR)}")
    print("  Filename format: first_last.jpg → 'First Last'\n")
    db    = FaceDatabase()
    count = db.load()
    print(f"\n[Register] Done — {count} face(s) registered:")
    for name in db.known_names:
        print(f"  + {name}")


def register_live(name: str):
    print(f"\n[Register] Live mode — registering: '{name}'\n")
    print("  1. Look directly at the camera")
    print("  2. Press SPACE to capture")
    print("  3. Press Q to quit\n")

    recognizer = FaceRecognizer(camera_id=0)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam."); return

    time.sleep(1.0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    registered = False

    try:
        import face_recognition as fr
    except ImportError:
        print("[ERROR] pip install face-recognition"); cap.release(); return

    while True:
        ret, frame = cap.read()
        if not ret: break

        display = cv2.resize(frame, (640, 480))
        rgb  = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        locs = fr.face_locations(rgb, model="hog")
        face_found = len(locs) > 0

        for (top,right,bottom,left) in locs:
            cv2.rectangle(display,(left,top),(right,bottom),(0,220,0),2)

        col  = (0,220,0) if face_found else (0,100,220)
        msg  = "Face detected — press SPACE" if face_found else "No face — look at camera"
        cv2.putText(display,f"Registering: {name}",(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.70,(255,255,255),2)
        cv2.putText(display,msg,(10,65),cv2.FONT_HERSHEY_SIMPLEX,0.55,col,1)
        cv2.putText(display,"SPACE: capture   Q: quit",(10,display.shape[0]-12),
                    cv2.FONT_HERSHEY_SIMPLEX,0.42,(150,150,150),1)

        if registered:
            cv2.putText(display,f"REGISTERED: {name}",(10,100),
                        cv2.FONT_HERSHEY_SIMPLEX,0.80,(0,255,100),2)

        cv2.imshow(f"Register Face — {name}", display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"): break
        elif key == ord(" ") and not registered:
            if not face_found:
                print("[Register] No face — try again."); continue
            success = recognizer.register_from_frame(cv2.resize(frame,(640,480)), name)
            if success:
                print(f"\n[Register] SUCCESS — '{name}' registered!\n")
                registered = True
            else:
                print("[Register] Failed — could not encode. Try again.")

    cap.release()
    cv2.destroyAllWindows()
    print(f"[Register] {'Done' if registered else 'Cancelled'}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["photo","live"], default="photo")
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    if args.mode == "photo":
        register_from_photos()
    elif args.mode == "live":
        if not args.name:
            print("[ERROR] --name required for live mode."); exit(1)
        register_live(args.name)