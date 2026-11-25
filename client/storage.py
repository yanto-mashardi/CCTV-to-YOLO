"""Daily cumulative snapshots. Local CSV is the recovery source; Drive gets closed days."""
import csv
import json
import os
import shutil
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

WIB = timezone(timedelta(hours=7))
FIELDS = ["jam", "jumlah_motor", "jumlah_mobil"]

def atomic_json(path, data):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

class DailyStore:
    def __init__(self, root, port, clock=None):
        self.root = Path(root)
        self.port = port
        self.clock = clock or (lambda: datetime.now(WIB))
        self.lock = threading.RLock()
        self.live = self.root / "live" / (port + ".json")
        self.daily = self.root / "daily" / port
        self.live.parent.mkdir(parents=True, exist_ok=True)
        self.daily.mkdir(parents=True, exist_ok=True)
        self.day = None
        self.state = {}
        self.tick()

    def _append(self, path, state):
        new = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: state[k] for k in FIELDS})
            f.flush()
            os.fsync(f.fileno())

    def _roll(self, now):
        day = now.date().isoformat()
        if self.day == day:
            return
        if self.day and day < self.day:
            raise RuntimeError("System clock moved to a previous day")
        path = self.daily / (day + ".csv")
        state = dict(tanggal=day, jam=now.strftime("%H:%M:%S.%f")[:-3], jumlah_motor=0, jumlah_mobil=0)
        if path.exists() and path.stat().st_size:
            with path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    state.update(jam=row["jam"], jumlah_motor=int(row["jumlah_motor"]), jumlah_mobil=int(row["jumlah_mobil"]))
        else:
            self._append(path, state)
        atomic_json(self.live, state)
        self.day, self.state = day, state

    def tick(self):
        with self.lock:
            self._roll(self.clock())

    def add(self, label):
        with self.lock:
            now = self.clock()
            self._roll(now)
            key = {"motorcycle": "jumlah_motor", "car": "jumlah_mobil"}[label]
            state = dict(self.state)
            state[key] += 1
            state["jam"] = now.strftime("%H:%M:%S.%f")[:-3]
            self._append(self.daily / (self.day + ".csv"), state)
            self.state = state
            atomic_json(self.live, state)
            return dict(state)

    def archive(self, drive_root):
        """Retry-safe local copy to existing Drive Desktop folder, not cloud confirmation."""
        root = Path(drive_root)
        if not root.is_dir():
            raise OSError("Google Drive archive root is unavailable")
        with self.lock:
            self._roll(self.clock())
            closed = [p for p in self.daily.glob("????-??-??.csv") if p.stem < self.day]
        for src in closed:
            dest = root / self.port / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() == src.read_bytes():
                continue
            tmp = dest.with_suffix(".tmp")
            shutil.copyfile(src, tmp)
            os.replace(tmp, dest)
            if dest.read_bytes() != src.read_bytes():
                raise OSError("Archive copy verification failed")
