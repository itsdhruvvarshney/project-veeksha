import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import base64
import json
import datetime
import asyncio
import sqlite3
from pathlib import Path

import cv2
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure veeksha-backend directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from vision_core import VeekshaVisionEngine

STATIC_DIR = BASE_DIR.parent # veeksha-command-center
DB_PATH = BASE_DIR / "veeksha_events.db"
CLOUD_RELAY_URL = os.getenv("CLOUD_RELAY_URL", "wss://veeksha-cloud.onrender.com/ws/relay")
SHOW_LOCAL_WINDOW = os.getenv("VEEKSHA_SHOW_WINDOW", "false").lower() in ("true", "1", "yes")

# Database initialization
def init_db():
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
    conn.close()

init_db()

def save_event_to_db(bus_id: str, event_type: str, confidence: float, gps: str, timestamp: str):
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (bus_id, event_type, confidence, gps, timestamp) VALUES (?, ?, ?, ?, ?)",
            (bus_id, event_type, confidence, gps, timestamp)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error saving event to SQLite: {e}")

app = FastAPI(title="VEEKSHA Command Hub & Edge AI Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vision_engine = VeekshaVisionEngine(
    pothole_model=str(BASE_DIR / "best_16_rebuilt.pt"),
    water_model=str(BASE_DIR / "waterlogging.pt")
)

cloud_ws = None
local_dashboards = set()
active_fleet = {} # bus_id -> { "last_seen": timestamp, "gps": coords }

async def broadcast_to_local_dashboards(message: str):
    if not local_dashboards:
        return
    dead_dashboards = set()
    for dash in list(local_dashboards):
        try:
            await dash.send_text(message)
        except Exception:
            dead_dashboards.add(dash)
    local_dashboards.difference_update(dead_dashboards)

async def connect_to_cloud():
    global cloud_ws
    while True:
        try:
            if cloud_ws is None:
                print(f"[i] Attempting uplink connection to Cloud Relay: {CLOUD_RELAY_URL}")
                cloud_ws = await asyncio.wait_for(websockets.connect(CLOUD_RELAY_URL), timeout=5.0)
                print("\n[✓] SECURE UPLINK TO CLOUD COMMAND CENTER ESTABLISHED")
            else:
                await cloud_ws.ping()
        except Exception:
            cloud_ws = None
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(connect_to_cloud())

# REST Endpoints for Dashboards & Monitoring
@app.get("/api/health")
def health_status():
    return {
        "status": "online",
        "service": "VEEKSHA Edge AI Command Hub",
        "active_fleet_count": len(active_fleet),
        "local_dashboards": len(local_dashboards),
        "cloud_relay_connected": cloud_ws is not None
    }

@app.get("/api/fleet")
def get_active_fleet():
    now = datetime.datetime.now()
    # Filter buses active in last 60 seconds
    fleet_list = []
    for bus_id, info in active_fleet.items():
        fleet_list.append({
            "id": bus_id,
            "gps": info.get("gps", "28.75333, 77.49881"),
            "last_seen": info.get("last_seen", "")
        })
    return {"fleet": fleet_list}

@app.get("/api/events")
def get_recent_events(limit: int = 50):
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"events": rows}
    except Exception as e:
        return {"events": [], "error": str(e)}

