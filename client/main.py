import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS","rtsp_transport;tcp")
import argparse, csv, json, time, uuid, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter as Totals
import cv2
from ultralytics import YOLO
from counting import Counter

CLASSES={2:"car",3:"motorcycle",5:"bus",7:"truck"}
FIELDS=["event_id","observed_at","port","vehicle_class","track_id","session_id","direction","confidence","source_status","class_total","vehicle_total"]
WIB=timezone(timedelta(hours=7))

def run_camera(cam,cfg):
    name=cam["name"]
    url=os.environ[cam["url_env"]]
    folder=Path(cfg["output"])/name
    folder.mkdir(parents=True,exist_ok=True)
    journal=folder/"events.jsonl"
    csv_path=folder/"events.csv"
    totals=Totals()
    # JSONL is the primary journal; rebuild CSV from it after restart.
    with csv_path.open("w",newline="",encoding="utf-8") as cf:
        writer=csv.DictWriter(cf,fieldnames=FIELDS)
        writer.writeheader()
        if journal.exists():
            with journal.open(encoding="utf-8") as jf:
                for line in jf:
                    row=json.loads(line)
                    totals[row["vehicle_class"]]+=1
                    writer.writerow(row)
    with journal.open("a",encoding="utf-8") as jf, csv_path.open("a",newline="",encoding="utf-8") as cf:
        writer=csv.DictWriter(cf,fieldnames=FIELDS)
        while True:
            cap=cv2.VideoCapture(url,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,10000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
            session=uuid.uuid4().hex
            counter=Counter(cam["line"],cam["entry"])
            model=YOLO(cfg["model"])
            try:
                while cap.isOpened():
                    ok,frame=cap.read()
                    if not ok: break
                    observed=datetime.now(WIB).isoformat(timespec="milliseconds")
                    h,w=frame.shape[:2]
                    result=model.track(frame,persist=True,tracker="bytetrack.yaml",classes=list(CLASSES),device=cfg["device"],verbose=False)[0]
                    boxes=result.boxes
                    if boxes is None or boxes.id is None: continue
                    for xy,tid,cls,conf in zip(boxes.xyxy.cpu().tolist(),boxes.id.int().cpu().tolist(),boxes.cls.int().cpu().tolist(),boxes.conf.cpu().tolist()):
                        point=((xy[0]+xy[2])/(2*w),xy[3]/h)
                        if not counter.update(tid,point,time.monotonic()): continue
                        label=CLASSES[cls]
                        totals[label]+=1
                        row=dict(event_id=uuid.uuid4().hex,observed_at=observed,port=name,vehicle_class=label,track_id=tid,session_id=session,direction="inbound",confidence=round(conf,4),source_status=cam["source_status"],class_total=totals[label],vehicle_total=sum(totals.values()))
                        jf.write(json.dumps(row)+"\n"); jf.flush(); os.fsync(jf.fileno())
                        writer.writerow(row); cf.flush()
                        print(name,label,totals[label],sum(totals.values()),flush=True)
            finally:
                cap.release()
            with (folder/"connection.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps({"time":datetime.now(WIB).isoformat(),"status":"disconnected","session_id":session})+"\n")
            time.sleep(2)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--config",default="config.local.json")
    p.add_argument("--camera",choices=["bengkalis","pakning","all"],default="all")
    args=p.parse_args()
    with open(args.config,encoding="utf-8") as f: cfg=json.load(f)
    cams=[c for c in cfg["cameras"] if args.camera in ("all",c["name"])]
    for c in cams:
        if not os.environ.get(c["url_env"]): raise SystemExit("Missing "+c["url_env"])
    threads=[threading.Thread(target=run_camera,args=(c,cfg)) for c in cams]
    for t in threads: t.start()
    for t in threads: t.join()
