#!/usr/bin/env python3
"""Build the soundtrack for a locked-audio H3 run: music cut to the clip, plus optional sound effects.

Runs on the Mac (needs numpy and scipy). Input files must be WAV; convert other formats first
(`afconvert -f WAVE -d LEI16 in.m4a out.wav` on macOS).

Writes two files with identical content:
  <out-dir>/<name>-32k.wav    32 kHz stereo, exactly round(frames / 24 * 40) * 800 samples:
                              pass it to submit-prompt.sh --soundtrack (H3 keeps it, draws the picture).
  <out-dir>/<name>-final.wav  the music's own sample rate, frames / 24 seconds:
                              put it on the finished mp4 with mux_audio.py (lossless, not the VAE round trip).
The JSON report on stdout has the tempo and beat times, each effect's level, the limiter's activity and the
regions where the mix differs from the music (only the effect windows may appear there). Warnings go to stderr.

Sound effects (optional --events JSON; a relative "wav" path is relative to the JSON file):
  {"events": [{"name": "fart", "wav": "sfx.wav", "src_start": 2.40, "src_onset": 2.43,
               "src_end": 2.80, "place_at": 9.40, "over_music_lu": 6}]}
  The cut src_start..src_end is placed so that src_onset lands at place_at (clip seconds). Its gain is set so
  that its momentary loudness (BS.1770 K-weighted, 400 ms from place_at) is over_music_lu above the music's in
  the same window (default 6; the user asked for effects clearly louder than the music). Where the music is
  quieter than -50 LUFS (a pause, or no music: pass a silent WAV), the effect is set to an absolute
  "target_lufs" instead (default -16). Gains beyond +-30 dB, and effect windows that are silent, are errors.
  A lookahead limiter at -1 dBFS then ramps down only where peaks need it; the music is untouched elsewhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from math import gcd

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter, resample_poly, stft

warnings.filterwarnings("ignore", category=wavfile.WavFileWarning)  # macOS writes extra chunks

H3_RATE = 32000
SAMPLES_PER_TICK = 800
FPS = 24
LIMIT_DBFS = -1.0
QUIET_MUSIC_LUFS = -50.0
MAX_GAIN_DB = 30.0


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def read_wav(path: str) -> tuple[int, np.ndarray]:
    rate, x = wavfile.read(path)
    if x.dtype == np.int16:
        x = x.astype(np.float64) / 32768
    elif x.dtype == np.int32:
        x = x.astype(np.float64) / 2147483648
    elif x.dtype == np.uint8:
        x = (x.astype(np.float64) - 128) / 128
    else:
        x = x.astype(np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    if x.shape[1] != 2:
        raise SystemExit(f"error: {path}: need mono or stereo, got {x.shape[1]} channels")
    return rate, x


def write_wav(path: str, rate: int, x: np.ndarray, seed: int) -> None:
    rng = np.random.default_rng(seed)
    dither = (rng.random(x.shape) - rng.random(x.shape)) / 32768  # TPDF
    wavfile.write(path, rate, np.clip(np.round((x + dither) * 32768), -32768, 32767).astype(np.int16))


def resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return x.copy()
    g = gcd(src, dst)
    return resample_poly(x, dst // g, src // g, axis=0)


def kweight(x: np.ndarray, fs: int) -> np.ndarray:
    """ITU-R BS.1770-4 K-weighting at any sample rate (De Man's analog-matched biquads, as in pyloudnorm)."""
    G, Q, fc = 3.999843853973347, 0.7071752369554196, 1681.974450955533
    K = np.tan(np.pi * fc / fs); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a = [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    x = lfilter(b, a, x, axis=0)
    Q, fc = 0.5003270373238773, 38.13547087602444
    K = np.tan(np.pi * fc / fs); a0 = 1 + K / Q + K * K
    return lfilter([1.0, -2.0, 1.0], [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0], x, axis=0)


def momentary_lufs(x: np.ndarray, fs: int, i0: int) -> float:
    y = kweight(x, fs)[i0:i0 + int(0.4 * fs)]
    return -0.691 + 10 * np.log10(np.mean(y ** 2, 0).sum() + 1e-20)


def auto_start(x: np.ndarray, fs: int) -> float:
    """First 10 ms block above -50 dBFS, minus a 10 ms pre-roll."""
    m = x.mean(1); blk = int(0.01 * fs)
    for i in range(0, len(m) - blk, blk):
        if 20 * np.log10(np.sqrt(np.mean(m[i:i + blk] ** 2)) + 1e-12) > -50:
            return max(0.0, i / fs - 0.01)
    raise SystemExit("error: --auto-start: the music never rises above -50 dBFS")


def limit(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Lookahead limiter: gain ramps down over 5 ms before a peak, never exceeds -1 dBFS, releases in 50 ms.

    The moving minimum over +-5 ms followed by a 5 ms moving average keeps every sample's gain at or below what
    its own peak needs (each averaged value comes from minima whose windows contain that sample)."""
    thr = 10 ** (LIMIT_DBFS / 20)
    la = max(1, int(0.005 * fs))
    need = np.minimum(1.0, thr / np.maximum(np.abs(x).max(1), 1e-12))
    g = uniform_filter1d(minimum_filter1d(need, 2 * la + 1), la + 1)
    g = np.minimum(g, need)  # float guard only; the averaged ramp is already <= need everywhere
    rel = np.exp(-1 / (0.05 * fs)); out = np.empty_like(g); cur = 1.0
    for i in range(len(g)):
        cur = g[i] if g[i] < cur else min(g[i], 1 - (1 - cur) * rel)
        out[i] = cur
    return x * out[:, None], out


def beats(x: np.ndarray, fs: int) -> tuple[float, list[float]]:
    """Tempo (BPM) and beat times: log-spectral flux, autocorrelation, DP tracking (Ellis 2007).

    The pulse is the strongest lag between 0.25 and 1.5 s under a prior centred on 120 BPM; check it against
    the music (it can pick the half or double tempo). Beats in passages quieter than -45 dBFS are dropped."""
    hop = int(0.01 * fs)
    f, t, Z = stft(x.mean(1), fs, nperseg=2048, noverlap=2048 - hop, boundary=None)
    S = np.log1p(1000 * np.abs(Z[(f > 30) & (f < 8000)]))
    flux = np.maximum(np.diff(S, axis=1), 0).sum(0)
    flux = np.maximum(flux - uniform_filter1d(flux, 100), 0)
    flux /= flux.std() + 1e-12
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    ac /= ac[0] + 1e-12
    lags = np.arange(len(ac)) / 100.0
    prior = np.exp(-0.5 * (np.log2(np.maximum(lags, 1e-3) / 0.5) / 1.4) ** 2)
    cand = (lags > 0.25) & (lags < 1.5)
    period = int(round(lags[cand][np.argmax((ac * prior)[cand])] * 100))
    score = flux.copy(); back = np.full(len(flux), -1)
    for i in range(len(flux)):
        lo, hi = i - 2 * period, i - period // 2
        if hi <= 0:
            continue
        js = np.arange(max(0, lo), hi)
        pen = -400.0 * np.log((i - js) / period) ** 2
        k = int(np.argmax(score[js] + pen))
        score[i] = flux[i] + score[js][k] + pen[k]
        back[i] = js[k]
    i = int(np.argmax(score[-period:])) + len(score) - period
    raw = []
    while i >= 0:
        raw.append(float(t[i + 1]))  # flux[i] is the change into STFT frame i + 1 (window centre)
        i = back[i]
    m = x.mean(1); w = int(0.15 * fs); out = []
    for b in raw[::-1]:
        c = int(b * fs)
        seg = m[max(0, c - w):c + w]
        if seg.size and 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12) > -45:
            out.append(round(b, 3))
    return round(6000 / period, 1), out


def changed_regions(a: np.ndarray, b: np.ndarray, fs: int, floor_db: float = -60.0) -> list[tuple[float, float]]:
    d = (a - b).mean(1); blk = int(0.01 * fs); on = []
    for i in range(0, len(d) - blk + 1, blk):
        if 20 * np.log10(np.sqrt(np.mean(d[i:i + blk] ** 2)) + 1e-12) > floor_db:
            on.append(i // blk)
    regions: list[list[int]] = []
    for k in on:
        if regions and k - regions[-1][1] <= 10:
            regions[-1][1] = k
        else:
            regions.append([k, k])
    return [(r[0] * 0.01, (r[1] + 1) * 0.01) for r in regions]


def place_event(ev: dict, base_dir: str, fs: int, music_only: np.ndarray) -> tuple[np.ndarray, dict]:
    name = ev.get("name", "event")
    path = ev["wav"] if os.path.isabs(ev["wav"]) else os.path.join(base_dir, ev["wav"])
    s0, on, s1 = float(ev["src_start"]), float(ev["src_onset"]), float(ev["src_end"])
    if not (0 <= s0 <= on < s1) or s1 - s0 < 0.1:
        raise SystemExit(f"error: event {name}: need 0 <= src_start <= src_onset < src_end and a cut of >= 0.1 s")
    sfs, sfx = read_wav(path)
    cut = sfx[int(s0 * sfs):int(s1 * sfs)].copy()
    if len(cut) < int(0.1 * sfs):
        raise SystemExit(f"error: event {name}: the cut runs past the end of {path}")
    fi, fo = int(0.02 * sfs), int(0.08 * sfs)
    cut[:fi] *= np.linspace(0, 1, fi)[:, None]
    cut[-fo:] *= np.linspace(1, 0, fo)[:, None]
    cut = resample(cut, sfs, fs)
    i0 = int(round((float(ev["place_at"]) - (on - s0)) * fs))
    if i0 < 0 or i0 + len(cut) > len(music_only):
        raise SystemExit(f"error: event {name} does not fit inside the clip")
    lay = np.zeros_like(music_only); lay[i0:i0 + len(cut)] = cut
    w0 = int(round(float(ev["place_at"]) * fs))
    sfx_l, music_l = momentary_lufs(lay, fs, w0), momentary_lufs(music_only, fs, w0)
    if sfx_l < -70:
        raise SystemExit(f"error: event {name}: the 400 ms after src_onset is silent ({sfx_l:.1f} LUFS); "
                         "check src_onset")
    if music_l < QUIET_MUSIC_LUFS:
        target = float(ev.get("target_lufs", -16.0)); mode = f"absolute {target:g} LUFS (music {music_l:.1f})"
        gain_db = target - sfx_l
    else:
        target = float(ev.get("over_music_lu", 6.0)); mode = f"{target:g} LU over the music"
        gain_db = target - (sfx_l - music_l)
    if abs(gain_db) > MAX_GAIN_DB:
        raise SystemExit(f"error: event {name}: needs {gain_db:+.1f} dB, beyond +-{MAX_GAIN_DB:g} dB; "
                         "check the cut and the source level")
    return lay * 10 ** (gain_db / 20), {"name": name, "place_at": ev["place_at"], "gain_db": round(gain_db, 2),
                                        "mode": mode}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("music", help="music WAV (any rate, mono or stereo); a silent WAV for effects only")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", required=True, help="file stem, e.g. swan")
    ap.add_argument("--frames", type=int, default=362, help="clip length in frames, legal 17n+5 (362 = 15.08 s)")
    start = ap.add_mutually_exclusive_group()
    start.add_argument("--start", type=float, default=None, help="music time (s) that lands on frame 0")
    start.add_argument("--auto-start", action="store_true", help="start 10 ms before the first sound")
    ap.add_argument("--fade-out", type=float, default=0.3, help="fade at the clip end, seconds (0 = hard cut)")
    ap.add_argument("--events", default=None, help="JSON file with sound effects to mix in")
    args = ap.parse_args(argv)

    if args.frames < 5 or (args.frames - 5) % 17:
        raise SystemExit(f"error: --frames {args.frames} is not a legal 17n+5 length")
    if args.fade_out < 0:
        raise SystemExit("error: --fade-out must be >= 0")
    fs, music = read_wav(args.music)
    t0 = auto_start(music, fs) if args.auto_start else (args.start or 0.0)
    if t0 < 0:
        raise SystemExit("error: --start must be >= 0")
    dur = args.frames / FPS
    n = int(round(dur * fs))
    seg = music[int(round(t0 * fs)):int(round(t0 * fs)) + n].copy()
    if len(seg) < n:
        warn(f"the music ends {(n - len(seg)) / fs:.2f} s before the clip; padded with silence")
        seg = np.pad(seg, ((0, n - len(seg)), (0, 0)))
    k = int(args.fade_out * fs)
    if k >= 1:
        seg[-k:] *= (np.linspace(1, 0, k) ** 2)[:, None]
    music_only = seg.copy()
    mix = seg.copy()

    report = {"music": os.path.abspath(args.music), "start_s": round(t0, 3), "frames": args.frames, "events": []}
    report["bpm"], report["beats_s"] = beats(music_only, fs)
    if args.events:
        base_dir = os.path.dirname(os.path.abspath(args.events))
        with open(args.events) as fh:
            events = json.load(fh)["events"]
        for ev in events:
            layer, info = place_event(ev, base_dir, fs, music_only)
            mix += layer
            report["events"].append(info)
    mix, gain = limit(mix, fs)
    gr = 20 * np.log10(gain); act = np.where(gr < -0.01)[0]
    report["limiter"] = {"max_reduction_db": round(float(gr.min()), 2), "active_ms": round(len(act) / fs * 1000),
                         "span_s": [round(act[0] / fs, 2), round(act[-1] / fs, 2)] if len(act) else None}
    for ev in report["events"]:
        w0 = int(round(float(ev["place_at"]) * fs))
        ev["mix_lufs_m"] = round(momentary_lufs(mix, fs, w0), 1)
        ev["music_lufs_m"] = round(momentary_lufs(music_only, fs, w0), 1)
    report["changed_regions_s"] = changed_regions(mix, music_only, fs)

    os.makedirs(args.out_dir, exist_ok=True)
    final = os.path.join(args.out_dir, f"{args.name}-final.wav")
    write_wav(final, fs, mix, seed=3)
    want = round(args.frames / FPS * 40) * SAMPLES_PER_TICK
    h3 = resample(mix, fs, H3_RATE)[:want]
    h3 = np.pad(h3, ((0, want - len(h3)), (0, 0)))
    locked = os.path.join(args.out_dir, f"{args.name}-32k.wav")
    write_wav(locked, H3_RATE, np.clip(h3, -1, 1), seed=4)
    report["outputs"] = {"locked_32k": locked, "locked_samples": want, "final": final, "final_rate": fs,
                         "peak_dbfs": round(20 * np.log10(np.abs(mix).max() + 1e-12), 2)}
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
