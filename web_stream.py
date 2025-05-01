import logging
import os
import signal
import time

from feedcarver import OBICamRecorder, StreamingServer

logger = logging.getLogger(__name__)


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
    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initialize camera
    recorder = OBICamRecorder(ip_address="192.168.1.129", port="4747")

    # Initialize and start streaming server - simplified initialization
    server = StreamingServer(recorder)  # Remove use_ngrok parameter
    server.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
