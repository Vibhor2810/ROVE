from app.music_providers.base import MusicProvider, ProviderError, ProviderNotConfigured  # noqa: F401
from app.music_providers.jamendo import JamendoProvider
from app.music_providers.musicbrainz import MusicBrainzProvider
from app.music_providers.vybe import VybeProvider
from app.music_providers.youtube import YouTubeProvider


def default_providers() -> list[MusicProvider]:
    # YouTube first: mainstream catalogue. Jamendo is the backup with full DJ analysis.
    return [YouTubeProvider(), JamendoProvider(), MusicBrainzProvider(), VybeProvider()]
