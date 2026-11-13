"""Offline tests for the skill's scripts. Run: python3 -m pytest -q .claude/skills/h3-make-video/tests

watch_progress.py runs against a fake ComfyUI (HTTP + a minimal websocket) on 127.0.0.1.
review_video.py needs OpenCV and a real video, so it is exercised on the Spark instead (see SKILL.md).
"""
import base64
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import lint_prompt  # noqa: E402

GOOD = """subject_definitions:
<Subject 1> is the red fox in <Picture 1> and <Picture 2>: a slim fox with rust-red fur, a white chest, and black legs.

summary:
[reference generation] <Subject 1> trots across a snowy field and stops to listen.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - rust-red fur, white chest, black legs.

detailed_description:
The target video is live-action nature footage in soft winter daylight.
[Shot 1] A wide shot shows <Subject 1>, the rust-red fox with a white chest and black legs, trotting left to right. {filler}
[Shot 2] At 00:04.000, the camera cuts to a medium shot of <Subject 1>, the rust-red fox, standing still with ears up. {filler}

overall_soundscape:
Wind over snow and the soft crunch of paws.

non_diegetic_music:
N/A
"""
FILLER = " ".join(["The snow sparkles under a pale sky while the fox keeps moving."] * 15)


def good(**kw):
    return GOOD.format(filler=FILLER, **kw)


def run_lint(text, duration=8.0, refs=2):
    return lint_prompt.check(text, duration, refs)


def test_lint_accepts_a_well_formed_prompt():
    errors, warnings, notes = run_lint(good())
    assert errors == []
    assert not any("words" in w for w in warnings)


@pytest.mark.parametrize("mutate, needle", [
    (lambda t: t.replace("[Shot 2] At 00:04.000, the camera", "[Shot 2] The camera"), "must start 'At MM:SS.mmm"),
    (lambda t: t.replace("00:04.000", "00:09.000"), "not inside the 8.00 s clip"),
    (lambda t: t.replace("[Shot 1] A wide", "[Shot 1] At 00:00.500, a wide"), "must not carry a timestamp"),
    (lambda t: t.replace("<Picture 2>", "<Picture 3>"), "only 2 still(s)"),
    (lambda t: t.replace("[reference generation]", "[reference gen]"), "unknown task type"),
    (lambda t: t.replace("fully_preserved -", "kept -"), "needs ': <marker> - ...'"),
    (lambda t: t.replace("non_diegetic_music:\nN/A", "non_diegetic_music:"), "is empty"),
    (lambda t: t.replace("standing still", "standing still (S1) says: <d>Hello.</d>"), "without a [Language] tag"),
    (lambda t: t.replace("trotting left", "trotting past <Subject 2> left"), "<Subject 2> is used but has no definition"),
    (lambda t: t.replace("summary:", "SUMMARY:"), "missing section 'summary:'"),
])
def test_lint_catches(mutate, needle):
    errors, _, _ = run_lint(mutate(good()))
    assert any(needle in e for e in errors), errors


def test_lint_warns_on_quotes_and_filler_and_length():
    t = good().replace("standing still", 'standing still beside a sign reading "EXIT", a stunning view')
    _, warnings, _ = run_lint(t)
    assert any('quoted text "EXIT"' in w for w in warnings)
    assert any("filler word 'stunning'" in w for w in warnings)
    short = GOOD.format(filler="")
    _, warnings, _ = run_lint(short)
    assert any("normally 350-500" in w for w in warnings)


@pytest.mark.parametrize("mutate, needle", [
    (lambda t: t.replace("trotting left", "trotting past <Subject1> left"), "malformed label '<Subject1>'"),
    (lambda t: t.replace("<Picture 2>", "<Picture 0>"), "labels are 1-based"),
    (lambda t: t.replace("fully_preserved -", "fully_preserved - also [Shot 7];"), "appears in [Shot 7]"),
    (lambda t: t.replace("Wind over snow", "<d>[English] Hello.</d> Wind over snow"), "dialogue inside 'overall_soundscape:'"),
    (lambda t: t.replace("00:04.000", "00:64.000"), "seconds >= 60"),
    (lambda t: t.replace("[Shot 2] At 00:04.000, the camera cuts to a medium shot of <Subject 1>, the rust-red fox,",
                         "[Shot 2] At 00:04.000, the camera cuts to a medium shot of the fox,"), None),
])
def test_lint_catches_more(mutate, needle):
    errors, _, _ = run_lint(mutate(good()))
    if needle is None:   # removing <Subject 1> from shot 2 only is legal
        assert errors == [], errors
    else:
        assert any(needle in e for e in errors), errors


def test_lint_subject_with_stills_must_appear_in_the_description():
    t = good().replace(
        "summary:",
        "<Subject 2> is the grey owl in <Picture 2>: round face.\n\nsummary:").replace(
        "<Picture 1> and <Picture 2>", "<Picture 1>").replace(
        "retention_analysis:\n", "retention_analysis:\n<Subject 2> (appears in [Shot 2]): fully_preserved - round face.\n")
    errors, _, _ = run_lint(t)
    assert any("<Subject 2> has stills but never appears" in e for e in errors), errors


