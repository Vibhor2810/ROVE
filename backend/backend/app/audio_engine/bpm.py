from __future__ import annotations

import numpy as np


def detect_bpm(y: np.ndarray, sr: int) -> float | None:
    """Estimate tempo with librosa's beat tracker. Octave-folded into 70-180."""
    import librosa

    if y.size < sr * 5:
        return None
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    if bpm <= 0:
        return None
    while bpm < 70:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    return round(bpm, 1)


def bpm_compatible(a: float | None, b: float | None, tolerance: float = 0.08) -> bool:
    """Compatible if within tolerance directly, or at half/double time."""
    if not a or not b:
        return True  # unknown must not block; callers treat as neutral
    for ratio in (1.0, 2.0, 0.5):
        if abs(a * ratio - b) / b <= tolerance:
            return True
    return False
