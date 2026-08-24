"""Unit tests for scripts/submit-prompt.py against a mock ComfyUI (no GPU)."""

from __future__ import annotations

import json
import os
import re
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
                    {
                        "filename": "history-name.mp4",
                        "subfolder": "clips",
                        "type": "output",
                    }
                ]
            }
        },
    }
}


def _multipart_filename(body: bytes) -> str:
    text = body.decode("latin-1")
    quoted = re.search(r'filename="([^"]+)"', text)
    if quoted:
        return os.path.basename(quoted.group(1))
    bare = re.search(r"filename=([^;\r\n]+)", text)
    if bare:
        return os.path.basename(bare.group(1).strip().strip('"'))
    return ""


class MockComfyServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.posted: list[object] = []
        self.uploads: list[str] = []
        self.upload_status = 200
        self.history_gets = 0
        self.history_error = False
        self.history_payload = SUCCESS_HISTORY


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
        if path == "/upload/image":
            filename = _multipart_filename(body)
            self.server.uploads.append(filename)
            status = getattr(self.server, "upload_status", 200)
            self._send_json(
                status,
                {"name": filename, "subfolder": "", "type": "input"},
            )
            return
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
                self._send_json(200, self.server.history_payload)
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
    expected = str(output_root.resolve() / "clips" / "history-name.mp4")
    stdout = result.stdout.strip()
    assert stdout == f"OUTPUT {expected}"
    assert stdout.endswith("history-name.mp4")
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
    assert _input_values(graph, "filename_prefix") == ["unit"]
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

    host_out = str(output_root.resolve() / "clips" / "history-name.mp4")
    assert "OUTPUT" in result.stdout
    assert host_out in result.stdout
    assert result.stdout.strip().endswith("history-name.mp4")
    assert "/opt/ComfyUI/output" not in result.stdout


def test_first_frame_flag_fails_when_graph_has_no_first_frame(tmp_path, mock_comfy):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["1"]["inputs"].pop("first_frame", None)
    workflow = tmp_path / "no-first-frame.json"
    workflow.write_text(json.dumps(data), encoding="utf-8")

    output_root = tmp_path / "out"
    output_root.mkdir()
    first = tmp_path / "face.png"
    first.write_bytes(b"x")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(workflow),
            "--prompt",
            "hello",
            "--seed",
            "7",
            "--name",
            "unit",
            "--first-frame",
            str(first),
            "--base-url",
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert result.returncode != 0
    assert "OUTPUT" not in result.stdout
    assert mock_comfy.posted == []


def test_history_error_prints_body_and_exits(tmp_path, mock_comfy):
    mock_comfy.history_error = True
    port = mock_comfy.server_address[1]
    result, _output_root, _workflow = _run_submit(tmp_path, port)
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "history failed" in combined
    assert "OUTPUT" not in result.stdout


