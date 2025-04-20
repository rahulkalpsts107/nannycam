from flask import Flask, Response, request, render_template
from flask_basicauth import BasicAuth
import cv2
from feedcarver import OBICamRecorder
import os
from pyngrok import ngrok, conf
import ssl
import certifi
import time
import logging
import queue
import threading

logger = logging.getLogger(__name__)

app = Flask(__name__)

# SSL Context
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Ngrok setup with error handling
def setup_ngrok():
    try:
        # Set default config including SSL certificates
        conf.get_default().config_path = os.path.join(os.path.expanduser('~'), '.ngrok2', 'ngrok.yml')
        conf.get_default().verify_api_cert = True
        conf.get_default().ssl_verify = certifi.where()
        
        # Start ngrok
        public_url = ngrok.connect(5000)
        print(f' * Public URL: {public_url}')
    except Exception as e:
        print(f'Failed to start ngrok: {e}')
        print('Running without public URL')

# Basic Authentication
app.config['BASIC_AUTH_USERNAME'] = os.environ.get('STREAM_USER', 'admin')
app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('STREAM_PASS', 'K@04Ec9303')
app.config['BASIC_AUTH_FORCE'] = True
basic_auth = BasicAuth(app)

# Initialize camera
recorder = OBICamRecorder(
    ip_address="192.168.1.129",  # Your Droidcam IP
    port="4747"
)

class StreamManager:
    def __init__(self, recorder):
        self.recorder = recorder
        self.frame_queue = queue.Queue(maxsize=10)  # Reduced buffer size
        self.is_running = True
        self.last_frame_time = time.time()
        self.stall_timeout = 2.0  # seconds
        self.capture_thread = threading.Thread(target=self._capture_frames)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
    def _check_stall(self):
        if time.time() - self.last_frame_time > self.stall_timeout:
            logger.warning("Stream stalled, reconnecting...")
            self.frame_queue.queue.clear()  # Clear stale frames
            return self.recorder.reconnect()
        return True

    def _capture_frames(self):
        while self.is_running:
            try:
                if not self._check_stall():
                    time.sleep(0.5)
                    continue
                    
                ret, frame = self.recorder.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                # Update frame timestamp
                self.last_frame_time = time.time()
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    # Clear queue if too old
                    while not self.frame_queue.empty() and self.frame_queue.qsize() > 5:
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            break
                            
                    self.frame_queue.put(buffer.tobytes(), block=False)
                    
            except Exception as e:
                logger.error(f"Capture error: {e}")
                time.sleep(0.1)

    def get_frame(self):
        try:
            frame_data = self.frame_queue.get(timeout=0.1)  # Reduced timeout
            return frame_data
        except queue.Empty:
            if not self._check_stall():
                time.sleep(0.1)
            return None

# Initialize stream manager
stream_manager = StreamManager(recorder)

def generate_frames():
    while True:
        frame_data = stream_manager.get_frame()
        if frame_data is not None:
            yield (b'--frame\r\n'
                  b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        else:
            time.sleep(0.1)

@app.route('/')
@basic_auth.required
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Connection': 'keep-alive'
        }
    )

if __name__ == '__main__':
    setup_ngrok()
    app.run(host='0.0.0.0', port=5000, ssl_context=ssl_context)
