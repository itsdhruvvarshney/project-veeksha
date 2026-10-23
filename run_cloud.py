#!/usr/bin/env python3
"""
VEEKSHA - Cloud Relay Server Launcher
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CLOUD_DIR = ROOT_DIR / "veeksha-cloud"
sys.path.insert(0, str(CLOUD_DIR))

def main():
    port = int(os.getenv("PORT", 10000))
    host = os.getenv("HOST", "0.0.0.0")

    print("=" * 66)
    print("   VEEKSHA Cloud Relay Server")
    print("=" * 66)
    print(f" [*] Cloud Relay Listening on: ws://{host}:{port}/ws/relay")
    print(f" [*] Dashboards Connecting to: ws://{host}:{port}/ws/dashboard")
    print(f" [*] Health Check URL:        http://{host}:{port}/health")
    print("=" * 66)

    import uvicorn
    from main import app
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
