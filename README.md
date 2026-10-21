# VEEKSHA 🚌👁️
### Mobile Urban Intelligence & Evidence Network

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00ffff?logo=yolo)](https://ultralytics.com)
[![WebSocket](https://img.shields.io/badge/WebSockets-Real--Time-blue)](https://websockets.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

VEEKSHA is an Edge-to-Cloud smart city platform that transforms everyday public transport buses and mobile edge devices into a distributed, real-time vision network. It detects road infrastructure anomalies (such as **potholes** and **waterlogging**) using Edge AI, verifies them through a multi-frame **temporal consensus engine**, logs evidence with geospatial tags into SQLite, and streams low-latency telemetry to a centralized command center.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────────┐
                    │     Mobile Edge Node       │
                    │   (Smartphone / Camera)    │
                    │  mobile-edge.html / driver │
                    └─────────────┬──────────────┘
                                  │  WebSocket (/ws/edge/{bus_id})
                                  │  Streams 480x320 @ 5 FPS + GPS
                                  ▼
                    ┌────────────────────────────┐
                    │    VEEKSHA Edge AI Hub     │
                    │      (veeksha-backend)     │
                    │  - Dual YOLOv8 Inference   │
                    │  - Temporal Consensus (3x) │
                    │  - SQLite Evidence Logging │
                    └───────┬────────────┬───────┘
                            │            │
  Local WebSocket           │            │  Uplink WebSocket
  (/ws/dashboard)           │            │  (/ws/relay)
                            ▼            ▼
     ┌────────────────────────────┐   ┌────────────────────────────┐
     │   Local Command Center     │   │    VEEKSHA Cloud Relay     │
     │   veeksha-dashboard.html   │   │      (veeksha-cloud)       │
     └────────────────────────────┘   └──────────────┬─────────────┘
                                                     │  Global WebSockets
                                                     │  (/ws/dashboard)
                                                     ▼
                                      ┌────────────────────────────┐
                                      │   Global Remote Console    │
                                      │   Municipal Web Clients    │
                                      └────────────────────────────┘
```

---

## 🚀 Quick Start (Local Run)

### 1. Prerequisites
- **Python 3.10 - 3.14**
- Core Python packages:
  ```bash
  pip install -r veeksha-command-center/requirements.txt
  ```

### 2. Launch with One Command
Run the master launcher:
```bash
python run_veeksha.py
```
*(Windows users can also double-click `start_veeksha.bat` or run `npm start`)*

This starts the Command Hub on port `8000` and automatically displays:
- **Operator Portal:** `http://localhost:8000/` (Passcode: `RadheRadhe`)
- **Command Center Dashboard:** `http://localhost:8000/veeksha-dashboard.html`
- **Driver Cabin Portal:** `http://localhost:8000/driver.html`
- **Mobile Edge Camera URL:** `http://<YOUR_LAN_IP>:8000/mobile-edge.html`

---

## 📱 Connecting a Phone as an Edge Node

1. Ensure your smartphone and laptop are connected to the **same Wi-Fi network**.
2. Note the LAN IP shown in terminal when running `python run_veeksha.py` (e.g. `http://192.168.1.15:8000`).
3. Open `http://<YOUR_LAN_IP>:8000/mobile-edge.html` on your phone's browser.
4. Mount the phone on the bus windshield or vehicle dashboard.
5. The edge node automatically streams live frames, GPS telemetry, and displays real-time AI confidence scores.

### 🎬 No Phone? Instant Demo Testing
If you don't have a phone or road camera handy:
1. Open `http://localhost:8000/mobile-edge.html` in a browser tab.
2. Click **"UPLOAD VIDEO"**.
3. Click the blue button: **"🎬 LOAD DEMO ROAD FOOTAGE"**.
4. The built-in `demo_road.mp4` loops automatically, and the dual AI engine immediately detects potholes and transmits alerts to the Command Center!

---

## ☁️ Cloud Deployment (VEEKSHA Cloud Relay)

`veeksha-cloud` acts as a high-performance, asynchronous WebSocket relay for multi-city fleet aggregation.

### Deploying to Render (Free Web Service)
1. Fork or push this repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com), click **New +** → **Web Service**.
3. Connect your repository.
4. Configure:
   - **Root Directory:** `veeksha-cloud`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click **Deploy**. Render will generate a URL like `https://veeksha-cloud.onrender.com`.

### Deploying with Docker
```bash
cd veeksha-cloud
docker build -t veeksha-cloud .
docker run -p 10000:10000 veeksha-cloud
```

---

## ⚙️ Configuration & Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` (Hub) / `10000` (Cloud) | HTTP / WebSocket server port |
| `HOST` | `0.0.0.0` | Binding host address |
| `CLOUD_RELAY_URL` | `wss://veeksha-cloud.onrender.com/ws/relay` | Cloud WebSocket relay uplink URL |
| `VEEKSHA_SHOW_WINDOW` | `false` | Enable OpenCV GUI debug window on edge machine (`true` / `false`) |
| `NO_BROWSER` | `0` | Set `1` to prevent automatic browser launch on startup |

---

## 🔑 Access Credentials
- **Role:** Command Operations (Admin)
- **Passcode:** `RadheRadhe`

---

## 🛡️ License
Licensed under the [MIT License](LICENSE).
Designed for smart-city evaluations, hackathons, and public transport intelligent networks.
