#!/usr/bin/env python3
"""
VEEKSHA - Mobile Urban Intelligence & Evidence Network
Master Launch Script for Command Center & Edge AI Engine
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import socket
import webbrowser
import threading
import time
from pathlib import Path

# Add veeksha-backend to python path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "veeksha-command-center" / "veeksha-backend"
sys.path.insert(0, str(BACKEND_DIR))

def find_available_port(preferred=8000):
    candidates = [preferred, 8080, 8001, 8002, 8888]
    for port in candidates:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            return port
        except Exception:
            continue
    return preferred

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def open_browser_after_delay(url, delay=2.5):
    def _open():
        time.sleep(delay)
        print(f"[+] Launching Operator Portal in browser: {url}")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

def main():
    chosen_port = int(os.getenv("PORT", find_available_port(8000)))
    os.environ["PORT"] = str(chosen_port)
    host = os.getenv("HOST", "0.0.0.0")
    lan_ip = get_lan_ip()

    print("=" * 66)
    print("   VEEKSHA - Mobile Urban Intelligence & Evidence Network")
    print("=" * 66)
    print(f" [*] Local Operator Portal:  http://localhost:{chosen_port}/")
    print(f" [*] Command Dashboard:     http://localhost:{chosen_port}/veeksha-dashboard.html")
    print(f" [*] Driver Cabin Portal:   http://localhost:{chosen_port}/driver.html")
    print("-" * 66)
    print(f" [PHONE] CONNECT PHONE / EDGE NODE ON SAME WI-FI:")
    print(f"         Open on mobile browser: http://{lan_ip}:{chosen_port}/mobile-edge.html")
    print("-" * 66)
    print(f" [*] Admin Passcode for Command Operations: RadheRadhe")
    print("=" * 66)

    # Automatically open local operator portal
    if os.getenv("NO_BROWSER", "0") != "1":
        open_browser_after_delay(f"http://localhost:{chosen_port}/")

    # Import and run server
    import uvicorn
    from server import app
    uvicorn.run(app, host=host, port=chosen_port)

if __name__ == "__main__":
    main()
