#!/usr/bin/env python3
"""Submit a ComfyUI API-format workflow; poll /history; print OUTPUT.

Patched node input names (scalars only; ComfyUI links like ["4", 0] are skipped):

  text, prompt         <- --prompt / --prompt-file
  seed, noise_seed     <- --seed  (KSampler.seed or RandomNoise.noise_seed)
  filename_prefix      <- --name
  LoadImage.image      <- --ref-image / --first-frame / --last-frame
                          (uploaded via POST /upload/image; never a host path)
  MiniMaxH3ReferenceToVideo.ref_images      <- nested dict from --ref-image
  MiniMaxH3ImageToVideo.first_frame / last_frame
                       <- link to the LoadImage titled first_frame / last_frame

Works on the Spark (default http://127.0.0.1:8188) and from another machine
(--base-url or $H3_COMFY_URL, e.g. http://spark-2a60:8188 over Tailscale).
Uploads go over HTTP, so local files work in both cases. When the server is
remote, or the mp4 is not already under --output-root, the mp4 is downloaded
with GET /view into --output-root. OUTPUT is always a real local path
(never /opt/ComfyUI/output/...).

Does not start Docker or ComfyUI. The server must already be up.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

# Free fields only. Canvas / frames / steps / checkpoint names stay locked.
PROMPT_KEYS = ("text", "prompt")
SEED_KEYS = ("seed", "noise_seed")
NAME_KEYS = ("filename_prefix",)
REF2VA_CLASS = "MiniMaxH3ReferenceToVideo"
I2V_CLASS = "MiniMaxH3ImageToVideo"
KEYFRAME_KEYS = ("first_frame", "last_frame")
MAX_REF_IMAGES = 9
REF_IMAGE_TITLE_RE = re.compile(r"^ref_image_(\d+)$")
FLAT_REF_IMAGE_KEY_RE = re.compile(r"^ref_image_\d+$")
# The H3 tokenizer prefixes each attached still with "<Picture N>: " (1-based).
PICTURE_TAG_RE = re.compile(r"<Picture\s+(\d+)>")

DEFAULT_BASE_URL = "http://127.0.0.1:8188"
LOOPBACK_HOSTS = ("localhost", "::1")

# Realistic ComfyUI history outputs are lists of {filename, subfolder, type}.
# Official SaveVideo PreviewVideo uses images + animated, not a videos key.
# Do not parse outputs[id]["filename"] as a string list.
MEDIA_KEYS = ("videos", "gifs", "images")
VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")

POLL_INTERVAL_S = 2
POLL_TIMEOUT_S = 3600
HTTP_TIMEOUT_S = 60
DOWNLOAD_CHUNK = 1 << 20


def _is_link(value: Any) -> bool:
    return isinstance(value, list)


def _patch_existing_scalars(graph: dict[str, Any], keys: Iterable[str], value: Any) -> int:
    patched = 0
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key in keys:
            if key in inputs and not _is_link(inputs[key]):
                inputs[key] = value
                patched += 1
    return patched


def load_image_nodes_by_title(graph: dict[str, Any]) -> list[tuple[str, dict]]:
    """Return LoadImage nodes titled ref_image_N, sorted by the integer suffix."""
    found: list[tuple[int, str, dict]] = []
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "LoadImage":
            continue
        meta = node.get("_meta")
        title = meta.get("title") if isinstance(meta, dict) else None
        if not isinstance(title, str):
            continue
        match = REF_IMAGE_TITLE_RE.fullmatch(title)
        if not match:
            continue
        found.append((int(match.group(1)), str(node_id), node))
    found.sort(key=lambda item: item[0])
    return [(node_id, node) for _suffix, node_id, node in found]


def _nodes_of_class(graph: dict[str, Any], class_type: str) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for node_id, node in graph.items():
        if isinstance(node, dict) and node.get("class_type") == class_type:
            found.append((str(node_id), node))
    return found


def _ref2va_nodes(graph: dict[str, Any]) -> list[tuple[str, dict]]:
    return _nodes_of_class(graph, REF2VA_CLASS)


def _load_images_titled(graph: dict[str, Any], title: str) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for node_id, node in _nodes_of_class(graph, "LoadImage"):
        meta = node.get("_meta")
        if isinstance(meta, dict) and meta.get("title") == title:
            found.append((node_id, node))
    return found


def upload_input_image(base_url: str, host_path: str, flag: str = "--ref-image") -> str:
    """POST a local file to ComfyUI /upload/image. Return the JSON name."""
    expanded = os.path.abspath(os.path.expanduser(host_path))
    if not os.path.isfile(expanded):
        print(f"error: {flag} file not found: {host_path}", file=sys.stderr)
        raise SystemExit(1)
    filename = os.path.basename(expanded).replace('"', "_")
    with open(expanded, "rb") as fh:
        file_bytes = fh.read()
    boundary = "----H3RefImageBoundary" + os.urandom(16).hex()
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header + file_bytes + footer
    url = f"{base_url.rstrip('/')}/upload/image"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"error: {flag} upload failed: HTTP {exc.code}", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(1) from exc
    except urllib.error.URLError as exc:
        print(f"error: {flag} upload failed: {getattr(exc, 'reason', exc)}", file=sys.stderr)
        raise SystemExit(1) from exc
    if status != 200:
        print(f"error: {flag} upload failed: HTTP {status}", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(1)
    try:
        parsed: Any = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(f"error: {flag} upload did not return JSON", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(1)
    name = parsed.get("name") if isinstance(parsed, dict) else None
    if not name:
        print(f"error: {flag} upload response missing name", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(1)
    return str(name)


def wire_ref_images(graph: dict[str, Any], base_url: str, host_paths: list[str]) -> None:
    """Upload stills, patch LoadImage filenames, write nested ref_images. Fail-close."""
    if len(host_paths) > MAX_REF_IMAGES:
        print(f"error: --ref-image accepts at most {MAX_REF_IMAGES} paths", file=sys.stderr)
        raise SystemExit(1)
    load_nodes = load_image_nodes_by_title(graph)
    if len(load_nodes) < len(host_paths):
        print(
            "error: --ref-image set but the graph does not have enough "
            f"LoadImage nodes titled ref_image_* (need {len(host_paths)}, "
            f"found {len(load_nodes)})",
            file=sys.stderr,
        )
        raise SystemExit(1)
    ref2va_nodes = _ref2va_nodes(graph)
    if len(ref2va_nodes) != 1:
        print(
            "error: --ref-image set but the graph does not have exactly one "
            f"{REF2VA_CLASS} node",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _node_id, ref_node = ref2va_nodes[0]
    inputs = ref_node.get("inputs")
    if not isinstance(inputs, dict):
        print(
            f"error: --ref-image set but {REF2VA_CLASS} inputs are invalid",
            file=sys.stderr,
        )
        raise SystemExit(1)
    nested: dict[str, list[Any]] = {}
    for index, host_path in enumerate(host_paths):
        load_id, load_node = load_nodes[index]
        uploaded_name = upload_input_image(base_url, host_path)
        load_inputs = load_node.setdefault("inputs", {})
        if not isinstance(load_inputs, dict):
            print(
                f"error: --ref-image LoadImage node {load_id} has invalid inputs",
                file=sys.stderr,
            )
            raise SystemExit(1)
        load_inputs["image"] = uploaded_name
        nested[f"ref_image_{index}"] = [load_id, 0]
    for key in list(inputs):
        if FLAT_REF_IMAGE_KEY_RE.fullmatch(str(key)):
            del inputs[key]
    inputs["ref_images"] = nested


def wire_keyframe(graph: dict[str, Any], base_url: str, key: str, host_path: str) -> None:
    """Upload a first/last-frame still and link it into MiniMaxH3ImageToVideo. Fail-close.

    The native node input is an IMAGE socket, so the graph must carry a LoadImage
    titled exactly like the input (first_frame / last_frame). Default text-only
    graphs do not, so the flag fails there on purpose. Ref2VA graphs have no
    MiniMaxH3ImageToVideo node: identity stills are --ref-image, not keyframes.
    """
    flag = "--" + key.replace("_", "-")
    i2v_nodes = _nodes_of_class(graph, I2V_CLASS)
    if len(i2v_nodes) != 1:
        print(
            f"error: {flag} set but the graph does not have exactly one {I2V_CLASS} node "
            "(keyframes are FL2VA-only; Ref2VA identity stills use --ref-image)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    load_nodes = _load_images_titled(graph, key)
    if len(load_nodes) != 1:
        print(
            f"error: {flag} set but the graph does not have exactly one LoadImage titled "
            f"{key} (use workflows/h3-fl2va-keyframes-8s.json or add one on a copy)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _i2v_id, i2v_node = i2v_nodes[0]
    i2v_inputs = i2v_node.setdefault("inputs", {})
    load_id, load_node = load_nodes[0]
    load_inputs = load_node.setdefault("inputs", {})
    if not isinstance(i2v_inputs, dict) or not isinstance(load_inputs, dict):
        print(f"error: {flag} target nodes have invalid inputs", file=sys.stderr)
        raise SystemExit(1)
    load_inputs["image"] = upload_input_image(base_url, host_path, flag=flag)
    i2v_inputs[key] = [load_id, 0]


def _drop_unwired_keyframe_scalars(graph: dict[str, Any]) -> None:
    """A scalar first_frame / last_frame on the IMAGE socket is never valid; drop it."""
    for _node_id, node in _nodes_of_class(graph, I2V_CLASS):
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key in KEYFRAME_KEYS:
            if key in inputs and not _is_link(inputs[key]):
                del inputs[key]


def check_picture_tags(prompt: str, graph: dict[str, Any], n_refs: int, n_keyframes: int) -> str | None:
    """Return an error if the prompt names a <Picture N> that no attached still backs.

    The H3 tokenizer labels attached stills "<Picture 1>", "<Picture 2>", ... in
    order: --ref-image order on Ref2VA, first_frame then last_frame on FL2VA.
    A label with no image behind it is an unresolved reference.
    """
    tags = sorted({int(m) for m in PICTURE_TAG_RE.findall(prompt)})
    if not tags:
        return None
    if _ref2va_nodes(graph):
        available, what = n_refs, "--ref-image"
    elif _nodes_of_class(graph, I2V_CLASS):
        available, what = n_keyframes, "--first-frame/--last-frame"
    else:
        return None
    bad = [n for n in tags if n < 1 or n > available]
    if not bad:
        return None
    return (
        f"error: prompt names <Picture {bad[0]}> but only {available} {what} "
        f"image(s) are attached; <Picture N> is 1-based in attach order"
    )


def default_output_root() -> str:
    return os.environ.get("H3_OUTPUT") or os.path.join(os.path.expanduser("~"), "h3-output")


def load_api_graph(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not data:
        raise SystemExit(f"workflow is not an API-format graph: {path}")
    if "nodes" in data and "links" in data:
        raise SystemExit("UI-format workflow (nodes/links) is not supported; need API format")
    if not all(isinstance(node, dict) and "class_type" in node for node in data.values()):
        raise SystemExit(f"workflow is not an API-format graph: {path}")
    return data


def http_json(method: str, url: str, payload: Any | None = None) -> tuple[int, str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8")
            try:
                parsed: Any = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                parsed = None
            return resp.status, raw, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = None
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            parsed = None
        return exc.code, raw, parsed
    except urllib.error.URLError as exc:
        print(str(getattr(exc, "reason", exc)), file=sys.stderr)
        raise SystemExit(1) from exc


def _history_entry(payload: Any, prompt_id: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    entry = payload.get(prompt_id)
    return entry if isinstance(entry, dict) else None


def _history_is_error(entry: dict[str, Any]) -> bool:
    status = entry.get("status") or {}
    if isinstance(status, dict) and status.get("status_str") == "error":
        return True
    messages = status.get("messages") if isinstance(status, dict) else None
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, (list, tuple)) and msg and msg[0] == "execution_error":
                return True
    return False


def _is_output_media(item: dict[str, Any]) -> bool:
    kind = item.get("type")
    return kind in (None, "", "output")


def _is_video_filename(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTS


def _first_media(entry: dict[str, Any]) -> dict[str, Any] | None:
    outputs = entry.get("outputs") or {}
    if not isinstance(outputs, dict):
        return None
    fallback = None
    for kind in MEDIA_KEYS:
        for node_out in outputs.values():
            if not isinstance(node_out, dict):
                continue
            items = node_out.get(kind)
            if not isinstance(items, list):
                continue
            for item in items:
                if not (isinstance(item, dict) and item.get("filename")):
                    continue
                if not _is_output_media(item):
                    continue
                if _is_video_filename(str(item["filename"])):
                    return item
                if fallback is None:
                    fallback = item
    return fallback


def host_output_path(output_root: str, item: dict[str, Any]) -> str:
    filename = str(item["filename"])
    subfolder = item.get("subfolder") or ""
    root = os.path.abspath(output_root)
    path = os.path.abspath(os.path.join(root, subfolder, filename))
    if os.path.commonpath([root, path]) != root:
        raise SystemExit(f"error: server output name escapes --output-root: {subfolder}/{filename}")
    return path


def default_base_url() -> str:
    return os.environ.get("H3_COMFY_URL") or DEFAULT_BASE_URL


def is_loopback(base_url: str) -> bool:
    host = (urllib.parse.urlsplit(base_url).hostname or "").lower()
    return host in LOOPBACK_HOSTS or host.startswith("127.")


def server_relpath(item: dict[str, Any]) -> str:
    subfolder = item.get("subfolder") or ""
    return "/".join(part for part in (subfolder, str(item["filename"])) if part)


def fetch_output(base_url: str, item: dict[str, Any], dest: str) -> None:
    """GET /view the finished file into dest (atomic). Skip if dest already matches."""
    query = urllib.parse.urlencode(
        {
            "filename": str(item["filename"]),
            "subfolder": item.get("subfolder") or "",
            "type": item.get("type") or "output",
        }
    )
    url = f"{base_url.rstrip('/')}/view?{query}"
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
            length = resp.headers.get("Content-Length")
            if length and os.path.isfile(dest) and os.path.getsize(dest) == int(length):
                return
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            part = dest + ".part"
            with open(part, "wb") as fh:
                while True:
                    chunk = resp.read(DOWNLOAD_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
            os.replace(part, dest)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"error: download {url} failed: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"error: download {url} failed: {getattr(exc, 'reason', exc)}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("workflow", help="API-format ComfyUI workflow JSON")
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt", help="Free-field text prompt (one string)")
    prompt.add_argument(
        "--prompt-file",
        help="Read the prompt from a UTF-8 file (use for multi-line structured H3 prompts)",
    )
    parser.add_argument("--seed", required=True, type=int, help="Free-field seed")
    parser.add_argument("--name", required=True, help="filename_prefix (Save node)")
    parser.add_argument(
        "--first-frame",
        default=None,
        help="Local first-frame still (FL2VA keyframe graphs only). Uploaded via POST /upload/image.",
    )
    parser.add_argument(
        "--last-frame",
        default=None,
        help="Local last-frame still (FL2VA keyframe graphs only). Uploaded via POST /upload/image.",
    )
    parser.add_argument(
        "--ref-image",
        action="append",
        default=None,
        help="Local identity still; repeatable (max 9). Uploaded via POST /upload/image.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"ComfyUI origin (default $H3_COMFY_URL or {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Local output dir (default $H3_OUTPUT or $HOME/h3-output)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=POLL_TIMEOUT_S,
        help=f"Seconds to wait for /history, including queue time (default {POLL_TIMEOUT_S})",
    )
    return parser.parse_args(argv)


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file is None:
        return args.prompt
    try:
        with open(os.path.expanduser(args.prompt_file), encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError as exc:
        raise SystemExit(f"error: --prompt-file: {exc}") from exc
    if not text:
        raise SystemExit("error: --prompt-file is empty")
    return text


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    graph = load_api_graph(args.workflow)
    output_root = args.output_root or default_output_root()
    base = (args.base_url or default_base_url()).rstrip("/")
    prompt = read_prompt(args)

    n_keyframes = sum(1 for path in (args.first_frame, args.last_frame) if path)
    error = check_picture_tags(prompt, graph, len(args.ref_image or []), n_keyframes)
    if error:
        print(error, file=sys.stderr)
        return 1

    _patch_existing_scalars(graph, PROMPT_KEYS, prompt)
    patched_seed = _patch_existing_scalars(graph, SEED_KEYS, args.seed)
    if patched_seed == 0:
        print(
            "error: --seed set but the graph has no scalar "
            "seed or noise_seed input to patch (missing or linked)",
            file=sys.stderr,
        )
        return 1
    _patch_existing_scalars(graph, NAME_KEYS, args.name)
    _drop_unwired_keyframe_scalars(graph)
    if args.first_frame:
        wire_keyframe(graph, base, "first_frame", args.first_frame)
    if args.last_frame:
        wire_keyframe(graph, base, "last_frame", args.last_frame)
    if args.ref_image:
        wire_ref_images(graph, base, args.ref_image)

    status, raw, parsed = http_json("POST", f"{base}/prompt", {"prompt": graph})
    if status != 200 or not isinstance(parsed, dict):
        print(raw)
        return 1
    node_errors = parsed.get("node_errors") or {}
    if node_errors:
        print(raw)
        return 1
    prompt_id = parsed.get("prompt_id")
    if not prompt_id:
        print(raw)
        return 1

    deadline = time.monotonic() + args.timeout
    while True:
        status, raw, parsed = http_json("GET", f"{base}/history/{prompt_id}")
        if status != 200 or not isinstance(parsed, dict):
            print(raw)
            return 1
        entry = _history_entry(parsed, str(prompt_id))
        if entry is not None:
            if _history_is_error(entry):
                print(raw)
                return 1
            item = _first_media(entry)
            if item is not None:
                local = host_output_path(output_root, item)
                remote = not is_loopback(base)
                if remote:
                    host = urllib.parse.urlsplit(base).hostname
                    # D-14 compose mounts the server's ~/h3-output as ComfyUI's output dir.
                    print(f"REMOTE_OUTPUT {host}:~/h3-output/{server_relpath(item)}", flush=True)
                if remote or not os.path.isfile(local):
                    fetch_output(base, item, local)
                print(f"OUTPUT {local}")
                return 0
            if (entry.get("status") or {}).get("completed"):
                print(raw)
                return 1
        if time.monotonic() >= deadline:
            print(
                f"timeout after {args.timeout}s waiting for /history/{prompt_id} "
                "(the job may still be queued or running on the server)",
                file=sys.stderr,
            )
            return 1
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
