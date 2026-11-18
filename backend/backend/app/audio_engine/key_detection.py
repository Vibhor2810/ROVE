from __future__ import annotations

import numpy as np

# Krumhansl-Schmuckler key profiles
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# pitch class (C=0) -> Camelot number
_CAMELOT_MAJOR = {0: 8, 1: 3, 2: 10, 3: 5, 4: 12, 5: 7, 6: 2, 7: 9, 8: 4, 9: 11, 10: 6, 11: 1}
_CAMELOT_MINOR = {0: 5, 1: 12, 2: 7, 3: 2, 4: 9, 5: 4, 6: 11, 7: 6, 8: 1, 9: 8, 10: 3, 11: 10}


def detect_key(y: np.ndarray, sr: int) -> str | None:
    """Return a Camelot code like '8B' (C major) or '5A' (C minor)."""
    import librosa

    if y.size < sr * 5:
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    if not np.any(chroma):
        return None
    best, best_score = None, -2.0
    for tonic in range(12):
        for mode, prof in (("B", _MAJOR), ("A", _MINOR)):
            score = float(np.corrcoef(chroma, np.roll(prof, tonic))[0, 1])
            if score > best_score:
                best, best_score = (tonic, mode), score
    tonic, mode = best
    num = (_CAMELOT_MAJOR if mode == "B" else _CAMELOT_MINOR)[tonic]
    return f"{num}{mode}"


def camelot_compatible(a: str | None, b: str | None) -> bool:
    """Same key, +/-1 on the wheel, or relative major/minor."""
    if not a or not b:
        return True
    try:
        na, ma, nb, mb = int(a[:-1]), a[-1], int(b[:-1]), b[-1]
    except ValueError:
        return True
    if ma == mb:
        d = abs(na - nb)
        return min(d, 12 - d) <= 1
    return na == nb
