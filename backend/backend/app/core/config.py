import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


def _csv(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


class Settings:
    APP_NAME = os.getenv("APP_NAME", "ROVE")
    APP_ENV = os.getenv("APP_ENV", "development")
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "8765"))
    CORS_ORIGINS = _csv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    # Optional. Only needed for HS256 (legacy) projects; modern projects use JWKS.
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
    # Optional. Never sent to the browser. Only needed for admin invite creation.
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    YOUTUBE_API_BASE = os.getenv("YOUTUBE_API_BASE", "https://www.googleapis.com/youtube/v3")  # override only for local tests
    VYBE_API_KEY = os.getenv("VYBE_API_KEY", "")
    JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
    MUSICBRAINZ_USER_AGENT = os.getenv(
        "MUSICBRAINZ_USER_AGENT", "ROVE/0.1.0 (private development app)"
    )

    CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    CLOUDFLARE_R2_ACCESS_KEY_ID = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "")
    CLOUDFLARE_R2_SECRET_ACCESS_KEY = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "")
    CLOUDFLARE_R2_BUCKET_NAME = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "")

    # Test harness only (requires APP_ENV=test): one extra trusted loopback audio host.
    TEST_AUDIO_HOST = os.getenv("TEST_AUDIO_HOST", "")

    # Cap on audio the analyser will download (bytes).
    ANALYSIS_MAX_BYTES = int(os.getenv("ANALYSIS_MAX_BYTES", str(25 * 1024 * 1024)))


settings = Settings()
