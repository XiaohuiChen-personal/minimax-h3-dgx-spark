#!/usr/bin/env python3
"""Stitch Masked-AV chain segments into one mp4 and measure every seam.

A chain-continue segment (workflows/h3-ref2va-maxq-chain-continue-1344.json) starts with the
previous segment's last CONTEXT frames, copied as latents and locked by denoise masks. So
segment B's frames [0, CONTEXT) re-show segment A's last CONTEXT frames, decoded a second time.

Stitching, for each pair A -> B, switching from A to B inside the overlap (S = switch point):
  video = A[: len(A) - CONTEXT + S - XF] + crossfade(XF frames) + B[S:]      (S = --video-switch, default
          the end of the overlap, so the picture switches where B's generated content begins)
  audio = A up to the same moment + crossfade(15 ms) + B from S             (S = --audio-switch, default
          the middle of the overlap: A's last ~0.2 s carry the audio decoder's end-of-clip fade)
Audio is placed on H3's 40 Hz latent ticks, not on the decoded length (AAC adds padding at the end).
The result has len(A) + len(B) - CONTEXT frames.

Writes, under OUTDIR:
  NAME.mp4            the stitched video (H.264 CRF 14 + AAC 192k, 24 fps)
  report.md / .json   per-seam numbers (below), per-segment drift, audio levels
  seam-K.jpg          stitched frames J-6 .. J+5 around seam K (J = first new frame of segment K+1)
  overlap-K.jpg       A's tail vs B's head at four overlap frames, with a x4 difference map

Seam numbers:
  overlap MAE         mean |A[-CONTEXT+i] - B[i]| (0-255) over the overlap; the locked latents are
                      identical, so this is the re-decode difference only (should be small)
  seam ratio          frame-to-frame change at the joint / median change in the 1 s on either side;
                      about 1 means the joint moves like any other frame, >2 is a visible jump
  motion before/after mean frame-to-frame change in the 1 s before vs after the joint (a freeze shows
                      as "after" much lower than "before")
  drift               per segment, over the frames each segment adds: mean luma, luma std (contrast),
                      Laplacian variance (sharpness), mean saturation; and A's last 1 s vs B's last 1 s
  audio               RMS in the 250 ms before/after the joint, largest sample step at the joint vs
                      the median step around it, and RMS of A-tail minus B-head over the overlap

Needs numpy + OpenCV + PyAV: the Spark's system python3 (CPU only). From the Mac, without copying:
  ssh spark-2a60 "python3 - OUTDIR NAME ~/h3-output/A_00001_.mp4 ~/h3-output/B_00001_.mp4" < stitch_segments.py
OUTDIR must be under /tmp/h3-review/ (AGENTS.md: review scripts write only there).

usage: stitch_segments.py OUTDIR NAME SEG1.mp4 SEG2.mp4 [SEG3.mp4 ...]
       [--context 39] [--xfade 4] [--audio-xfade-ms 15] [--crf 14]
"""
import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

SMALL_W = 240           # frame-difference metrics run on frames scaled to this width
AUDIO_LATENT_HZ = 40    # H3 audio latent ticks per second; the chain graph copies whole ticks


