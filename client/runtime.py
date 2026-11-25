import cv2
import time
import threading
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

class LatestFrame:
    def __init__(self,url):
        self.cv=threading.Condition()
        self.seq=0
        self.frame=None
        self.closed=False
        self.stop=False
        self.thread=threading.Thread(target=self.run,args=(url,),daemon=True)
        self.thread.start()
    def run(self,url):
        cap=None
        try:
            cap=cv2.VideoCapture(url,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,10000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
            while not self.stop and cap.isOpened():
                ok,frame=cap.read()
                if not ok: break
                with self.cv:
                    self.seq+=1
                    self.frame=frame
                    self.cv.notify_all()
        finally:
            if cap is not None: cap.release()
            with self.cv:
                self.closed=True
                self.cv.notify_all()
    def read(self,seq):
        with self.cv:
            self.cv.wait_for(lambda:self.closed or self.seq>seq,timeout=15)
            if self.closed or self.seq<=seq: return None
            return self.seq,self.frame
    def release(self):
        self.stop=True
        self.thread.join(timeout=16)

class Validation:
    def __init__(self,root,fps):
        self.root=Path(root)
        self.fps=float(fps)
        self.lock=threading.Lock()
        self.ports={p:dict(until=0,record_until=0,last=0,jpeg=None,writer=None,status="OFFLINE",frames=0) for p in ("bengkalis","pakning")}
    def status(self,p,status):
        with self.lock:
            s=self.ports[p]
            s["status"]=status
            if status!="ONLINE":
                s["jpeg"]=None
                self.close_writer(s)
    def close_writer(self,s):
        if s["writer"] is not None:
            s["writer"].release()
            s["writer"]=None
    def control(self,p,action,seconds):
        with self.lock:
            s=self.ports[p]
            now=time.monotonic()
            if action=="preview": s["until"]=now+seconds
            elif action=="record": s["record_until"]=now+seconds
            elif action=="stop":
                s["until"]=s["record_until"]=0
                s["jpeg"]=None
                self.close_writer(s)
            else: raise ValueError("Invalid action")
    def frame(self,p,frame,result,line,state):
        with self.lock:
            s=self.ports[p]
            now=time.monotonic()
            s["frames"]+=1
            recording=now<s["record_until"]
            preview=now<s["until"]
            if not recording: self.close_writer(s)
            if not preview: s["jpeg"]=None
            if not (recording or preview) or now-s["last"]<1/self.fps: return
            s["last"]=now
            img=result.plot()
            h,w=img.shape[:2]
            a,b=[(int(x*w),int(y*h)) for x,y in line]
            cv2.line(img,a,b,(0,255,255),2)
            cv2.putText(img,f'Motor {state.get("jumlah_motor",0)}  Mobil {state.get("jumlah_mobil",0)}',(10,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2)
            if preview:
                ok,data=cv2.imencode(".jpg",img,[cv2.IMWRITE_JPEG_QUALITY,75])
                if ok: s["jpeg"]=data.tobytes()
            if recording:
                if s["writer"] is None:
                    folder=self.root/"validation"/p
                    folder.mkdir(parents=True,exist_ok=True)
                    path=folder/(time.strftime("%Y%m%d_%H%M%S")+"_"+str(time.time_ns())+".mp4")
                    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),self.fps,(w,h))
                    if not writer.isOpened():
                        writer.release()
                        s["record_until"]=0
                        print(p,"validation recording failed",flush=True)
                        return
                    s["writer"]=writer
                s["writer"].write(img)
    def snapshot(self,p):
        with self.lock:
            s=self.ports[p]
            return dict(status=s["status"],frames=s["frames"],preview=time.monotonic()<s["until"],recording=time.monotonic()<s["record_until"])
    def expire(self):
        with self.lock:
            now=time.monotonic()
            for s in self.ports.values():
                if now>=s["record_until"]: self.close_writer(s)
                if now>=s["until"]: s["jpeg"]=None

PAGE="""<!doctype html><meta charset=utf-8><title>CCTV local validation</title>
<h2>Local CCTV validation</h2><p>Preview and recording disabled by default. Recording saves annotated video locally.</p>
<div id=app></div><script>
for(const p of ['bengkalis','pakning']){
const d=document.createElement('section');d.innerHTML='<h3>'+p+'</h3><button>Preview 5 min</button> <button>Record 5 min</button> <button>Stop</button><p><img width=640></p><pre></pre>';document.querySelector('#app').append(d);
const buttons=d.querySelectorAll('button');['preview','record','stop'].forEach((a,i)=>buttons[i].onclick=()=>fetch('/control?port='+p+'&action='+a+'&seconds=300',{method:'POST'}));
setInterval(async()=>{const s=await(await fetch('/status?port='+p)).json();d.querySelector('pre').textContent=JSON.stringify(s);const im=d.querySelector('img');if(s.preview)im.src='/frame?port='+p+'&t='+Date.now();else im.removeAttribute('src');},200);
}</script>"""
class PreviewServer:
    def __init__(self,v):
        self.v=v
    def start(self):
        v=self.v
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def send(self,status,kind,data):
                self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Cache-Control","no-store");self.end_headers()
                self.wfile.write(data)
            def do_GET(self):
                q=urlparse(self.path);p=parse_qs(q.query).get("port",[""])[0]
                if q.path=="/": return self.send(200,"text/html; charset=utf-8",PAGE.encode())
                if p not in v.ports: return self.send(400,"text/plain",b"Invalid port")
                if q.path=="/status": return self.send(200,"application/json",json.dumps(v.snapshot(p)).encode())
                if q.path=="/frame":
                    with v.lock: data=v.ports[p]["jpeg"]
                    return self.send(200,"image/jpeg",data) if data else self.send(404,"text/plain",b"No frame")
                self.send(404,"text/plain",b"Not found")
            def do_POST(self):
                if self.headers.get("Origin") not in (None,"http://127.0.0.1:8765"): return self.send(403,"text/plain",b"Forbidden")
                q=urlparse(self.path);a=parse_qs(q.query)
                try:
                    if q.path!="/control": raise ValueError()
                    v.control(a["port"][0],a["action"][0],max(1,min(3600,int(a["seconds"][0]))))
                except (KeyError,ValueError): return self.send(400,"text/plain",b"Invalid control")
                self.send(200,"application/json",b'{"ok":true}')
        self.http=ThreadingHTTPServer(("127.0.0.1",8765),Handler)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        def expire():
            while True:
                v.expire()
                time.sleep(.5)
        threading.Thread(target=expire,daemon=True).start()
