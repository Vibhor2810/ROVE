from enum import Enum


class TrackPermission(str, Enum):
    FULL_PLAYBACK = "full_playback"
    SEEK_PLAYBACK = "seek_playback"
    CROSSFADE = "crossfade"
    SEGMENT_PLAYBACK = "segment_playback"
    DJ_TRANSITION = "dj_transition"
    MIXTAPE_SHARING = "mixtape_sharing"
    PUBLIC_PERFORMANCE = "public_performance"


ALL_DENIED: dict[str, bool] = {p.value: False for p in TrackPermission}


def normalise_rights(rights: dict | None) -> dict[str, bool]:
    """Every permission key is present; anything not explicitly True is False."""
    out = dict(ALL_DENIED)
    for key in out:
        out[key] = bool(rights and rights.get(key) is True)
    return out


def permission_allowed(rights: dict | None, permission: TrackPermission) -> bool:
    """Fail closed when a track's permission is missing."""
    return bool(rights and rights.get(permission.value) is True)
