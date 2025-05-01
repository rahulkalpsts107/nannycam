import unittest
import os
import logging
import tempfile
from logutil import setup_logging

class TestLogUtil(unittest.TestCase):
    def test_log_rotation(self):
        # Create a temp log file >10MB
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b'x' * (10 * 1024 * 1024 + 1))
            log_path = tmp.name
        os.environ['LOG_FILE'] = log_path
        logger = setup_logging()
        logger.info('Test log entry')
        # After setup_logging, the file should be truncated/rotated and a new log file created
        self.assertTrue(os.path.exists(log_path))
        self.assertLess(os.path.getsize(log_path), 1024 * 1024)  # Should be small
        # Clean up
        os.remove(log_path)
        # Remove rotated log if exists
        for f in os.listdir(os.path.dirname(log_path)):
            if f.startswith(os.path.splitext(os.path.basename(log_path))[0]) and f.endswith('.log'):
                try:
                    os.remove(os.path.join(os.path.dirname(log_path), f))
                except Exception:
                    pass

if __name__ == '__main__':
    unittest.main()
