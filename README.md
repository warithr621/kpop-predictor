# K-pop Release Prediction Project

This project is (very much) a work in progress. However, the eventual goal is to use historical data scraped from MusicBrainz API to build a model that can forecast future k-pop releases.

## Local Test Instructions

Install the necessary dependencies:
```bash
pip install fastapi uvicorn pandas lightgbm scikit-learn numpy pydantic python-dateutil
```

Run the backend:
```bash
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Run the frontend:
```bash
cd frontend
npm install
npm run dev
```