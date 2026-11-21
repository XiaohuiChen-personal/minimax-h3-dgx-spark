"""The ComfyUI pin is fixed (D-11); the H3 VAE tile-blend fix is upstream and still tested in the build."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / "deploy" / "patches" / "test_h3_vae_tile_blend.py"
PIN = "a277b5bf213e8a44fa34817b7770b54f86ef4cea"  # ComfyUI v0.46.0


def test_pin_is_recorded_in_dockerfile_and_compose():
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text()
    compose = (ROOT / "deploy" / "compose.yaml").read_text()
    assert f"ARG COMFYUI_SHA={PIN}" in dockerfile
    assert f"COMFYUI_SHA: {PIN}" in compose
    assert "b78cec879b9460d5cb25228a83a942fb78d2cd24" not in dockerfile + compose


def test_vae_tile_blend_regression_test_runs_in_build():
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text()
    assert "COPY deploy/patches /opt/h3/patches" in dockerfile
    assert "python /opt/h3/patches/test_h3_vae_tile_blend.py" in dockerfile
    # fc584aaa is upstream in the pin: nothing is patched any more, and the fixed loop must be there.
    assert "patch -p1" not in dockerfile
    assert "grep -q 'Tiles blend against' comfy/ldm/minimax/vae.py" in dockerfile
    assert not (ROOT / "deploy" / "patches" / "comfyui-h3-vae-tile-blend.patch").exists()
    # Late layer: after the expensive SageAttention / torchaudio builds, before COPY scripts.
    assert dockerfile.index("test_h3_vae_tile_blend.py") > dockerfile.index("torchaudio-2.9.0")
    assert dockerfile.index("test_h3_vae_tile_blend.py") < dockerfile.index("COPY scripts /opt/h3/scripts")
    assert TEST.is_file()


def test_tile_blend_fake_decoder_handles_batched_tiles():
    # upstream v0.46 decodes up to 4 tiles per call; a batch-1 fake would break chunk() silently
    text = TEST.read_text()
    assert "for b in range(zt.shape[0])" in text


def test_dockerignore_keeps_patches_in_build_context():
    ignored = (ROOT / ".dockerignore").read_text().split()
    assert "deploy" not in ignored and "deploy/" not in ignored and "deploy/patches" not in ignored
