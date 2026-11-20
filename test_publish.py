"""Run publish.py against a fake Buzzsprout server; checks the call sequence."""
import json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import config, publish

calls = []
state = {"polls": 0, "fail_put": False}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _do(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n)
        calls.append((self.command, self.path, self.headers.get("Authorization"), len(body)))
        out = {}
        if self.command == "GET":
            state["polls"] += 1; out = {"id": 42, "duration": -1 if state["polls"] < 2 else 1236}
            calls.append(("GET", self.path, None, 0)); self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(out).encode()); return
        if state["fail_put"] and self.path == "/store":
            self.send_response(403); self.end_headers(); self.wfile.write(b'{"error":{"code":"expired"}}'); return
        if self.path.endswith("/episodes"): out = {"id": 42}
        elif self.path.endswith("/uploads"):
            out = {"upload": {"id": "up/1", "upload_url": f"http://127.0.0.1:{self.server.server_port}/store"}}
        self.send_response(201 if self.command == "POST" else 200)
        self.end_headers(); self.wfile.write(json.dumps(out).encode())
    do_POST = do_PUT = do_PATCH = do_GET = do_DELETE = _do

srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update(BUZZSPROUT_API_TOKEN="tok", BUZZSPROUT_PODCAST_ID="7",
                  BUZZSPROUT_BASE=f"http://127.0.0.1:{srv.server_port}")
publish.LEDGER = Path(tempfile.mkdtemp()) / "published.json"
f = Path(tempfile.mkdtemp()) / "Test Sermon.m4a"; f.write_bytes(b"x" * 1234)
print(publish.publish(f))
for c in calls: print(c)
assert [c[0] for c in calls] == ["POST", "POST", "PUT", "POST"], calls
assert calls[2][2] is None and calls[2][3] == 1234          # storage PUT: no auth, exact bytes
assert calls[0][2] == "Token token=tok"
assert calls[3][1].endswith("/uploads/up%2F1/complete")
try: publish.publish(f); raise SystemExit("duplicate not blocked")
except RuntimeError as e: print("duplicate blocked:", e)
config.ENCODE_POLL_SECONDS = 0.01; config.PUBLISH_LIVE = True; f2 = f.with_name("Other.m4a"); f2.write_bytes(b"y"); publish.publish(f2)
seq = [c[0] for c in calls]; assert seq.index("PATCH") > max(i for i, m in enumerate(seq) if m == "GET") and state["polls"] == 2, seq
# failed upload: draft id is remembered, retry reuses it (no 2nd POST /episodes), abort was called
config.PUBLISH_LIVE = False; state["fail_put"] = True; f3 = f.with_name("Third.m4a"); f3.write_bytes(b"z")
n_create = sum(1 for c in calls if c[1].endswith("/episodes") and c[0] == "POST")
try: publish.publish(f3); raise SystemExit("should fail")
except RuntimeError as e: print("error shows body:", e); assert "expired" in str(e) and "HTTP 403" in str(e)
assert any(c[0] == "DELETE" and c[1].endswith("/abort") for c in calls)
state["fail_put"] = False; publish.publish(f3)
assert sum(1 for c in calls if c[1].endswith("/episodes") and c[0] == "POST") == n_create + 1   # one create across both tries
print("PASS")
