import os
import sys
from pathlib import Path
import cv2
import numpy as np
import base64
import json
import sqlite3
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "veeksha-backend"
DB_PATH = BASE_DIR / "edge_events.db"
MODEL_PATH = BACKEND_DIR / "best_16_rebuilt.pt" if (BACKEND_DIR / "best_16_rebuilt.pt").exists() else BASE_DIR / "best_16_rebuilt.pt"
SHOW_LOCAL_WINDOW = os.getenv("VEEKSHA_SHOW_WINDOW", "false").lower() in ("true", "1", "yes")

app = FastAPI(title="VEEKSHA Edge Processing Node")

print(f"[INFO] Loading YOLO Model from {MODEL_PATH}...")
model = YOLO(str(MODEL_PATH))
print("[INFO] Model Loaded Successfully!")

# SQLite Database for Urban Events
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_id TEXT,
        event_type TEXT,
        confidence REAL,
        gps TEXT,
        timestamp TEXT
    )
""")
conn.commit()

# Temporal Validation Memory
track_history = {} 
TEMPORAL_HITS_REQUIRED = 3

@app.websocket("/ws/edge/{bus_id}")
async def edge_endpoint(websocket: WebSocket, bus_id: str):
    await websocket.accept()
    print(f"\n[+] VEEKSHA EDGE NODE CONNECTED: {bus_id}")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "FRAME_DATA":
                img_data = payload.get("image", "")
                base64_str = img_data.split(",")[1] if "," in img_data else img_data
                img_bytes = base64.b64decode(base64_str)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                current_frame_ids = []
                max_conf = 0.0
                confirmed_events = []

                if results[0].boxes is not None and len(results[0].boxes) > 0:
                    boxes = results[0].boxes
                    has_ids = boxes.id is not None
                    for idx, (box, conf) in enumerate(zip(boxes.xyxy, boxes.conf)):
                        confidence = float(conf.item())
                        max_conf = max(max_conf, confidence)
                        tid = int(boxes.id[idx].item()) if has_ids else idx + 1
                        current_frame_ids.append(tid)

                        if tid not in track_history:
                            track_history[tid] = {"hits": 1, "synced": False}
                        else:
                            track_history[tid]["hits"] += 1

                        if track_history[tid]["hits"] >= TEMPORAL_HITS_REQUIRED and not track_history[tid]["synced"]:
                            print(f"🚀 [VERIFIED EVENT] Pothole Detected! Track ID: {tid} | Conf: {confidence:.2f}")
                            gps_coords = payload.get("gps", "Unknown")
                            ts = datetime.datetime.now().isoformat()
                            cursor.execute(
                                "INSERT INTO events (bus_id, event_type, confidence, gps, timestamp) VALUES (?,?,?,?,?)",
                                (bus_id, "pothole", confidence, gps_coords, ts)
                            )
                            conn.commit()
                            track_history[tid]["synced"] = True
                            confirmed_events.append({
                                "event_type": "pothole",
                                "confidence": confidence,
                                "track_id": str(tid)
                            })

                # Send feedback stats to mobile HUD
                await websocket.send_json({
                    "type": "FRAME_STATS",
                    "stats": {"pothole_conf": max_conf, "water_conf": 0.0},
                    "req_timestamp": payload.get("timestamp")
                })

                if confirmed_events:
                    await websocket.send_json({
                        "type": "DETECTION_ALERT",
                        "events": confirmed_events
                    })

                for k in list(track_history.keys()):
                    if k not in current_frame_ids:
                        track_history[k]["hits"] = max(0, track_history[k]["hits"] - 1)
                        if track_history[k]["hits"] <= 0:
                            del track_history[k]

                if SHOW_LOCAL_WINDOW:
                    try:
                        annotated_frame = results[0].plot()
                        cv2.imshow(f"VEEKSHA Edge Processing - {bus_id}", annotated_frame)
                        cv2.waitKey(1)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        print(f"\n[-] EDGE NODE DISCONNECTED: {bus_id}")
        if SHOW_LOCAL_WINDOW:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

# Mount static frontend
if BASE_DIR.exists():
    app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
