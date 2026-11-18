import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, invitations, library, music, playback, playlists
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="RØVE API",
    description="The backend powering RØVE music experiences.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth.router, invitations.router, music.router, playlists.router, playback.router, library.router):
    app.include_router(r)


@app.get("/")
def home():
    return {"app": "RØVE", "message": "Find your frequency.", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy", "backend": "online", "service": "rove-api"}
