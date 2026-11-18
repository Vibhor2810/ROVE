"""YouTube provider: official YouTube Data API v3 for search + metadata.

Playback happens ONLY through YouTube's official IFrame player in the browser.
This module never touches, extracts or proxies audio/video streams, so there is
no audio_url. It fetches metadata and checks the video is embeddable.

Quota: search.list costs 100 units (free quota is 10,000/day => ~100 searches),
videos.list costs 1. Results are cached for 24h to protect the quota.
"""
from __future__ import annotations

import html
import re
import time

import httpx

from app.core.config import settings
from app.models.track import Rights, Track
from app.music_providers.base import MusicProvider, ProviderError, ProviderNotConfigured

_LANG_CODE = {"hindi": "hi", "punjabi": "pa", "english": "en", "tamil / telugu": "ta", "garba / gujarati": "gu"}
_LANG_WORD = {"hindi": "hindi", "punjabi": "punjabi", "english": "english", "tamil / telugu": "tamil telugu",
              "garba / gujarati": "gujarati garba"}
MIN_SEC, MAX_SEC = 90, 720          # drops shorts, mixes, hour-long compilations
CACHE_TTL = 24 * 3600
_CACHE: dict = {}
_BY_ID: dict[str, Track] = {}
_NOISE = re.compile(r"\s*[\(\[][^)\]]*(official|video|audio|lyric|lyrics|full song|hd|4k|visualizer)[^)\]]*[\)\]]", re.I)
_DUR = re.compile(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")

# YouTube rights: full playback + seek + segment (start/end) are what the IFrame API provides.
# Crossfading two players is NOT clearly permitted by the API terms, so it stays denied;
# sharing and public performance are never assumed.
YT_RIGHTS = Rights(full_playback=True, seek_playback=True, segment_playback=True,
                   crossfade=False, dj_transition=False, mixtape_sharing=False, public_performance=False)


def parse_duration(iso: str | None) -> int | None:
    m = _DUR.match(iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def clean(title: str, channel: str) -> tuple[str, str]:
    title, channel = html.unescape(title or ""), html.unescape(channel or "")
    artist = re.sub(r"\s*-\s*Topic$|VEVO$", "", channel, flags=re.I).strip() or "Unknown artist"
    title = _NOISE.sub("", title).split(" | ")[0].strip()
    if " - " in title:  # "Artist - Song"
        a, _, t = title.partition(" - ")
        if a and t and len(a) < 60:
            artist, title = a.strip(), t.strip()
    return (title or "Untitled"), artist


def parse_video(v: dict) -> Track | None:
    """Return a Track only if the video can legitimately be played in an embed."""
    status, cd, sn = v.get("status") or {}, v.get("contentDetails") or {}, v.get("snippet") or {}
    if not status.get("embeddable") or status.get("privacyStatus") != "public":
        return None
    if sn.get("liveBroadcastContent", "none") != "none":
        return None
    if (cd.get("contentRating") or {}).get("ytRating") == "ytAgeRestricted":
        return None
    dur = parse_duration(cd.get("duration"))
    if dur is None or not (MIN_SEC <= dur <= MAX_SEC):
        return None
    vid = v["id"]
    title, artist = clean(sn.get("title", ""), sn.get("channelTitle", ""))
    thumbs = sn.get("thumbnails") or {}
    art = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    return Track(id=f"youtube:{vid}", provider="youtube", provider_track_id=vid, title=title, artist=artist,
                 duration_sec=dur, artwork_url=art, youtube_id=vid, rights=YT_RIGHTS.model_copy())


class YouTubeProvider(MusicProvider):
    name = "youtube"
    supplies_audio = False   # plays via the official IFrame player, never as an audio URL
    open_catalogue = True

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    def configured(self) -> bool:
        return bool(settings.YOUTUBE_API_KEY)

    def note(self) -> str:
        return ("Plays via the official YouTube IFrame player (needs a visible player; Premium removes ads). "
                "No audio analysis. Free API quota is ~100 searches/day."
                if self.configured() else "Set YOUTUBE_API_KEY (Google Cloud Console > YouTube Data API v3).")

    async def _get(self, path: str, params: dict) -> dict:
        if not self.configured():
            raise ProviderNotConfigured("YOUTUBE_API_KEY is not set")
        params = {**params, "key": settings.YOUTUBE_API_KEY}
        try:
            if self._client:
                r = await self._client.get(f"{settings.YOUTUBE_API_BASE}{path}", params=params)
            else:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{settings.YOUTUBE_API_BASE}{path}", params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"YouTube request failed: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            try:
                reason = r.json()["error"]["errors"][0]["reason"]
            except (ValueError, KeyError, IndexError):
                reason = str(r.status_code)
            if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
                raise ProviderError("YouTube API quota used up for today")
            if reason in ("keyInvalid", "API_KEY_INVALID", "accessNotConfigured", "forbidden"):
                raise ProviderError("YouTube API key rejected, check YOUTUBE_API_KEY and that Data API v3 is enabled")
            raise ProviderError(f"YouTube API error ({reason})")
        try:
            return r.json()
        except ValueError as exc:
            raise ProviderError("YouTube returned an invalid response") from exc

    async def _details(self, ids: list[str]) -> list[Track]:
        data = await self._get("/videos", {"part": "snippet,contentDetails,status", "id": ",".join(ids), "maxResults": len(ids)})
        out = []
        for v in data.get("items", []):
            t = parse_video(v)
            if t:
                _BY_ID[t.provider_track_id] = t
                out.append(t)
        return out

    async def search(self, query="", *, language=None, genres=None, limit=20):
        lang = (language or "").lower()
        q = query.strip() or " ".join(
            p for p in [_LANG_WORD.get(lang, ""), *[re.sub(r"[/]", " ", g.lower()) for g in (genres or [])], "songs"] if p)
        limit = max(1, min(limit, 50))
        key = (q, _LANG_CODE.get(lang), limit)
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return hit[1]
        params = {"part": "snippet", "type": "video", "videoCategoryId": "10", "videoEmbeddable": "true",
                  "videoSyndicated": "true", "maxResults": min(50, limit + 10), "q": q}  # +10: some get filtered
        if _LANG_CODE.get(lang):
            params["relevanceLanguage"] = _LANG_CODE[lang]
        found = await self._get("/search", params)
        ids = [i["id"]["videoId"] for i in found.get("items", []) if (i.get("id") or {}).get("videoId")]
        tracks = (await self._details(ids))[:limit] if ids else []
        if len(_CACHE) >= 200:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (time.monotonic(), tracks)
        return tracks

    async def get_track(self, provider_track_id):
        if provider_track_id in _BY_ID:
            return _BY_ID[provider_track_id]
        res = await self._details([provider_track_id])
        return res[0] if res else None


