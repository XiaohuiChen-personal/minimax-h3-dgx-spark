"""Unit tests for scripts/submit-prompt.py against a mock ComfyUI (no GPU)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "submit-prompt.py"
FIXTURE = REPO / "tests" / "fixtures" / "tiny-workflow.json"

SUCCESS_HISTORY = {
    "abc": {
        "status": {"status_str": "success", "completed": True},
        "outputs": {
            "9": {
                "videos": [
                    {"filename": "tiny.mp4", "subfolder": "", "type": "output"}
                ]
            }
        },
    }
}


class MockComfyServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.posted: list[object] = []
        self.history_gets = 0
        self.history_error = False


class MockComfyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return

    def _send_json(self, status: int, payload: object) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/prompt":
            self.server.posted.append(json.loads(body.decode("utf-8")))
            self._send_json(
                200,
                {"prompt_id": "abc", "number": 1, "node_errors": {}},
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/history/abc":
            self.server.history_gets += 1
            if getattr(self.server, "history_error", False):
                self._send_json(500, {"error": "history failed"})
                return
            if self.server.history_gets == 1:
                self._send_json(200, {})
            else:
                self._send_json(200, SUCCESS_HISTORY)
            return
        self._send_json(404, {"error": "not found"})


@pytest.fixture
def mock_comfy():
    server = MockComfyServer(("127.0.0.1", 0), MockComfyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _input_values(graph: dict, key: str) -> list:
    found = []
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        if key in inputs:
            found.append(inputs[key])
    return found


def _run_submit(tmp_path: Path, port: int, extra: list[str] | None = None, env=None):
    workflow = tmp_path / "tiny-workflow.json"
    shutil.copy(FIXTURE, workflow)
    output_root = tmp_path / "out"
    output_root.mkdir()
    cmd = [
        sys.executable,
        str(SCRIPT),
        str(workflow),
        "--prompt",
        "hello",
        "--seed",
        "7",
        "--name",
        "unit",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--output-root",
        str(output_root),
    ]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env if env is not None else os.environ.copy(),
        check=False,
    )
    return result, output_root, workflow


def test_submit_prompt_prints_host_output_from_history(tmp_path, mock_comfy):
    port = mock_comfy.server_address[1]
    result, output_root, _workflow = _run_submit(tmp_path, port)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "OUTPUT" in result.stdout
    expected = str((output_root.resolve() / "tiny.mp4"))
    stdout = result.stdout.strip()
    assert stdout.endswith("tiny.mp4")
    assert expected in result.stdout

    assert mock_comfy.posted, "expected POST /prompt"
    body = mock_comfy.posted[0]
    assert isinstance(body, dict)
    assert "prompt" in body
    assert "nodes" not in body
    assert "links" not in body
    graph = body["prompt"]
    assert "hello" in _input_values(graph, "prompt") + _input_values(graph, "text")
    assert 7 in _input_values(graph, "seed")
    assert 960 in _input_values(graph, "width")
    assert mock_comfy.history_gets >= 2


def test_does_not_change_locked_canvas(tmp_path, mock_comfy):
    port = mock_comfy.server_address[1]
    result, _output_root, _workflow = _run_submit(tmp_path, port)
    assert result.returncode == 0, result.stderr + result.stdout
    graph = mock_comfy.posted[0]["prompt"]
    widths = _input_values(graph, "width")
    assert widths == [960]
    assert 544 in _input_values(graph, "height")
    assert all(steps == 8 for steps in _input_values(graph, "steps"))


def test_rewrites_keyframe_host_paths_to_data(tmp_path, mock_comfy):
    data_root = tmp_path / "h3-data"
    (data_root / "shots").mkdir(parents=True)
    first = data_root / "first.png"
    last = data_root / "shots" / "last.png"
    first.write_bytes(b"x")
    last.write_bytes(b"y")

    env = os.environ.copy()
    env["H3_DATA"] = str(data_root)

    port = mock_comfy.server_address[1]
    result, output_root, _workflow = _run_submit(
        tmp_path,
        port,
        extra=["--first-frame", str(first), "--last-frame", str(last)],
        env=env,
    )
    assert result.returncode == 0, result.stderr + result.stdout

    graph = mock_comfy.posted[0]["prompt"]
    assert _input_values(graph, "first_frame") == ["/data/first.png"]
    assert _input_values(graph, "last_frame") == ["/data/shots/last.png"]

    host_out = str((output_root.resolve() / "tiny.mp4"))
    assert "OUTPUT" in result.stdout
    assert host_out in result.stdout
    assert result.stdout.strip().endswith("tiny.mp4")
    assert "/opt/ComfyUI/output" not in result.stdout


def test_history_error_prints_body_and_exits(tmp_path, mock_comfy):
    mock_comfy.history_error = True
    port = mock_comfy.server_address[1]
    result, _output_root, _workflow = _run_submit(tmp_path, port)
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "history failed" in combined
    assert "OUTPUT" not in result.stdout
