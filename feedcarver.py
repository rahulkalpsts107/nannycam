import datetime
import logging
import os
import queue
import threading
import time

import cv2
import numpy as np
from flask import Flask, Response, render_template_string, send_from_directory
from pyngrok import ngrok

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PORT = "4747"
RECORDINGS_DIR = "/Users/Rahul/recordings"
VIDEO_FORMAT = "avc1"  # H.264 codec
VIDEO_EXTENSIONS = {"avc1": ".mp4"}  # MP4 container
VIDEO_WIDTH = 1280  # Increased from 640
VIDEO_HEIGHT = 720  # Increased from 480
VIDEO_FPS = 60.0  # Match iPhone DroidCam settings
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
DISPLAY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
FILENAME_PREFIX = "droidcam"
WINDOW_TITLE = "Droidcam Stream"
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
    <title>Anvi Nanny Cam</title>
    <style>
        body { 
            margin: 0;
            padding: 0;
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #2c3e50;
        }
        .header {
            text-align: center;
            padding: 30px 20px;
            color: white;
        }
        .header h1 {
            font-size: 2.5em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            opacity: 0.9;
            margin: 10px 0;
            font-size: 1.1em;
        }
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .panel {
            width: 100%;
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            margin-bottom: 30px;
            text-align: center;
        }
        #live-panel {
            aspect-ratio: 16/9;  /* Match iPhone camera ratio */
            width: 100%;
            max-width: 1440px;
            background: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        #live-stream {
            width: 100%;
            height: 100%;
            object-fit: contain;  /* This preserves aspect ratio */
            display: block;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: white;
            margin-top: 40px;
        }
        .footer a {
            color: white;
            text-decoration: none;
            opacity: 0.8;
            transition: opacity 0.2s;
        }
        .footer a:hover {
            opacity: 1;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: white;
            border-radius: 8px;
            cursor: pointer;
        }
        .tab.active {
            background: #2c3e50;
            color: white;
        }
        .recordings-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .recording-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .recording-item:hover {
            transform: translateY(-2px);
        }
        .recording-info {
            flex: 1;
        }
        .play-btn {
            padding: 8px 16px;
            background: #2c3e50;
            color: white;
            border: none;
            border-radius: 4px;
        }
        #videoModal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
        }
        .modal-content {
            position: relative;
            width: 90%;
            max-width: 1280px;
            margin: 40px auto;
        }
        .modal-video {
            width: 100%;
            height: auto;
            max-height: 90vh;
            object-fit: contain;  /* Changed from default to contain */
            border-radius: 8px;
            background: #000;  /* Added black background */
        }
        .close-btn {
            position: absolute;
            right: -40px;
            top: 0;
            color: white;
            font-size: 30px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Anvi Nanny Cam</h1>
        <p>Keeping our little angel safe and sound</p>
    </div>

    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="showPanel('live')">Live Stream</div>
            <div class="tab" onclick="showPanel('recordings')">Recordings</div>
        </div>
        
        <div id="live-panel" class="panel">
            <img id="live-stream" src="{{ url_for('video_feed') }}" alt="Live Stream">
        </div>

        <div id="recordings-panel" class="panel" style="display:none">
            <div id="recordings-list" class="recordings-list"></div>
        </div>
    </div>

    <div class="footer">
        <p>Powered by <a href="https://anvi.io" target="_blank">Anvi.io</a> | Made with ❤️ for Anvi</p>
    </div>

    <div id="videoModal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal()">&times;</span>
            <video id="modalVideo" class="modal-video" controls>
                <source src="" type="video/mp4">
            </video>
        </div>
    </div>

    <script>
        function showPanel(id) {
            document.querySelectorAll('.tab').forEach(tab => 
                tab.classList.toggle('active', tab.textContent.toLowerCase().includes(id)));
            document.getElementById('live-panel').style.display = id === 'live' ? 'block' : 'none';
            document.getElementById('recordings-panel').style.display = id === 'recordings' ? 'block' : 'none';
            
            if (id === 'recordings') {
                loadRecordings();
            }
        }

        function loadRecordings() {
            fetch('/recordings')
                .then(response => response.json())
                .then(data => {
                    const list = document.getElementById('recordings-list');
                    list.innerHTML = data.recordings.map(rec => `
                        <div class="recording-item">
                            <div class="recording-info">
                                <div><strong>${rec.filename}</strong></div>
                                <div>Recorded: ${rec.date}</div>
                                <div>Size: ${rec.duration}</div>
                            </div>
                            <button class="play-btn" onclick="playVideo('/recording/${rec.filename}')">Play</button>
                        </div>
                    `).join('');
                });
        }

        function playVideo(url) {
            const modal = document.getElementById('videoModal');
            const video = document.getElementById('modalVideo');
            video.querySelector('source').src = url;
            video.load();
            modal.style.display = 'block';
            video.play().catch(e => console.error('Error playing video:', e));
        }

        function closeModal() {
            const modal = document.getElementById('videoModal');
            const video = document.getElementById('modalVideo');
            video.pause();
            video.querySelector('source').src = '';
            video.load();
            modal.style.display = 'none';
        }

        // Close modal on outside click
        document.getElementById('videoModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    </script>
</body>
</html>
"""


class OBICamRecorder:
    def __init__(
        self,
        ip_address,
        port=DEFAULT_PORT,
        username=None,
        password=None,
        recording_duration=DEFAULT_RECORDING_DURATION,
        show_window=False,
    ):
        # Initialize basic attributes first
        self.ip_address = ip_address
        self.port = port
        self.recording_duration = recording_duration
        self.show_window = show_window

        # Initialize recording attributes
        self.current_output = None
        self.current_filename = None
        self.recording_start_time = None
        self.width = None
        self.height = None
        self.fps = None

        # Initialize camera connection
        self.stream_url = f"http://{ip_address}:{port}/video"
        self.cap = cv2.VideoCapture(self.stream_url)

        if not self.cap.isOpened():
            raise ConnectionError("Failed to open camera stream")

        # Configure camera properties
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        self.cap.set(cv2.CAP_PROP_FPS, 60)  # Set to 60 FPS explicitly
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        # Get actual dimensions from camera
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Camera dimensions: {self.width}x{self.height}")

        # Use native camera dimensions instead of forcing our own
        global VIDEO_WIDTH, VIDEO_HEIGHT
        VIDEO_WIDTH = self.width
        VIDEO_HEIGHT = self.height

        # Validate stream last
        if not self._validate_stream():
            raise ConnectionError("Failed to initialize valid video stream")

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
                logger.error(f"Stream validation error (attempt {attempt + 1}): {e}")
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
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            return self._validate_stream()
        return False

    def create_new_recording(self):
        try:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR)

            self.close_recording()
            timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
            filename = f"{RECORDINGS_DIR}/{FILENAME_PREFIX}_{timestamp}.mp4"

            logger.info(f"Creating recording file: {filename}")

            # Force 60 FPS to match iPhone settings
            target_fps = 60.0
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            new_output = cv2.VideoWriter(
                filename,
                fourcc,
                target_fps,  # Force 60 FPS
                (self.width, self.height),
                True
            )

            if not new_output.isOpened():
                raise RuntimeError(f"VideoWriter failed to open with codec {VIDEO_FORMAT}")

            logger.info(f"Recording at {target_fps} FPS with dimensions {self.width}x{self.height}")
            self.current_output = new_output
            self.current_filename = filename
            self.recording_start_time = time.time()
            return True

        except Exception as e:
            logger.error(f"Recording error: {str(e)}")
            if "new_output" in locals():
                new_output.release()
            self.current_output = None
            return False

    def close_recording(self):
        """Safely close current recording"""
        if self.current_output is not None:
            logger.info("Finalizing recording...")
            self.current_output.release()
            self.current_output = None

        if self.cap is not None:
            self.cap.release()

    def __del__(self):
        """Ensure proper cleanup on deletion"""
        self.close_recording()

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
                    cv2.putText(
                        frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                    )
                    cv2.imshow(WINDOW_TITLE, frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        finally:
            self.close_recording()
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
        self._cleanup_recordings()  # Initial cleanup

        # Add root route
        @self.app.route("/video_feed")
        def video_feed():
            return self.video_feed()

    def _cleanup_recordings(self):
        """Delete recordings older than 10 days"""
        try:
            now = time.time()
            max_age = 10 * 24 * 60 * 60  # 10 days in seconds
            
            for file in os.listdir(RECORDINGS_DIR):
                if file.endswith(".mp4"):
                    filepath = os.path.join(RECORDINGS_DIR, file)
                    file_age = now - os.path.getmtime(filepath)
                    
                    if file_age > max_age:
                        try:
                            os.remove(filepath)
                            logger.info(f"Deleted old recording: {file}")
                        except OSError as e:
                            logger.error(f"Error deleting {file}: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

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
        cleanup_interval = 3600  # Run cleanup every hour
        last_cleanup = time.time()

        while self._running:
            try:
                if not self._connection_healthy:
                    if not self._check_connection_health():
                        time.sleep(1)
                        continue

                ret, frame = self.recorder.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    logger.error(
                        f"Failed to read frame (attempt {consecutive_failures}/{max_failures})"
                    )

                    if consecutive_failures >= max_failures:
                        self._connection_healthy = False
                        consecutive_failures = 0
                    time.sleep(0.1)
                    continue

                # Handle recording
                if self._recording_enabled:
                    current_time = time.time()
                    if current_time - recording_start_time >= self.recorder.recording_duration:
                        if not self.recorder.create_new_recording():
                            logger.error("Failed to create new recording, disabling recording")
                            self._recording_enabled = False
                        else:
                            recording_start_time = current_time

                    if (
                        self.recorder.current_output is not None
                        and self.recorder.current_output.isOpened()
                    ):
                        try:
                            self.recorder.current_output.write(frame)
                        except Exception as e:
                            logger.error(f"Failed to write frame: {e}")
                            self._recording_enabled = False
                            self.recorder.close_recording()

                # Run periodic cleanup
                current_time = time.time()
                if current_time - last_cleanup > cleanup_interval:
                    self._cleanup_recordings()
                    last_cleanup = current_time

                # Continue with streaming
                consecutive_failures = 0
                self._last_frame_time = time.time()
                frame_copy = frame.copy()
                # Increase JPEG quality for better stream clarity
                ret, buffer = cv2.imencode(".jpg", frame_copy, [cv2.IMWRITE_JPEG_QUALITY, 95])
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

        yield b"--FRAME\r\n"

        while True:
            try:
                frame_data = self._frame_buffer.get(timeout=5.0)
                yield b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n--FRAME\r\n"

            except queue.Empty:
                logger.warning("Frame buffer empty, sending blank frame...")
                blank_frame = np.zeros((480, 640, 3), np.uint8)
                _, buffer = cv2.imencode(".jpg", blank_frame)
                yield b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n--FRAME\r\n"

            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                time.sleep(0.1)

    def video_feed(self):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
        }
        return Response(
            self.generate_frames(),
            mimetype="multipart/x-mixed-replace; boundary=FRAME",
            headers=headers,
        )

    def __del__(self):
        self._running = False
        if self._recording_enabled and hasattr(self.recorder, "current_output"):
            self.recorder.current_output.release()
        if hasattr(self, "_capture_thread"):
            self._capture_thread.join(timeout=1.0)
        self._current_frame = None
        if hasattr(self, "recorder") and self.recorder:
            self.recorder.cap.release()

    def start(self):
        try:
            if not self._capture_thread.is_alive():
                self._capture_thread.start()
                time.sleep(1)

            if self.use_ngrok:
                self.public_url = ngrok.connect(FLASK_PORT).public_url
            logger.info(f"Stream available at: {self.public_url}")

            @self.app.route("/")
            def index():
                return render_template_string(HTML_TEMPLATE, stream_url=self.public_url)

            @self.app.route("/recordings")
            def list_recordings():
                recordings = []
                for file in os.listdir(RECORDINGS_DIR):
                    if file.endswith(".mp4"):
                        path = os.path.join(RECORDINGS_DIR, file)
                        stat = os.stat(path)
                        recordings.append({
                            "filename": file,
                            "date": datetime.datetime.fromtimestamp(stat.st_mtime).strftime(DISPLAY_TIMESTAMP_FORMAT),
                            "duration": f"{stat.st_size / (1024*1024):.1f} MB"
                        })
                result = {"recordings": sorted(recordings, key=lambda x: x["date"], reverse=True)}
                logger.info(f"Found {len(recordings)} recordings")
                return result

            @self.app.route("/recording/<path:filename>")
            def serve_recording(filename):
                logger.info(f"Requested video: {filename}")
                try:
                    filepath = os.path.join(RECORDINGS_DIR, filename)
                    if not os.path.exists(filepath):
                        logger.error(f"File not found: {filepath}")
                        return "File not found", 404
                        
                    response = send_from_directory(RECORDINGS_DIR, filename)
                    response.headers.update({
                        'Content-Type': 'video/mp4',
                        'Accept-Ranges': 'bytes',
                        'Cache-Control': 'no-cache'
                    })
                    logger.info(f"Serving video: {filename} ({response.content_length} bytes)")
                    return response
                except Exception as e:
                    logger.error(f"Error serving video: {str(e)}")
                    return str(e), 500

            # Start the Flask server
            threading.Thread(
                target=lambda: self.app.run(
                    host="0.0.0.0", 
                    port=FLASK_PORT,
                    debug=False,
                    use_reloader=False,
                    threaded=True
                )
            ).start()

        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}")
            raise
