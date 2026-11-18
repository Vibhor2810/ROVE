import httpx
import pytest

from app.core.config import settings
from app.music_providers.base import ProviderError, ProviderNotConfigured
from app.music_providers.jamendo import JamendoProvider, parse_track, rights_for_license
from app.music_providers.musicbrainz import MusicBrainzProvider, parse_recording
from app.music_providers.vybe import VybeProvider

RAW = {"id": "123", "name": "Song", "artist_name": "Artist", "duration": 200,
       "audio": "https://prod-1.storage.jamendo.com/?trackid=123&format=mp31",
       "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
       "musicinfo": {"speed": "high", "tags": {"genres": ["Pop"], "vartags": ["happy"]}}}


def test_jamendo_parse_and_rights():
    t = parse_track(RAW)
    assert t.id == "jamendo:123" and t.energy == 0.75 and t.energy_source == "provider"
    assert t.rights.full_playback and t.rights.crossfade
    assert not t.rights.public_performance and not t.rights.mixtape_sharing
    assert bpm_is_none(t)


def bpm_is_none(t):
    return t.bpm is None and t.key is None  # never invented


def test_nd_license_blocks_derivative_modes():
    r = rights_for_license("by-nc-nd", has_audio=True)
    assert r.full_playback and not r.crossfade and not r.dj_transition and not r.segment_playback


def test_unknown_license_or_no_audio_denies_everything():
    assert not any(rights_for_license(None, has_audio=True).model_dump().values())
    assert not any(rights_for_license("by", has_audio=False).model_dump().values())


def test_missing_energy_stays_none():
    raw = {**RAW, "musicinfo": {}}
    t = parse_track(raw)
    assert t.energy is None and t.energy_source is None


async def test_jamendo_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "JAMENDO_CLIENT_ID", "")
    with pytest.raises(ProviderNotConfigured):
        await JamendoProvider().search("x")


async def test_jamendo_search_via_mock(monkeypatch):
    monkeypatch.setattr(settings, "JAMENDO_CLIENT_ID", "abc")
    seen = {}

    def handler(req: httpx.Request):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json={"headers": {"code": 0}, "results": [RAW]})

    p = JamendoProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    out = await p.search("hello", language="Hindi", genres=["pop"], limit=5)
    assert len(out) == 1 and seen["client_id"] == "abc" and seen["lang"] == "hi" and seen["tags"] == "pop"


def test_genre_mapping_drops_unknown_labels():
    from app.music_providers.jamendo import map_genres
    assert map_genres(["Desi Hip-Hop", "Gym / Workout", "Dance", "dance"]) == ["hiphop", "dance"]
    assert map_genres(None) == []


async def test_jamendo_api_error_and_http_error(monkeypatch):
    monkeypatch.setattr(settings, "JAMENDO_CLIENT_ID", "abc")
    bad = JamendoProvider(httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"headers": {"code": 5, "error_message": "bad"}, "results": []}))))
    with pytest.raises(ProviderError):
        await bad.search("x")
    down = JamendoProvider(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with pytest.raises(ProviderError):
        await down.search("x")


def test_musicbrainz_is_metadata_only():
    t = parse_recording({"id": "m1", "title": "T", "length": 180000,
                         "artist-credit": [{"name": "A", "joinphrase": " & "}, {"name": "B"}]})
    assert t.artist == "A & B" and t.duration_sec == 180 and t.audio_url is None
    assert not any(t.rights.model_dump().values())


async def test_musicbrainz_search_mock(monkeypatch):
    p = MusicBrainzProvider(httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"recordings": [{"id": "m1", "title": "T"}]}))))
    out = await p.search("t")
    assert out[0].provider == "musicbrainz" and out[0].audio_url is None


async def test_vybe_never_claims_success():
    v = VybeProvider()
    assert v.configured() is False
    with pytest.raises(ProviderNotConfigured):
        await v.search("x")
