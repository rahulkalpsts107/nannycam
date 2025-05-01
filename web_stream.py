import logging
import os
import signal
import time
import datetime  # Add this import
from dotenv import load_dotenv  # Add this import
from logutil import setup_logging

from feedcarver import OBICamRecorder, StreamingServer

# Load environment variables from .env if present
load_dotenv()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000")
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/Users/Rahul/recordings")
LOG_FILE = os.environ.get("LOG_FILE", "nannycam.log")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
DROIDCAM_IP_ADDRESS = os.environ.get("DROIDCAM_IP_ADDRESS", "192.168.1.129")
DROIDCAM_PORT = os.environ.get("DROIDCAM_PORT", "4747")

# Rotate log file if it exceeds MAX_LOG_SIZE
if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
    dt_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    rotated_name = f"{os.path.splitext(LOG_FILE)[0]}-{dt_str}.log"
    os.rename(LOG_FILE, rotated_name)


def handle_shutdown(signum, frame):
    """Handle graceful shutdown"""
    logger.info("Shutdown signal received, closing gracefully...")
    try:
        if "server" in globals() and server is not None:
            server._running = False
            if server.recorder:
                server.recorder.close_recording()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        os._exit(0)


if __name__ == "__main__":
    # Setup logging
    logger = setup_logging()
    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initialize camera
    recorder = OBICamRecorder(ip_address=DROIDCAM_IP_ADDRESS, port=DROIDCAM_PORT)

    # Initialize and start streaming server - simplified initialization
    server = StreamingServer(recorder)  # Remove use_ngrok parameter
    server.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
