#!/usr/bin/env bash
# Unit: smoke-test.sh --offline-mp4. Fixtures are generated here; never commit *.mp4.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SMOKE="$ROOT/scripts/smoke-test.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Generate tiny fixtures with the host ffmpeg. Do not commit these files.
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=32x32:d=0.1 \
  -an -c:v mpeg4 \
  "$TMP/silent-video-only.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=32x32:d=0.1 \
  -f lavfi -i sine=frequency=440:sample_rate=48000:duration=0.1 \
  -ac 2 -c:v mpeg4 -c:a aac \
  "$TMP/stereo-tone.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=32x32:d=0.1 \
  -f lavfi -i sine=frequency=440:sample_rate=48000:duration=0.1 \
  -ac 1 -c:v mpeg4 -c:a aac \
  "$TMP/mono-tone.mp4"

# Confirm the required probe strings before calling the script.
stereo_probe="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_type,channels -of csv=p=0 "$TMP/stereo-tone.mp4")"
mono_probe="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_type,channels -of csv=p=0 "$TMP/mono-tone.mp4")"
video_only_probe="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_type,channels -of csv=p=0 "$TMP/silent-video-only.mp4")"
[[ "$stereo_probe" == "audio,2" ]]
[[ "$mono_probe" == "audio,1" ]]
[[ -z "$video_only_probe" ]]

# Offline must not require the Task 7 workflow JSON, submit-prompt.sh, or Docker.
# A PATH stub of submit-prompt.sh is not coverage: the real script uses $ROOT/scripts/...
# Copy smoke-test.sh into a tree with no workflows/ and no scripts/submit-prompt.sh.
ISOLATED="$TMP/isolated"
mkdir -p "$ISOLATED/scripts" "$TMP/bin"
cp "$SMOKE" "$ISOLATED/scripts/smoke-test.sh"
chmod +x "$ISOLATED/scripts/smoke-test.sh"
[[ ! -e "$ISOLATED/workflows" ]]
[[ ! -e "$ISOLATED/scripts/submit-prompt.sh" ]]
ISOLATED_SMOKE="$ISOLATED/scripts/smoke-test.sh"

cat > "$TMP/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "docker must not run in --offline-mp4 mode" >&2
exit 99
EOF
cat > "$TMP/bin/submit-prompt.sh" <<'EOF'
#!/usr/bin/env bash
echo "submit-prompt.sh must not run in --offline-mp4 mode" >&2
exit 99
EOF
chmod +x "$TMP/bin/docker" "$TMP/bin/submit-prompt.sh"
export PATH="$TMP/bin:$PATH"

# Isolation tripwire: this copy has no Task 7/9 files. Stereo must still exit 0.
"$ISOLATED_SMOKE" --offline-mp4 "$TMP/stereo-tone.mp4"

# Keep stereo PASS / video-only FAIL / mono FAIL on the isolated copy.
# Do not pipe the checker under pipefail: a FAIL exit 1 is the assertion.
if out="$("$ISOLATED_SMOKE" --offline-mp4 "$TMP/silent-video-only.mp4" 2>&1)"; then
  echo "expected failure on video-only mp4"; exit 1
fi
printf '%s\n' "$out" | grep -q 'audio,2'

if out="$("$ISOLATED_SMOKE" --offline-mp4 "$TMP/mono-tone.mp4" 2>&1)"; then
  echo "expected failure on mono mp4"; exit 1
fi
printf '%s\n' "$out" | grep -q 'audio,1'

# Live mode must reprint submit-prompt.sh stdout (OUTPUT on success, error JSON on failure).
LIVE="$TMP/live"
mkdir -p "$LIVE/scripts" "$LIVE/workflows"
cp "$SMOKE" "$LIVE/scripts/smoke-test.sh"
chmod +x "$LIVE/scripts/smoke-test.sh"
: > "$LIVE/workflows/h3-ref2va-smoke-5s17.json"
cat > "$LIVE/scripts/submit-prompt.sh" <<EOF
#!/usr/bin/env bash
if [[ "\${H3_SMOKE_SUBMIT_FAIL:-}" == "1" ]]; then
  printf '%s\n' '{"error":"prompt rejected"}'
  exit 7
fi
echo "OUTPUT $TMP/stereo-tone.mp4"
exit 0
EOF
chmod +x "$LIVE/scripts/submit-prompt.sh"
LIVE_SMOKE="$LIVE/scripts/smoke-test.sh"

live_ok="$("$LIVE_SMOKE" --prompt 'a cat' --seed 1 --name live-ok)"
printf '%s\n' "$live_ok" | grep -q "^OUTPUT $TMP/stereo-tone.mp4\$"

set +e
live_fail="$(H3_SMOKE_SUBMIT_FAIL=1 "$LIVE_SMOKE" --prompt 'a cat' --seed 1 --name live-fail 2>&1)"
live_rc=$?
set -e
[[ "$live_rc" -eq 7 ]]
printf '%s\n' "$live_fail" | grep -q 'prompt rejected'

# Default live graph is the Ref2VA 5.17 file. --workflow / --ref-image must reach submit.
grep -q 'WORKFLOW="$ROOT/workflows/h3-ref2va-smoke-5s17.json"' "$SMOKE"
if grep -q 'h3-fl2va-smoke-5s17.json' "$SMOKE"; then
  echo "smoke-test.sh default must not be the FL2VA 5.17 graph"; exit 1
fi

ARGS_LOG="$TMP/submit-args.txt"
CUSTOM_WF="$LIVE/workflows/custom-ref2va.json"
REF_IMG="$TMP/ref-still.jpg"
: > "$CUSTOM_WF"
: > "$REF_IMG"
cat > "$LIVE/scripts/submit-prompt.sh" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" > "$ARGS_LOG"
echo "OUTPUT $TMP/stereo-tone.mp4"
exit 0
EOF
chmod +x "$LIVE/scripts/submit-prompt.sh"

"$LIVE_SMOKE" --prompt 'a cat' --seed 1 --name live-ok \
  --workflow "$CUSTOM_WF" \
  --ref-image "$REF_IMG" >/dev/null

grep -q -- "$CUSTOM_WF" "$ARGS_LOG"
grep -q -- "--ref-image" "$ARGS_LOG"
grep -q -- "$REF_IMG" "$ARGS_LOG"

echo OK
