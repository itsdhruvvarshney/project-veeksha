# VEEKSHA 🚌👁️
**Mobile Urban Intelligence & Evidence Network**

VEEKSHA is a production-grade, Edge-to-Cloud smart city platform that transforms everyday public transport buses into a distributed, real-time vision network. It detects road infrastructure anomalies (like potholes and waterlogging) using Edge AI and streams live telemetry directly to a centralized municipal command center.

## 🚀 Key Features

* **Edge AI Processing:** Runs YOLO-based object detection locally on edge nodes (smartphones/bus cameras) to save bandwidth and ensure zero-latency inference.
* **Live Fleet Tracking:** Real-time geospatial mapping of the entire public transport fleet using dynamic SVG rendering and smooth CSS transitions.
* **Zero-Latency Video Streaming:** WebSocket-based continuous live video feed from any active edge node directly to the command center dashboard.
* **Multi-Sensor Consensus Engine:** Automatically corroborates detections from multiple buses over a temporal window to verify anomalies and filter out false positives.
* **Automated Evidence Logging:** Captures and saves bounding-box annotated evidence images the moment a critical anomaly is verified.

## 🏗️ Architecture Stack

* **AI Engine:** YOLOv8 (Ultralytics) + ByteTrack for temporal tracking.
* **Backend:** FastAPI + WebSockets (Python) for asynchronous, high-concurrency data streams.
* **Frontend Dashboard:** HTML5, CSS3 (Glassmorphism UI), Vanilla JavaScript, Leaflet.js (for OpenStreetMap integration), and Chart.js.
* **Database:** SQLite for lightweight event logging.

## ⚙️ Local Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/veeksha-live.git](https://github.com/yourusername/veeksha-live.git)
   cd veeksha-live

Install dependencies:

Bash
pip install -r requirements.txt
Run the Command Hub (Backend):

Bash
python server.py
The server will start on http://localhost:8000.

Launch the Interfaces:

Open veeksha-dashboard.html in your browser for the Command Center.

Open mobile-edge.html on your mobile device (ensure it's on the same network or use Ngrok/Cloud deployment).

🛡️ License & Terms
This project is licensed under the MIT License - designed exclusively for demonstration, academic evaluation, and smart-city hackathon deployments.