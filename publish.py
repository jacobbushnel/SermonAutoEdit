"""Upload an edited sermon to Buzzsprout as a new episode.

Flow (per Buzzsprout's API docs): create private episode -> start upload ->
PUT bytes -> complete upload -> optionally publish.

Credentials come from environment variables or a git-ignored `.env` file next
to this script:
    BUZZSPROUT_API_TOKEN=...      (Buzzsprout: Profile -> API)
    BUZZSPROUT_PODCAST_ID=...     (numeric id of your podcast)

Manual / retry use:  python3 publish.py "path/to/sermon.m4a" ["Episode title"]
"""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config

USER_AGENT = "SermonAutoEdit/1.0"
MIME = {".m4a": "audio/mp4", ".mp4": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}
LEDGER = Path(__file__).resolve().parent / "published.json"   # avoids duplicate uploads


def _load_env() -> dict:
    env = dict(os.environ)
    f = Path(__file__).resolve().parent / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def _call(method, url, token=None, body=None, raw=None, headers=None):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Token token={token}"
    data = raw
    if body is not None:
        h["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body).encode()
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            txt = r.read().decode() or "{}"
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        path = urllib.parse.urlsplit(url).path       # no query strings / signed URLs
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
    try:
        return json.loads(txt)
    except ValueError:
        return {}


def publish(path: Path, title: str | None = None, description: str = "") -> dict:
    env = _load_env()
    token, pid = env.get("BUZZSPROUT_API_TOKEN"), env.get("BUZZSPROUT_PODCAST_ID")
    if not token or not pid:
        raise RuntimeError("set BUZZSPROUT_API_TOKEN and BUZZSPROUT_PODCAST_ID "
                           "(env vars or .env file)")
    base = env.get("BUZZSPROUT_BASE", "https://www.buzzsprout.com")
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    entry = ledger.get(path.name, {})
    if entry.get("done"):
        raise RuntimeError(f"{path.name} was already uploaded (episode {entry['id']})")

    def save(**kw):
        ledger[path.name] = {**ledger.get(path.name, {}), **kw}
        LEDGER.write_text(json.dumps(ledger, indent=2))

    title = title or path.stem
    if entry.get("id"):          # earlier attempt failed midway: reuse its draft
        eid = entry["id"]
    else:
        ep = _call("POST", f"{base}/api/{pid}/episodes", token,
                   {"title": title, "description": description, "private": True})
        eid = ep["id"]
        save(id=eid, done=False)  # remember it before anything can fail
    data = path.read_bytes()
    mime = MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    up = _call("POST", f"{base}/api/{pid}/episodes/{eid}/uploads", token,
               {"filename": path.name, "type": mime, "byte_size": len(data)})["upload"]
    uid = urllib.parse.quote(str(up["id"]), safe="")
    try:
        # No Buzzsprout auth header on the storage PUT.
        _call("PUT", up["upload_url"], raw=data, headers={"Content-Type": mime})
        _call("POST", f"{base}/api/{pid}/episodes/{eid}/uploads/{uid}/complete", token)
    except Exception:
        try:
            _call("DELETE", f"{base}/api/{pid}/episodes/{eid}/uploads/{uid}/abort", token)
        except Exception:
            pass
        raise
    save(done=True)
    live = False
    if config.PUBLISH_LIVE:
        # Encoding is asynchronous; only publish once duration is positive.
        deadline = time.monotonic() + config.ENCODE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            dur = _call("GET", f"{base}/api/{pid}/episodes/{eid}", token).get("duration", -1)
            if isinstance(dur, int) and dur > 0:
                _call("PATCH", f"{base}/api/{pid}/episodes/{eid}", token, {"private": False})
                live = True
                break
            time.sleep(config.ENCODE_POLL_SECONDS)
        else:
            print(f"encoding not finished after {config.ENCODE_TIMEOUT_SECONDS}s; "
                  f"episode {eid} left as a private draft - publish it in Buzzsprout")
    return {"id": eid, "live": live}


if __name__ == "__main__":
    import urllib.parse  # noqa: F401  (used above; imported here for CLI clarity)
    res = publish(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
    print("uploaded:", res)
