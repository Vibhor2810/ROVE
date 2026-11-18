from __future__ import annotations

from app.models.track import Preferences, Track

_STAGE_MOODS = {
    "warming_up": {"chill", "relaxed", "mellow", "groovy"},
    "peak": {"energetic", "happy", "upbeat", "party", "dance"},
    "winding_down": {"chill", "relaxed", "romantic", "calm", "sad"},
    "only_bangers": {"energetic", "party", "dance", "powerful"},
}


_PURPOSE_MOODS = {
    "workout": {"energetic", "powerful", "dance"},
    "focus": {"calm", "relaxed", "ambient"},
    "chill": {"chill", "relaxed", "mellow"},
    "drive": {"upbeat", "happy", "groovy"},
}


def score_track(t: Track, prefs: Preferences) -> float:
    """Relevance 0..1. Only uses attributes the track actually has."""
    score = 0.3  # base: it is playable and in the catalogue
    wanted_genres = {g.lower() for gs in prefs.genres.values() for g in gs}
    if wanted_genres and wanted_genres & set(t.genres):
        score += 0.4
    if prefs.languages and t.language:
        langs = {l.lower() for l in prefs.languages}
        if t.language.lower() in langs:
            score += 0.2
    if _STAGE_MOODS[prefs.stage] & set(t.moods):
        score += 0.1
    purpose = prefs.effective_purpose()
    if purpose and _PURPOSE_MOODS[purpose] & set(t.moods):
        score += 0.1
    return min(score, 1.0)
