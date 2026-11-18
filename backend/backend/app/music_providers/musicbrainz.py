"""MusicBrainz adapter. METADATA ONLY: no audio, all rights denied."""
from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import settings
from app.models.track import Rights, Track
from app.music_providers.base import MusicProvider, ProviderError

API = "https://musicbrainz.org/ws/2"
_lock = asyncio.Lock()
_last_call = 0.0


def parse_recording(raw: dict) -> Track:
    mbid = raw["id"]
    credit = raw.get("artist-credit") or []
    artist = "".join(c.get("name", "") + c.get("joinphrase", "") for c in credit) or "Unknown artist"
    rel = (raw.get("releases") or [{}])[0]
    length = raw.get("length")
    return Track(
        id=f"musicbrainz:{mbid}",
        provider="musicbrainz",
        provider_track_id=mbid,
        title=raw.get("title") or "Untitled",
        artist=artist,
        album=rel.get("title"),
        duration_sec=round(length / 1000) if length else None,
        musicbrainz_id=mbid,
        genres=[t["name"].lower() for t in raw.get("tags", []) if t.get("name")],
        rights=Rights(),  # metadata only
    )


class MusicBrainzProvider(MusicProvider):
    name = "musicbrainz"
    supplies_audio = False

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    def configured(self) -> bool:
        return True  # no key required, only a descriptive User-Agent

    def note(self) -> str:
        return "Metadata only. Never returns playable audio."

    async def _throttle(self) -> None:
        global _last_call
        async with _lock:  # MusicBrainz asks for max 1 request/second
            wait = 1.05 - (time.monotonic() - _last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call = time.monotonic()

    async def search(self, query="", *, language=None, genres=None, limit=20):
        if not query:
            return []
        await self._throttle()
        params = {"query": query, "fmt": "json", "limit": max(1, min(limit, 100))}
        headers = {"User-Agent": settings.MUSICBRAINZ_USER_AGENT}
        try:
            if self._client:
                r = await self._client.get(f"{API}/recording", params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{API}/recording", params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"MusicBrainz request failed: {exc}") from exc
        return [parse_recording(x) for x in data.get("recordings", []) if x.get("id")]
