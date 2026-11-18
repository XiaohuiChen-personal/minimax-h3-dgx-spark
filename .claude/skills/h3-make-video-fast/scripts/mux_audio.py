#!/usr/bin/env python3
"""Replace an mp4's audio with a WAV, copying the video packets untouched, then prove it.

Runs on the Spark with the system python3 (PyAV + numpy, CPU only), and writes only under /tmp/h3-review/:

  scp WORK/audio/<story>-final.wav spark-2a60:/tmp/h3-review/<name>-mux/
  ssh spark-2a60 "python3 - ~/h3-output/<file> /tmp/h3-review/<name>-mux/<story>-final.wav \
      /tmp/h3-review/<name>-mux/<name>-music.mp4 --expect-locked" < mux_audio.py

<file> is the render's file name as submit printed it (it already ends in .mp4).

Fails (exit 1, MUX_FAILED) unless:
  - the WAV and the video last the same time within 0.05 s;
  - with --expect-locked (renders from the locked-audio graph): the WAV correlates >= 0.5 at lag 0 with the
    render's own audio, which is the locked soundtrack after the VAE round trip (0.8-0.98 measured), so a WAV
    from another prepare_soundtrack run or another length is caught;
  - the output's video packets have the same bytes and timestamps as the source's;
  - the output audio starts at 0, lines up with the WAV (lag 0), correlates >= 0.99, level within 0.5 dB.
Prints MUX_OK on success.
"""
import hashlib
import os
import sys
import wave

import av
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith("--")]
expect_locked = "--expect-locked" in sys.argv[1:]
if len(args) != 3:
    sys.exit("usage: mux_audio.py SRC.mp4 AUDIO.wav DST.mp4 [--expect-locked]")
src, wav_path, dst = os.path.expanduser(args[0]), args[1], args[2]
dst_real = os.path.realpath(dst)
if not dst_real.startswith("/tmp/h3-review/"):
    sys.exit("error: write only under /tmp/h3-review/ (AGENTS.md)")
os.makedirs(os.path.dirname(dst_real), exist_ok=True)


def fail(msg):
    print(f"MUX_FAILED {msg}")
    sys.exit(1)


with wave.open(wav_path, "rb") as w:
    if w.getsampwidth() != 2:
        sys.exit("error: the WAV must be 16-bit PCM")
    rate, ch = w.getframerate(), w.getnchannels()
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, ch)
if ch == 1:
    pcm = np.repeat(pcm, 2, axis=1)
elif ch != 2:
    sys.exit(f"error: need mono or stereo, got {ch} channels")
ref = pcm.astype(np.float64).mean(1) / 32768


def decode_audio(path):
    c = av.open(path)
    if not c.streams.audio:
        c.close()
        return None, None, None
    s = c.streams.audio[0]
    first, chunks = None, []
    for f in c.decode(s):
        if first is None:
            first = f.pts * float(f.time_base)
        a = f.to_ndarray()
        chunks.append(a if a.ndim == 2 else a.reshape(1, -1))
    sr = s.codec_context.sample_rate
    c.close()
    x = np.concatenate(chunks, axis=1).astype(np.float64)
    if np.abs(x).max() > 2:
        x /= 32768
    return x.mean(0), sr, first


def video_info(path):
    c = av.open(path)
    v = c.streams.video[0]
    h = hashlib.sha256()
    stamps = []
    for pk in c.demux(v):
        if pk.dts is None:
            continue
        h.update(bytes(pk))
        stamps.append((pk.pts, pk.dts))
    frames = len(stamps)
    rate = float(v.average_rate or v.guessed_rate or 24)
    c.close()
    return h.hexdigest(), stamps, frames / rate


h_src, ts_src, video_s = video_info(src)
if abs(len(pcm) / rate - video_s) > 0.05:
    fail(f"audio {len(pcm) / rate:.3f} s vs video {video_s:.3f} s")

if expect_locked:
    orig, osr, _ = decode_audio(src)
    if orig is None:
        fail("--expect-locked but the render has no audio")
    t_src = np.arange(len(orig)) / osr
    ref_rs = np.interp(t_src, np.arange(len(ref)) / rate, ref, right=0.0)
    n = min(len(orig), len(ref_rs))
    c_locked = float(np.corrcoef(orig[:n], ref_rs[:n])[0, 1])
    print(f"locked check: WAV vs render audio corr {c_locked:.3f} at lag 0")
    if not c_locked >= 0.5:
        fail("this WAV is not the soundtrack the render was locked to")

inp = av.open(src)
vin = inp.streams.video[0]
out = av.open(dst_real, "w")
vout = out.add_stream_from_template(vin)
aout = out.add_stream("aac", rate=rate)
aout.layout = "stereo"
aout.bit_rate = 256000
for pkt in inp.demux(vin):
    if pkt.dts is None:
        continue
    pkt.stream = vout
    out.mux(pkt)
pts = 0
for i in range(0, len(pcm), 1024):
    fr = av.AudioFrame.from_ndarray(np.ascontiguousarray(pcm[i:i + 1024].T), format="s16p", layout="stereo")
    fr.sample_rate = rate
    fr.pts = pts
    pts += fr.samples
    for p in aout.encode(fr):
        out.mux(p)
for p in aout.encode(None):
    out.mux(p)
out.close()
inp.close()

h_dst, ts_dst, _ = video_info(dst_real)
m, _sr, first = decode_audio(dst_real)


def corr(k):
    u, v = (m[k:], ref) if k >= 0 else (m, ref[-k:])
    n = min(len(u), len(v))
    return float(np.corrcoef(u[:n], v[:n])[0, 1])


coarse = max(range(-2048, 2049, 16), key=corr)
lag = max(range(coarse - 16, coarse + 17), key=corr)
cc = corr(lag)
level = 20 * np.log10(np.sqrt(np.mean(m[:len(ref)] ** 2)) / (np.sqrt(np.mean(ref ** 2)) + 1e-12) + 1e-12)
print(f"video packets: source {len(ts_src)} {h_src[:16]}, output {len(ts_dst)} {h_dst[:16]}, "
      f"timestamps {'same' if ts_src == ts_dst else 'DIFFERENT'}")
print(f"audio: first pts {first:.4f} s, lag {lag} samples, corr {cc:.4f}, level {level:+.2f} dB")
ok = (h_src == h_dst and ts_src == ts_dst and abs(first) < 1e-6 and lag == 0 and cc >= 0.99
      and abs(level) <= 0.5)
if not ok:
    fail(dst_real)
print("MUX_OK", dst_real)