def latent_ticks(n_frames, fps):
    """Audio latent length H3 gives a clip of n_frames (round(frames / 24 * 40))."""
    return int(round(n_frames / fps * AUDIO_LATENT_HZ))


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("outdir")
    p.add_argument("name")
    p.add_argument("segments", nargs="+")
    p.add_argument("--context", type=int, default=39, help="locked context frames at the head of each later segment")
    p.add_argument("--xfade", type=int, default=4, help="video crossfade frames, inside the overlap")
    p.add_argument("--audio-xfade-ms", type=float, default=15.0)
    p.add_argument("--video-switch", type=float, default=1.0,
                   help="where inside the overlap the picture switches from A to B (0 = overlap start, "
                        "1 = overlap end, i.e. at B's first generated frame)")
    p.add_argument("--audio-switch", type=float, default=0.5,
                   help="where inside the overlap the sound switches from A to B; the default 0.5 avoids "
                        "the audio decoder's fade on A's last ~0.2 s (measured -36 dBFS on 2026-11-15)")
    p.add_argument("--no-audio-level-match", dest="audio_level_match", action="store_false",
                   help="keep B's generated audio at its own level. By default its beat-peak level is matched "
                        "to the 2 s before the joint (max ±9 dB, 0.3 s ramp from the joint, peak-limited): on "
                        "2026-11-15 the generated music came out ~7 dB quieter than the locked head")
    p.add_argument("--crf", type=int, default=14)
    args = p.parse_args(argv)
    if len(args.segments) < 2:
        p.error("need at least two segments")
    if not (0 <= args.xfade <= args.context):
        p.error("--xfade must be between 0 and --context")
    if not (0.0 <= args.video_switch <= 1.0 and 0.0 <= args.audio_switch <= 1.0):
        p.error("--video-switch / --audio-switch must be within 0..1")
    sv = int(round(args.video_switch * args.context))
    if sv < args.xfade:
        p.error("--video-switch leaves less than --xfade frames of overlap before the switch")
    return args


def read_segment(path):
    """All frames (RGB uint8), fps, and stereo float PCM aligned to t=0."""
    container = av.open(str(path))
    vs = container.streams.video[0]
    fps = float(vs.average_rate)
    frames = [f.to_ndarray(format="rgb24") for f in container.decode(vs)]
    container.close()
    container = av.open(str(path))
    astream = next((s for s in container.streams if s.type == "audio"), None)
    pcm, rate = None, None
    if astream is not None:
        rate = astream.codec_context.sample_rate or astream.rate
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=rate)
        chunks, start = [], None
        for frame in container.decode(astream):
            if start is None and frame.pts is not None:
                start = float(frame.pts * frame.time_base)
            for rf in resampler.resample(frame) or []:
                chunks.append(rf.to_ndarray().astype(np.float32))
        if chunks:
            pcm = np.concatenate(chunks, axis=1)
            offset = int(round((start or 0.0) * rate))
            if offset < 0:
                pcm = pcm[:, -offset:]
            elif offset > 0:
                pcm = np.concatenate([np.zeros((2, offset), np.float32), pcm], axis=1)
    container.close()
    return {"path": str(path), "frames": frames, "fps": fps, "pcm": pcm, "rate": rate}


def small_gray(img):
    h, w = img.shape[:2]
    s = cv2.resize(img, (SMALL_W, max(1, round(h * SMALL_W / w))), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(s, cv2.COLOR_RGB2GRAY).astype(np.float32)


def frame_stats(img):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    return {
        "luma_mean": float(gray.mean()),
        "luma_std": float(gray.std()),
        "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "saturation": float(hsv[..., 1].mean()),
    }


def mean_stats(frames):
    rows = [frame_stats(f) for f in frames]
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} if rows else {}


