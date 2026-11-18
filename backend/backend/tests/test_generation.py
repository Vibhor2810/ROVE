from app.core.permissions import TrackPermission, normalise_rights, permission_allowed
from app.models.track import Preferences, Rights, Track
from app.services.music_catalogue import Catalogue, is_playable
from app.services.playback_manager import authorize
from app.services.playlist_generator import energy_curve, generate_set, pick_replacement
from app.audio_engine.transitions import plan_transition
from app.audio_engine.bpm import bpm_compatible
from app.audio_engine.key_detection import camelot_compatible
from app.music_providers.base import MusicProvider, ProviderError

OPEN = Rights(full_playback=True, seek_playback=True, crossfade=True, segment_playback=True, dj_transition=True)


def mk(i, energy=None, rights=OPEN, bpm=None, key=None, dur=200, audio=True, **kw):
    return Track(id=f"p:{i}", provider="p", provider_track_id=str(i), title=f"T{i}", artist="A",
                 duration_sec=dur, energy=energy, bpm=bpm, key=key, rights=rights,
                 audio_url="https://x/a.mp3" if audio else None, **kw)


def test_permissions_fail_closed():
    assert not permission_allowed(None, TrackPermission.FULL_PLAYBACK)
    assert not permission_allowed({}, TrackPermission.FULL_PLAYBACK)
    assert not permission_allowed({"full_playback": "yes"}, TrackPermission.FULL_PLAYBACK)
    assert all(v is False for v in normalise_rights(None).values())


def test_playable_requires_audio_and_rights():
    assert is_playable(mk(1))
    assert not is_playable(mk(2, audio=False))
    assert not is_playable(mk(3, rights=Rights()))


def test_authorize_denied_hides_audio_url():
    r = authorize(mk(1, rights=Rights()))
    assert r["playable"] is False and r["audio_url"] is None and r["default_mode"] == "denied"


def test_authorize_nd_falls_back_to_full():
    r = authorize(mk(1, rights=Rights(full_playback=True, seek_playback=True)))
    assert r["default_mode"] == "full" and r["allowed"]["segment"] is False


def test_energy_curves():
    assert energy_curve("only_bangers", 5) == [0.9] * 5
    w = energy_curve("warming_up", 6); assert w == sorted(w)
    d = energy_curve("winding_down", 6); assert d == sorted(d, reverse=True)
    assert energy_curve("peak", 0) == []


def test_winding_down_orders_high_to_low():
    tracks = [mk(i, energy=e) for i, e in enumerate([0.2, 0.9, 0.5, 0.7, 0.3, 0.8])]
    out = generate_set(tracks, Preferences(stage="winding_down", target_minutes=240), seed=1)
    es = [t.energy for t in out]
    assert es == sorted(es, reverse=True) and [t.position for t in out] == list(range(6))


def test_only_bangers_filters_low_energy():
    tracks = [mk(1, energy=0.2), mk(2, energy=0.95), mk(3, energy=0.7)]
    out = generate_set(tracks, Preferences(stage="only_bangers", target_minutes=240), seed=1)
    assert {t.id for t in out} == {"p:2", "p:3"}


def test_empty_candidates_gives_empty_set():
    assert generate_set([], Preferences()) == []


def test_target_duration_respected():
    tracks = [mk(i, energy=0.5, dur=300) for i in range(50)]
    out = generate_set(tracks, Preferences(target_minutes=30), seed=1)
    assert 6 <= len(out) <= 7


def test_deterministic_with_seed_and_regenerate_differs():
    tracks = [mk(i, energy=0.5 + (i % 5) / 20) for i in range(40)]
    p = Preferences(target_minutes=20)
    a = [t.id for t in generate_set(tracks, p, seed=1)]
    assert a == [t.id for t in generate_set(tracks, p, seed=1)]
    assert a != [t.id for t in generate_set(tracks, p, seed=2)]


def test_replace_avoids_duplicates():
    tracks = [mk(i, energy=0.6) for i in range(6)]
    cur = tracks[:3]
    r = pick_replacement(tracks, cur, 1, Preferences(), seed=1)
    assert r and r.id not in {t.id for t in cur}
    assert pick_replacement(tracks[:3], cur, 1, Preferences()) is None


def test_crowd_only_for_events():
    assert Preferences(occasion="listening", crowd="20+").effective_crowd() is None
    assert Preferences(occasion="sangeet", crowd="20+").effective_crowd() == "20+"


def test_bpm_key_compat():
    assert bpm_compatible(120, 124) and bpm_compatible(70, 140) and not bpm_compatible(90, 128)
    assert bpm_compatible(None, 128)
    assert camelot_compatible("8A", "9A") and camelot_compatible("8A", "8B") and camelot_compatible("12A", "1A")
    assert not camelot_compatible("8A", "3A")


def test_transitions_respect_rights():
    nd = Rights(full_playback=True)
    assert plan_transition(mk(1, rights=nd), mk(2))["type"] == "cut"
    assert plan_transition(mk(1), mk(2))["type"] == "crossfade"
    bm = plan_transition(mk(1, bpm=120, key="8A"), mk(2, bpm=122, key="9A"))
    assert bm["type"] == "beatmatch" and bm["duration_sec"] <= 12


class Boom(MusicProvider):
    name = "boom"
    def configured(self): return True
    async def search(self, *a, **k): raise ProviderError("down")


class Ok(MusicProvider):
    name = "ok"
    def configured(self): return True
    async def search(self, *a, **k): return [mk(1), mk(2, rights=Rights())]


async def test_catalogue_survives_failing_provider_and_filters_unplayable():
    tracks, errors = await Catalogue([Boom(), Ok()]).search("x", playable_only=True)
    assert [t.id for t in tracks] == ["p:1"] and "boom" in errors


async def test_catalogue_empty():
    tracks, errors = await Catalogue([]).search("x")
    assert tracks == [] and errors == {}


def test_purpose_only_applies_to_personal_listening():
    assert Preferences(occasion="listening", purpose="workout").effective_purpose() == "workout"
    assert Preferences(occasion="wedding", purpose="workout").effective_purpose() is None


def test_purpose_moods_boost_score():
    from app.services.recommendation import score_track
    a, b = mk(1, moods=["energetic"]), mk(2, moods=[])
    p = Preferences(occasion="listening", purpose="workout")
    assert score_track(a, p) > score_track(b, p)
