#!/usr/bin/env python3
"""Every-frame review pack for one generated mp4.

Writes, under OUTDIR:
  report.md                  cuts, per-shot camera motion, audio levels, flags
  stats.csv                  one row per frame (brightness, change, background shift, zoom)
  sheets/sheet-XX.jpg        every frame as a numbered thumbnail, background shift printed under it
  detail/detail-XX.jpg       one frame every 0.5 s (--detail-every 12) at half resolution, six per sheet
  keyframes/                 full-resolution first / middle / last frame of every shot (PNG)
  stabilized/shotK-strip.jpg six moments of shot K re-aligned so the BACKGROUND holds still
  stabilized/shotK-trail.jpg the same moments on one clean background: whatever moved through the
                             scene shows up at each position it passed (a chronophotograph)

Why: when the camera tracks a walking character, the character keeps its spot on screen and only the
background slides, so judged against the frame edges the character looks static. The stabilized views
undo the camera motion, so motion through the scene is visible directly. Automatic subject tracking is
deliberately not attempted: falling snow, rain and sparkles fool it.

Needs numpy + OpenCV (+ PyAV for audio). On this stack: the Spark's system python3 (CPU only).
From a remote machine, without copying the file:
  ssh spark-2a60 "python3 - ~/h3-output/NAME_00001_.mp4 /tmp/h3-review/NAME" < review_video.py

usage: review_video.py VIDEO OUTDIR [--cols 6] [--rows 5] [--thumb 320] [--cut 25] [--detail-every 12]
       review_video.py VIDEO OUTDIR --dump 120,180 [--crop x0,y0,x1,y1]   (full-res frames only)
"""
import argparse
import csv
import json
import math
import sys
import warnings
from pathlib import Path

import cv2
import numpy as np

ANALYSIS_W = 480        # camera-motion analysis runs on frames scaled to this width
COMPOSITE_W = 640       # stabilized views are built from frames scaled to this width
CUT_SMALL = (160, 90)   # cut detection compares frames at this size
STATIC_PAN = 0.03       # |total background shift| below 3 % of the width / height = no pan / tilt
STATIC_ZOOM = 0.03      # |zoom - 1| below 3 % = no push / zoom
SAMPLES = 6             # moments per shot in the stabilized views


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("outdir")
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--rows", type=int, default=5)
    p.add_argument("--thumb", type=int, default=320, help="thumbnail width in px")
    p.add_argument("--cut", type=float, default=25.0,
                   help="mean colour change (0-255) that marks a cut, unless camera motion explains it")
    p.add_argument("--detail-every", type=int, default=12, help="frame step for the half-resolution detail sheets")
    p.add_argument("--dump", help="comma-separated frame numbers: save only these frames at full resolution")
    p.add_argument("--crop", help="with --dump: x0,y0,x1,y1 in full-res pixels")
    return p.parse_args(argv)


def camera_motion(prev, cur):
    """Dominant (background) similarity motion prev -> cur on small grey frames.

    Returns (M 2x3, shift_x, shift_y, scale, rot_deg, n_inliers) or None. shift_* is how far the content
    at the frame centre moved on screen, in analysis pixels. Content sliding left = camera moving right.
    """
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=600, qualityLevel=0.01, minDistance=6, blockSize=7)
    if pts is None or len(pts) < 12:
        return None
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, winSize=(21, 21), maxLevel=3)
    good = st.reshape(-1) == 1
    p0, p1 = pts[good], nxt[good]
    if len(p0) < 12:
        return None
    M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=1.0,
                                         maxIters=2000, confidence=0.99)
    if M is None or inl is None or int(inl.sum()) < 10:
        return None
    h, w = prev.shape
    cx, cy = M @ np.array([w / 2.0, h / 2.0, 1.0])
    return (M, cx - w / 2.0, cy - h / 2.0, math.hypot(M[0, 0], M[1, 0]),
            math.degrees(math.atan2(M[1, 0], M[0, 0])), int(inl.sum()))