def mean_lab(frames):
    """Mean CIE Lab (L 0-100, a/b signed) over downscaled frames."""
    labs = []
    for f in frames:
        s = cv2.resize(f, (SMALL_W, max(1, round(f.shape[0] * SMALL_W / f.shape[1]))), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(s, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float64).mean(axis=0)
        labs.append([lab[0] * 100.0 / 255.0, lab[1] - 128.0, lab[2] - 128.0])
    return np.mean(labs, axis=0) if labs else np.zeros(3)


def beat_peak_db(x, rate):
    """Music loudness that ignores the gaps between beats: 90th percentile of 50 ms RMS (dBFS)."""
    w = max(1, int(0.05 * rate))
    vals = [rms_db(x[:, i:i + w]) for i in range(0, x.shape[1] - w + 1, w)]
    return float(np.percentile(vals, 90)) if vals else -120.0


def match_level(pcm, start, rate, seam, enabled):
    """Gain B's generated audio (pcm[:, start:]) to the beat-peak level of the 2 s before it."""
    ref = beat_peak_db(pcm[:, max(0, start - 2 * rate):start], rate)
    cur = beat_peak_db(pcm[:, start:start + 4 * rate], rate)
    seam["audio_level_before_2s_db"], seam["audio_level_after_db"] = ref, cur
    gain_db = float(np.clip(ref - cur, -9.0, 9.0)) if enabled and abs(ref - cur) > 1.5 else 0.0
    limited = 0.0
    if gain_db:
        tail = pcm[:, start:]
        knee, ceiling = 0.79, 0.99
        while True:
            # Soft limiter above the knee; lower the gain until it touches at most 0.1 % of samples.
            g = 10 ** (gain_db / 20)
            ramp_n = min(int(0.3 * rate), tail.shape[1])
            env = np.full(tail.shape[1], g, dtype=np.float32)
            env[:ramp_n] = np.linspace(1.0, g, ramp_n, dtype=np.float32)
            y = tail * env
            over = np.abs(y) > knee
            limited = float(over.mean())
            if limited <= 0.001 or gain_db <= 0.5:
                break
            gain_db -= 0.5
        a = np.abs(y[over])
        y[over] = np.sign(y[over]) * (knee + (ceiling - knee) * np.tanh((a - knee) / (ceiling - knee)))
        pcm = np.concatenate([pcm[:, :start], y.astype(np.float32)], axis=1)
    seam["audio_gain_applied_db"] = gain_db
    seam["audio_samples_soft_limited_pct"] = 100.0 * limited
    return pcm


def rms_db(x):
    r = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    return 20 * math.log10(r) if r > 1e-6 else -120.0


def label(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def grid(images, cols):
    h, w = images[0].shape[:2]
    rows = math.ceil(len(images) / cols)
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = im
    return sheet


def thumb(img, width):
    h, w = img.shape[:2]
    return cv2.resize(img, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)


def write_rgb(path, rgb):
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])


