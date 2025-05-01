#!/bin/bash
# Load environment variables from .env and run web_stream.py

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

python3 web_stream.py
