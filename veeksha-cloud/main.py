from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

dashboards = set()

@app.get("/")
def health_check():
    return {"status": "VEEKSHA Cloud Relay Online", "connected_dashboards": len(dashboards)}

@app.websocket("/ws/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await websocket.accept()
    dashboards.add(websocket)
    print(f"[+] Dashboard connected. Total: {len(dashboards)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboards.discard(websocket)
        print("[-] Dashboard disconnected.")

@app.websocket("/ws/relay")
async def relay_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[+] Edge Compute Node (Laptop) Connected to Cloud Relay")
    try:
        while True:
            data = await websocket.receive_text()
            # Dashboard ko data forward karo
            dead_dashboards = set()
            for dash in dashboards:
                try:
                    await dash.send_text(data)
                except:
                    dead_dashboards.add(dash)
            dashboards.difference_update(dead_dashboards)
    except WebSocketDisconnect:
        print("[-] Edge Compute Node Disconnected")