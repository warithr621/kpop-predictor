# K-pop Release Prediction Project

The goal of this project is to use historical data scraped from MusicBrainz API to build a model that can forecast future K-pop releases for top 4th and 5th gen groups. All data is updated as of May 11, 2026.

## Local Test Instructions

Install the necessary dependencies:
```bash
pip install -r requirements.txt
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