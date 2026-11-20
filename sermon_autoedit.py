"""Watch a folder for new recordings, cut out the sermon, archive the original.

Run:  python3 sermon_autoedit.py
"""
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path

import audio
import config
import detect

log = logging.getLogger("sermon")


def is_candidate(p: Path) -> bool:
    return (p.is_file() and p.suffix.lower() in config.AUDIO_EXTS
            and not p.name.startswith("."))


def wait_until_stable(p: Path) -> bool:
    """True once size is unchanged for STABLE_SECONDS (Audacity done writing)."""
    last, since = -1, time.monotonic()
    while True:
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            return False
        if size != last or size == 0:
            last, since = size, time.monotonic()
        elif time.monotonic() - since >= config.STABLE_SECONDS:
            return True
        time.sleep(1)


def archive(original: Path) -> None:
    """Add original to the zip, verify, then delete the original."""
    with zipfile.ZipFile(config.ARCHIVE_ZIP, "a", zipfile.ZIP_STORED) as z:
        name = original.name
        if name in z.namelist():  # don't clobber an earlier recording
            name = f"{original.stem}-{int(time.time())}{original.suffix}"
        z.write(original, arcname=name)
    with zipfile.ZipFile(config.ARCHIVE_ZIP) as z:
        if z.testzip() is not None:
            raise RuntimeError("archive zip failed verification; original kept")
    original.unlink()


def process(p: Path) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dur = audio.duration(p)
    start, end = detect.find_sermon_bounds(p, dur)
    log.info("%s: %.1fs total, keeping %.1f-%.1f", p.name, dur, start, end)

    out_ext = "." + config.OUTPUT_FORMAT
    final = config.OUTPUT_DIR / (p.stem + out_ext)
    tmp = config.OUTPUT_DIR / (p.stem + ".part" + out_ext)  # uploader ignores .part
    audio.trim(p, tmp, start, end)
    os.replace(tmp, final)          # atomic: uploader never sees a half file
    log.info("wrote %s", final)

    archive(p)                      # only after the edit exists
    for side in p.parent.glob(p.name + ".words.json"):
        side.unlink()
    log.info("archived %s -> %s", p.name, config.ARCHIVE_ZIP.name)


def handle(p: Path) -> None:
    try:
        if wait_until_stable(p):
            process(p)
    except Exception:
        log.exception("failed on %s; moving to %s", p.name, config.FAILED_DIR)
        config.FAILED_DIR.mkdir(exist_ok=True)
        if p.exists():
            shutil.move(str(p), config.FAILED_DIR / p.name)
        side = p.with_suffix(p.suffix + ".words.json")   # transcript, for debugging
        if side.exists():
            shutil.move(str(side), config.FAILED_DIR / side.name)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log.info("watching %s", config.WATCH_DIR)
    while True:
        for p in sorted(config.WATCH_DIR.iterdir()):
            if is_candidate(p):
                handle(p)   # sequential; originals leave the folder when done
        time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
