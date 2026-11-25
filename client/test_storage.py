import tempfile
import unittest
from pathlib import Path
from datetime import datetime
import csv
import json
from storage import DailyStore, WIB

class TestStorage(unittest.TestCase):
    def test_recovery_rollover_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = [datetime(2026,11,25,23,59,58,tzinfo=WIB)]
            s = DailyStore(root/"local","bengkalis",lambda:now[0])
            s.add("motorcycle")
            s.add("car")
            s = DailyStore(root/"local","bengkalis",lambda:now[0])
            self.assertEqual(s.state["jumlah_mobil"],1)
            now[0] = datetime(2026,11,26,0,0,0,tzinfo=WIB)
            s.tick()
            self.assertEqual(json.loads(s.live.read_text())["jumlah_motor"],0)
            drive = root/"drive"
            drive.mkdir()
            s.archive(drive)
            s.archive(drive)
            with (drive/"bengkalis"/"2026-11-25.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[-1]["jumlah_motor"],"1")
            self.assertEqual(len(list(drive.rglob("*.csv"))),1)
if __name__ == "__main__":
    unittest.main()
