"""Check MiniMaxH3VideoVAE.tiled_decode against a separable overlap-add reference (CPU only).

Run inside the h3-spark image (no GPU, no weights, no ComfyUI server):

  docker run --rm --entrypoint python -v "$PWD/deploy/patches:/t:ro" -w /opt/ComfyUI \
    h3-spark:local /t/test_h3_vae_tile_blend.py

Each fake tile decodes to a smooth global image plus a tile-specific constant, so
neighbouring tiles disagree inside their overlaps. Correct blending (upstream
ComfyUI fc584aaa / #16436) equals sum_i sum_j wy_i(y) * wx_j(x) * tile_ij with the
same linear ramps `blend` uses. The pre-fix loop leaves a step where a vertical and
a horizontal overlap cross. Pass --expect-bug to assert the unpatched loop is wrong.
"""

import sys

EXPECT_BUG = "--expect-bug" in sys.argv[1:]
sys.argv = [sys.argv[0], "--cpu"]  # ComfyUI probes CUDA at import unless --cpu is parsed
sys.path.insert(0, "/opt/ComfyUI")

import comfy.options  # noqa: E402

comfy.options.enable_args_parsing()

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from comfy.ldm.minimax.vae import MiniMaxH3VideoVAE  # noqa: E402

RATIO = 16


def make_vae():
    vae = MiniMaxH3VideoVAE.__new__(MiniMaxH3VideoVAE)
    nn.Module.__init__(vae)
    vae.vae_ratio = RATIO
    vae.tile_size = 256
    vae.tile_overlap_min = 64

    def fake_decode(zt):
        # zt[:, 0] / zt[:, 1] carry global latent row / col; build pixels from them.
        rows = zt[0, 0, 0, :, 0]
        cols = zt[0, 1, 0, 0, :]
        y = (rows[0] * RATIO + torch.arange(len(rows) * RATIO, dtype=torch.float64))
        x = (cols[0] * RATIO + torch.arange(len(cols) * RATIO, dtype=torch.float64))
        base = torch.sin(y[:, None] / 37.0) + torch.cos(x[None, :] / 53.0)
        offset = 0.25 * float(rows[0]) + 0.5 * float(cols[0]) / 7.0  # differs per tile
        img = base + offset
        return img.expand(1, 3, zt.shape[2], *img.shape).clone()

    vae._decode_pixels = fake_decode
    return vae, fake_decode


def latent(h, w, t=2):
    z = torch.zeros(1, 24, t, h, w, dtype=torch.float64)
    z[:, 0] = torch.arange(h, dtype=torch.float64)[:, None]
    z[:, 1] = torch.arange(w, dtype=torch.float64)[None, :]
    return z


def ramps(n, idx, lens, overlaps, k):
    w = torch.ones(lens[k], dtype=torch.float64)
    if k > 0:
        o = overlaps[k - 1]
        w[:o] = torch.arange(o, dtype=torch.float64) / o
    if k < len(idx) - 1:
        o = overlaps[k]
        w[-o:] = 1 - torch.arange(o, dtype=torch.float64) / o
    return w


def reference(vae, decode, z):
    height, width = z.shape[-2] * RATIO, z.shape[-1] * RATIO
    y_idx, y_len, y_ov = vae.split_tiles(height)
    x_idx, x_len, x_ov = vae.split_tiles(width)
    out = torch.zeros(1, 3, z.shape[2], height, width, dtype=torch.float64)
    for i, (yp, yl) in enumerate(zip(y_idx, y_len)):
        wy = ramps(height, y_idx, y_len, y_ov, i)
        for j, (xp, xl) in enumerate(zip(x_idx, x_len)):
            wx = ramps(width, x_idx, x_len, x_ov, j)
            tile = decode(z[..., yp // RATIO:(yp + yl) // RATIO, xp // RATIO:(xp + xl) // RATIO])
            out[..., yp:yp + yl, xp:xp + xl] += wy[:, None] * wx[None, :] * tile
    return out


def main():
    worst = 0.0
    for h, w in ((34, 60), (48, 84), (60, 34)):  # 544x960, 768x1344, portrait 960x544
        vae, decode = make_vae()
        z = latent(h, w)
        got = vae.tiled_decode(z)
        ref = reference(vae, decode, z)
        err = float((got - ref).abs().max())
        worst = max(worst, err)
        print(f"{h * RATIO}x{w * RATIO}: max |tiled_decode - overlap_add| = {err:.3e}")
    if EXPECT_BUG:
        assert worst > 1e-3, "expected the unpatched decode to differ from the reference"
        print("OK: unpatched decode shows seam steps")
    else:
        assert worst < 1e-9, f"tiled_decode does not match the overlap-add reference ({worst})"
        print("OK: tiled_decode matches the separable overlap-add reference")


if __name__ == "__main__":
    main()
