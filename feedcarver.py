import cv2
import datetime
import os
import time
import logging
from flask import Flask, Response, render_template_string
from pyngrok import ngrok
import threading
import queue
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PORT = "4747"
RECORDINGS_DIR = '/Users/Rahul/recordings'
VIDEO_FORMAT = 'avc1'  # Changed from mp4v for macOS compatibility
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
DISPLAY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
FILENAME_PREFIX = "droidcam"
WINDOW_TITLE = 'Droidcam Stream'
DEFAULT_RECORDING_DURATION = 3600  # 1 hour in seconds
FLASK_PORT = 8000  # Changed from 5000
FLASK_PORT_FALLBACK = 8080  # Fallback port if primary is in use
NGROK_AUTH_TOKEN = "2vzWj2vkowo5gKH4v76TzvfKZs0_6MXA3sk8otnHKzPyL4v2B"
PUBLIC_IP = "infinite-cunning-eagle.ngrok-free.app"  # Add your public IP here
USE_NGROK = False  # Set to False to use public IP instead

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Nanny Cam Stream</title>
    <style>
        body { text-align: center; padding: 20px; }
        h1 { color: #333; }
        .url-info { margin: 20px; padding: 10px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Live Stream</h1>
    <div class="url-info">
        <p>Stream URL: <a href="{{ stream_url }}" target="_blank">{{ stream_url }}</a></p>
    </div>
    <img src="{{ url_for('video_feed') }}" width="640" height="480">
</body>
</html>
"""

class OBICamRecorder:
    def __init__(self, ip_address, port=DEFAULT_PORT, username=None, password=None, 
                 recording_duration=DEFAULT_RECORDING_DURATION, show_window=False):
        self.stream_url = f"http://{ip_address}:{port}/video"
        self.cap = cv2.VideoCapture(self.stream_url)
        
        # Set buffer size and timeouts
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        self.cap.set(cv2.CAP_PROP_FPS, 30)  # Force 30fps
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        
        # Validate stream
        if not self._validate_stream():
            raise ConnectionError("Failed to initialize valid video stream")
        
        self.recording_duration = recording_duration
        self.current_output = None
        self.recording_start_time = None
        self.ip_address = ip_address
        self.port = port
        self.show_window = show_window
        
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        
    def _validate_stream(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Read test frame to validate stream
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    return True
                self.cap.release()
                time.sleep(1)
                self.cap = cv2.VideoCapture(self.stream_url)
            except Exception as e:
                logger.error(f"Stream validation error (attempt {attempt+1}): {e}")
                time.sleep(1)
        return False

    def reconnect(self):
        logger.info("Attempting to reconnect to camera...")
        self.cap.release()
        time.sleep(0.5)  # Add delay before reconnect
        self.cap = cv2.VideoCapture(self.stream_url)
        
        # Reset capture properties
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            return self._validate_stream()
        return False

    def create_new_recording(self):
        if not os.path.exists(RECORDINGS_DIR):
            os.makedirs(RECORDINGS_DIR)
            
        timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
        filename = f"{RECORDINGS_DIR}/{FILENAME_PREFIX}_{timestamp}.mp4"
        
        if self.current_output is not None:
            self.current_output.release()
            
        fourcc = cv2.VideoWriter_fourcc(*VIDEO_FORMAT)
        self.current_output = cv2.VideoWriter(filename, fourcc, self.fps, 
                                            (self.width, self.height))
        self.recording_start_time = time.time()
        print(f"Started new recording: {filename}")
        
    def close_recording(self):
        """Safely close current recording and release resources"""
        logger.info("Closing recording...")
        if self.current_output is not None:
            self.current_output.release()
            self.current_output = None
        if self.cap is not None:
            self.cap.release()
            
    def run(self):
        try:
            self.create_new_recording()
            
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break
                    
                current_time = time.time()
                elapsed_time = current_time - self.recording_start_time
                
                if elapsed_time >= self.recording_duration:
                    self.create_new_recording()
                
                self.current_output.write(frame)
                
                if self.show_window:
                    timestamp = datetime.datetime.now().strftime(DISPLAY_TIMESTAMP_FORMAT)
                    cv2.putText(frame, timestamp, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow(WINDOW_TITLE, frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                        
        finally:
            self.cap.release()
            if self.current_output is not None:
                self.current_output.release()
            if self.show_window:
                cv2.destroyAllWindows()

class StreamingServer:
    def __init__(self, recorder, use_ngrok=USE_NGROK):
        self.use_ngrok = use_ngrok
        if self.use_ngrok:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
        else:
            self.public_url = f"https://{PUBLIC_IP}"  # Use configured public URL
            logger.info(f"Using public URL: {self.public_url}")
        self.app = Flask(__name__)
        self.recorder = recorder
        self.frame_count = 0
        self._frame_lock = threading.Lock()
        self._frame_buffer = queue.Queue(maxsize=30)  # Buffer 30 frames
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_frames)
        self._capture_thread.daemon = True
        self._last_frame_time = time.time()
        self._connection_healthy = True
        self._reconnect_timeout = 5  # seconds
        self._recording_enabled = True
        if self._recording_enabled:
            self.recorder.create_new_recording()

        # Add root route
        @self.app.route('/video_feed')
        def video_feed():
            return self.video_feed()

    def _check_connection_health(self):
        if time.time() - self._last_frame_time > self._reconnect_timeout:
            self._connection_healthy = False
            if self.recorder.reconnect():
                self._connection_healthy = True
                self._last_frame_time = time.time()
                logger.info("Successfully reconnected to camera")
                return True
            return False
        return True

    def _capture_frames(self):
        consecutive_failures = 0
        max_failures = 3
        recording_start_time = time.time()
        
        while self._running:
            try:
                if not self._connection_healthy:
                    if not self._check_connection_health():
                        time.sleep(1)
                        continue

                ret, frame = self.recorder.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    logger.error(f"Failed to read frame (attempt {consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        self._connection_healthy = False
                        consecutive_failures = 0
                    time.sleep(0.1)
                    continue

                # Handle recording
                if self._recording_enabled:
                    current_time = time.time()
                    if current_time - recording_start_time >= self.recorder.recording_duration:
                        self.recorder.create_new_recording()
                        recording_start_time = current_time
                    self.recorder.current_output.write(frame)

                # Continue with streaming
                consecutive_failures = 0
                self._last_frame_time = time.time()
                frame_copy = frame.copy()
                ret, buffer = cv2.imencode('.jpg', frame_copy, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    self._frame_buffer.put(buffer.tobytes(), block=False)

            except queue.Full:
                continue
            except Exception as e:
                logger.error(f"Capture error: {str(e)}")
                self._connection_healthy = False
                time.sleep(0.1)

    def generate_frames(self):
        if not self._capture_thread.is_alive():
            self._capture_thread.start()

        yield b'--FRAME\r\n'

        while True:
            try:
                frame_data = self._frame_buffer.get(timeout=5.0)
                yield b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n--FRAME\r\n'
                
            except queue.Empty:
                logger.warning("Frame buffer empty, sending blank frame...")
                blank_frame = np.zeros((480, 640, 3), np.uint8)
                _, buffer = cv2.imencode('.jpg', blank_frame)
                yield b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n--FRAME\r\n'
                
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                time.sleep(0.1)

    def video_feed(self):
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Connection': 'keep-alive'
        }
        return Response(
            self.generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=FRAME',
            headers=headers
        )

    def __del__(self):
        self._running = False
        if self._recording_enabled and hasattr(self.recorder, 'current_output'):
            self.recorder.current_output.release()
        if hasattr(self, '_capture_thread'):
            self._capture_thread.join(timeout=1.0)
        self._current_frame = None
        if hasattr(self, 'recorder') and self.recorder:
            self.recorder.cap.release()

    def start(self):
        try:
            if not self._capture_thread.is_alive():
                self._capture_thread.start()
                time.sleep(1)

            if self.use_ngrok:
                self.public_url = ngrok.connect(FLASK_PORT).public_url
            
            logger.info(f"Stream available at: {self.public_url}")
            
            @self.app.route('/')
            def index():
                return render_template_string(HTML_TEMPLATE, 
                                           stream_url=self.public_url)
            
            @self.app.route('/url')
            def get_url():
                return {'url': self.public_url}
            
            threading.Thread(target=lambda: self.app.run(
                host='0.0.0.0', 
                port=FLASK_PORT, 
                debug=False, 
                use_reloader=False,
                threaded=True
            )).start()
            
        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}")
            raise