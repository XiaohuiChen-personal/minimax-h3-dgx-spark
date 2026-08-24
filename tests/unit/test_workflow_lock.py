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


REF2VA_GRAPHS = (
    "h3-ref2va-smoke-5s17.json",
    "h3-ref2va-default-8s.json",
    "h3-ref2va-long-15s08.json",
)

REF2VA_PREFIX = {
    "h3-ref2va-smoke-5s17.json": "h3-ref2va-smoke",
    "h3-ref2va-default-8s.json": "h3-ref2va",
    "h3-ref2va-long-15s08.json": "h3-ref2va-15s08",
}

# Nodes copied from the FL2VA template and not allowed to drift (Sage / Sol-Attn / FBC / SPAN).
REF2VA_TEMPLATE_LOCK = tuple(
    str(i) for i in (*range(2, 5), *range(6, 10), 11, 12, *range(14, 23))
)


def span_checkpoint_name() -> str:
    span = next(
        line.strip()
        for line in (ROOT / "scripts" / "required-weights.txt").read_text().splitlines()
        if line.startswith("upscale_models/")
    )
    return Path(span).name


def links_to_load_image(val, load_ids: set[str]) -> bool:
    if isinstance(val, list) and len(val) == 2 and str(val[0]) in load_ids:
        return True
    if isinstance(val, dict):
        return any(links_to_load_image(inner, load_ids) for inner in val.values())
    return False


def test_ref2va_smoke_default_and_long():
    smoke = load("h3-ref2va-smoke-5s17.json")
    default = load("h3-ref2va-default-8s.json")
    long = load("h3-ref2va-long-15s08.json")
    span_name = span_checkpoint_name()
    assert 124 in int_inputs(smoke, "length")
    assert 192 not in int_inputs(smoke, "length")
    assert 362 not in int_inputs(smoke, "length")
    assert 192 in int_inputs(default, "length")
    assert 124 not in int_inputs(default, "length")
    assert 362 not in int_inputs(default, "length")
    assert 362 in int_inputs(long, "length")
    assert 124 not in int_inputs(long, "length")
    assert 192 not in int_inputs(long, "length")
    assert 360 not in int_inputs(long, "length")
    assert 361 not in int_inputs(long, "length")
    for name in REF2VA_GRAPHS:
        raw = (ROOT / "workflows" / name).read_text()
        g = load(name)
        assert 960 in int_inputs(g, "width")
        assert 544 in int_inputs(g, "height")
        assert 4 in int_inputs(g, "steps")
        assert 8 not in int_inputs(g, "steps")
        assert 360 not in int_inputs(g, "length")
        assert 361 not in int_inputs(g, "length")
        assert "MiniMaxH3ReferenceToVideo" in raw
        assert "minimax_h3_ref2va_pruned_fp8_scaled" in raw
        assert "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16" in raw
        assert "qwen3vl_32b_minimax_h3_int8_convrot" in raw
        assert "triton_ref" in raw
        assert "H3 Safe" in raw or "H3Safe" in raw
        assert "ModelSamplingAV" in raw
        assert span_name in raw
        for i in range(1, 7):
            assert f"<Picture {i}>" in raw
        for bad in (
            "EasyCache",
            "flex_attention",
            "lowvram",
            "nvfp4",
            "15.04",
            "15.00",
            "10.00",
            "minimax_h3_fl2va_pruned_fp8_scaled",
            "minimax_h3_fl2v_turbo_8step",
            "minimax_h3_ref2va_pruned_int8_convrot",
            "MiniMaxH3ImageToVideo",
        ):
            assert bad not in raw, bad
        titles = [
            (node.get("_meta") or {}).get("title")
            for node in prompt_graph(g).values()
            if node.get("class_type") == "LoadImage"
        ]
        assert titles == [f"ref_image_{i}" for i in range(6)]
        prefixes = [
            (node.get("inputs") or {}).get("filename_prefix")
            for node in prompt_graph(g).values()
            if "filename_prefix" in (node.get("inputs") or {})
        ]
        assert prefixes == [REF2VA_PREFIX[name]]
        ref2va_nodes = [
            node
            for node in prompt_graph(g).values()
            if node.get("class_type") == "MiniMaxH3ReferenceToVideo"
        ]
        assert len(ref2va_nodes) == 1
        ref_inputs = ref2va_nodes[0].get("inputs") or {}
        assert "ref_images" not in ref_inputs
        assert ref_inputs.get("ref_image_size") == "match"
        assert ref_inputs.get("clip") == ["2", 0]
        assert ref_inputs.get("vae") == ["3", 0]
        assert ref_inputs.get("audio_vae") == ["4", 0]
        assert "first_frame" not in ref_inputs
        assert "last_frame" not in ref_inputs
        load_ids = set()
        for nid, node in prompt_graph(g).items():
            if node.get("class_type") != "LoadImage":
                continue
            load_ids.add(str(nid))
            assert (node.get("inputs") or {}).get("image") == "example.png"
        assert load_ids
        for nid, node in prompt_graph(g).items():
            for val in (node.get("inputs") or {}).values():
                assert not links_to_load_image(val, load_ids), (name, nid)
        for key in ref_inputs:
            # ref_image_size is required; flat autogrow and dotted ref_images.* stay out of git.
            assert key == "ref_image_size" or not str(key).startswith("ref_image_"), key
            assert not str(key).startswith("ref_images"), key


def test_ref2va_kernel_chain_matches_fl2va_template():
    template = prompt_graph(load("h3-fl2va-default-8s.json"))
    for name in REF2VA_GRAPHS:
        g = prompt_graph(load(name))
        for nid in REF2VA_TEMPLATE_LOCK:
            assert g[nid] == template[nid], (name, nid)


def test_fl2va_graphs_still_forbid_ref2va():
    for name in ("h3-fl2va-smoke-5s17.json", "h3-fl2va-default-8s.json"):
        raw = (ROOT / "workflows" / name).read_text()
        assert "MiniMaxH3ReferenceToVideo" not in raw
        assert "ref2va" not in raw
        assert "<Picture " not in raw
