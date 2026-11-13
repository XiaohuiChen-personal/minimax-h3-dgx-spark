#!/usr/bin/env python3
"""Watch one ComfyUI job for a fixed window, print ONE status line, exit. Built for 10-minute check-ins.

Run it in the background with --window 600 and relaunch it each time it exits while the job is still
running. It exits early when the job finishes, fails, or vanishes, so the last line is always the newest
state.

Where the numbers come from (ComfyUI b78cec87):
  - step progress: websocket "progress" events {value, max, prompt_id, node}. They reach every listener
    because submit-prompt.py queues without a client_id.
  - finished / failed: GET /history/<prompt_id>. With no client_id ComfyUI does NOT broadcast
    execution_success / execution_error, so the websocket alone cannot tell you the job ended.
    execution_interrupted IS broadcast, for every job, so it only counts when its prompt_id is ours.
  - running / pending: GET /queue. The job is found by --prompt-id, or by the SaveVideo filename_prefix
    that submit-prompt.py's --name wrote into the graph. With --started, jobs created before that time
    (extra_data.create_time, set by the server on POST /prompt) are ignored, so an older run with the
    same name cannot be mistaken for this one.

usage: watch_progress.py (--name NAME | --prompt-id ID) [--url URL] [--window 600] [--started EPOCH]
                         [--wait-queued 180]
Prints one line that starts with STATE <running|queued|done|error|missing|unreachable>.
exit 0 = running / queued / done, 1 = error, 4 = missing, 5 = unreachable (2 = bad arguments, argparse)
"""
import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

POLL_S = 15
HTTP_RETRIES = 3
CREATE_SLACK_MS = 120_000   # clocks of the two machines may differ a little
EXIT = {"done": 0, "running": 0, "queued": 0, "error": 1, "missing": 4, "unreachable": 5}


class Unreachable(Exception):
    pass


def http_json(url, timeout=10):
    """GET JSON with a few retries; raise Unreachable with a readable reason after the last one."""
    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = f"http {exc.code} from {url}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = f"{url}: {getattr(exc, 'reason', exc)}"
        if attempt < HTTP_RETRIES - 1:
            time.sleep(2 * (attempt + 1))
    raise Unreachable(last)


def graph_prefixes(graph):
    if not isinstance(graph, dict):
        return set()
    return {str(n.get("inputs", {}).get("filename_prefix")) for n in graph.values()
            if isinstance(n, dict) and "filename_prefix" in n.get("inputs", {})}


def is_ours(item, prompt_id, name, started_ms):
    """item = [number, prompt_id, graph, extra_data, outputs] (queue and history share the shape)."""
    pid = item[1] if len(item) > 1 else None
    if prompt_id:
        return pid == prompt_id
    graph = item[2] if len(item) > 2 else None
    if name not in graph_prefixes(graph):
        return False
    if started_ms is not None:
        extra = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
        created = extra.get("create_time")
        if isinstance(created, (int, float)) and created < started_ms - CREATE_SLACK_MS:
            return False
    return True


def find_in_queue(base, prompt_id, name, started_ms):
    """-> ('running'|'queued', prompt_id, jobs_ahead) or None."""
    q = http_json(f"{base}/queue")
    running = q.get("queue_running", [])
    for state, items in (("running", running), ("queued", q.get("queue_pending", []))):
        for pos, item in enumerate(sorted(items, key=lambda it: it[0])):
            if is_ours(item, prompt_id, name, started_ms):
                return state, item[1], pos + (len(running) if state == "queued" else 0)
    return None


def find_in_history(base, prompt_id, name, started_ms):
    """-> (prompt_id, entry) or None. By name, the newest matching entry wins."""
    if prompt_id:
        h = http_json(f"{base}/history/{urllib.parse.quote(prompt_id)}")
        return (prompt_id, h[prompt_id]) if prompt_id in h else None
    h = http_json(f"{base}/history?max_items=64")
    best = None
    for pid, entry in h.items():
        item = entry.get("prompt") or []
        if len(item) > 2 and is_ours(item, None, name, started_ms):
            num = item[0] if item else -1
            if best is None or num > best[0]:
                best = (num, pid, entry)
    return (best[1], best[2]) if best else None


def history_outcome(entry):
    """-> ('done', file) | ('error', message) | None while not finished."""
    status = entry.get("status") or {}
    for outputs in (entry.get("outputs") or {}).values():
        for key in ("images", "gifs", "videos"):
            for item in outputs.get(key) or []:
                if isinstance(item, dict) and item.get("filename"):
                    return "done", os.path.join(item.get("subfolder") or "", item["filename"])
    if status.get("status_str") == "error":
        for m in status.get("messages") or []:
            if not (isinstance(m, list) and m):
                continue
            d = m[1] if len(m) > 1 and isinstance(m[1], dict) else {}
            if m[0] == "execution_error":
                return "error", (f"{d.get('node_type', '?')} node {d.get('node_id', '?')}: "
                                 f"{str(d.get('exception_message', '')).strip()[:200]}")
            if m[0] == "execution_interrupted":
                return "error", f"interrupted at {d.get('node_type', '?')} node {d.get('node_id', '?')} (Cancel / interrupt)"
        return "error", "status_str=error"
    if status.get("completed"):
        return "error", "completed without a media output"
    return None


