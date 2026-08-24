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
# Hide them so a stray test -f / exec would fail this unit run.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/submit-prompt.sh" <<'EOF'
#!/usr/bin/env bash
echo "submit-prompt.sh must not run in --offline-mp4 mode" >&2
exit 99
EOF
chmod +x "$TMP/bin/submit-prompt.sh"
# Prefer a PATH tripwire; the real script must not exec submit-prompt at all.
export PATH="$TMP/bin:$PATH"

"$SMOKE" --offline-mp4 "$TMP/stereo-tone.mp4"

# Do not pipe the checker under pipefail: a FAIL exit 1 is the assertion.
if out="$("$SMOKE" --offline-mp4 "$TMP/silent-video-only.mp4" 2>&1)"; then
  echo "expected failure on video-only mp4"; exit 1
fi
printf '%s\n' "$out" | grep -q 'audio,2'

if out="$("$SMOKE" --offline-mp4 "$TMP/mono-tone.mp4" 2>&1)"; then
  echo "expected failure on mono mp4"; exit 1
fi
printf '%s\n' "$out" | grep -q 'audio,1'

echo OK
