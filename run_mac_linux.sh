#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "*** Edit the .env file and paste your Roboflow API key, then run this again. ***"
  exit 1
fi
echo "Starting API at http://127.0.0.1:8000"
uvicorn main:app --host 127.0.0.1 --port 8000
