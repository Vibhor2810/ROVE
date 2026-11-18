from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Occasion = Literal[
    "listening", "wedding", "baraat", "sangeet", "mehendi", "haldi",
    "birthday", "house_party", "club", "corporate",
]
EVENT_OCCASIONS = {
    "wedding", "baraat", "sangeet", "mehendi", "haldi",
    "birthday", "house_party", "club", "corporate",
}
Stage = Literal["warming_up", "peak", "winding_down", "only_bangers"]
Crowd = Literal["4-6", "10-20", "20+"]
Purpose = Literal["workout", "focus", "chill", "drive"]


class Rights(BaseModel):
    full_playback: bool = False
    seek_playback: bool = False
    crossfade: bool = False
    segment_playback: bool = False
    dj_transition: bool = False
    mixtape_sharing: bool = False
    public_performance: bool = False


class Track(BaseModel):
    """Provider-neutral track. Fields a provider does not supply stay None;
    they are never invented."""
    id: str                      # "<provider>:<provider_track_id>"
    provider: str
    provider_track_id: str
    title: str
    artist: str
    album: str | None = None
    duration_sec: int | None = None
    artwork_url: str | None = None
    audio_url: str | None = None      # only set when a provider legitimately supplies it
    youtube_id: str | None = None     # playback via the official YouTube IFrame player ONLY (never extracted audio)
    language: str | None = None
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    bpm: float | None = None
    key: str | None = None            # Camelot, e.g. "8A"
    energy: float | None = None       # 0..1, only if provider-supplied or analysed
    energy_source: Literal["provider", "analysis"] | None = None
    musicbrainz_id: str | None = None
    license: str | None = None
    license_url: str | None = None
    rights: Rights = Field(default_factory=Rights)


class SetTrack(Track):
    position: int = 0


class Preferences(BaseModel):
    occasion: Occasion = "listening"
    languages: list[str] = Field(default_factory=list)
    genres: dict[str, list[str]] = Field(default_factory=dict)  # language -> genres
    purpose: Purpose | None = None   # only meaningful when occasion == "listening"
    stage: Stage = "peak"
    crowd: Crowd | None = None
    target_minutes: int = Field(default=60, ge=10, le=240)

    @field_validator("languages")
    @classmethod
    def _max_langs(cls, v: list[str]) -> list[str]:
        if len(v) > 6:
            raise ValueError("too many languages")
        return v

    def effective_purpose(self) -> Purpose | None:
        return self.purpose if self.occasion == "listening" else None

    def effective_crowd(self) -> Crowd | None:
        """Crowd size is only meaningful for event occasions."""
        return self.crowd if self.occasion in EVENT_OCCASIONS else None
