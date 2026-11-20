"""End-to-end check using a generated WAV (no ffmpeg needed)."""
import math, struct, subprocess, sys, tempfile, threading, time, wave, zipfile
from pathlib import Path

here = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp())
watch, out = tmp / "watch", tmp / "out"
watch.mkdir()
for f in here.glob("*.py"):
    if f.name != "test_pipeline.py":
        (watch / f.name).write_text(f.read_text())
cfg = (watch / "config.py").read_text()
cfg = cfg.replace("Path.home() / \"SermonsReady\"", f"Path({str(out)!r})")
cfg = cfg.replace("STABLE_SECONDS = 20", "STABLE_SECONDS = 3").replace("POLL_SECONDS = 5", "POLL_SECONDS = 1")
cfg = cfg.replace('OUTPUT_FORMAT = "m4a"', 'OUTPUT_FORMAT = "wav"')
cfg = cfg.replace("PUBLISH = True", "PUBLISH = False")
(watch / "config.py").write_text(cfg)
(watch / "detect.py").write_text("def find_sermon_bounds(a, d):\n    return 0.0, d\n")  # stub: pipeline test only

proc = subprocess.Popen([sys.executable, "sermon_autoedit.py"], cwd=watch)
try:
    time.sleep(1)
    # write slowly in chunks to prove the stability check waits
    f = watch / "svc.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        for _ in range(6):
            w.writeframes(b"".join(struct.pack("<h", int(3000*math.sin(i/10))) for i in range(8000)))
            w._file.flush(); time.sleep(1)
    time.sleep(10)
finally:
    proc.terminate()
res = out / "svc.wav"
ok = res.exists() and not (watch/"svc.wav").exists()
ok = ok and "svc.wav" in zipfile.ZipFile(watch/"originals.zip").namelist()
with wave.open(str(res)) as w:
    secs = w.getnframes()/w.getframerate()
print("output:", res.exists(), "seconds:", secs, "original removed:", not (watch/'svc.wav').exists())
print("PASS" if ok and abs(secs-6) < 0.1 else "FAIL")
