#!/usr/bin/env python3
"""Submit a locked ComfyUI API-format workflow; poll /history; print OUTPUT.

Patched node input names (scalars only; ComfyUI links like ["4", 0] are skipped):

  text, prompt         <- --prompt
  seed                 <- --seed
  filename_prefix      <- --name
  first_frame          <- --first-frame
  last_frame           <- --last-frame

Host keyframe paths under $H3_DATA or $HOME/h3-data are rewritten to /data/<rel>
in the posted graph. The printed OUTPUT path is always a host path under
--output-root / $H3_OUTPUT / $HOME/h3-output (never /opt/ComfyUI/output/...).

Does not start Docker or ComfyUI. The server must already be up.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Iterable

# Free fields only. Canvas / frames / steps / checkpoint names stay locked.
PROMPT_KEYS = ("text", "prompt")
SEED_KEYS = ("seed",)
NAME_KEYS = ("filename_prefix",)
FIRST_FRAME_KEYS = ("first_frame",)
LAST_FRAME_KEYS = ("last_frame",)

# Realistic ComfyUI history outputs are lists of {filename, subfolder, type}.
# Do not parse outputs[id]["filename"] as a string list.
MEDIA_KEYS = ("videos", "gifs", "images")

POLL_INTERVAL_S = 2
POLL_TIMEOUT_S = 3600
HTTP_TIMEOUT_S = 60


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


def _data_roots() -> list[str]:
    roots: list[str] = []
    env = os.environ.get("H3_DATA")
    if env:
        roots.append(os.path.realpath(os.path.expanduser(env)))
    roots.append(os.path.realpath(os.path.join(os.path.expanduser("~"), "h3-data")))
    seen: set[str] = set()
    unique: list[str] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def rewrite_keyframe_path(host_path: str) -> str:
    """Map a host path under the data mount to /data/<rel>; leave others as-is."""
    if not host_path:
        return host_path
    if host_path == "/data" or host_path.startswith("/data/"):
        return host_path
    expanded = os.path.realpath(os.path.abspath(os.path.expanduser(host_path)))
    for root in _data_roots():
        try:
            common = os.path.commonpath([expanded, root])
        except ValueError:
            continue
        if common != root:
            continue
        rel = os.path.relpath(expanded, root)
        if rel == ".":
            return "/data"
        return "/data/" + rel.replace(os.sep, "/")
    return host_path


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


def _first_media(entry: dict[str, Any]) -> dict[str, Any] | None:
    outputs = entry.get("outputs") or {}
    if not isinstance(outputs, dict):
        return None
    for kind in MEDIA_KEYS:
        for node_out in outputs.values():
            if not isinstance(node_out, dict):
                continue
            items = node_out.get(kind)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("filename"):
                    return item
    return None


def host_output_path(output_root: str, item: dict[str, Any]) -> str:
    filename = str(item["filename"])
    subfolder = item.get("subfolder") or ""
    return os.path.abspath(os.path.join(output_root, subfolder, filename))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("workflow", help="API-format ComfyUI workflow JSON")
    parser.add_argument("--prompt", required=True, help="Free-field text prompt")
    parser.add_argument("--seed", required=True, type=int, help="Free-field seed")
    parser.add_argument("--name", required=True, help="filename_prefix (Save node)")
    parser.add_argument("--first-frame", default=None, help="Optional host first-frame image")
    parser.add_argument("--last-frame", default=None, help="Optional host last-frame image")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI origin (default http://127.0.0.1:8188)",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Host output dir (default $H3_OUTPUT or $HOME/h3-output)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    graph = load_api_graph(args.workflow)
    output_root = args.output_root or default_output_root()
    base = args.base_url.rstrip("/")

    _patch_existing_scalars(graph, PROMPT_KEYS, args.prompt)
    _patch_existing_scalars(graph, SEED_KEYS, args.seed)
    _patch_existing_scalars(graph, NAME_KEYS, args.name)
    if args.first_frame:
        patched = _patch_existing_scalars(
            graph, FIRST_FRAME_KEYS, rewrite_keyframe_path(args.first_frame)
        )
        if patched == 0:
            print(
                "error: --first-frame set but the graph has no scalar "
                "first_frame input to patch (missing or linked)",
                file=sys.stderr,
            )
            return 1
    if args.last_frame:
        patched = _patch_existing_scalars(
            graph, LAST_FRAME_KEYS, rewrite_keyframe_path(args.last_frame)
        )
        if patched == 0:
            print(
                "error: --last-frame set but the graph has no scalar "
                "last_frame input to patch (missing or linked)",
                file=sys.stderr,
            )
            return 1

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

    deadline = time.monotonic() + POLL_TIMEOUT_S
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
                print(f"OUTPUT {host_output_path(output_root, item)}")
                return 0
            if (entry.get("status") or {}).get("completed"):
                print(raw)
                return 1
        if time.monotonic() >= deadline:
            print(f"timeout after {POLL_TIMEOUT_S}s waiting for /history/{prompt_id}", file=sys.stderr)
            return 1
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
