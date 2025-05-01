import os
import logging
import datetime

def setup_logging():
    LOG_FILE = os.environ.get("LOG_FILE", "nannycam.log")
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB

    # Rotate log file if it exceeds MAX_LOG_SIZE
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        rotated_name = f"{os.path.splitext(LOG_FILE)[0]}-{dt_str}.log"
        os.rename(LOG_FILE, rotated_name)

    logging.basicConfig(
        level=logging.DEBUG,
        filename=LOG_FILE,
        filemode='a',
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        force=True
    )
    logger = logging.getLogger(__name__)

    for lib in ("werkzeug", "flask", "__main__"):
        logging.getLogger(lib).setLevel(logging.DEBUG)
    return logger
