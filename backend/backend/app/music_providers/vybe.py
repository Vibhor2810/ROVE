"""VYBE adapter: STRUCTURE ONLY.

I could not verify a public VYBE partner API (endpoints, auth scheme, rights
terms), so no HTTP calls are made here and none are faked. When VYBE grants
partner access, implement `search`/`get_track` against their documentation,
map their BPM/key/energy/waveform fields onto `Track`, and set `Rights`
strictly from the licence they grant you.
"""
from __future__ import annotations

from app.core.config import settings
from app.models.track import Track
from app.music_providers.base import MusicProvider, ProviderNotConfigured


class VybeProvider(MusicProvider):
    name = "vybe"
    supplies_audio = False

    def configured(self) -> bool:
        return False  # never report success until a real integration exists

    def note(self) -> str:
        if settings.VYBE_API_KEY:
            return "Key present but adapter not implemented: partner API docs/approval required."
        return "Requires VYBE partner approval and API key. Not integrated."

    async def search(self, query="", *, language=None, genres=None, limit=20) -> list[Track]:
        raise ProviderNotConfigured("VYBE integration requires partner approval")
