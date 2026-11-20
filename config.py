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
OUTPUT_FORMAT = "m4a"          # "m4a" (AAC in an MP4 container) or "mp3"
AUDIO_BITRATE = "96k"          # speech is transparent at 96k mono AAC; 128k+ for stereo
CHANNELS = 1                   # 1 = mono (right for a single preacher), 2 = stereo
NORMALIZE = True               # even out loudness to the podcast standard
TARGET_LUFS = -16.0            # Apple/Spotify podcast target (stereo); mono -16 also fine
HIGHPASS_HZ = 80               # remove rumble/handling noise below this

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
# No prompt: Whisper echoed prompt text into the transcript during the
# prelude when we gave it one.
WHISPER_PROMPT = None

# Whisper often drops sung lyrics but does catch the pastor's spoken cue.
# The song ends at the first word after a silence of at least this long
# (in the transcript) following the cue.
START_CUE_PHRASE = "The Gospel of Christ"
SONG_GAP_SECONDS = 5.0
SONG_MAX_SECONDS = 90.0     # give up looking for the end of the song after this
START_CUE_THRESHOLD = 0.9   # stricter than MATCH_THRESHOLD: short phrase, easy to false-match
REFINE_WINDOW_SECONDS = 45   # how far past the anchor to re-listen for the first spoken word
