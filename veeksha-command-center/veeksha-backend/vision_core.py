import cv2
import numpy as np
from ultralytics import YOLO

class VeekshaVisionEngine:
    def __init__(self, pothole_model="best_16_rebuilt.pt", water_model="waterlogging.pt"):
        print("[INFO] Booting Dual AI Engines (Pothole & Waterlogging)...")
        self.model_p = YOLO(pothole_model)
        
        try:
            self.model_w = YOLO(water_model)
            self.dual_mode = True
            print("[INFO] Both Pothole and Waterlogging models loaded!")
        except Exception as e:
            print(f"[WARN] {water_model} not found or error. Running single engine. Error: {e}")
            self.dual_mode = False

        # Nested dictionary: { "BUS_ID": { "track_id": {"hits": 1, "synced": False} } }
        self.track_history = {}
        self.TEMPORAL_HITS_REQUIRED = 3
        print("[INFO] Dual Vision Core Online & Ready for Multi-Fleet!")

    def preprocess(self, frame):
        return cv2.resize(frame, (640, 480))

    def process_frame(self, frame_bytes, bus_id):
        # Nayi bus aaye toh uski alag memory banao
        if bus_id not in self.track_history:
            self.track_history[bus_id] = {}

        np_arr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        frame = self.preprocess(frame)

        current_frame_ids = []
        confirmed_events = []
        current_stats = {"pothole_conf": 0.0, "water_conf": 0.0}

        def extract_and_draw(results, engine_code, color):
            if results[0].boxes.id is not None:
                boxes = results[0].boxes
                for box, track_id, conf, cls in zip(boxes.xyxy, boxes.id, boxes.conf, boxes.cls):
                    tid = f"{engine_code}_{int(track_id.item())}" 
                    confidence = float(conf.item())
                    class_name = results[0].names[int(cls.item())]
                    
                    if engine_code == 'P':
                        current_stats["pothole_conf"] = max(current_stats["pothole_conf"], confidence)
                    elif engine_code == 'W':
                        current_stats["water_conf"] = max(current_stats["water_conf"], confidence)
                    
                    current_frame_ids.append(tid)

                    # Update logic strictly for THIS specific bus
                    if tid not in self.track_history[bus_id]:
                        self.track_history[bus_id][tid] = {"hits": 1, "synced": False}
                    else:
                        self.track_history[bus_id][tid]["hits"] += 1

                    if self.track_history[bus_id][tid]["hits"] >= self.TEMPORAL_HITS_REQUIRED and not self.track_history[bus_id][tid]["synced"]:
                        confirmed_events.append({
                            "event_type": class_name,
                            "confidence": confidence,
                            "track_id": tid
                        })
                        self.track_history[bus_id][tid]["synced"] = True

                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{class_name} {confidence:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Basic Tracking logic without global persist collision
        res_p = self.model_p.track(frame, persist=False, verbose=False) 
        extract_and_draw(res_p, 'P', (0, 0, 255)) 

        if self.dual_mode:
            res_w = self.model_w.track(frame, persist=False, verbose=False)
            extract_and_draw(res_w, 'W', (255, 0, 0)) 

        # Cleanup lost tracks FOR THIS BUS ONLY
        for k in list(self.track_history[bus_id].keys()):
            if k not in current_frame_ids:
                self.track_history[bus_id][k]["hits"] = max(0, self.track_history[bus_id][k]["hits"] - 1)
                if self.track_history[bus_id][k]["hits"] <= 0:
                    del self.track_history[bus_id][k]

        return confirmed_events, frame, current_stats