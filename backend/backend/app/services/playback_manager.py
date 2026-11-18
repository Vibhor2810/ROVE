from __future__ import annotations

from app.core.permissions import TrackPermission, permission_allowed
from app.models.track import Track

MODES = {
    "full": TrackPermission.FULL_PLAYBACK,
    "segment": TrackPermission.SEGMENT_PLAYBACK,
    "crossfade": TrackPermission.CROSSFADE,
    "seek": TrackPermission.SEEK_PLAYBACK,
}


def authorize(track: Track) -> dict:
    """Server-side decision from the provider's own data (never from the client)."""
    r = track.rights.model_dump()
    has_audio = bool(track.audio_url or track.youtube_id)
    full = has_audio and permission_allowed(r, TrackPermission.FULL_PLAYBACK)
    seg = full and permission_allowed(r, TrackPermission.SEGMENT_PLAYBACK)
    return {
        "track_id": track.id,
        "playable": full,
        "audio_url": track.audio_url if full else None,
        # How the frontend must play it. YouTube tracks play ONLY inside the official IFrame player.
        "source": (None if not full else ({"kind": "youtube", "id": track.youtube_id} if track.youtube_id else {"kind": "audio", "url": track.audio_url})),
        "allowed": {
            "full": full,
            "segment": seg,
            "seek": full and permission_allowed(r, TrackPermission.SEEK_PLAYBACK),
            "crossfade": full and permission_allowed(r, TrackPermission.CROSSFADE),
        },
        # Skip Song always works; segment mode falls back to full if not permitted.
        "default_mode": "segment" if seg else ("full" if full else "denied"),
        "reason": None if full else "No audio URL or full playback is not permitted by the provider licence",
        "license": track.license,
    }
