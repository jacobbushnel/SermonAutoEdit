"""Duration + trim/export. Uses ffmpeg; WAV->WAV falls back to stdlib."""
import json
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


def _filters(src: Path, start: float, end: float) -> list[str]:
    """Audio cleanup chain: rumble filter + two-pass loudness normalisation."""
    chain = []
    if config.HIGHPASS_HZ:
        chain.append(f"highpass=f={config.HIGHPASS_HZ}")
    if config.NORMALIZE:
        base = ",".join(chain + [f"loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11"])
        probe = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", f"{start}", "-to", f"{end}", "-i", str(src),
             "-af", base + ":print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, check=True).stderr
        i = probe.rindex("{")
        m = json.loads(probe[i:probe.index("}", i) + 1])
        chain.append(
            f"loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11:"
            f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true")
    return chain


def trim(src: Path, dst: Path, start: float, end: float) -> None:
    """Write src[start:end] to dst (format chosen by dst's extension)."""
    if _ffmpeg():
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start}", "-to", f"{end}",
               "-i", str(src), "-vn", "-ac", str(config.CHANNELS)]
        chain = _filters(src, start, end)
        if chain:
            cmd += ["-af", ",".join(chain)]
        ext = dst.suffix.lower()
        if ext == ".mp3":
            cmd += ["-codec:a", "libmp3lame", "-b:a", config.AUDIO_BITRATE, "-ar", "44100"]
        elif ext in (".m4a", ".mp4"):
            cmd += ["-codec:a", "aac", "-b:a", config.AUDIO_BITRATE,
                    "-ar", "44100", "-movflags", "+faststart"]
        subprocess.run(cmd + [str(dst)], check=True)
        return
    if src.suffix.lower() == ".wav" and dst.suffix.lower() == ".wav":
        with wave.open(str(src)) as r, wave.open(str(dst), "wb") as w:
            w.setparams(r.getparams())
            r.setpos(int(start * r.getframerate()))
            w.writeframes(r.readframes(int((end - start) * r.getframerate())))
        return
    raise RuntimeError("ffmpeg not found - run: brew install ffmpeg")
