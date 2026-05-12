# K-pop Release Prediction Project

The goal of this project is to use historical data scraped from MusicBrainz API to build a model that can forecast future K-pop releases. All data is updated as of May 11, 2026. Across top 4th and 5th gen groups, the model has a median error under 6 weeks for 75% of groups, and a prediction accuracy of 86% within a 12-week window.

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