import httpx
from pathlib import Path

img = r"C:/Users/simmer/Pictures/Camera Roll/anomaly.jpg"
files = {
    "task_id": (None, "test-001"),
    "asset_id": (None, "asset-001"),
    "start_time": (None, "2026-04-18T10:00:00"),
    "end_time": (None, "2026-04-18T10:05:00"),
    "question": (None, "please analyze anomalies"),
    "image": (Path(img).name, open(img, "rb"), "image/jpeg"),
}
c = httpx.Client(timeout=120.0)
r = c.post("http://127.0.0.1:8000/v1/detect", files=files)
print("Status:", r.status_code)
print("Raw:", r.text[:3000])
c.close()
