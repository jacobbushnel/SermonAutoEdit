"""Find where the sermon starts and ends.  <-- the tricky part, to be built.

find_sermon_bounds() is the only thing the rest of the pipeline cares about.
Transcribe() saves word-level timestamps to <audio>.words.json so you can
tune the detection logic without re-transcribing a 60-90 minute file.
"""
import difflib
import json
import re
from pathlib import Path

import config


def transcribe(audio: Path) -> list[dict]:
    """Return [{'word','start','end'}, ...]; cached in a .words.json sidecar."""
    cache = audio.with_suffix(audio.suffix + ".words.json")
    if cache.exists():
        return json.loads(cache.read_text())
    from faster_whisper import WhisperModel  # lazy: only needed here
    model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    segments, _ = model.transcribe(str(audio), word_timestamps=True,
                                       initial_prompt=config.WHISPER_PROMPT or None)
    words = [{"word": w.word.strip(), "start": w.start, "end": w.end}
             for seg in segments for w in seg.words]
    cache.write_text(json.dumps(words))
    return words


_MODEL = None


def first_spoken_word(audio: Path, a: float, b: float) -> float | None:
    """Re-transcribe just [a, b] seconds with a fresh context and voice-activity
    filtering (which skips sung/instrumental parts); return the first word's start."""
    global _MODEL
    from faster_whisper import WhisperModel
    _MODEL = _MODEL or WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    segs, _ = _MODEL.transcribe(str(audio), word_timestamps=True,
                                clip_timestamps=[a, b],
                                condition_on_previous_text=False, vad_filter=True)
    for seg in segs:
        for w in seg.words:
            if w.start >= a:
                return w.start
    return None


def _norm(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def find_phrase(words: list[dict], phrase: str, threshold: float | None = None,
                after: float = 0.0) -> list[tuple[float, float, float]]:
    """Fuzzy-find `phrase` in the word list (sung lyrics transcribe badly, so
    exact matching is too brittle). Returns [(start, end, score)] for each
    non-overlapping match at/after `after` seconds, in time order."""
    threshold = threshold or config.MATCH_THRESHOLD
    target = _norm(phrase)
    n = len(target)
    toks = [(w["start"], w["end"], _norm(w["word"])) for w in words]
    flat = [(a, b, t) for a, b, ts in toks for t in ts]   # one token per entry
    def score(i):
        best = (0.0, n)
        for size in (n - 1, n, n + 1):                    # tolerate dropped/extra words
            if size < 1 or i + size > len(flat):
                continue
            cand = [t for _, _, t in flat[i:i + size]]
            sc = difflib.SequenceMatcher(None, target, cand).ratio()
            if sc > best[0]:
                best = (sc, size)
        return best

    hits, i = [], 0
    while i + n <= len(flat):
        if flat[i][0] < after or score(i)[0] < threshold:
            i += 1
            continue
        # a window that starts a few words early also scores well; pick the
        # best-aligned start within the next few positions
        j = max(range(i, min(i + n // 2 + 1, len(flat))), key=lambda k: score(k)[0])
        sc, size = score(j)
        hits.append((flat[j][0], flat[j + size - 1][1], sc))
        i = j + size
    return hits


def song_end_after(words: list[dict], t: float) -> float | None:
    """Start time of the first word that follows a >= SONG_GAP_SECONDS silence
    after time t (within SONG_MAX_SECONDS)."""
    prev_end = t
    for w in words:
        if w["start"] < t:
            continue
        if w["start"] - prev_end >= config.SONG_GAP_SECONDS:
            return w["start"] - config.START_PAD
        if w["start"] - t > config.SONG_MAX_SECONDS:
            return None
        prev_end = w["end"]
    return None


def bounds_from_words(words: list[dict], duration: float,
                      refine=None) -> tuple[float, float]:
    # Song-end candidates, from two kinds of anchor (sung text is unreliable):
    #  1. the sung "Praise and honor..." itself -> song ends at its last word
    #  2. the pastor's spoken cue "The Gospel of Christ" -> song ends at the
    #     first word after a silence in the transcript (Whisper drops singing)
    cands = [(a, b + config.START_PAD, a) for a, b, _ in find_phrase(words, config.START_PHRASE)]
    for a, b, _ in find_phrase(words, config.START_CUE_PHRASE, config.START_CUE_THRESHOLD):
        nxt = song_end_after(words, b)
        if nxt is not None:
            cands.append((a, nxt, b))
    if not cands:
        raise RuntimeError("no start anchor found (sung response or spoken cue)")
    cands.sort()
    first_anchor = cands[0][0]
    # END: first offering line after the first start anchor.
    ends = find_phrase(words, config.END_PHRASE, after=first_anchor)
    if not ends:
        raise RuntimeError(f"end phrase not found: {config.END_PHRASE!r}")
    end = ends[0][0] - config.END_PAD            # cut just before it is spoken
    # START: song ends of the last anchor before the end phrase (the response
    # may repeat, so take the last).
    ok = [c for c in cands if c[1] < end]
    start = ok[-1][1]
    if refine is not None:
        # The full-file transcript can attach the song's last words to speech.
        # Re-listen to a short window after the anchor, with VAD, and use the
        # first word actually spoken.
        t = refine(ok[-1][2], min(end, ok[-1][2] + config.REFINE_WINDOW_SECONDS))
        if t is not None and t < end:
            start = t - config.START_PAD
    if not (0 <= start < end <= duration + 1) or end - start < config.MIN_SERMON_SECONDS:
        raise RuntimeError(f"implausible bounds {start:.1f}-{end:.1f}s")
    return start, min(end, duration)


def find_sermon_bounds(audio: Path, duration: float) -> tuple[float, float]:
    """Return (start_seconds, end_seconds) of the sermon.
    Raises on failure so the recording goes to failed/ instead of being
    published with a wrong cut."""
    return bounds_from_words(transcribe(audio), duration,
                             refine=lambda a, b: first_spoken_word(audio, a, b))


def _text(words, a, b):
    return " ".join(w["word"] for w in words if a - 0.01 <= w["start"] <= b + 0.01)


if __name__ == "__main__":
    # Dry run, touches nothing:  python3 detect.py recording.wav
    import sys
    import audio
    f = Path(sys.argv[1])
    ws = transcribe(f)
    print(f"{len(ws)} words transcribed")
    for label, ph in (("START", config.START_PHRASE), ("CUE", config.START_CUE_PHRASE), ("END", config.END_PHRASE)):
        for a, b, sc in find_phrase(ws, ph, config.START_CUE_THRESHOLD if label == "CUE" else None):
            print(f"{label} hit {a:8.1f}-{b:8.1f}s score {sc:.2f}: {_text(ws, a, b)}")
    try:
        st, en = bounds_from_words(ws, audio.duration(f),
                                   refine=lambda a, b: first_spoken_word(f, a, b))
        print(f"CHOSEN: {st:.1f}s -> {en:.1f}s  ({(en - st) / 60:.1f} min)")
    except RuntimeError as e:
        print("FAILED:", e)
