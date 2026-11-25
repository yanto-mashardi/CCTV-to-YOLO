# Storage contract
- Local output/<simulation|observed>/live/<port>.json: tanggal, jam, jumlah_motor, jumlah_mobil. Counts are cumulative daily; reset at midnight WIB while process runs, or on next startup if offline. Time is campus write time with milliseconds.
- Local output/<mode>/daily/<port>/YYYY-MM-DD.csv: jam,jumlah_motor,jumlah_mobil. Initial snapshot at startup/rollover and one row per crossing. Local CSV is recovery source; retain it until cloud sync is confirmed.
- Google Drive Desktop archive: set CCTV_GDRIVE_ARCHIVE to an existing user-selected folder. Create simulation and observed subfolders in it. Closed days copied to <mode>/<port>/YYYY-MM-DD.csv, retried periodically. Only CSV copied; no video or JSON. Local copy byte verification is not proof of cloud sync. Check Drive Desktop status. Use one process per port/mode, do not edit live CSV while running.
- Only COCO car and motorcycle classes counted; bus/truck excluded pending classification decision.
- No queue, loading, aggregation, or ETD model logic. Disconnection prints operational warning; no data completeness proof from a flat count alone. No video recording by default; manual validation recording remains to be implemented separately.
- Test: from client, python -m unittest test_storage test_counting. Prototype; live stream/Drive sync not yet validated.
