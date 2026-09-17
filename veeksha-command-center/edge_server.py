import cv2
import numpy as np
import base64
import json
import sqlite3
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from ultralytics import YOLO

# FastAPI App initialization
app = FastAPI()

# 1. Load your YOLO model
# Make sure "pothole.pt" is in the same folder as this script
print("[INFO] Loading YOLO Model...")
model = YOLO("best_16_rebuilt.pt")
print("[INFO] Model Loaded Successfully!")

# 2. Setup SQLite Database for Urban Events
conn = sqlite3.connect("edge_events.db", check_same_thread=False)
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

# 3. Temporal Validation Memory
# Ye dictionary track karegi ki ek pothole kitni baar dikha
track_history = {} 
TEMPORAL_HITS_REQUIRED = 3  # Kam se kam 3 frames me dikhna zaroori hai

@app.websocket("/ws/edge/{bus_id}")
async def edge_endpoint(websocket: WebSocket, bus_id: str):
    await websocket.accept()
    print(f"\n[+] VEEKSHA EDGE NODE CONNECTED: {bus_id}")

    try:
        while True:
            # Phone se frame receive karo
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "FRAME_DATA":
                # Base64 string ko wapas OpenCV Image me convert karo
                base64_str = payload["image"].split(",")[1]
                img_bytes = base64.b64decode(base64_str)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                # --- YOLO INFERENCE WITH BYTETRACK ---
                # persist=True ensures ByteTrack assigns consistent IDs
                results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                
                current_frame_ids = []

                # Agar kuch detect hua
                if results[0].boxes.id is not None:
                    boxes = results[0].boxes
                    for box, track_id, conf in zip(boxes.xyxy, boxes.id, boxes.conf):
                        tid = int(track_id.item())
                        confidence = float(conf.item())
                        current_frame_ids.append(tid)

                        # Update hit count
                        if tid not in track_history:
                            track_history[tid] = {"hits": 1, "synced": False}
                        else:
                            track_history[tid]["hits"] += 1

                        # --- TEMPORAL VALIDATION ---
                        # Agar lagatar 3 baar dikha aur abhi tak save nahi hua
                        if track_history[tid]["hits"] >= TEMPORAL_HITS_REQUIRED and not track_history[tid]["synced"]:
                            print(f"🚀 [VERIFIED EVENT] Pothole Detected! Track ID: {tid} | Conf: {confidence:.2f}")
                            
                            # 1. Save to SQLite
                            gps_coords = payload.get("gps", "Unknown")
                            ts = datetime.datetime.now().isoformat()
                            cursor.execute(
                                "INSERT INTO events (bus_id, event_type, confidence, gps, timestamp) VALUES (?,?,?,?,?)",
                                (bus_id, "pothole", confidence, gps_coords, ts)
                            )
                            conn.commit()
                            
                            # Mark as synced so we don't spam the DB
                            track_history[tid]["synced"] = True

                # Memory Cleanup: Remove old tracks that left the frame
                for k in list(track_history.keys()):
                    if k not in current_frame_ids:
                        track_history[k]["hits"] = max(0, track_history[k]["hits"] - 1)
                        if track_history[k]["hits"] <= 0:
                            del track_history[k]

                # --- LIVE DEBUG DISPLAY (For the judges!) ---
                annotated_frame = results[0].plot()
                cv2.imshow(f"VEEKSHA Edge Processing - {bus_id}", annotated_frame)
                cv2.waitKey(1)  # Refresh window

    except WebSocketDisconnect:
        print(f"\n[-] EDGE NODE DISCONNECTED: {bus_id}")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    import uvicorn
    # Run server on all interfaces (0.0.0.0) so phone can connect
    uvicorn.run(app, host="0.0.0.0", port=8000)