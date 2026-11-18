from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.track import Track


class ProviderError(Exception):
    """Provider call failed (network, bad response)."""


class ProviderNotConfigured(ProviderError):
    """Credentials or partner approval are missing."""


class MusicProvider(ABC):
    name: str = "base"
    #: What the provider can legitimately supply. Used by /api/music/providers.
    supplies_audio: bool = False
    #: True when the provider searches a huge catalogue on demand (no meaningful "N songs ready").
    open_catalogue: bool = False

    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    async def search(
        self, query: str = "", *, language: str | None = None,
        genres: list[str] | None = None, limit: int = 20,
    ) -> list[Track]: ...

    async def get_track(self, provider_track_id: str) -> Track | None:
        return None

    def status(self) -> dict:
        return {
            "name": self.name,
            "configured": self.configured(),
            "supplies_audio": self.supplies_audio,
            "note": self.note(),
        }

    def note(self) -> str:
        return ""
