#!/usr/bin/env bash
cd "$(dirname "$0")"
(cd backend/backend && [ -d .venv ] || (python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt))
(cd backend/backend && . .venv/bin/activate && uvicorn app.main:app --port 8765 --reload) &
cd frontend/frontend && [ -d node_modules ] || npm install
npm run dev
