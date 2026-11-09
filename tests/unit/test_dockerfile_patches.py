"""The ComfyUI pin stays fixed; quality backports are applied and tested in the image build."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "deploy" / "patches" / "comfyui-h3-vae-tile-blend.patch"
TEST = ROOT / "deploy" / "patches" / "test_h3_vae_tile_blend.py"


def test_vae_tile_blend_patch_is_applied_and_tested_in_build():
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text()
    assert "COPY deploy/patches /opt/h3/patches" in dockerfile
    assert "patch -p1 --forward --fuzz=0 < /opt/h3/patches/comfyui-h3-vae-tile-blend.patch" in dockerfile
    assert "python /opt/h3/patches/test_h3_vae_tile_blend.py" in dockerfile
    # Late layer: after the expensive SageAttention / torchaudio builds, before COPY scripts.
    assert dockerfile.index("comfyui-h3-vae-tile-blend.patch") > dockerfile.index("torchaudio-2.9.0")
    assert dockerfile.index("comfyui-h3-vae-tile-blend.patch") < dockerfile.index("COPY scripts /opt/h3/scripts")
    # The pin itself does not move.
    assert "ARG COMFYUI_SHA=b78cec879b9460d5cb25228a83a942fb78d2cd24" in dockerfile


def test_vae_tile_blend_patch_targets_only_tiled_decode():
    text = PATCH.read_text()
    assert text.startswith("--- a/comfy/ldm/minimax/vae.py\n+++ b/comfy/ldm/minimax/vae.py\n")
    assert text.count("\n@@ ") + text.startswith("@@ ") == 1
    removed = [l for l in text.splitlines() if l.startswith("-") and not l.startswith("---")]
    added = [l for l in text.splitlines() if l.startswith("+") and not l.startswith("+++")]
    assert any("row_tails" in l for l in removed)
    assert not any("row_tails" in l for l in added)
    assert any("Backport of upstream ComfyUI fc584aaa" in l for l in added)
    assert TEST.is_file()


def test_dockerignore_keeps_patches_in_build_context():
    ignored = (ROOT / ".dockerignore").read_text().split()
    assert "deploy" not in ignored and "deploy/" not in ignored and "deploy/patches" not in ignored
