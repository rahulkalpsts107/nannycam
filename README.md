# NannyCam

A simple nanny camera streaming and recording server built with Python, Flask, and OpenCV. It streams live video from an IP camera, records video segments, and provides a web interface to view the live stream and past recordings.

## Features
- Live video streaming from an IP camera (e.g., DroidCam)
- Automatic video recording in segments
- Web interface to view live stream and recordings
- Recordings auto-cleaned after 10 days
- Environment variable support for sensitive configuration

## Requirements
- Python 3.8+
- macOS (tested), should work on Linux/Windows
- IP camera or DroidCam app

## Installation
1. Clone this repository:
   ```sh
   git clone <your-repo-url>
   cd nannycam
   ```
2. (Optional) Create and activate a virtual environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Configuration
Create a `.env` file in the project root with the following content:
```
PUBLIC_URL=http://your-public-url:8000
RECORDINGS_DIR=/path/to/recordings
FLASK_PORT=0000
LOG_FILE=nannycam.log
DROIDCAM_IP_ADDRESS=x.x.x.x
DROIDCAM_PORT=0000
```
- `PUBLIC_URL`: The URL where your stream will be accessible (default: http://localhost:8000)
- `RECORDINGS_DIR`: Directory to store video recordings (default: /recordings)
- `FLASK_PORT`: Port for the Flask server (default: 8000)
- `LOG_FILE`: File to store server logs (default: nannycam.log)
- `DROIDCAM_IP_ADDRESS`: The IP address of your camera (default: 192.168.1.129)
- `DROIDCAM_PORT`: The port of your camera stream (default: 4747)

## Usage
To start the server, run:
```sh
./run_nannycam.sh
```
This script loads environment variables from `.env` and launches the server.

Visit `http://localhost:8000` (or your `PUBLIC_URL`) in your browser to view the live stream and recordings.

## Notes
- Make sure your IP camera is accessible and the IP address/port is set correctly in `web_stream.py`.
- The `.env` file is ignored by git for security.
- Recordings older than 10 days are deleted automatically.

## Troubleshooting
- If you see `ModuleNotFoundError: No module named 'dotenv'`, run `pip install -r requirements.txt`.
- Ensure your camera stream URL is correct and accessible from your server.

## License
MIT
