import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
import argparse, json, time, threading
import cv2
from ultralytics import YOLO
from counting import Counter
from storage import DailyStore

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

def run_camera(cam, cfg):
    name = cam["name"]
    url = os.environ[cam["url_env"]]
    # Simulation outputs must never be mixed with actual research archives.
    mode = cam["source_status"]
    if mode not in ("SIMULATION", "OBSERVED"):
        raise ValueError("Invalid source_status")
    from pathlib import Path
    root = Path(cfg["output"]) / mode.lower()
    archive = Path(os.environ[cfg["archive_env"]]) / mode.lower()
    # The operator creates these Drive folders beforehand.
    store = DailyStore(root, name)
    stop = threading.Event()
    worker = threading.Thread(target=maintenance, args=(store, archive, stop), daemon=True)
    worker.start()
    try:
        while True:
            model = YOLO(cfg["model"])
            counter = Counter(cam["line"], cam["entry"])
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,10000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
            try:
                while cap.isOpened():
                    ok, frame = cap.read()
                    if not ok:
                        break
                    h,w = frame.shape[:2]
                    result = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=list(CLASSES), device=cfg["device"], verbose=False)[0]
                    boxes = result.boxes
                    if boxes is None or boxes.id is None:
                        continue
                    for xy,tid,cls in zip(boxes.xyxy.cpu().tolist(),boxes.id.int().cpu().tolist(),boxes.cls.int().cpu().tolist()):
                        point = ((xy[0]+xy[2])/(2*w), xy[3]/h)
                        if counter.update(tid, point, time.monotonic()):
                            print(name, store.add(CLASSES[cls]), flush=True)
            finally:
                cap.release()
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
    if not os.environ.get(cfg["archive_env"]):
        raise SystemExit("Missing " + cfg["archive_env"])
    threads = [threading.Thread(target=run_camera,args=(c,cfg)) for c in cams]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
