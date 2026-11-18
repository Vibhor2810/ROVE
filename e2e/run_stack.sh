#!/usr/bin/env bash
# Starts: fake infra (:54321), real backend (:8765), real frontend dev server (:5173)
set -e
cd "$(dirname "$0")"
pkill -f "uvicorn fake_infra" 2>/dev/null || true; pkill -f "uvicorn app.main" 2>/dev/null || true; pkill -f "vite" 2>/dev/null || true
sleep 1
PY=/home/claude/venv/bin/python
nohup $PY -m uvicorn fake_infra:app --port 54321 --log-level warning > /tmp/fake.log 2>&1 &
(cd ../backend/backend && \
  APP_ENV=test SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_ANON_KEY=anon-test SUPABASE_JWT_SECRET= \
  JAMENDO_CLIENT_ID=test JAMENDO_API_BASE=http://127.0.0.1:54321/v3.0 TEST_AUDIO_HOST=127.0.0.1 \
  nohup $PY -m uvicorn app.main:app --port 8765 --log-level info > /tmp/backend.log 2>&1 &)
(cd ../frontend/frontend && \
  VITE_SUPABASE_URL=http://127.0.0.1:54321 VITE_SUPABASE_ANON_KEY=anon-test VITE_API_URL=http://127.0.0.1:8765 \
  nohup npx vite --port 5173 --strictPort > /tmp/vite.log 2>&1 &)
sleep 5
curl -s localhost:8765/health; echo; curl -s localhost:54321/auth/v1/.well-known/jwks.json | head -c 80; echo; curl -s -o /dev/null -w "frontend %{http_code}\n" localhost:5173
