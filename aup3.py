"""Read raw audio out of an Audacity .aup3 project (no Audacity needed).

Assumes a plain two-track stereo recording whose sample blocks were written
interleaved (odd blockid = left, even = right), which is how Audacity stores
a fresh, un-edited recording. Used to test detect.py on project files.

  python3 aup3.py "All Saints Robert Rice.aup3" out_mono16k.wav
"""
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

RATE = 44100  # the project XML says 44100.0


def to_mono_wav(aup3: Path, out: Path, out_rate: int = 16000) -> None:
    db = sqlite3.connect(f"file:{aup3}?mode=ro&immutable=1", uri=True)
    ids = [r[0] for r in db.execute("select blockid from sampleblocks order by blockid")]
    with tempfile.TemporaryDirectory() as td:
        paths = [Path(td) / "L.f32", Path(td) / "R.f32"]
        with open(paths[0], "wb") as fl, open(paths[1], "wb") as fr:
            for i, bid in enumerate(ids):
                blob = db.execute("select samples from sampleblocks where blockid=?",
                                  (bid,)).fetchone()[0]
                (fl if i % 2 == 0 else fr).write(blob)
        cmd = ["ffmpeg", "-y", "-v", "error"]
        for p in paths:
            cmd += ["-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", str(p)]
        cmd += ["-filter_complex", "[0][1]amerge=inputs=2,pan=mono|c0=0.5*c0+0.5*c1",
                "-ar", str(out_rate), str(out)]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    to_mono_wav(Path(sys.argv[1]), Path(sys.argv[2]))