def test_patches_noise_seed_on_official_random_noise_graph(tmp_path, mock_comfy):
    """Official H3 graphs seed via RandomNoise.noise_seed, not KSampler.seed."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["2"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": 0}}
    workflow = tmp_path / "noise-seed.json"
    workflow.write_text(json.dumps(data), encoding="utf-8")

    output_root = tmp_path / "out"
    output_root.mkdir()
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert mock_comfy.posted
    graph = mock_comfy.posted[0]["prompt"]
    assert _input_values(graph, "noise_seed") == [7]
    assert _input_values(graph, "seed") == []


def test_seed_flag_fails_when_graph_has_no_seed(tmp_path, mock_comfy):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["2"]["inputs"].pop("seed", None)
    workflow = tmp_path / "no-seed.json"
    workflow.write_text(json.dumps(data), encoding="utf-8")

    output_root = tmp_path / "out"
    output_root.mkdir()
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert result.returncode != 0
    assert "OUTPUT" not in result.stdout
    assert mock_comfy.posted == []


def test_history_prefers_output_mp4_over_input_or_temp_images(tmp_path, mock_comfy):
    """Official SaveVideo emits images+animated; LoadImage/Preview use the same key."""
    mock_comfy.history_payload = {
        "abc": {
            "status": {"status_str": "success", "completed": True},
            "outputs": {
                "5": {
                    "images": [
                        {"filename": "first.png", "subfolder": "", "type": "input"}
                    ]
                },
                "8": {
                    "images": [
                        {
                            "filename": "ComfyUI_temp_abc_00001_.png",
                            "subfolder": "",
                            "type": "temp",
                        }
                    ]
                },
                "9": {
                    "images": [
                        {
                            "filename": "unit_00001_.mp4",
                            "subfolder": "video",
                            "type": "output",
                        }
                    ],
                    "animated": [True],
                },
            },
        }
    }
    port = mock_comfy.server_address[1]
    result, output_root, _workflow = _run_submit(tmp_path, port)
    assert result.returncode == 0, result.stderr + result.stdout
    expected = str(output_root.resolve() / "video" / "unit_00001_.mp4")
    assert result.stdout.strip() == f"OUTPUT {expected}"
    assert "first.png" not in result.stdout
    assert "ComfyUI_temp" not in result.stdout
    assert "/opt/ComfyUI/output" not in result.stdout


def test_ref_images_upload_and_nested_wiring(tmp_path, mock_comfy):
    workflow = tmp_path / "tiny-ref2va-workflow.json"
    shutil.copy(REPO / "tests/fixtures/tiny-ref2va-workflow.json", workflow)
    output_root = tmp_path / "out"
    output_root.mkdir()
    img0 = tmp_path / "blue.png"
    img1 = tmp_path / "yellow.png"
    img0.write_bytes(b"x")
    img1.write_bytes(b"y")
    port = mock_comfy.server_address[1]
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), str(workflow),
            "--prompt", "<Picture 1> blue bird. <Picture 2> yellow bird.",
            "--seed", "7", "--name", "unit",
            "--base-url", f"http://127.0.0.1:{port}",
            "--output-root", str(output_root),
            "--ref-image", str(img0), "--ref-image", str(img1),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    graph = mock_comfy.posted[0]["prompt"]
    assert graph["24"]["inputs"]["image"] == "blue.png"
    assert graph["25"]["inputs"]["image"] == "yellow.png"
    assert graph["10"]["inputs"]["ref_images"] == {
        "ref_image_0": ["24", 0],
        "ref_image_1": ["25", 0],
    }
    assert "ref_image_0" not in graph["10"]["inputs"]
    assert mock_comfy.uploads == ["blue.png", "yellow.png"]


def test_ref_image_fails_on_fl2va_fixture_without_loadimage(tmp_path, mock_comfy):
    img = tmp_path / "blue.png"
    img.write_bytes(b"x")
    port = mock_comfy.server_address[1]
    result, _output_root, _workflow = _run_submit(
        tmp_path, port, extra=["--ref-image", str(img)]
    )
    combined = (result.stderr + result.stdout).lower()
    assert result.returncode != 0
    assert result.returncode == 1
    assert "ref-image" in combined
    assert "unrecognized arguments" not in combined
    assert not mock_comfy.posted


def test_ref_image_fails_when_not_enough_loadimage_titles(tmp_path, mock_comfy):
    data = json.loads(
        (REPO / "tests/fixtures/tiny-ref2va-workflow.json").read_text(encoding="utf-8")
    )
    del data["25"]
    workflow = tmp_path / "one-ref.json"
    workflow.write_text(json.dumps(data), encoding="utf-8")
    output_root = tmp_path / "out"
    output_root.mkdir()
    img0 = tmp_path / "blue.png"
    img1 = tmp_path / "yellow.png"
    img0.write_bytes(b"x")
    img1.write_bytes(b"y")
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
            "--ref-image",
            str(img0),
            "--ref-image",
            str(img1),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "ref-image" in (result.stderr + result.stdout).lower()
    assert not mock_comfy.posted
    assert mock_comfy.uploads == []


def test_ref_image_fails_when_upload_not_200(tmp_path, mock_comfy):
    mock_comfy.upload_status = 500
    workflow = tmp_path / "tiny-ref2va-workflow.json"
    shutil.copy(REPO / "tests/fixtures/tiny-ref2va-workflow.json", workflow)
    output_root = tmp_path / "out"
    output_root.mkdir()
    img = tmp_path / "blue.png"
    img.write_bytes(b"x")
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
            "--ref-image",
            str(img),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "ref-image" in (result.stderr + result.stdout).lower()
    assert not mock_comfy.posted


def test_ref_image_rejects_more_than_nine(tmp_path, mock_comfy):
    workflow = tmp_path / "tiny-ref2va-workflow.json"
    shutil.copy(REPO / "tests/fixtures/tiny-ref2va-workflow.json", workflow)
    output_root = tmp_path / "out"
    output_root.mkdir()
    extras = []
    for i in range(10):
        img = tmp_path / f"ref{i}.png"
        img.write_bytes(b"x")
        extras.extend(["--ref-image", str(img)])
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
            *extras,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "ref-image" in (result.stderr + result.stdout).lower()
    assert not mock_comfy.posted
    assert mock_comfy.uploads == []


def test_ref_image_deletes_flat_keys_keeps_ref_image_size(tmp_path, mock_comfy):
    data = json.loads(
        (REPO / "tests/fixtures/tiny-ref2va-workflow.json").read_text(encoding="utf-8")
    )
    data["10"]["inputs"]["ref_image_0"] = ["24", 0]
    data["10"]["inputs"]["ref_image_1"] = "should-be-removed"
    workflow = tmp_path / "flat-keys.json"
    workflow.write_text(json.dumps(data), encoding="utf-8")
    output_root = tmp_path / "out"
    output_root.mkdir()
    img0 = tmp_path / "blue.png"
    img1 = tmp_path / "yellow.png"
    img0.write_bytes(b"x")
    img1.write_bytes(b"y")
    result = subprocess.run(
        [
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
            f"http://127.0.0.1:{mock_comfy.server_address[1]}",
            "--output-root",
            str(output_root),
            "--ref-image",
            str(img0),
            "--ref-image",
            str(img1),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    graph = mock_comfy.posted[0]["prompt"]
    inputs = graph["10"]["inputs"]
    assert inputs["ref_image_size"] == "match"
    assert "ref_image_0" not in inputs
    assert "ref_image_1" not in inputs
    assert inputs["ref_images"] == {
        "ref_image_0": ["24", 0],
        "ref_image_1": ["25", 0],
    }
    assert str(tmp_path / "blue.png") not in json.dumps(graph)
    assert "/data/" not in graph["24"]["inputs"]["image"]
    assert "/data/" not in graph["25"]["inputs"]["image"]
