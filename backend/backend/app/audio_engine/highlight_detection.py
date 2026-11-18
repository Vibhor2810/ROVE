from __future__ import annotations

import numpy as np


def waveform_peaks(y: np.ndarray, bars: int = 120) -> list[float]:
    """Normalised 0..1 amplitude per bar for drawing a waveform."""
    if y.size == 0:
        return []
    chunks = np.array_split(np.abs(y), bars)
    peaks = np.array([c.max() if c.size else 0.0 for c in chunks])
    m = peaks.max()
    return [round(float(p / m), 3) for p in peaks] if m > 0 else [0.0] * bars


def estimate_highlight(y: np.ndarray, sr: int, window_sec: float = 30.0) -> dict | None:
    """Estimate an energetic section by loudness (RMS) over a sliding window.

    This is an *estimate from audio analysis*. It is NOT the most-listened
    part of the song, and is reported with source='estimated' so the UI never
    claims otherwise.
    """
    import librosa

    dur = y.size / sr
    if dur < 20:
        return None
    window_sec = min(window_sec, dur)
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    fps = sr / hop
    w = max(1, int(window_sec * fps))
    if rms.size <= w:
        return {"in_sec": 0.0, "out_sec": round(dur, 2), "source": "estimated"}
    csum = np.concatenate([[0.0], np.cumsum(rms)])
    sums = csum[w:] - csum[:-w]
    # Skip the first 5% (intros are quiet) when choosing.
    start_min = int(0.05 * rms.size)
    idx = start_min + int(np.argmax(sums[start_min:])) if sums.size > start_min else int(np.argmax(sums))
    in_sec = idx / fps
    return {
        "in_sec": round(in_sec, 2),
        "out_sec": round(min(dur, in_sec + window_sec), 2),
        "source": "estimated",
    }