class Listener(threading.Thread):
    """Collect websocket progress / interrupt events in the background."""

    def __init__(self, ws_url):
        super().__init__(daemon=True)
        self.ws_url = ws_url
        self.events = []          # (time, value, max, node, prompt_id)
        self.interrupted = set()  # prompt_ids seen in execution_interrupted
        self.connected = False
        self.error = None
        self.stop = threading.Event()

    def run(self):
        try:
            import websocket  # websocket-client; present on the Spark and on this operator's MacBook
        except ImportError:
            self.error = "websocket-client not installed (pip install websocket-client); no step numbers"
            return
        try:
            ws = websocket.create_connection(self.ws_url, timeout=5)
        except Exception as exc:  # noqa: BLE001
            self.error = f"websocket connect failed: {exc}"
            return
        self.connected = True
        while not self.stop.is_set():
            try:
                msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:  # noqa: BLE001
                self.error = f"websocket closed: {exc}"
                return
            if isinstance(msg, bytes):
                continue          # preview images
            try:
                d = json.loads(msg)
            except ValueError:
                continue
            data = d.get("data") or {}
            if d.get("type") == "progress":
                self.events.append((time.time(), data.get("value"), data.get("max"), data.get("node"),
                                    data.get("prompt_id")))
            elif d.get("type") == "execution_interrupted" and data.get("prompt_id"):
                self.interrupted.add(data["prompt_id"])
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass


def fmt_min(sec):
    return f"{sec / 60:.0f} min" if sec >= 90 else f"{sec:.0f} s"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help="the --name given to submit-prompt.sh (SaveVideo filename_prefix)")
    g.add_argument("--prompt-id")
    p.add_argument("--url", default=os.environ.get("H3_COMFY_URL", "http://127.0.0.1:8188"))
    p.add_argument("--window", type=float, default=600.0, help="seconds to watch before reporting")
    p.add_argument("--started", type=float, help="unix time of the submit; enables elapsed time and ignores older jobs")
    p.add_argument("--wait-queued", type=float, default=0.0,
                   help="seconds to keep looking for the job before calling it missing (stills upload first)")
    p.add_argument("--decode-min", type=float, default=3.5, help="minutes added to the ETA after the last step")
    a = p.parse_args(argv)
    base = a.url.rstrip("/")
    started_ms = a.started * 1000 if a.started else None
    parts = urllib.parse.urlsplit(base)
    ws_url = urllib.parse.urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc, "/ws",
                                      f"clientId=h3-watch-{uuid.uuid4().hex[:8]}", ""))
    listener = Listener(ws_url)
    listener.start()
    t0 = time.time()
    t_end = t0 + a.window
    seen_deadline = t0 + a.wait_queued
    prompt_id, state, ahead, final = a.prompt_id, None, 0, None
    while True:
        try:
            hit = find_in_queue(base, prompt_id, a.name, started_ms)
            if hit:
                state, prompt_id, ahead = hit
            else:
                h = find_in_history(base, prompt_id, a.name, started_ms)
                if h:
                    prompt_id = h[0]
                    final = history_outcome(h[1])
                    if final is None:      # in history but unfinished should not happen; keep watching
                        state = "running"
                elif time.time() >= seen_deadline:
                    # Not queued and not in history. A finished job moves to history atomically, so one
                    # short re-check is enough before calling it missing.
                    time.sleep(3)
                    if not find_in_queue(base, prompt_id, a.name, started_ms) and \
                            not find_in_history(base, prompt_id, a.name, started_ms):
                        final = ("missing", "not in /queue or /history"
                                 + (f" after waiting {a.wait_queued:.0f} s" if a.wait_queued else ""))
                    else:
                        continue
                else:
                    state = state or "waiting"
        except Unreachable as exc:
            final = ("unreachable", str(exc))
        if final or (prompt_id and prompt_id in listener.interrupted) or time.time() >= t_end:
            break
        poll = POLL_S if state in ("running", "queued") else 3
        time.sleep(min(poll, max(0.0, t_end - time.time())))
    listener.stop.set()

    now_t = time.time()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    job = f" name={a.name}" if a.name else ""
    job += f" prompt={prompt_id[:8]}" if prompt_id else ""
    elapsed = f" | elapsed {fmt_min(now_t - a.started)}" if a.started else ""
    if not final and prompt_id and prompt_id in listener.interrupted:
        final = ("error", "execution_interrupted for this job (Cancel pressed, or the server interrupted it)")
    if not final and state == "waiting":
        final = ("missing", f"not queued yet after {a.window:.0f} s (raise --wait-queued, or check the submit task)")
    if final:
        kind, detail = final
        print(f"{now} STATE {kind} |{job}{elapsed} | {detail}", flush=True)
        return EXIT[kind]

    evs = [e for e in listener.events if e[4] in (None, prompt_id)]
    msg = f"{now} STATE {state} |{job}{elapsed}"
    if state == "queued":
        msg += f" | {ahead} job(s) ahead"
    if evs:
        t_last, value, mx, node, _ = evs[-1]
        msg += f" | node {node} step {value}/{mx} (seen {fmt_min(now_t - t_last)} ago)"
        same = [e for e in evs if e[3] == node and e[2] == mx]
        if value == mx:
            msg += " | sampling finished; decoding / saving"
        elif len(same) >= 2 and same[-1][1] != same[0][1]:
            rate = (same[-1][0] - same[0][0]) / (same[-1][1] - same[0][1])
            eta = max(0.0, (mx - value) * rate - (now_t - t_last)) + a.decode_min * 60
            msg += f" | {rate:.1f} s/step | ETA ~{fmt_min(eta)} incl. ~{a.decode_min:g} min decode"
    elif state == "running":
        msg += f" | no step event in the last {fmt_min(a.window)}"
        if a.window >= 300:
            msg += " (loading, encoding, or decoding - or stuck: check `docker logs` on the Spark)"
    if listener.error:
        msg += f" | {listener.error}"
    elif not listener.connected:
        msg += " | websocket never connected (no step numbers)"
    print(msg, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
