# CCTV-to-YOLO

Standalone vehicle arrival event logger for Bengkalis and Pakning. No ETA–ETD integration in this phase. RTMP publishers (OBS, Larix, IP cameras) → MediaMTX on VPS → RTSP/TCP → YOLO on campus PC → CSV and JSON Lines per inbound vehicle crossing. No five-minute aggregation. Timestamp is campus observation time, not guaranteed camera capture time. No credentials or production deployment in GitHub.

Development and deployment instructions will be in the project files. Do not modify existing ETA–ETD services; inspect live VPS ports first.
