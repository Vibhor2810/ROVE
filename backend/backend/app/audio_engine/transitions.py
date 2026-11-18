from __future__ import annotations

from app.audio_engine.bpm import bpm_compatible
from app.audio_engine.key_detection import camelot_compatible
from app.core.permissions import TrackPermission, permission_allowed
from app.models.track import Track


def plan_transition(a: Track, b: Track) -> dict:
    """Plan how to move from track a to b, honouring rights.

    Crossfading needs CROSSFADE on BOTH tracks (a is faded out, b is faded in);
    otherwise a hard cut is used. Beat-matched mixing additionally needs
    DJ_TRANSITION on both and known BPMs.
    """
    a_r, b_r = a.rights.model_dump(), b.rights.model_dump()
    can_fade = permission_allowed(a_r, TrackPermission.CROSSFADE) and permission_allowed(b_r, TrackPermission.CROSSFADE)
    can_dj = can_fade and permission_allowed(a_r, TrackPermission.DJ_TRANSITION) and permission_allowed(b_r, TrackPermission.DJ_TRANSITION)

    bpm_ok = bpm_compatible(a.bpm, b.bpm)
    key_ok = camelot_compatible(a.key, b.key)

    if not can_fade:
        return {"type": "cut", "duration_sec": 0.0, "reason": "crossfade not permitted for this pair",
                "bpm_compatible": bpm_ok, "key_compatible": key_ok, "eq": None}
    if can_dj and a.bpm and b.bpm and bpm_ok:
        beat = 60.0 / a.bpm
        dur = round(beat * (16 if key_ok else 8), 2)  # 16 beats if harmonic, else a short blend
        return {"type": "beatmatch", "duration_sec": min(dur, 12.0), "reason": "bpm compatible",
                "bpm_compatible": True, "key_compatible": key_ok,
                "eq": {"outgoing_low_cut": True, "incoming_low_cut_until_half": True}}
    return {"type": "crossfade", "duration_sec": 4.0 if (bpm_ok and key_ok) else 2.0,
            "reason": "plain crossfade (bpm/key unknown or incompatible)",
            "bpm_compatible": bpm_ok, "key_compatible": key_ok, "eq": None}
