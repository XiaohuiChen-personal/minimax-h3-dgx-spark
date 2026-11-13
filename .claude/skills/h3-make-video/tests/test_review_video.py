"""review_video.py on synthetic clips. Needs OpenCV, so it runs where OpenCV is (the Spark):

  ssh spark-2a60 'mkdir -p /tmp/h3-review/selftest'
  scp .claude/skills/h3-make-video/scripts/review_video.py .claude/skills/h3-make-video/tests/test_review_video.py \
      spark-2a60:/tmp/h3-review/selftest/
  ssh spark-2a60 'cd /tmp/h3-review/selftest && python3 test_review_video.py'

Under pytest without OpenCV (the MacBook) every test is skipped.
"""
import json
import math
import sys
import tempfile
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - the Mac
    cv2 = None

HERE = Path(__file__).resolve().parent
for cand in (HERE, HERE.parent / "scripts"):
    if (cand / "review_video.py").exists():
        sys.path.insert(0, str(cand))
        break

W, H, FPS = 640, 352, 24


def texture(seed, w, h):
    rng = np.random.default_rng(seed)
    img = (rng.random((h // 8, w // 8, 3)) * 255).astype(np.uint8)
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_CUBIC)
    for _ in range(60):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        cv2.rectangle(img, (x, y), (x + int(rng.integers(10, 60)), y + int(rng.integers(10, 60))),
                      tuple(int(v) for v in rng.integers(0, 255, 3)), -1)
    return img


def write(path, frames):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for f in frames:
        vw.write(f)
    vw.release()


def run(video, out):
    import review_video
    assert review_video.main([str(video), str(out)]) == 0
    return json.loads((out / "summary.json").read_text()), (out / "report.md").read_text()


def _skip():
    if cv2 is None:
        import pytest
        pytest.skip("needs OpenCV (run on the Spark)")


def test_fast_pan_is_not_a_cut_and_direction_is_right():
    _skip()
    with tempfile.TemporaryDirectory(dir=HERE) as d:
        d = Path(d)
        big = texture(1, W * 4, H)
        step = 24                                   # px/frame: raw change is far above --cut 25
        frames = [big[:, i * step:i * step + W].copy() for i in range(48)]
        write(d / "pan.mp4", frames)
        summary, report = run(d / "pan.mp4", d / "out")
        assert len(summary["shots"]) == 1, report
        cam = summary["shots"][0]["camera"]
        assert "camera moves right" in cam, cam      # window slides right = camera moves right
        assert summary["shots"][0]["bg_shift_x"] < -1.0   # background slid left by > 1 frame width
        assert "fast move, not a cut" in report
        assert (d / "out" / "stabilized" / "shot1-trail.jpg").exists()


def test_hard_cut_is_found_once():
    _skip()
    with tempfile.TemporaryDirectory(dir=HERE) as d:
        d = Path(d)
        a, b = texture(2, W, H), texture(3, W, H)
        write(d / "cut.mp4", [a] * 30 + [b] * 30)
        summary, report = run(d / "cut.mp4", d / "out")
        assert [s["first"] for s in summary["shots"]] == [0, 30], report
        assert all(s["camera"] == "static or near-static" for s in summary["shots"])


def test_static_clip_without_audio_and_detail_sheets():
    _skip()
    with tempfile.TemporaryDirectory(dir=HERE) as d:
        d = Path(d)
        img = texture(4, W, H)
        n = 100
        write(d / "static.mp4", [img] * n)
        summary, report = run(d / "static.mp4", d / "out")
        assert "no audio stream" in report
        detail = sorted((d / "out" / "detail").glob("detail-*.jpg"))
        assert len(detail) == math.ceil(math.ceil(n / 12) / 6)
        assert "freeze?" in report                   # 100 identical frames are flagged
        sheets = sorted((d / "out" / "sheets").glob("sheet-*.jpg"))
        assert len(sheets) == math.ceil(n / 30)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {exc!r}")
    sys.exit(1 if failed else 0)
