import unittest
from unittest.mock import patch, MagicMock
from feedcarver import OBICamRecorder

class TestOBICamRecorder(unittest.TestCase):
    @patch('cv2.VideoCapture')
    def test_init_success(self, mock_vc):
        # Mock VideoCapture to simulate a working camera
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, MagicMock())
        mock_cap.get.side_effect = lambda x: 640 if x == 3 else 480  # width/height
        mock_vc.return_value = mock_cap
        with patch.object(OBICamRecorder, '_validate_stream', return_value=True):
            recorder = OBICamRecorder(ip_address='127.0.0.1', port='4747')
            self.assertEqual(recorder.width, 640)
            self.assertEqual(recorder.height, 480)
            self.assertTrue(recorder.cap.isOpened())

    @patch('cv2.VideoCapture')
    def test_init_fail(self, mock_vc):
        # Simulate camera not opening
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc.return_value = mock_cap
        with self.assertRaises(ConnectionError):
            OBICamRecorder(ip_address='127.0.0.1', port='4747')

if __name__ == '__main__':
    unittest.main()
