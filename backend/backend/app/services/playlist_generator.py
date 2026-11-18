from __future__ import annotations

import random

from app.audio_engine.bpm import bpm_compatible
from app.audio_engine.key_detection import camelot_compatible
from app.models.track import Preferences, SetTrack, Track
from app.services.recommendation import score_track

MIN_TRACKS = 100
MAX_TRACKS = 200
UNKNOWN_ENERGY_COST = 0.06
BPM_PENALTY = 0.04
KEY_PENALTY = 0.02


def energy_curve(stage: str, n: int) -> list[float]:
    if n <= 0:
        return []
    def lerp(a, b, i):
        return a + (b - a) * (i / max(1, n - 1))
    if stage == "warming_up":
        return [lerp(0.3, 0.65, i) for i in range(n)]
    if stage == "winding_down":
        return [lerp(0.7, 0.2, i) for i in range(n)]
    if stage == "only_bangers":
        return [0.9] * n
    out = []
    for i in range(n):
        base = 0.8 if i >= max(1, n // 8) else lerp(0.55, 0.8, i)
        if n >= 10 and abs(i - n // 2) <= 0:
            base = 0.65
        out.append(base)
    return out


def _energy_cost(t: Track, target: float) -> float:
    return UNKNOWN_ENERGY_COST if t.energy is None else (t.energy - target) ** 2


def _transition_penalty(a: Track, b: Track) -> float:
    return (BPM_PENALTY if not bpm_compatible(a.bpm, b.bpm) else 0.0) + (KEY_PENALTY if not camelot_compatible(a.key, b.key) else 0.0)


def _cost(t: Track, target: float, prev: Track | None) -> float:
    return _energy_cost(t, target) + (_transition_penalty(prev, t) if prev is not None else 0.0)


def _order(chosen: list[Track], targets: list[float]) -> list[Track]:
    """Fast O(n log n) energy-curve + BPM/key compatible ordering."""
    remaining = chosen[:]
    ordered: list[Track] = []
    prev: Track | None = None
    for tg in targets:
        best_idx = min(range(len(remaining)), key=lambda idx: _cost(remaining[idx], tg, prev))
        pick = remaining.pop(best_idx)
        ordered.append(pick)
        prev = pick
    return ordered


def generate_set(candidates: list[Track], prefs: Preferences, *, seed: int | None = None,
                 exclude_ids: set[str] | None = None) -> list[SetTrack]:
    rng = random.Random(seed)
    pool = [t for t in candidates if not exclude_ids or t.id not in exclude_ids]
    if prefs.stage == "only_bangers":
        filtered = [t for t in pool if t.energy is None or t.energy >= 0.6]
        if len(filtered) >= MIN_TRACKS:
            pool = filtered

    scored = sorted(pool, key=lambda t: score_track(t, prefs) + rng.random() * 0.15, reverse=True)

    chosen: list[Track] = []
    total, target_sec = 0, prefs.target_minutes * 60
    for t in scored:
        if len(chosen) >= MAX_TRACKS:
            break
        if len(chosen) >= MIN_TRACKS and total >= target_sec:
            break
        chosen.append(t)
        total += t.duration_sec or 180
    if not chosen:
        return []

    targets = energy_curve(prefs.stage, len(chosen))
    ordered = _order(chosen, targets)
    return [SetTrack(**t.model_dump(), position=i) for i, t in enumerate(ordered)]


def pick_replacement(candidates: list[Track], current: list[Track], index: int,
                     prefs: Preferences, seed: int | None = None) -> Track | None:
    used = {t.id for t in current}
    pool = [t for t in candidates if t.id not in used]
    if not pool:
        return None
    target = energy_curve(prefs.stage, len(current))[index]
    prev = current[index - 1] if index > 0 else None
    rng = random.Random(seed)
    return min(pool, key=lambda t: _cost(t, target, prev) - score_track(t, prefs) * 0.05 + rng.random() * 0.005)
