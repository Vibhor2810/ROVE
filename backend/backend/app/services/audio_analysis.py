from __future__ import annotations

import io
import logging
from urllib.parse import urlparse

import httpx
import numpy as np

from app.audio_engine.bpm import detect_bpm
from app.audio_engine.highlight_detection import estimate_highlight, waveform_peaks
from app.audio_engine.key_detection import detect_key
from app.core.config import settings

log = logging.getLogger("rove.analysis")
# Only analyse audio from hosts a rights-cleared provider supplies.
ALLOWED_HOSTS = ("jamendo.com",)


class AnalysisError(Exception):
    pass


def host_allowed(url: str) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    # APP_ENV=test (local test harness only) additionally trusts one loopback audio host over http.
    if settings.APP_ENV == "test" and settings.TEST_AUDIO_HOST and host == settings.TEST_AUDIO_HOST and u.scheme == "http":
        return True
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def analyse_samples(y: np.ndarray, sr: int) -> dict:
    return {
        "duration_sec": round(y.size / sr, 2),
        "bpm": detect_bpm(y, sr),
        "key": detect_key(y, sr),
        "highlight": estimate_highlight(y, sr),
        "waveform": waveform_peaks(y),
    }


_CACHE: dict[str, dict] = {}
_CACHE_MAX = 200


async def analyse_url(url: str) -> dict:
    if not host_allowed(url):
        raise AnalysisError("Audio host is not an approved provider host")
    if url in _CACHE:
        return _CACHE[url]
    result = await _analyse_uncached(url)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[url] = result
    return result


async def _analyse_uncached(url: str) -> dict:
    import librosa

    buf = io.BytesIO()
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            async with c.stream("GET", url) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes():
                    buf.write(chunk)
                    if buf.tell() > settings.ANALYSIS_MAX_BYTES:
                        raise AnalysisError("Audio file too large to analyse")
    except httpx.HTTPError as exc:
        raise AnalysisError(f"Could not fetch audio: {exc}") from exc
    buf.seek(0)
    try:
        y, sr = librosa.load(buf, sr=22050, mono=True)
    except Exception as exc:  # decoder errors vary by backend
        raise AnalysisError(f"Could not decode audio: {exc}") from exc
    return analyse_samples(y, sr)
