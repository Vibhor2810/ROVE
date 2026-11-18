"""Jamendo adapter (https://developer.jamendo.com/v3.0).

Jamendo supplies Creative-Commons licensed music with stream URLs. Rights are
derived from each track's own license URL, conservatively:

* ND (NoDerivatives) licences => no crossfade / DJ transition / segment play.
* Public performance and mixtape sharing are always denied here; Jamendo
  handles commercial/public use through a separate licensing programme.
* Jamendo's API terms cover non-commercial use for free. Whether a private
  invite-only app counts is for you to confirm with Jamendo.
"""
from __future__ import annotations

import os
import re

import httpx

from app.core.config import settings
from app.models.track import Rights, Track
from app.music_providers.base import MusicProvider, ProviderError, ProviderNotConfigured

API = os.getenv("JAMENDO_API_BASE", "https://api.jamendo.com/v3.0")  # override only for local tests
_SPEED_TO_ENERGY = {"verylow": 0.1, "low": 0.3, "medium": 0.5, "high": 0.75, "veryhigh": 0.9}
_LANG_CODES = {
    "hindi": "hi", "punjabi": "pa", "english": "en", "tamil / telugu": "ta",
    "tamil": "ta", "telugu": "te", "garba / gujarati": "gu", "gujarati": "gu",
}


# UI genre label -> Jamendo tag. Labels with no real Jamendo tag are dropped
# rather than sent as a made-up tag (which would silently return nothing).
_GENRE_TAGS = {
    "dance": "dance", "pop": "pop", "rock": "rock", "electronic": "electronic",
    "hip-hop": "hiphop", "desi hip-hop": "hiphop", "romantic": "lounge",
    "folk": "folk", "sufi": "world", "melody": "pop", "retro": "oldies",
    "party": "dance", "wedding": "world", "garba": "world",
}


def map_genres(labels: list[str] | None) -> list[str]:
    out: list[str] = []
    for label in labels or []:
        tag = _GENRE_TAGS.get(label.strip().lower())
        if tag and tag not in out:
            out.append(tag)
    return out


def license_slug(url: str | None) -> str | None:
    m = re.search(r"/licenses/([a-z\-]+)/", url or "")
    return m.group(1) if m else None


def rights_for_license(slug: str | None, *, has_audio: bool) -> Rights:
    if not slug or not has_audio:
        return Rights()  # unknown => denied
    no_derivs = "nd" in slug.split("-")
    return Rights(
        full_playback=True,
        seek_playback=True,
        crossfade=not no_derivs,
        segment_playback=not no_derivs,
        dj_transition=not no_derivs,
        mixtape_sharing=False,
        public_performance=False,
    )


def parse_track(raw: dict) -> Track:
    tid = str(raw["id"])
    audio = raw.get("audio") or None
    slug = license_slug(raw.get("license_ccurl"))
    info = raw.get("musicinfo") or {}
    tags = info.get("tags") or {}
    speed = info.get("speed")
    energy = _SPEED_TO_ENERGY.get(speed) if speed else None
    return Track(
        id=f"jamendo:{tid}",
        provider="jamendo",
        provider_track_id=tid,
        title=raw.get("name") or "Untitled",
        artist=raw.get("artist_name") or "Unknown artist",
        album=raw.get("album_name") or None,
        duration_sec=int(raw["duration"]) if raw.get("duration") else None,
        artwork_url=raw.get("image") or raw.get("album_image") or None,
        audio_url=audio,
        language=(info.get("lang") or None),
        genres=[g.lower() for g in tags.get("genres", [])],
        moods=[m.lower() for m in tags.get("vartags", [])],
        energy=energy,
        energy_source="provider" if energy is not None else None,
        license=slug,
        license_url=raw.get("license_ccurl"),
        rights=rights_for_license(slug, has_audio=bool(audio)),
    )


class JamendoProvider(MusicProvider):
    name = "jamendo"
    supplies_audio = True

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    def configured(self) -> bool:
        return bool(settings.JAMENDO_CLIENT_ID)

    def note(self) -> str:
        return "" if self.configured() else "Set JAMENDO_CLIENT_ID (free at developer.jamendo.com)."

    async def _get(self, path: str, params: dict) -> dict:
        if not self.configured():
            raise ProviderNotConfigured("JAMENDO_CLIENT_ID is not set")
        params = {"client_id": settings.JAMENDO_CLIENT_ID, "format": "json", **params}
        try:
            if self._client:
                r = await self._client.get(f"{API}{path}", params=params)
            else:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{API}{path}", params=params)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Jamendo request failed: {exc}") from exc
        code = (data.get("headers") or {}).get("code")
        if code not in (0, None):
            raise ProviderError(f"Jamendo error: {(data.get('headers') or {}).get('error_message')}")
        return data

    async def search(self, query="", *, language=None, genres=None, limit=20):
        params: dict = {
            "limit": max(1, min(limit, 200)),
            "include": "musicinfo",
            "audioformat": "mp32",
            "order": "popularity_total",
            "audiodlformat": "mp32",
        }
        if query:
            params["search"] = query
        tags = map_genres(genres)
        if tags:
            params["tags"] = "+".join(tags)
        if language and language.lower() in _LANG_CODES:
            params["lang"] = _LANG_CODES[language.lower()]
        data = await self._get("/tracks/", params)
        return [parse_track(r) for r in data.get("results", []) if r.get("id")]

    async def get_track(self, provider_track_id):
        data = await self._get("/tracks/", {"id": provider_track_id, "include": "musicinfo", "audioformat": "mp32"})
        res = data.get("results") or []
        return parse_track(res[0]) if res else None