def encode(path, frames, fps, pcm, rate, crf):
    out = av.open(str(path), mode="w")
    vs = out.add_stream("libx264", rate=Fraction(fps).limit_denominator(1000))
    vs.width, vs.height = frames[0].shape[1], frames[0].shape[0]
    vs.pix_fmt = "yuv420p"
    vs.options = {"crf": str(crf), "preset": "medium"}
    ast = None
    if pcm is not None:
        ast = out.add_stream("aac", rate=rate)
        ast.layout = "stereo"
        ast.bit_rate = 192000
    for img in frames:
        for packet in vs.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(packet)
    for packet in vs.encode():
        out.mux(packet)
    if ast is not None:
        chunk = 1024
        data = np.clip(pcm, -1.0, 1.0).astype(np.float32)
        for i in range(0, data.shape[1], chunk):
            piece = np.ascontiguousarray(data[:, i:i + chunk])
            frame = av.AudioFrame.from_ndarray(piece, format="fltp", layout="stereo")
            frame.sample_rate = rate
            frame.pts = i
            for packet in ast.encode(frame):
                out.mux(packet)
        for packet in ast.encode():
            out.mux(packet)
    out.close()


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    segs = [read_segment(p) for p in args.segments]
    fps = segs[0]["fps"]
    if any(abs(s["fps"] - fps) > 1e-3 for s in segs):
        raise SystemExit("error: segments have different frame rates")
    shapes = {s["frames"][0].shape for s in segs}
    if len(shapes) != 1:
        raise SystemExit(f"error: segments have different frame sizes: {shapes}")
    C, XF = args.context, args.xfade
    for s in segs[1:]:
        if len(s["frames"]) <= C:
            raise SystemExit(f"error: {s['path']} has only {len(s['frames'])} frames (context {C})")
    has_audio = all(s["pcm"] is not None for s in segs)
    rate = segs[0]["rate"] if has_audio else None

    frames = list(segs[0]["frames"])
    pcm = None
    if has_audio:
        # Decoded AAC carries padding after the last real sample; the latent length is the truth.
        spt = rate // AUDIO_LATENT_HZ   # samples per audio latent tick (800 at 32 kHz)
        if rate % AUDIO_LATENT_HZ:
            raise SystemExit(f"error: audio rate {rate} is not a multiple of {AUDIO_LATENT_HZ}")
        pcm = segs[0]["pcm"][:, :latent_ticks(len(segs[0]["frames"]), fps) * spt]
    audio_joints = []
    report = {"name": args.name, "fps": fps, "context_frames": C, "video_xfade_frames": XF,
              "audio_xfade_ms": args.audio_xfade_ms, "segments": [], "seams": []}
    added = [list(segs[0]["frames"])]   # frames each segment contributes, for drift stats
    joints = []
    for k in range(1, len(segs)):
        a, b = segs[k - 1], segs[k]
        A, B = a["frames"], b["frames"]
        # Overlap agreement: A's tail and B's locked head come from identical latents.
        ov = [float(np.abs(A[len(A) - C + i].astype(np.int16) - B[i].astype(np.int16)).mean()) for i in range(C)]
        # Picture: frames already appended end with A's last frame. Switch to B at overlap frame sv.
        sv = int(round(args.video_switch * C))
        del frames[len(frames) - (C - sv):]
        base = len(frames) - XF
        for i in range(XF):
            w = (i + 1) / (XF + 1)
            blend = (1 - w) * A[len(A) - C + sv - XF + i].astype(np.float32) + w * B[sv - XF + i].astype(np.float32)
            frames[base + i] = np.clip(blend + 0.5, 0, 255).astype(np.uint8)
        switch = len(frames)             # index of B[sv]
        frames.extend(B[sv:])
        joint = switch + (C - sv)        # index of B[C], the first frame segment k generated
        joints.append(joint)
        added.append(list(B[C:]))
        seam = {"segment": k + 1, "joint_frame": joint, "joint_time_s": joint / fps,
                "video_switch_frame": switch,
                "overlap_mae_mean": float(np.mean(ov)), "overlap_mae_max": float(np.max(ov)),
                "overlap_mae_first": ov[0], "overlap_mae_last": ov[-1]}
        if has_audio:
            # The chain graph copied A's last ctx_ticks audio latent ticks into B's first ctx_ticks.
            ctx_ticks = latent_ticks(C, fps)
            a_ticks, b_ticks = latent_ticks(len(A), fps), latent_ticks(len(B), fps)
            n_ctx = ctx_ticks * spt
            tail_a = a["pcm"][:, (a_ticks - ctx_ticks) * spt:a_ticks * spt]
            head_b = b["pcm"][:, :n_ctx]
            n = min(tail_a.shape[1], head_b.shape[1])
            seam["audio_overlap_diff_dbfs"] = rms_db(tail_a[:, :n] - head_b[:, :n]) if n else None
            seam["audio_overlap_level_dbfs"] = rms_db(tail_a[:, :n]) if n else None
            m = max(1, int(round(args.audio_xfade_ms / 1000 * rate)))
            n_sw = max(m, int(round(args.audio_switch * n_ctx)))   # switch point inside the overlap
            pcm = pcm[:, :pcm.shape[1] - (n_ctx - n_sw)]
            ramp = np.linspace(0.0, 1.0, m, dtype=np.float32)
            mixed = pcm[:, -m:] * (1 - ramp) + b["pcm"][:, n_sw - m:n_sw] * ramp
            seam["audio_switch_s"] = pcm.shape[1] / rate
            gen_start = pcm.shape[1] + (n_ctx - n_sw)               # where B's generated audio begins
            audio_joints.append(gen_start)
            seam["av_offset_ms"] = 1000.0 * (gen_start / rate - joint / fps)
            pcm = np.concatenate([pcm[:, :-m], mixed, b["pcm"][:, n_sw:b_ticks * spt]], axis=1)
            pcm = match_level(pcm, gen_start, rate, seam, args.audio_level_match)
        report["seams"].append(seam)

    # Seam motion metrics on the stitched frames.
    gray = [small_gray(f) for f in frames]
    diff = [0.0] + [float(np.abs(gray[i] - gray[i - 1]).mean()) for i in range(1, len(gray))]
    one_s = int(round(fps))
    for idx, (seam, j) in enumerate(zip(report["seams"], joints)):
        sw = seam["video_switch_frame"]
        around = diff[max(1, j - one_s):j - XF] + diff[j + 2:j + 2 + one_s]
        med = float(np.median(around)) if around else 0.0
        local = diff[j - XF:j + 2]
        seam["seam_ratio_max"] = (max(local) / med) if med > 1e-6 else None
        seam["seam_diffs"] = [round(x, 3) for x in local]
        seam["motion_before"] = float(np.mean(diff[max(1, j - one_s):j - XF])) if j - XF > 1 else None
        seam["motion_after"] = float(np.mean(diff[j + 1:j + 1 + one_s]))
        # Colour jump: the half second before the crossfade vs the half second from the joint.
        half = max(1, one_s // 2)
        before, after = frames[max(0, j - XF - half):j - XF], frames[j:j + half]
        lab_b, lab_a = mean_lab(before), mean_lab(after)
        seam["color_delta_e_half_s"] = float(np.linalg.norm(lab_a - lab_b))
        sb, sa = mean_stats(before), mean_stats(after)
        seam["luma_before_after"] = [sb.get("luma_mean"), sa.get("luma_mean")]
        seam["saturation_before_after"] = [sb.get("saturation"), sa.get("saturation")]
        if has_audio:
            js = audio_joints[idx]
            win = int(0.25 * rate)
            seam["audio_rms_before_dbfs"] = rms_db(pcm[:, max(0, js - win):js])
            seam["audio_rms_after_dbfs"] = rms_db(pcm[:, js:js + win])
            step = np.abs(np.diff(pcm, axis=1)).max(axis=0)
            near = step[max(0, js - 64):js + 64]
            ctx = np.concatenate([step[max(0, js - win):max(0, js - 64)], step[js + 64:js + win]])
            seam["audio_step_ratio"] = float(near.max() / (np.median(ctx) + 1e-6)) if ctx.size else None
        # Seam sheet: stitched frames J-6 .. J+5.
        tw = 256
        cells = []
        for t in range(j - 6, j + 6):
            if 0 <= t < len(frames):
                src = ("A" if t < sw - XF else "blend" if t < sw else "B-locked" if t < j else "B-new")
                cells.append(label(thumb(frames[t], tw), f"{t} {t / fps:.2f}s {src}"))
        write_rgb(outdir / f"seam-{seam['segment'] - 1}.jpg", grid(cells, 6))
    # Overlap sheets: A tail | B head | x4 difference, at four overlap frames.
    for k in range(1, len(segs)):
        A, B = segs[k - 1]["frames"], segs[k]["frames"]
        cells = []
        for i in sorted({0, C // 3, (2 * C) // 3, C - 1}):
            a_img, b_img = A[len(A) - C + i], B[i]
            d = np.clip(np.abs(a_img.astype(np.int16) - b_img.astype(np.int16)) * 4, 0, 255).astype(np.uint8)
            cells += [label(thumb(a_img, 256), f"A[{len(A) - C + i}]"), label(thumb(b_img, 256), f"B[{i}]"),
                      label(thumb(d, 256), "|A-B| x4")]
        write_rgb(outdir / f"overlap-{k}.jpg", grid(cells, 6))

    # Drift: what each segment adds, and the last second of each segment.
    for k, (seg, new) in enumerate(zip(segs, added), start=1):
        report["segments"].append({
            "segment": k, "path": seg["path"], "frames": len(seg["frames"]), "frames_added": len(new),
            "added_stats": mean_stats(new[::4]),
            "last_second_stats": mean_stats(seg["frames"][-one_s:]),
            "first_second_stats": mean_stats(seg["frames"][:one_s]),
        })
    first = report["segments"][0]["last_second_stats"]
    for seg in report["segments"][1:]:
        seg["last_second_vs_segment1_pct"] = {
            key: 100.0 * (seg["last_second_stats"][key] - first[key]) / first[key] if first[key] else None
            for key in first}

    out_path = outdir / f"{args.name}.mp4"
    encode(out_path, frames, fps, pcm, rate, args.crf)
    report["output"] = str(out_path)
    report["frames"] = len(frames)
    report["duration_s"] = len(frames) / fps
    if has_audio:
        report["audio_duration_s"] = pcm.shape[1] / rate
    (outdir / "report.json").write_text(json.dumps(report, indent=2))

    lines = [f"# Stitch report: {args.name}", "",
             f"- Output: `{out_path}` — {len(frames)} frames = {len(frames) / fps:.3f} s"
             + (f", audio {pcm.shape[1] / rate:.3f} s" if has_audio else ", no audio"),
             f"- Context {C} frames, video crossfade {XF} frames at overlap fraction {args.video_switch:g}, "
             f"audio crossfade {args.audio_xfade_ms:g} ms at overlap fraction {args.audio_switch:g}", "",
             "## Seams", "",
             "| Seam | Joint | Overlap MAE mean / max | Seam ratio | Motion before / after | Audio before / after dBFS | Audio step ratio | Audio overlap diff dBFS | A/V offset ms |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in report["seams"]:
        def f(x, p=2):
            return "n/a" if x is None else f"{x:.{p}f}"
        lines.append(
            f"| {s['segment'] - 1}->{s['segment']} | frame {s['joint_frame']} ({s['joint_time_s']:.3f} s) | "
            f"{f(s['overlap_mae_mean'])} / {f(s['overlap_mae_max'])} | {f(s['seam_ratio_max'])} | "
            f"{f(s['motion_before'])} / {f(s['motion_after'])} | "
            f"{f(s.get('audio_rms_before_dbfs'), 1)} / {f(s.get('audio_rms_after_dbfs'), 1)} | "
            f"{f(s.get('audio_step_ratio'))} | {f(s.get('audio_overlap_diff_dbfs'), 1)} "
            f"(level {f(s.get('audio_overlap_level_dbfs'), 1)}) | {f(s.get('av_offset_ms'), 1)} |")
    if has_audio:
        lines += ["", "Music level at each joint (beat peaks: 2 s before vs the generated part, before any gain):", ""]
        for s in report["seams"]:
            lines.append(f"- seam {s['segment'] - 1}->{s['segment']}: {s['audio_level_before_2s_db']:.1f} -> "
                         f"{s['audio_level_after_db']:.1f} dBFS; gain applied to the generated part "
                         f"{s['audio_gain_applied_db']:+.1f} dB "
                         f"({s.get('audio_samples_soft_limited_pct', 0.0):.3f} % of samples soft-limited)")
    lines += ["", "Colour at each joint (0.5 s before the crossfade vs 0.5 s from the joint):", ""]
    for s in report["seams"]:
        lb, la = s["luma_before_after"]
        sb, sa = s["saturation_before_after"]
        lines.append(f"- seam {s['segment'] - 1}->{s['segment']}: ΔE {s['color_delta_e_half_s']:.2f} "
                     f"(<2 invisible, 2-5 noticeable side by side, >5 a visible jump); "
                     f"luma {lb:.1f} -> {la:.1f}; saturation {sb:.1f} -> {sa:.1f}")
    lines += ["", "## Drift (frames each segment adds, every 4th frame)", "",
              "| Segment | Frames added | Luma mean | Luma std (contrast) | Sharpness (Lap. var) | Saturation |",
              "|---|---|---|---|---|---|"]
    for seg in report["segments"]:
        st = seg["added_stats"]
        lines.append(f"| {seg['segment']} | {seg['frames_added']} | {st['luma_mean']:.1f} | {st['luma_std']:.1f} | "
                     f"{st['sharpness']:.1f} | {st['saturation']:.1f} |")
    lines += ["", "Last second of each later segment vs the last second of segment 1 (%):", ""]
    for seg in report["segments"][1:]:
        pct = seg["last_second_vs_segment1_pct"]
        lines.append(f"- segment {seg['segment']}: " + ", ".join(
            f"{k} {v:+.1f}%" for k, v in pct.items() if v is not None))
    lines += ["", "Read with the sheets: seam ratio ~1 = the joint moves like its neighbours; >2 = a visible jump.",
              "Motion after << before = a freeze at the joint. Overlap MAE is re-decode noise only.",
              "Sheets: " + ", ".join(sorted(p.name for p in outdir.glob("*.jpg")))]
    (outdir / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"STITCHED {out_path}")


if __name__ == "__main__":
    main()
