import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((ROOT / "workflows" / name).read_text())


def prompt_graph(doc: dict) -> dict:
    if "prompt" in doc and isinstance(doc["prompt"], dict):
        doc = doc["prompt"]
    nodes = [v for v in doc.values() if isinstance(v, dict)]
    assert nodes and all("class_type" in n for n in nodes), (
        "workflow must be ComfyUI API format for POST /prompt, not UI nodes/links"
    )
    return doc


def int_inputs(graph: dict, key: str) -> list[int]:
    out = []
    for node in prompt_graph(graph).values():
        if not isinstance(node, dict):
            continue
        val = (node.get("inputs") or {}).get(key)
        if isinstance(val, int):
            out.append(val)
    return out


def test_smoke_frames_and_canvas():
    g = load("h3-fl2va-smoke-5s17.json")
    assert 960 in int_inputs(g, "width")
    assert 544 in int_inputs(g, "height")
    assert 124 in int_inputs(g, "length")
    assert 192 not in int_inputs(g, "length")
    raw = json.dumps(g)
    assert "1920" in raw and "1088" in raw


def test_default_frames():
    g = load("h3-fl2va-default-8s.json")
    assert 192 in int_inputs(g, "length")
    assert 124 not in int_inputs(g, "length")
    assert 960 in int_inputs(g, "width")
    assert 8 in int_inputs(g, "steps")


def test_forbidden_and_required_strings():
    span = next(
        line.strip()
        for line in (ROOT / "scripts" / "required-weights.txt").read_text().splitlines()
        if line.startswith("upscale_models/")
    )
    span_name = Path(span).name
    for name in ("h3-fl2va-smoke-5s17.json", "h3-fl2va-default-8s.json"):
        raw = (ROOT / "workflows" / name).read_text()
        g = load(name)
        assert 8 in int_inputs(g, "steps")
        for bad in (
            "EasyCache",
            "flex_attention",
            "lowvram",
            "<Picture ",
            "ref2va",
            "MiniMaxH3ReferenceToVideo",
            "nvfp4",
            "minimax_h3_fl2va_pruned_int8_convrot",
        ):
            assert bad not in raw, bad
        assert "triton_ref" in raw
        assert "H3 Safe" in raw or "H3Safe" in raw or "h3_safe" in raw
        assert "ModelSamplingAV" in raw
        assert "minimax_h3_fl2va_pruned_fp8_scaled" in raw
        assert "qwen3vl_32b_minimax_h3_int8_convrot" in raw
        assert span_name in raw