def test_lint_no_false_positives_on_legal_forms():
    t = good()
    # bulleted definition / retention lines, a <Video> cited inside a subject line, a back-reference
    t = t.replace("<Subject 1> is the red fox in <Picture 1> and <Picture 2>:",
                  "- <Subject 1> is the red fox in <Picture 1> and <Picture 2>, whose trot comes from <Video 1>:")
    t = t.replace("<Subject 1> (appears in", "- <Subject 1> (appears in")
    t = t.replace("standing still with ears up.", "standing still with ears up, in the same field as in [Shot 1].")
    # the same quote twice -> one warning; a quote inside dialogue -> none
    t = t.replace("white chest, and black legs.", 'white chest, and black legs, with a "W"-shaped marking and a "W"-shaped marking.')
    t = t.replace("standing still", 'standing still (S1) and says: <d>[English] Look, "snow".</d> Then standing still')
    errors, warnings, _ = run_lint(t)
    assert errors == [], errors
    assert sum('quoted text "W"' in w for w in warnings) == 1, warnings
    assert not any('"snow"' in w for w in warnings), warnings


def test_lint_keyframe_alignment_marks():
    base = ("How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with "
            "the {t}-second mark of the target video.\n\nintegrated_multimodal_description: [Shot 1] A glass "
            "falls.\n\noverall_soundscape: A crash.\n\nnon_diegetic_music: N/A\n")
    errors, warnings, _ = lint_prompt.check(base.format(t="6.00"), 8.0, None)
    assert errors == [] and any("normally aligns with the clip end" in w for w in warnings)
    errors, _, _ = lint_prompt.check(base.format(t="9.00"), 8.0, None)
    assert any("beyond the 8.00 s clip" in e for e in errors)


# ---------- fake ComfyUI for watch_progress.py ----------

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class Fake:
    queue = {"queue_running": [], "queue_pending": []}
    history = {}
    events = []          # websocket text frames to send, one every 0.2 s
    fail_queue = 0       # answer this many /queue requests with HTTP 500 first
    ws_connections = 0


def graph(prefix):
    return {"23": {"class_type": "SaveVideo", "inputs": {"filename_prefix": prefix}}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/ws":
            Fake.ws_connections += 1
            key = self.headers["Sec-WebSocket-Key"]
            accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            try:
                for ev in Fake.events:
                    data = json.dumps(ev).encode()
                    self.wfile.write(bytes([0x81, len(data)]) + data)   # all test frames are < 126 bytes
                    self.wfile.flush()
                    time.sleep(0.2)
                time.sleep(5)
            except OSError:
                pass
            self.close_connection = True
        elif path == "/queue":
            if Fake.fail_queue > 0:
                Fake.fail_queue -= 1
                self.send_error(500)
                return
            self._json(Fake.queue)
        elif path.startswith("/history/"):
            pid = path.rsplit("/", 1)[1]
            self._json({pid: Fake.history[pid]} if pid in Fake.history else {})
        elif path == "/history":
            n = int(self.path.split("max_items=")[1]) if "max_items=" in self.path else None
            items = sorted(Fake.history.items(), key=lambda kv: kv[1]["prompt"][0])
            self._json(dict(items[-n:] if n else items))
        else:
            self.send_error(404)


@pytest.fixture()
def server():
    Fake.queue = {"queue_running": [], "queue_pending": []}
    Fake.history, Fake.events, Fake.fail_queue, Fake.ws_connections = {}, [], 0, 0
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def watch(url, *args, window="1.5"):
    r = subprocess.run([sys.executable, str(SCRIPTS / "watch_progress.py"), "--url", url, "--window", window, *args],
                       capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout.strip(), r.stderr


def test_watch_reports_step_and_rate(server):
    Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {}, ["23"]]]
    Fake.events = [{"type": "progress", "data": {"value": v, "max": 25, "prompt_id": "abc123", "node": "15"}}
                   for v in (1, 2, 3, 4)]
    code, out, err = watch(server, "--name", "dance", "--started", str(time.time() - 300))
    assert code == 0, (out, err)
    assert "STATE running" in out and "prompt=abc123" in out
    assert "node 15 step 4/25" in out
    assert "s/step" in out and "ETA" in out
    assert "elapsed 5 min" in out


def test_watch_ignores_other_jobs_progress(server):
    Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {}, ["23"]]]
    Fake.events = [{"type": "progress", "data": {"value": 9, "max": 30, "prompt_id": "other", "node": "3"}},
                   {"type": "progress", "data": {"value": 2, "max": 25, "prompt_id": "abc123", "node": "15"}}]
    code, out, _ = watch(server, "--name", "dance", window="1.5")
    assert code == 0 and "step 9/30" not in out and "step 2/25" in out, out
    assert Fake.ws_connections == 1


