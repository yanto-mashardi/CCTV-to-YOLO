# CCTV-to-YOLO
Standalone real-time vehicle arrival counting for Bengkalis and Pakning. RTMP (OBS/Larix/CCTV) → MediaMTX VPS relay → RTSP/TCP → campus YOLO. No video recording by default, no ETA–ETD integration or queue logic. Only car and motorcycle classes counted in this phase.

Live JSON: overwritten atomically per event, reset at WIB midnight. Daily CSV: time and cumulative motorcycle/car counts per crossing, one file per port/day, local spool copied to Google Drive Desktop after day closes. No JSONL archive, no five-minute aggregation. Simulation and observed output separated. See docs/SETUP.md and docs/STORAGE.md. No credentials in GitHub; not deployed.