# WebSocket for Local Dashboards
@app.websocket("/ws/dashboard")
async def local_dashboard_endpoint(websocket: WebSocket):
    await websocket.accept()
    local_dashboards.add(websocket)
    print(f"[+] Local Dashboard connected. Total local dashboards: {len(local_dashboards)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        local_dashboards.discard(websocket)
        print("[-] Local Dashboard disconnected.")

# WebSocket for Driver Cabin Portal
@app.websocket("/ws/video")
async def driver_video_endpoint(websocket: WebSocket, fleet: str = "BUS-01"):
    await edge_endpoint(websocket, fleet)

# WebSocket for Edge Nodes (Smartphones / On-board Bus Cameras)
@app.websocket("/ws/edge/{bus_id}")
async def edge_endpoint(websocket: WebSocket, bus_id: str):
    global cloud_ws
    await websocket.accept()
    print(f"\n[+] BUS CAMERA CONNECTED: {bus_id}")
    active_fleet[bus_id] = {
        "last_seen": datetime.datetime.now().isoformat(),
        "gps": "28.75333, 77.49881"
    }

    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("{"):
                try:
                    payload = json.loads(data)
                except Exception:
                    continue
                img_data = payload.get("image", "")
                gps_coords = payload.get("gps", "28.75333, 77.49881")
                req_ts = payload.get("timestamp")
            else:
                # Raw base64 frame from driver.html
                payload = {"type": "FRAME_DATA"}
                img_data = data
                gps_coords = "28.75333, 77.49881"
                req_ts = None

            if payload.get("type") == "FRAME_DATA" or img_data:
                if "," in img_data:
                    base64_str = img_data.split(",")[1]
                else:
                    base64_str = img_data

                try:
                    img_bytes = base64.b64decode(base64_str)
                except Exception:
                    continue

                confirmed_events, display_frame, current_stats = vision_engine.process_frame(img_bytes, bus_id)

                ts = datetime.datetime.now().isoformat()
                active_fleet[bus_id] = {"last_seen": ts, "gps": gps_coords}

                # Send live frame stats back to Edge Node phone
                await websocket.send_json({
                    "type": "FRAME_STATS",
                    "stats": current_stats,
                    "req_timestamp": req_ts
                })

                # Compress video frame for lightweight dashboard streaming
                small_frame = cv2.resize(display_frame, (480, 320))
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 45])
                b64_frame = base64.b64encode(buffer).decode('utf-8')
                frame_data_url = f"data:image/jpeg;base64,{b64_frame}"

                feed_message = json.dumps({
                    "type": "LIVE_FEED",
                    "bus_id": bus_id,
                    "gps": gps_coords,
                    "image": frame_data_url
                })

                # Broadcast live feed to local dashboards
                await broadcast_to_local_dashboards(feed_message)

                # Send live feed to cloud relay
                if cloud_ws:
                    try:
                        await cloud_ws.send(feed_message)
                    except Exception:
                        cloud_ws = None

                # Process verified anomalies
                if confirmed_events:
                    # Notify edge phone UI
                    await websocket.send_json({
                        "type": "DETECTION_ALERT",
                        "events": confirmed_events
                    })

                    for event in confirmed_events:
                        event_type = event["event_type"].upper()
                        confidence = float(event["confidence"])
                        print(f"🚨 [AI DETECTED & VERIFIED] {event_type} on {bus_id} ({confidence*100:.1f}%)")

                        try:
                            lat, lng = map(float, gps_coords.split(","))
                        except Exception:
                            lat, lng = 28.75333, 77.49881

                        save_event_to_db(bus_id, event["event_type"], confidence, gps_coords, ts)

                        anomaly_msg = json.dumps({
                            "type": "CRITICAL_ANOMALY",
                            "event": event["event_type"],
                            "node": bus_id,
                            "confidence": confidence,
                            "position": [lat, lng],
                            "timestamp": ts,
                            "image_url": frame_data_url
                        })

                        # Broadcast to local dashboards
                        await broadcast_to_local_dashboards(anomaly_msg)

                        # Broadcast to cloud relay
                        if cloud_ws:
                            try:
                                await cloud_ws.send(anomaly_msg)
                            except Exception:
                                cloud_ws = None

                # Optional desktop GUI debug window
                if SHOW_LOCAL_WINDOW:
                    try:
                        cv2.imshow(f"Bus Local AI Unit - {bus_id}", display_frame)
                        cv2.waitKey(1)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        print(f"\n[-] BUS CAMERA DISCONNECTED: {bus_id}")
        if bus_id in active_fleet:
            del active_fleet[bus_id]
        if SHOW_LOCAL_WINDOW:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

# Mount static frontend
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    print(f"\n=======================================================")
    print(f"  VEEKSHA Command Hub & Edge AI Server Starting")
    print(f"  Access Operator Portal at: http://localhost:{port}/")
    print(f"  Access Command Center at:  http://localhost:{port}/veeksha-dashboard.html")
    print(f"  Access Edge Node Camera at: http://localhost:{port}/mobile-edge.html")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port)