def test_watch_done_exits_early(server):
    Fake.history["abc123"] = {"prompt": [7, "abc123", graph("dance"), {}, ["23"]],
                              "outputs": {"23": {"images": [{"filename": "dance_00001_.mp4", "subfolder": "",
                                                             "type": "output"}]}},
                              "status": {"status_str": "success", "completed": True, "messages": []}}
    t0 = time.time()
    code, out, _ = watch(server, "--name", "dance", window="20")
    assert code == 0 and "STATE done" in out and "dance_00001_.mp4" in out
    assert time.time() - t0 < 10


def test_watch_error(server):
    Fake.history["abc123"] = {"prompt": [7, "abc123", graph("dance"), {}, ["23"]], "outputs": {},
                              "status": {"status_str": "error", "completed": False, "messages": [
                                  ["execution_error", {"node_id": "15", "node_type": "SamplerCustomAdvanced",
                                                       "exception_message": "CUDA out of memory"}]]}}
    code, out, _ = watch(server, "--prompt-id", "abc123")
    assert code == 1 and "STATE error" in out and "CUDA out of memory" in out


def test_watch_queued_and_missing(server):
    Fake.queue = {"queue_running": [[6, "zzz", graph("other"), {}, ["23"]]],
                  "queue_pending": [[7, "abc123", graph("dance"), {}, ["23"]]]}
    code, out, _ = watch(server, "--name", "dance", window="0.5")
    assert code == 0 and "STATE queued" in out and "1 job(s) ahead" in out
    Fake.queue = {"queue_running": [], "queue_pending": []}
    code, out, _ = watch(server, "--name", "dance", window="0.5")
    assert code == 4 and "STATE missing" in out


def test_watch_unreachable():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    code, out, _ = watch(f"http://127.0.0.1:{port}", "--name", "dance", window="0.5")
    assert code == 5 and "STATE unreachable" in out


def test_watch_foreign_interrupt_is_not_ours(server):
    Fake.queue = {"queue_running": [[6, "zzz", graph("other"), {}, ["23"]]],
                  "queue_pending": [[7, "abc123", graph("dance"), {}, ["23"]]]}
    Fake.events = [{"type": "execution_interrupted", "data": {"prompt_id": "zzz", "node_id": "15"}}]
    code, out, _ = watch(server, "--name", "dance", window="1.5")
    assert code == 0 and "STATE queued" in out, out


def test_watch_own_interrupt(server):
    Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {}, ["23"]]]
    Fake.events = [{"type": "execution_interrupted", "data": {"prompt_id": "abc123", "node_id": "15"}}]
    code, out, _ = watch(server, "--name", "dance", window="5")
    assert code == 1 and "STATE error" in out and "interrupted" in out, out
    Fake.queue["queue_running"] = []
    Fake.events = []
    Fake.history["abc123"] = {"prompt": [7, "abc123", graph("dance"), {}, ["23"]], "outputs": {},
                              "status": {"status_str": "error", "completed": False, "messages": [
                                  ["execution_interrupted", {"node_id": "15", "node_type": "SamplerCustomAdvanced"}]]}}
    code, out, _ = watch(server, "--prompt-id", "abc123")
    assert code == 1 and "interrupted at SamplerCustomAdvanced node 15" in out, out


def test_watch_waits_for_the_job_to_be_queued(server):
    def later():
        time.sleep(2.5)
        Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {"create_time": int(time.time() * 1000)}, ["23"]]]
    threading.Thread(target=later, daemon=True).start()
    code, out, _ = watch(server, "--name", "dance", "--wait-queued", "10", "--started", str(time.time()), window="5")
    assert code == 0 and "STATE running" in out, out


def test_watch_ignores_an_older_job_with_the_same_name(server):
    old = int((time.time() - 3600) * 1000)
    Fake.history["old111"] = {"prompt": [3, "old111", graph("dance"), {"create_time": old}, ["23"]],
                              "outputs": {"23": {"images": [{"filename": "dance_00001_.mp4", "subfolder": ""}]}},
                              "status": {"status_str": "success", "completed": True, "messages": []}}
    code, out, _ = watch(server, "--name", "dance", "--wait-queued", "1", "--started", str(time.time()), window="3")
    assert code == 4 and "STATE missing" in out and "old111" not in out, out


def test_watch_survives_a_transient_http_500(server):
    Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {}, ["23"]]]
    Fake.fail_queue = 1
    code, out, _ = watch(server, "--name", "dance", window="1.0")
    assert code == 0 and "STATE running" in out, out


def test_watch_last_step_says_decoding(server):
    Fake.queue["queue_running"] = [[7, "abc123", graph("dance"), {}, ["23"]]]
    Fake.events = [{"type": "progress", "data": {"value": v, "max": 25, "prompt_id": "abc123", "node": "15"}}
                   for v in (24, 25)]
    code, out, _ = watch(server, "--name", "dance", window="1.5")
    assert code == 0 and "step 25/25" in out and "decoding" in out and "ETA" not in out, out
