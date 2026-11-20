"""Settings for SermonAutoEdit. Edit these paths for your machine."""
from pathlib import Path

# Folder Audacity saves into (this script lives here too).
WATCH_DIR = Path(__file__).resolve().parent
# Folder your RSS-upload automation watches.
OUTPUT_DIR = Path.home() / "SermonsReady"
# One zip that collects every original recording.
ARCHIVE_ZIP = WATCH_DIR / "originals.zip"
# Originals that failed to process are moved here (never deleted).
FAILED_DIR = WATCH_DIR / "failed"

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".aif", ".ogg"}
OUTPUT_FORMAT = "mp3"          # what the podcast feed gets
MP3_BITRATE = "128k"

POLL_SECONDS = 5               # how often to look for new files
STABLE_SECONDS = 20            # file size must be unchanged this long
                               # (Audacity is still writing before that)

# Transcription (used by detect.py)
WHISPER_MODEL = "small.en"

# --- Sermon boundaries (detect.py) ---
# Sermon starts right after the last time this is sung (before END_PHRASE).
START_PHRASE = "Praise and honor to You, Lord Jesus Christ"
# Sermon ends right before this is spoken.
END_PHRASE = "Church of Jesus Christ, what gifts have you brought for your Lord"
MATCH_THRESHOLD = 0.75      # 0-1 fuzzy match; lower = more forgiving of sung lyrics
START_PAD = 0.3             # seconds added after the song's last word
END_PAD = 0.3               # seconds trimmed before the end phrase
MIN_SERMON_SECONDS = 120    # sanity check; shorter than this -> treated as failure
# Vocabulary hint only (full anchor sentences here can get echoed into the
# transcript during music/silence and cause false matches).
WHISPER_PROMPT = "Gospel, Lord Jesus Christ, praise, offering, gifts, Church of Jesus Christ."
