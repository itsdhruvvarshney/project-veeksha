import base64
import json
import datetime
import cv2
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from vision_core import VeekshaVisionEngine

# 👉 Apna Render URL yahan check kar lena
CLOUD_RELAY_URL = "wss://veeksha-cloud.onrender.com/ws/relay" 

app = FastAPI()
vision_engine = VeekshaVisionEngine(pothole_model="best_16_rebuilt.pt", water_model="waterlogging.pt")

cloud_ws = None

async def connect_to_cloud():
    global cloud_ws
    while True:
        try:
            if cloud_ws is None:
                cloud_ws = await websockets.connect(CLOUD_RELAY_URL)
                print("\n[✓] SECURE UPLINK TO CLOUD COMMAND CENTER ESTABLISHED")
            else:
                # Har 3 second me cloud ko 'Ping' karega taaki connection zinda rahe
                await cloud_ws.ping() 
        except Exception as e:
            # Agar connection sach me toot jaye, toh wapas try karega
            cloud_ws = None
        await asyncio.sleep(3)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(connect_to_cloud())

@app.websocket("/ws/edge/{bus_id}")
async def edge_endpoint(websocket: WebSocket, bus_id: str):
    global cloud_ws
    await websocket.accept()
    print(f"\n[+] BUS CAMERA CONNECTED: {bus_id}")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "FRAME_DATA":
                base64_str = payload["image"].split(",")[1]
                img_bytes = base64.b64decode(base64_str)
                confirmed_events, display_frame, current_stats = vision_engine.process_frame(img_bytes, bus_id)

                await websocket.send_json({"type": "FRAME_STATS", "stats": current_stats, "req_timestamp": payload.get("timestamp")})

                gps_coords = payload.get("gps", "28.75333, 77.49881")
                ts = datetime.datetime.now().isoformat()

                # Video ko resize aur compress karo taaki lag khatam ho jaye
                small_frame = cv2.resize(display_frame, (480, 320))
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 30])
                b64_frame = base64.b64encode(buffer).decode('utf-8')

                # SEND LIVE FEED TO CLOUD
                if cloud_ws:
                    try:
                        await cloud_ws.send(json.dumps({
                            "type": "LIVE_FEED", "bus_id": bus_id, "gps": gps_coords, "image": f"data:image/jpeg;base64,{b64_frame}"
                        }))
                    except:
                        cloud_ws = None # Tuta toh reconnect hoga

                # SEND ANOMALY EVIDENCE TO CLOUD
                if confirmed_events:
                    for event in confirmed_events:
                        print(f"🚨 [AI DETECTED] {event['event_type'].upper()}")
                        try: lat, lng = map(float, gps_coords.split(","))
                        except: lat, lng = 28.75333, 77.49881 

                        if cloud_ws:
                            try:
                                await cloud_ws.send(json.dumps({
                                    "type": "CRITICAL_ANOMALY", "event": event["event_type"], "node": bus_id,
                                    "confidence": event["confidence"], "position": [lat, lng], "timestamp": ts,
                                    "image_url": f"data:image/jpeg;base64,{b64_frame}" 
                                }))
                            except:
                                cloud_ws = None

                cv2.imshow(f"Bus Local AI Unit - {bus_id}", display_frame)
                cv2.waitKey(1)
    except WebSocketDisconnect:
        print(f"\n[-] BUS CAMERA DISCONNECTED: {bus_id}")
        cv2.destroyAllWindows()

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)