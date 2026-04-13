import time
import os
import requests
import cv2
from io import BytesIO
from features.risk_detection.vision_service import analyze_image
from features.risk_detection.storage_service import handle_storage

# Configuration
CAMERA_ID = os.getenv("CAMERA_ID", "CAM_MAIN_001")
LOCATION = os.getenv("CAMERA_LOCATION", "Main Entrance - Gate A")
INTERVAL = 5  # Seconds
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE") # e.g., "path/to/demo_video.mp4" or "0" for webcam

class FrameIngestor:
    def __init__(self, source=None):
        self.source = source
        self.cap = None
        self.fps = 0
        self.is_video_file = False
        self._initialize_source()

    def _initialize_source(self):
        if self.source:
            try:
                # Try to open as an integer (webcam index) or string (path/URL)
                src = int(self.source) if self.source.isdigit() else self.source
                self.cap = cv2.VideoCapture(src)
                if self.cap.isOpened():
                    self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                    # If FPS is 0 or very low, it might be a webcam, otherwise it's likely a file
                    self.is_video_file = self.fps > 0 and not str(self.source).isdigit()
                    print(f"Source initialized: {self.source} (Video File: {self.is_video_file}, FPS: {self.fps})")
                else:
                    print(f"Failed to open source: {self.source}")
                    self.cap = None
            except Exception as e:
                print(f"Error initializing source: {str(e)}")
                self.cap = None

    def capture_frame(self, current_time_offset=0):
        """
        Captures a frame from the initialized source or falls back to mock.
        """
        if self.cap and self.cap.isOpened():
            if self.is_video_file:
                # Seek to the correct timestamp in the video
                frame_idx = int(current_time_offset * self.fps)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            
            ret, frame = self.cap.read()
            if ret:
                # Convert OpenCV BGR to JPEG bytes
                _, buffer = cv2.imencode('.jpg', frame)
                return buffer.tobytes()
            elif self.is_video_file:
                print("End of video reached.")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Loop video
                return self.capture_frame(0)

        # Fallback to Mock / Placeholder
        print("Using Mock Ingestion (Picsum Placeholder)...")
        try:
            response = requests.get("https://picsum.photos/800/600", timeout=10)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"Mock Capture Error: {str(e)}")
        return None

def run_worker():
    print(f"Starting Enhanced Ingestion Worker for {CAMERA_ID} at {LOCATION}...")
    ingestor = FrameIngestor(VIDEO_SOURCE)
    
    current_offset = 0
    try:
        while True:
            start_loop = time.time()
            
            print(f"\n[{time.strftime('%H:%M:%S')}] Pulling frame (Offset: {current_offset}s)...")
            image_bytes = ingestor.capture_frame(current_offset)
            
            if image_bytes:
                print("Analyzing risk level...")
                analysis = analyze_image(image_bytes)
                risk_level = analysis["risk_level"]
                print(f"Detected Risk: {risk_level}")
                
                print("Processing storage...")
                result = handle_storage(
                    image_bytes=image_bytes,
                    risk_level=risk_level,
                    camera_id=CAMERA_ID,
                    location=LOCATION,
                    metadata=analysis
                )
                print(f"Storage successful: {result['storage_path']}")
            
            # Update offset logic for video files
            current_offset += INTERVAL
            
            # Maintain the 5-second interval
            elapsed = time.time() - start_loop
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")
    except Exception as e:
        print(f"Worker Fatal Error: {str(e)}")
    finally:
        if ingestor.cap:
            ingestor.cap.release()

if __name__ == "__main__":
    run_worker()
