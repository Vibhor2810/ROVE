import httpx
import pytest

from app.core.config import settings
from app.music_providers import youtube as yt
from app.music_providers.base import ProviderError, ProviderNotConfigured
from app.music_providers.youtube import YouTubeProvider, clean, parse_duration, parse_video
from app.services.music_catalogue import Catalogue, is_playable
from app.services.playback_manager import authorize


def vid(i="abc123", dur="PT3M30S", embeddable=True, privacy="public", live="none", rating=None,
        title="Naacho Naacho (Full Video) | RRR", channel="T-Series"):
    return {"id": i,
            "snippet": {"title": title, "channelTitle": channel, "liveBroadcastContent": live,
                        "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{i}/hq.jpg"}}},
            "contentDetails": {"duration": dur, **({"contentRating": {"ytRating": rating}} if rating else {})},
            "status": {"embeddable": embeddable, "privacyStatus": privacy}}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "k")
    yt._CACHE.clear(); yt._BY_ID.clear()


def test_duration_parsing():
    assert parse_duration("PT3M30S") == 210 and parse_duration("PT1H2M3S") == 3723 and parse_duration("PT45S") == 45
    assert parse_duration("garbage") is None and parse_duration(None) is None


def test_title_cleaning():
    assert clean("Naacho Naacho (Full Video) | RRR | Rahul", "T-Series") == ("Naacho Naacho", "T-Series")
    assert clean("Diljit Dosanjh - Lover (Official Video)", "Diljit") == ("Lover", "Diljit Dosanjh")
    assert clean("Song", "Arijit Singh - Topic")[1] == "Arijit Singh"
    assert clean("It&#39;s Fine", "X")[0] == "It's Fine"
    assert clean("", "")[0] == "Untitled"


@pytest.mark.parametrize("kw", [
    dict(embeddable=False), dict(privacy="private"), dict(live="live"), dict(dur="PT30S"),
    dict(dur="PT2H"), dict(rating="ytAgeRestricted"), dict(dur="bad"),
])
def test_unplayable_videos_filtered(kw):
    assert parse_video(vid(**kw)) is None


def test_good_video_becomes_track_with_honest_rights():
    t = parse_video(vid())
    assert t.id == "youtube:abc123" and t.youtube_id == "abc123" and t.duration_sec == 210
    assert t.audio_url is None and t.artwork_url.startswith("https://i.ytimg.com/")
    r = t.rights
    assert r.full_playback and r.seek_playback and r.segment_playback
    assert not (r.crossfade or r.dj_transition or r.mixtape_sharing or r.public_performance)
    assert t.bpm is None and t.key is None and t.energy is None   # never invented
    assert is_playable(t)


def test_authorize_youtube_uses_iframe_source_not_audio_url():
    a = authorize(parse_video(vid()))
    assert a["playable"] and a["audio_url"] is None
    assert a["source"] == {"kind": "youtube", "id": "abc123"}
    assert a["allowed"]["segment"] and not a["allowed"]["crossfade"]


def mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_search_two_step_filters_and_caches():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req.url.path)
        if req.url.path.endswith("/search"):
            p = dict(req.url.params)
            assert p["videoEmbeddable"] == "true" and p["videoCategoryId"] == "10" and p["key"] == "k"
            assert p["relevanceLanguage"] == "hi" and "hindi" in p["q"] and "dance" in p["q"]
            return httpx.Response(200, json={"items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}, {"id": {}}]})
        return httpx.Response(200, json={"items": [vid("a"), vid("b", embeddable=False)]})

    p = YouTubeProvider(mock_client(handler))
    out = await p.search("", language="Hindi", genres=["Dance"], limit=10)
    assert [t.id for t in out] == ["youtube:a"]
    await p.search("", language="Hindi", genres=["Dance"], limit=10)
    assert calls.count("/youtube/v3/search") + calls.count("/search") == 1  # second call served from cache
    assert (await p.get_track("a")).id == "youtube:a"  # served from id cache, no new call


async def test_get_track_unavailable_returns_none():
    p = YouTubeProvider(mock_client(lambda r: httpx.Response(200, json={"items": []})))
    assert await p.get_track("gone") is None


@pytest.mark.parametrize("reason,msg", [("quotaExceeded", "quota"), ("keyInvalid", "key rejected")])
async def test_api_errors_are_clear(reason, msg):
    body = {"error": {"errors": [{"reason": reason}]}}
    p = YouTubeProvider(mock_client(lambda r: httpx.Response(403, json=body)))
    with pytest.raises(ProviderError, match=msg):
        await p.search("x")


async def test_network_failure_is_provider_error():
    def boom(req): raise httpx.ConnectError("down")
    with pytest.raises(ProviderError):
        await YouTubeProvider(mock_client(boom)).search("x")


async def test_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
    assert YouTubeProvider().configured() is False
    with pytest.raises(ProviderNotConfigured):
        await YouTubeProvider().search("x")


async def test_catalogue_falls_back_to_other_provider_when_youtube_quota_dies():
    from app.models.track import Rights, Track

    class Backup(yt.MusicProvider):
        name = "backup"
        def configured(self): return True
        async def search(self, *a, **k):
            return [Track(id="b:1", provider="backup", provider_track_id="1", title="T", artist="A",
                          audio_url="https://x/a.mp3", rights=Rights(full_playback=True))]

    body = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    cat = Catalogue([YouTubeProvider(mock_client(lambda r: httpx.Response(403, json=body))), Backup()])
    tracks, errors = await cat.search("x", playable_only=True)
    assert [t.id for t in tracks] == ["b:1"] and "quota" in errors["youtube"]


def test_languages_endpoint_reports_open_catalogue_without_probing(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import current_member
    app.dependency_overrides[current_member] = lambda: object()
    try:
        r = TestClient(app).get("/api/music/languages")
    finally:
        app.dependency_overrides.clear()
    langs = r.json()["languages"]
    assert all(l["open"] and l["count"] is None for l in langs) and len(langs) == 5


def test_analysis_refused_for_youtube_tracks(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import current_member
    from app.deps import get_catalogue
    t = parse_video(vid())

    class C:
        async def get_track(self, _): return t
    app.dependency_overrides[current_member] = lambda: object()
    app.dependency_overrides[get_catalogue] = lambda: C()
    try:
        r = TestClient(app).post("/api/audio/analyze", json={"track_id": "youtube:abc123"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422 and "YouTube" in r.json()["detail"]
