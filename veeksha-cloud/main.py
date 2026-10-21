import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import time
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="VEEKSHA Cloud Relay Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dashboards = set()
edge_relays = set()

# State caching: latest fleet locations and recent critical anomalies
fleet_state = {} # bus_id -> { gps, image, timestamp }
recent_anomalies = deque(maxlen=50)

@app.get("/")
def health_check():
    return {
        "status": "VEEKSHA Cloud Relay Online",
        "service": "veeksha-cloud",
        "connected_dashboards": len(dashboards),
        "connected_edge_relays": len(edge_relays),
        "active_fleet_nodes": len(fleet_state),
        "cached_anomalies": len(recent_anomalies),
        "timestamp": time.time()
    }

@app.get("/health")
def health_simple():
    return {"status": "ok"}

@app.get("/api/stats")
def stats():
    return {
        "connected_dashboards": len(dashboards),
        "connected_edge_relays": len(edge_relays),
        "fleet": list(fleet_state.keys()),
        "recent_anomalies_count": len(recent_anomalies)
    }

@app.websocket("/ws/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await websocket.accept()
    dashboards.add(websocket)
    print(f"[+] Dashboard connected. Total: {len(dashboards)}")

    # Send cached state to newly connected dashboard
    try:
        # 1. Send recent anomalies
        for anomaly in list(recent_anomalies):
            await websocket.send_text(json.dumps(anomaly))
        # 2. Send latest positions of active buses
        for bus_id, bus_data in list(fleet_state.items()):
            await websocket.send_text(json.dumps({
                "type": "LIVE_FEED",
                "bus_id": bus_id,
                "gps": bus_data.get("gps", "28.75333, 77.49881"),
                "image": bus_data.get("image", "")
            }))
    except Exception as e:
        print(f"[!] Error seeding initial state to dashboard: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboards.discard(websocket)
        print(f"[-] Dashboard disconnected. Remaining: {len(dashboards)}")

@app.websocket("/ws/relay")
async def relay_endpoint(websocket: WebSocket):
    await websocket.accept()
    edge_relays.add(websocket)
    print(f"[+] Edge Compute Node connected to Cloud Relay. Total Relays: {len(edge_relays)}")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Cache fleet location
                if payload.get("type") == "LIVE_FEED" and "bus_id" in payload:
                    fleet_state[payload["bus_id"]] = {
                        "gps": payload.get("gps"),
                        "image": payload.get("image", ""),
                        "timestamp": time.time()
                    }
                elif payload.get("type") == "CRITICAL_ANOMALY":
                    recent_anomalies.append(payload)
            except Exception:
                pass

            # Forward data to all active dashboards
            dead_dashboards = set()
            for dash in list(dashboards):
                try:
                    await dash.send_text(data)
                except Exception:
                    dead_dashboards.add(dash)
            dashboards.difference_update(dead_dashboards)

    except WebSocketDisconnect:
        edge_relays.discard(websocket)
        print(f"[-] Edge Compute Node disconnected. Remaining Relays: {len(edge_relays)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"[INFO] VEEKSHA Cloud Relay starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
