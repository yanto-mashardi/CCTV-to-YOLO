import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
import argparse, json, time, threading
import cv2
from ultralytics import YOLO
from counting import Counter
from storage import DailyStore
from runtime import LatestFrame, Validation, PreviewServer

CLASSES = {2: "car", 3: "motorcycle"}

def maintenance(store, archive_root, stop):
    next_archive = 0
    while not stop.is_set():
        try:
            store.tick()
            if time.monotonic() >= next_archive:
                next_archive = time.monotonic() + 60
                store.archive(archive_root)
        except Exception as exc:
            print(store.port, "storage/Drive maintenance:", type(exc).__name__, flush=True)
        stop.wait(1)

def run_camera(cam, cfg, validation):
    name = cam["name"]
    url = os.environ[cam["url_env"]]
    # Simulation outputs must never be mixed with actual research archives.
    mode = cam["source_status"]
    if mode not in ("SIMULATION", "OBSERVED"):
        raise ValueError("Invalid source_status")
    from pathlib import Path
    root = Path(cfg["output"]) / mode.lower()
    archive = Path(os.environ.get(cfg["archive_env"], cfg["archive_path"])) / mode.lower()
    # Keep local spool even if Drive is unavailable.
    store = DailyStore(root, name)
    stop = threading.Event()
    worker = threading.Thread(target=maintenance, args=(store, archive, stop), daemon=True)
    worker.start()
    try:
        while True:
            model = YOLO(cfg["model"])
            counter = Counter(cam["line"], cam["entry"])
            cap = LatestFrame(url)
            seq = -1
            last = 0.0
            validation.status(name, "CONNECTING")
            try:
                while True:
                    item = cap.read(seq)
                    if item is None:
                        break
                    seq, frame = item
                    now = time.monotonic()
                    if now-last < 1/float(cfg["inference_fps"]):
                        continue
                    last = now
                    validation.status(name, "ONLINE")
                    h,w = frame.shape[:2]
                    result = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=list(CLASSES), device=cfg["device"], conf=float(cam.get("confidence",cfg["confidence"])), verbose=False)[0]
                    boxes = result.boxes
                    if boxes is not None and boxes.id is not None:
                      for xy,tid,cls in zip(boxes.xyxy.cpu().tolist(),boxes.id.int().cpu().tolist(),boxes.cls.int().cpu().tolist()):
                        point = ((xy[0]+xy[2])/(2*w), xy[3]/h)
                        if counter.update(tid, point, time.monotonic()):
                            print(name, store.add(CLASSES[cls]), flush=True)
                    validation.frame(name, frame, result, cam["line"], store.state.copy())
            finally:
                cap.release()
                validation.status(name, "OFFLINE")
            print(name, "stream disconnected; retrying", flush=True)
            time.sleep(2)
    finally:
        stop.set()
        worker.join(timeout=2)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.local.json")
    p.add_argument("--camera", choices=["bengkalis","pakning","all"], default="all")
    args = p.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    cams = [c for c in cfg["cameras"] if args.camera in ("all",c["name"])]
    for c in cams:
        if not os.environ.get(c["url_env"]):
            raise SystemExit("Missing " + c["url_env"])
    validation = Validation(cfg["output"], cfg["preview_fps"])
    server = PreviewServer(validation)
    server.start()
    print("Local validation: http://127.0.0.1:8765", flush=True)
    threads = [threading.Thread(target=run_camera,args=(c,cfg,validation)) for c in cams]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
