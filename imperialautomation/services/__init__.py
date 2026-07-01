from .feed_service import FeedService
from .music_service import AUDIO_ALLOWED_COMMANDS, MusicService

# `summon` is a safe Audio controller command. Keep it available when the
# dedicated #music-request gate is enabled.
AUDIO_ALLOWED_COMMANDS.add("summon")

__all__ = ("FeedService", "MusicService")
