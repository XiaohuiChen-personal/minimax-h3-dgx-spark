#!/usr/bin/env python3
"""Sharpen an already-rendered mp4 after the fact (renders made before the fast graphs had ImageSharpen).

Spark, system python3 (PyAV + OpenCV, CPU), writes only under /tmp/h3-review/. Sharpens the luma plane with the
same kernel as ComfyUI's ImageSharpen, leaves chroma untouched (an RGB round trip shifted colour by ~3/255
before), copies the colour tags and encodes H.264 CRF 16. The output has no audio: add it with mux_audio.py.

  ssh spark-2a60 "python3 - ~/h3-output/<file> /tmp/h3-review/<name>-sharp/<name>-sharp-video.mp4 1 1.0 0.1" < sharpen_video.py

Measured 2026-11-17 on 《布布的天鹅湖》's upscaled test: Yier's outline index 3.10 -> 3.52 (native 3.52),
mean colour shift <= 0.16/255. Prefer re-rendering through the shipped fast graph, which sharpens in-graph.
"""
import sys, os, av, cv2, numpy as np
if len(sys.argv) != 6:
    sys.exit("usage: sharpen_video.py SRC.mp4 DST.mp4 RADIUS SIGMA ALPHA   (fast-graph default: 1 1.0 0.1)")
src, dst, r, sigma, alpha = os.path.expanduser(sys.argv[1]), sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
dst = os.path.realpath(dst)
if not dst.startswith("/tmp/h3-review/"):
    sys.exit("error: write only under /tmp/h3-review/ (AGENTS.md)")
os.makedirs(os.path.dirname(dst), exist_ok=True)
k = 2*r+1; ax = np.arange(k) - r; g = np.exp(-(ax[:, None]**2 + ax[None, :]**2) / (2*sigma**2)); g /= g.sum()
ker = (g * -(alpha*10)).astype(np.float32); ker[r, r] = ker[r, r] - ker.sum() + 1.0
inp = av.open(src); vin = inp.streams.video[0]; cc = vin.codec_context
out = av.open(dst, "w"); vs = out.add_stream("libx264", rate=vin.average_rate or 24)
vs.width, vs.height, vs.pix_fmt = cc.width, cc.height, "yuv420p"; vs.options = {"crf": "16"}
for attr in ("color_range", "colorspace", "color_primaries", "color_trc"):
    try: setattr(vs.codec_context, attr, getattr(cc, attr))
    except Exception as e: print("tag", attr, "not copied:", e)
n = 0
for fr in inp.decode(vin):
    a = fr.to_ndarray(format="yuv420p").copy(); H = fr.height
    y = a[:H].astype(np.float32)
    a[:H] = np.clip(cv2.filter2D(y, -1, ker, borderType=cv2.BORDER_REFLECT), 0, 255).round().astype(np.uint8)
    nf = av.VideoFrame.from_ndarray(a, format="yuv420p")
    for attr in ("color_range", "colorspace"):
        try: setattr(nf, attr, getattr(fr, attr))
        except Exception: pass
    nf.pts = None
    for p in vs.encode(nf): out.mux(p)
    n += 1
for p in vs.encode(None): out.mux(p)
out.close(); inp.close(); print("wrote", dst, n, "frames; tags", {a: getattr(cc, a, None) for a in ("color_range", "colorspace", "color_primaries", "color_trc")})
