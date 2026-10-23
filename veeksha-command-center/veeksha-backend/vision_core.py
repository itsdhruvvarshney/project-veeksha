import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

def calculate_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interWidth = max(0, xB - xA)
    interHeight = max(0, yB - yA)
    interArea = interWidth * interHeight

    boxAArea = max(0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    unionArea = float(boxAArea + boxBArea - interArea)
    if unionArea <= 0:
        return 0.0
    return interArea / unionArea

class VeekshaVisionEngine:
    def __init__(self, pothole_model=None, water_model=None):
        base_dir = Path(__file__).resolve().parent
        pothole_path = pothole_model if pothole_model else str(base_dir / "best_16_rebuilt.pt")
        water_path = water_model if water_model else str(base_dir / "waterlogging.pt")

        print(f"[INFO] Booting Dual AI Engines (Pothole & Waterlogging)...")
        print(f"[INFO] Loading Pothole Model: {pothole_path}")
        self.model_p = YOLO(pothole_path)

        try:
            print(f"[INFO] Loading Waterlogging Model: {water_path}")
            self.model_w = YOLO(water_path)
            self.dual_mode = True
            print("[INFO] Both Pothole and Waterlogging models loaded successfully!")
        except Exception as e:
            print(f"[WARN] {water_path} not found or error. Running single engine. Error: {e}")
            self.dual_mode = False

        # Nested dictionary per bus:
        # { bus_id: { track_id: {"box": [x1, y1, x2, y2], "hits": int, "misses": int, "synced": bool, "confidence": float, "class_name": str} } }
        self.track_history = {}
        self.next_track_id = {}
        self.TEMPORAL_HITS_REQUIRED = 3
        self.MAX_MISSED_FRAMES = 5
        self.CONFIDENCE_THRESHOLD = 0.15
        print("[INFO] Dual Vision Core Online & Ready for Multi-Fleet!")

    def preprocess(self, frame):
        return cv2.resize(frame, (640, 480))

    def process_frame(self, frame_bytes, bus_id):
        if not frame_bytes:
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            return [], dummy, {"pothole_conf": 0.0, "water_conf": 0.0}

        try:
            np_arr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                dummy = np.zeros((480, 640, 3), dtype=np.uint8)
                return [], dummy, {"pothole_conf": 0.0, "water_conf": 0.0}
        except Exception:
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            return [], dummy, {"pothole_conf": 0.0, "water_conf": 0.0}

        frame = self.preprocess(frame)

        if bus_id not in self.track_history:
            self.track_history[bus_id] = {}
            self.next_track_id[bus_id] = 1

        confirmed_events = []
        current_stats = {"pothole_conf": 0.0, "water_conf": 0.0}
        detected_items = []

        # Run Pothole Model inference
        try:
            res_p = self.model_p(frame, verbose=False, conf=self.CONFIDENCE_THRESHOLD)
            if res_p and len(res_p) > 0 and res_p[0].boxes is not None:
                boxes = res_p[0].boxes
                for box, conf, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
                    c = float(conf.item())
                    current_stats["pothole_conf"] = max(current_stats["pothole_conf"], c)
                    cls_id = int(cls.item())
                    class_name = res_p[0].names.get(cls_id, "pothole")
                    detected_items.append({
                        "engine": "P",
                        "box": [float(v) for v in box],
                        "confidence": c,
                        "class_name": class_name,
                        "color": (0, 0, 255) # Red for potholes
                    })
        except Exception as e:
            print(f"[ERROR] Pothole inference error: {e}")

        # Run Waterlogging Model inference
        if self.dual_mode:
            try:
                res_w = self.model_w(frame, verbose=False, conf=self.CONFIDENCE_THRESHOLD)
                if res_w and len(res_w) > 0 and res_w[0].boxes is not None:
                    boxes = res_w[0].boxes
                    for box, conf, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
                        c = float(conf.item())
                        current_stats["water_conf"] = max(current_stats["water_conf"], c)
                        cls_id = int(cls.item())
                        class_name = res_w[0].names.get(cls_id, "waterlogging")
                        detected_items.append({
                            "engine": "W",
                            "box": [float(v) for v in box],
                            "confidence": c,
                            "class_name": class_name,
                            "color": (255, 180, 0) # Cyan/Blue for waterlogging
                        })
            except Exception as e:
                print(f"[ERROR] Waterlogging inference error: {e}")

        bus_tracks = self.track_history[bus_id]
        matched_track_ids = set()

        # Match detections to existing tracks for this bus
        for item in detected_items:
            best_iou = 0.0
            best_tid = None
            box = item["box"]

            for tid, track in bus_tracks.items():
                if track["class_name"] != item["class_name"]:
                    continue
                iou = calculate_iou(box, track["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

            if best_iou >= 0.20 and best_tid is not None:
                # Update existing track
                bus_tracks[best_tid]["box"] = box
                bus_tracks[best_tid]["confidence"] = max(bus_tracks[best_tid]["confidence"], item["confidence"])
                bus_tracks[best_tid]["hits"] += 1
                bus_tracks[best_tid]["misses"] = 0
                matched_track_ids.add(best_tid)
                assigned_tid = best_tid
            else:
                # Create new track
                tid_num = self.next_track_id[bus_id]
                self.next_track_id[bus_id] += 1
                assigned_tid = f"{item['engine']}_{tid_num}"
                bus_tracks[assigned_tid] = {
                    "box": box,
                    "confidence": item["confidence"],
                    "class_name": item["class_name"],
                    "hits": 1,
                    "misses": 0,
                    "synced": False
                }
                matched_track_ids.add(assigned_tid)

            # Check for temporal consensus confirmation
            tr = bus_tracks[assigned_tid]
            if tr["hits"] >= self.TEMPORAL_HITS_REQUIRED and not tr["synced"]:
                confirmed_events.append({
                    "event_type": tr["class_name"],
                    "confidence": tr["confidence"],
                    "track_id": assigned_tid
                })
                tr["synced"] = True

            # Draw bounding box and crisp HUD label on frame
            x1, y1, x2, y2 = map(int, box)
            color = item["color"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label_text = f"{item['class_name'].upper()} {item['confidence']:.2f} [ID:{assigned_tid}]"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, max(th + 8, y1)), color, -1)
            cv2.putText(frame, label_text, (x1 + 3, max(th + 3, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        # Decay tracks not matched in this frame
        dead_tracks = []
        for tid, track in bus_tracks.items():
            if tid not in matched_track_ids:
                track["misses"] += 1
                if track["misses"] > self.MAX_MISSED_FRAMES:
                    dead_tracks.append(tid)

        for tid in dead_tracks:
            del bus_tracks[tid]

        return confirmed_events, frame, current_stats