def compensated_change(prev, cur, M):
    """Mean grey difference after undoing the camera motion (valid area only)."""
    h, w = cur.shape
    warped = cv2.warpAffine(prev, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpAffine(np.full((h, w), 255, np.uint8), M, (w, h), borderValue=0)
    valid = cv2.erode(valid, np.ones((9, 9), np.uint8)) > 0
    if valid.sum() < 0.3 * w * h:
        return 255.0
    return float(cv2.absdiff(warped, cur)[valid].mean())


def describe_camera(sx, sy, zoom):
    """Plain words for a shot's accumulated background motion (fractions of frame width / height)."""
    parts = []
    if abs(zoom - 1.0) >= STATIC_ZOOM:
        parts.append(f"push-in / zoom-in ({zoom:.2f}x)" if zoom > 1 else f"pull-out / zoom-out ({zoom:.2f}x)")
    if abs(sx) >= STATIC_PAN:
        parts.append(f"camera moves {'right' if sx < 0 else 'left'} (background slides {abs(sx) * 100:.0f}% "
                     f"of the width {'left' if sx < 0 else 'right'})")
    if abs(sy) >= STATIC_PAN:
        parts.append(f"camera moves {'up' if sy > 0 else 'down'} (background slides {abs(sy) * 100:.0f}% "
                     f"of the height {'down' if sy > 0 else 'up'})")
    return "; ".join(parts) if parts else "static or near-static"


def stabilized_views(samples, chain, outdir, k, fps):
    """Warp each sampled frame into the shot's first-frame coordinates and write the strip and trail."""
    idxs = sorted(samples)
    ch, cw = samples[idxs[0]].shape[:2]
    corners = np.array([[0, 0, 1], [cw, 0, 1], [cw, ch, 1], [0, ch, 1]], np.float64).T
    inv = {i: np.linalg.inv(chain[i]) for i in idxs}
    pts = np.hstack([(inv[i] @ corners)[:2] for i in idxs])
    x0, y0 = pts.min(axis=1)
    x1, y1 = pts.max(axis=1)
    # Fit everything on a canvas of at most 3 x 3 frames: scale down rather than crop a long pan.
    fit = min(1.0, 3 * cw / max(1.0, x1 - x0), 3 * ch / max(1.0, y1 - y0))
    W2 = int((x1 - x0) * fit) + 1
    H2 = int((y1 - y0) * fit) + 1
    off = np.array([[fit, 0, -x0 * fit], [0, fit, -y0 * fit], [0, 0, 1]], np.float64)
    warped = []
    for i in idxs:
        A = (off @ inv[i])[:2]
        img = cv2.warpAffine(samples[i], A, (W2, H2), flags=cv2.INTER_LINEAR, borderValue=0)
        valid = cv2.warpAffine(np.full((ch, cw), 255, np.uint8), A, (W2, H2), borderValue=0) > 0
        warped.append((i, img, valid, A))

    # Strip: one stabilized moment per row, labelled, with that frame's footprint outlined.
    rows = []
    for i, img, _, A in warped:
        im = img.copy()
        poly = (A @ corners).T.astype(np.int32)
        cv2.polylines(im, [poly], True, (0, 255, 255), 2)
        cv2.putText(im, f"#{i} {i / fps:.2f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        rows.append(im)
    cv2.imwrite(str(outdir / f"shot{k}-strip.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])

    # Trail: median of the stabilized moments = clean background; paste back, per moment, what differs.
    stack = np.stack([img.astype(np.float32) for _, img, _, _ in warped])
    masks = np.stack([v for _, _, v, _ in warped])
    stack_nan = np.where(masks[..., None], stack, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # canvas corners no moment covers are all-NaN
        bg = np.nanmedian(stack_nan, axis=0)
    bg = np.nan_to_num(bg, nan=0.0)
    trail = bg.copy()
    for (_, img, valid, _) in warped:
        d = np.abs(img.astype(np.float32) - bg).max(axis=2)
        m = ((d > 40) & valid).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0   # drop specks (snow, rain)
        trail[m] = img[m]
    trail = trail.astype(np.uint8)
    for n_, (i, _, _, A) in enumerate(warped):
        poly = (A @ corners).T.astype(np.int32)
        cv2.polylines(trail, [poly], True, (0, 255, 255), 1)
        cv2.putText(trail, f"{i / fps:.1f}s", (int(poly[0][0]) + 4, int(poly[0][1]) + 16 + 16 * n_),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.imwrite(str(outdir / f"shot{k}-trail.jpg"), trail, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return True


def read_audio(path):
    """Audio facts from the container: codec, rate, channels, duration, RMS per 0.25 s (dBFS)."""
    try:
        import av
    except ImportError:
        return {"error": "PyAV not installed; audio not measured"}
    try:
        container = av.open(str(path))
    except Exception as exc:  # noqa: BLE001 - report, do not crash the review
        return {"error": f"cannot open: {exc}"}
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        container.close()
        return {"error": "no audio stream"}
    rate = stream.codec_context.sample_rate or stream.rate
    layout = stream.codec_context.layout
    channels = len(layout.channels) if layout is not None else 0
    # Planar float gives one row per channel, values in [-1, 1], whatever the stored format is.
    resampler = av.AudioResampler(format="fltp", layout=layout.name if layout is not None else "stereo", rate=rate)
    chunks = []
    for frame in container.decode(stream):
        out = resampler.resample(frame)
        for rf in (out if isinstance(out, list) else [out]):
            if rf is not None:
                chunks.append(rf.to_ndarray().astype(np.float32))
    info = {"codec": stream.codec_context.name, "rate": rate, "channels": channels}
    container.close()
    if not chunks:
        info["error"] = "audio stream decoded to nothing"
        return info
    pcm = np.concatenate(chunks, axis=1)
    mono = np.sqrt((pcm ** 2).mean(axis=0))
    win = max(1, int(rate * 0.25))
    db = []
    for i in range(len(mono) // win):
        r = float(np.sqrt((mono[i * win:(i + 1) * win] ** 2).mean()))
        db.append(20 * math.log10(r) if r > 1e-6 else -120.0)
    peak = float(np.abs(pcm).max())
    info.update({"duration_s": pcm.shape[1] / float(rate),
                 "peak_dbfs": 20 * math.log10(peak) if peak > 1e-6 else -120.0,
                 "window_s": 0.25, "rms_dbfs": db})
    return info


def dump_frames(args):
    wanted = sorted({int(x) for x in args.dump.split(",") if x.strip()})
    crop = [int(v) for v in args.crop.split(",")] if args.crop else None
    out = Path(args.outdir) / "dump"
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    i, saved = 0, []
    while wanted and i <= wanted[-1]:
        ok, f = cap.read()
        if not ok:
            break
        if i in wanted:
            if crop:
                x0, y0, x1, y1 = crop
                f = f[y0:y1, x0:x1]
            path = out / f"frame-{i:04d}.png"
            cv2.imwrite(str(path), f)
            saved.append(str(path))
        i += 1
    cap.release()
    print("\n".join(saved) if saved else "no frames saved")
    return 0 if saved else 1


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.dump:
        return dump_frames(args)
    outdir = Path(args.outdir)
    for sub in ("sheets", "detail", "keyframes", "stabilized"):
        (outdir / sub).mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"error: cannot open {args.video}", file=sys.stderr)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    rows, thumbs, motions, fast_moves = [], [], [], []
    expected_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    prev_small = prev_grey = None
    W = H = ah = th = None
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if W is None:
            H, W = f.shape[:2]
            ah = int(round(H * ANALYSIS_W / W))
            th = int(round(H * args.thumb / W))
        small = cv2.resize(f, CUT_SMALL, interpolation=cv2.INTER_AREA).astype(np.float32)
        grey = cv2.cvtColor(cv2.resize(f, (ANALYSIS_W, ah), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        v = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 2]
        row = {"frame": i, "t": i / fps, "brightness": float(v.mean()), "change": 0.0, "cut": 0,
               "bg_dx": "", "bg_dy": "", "zoom": "", "rot": "", "inliers": ""}
        M = None
        if prev_small is not None:
            row["change"] = float(np.abs(small - prev_small).mean())
            cm = camera_motion(prev_grey, grey)
            if row["change"] > args.cut:
                # A fast pan also changes every pixel. Call it a cut only if camera motion cannot explain it.
                explained = cm is not None and cm[5] >= 40 and \
                    compensated_change(prev_grey, grey, cm[0]) < min(12.0, args.cut * 0.5)
                if explained:
                    fast_moves.append(i)
                else:
                    row["cut"] = 1
                    cm = None
            if cm is not None:
                M, sx, sy, sc, rot, n_in = cm
                row.update(bg_dx=sx / ANALYSIS_W, bg_dy=sy / ah, zoom=sc, rot=rot, inliers=n_in)
        rows.append(row)
        motions.append(M)
        thumbs.append(cv2.resize(f, (args.thumb, th), interpolation=cv2.INTER_AREA))
        prev_small, prev_grey = small, grey
        i += 1
    cap.release()
    n = len(rows)
    if n == 0:
        print("error: no frames decoded", file=sys.stderr)
        return 1

    starts = [0] + [r["frame"] for r in rows if r["cut"]]
    shots = [(a, (starts[k + 1] - 1) if k + 1 < len(starts) else n - 1) for k, a in enumerate(starts)]

    # Contact sheets: every frame, with the background shift since the previous frame under it.
    per = args.cols * args.rows
    label_h = 36
    for s0 in range(0, n, per):
        sheet = np.zeros((args.rows * (th + label_h), args.cols * args.thumb, 3), np.uint8)
        for k, idx in enumerate(range(s0, min(n, s0 + per))):
            r, c = divmod(k, args.cols)
            y = r * (th + label_h)
            sheet[y + label_h:y + label_h + th, c * args.thumb:(c + 1) * args.thumb] = thumbs[idx]
            row = rows[idx]
            top = f"#{idx} {row['t']:.2f}s" + ("  CUT" if row["cut"] else "")
            if row["bg_dx"] == "":
                cam = "bg: (cut)" if row["cut"] else "bg: n/a"
            else:
                cam = f"bg {row['bg_dx'] * 100:+.1f}%x {row['bg_dy'] * 100:+.1f}%y z{row['zoom']:.3f}"
            cv2.putText(sheet, top, (c * args.thumb + 4, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (60, 60, 255) if row["cut"] else (255, 255, 255), 1)
            cv2.putText(sheet, cam, (c * args.thumb + 4, y + 31), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 230, 255), 1)
        cv2.imwrite(str(outdir / "sheets" / f"sheet-{s0 // per:02d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])

    # Per-shot camera chains: chain[t] maps the shot's first frame onto frame t (COMPOSITE_W pixels);
    # stabilized_views warps with its inverse.
    s = COMPOSITE_W / float(ANALYSIS_W)
    chains, sample_idx = [], {}
    for k, (a, b) in enumerate(shots, 1):
        chain = {a: np.eye(3)}
        for t in range(a + 1, b + 1):
            M3 = np.eye(3)
            if motions[t] is not None:
                M3[:2] = motions[t]
                M3[:2, 2] *= s
            chain[t] = M3 @ chain[t - 1]
        chains.append(chain)
        for idx in sorted({int(round(a + j * (b - a) / (SAMPLES - 1))) for j in range(SAMPLES)}):
            sample_idx.setdefault(idx, []).append(k)

    # Second pass: full-res keyframes and the frames for the stabilized views.
    keyframes = {}
    for k, (a, b) in enumerate(shots, 1):
        for tag, idx in (("first", a), ("mid", (a + b) // 2), ("last", b)):
            keyframes.setdefault(idx, []).append(f"shot{k}-{tag}")
    samples = {k: {} for k in range(1, len(shots) + 1)}
    ch_ = int(round(H * COMPOSITE_W / W))
    step = max(1, args.detail_every)
    dw, dh = W // 2, H // 2
    detail = []
    cap = cv2.VideoCapture(args.video)
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        for name in keyframes.get(idx, []):
            cv2.imwrite(str(outdir / "keyframes" / f"{name}-f{idx:04d}.png"), f)
        for k in sample_idx.get(idx, []):
            samples[k][idx] = cv2.resize(f, (COMPOSITE_W, ch_), interpolation=cv2.INTER_AREA)
        if idx % step == 0:
            detail.append((idx, cv2.resize(f, (dw, dh), interpolation=cv2.INTER_AREA)))
        idx += 1
    cap.release()
    written = set()
    for k in samples:
        if len(samples[k]) >= 2:
            if stabilized_views(samples[k], chains[k - 1], outdir / "stabilized", k, fps):
                written.add(k)
    shot_of = {}
    for k, (a, b) in enumerate(shots, 1):
        for t in range(a, b + 1):
            shot_of[t] = k
    n_detail_sheets = 0
    for s0 in range(0, len(detail), 6):
        part = detail[s0:s0 + 6]
        sheet = np.zeros((3 * (dh + 28), 2 * dw, 3), np.uint8)
        for k, (fi, im) in enumerate(part):
            r, c = divmod(k, 2)
            y = r * (dh + 28)
            sheet[y + 28:y + 28 + dh, c * dw:(c + 1) * dw] = im
            cv2.putText(sheet, f"#{fi} {fi / fps:.2f}s  shot {shot_of.get(fi, '?')}", (c * dw + 6, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imwrite(str(outdir / "detail" / f"detail-{s0 // 6:02d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
        n_detail_sheets += 1

    with open(outdir / "stats.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        for row in rows:
            wr.writerow({k: (f"{v:.5f}" if isinstance(v, float) else v) for k, v in row.items()})

    audio = read_audio(args.video)

    lines = [f"# Review pack: {Path(args.video).name}", "",
             f"- Frames: **{n}** at {fps:.2f} fps = **{n / fps:.2f} s**, {W}x{H}",
             f"- Cuts (colour change > {args.cut:g}): " + (", ".join(
                 f"#{r['frame']} @ {r['t']:.2f} s ({r['change']:.0f})" for r in rows if r["cut"]) or "none"),
             f"- `sheets/`: {math.ceil(n / per)} sheets, {per} frames each. Under each thumbnail, `bg` = how far "
             "the background slid since the previous frame (% of width / height; negative x = slid left = camera "
             "moved right) and `z` = zoom factor.",
             f"- `detail/`: {n_detail_sheets} sheets, one frame every {step} frames ({step / fps:.2f} s) at half "
             "resolution, for faces, hands and artifacts.",
             "- `stabilized/`: per shot, six moments with the camera motion undone (`-strip`) and the same "
             "moments on one background (`-trail`). Whatever changes position there moved through the scene. "
             "Yellow outlines = where the camera was looking at each moment.",
             "", "## Shots", ""]
    summary = {"frames": n, "fps": fps, "width": W, "height": H, "shots": [], "audio": {}}
    for k, (a, b) in enumerate(shots, 1):
        seg = [r for r in rows[a + 1:b + 1] if r["bg_dx"] != ""]
        sx = sum(r["bg_dx"] for r in seg)
        sy = sum(r["bg_dy"] for r in seg)
        zoom = float(np.prod([r["zoom"] for r in seg])) if seg else 1.0
        measured = len(seg) / max(1, b - a)
        shot = {"shot": k, "first": a, "last": b, "t0": a / fps, "t1": (b + 1) / fps, "bg_shift_x": sx,
                "bg_shift_y": sy, "zoom": zoom, "camera": describe_camera(sx, sy, zoom),
                "camera_measured_share": measured}
        bri = [r["brightness"] for r in rows[a:b + 1]]
        lines += [f"### Shot {k}: frames {a}-{b} ({a / fps:.2f}-{(b + 1) / fps:.2f} s, {(b - a + 1) / fps:.2f} s)",
                  f"- Camera: **{shot['camera']}** (measured on {measured * 100:.0f}% of frame pairs"
                  + ("; LOW - judge the camera by eye" if measured < 0.6 else "") + ")",
                  (f"- Views: `stabilized/shot{k}-strip.jpg`, `stabilized/shot{k}-trail.jpg`; keyframes "
                   f"#{a}, #{(a + b) // 2}, #{b}" if k in written else
                   f"- Views: none (shot too short for stabilized views); keyframes #{a}, #{b}"),
                  f"- Brightness: mean {np.mean(bri):.0f}, min {min(bri):.0f}, max {max(bri):.0f}", ""]
        summary["shots"].append(shot)

    flags = []
    for r0, r1 in zip(rows, rows[1:]):
        if not r1["cut"] and abs(r1["brightness"] - r0["brightness"]) > 20:
            flags.append(f"brightness jump {r0['brightness']:.0f}->{r1['brightness']:.0f} at #{r1['frame']} "
                         f"({r1['t']:.2f} s) without a cut (flicker?)")
    if expected_frames and abs(expected_frames - n) > 1:
        flags.append(f"container says {expected_frames} frames but {n} decoded (truncated or damaged file?)")
    if fast_moves:
        flags.append(f"{len(fast_moves)} frame(s) changed more than --cut but camera motion explains them "
                     f"(fast move, not a cut): first at #{fast_moves[0]}. Confirm on the sheets.")
    run, need = 0, max(2, int(round(0.5 * fps)))
    for r in rows[1:]:
        run = run + 1 if r["change"] < 0.3 else 0
        if run == need:
            flags.append(f"near-identical frames for 0.5 s ending #{r['frame']} ({r['t']:.2f} s) (freeze?)")
    for k, (a, b) in enumerate(shots, 1):
        if (b - a + 1) / fps < 1.0:
            flags.append(f"shot {k} lasts only {(b - a + 1) / fps:.2f} s (unplanned cut or flash?)")
    lines += ["## Flags", ""] + ([f"- {x}" for x in flags] or ["- none"]) + [""]

    lines += ["## Audio (measured, not listened to)", ""]
    if "error" in audio:
        lines.append(f"- {audio['error']}")
    else:
        db = audio["rms_dbfs"]
        lines.append(f"- {audio['codec']}, {audio['rate']} Hz, {audio['channels']} ch, {audio['duration_s']:.2f} s, "
                     f"peak {audio['peak_dbfs']:.1f} dBFS")
        quiet = [j * 0.25 for j, d in enumerate(db) if d < -50]
        lines.append(f"- 0.25 s windows below -50 dBFS: {len(quiet)} of {len(db)}"
                     + (f" (first at {quiet[0]:.2f} s)" if quiet else ""))
        if abs(audio["duration_s"] - n / fps) > 0.15:
            lines.append(f"- **Audio is {audio['duration_s']:.2f} s but the video is {n / fps:.2f} s.**")
        for k, (a, b) in enumerate(shots, 1):
            j0 = int(round(a / fps / 0.25))
            w = db[j0:max(j0 + 1, int(round((b + 1) / fps / 0.25)))]
            if w:
                lines.append(f"- Shot {k}: mean {np.mean(w):.1f} dBFS, max {max(w):.1f} dBFS")
        top = sorted(range(len(db)), key=lambda j: db[j], reverse=True)[:6]
        lines.append("- Loudest 0.25 s windows start at: " + ", ".join(f"{j * 0.25:.2f} s" for j in sorted(top)))
        summary["audio"] = {key: val for key, val in audio.items() if key != "rms_dbfs"}
    lines.append("")
    (outdir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{n} frames, {len(shots)} shots, {math.ceil(n / per)} sheets -> {outdir}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
