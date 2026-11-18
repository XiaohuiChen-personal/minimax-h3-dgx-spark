"""Offline tests for prepare_soundtrack.py. Run: python3 -m pytest -q .claude/skills/h3-make-video-fast/tests

mux_audio.py needs PyAV and a real mp4, so it is exercised on the Spark (its own MUX_OK checks).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
wavfile = pytest.importorskip("scipy.io.wavfile")

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_soundtrack.py"
sys.path.insert(0, str(SCRIPT.parent))
import prepare_soundtrack as ps  # noqa: E402

FS = 44100


def _music(path: Path, seconds=20.0, lead_silence=0.5, bpm=120.0) -> Path:
    """Decaying 440/660 Hz notes on every beat after a silent lead-in, plus a quiet pad."""
    t = np.arange(int(seconds * FS)) / FS
    x = 0.02 * np.sin(2 * np.pi * 220 * t)
    for b in np.arange(lead_silence, seconds, 60 / bpm):
        i = int(b * FS); n = min(int(0.25 * FS), len(t) - i)
        env = np.exp(-np.arange(n) / (0.05 * FS))
        x[i:i + n] += 0.3 * env * (np.sin(2 * np.pi * 440 * t[:n]) + 0.5 * np.sin(2 * np.pi * 660 * t[:n]))
    x[: int(lead_silence * FS)] = 0
    wavfile.write(str(path), FS, (np.stack([x, x], 1) * 32767).astype(np.int16))
    return path


def _sfx(path: Path, fs=32000) -> Path:
    """Silence, then a 0.3 s buzzy burst starting at 1.00 s."""
    rng = np.random.default_rng(0)
    x = np.zeros(2 * fs)
    n = int(0.3 * fs); t = np.arange(n) / fs
    x[fs:fs + n] = 0.5 * np.sign(np.sin(2 * np.pi * 90 * t)) * np.exp(-t / 0.15) + 0.05 * rng.standard_normal(n)
    wavfile.write(str(path), fs, (x * 32767).astype(np.int16))
    return path


def _run(args):
    r = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    return r, (json.loads(r.stdout) if r.returncode == 0 else None)


def test_lengths_rates_and_beats_without_events(tmp_path):
    music = _music(tmp_path / "m.wav")
    r, rep = _run([music, "--out-dir", tmp_path / "o", "--name", "s", "--frames", 362, "--auto-start"])
    assert r.returncode == 0, r.stderr
    rate, h3 = wavfile.read(rep["outputs"]["locked_32k"])
    assert rate == 32000 and h3.shape == (603 * 800, 2) and h3.dtype == np.int16
    rate, final = wavfile.read(rep["outputs"]["final"])
    assert rate == FS and len(final) == round(362 / 24 * FS)
    assert abs(rep["start_s"] - 0.49) < 0.02  # 10 ms before the first note at 0.50 s
    assert abs(rep["bpm"] - 120) < 3
    gaps = np.diff(rep["beats_s"])
    assert np.median(gaps) == pytest.approx(0.5, abs=0.02)
    assert rep["changed_regions_s"] == [] and rep["events"] == []
    assert np.abs(final[-10:]).max() < 50  # faded out


def test_event_lands_on_time_at_target_loudness_and_nothing_else_changes(tmp_path):
    music = _music(tmp_path / "m.wav")
    sfx = _sfx(tmp_path / "fx.wav")
    events = tmp_path / "ev.json"
    events.write_text(json.dumps({"events": [{"name": "fart", "wav": str(sfx), "src_start": 0.9,
                                              "src_onset": 1.0, "src_end": 1.4, "place_at": 6.25,
                                              "over_music_lu": 6}]}))
    common = [music, "--frames", 362, "--start", 0.49, "--name", "s"]
    r0, rep0 = _run([*common, "--out-dir", tmp_path / "plain"])
    r1, rep1 = _run([*common, "--out-dir", tmp_path / "fx", "--events", events])
    assert r0.returncode == 0 and r1.returncode == 0, r0.stderr + r1.stderr
    ev = rep1["events"][0]
    # The SFX alone sits 6 LU over the music, so music + SFX sits 10*log10(1 + 10**0.6) = 6.97 LU over it
    # (minus whatever the limiter took off the peaks).
    got = ev["mix_lufs_m"] - ev["music_lufs_m"]
    want = 10 * np.log10(1 + 10 ** 0.6)
    assert want + rep1["limiter"]["max_reduction_db"] - 0.5 <= got <= want + 0.3
    assert rep1["outputs"]["peak_dbfs"] <= -0.95
    (start, end), = rep1["changed_regions_s"]
    assert 6.1 <= start <= 6.25 and end <= 6.7
    _, plain = wavfile.read(rep0["outputs"]["final"])
    _, mixed = wavfile.read(rep1["outputs"]["final"])
    diff = np.abs(mixed.astype(float) - plain.astype(float)).max(1)
    onset = np.argmax(diff > 0.05 * 32768) / FS
    assert abs(onset - 6.25) < 0.02
    outside = np.r_[0:int(6.0 * FS), int(6.8 * FS):len(diff)]
    assert diff[outside].max() <= 2  # dither only


def test_limiter_only_touches_peaks_above_minus_one_dbfs():
    x = np.zeros((FS, 2)); x[1000:1100] = 1.2; x[30000:30010] = 0.5
    out, gain = ps.limit(x, FS)
    assert np.abs(out).max() <= 10 ** (-1 / 20) + 1e-9
    # 0.66 s after the clipped peak the 50 ms release has recovered to within 1e-5 (< 0.0001 dB)
    assert gain[30000] == pytest.approx(1.0, abs=1e-5) and gain[-1] == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("frames", [360, 4, 363])
def test_illegal_frame_counts_fail(tmp_path, frames):
    r, _ = _run([_music(tmp_path / "m.wav"), "--out-dir", tmp_path / "o", "--name", "s", "--frames", frames])
    assert r.returncode != 0 and "17n+5" in r.stderr


def test_event_outside_the_clip_fails(tmp_path):
    sfx = _sfx(tmp_path / "fx.wav")
    events = tmp_path / "ev.json"
    events.write_text(json.dumps({"events": [{"name": "late", "wav": str(sfx), "src_start": 0.9,
                                              "src_onset": 1.0, "src_end": 1.4, "place_at": 15.0}]}))
    r, _ = _run([_music(tmp_path / "m.wav"), "--out-dir", tmp_path / "o", "--name", "s", "--events", events])
    assert r.returncode != 0 and "does not fit" in r.stderr


def test_k_weighting_matches_bs1770_reference_sine():
    """BS.1770: a full-scale 997 Hz sine in one channel reads -3.01 LUFS (any sample rate)."""
    for fs in (32000, 44100, 48000):
        t = np.arange(int(1.0 * fs)) / fs
        x = np.stack([np.sin(2 * np.pi * 997 * t), np.zeros_like(t)], 1)
        assert ps.momentary_lufs(x, fs, int(0.3 * fs)) == pytest.approx(-3.01, abs=0.05), fs


def test_no_beats_reported_in_silence(tmp_path):
    """Music that stops at 8 s: no beats after it; the first beat is on the first note, not before it."""
    music = _music(tmp_path / "m.wav", seconds=8.0, lead_silence=0.64)
    r, rep = _run([music, "--out-dir", tmp_path / "o", "--name", "s", "--frames", 362, "--start", 0])
    assert r.returncode == 0, r.stderr
    assert "padded with silence" in r.stderr  # the warning goes to stderr, the report still parses
    assert rep["beats_s"][0] >= 0.6 and rep["beats_s"][-1] <= 8.1


def test_effect_over_silent_music_uses_the_absolute_target(tmp_path):
    silent = tmp_path / "silence.wav"
    wavfile.write(str(silent), FS, np.zeros((int(16 * FS), 2), np.int16))
    _sfx(tmp_path / "fx.wav")
    events = tmp_path / "ev.json"  # relative "wav": resolved next to the JSON file, not the current directory
    events.write_text(json.dumps({"events": [{"name": "boom", "wav": "fx.wav", "src_start": 0.9,
                                              "src_onset": 1.0, "src_end": 1.4, "place_at": 5.0}]}))
    r, rep = _run([silent, "--out-dir", tmp_path / "o", "--name", "s", "--events", events])
    assert r.returncode == 0, r.stderr
    ev = rep["events"][0]
    assert ev["mode"].startswith("absolute -16")
    assert ev["mix_lufs_m"] == pytest.approx(-16, abs=1.0)


@pytest.mark.parametrize("edit, needle", [
    ({"src_onset": 0.1, "src_start": 0.0, "src_end": 0.6}, "is silent"),   # onset window holds only silence
    ({"src_end": 0.95}, ">= 0.1 s"),                                       # cut shorter than 0.1 s
    ({"over_music_lu": 45}, "beyond +-30 dB"),
])
def test_bad_effects_fail_with_a_clear_error(tmp_path, edit, needle):
    sfx = _sfx(tmp_path / "fx.wav")
    ev = {"name": "x", "wav": str(sfx), "src_start": 0.9, "src_onset": 1.0, "src_end": 1.4, "place_at": 6.0}
    ev.update(edit)
    events = tmp_path / "ev.json"
    events.write_text(json.dumps({"events": [ev]}))
    r, _ = _run([_music(tmp_path / "m.wav"), "--out-dir", tmp_path / "o", "--name", "s", "--start", 0.49,
                 "--events", events])
    assert r.returncode != 0 and needle in r.stderr, r.stderr


def test_limiter_ramps_in_instead_of_stepping():
    x = np.full((FS, 2), 0.5); x[24000] = 1.5
    out, gain = ps.limit(x, FS)
    assert np.abs(out).max() <= 10 ** (-1 / 20) + 1e-9
    steps = np.abs(np.diff(20 * np.log10(gain[23500:24100])))
    assert steps.max() < 1.0  # dB per sample; an instant 4 dB step would click
