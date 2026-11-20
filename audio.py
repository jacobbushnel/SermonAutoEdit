"""Duration + trim/export. Uses ffmpeg; WAV->WAV falls back to stdlib."""
import shutil
import subprocess
import wave
from pathlib import Path

import config


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found - run: brew install ffmpeg")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(out)


def trim(src: Path, dst: Path, start: float, end: float) -> None:
    """Write src[start:end] to dst (format chosen by dst's extension)."""
    if _ffmpeg():
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start}", "-to", f"{end}",
               "-i", str(src), "-vn"]
        if dst.suffix.lower() == ".mp3":
            cmd += ["-codec:a", "libmp3lame", "-b:a", config.MP3_BITRATE]
        subprocess.run(cmd + [str(dst)], check=True)
        return
    if src.suffix.lower() == ".wav" and dst.suffix.lower() == ".wav":
        with wave.open(str(src)) as r, wave.open(str(dst), "wb") as w:
            w.setparams(r.getparams())
            r.setpos(int(start * r.getframerate()))
            w.writeframes(r.readframes(int((end - start) * r.getframerate())))
        return
    raise RuntimeError("ffmpeg not found - run: brew install ffmpeg")
