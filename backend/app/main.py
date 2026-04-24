"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/main.py
  Purpose : Entry point — camera threads, grid display.

  DAY 13: Uses SHARED_DETECTOR (one YOLO model for all cams).
  DAY 14: Demo mode — set DEMO_MODE=1 in .env to use videos.

  Run:
    Terminal 1: set PYTHONPATH=backend && uvicorn app.api_main:app --reload --port 8000
    Terminal 2: cd backend && python app/main.py

  Demo mode:
    set DEMO_MODE=1
    python app/main.py
=============================================================
"""

import threading, sys, os, time, cv2, numpy as np
from collections import deque

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.camera_processor import CameraProcessor
from app.cross_camera_tracker import GLOBAL_TRACKER
from app.stream_bridge import STREAM_BRIDGE
from app.shared_model import SHARED_DETECTOR
from app.demo_mode import DEMO_MODE, DEMO_INJECTOR, get_demo_source


# ── Camera configuration ──────────────────────────────────────
_BASE_CAMERAS = [
    {"id": 1, "source": 0,                                "name": "Laptop Cam"},
    {"id": 2, "source": "http://10.54.125.53:4747/video", "name": "Mobile Cam"},
]

# In demo mode, replace sources with video files
if DEMO_MODE:
    CAMERA_SOURCES = [
        {"id": c["id"], "source": get_demo_source(c["id"]), "name": f"{c['name']} [DEMO]"}
        for c in _BASE_CAMERAS
    ]
    print("\n[DEMO MODE] Using pre-recorded video files.")
    print("[DEMO MODE] Events will fire automatically at scheduled timestamps.\n")
else:
    CAMERA_SOURCES = _BASE_CAMERAS

WINDOW_TITLE = "Smart AI Surveillance"
TITLE_BAR_H  = 36

latest_frames : dict = {}
camera_procs  : dict = {}
lock          = threading.Lock()
running       = True


def _no_signal(cam_id, name):
    f = np.zeros((360, 480, 3), dtype=np.uint8)
    cx, cy = 240, 150
    cv2.circle(f,(cx,cy),28,(0,0,180),-1)
    cv2.line(f,(cx-16,cy-16),(cx+16,cy+16),(255,255,255),4)
    cv2.line(f,(cx+16,cy-16),(cx-16,cy+16),(255,255,255),4)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(f,f"Camera {cam_id} — {name}",(cx-90,cy+52),font,0.50,(200,200,200),1,cv2.LINE_AA)
    cv2.putText(f,"NO SIGNAL",(cx-58,cy+80),font,0.70,(0,0,255),2,cv2.LINE_AA)
    cv2.putText(f,"Connecting...",(cx-55,cy+108),font,0.45,(120,120,120),1,cv2.LINE_AA)
    return f


def camera_worker(cfg):
    global running
    cam_id=cfg["id"]; source=cfg["source"]; name=cfg["name"]
    with lock: latest_frames[cam_id] = _no_signal(cam_id, name)
    try:
        print(f"[INFO] Starting Camera {cam_id} — {name}")
        cam = CameraProcessor(camera_id=cam_id, source=source)
        with lock: camera_procs[cam_id] = cam
        while running:
            frame = cam.get_frame()
            with lock: latest_frames[cam_id] = frame
            STREAM_BRIDGE.put_frame(cam_id, frame)
        cam.release()
    except Exception as e:
        print(f"[CRASH] Camera {cam_id} — {e}")
        import traceback; traceback.print_exc()
        while running:
            ns = _no_signal(cam_id, name)
            with lock: latest_frames[cam_id] = ns
            STREAM_BRIDGE.put_frame(cam_id, ns)
            time.sleep(0.5)


def build_grid(frames_dict):
    if not frames_dict: return None, 1, 1
    ordered = [frames_dict[k] for k in sorted(frames_dict.keys())]
    n=len(ordered); cols=int(np.ceil(np.sqrt(n))); rows=int(np.ceil(n/cols))
    h,w=ordered[0].shape[:2]
    while len(ordered)<rows*cols: ordered.append(np.zeros((h,w,3),dtype=np.uint8))
    grid=np.vstack([np.hstack(ordered[r*cols:(r+1)*cols]) for r in range(rows)])
    return grid, cols, rows


def draw_title_bar(grid, avg_fps, procs):
    gw=grid.shape[1]; font=cv2.FONT_HERSHEY_SIMPLEX
    cv2.rectangle(grid,(0,0),(gw,TITLE_BAR_H),(12,12,12),-1)
    cv2.line(grid,(0,TITLE_BAR_H),(gw,TITLE_BAR_H),(55,55,55),1)

    title = "SMART AI SURVEILLANCE [DEMO]" if DEMO_MODE else "SMART AI SURVEILLANCE"
    title_color = (0,200,255) if DEMO_MODE else (0,220,220)
    cv2.putText(grid,title,(10,25),font,0.58,title_color,2,cv2.LINE_AA)

    status = GLOBAL_TRACKER.get_status()
    streaming = len(STREAM_BRIDGE.active_camera_ids())
    any_fire  = any(
        getattr(getattr(p,'behavior',None),'fire',None) and p.behavior.fire.has_fire
        for p in procs.values()
    )
    if any_fire:
        fw,_ = cv2.getTextSize("  FIRE DETECTED  ",font,0.50,2)[0]
        cv2.putText(grid," FIRE DETECTED ",(gw//2-fw//2,25),font,0.50,(0,60,255),2,cv2.LINE_AA)
    else:
        mid=(f"FPS:{int(avg_fps)}  IDs:{status['total_identities']}  "
             f"Cross:{status['cross_camera_matches']}  Stream:{streaming}  [shared YOLO]")
        (fw,_),_=cv2.getTextSize(mid,font,0.40,1)
        cv2.putText(grid,mid,(gw//2-fw//2,25),font,0.40,(0,200,80),1,cv2.LINE_AA)

    target_parts=[]
    for cid,proc in sorted(procs.items()):
        info=proc.target_manager.get_target_info()
        if info: target_parts.append(f"Cam{cid}:{info['target_id']}")
    rt=("Target: "+"  ".join(target_parts) if target_parts
        else "L:target  R:clear  T:trails  D:debug  H:heat  Z:zones  F:fire  S:snap  Q:quit")
    rc=(80,80,255) if target_parts else (80,80,80)
    (rw,_),_=cv2.getTextSize(rt,font,0.34,1)
    cv2.putText(grid,rt,(gw-rw-10,25),font,0.34,rc,1,cv2.LINE_AA)
    return grid


if __name__ == "__main__":
    print("\n========== SMART AI MULTI-CAMERA SURVEILLANCE ==========\n")
    print(f"[INFO] Mode: {'DEMO (video files)' if DEMO_MODE else 'LIVE (cameras)'}")
    print(f"[INFO] Shared YOLO model — 1 model for {len(CAMERA_SOURCES)} cameras")
    print("[INFO] Green=local  Cyan=cross-camera  Orange=vehicle")
    print("[INFO] Keys: L=target R=clear T=trails D=debug H=heat Z=zones F=fire S=snap Q=quit\n")

    # Start demo event injector
    if DEMO_MODE:
        DEMO_INJECTOR.start()

    for cfg in CAMERA_SOURCES:
        threading.Thread(target=camera_worker,args=(cfg,),daemon=True).start()
        time.sleep(0.4)

    print("[INFO] Initialising cameras...")
    time.sleep(1.5)

    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)

    fps_queue=deque(maxlen=20); prev_time=time.time()
    grid_layout={"cols":1,"rows":1,"fw":480,"fh":360}

    def on_mouse(event, x, y, flags, param):
        if event not in (cv2.EVENT_LBUTTONDOWN,cv2.EVENT_RBUTTONDOWN): return
        y_adj=y-TITLE_BAR_H
        if y_adj<0: return
        cols=grid_layout["cols"]; fw=grid_layout["fw"]; fh=grid_layout["fh"]
        col_idx=x//fw; row_idx=y_adj//fh; cam_idx=row_idx*cols+col_idx
        with lock:
            sorted_ids=sorted(latest_frames.keys()); p_snap=camera_procs.copy()
        if cam_idx>=len(sorted_ids): return
        cam_id=sorted_ids[cam_idx]
        if cam_id not in p_snap: return
        lx=x-col_idx*fw; ly=y_adj-row_idx*fh
        p_snap[cam_id].target_manager.on_mouse_click(event,lx,ly,flags,None)

    cv2.setMouseCallback(WINDOW_TITLE, on_mouse)
    os.makedirs("backend/screenshots", exist_ok=True)
    os.makedirs("backend/videos", exist_ok=True)

    try:
        while True:
            with lock:
                frames_copy={k:v.copy() for k,v in latest_frames.items()}
                procs_copy=camera_procs.copy()

            grid,cols,rows=build_grid(frames_copy)
            if grid is None: time.sleep(0.05); continue

            grid_layout.update({"cols":cols,"rows":rows,"fw":480,"fh":360})
            now=time.time()
            fps_queue.append(1.0/max(now-prev_time,1e-6))
            prev_time=now; avg_fps=sum(fps_queue)/len(fps_queue)

            title_bar=np.full((TITLE_BAR_H,grid.shape[1],3),12,dtype=np.uint8)
            display=np.vstack([title_bar,grid])
            display=draw_title_bar(display,avg_fps,procs_copy)

            cv2.imshow(WINDOW_TITLE,display)
            key=cv2.waitKey(1)&0xFF

            if   key==ord("q"): print("\n[INFO] Quit."); break
            elif key==ord("t"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.show_trails=not proc.show_trails
                print(f"[INFO] Trails {'ON' if p and next(iter(p.values())).show_trails else 'OFF'}")
            elif key==ord("d"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.show_debug_id=not proc.show_debug_id
                print(f"[INFO] Debug {'ON' if p and next(iter(p.values())).show_debug_id else 'OFF'}")
            elif key==ord("h"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.show_heatmap=not proc.show_heatmap
                print(f"[INFO] Heatmap {'ON' if p and next(iter(p.values())).show_heatmap else 'OFF'}")
            elif key==ord("z"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.show_zones=not proc.show_zones
                print(f"[INFO] Zones {'ON' if p and next(iter(p.values())).show_zones else 'OFF'}")
            elif key==ord("f"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.show_fire_tint=not proc.show_fire_tint
                print(f"[INFO] Fire tint {'ON' if p and next(iter(p.values())).show_fire_tint else 'OFF'}")
            elif key==ord("s"):
                ts=time.strftime("%Y%m%d_%H%M%S")
                path=f"backend/screenshots/grid_{ts}.jpg"
                cv2.imwrite(path,display)
                print(f"[INFO] Screenshot → {path}")
            elif key==ord("r"):
                with lock: p=camera_procs.copy()
                for proc in p.values(): proc.tracker.reset()
                print("[INFO] All trackers reset.")

    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")
    finally:
        running=False; time.sleep(0.8)
        cv2.destroyAllWindows()
        print("[INFO] System stopped.")