#!/usr/bin/env bash
# Submit the 5.17 s smoke graph, or probe an existing mp4.
# Exit 0 only if the file has a video stream and stereo audio (ffprobe audio,2).
# --offline-mp4: probe only. Do not test -f the workflow, call submit-prompt, or start Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKFLOW="$ROOT/workflows/h3-fl2va-smoke-5s17.json"
SUBMIT="$ROOT/scripts/submit-prompt.sh"

OFFLINE_MP4=""
PROMPT=""
SEED=""
NAME=""
FORWARD=()

usage() {
  echo "usage: $0 --offline-mp4 <path>" >&2
  echo "       $0 --prompt TEXT --seed N --name PREFIX [submit-prompt flags]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline-mp4)
      OFFLINE_MP4="${2:?usage: --offline-mp4 <path>}"
      shift 2
      ;;
    --prompt)
      PROMPT="${2:?}"
      shift 2
      ;;
    --seed)
      SEED="${2:?}"
      shift 2
      ;;
    --name)
      NAME="${2:?}"
      shift 2
      ;;
    --first-frame|--last-frame|--base-url|--output-root)
      FORWARD+=("$1" "${2:?}")
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      ;;
  esac
done

probe_mp4() {
  local mp4="$1"
  if [[ ! -f "$mp4" ]]; then
    echo "error: mp4 not found: $mp4" >&2
    exit 1
  fi
  local video audio
  video="$(
    ffprobe -v error -select_streams v:0 -show_entries stream=codec_type \
      -of csv=p=0 "$mp4"
  )"
  audio="$(
    ffprobe -v error -select_streams a:0 -show_entries stream=codec_type,channels \
      -of csv=p=0 "$mp4"
  )"
  if [[ "$video" != "video" ]]; then
    echo "FAIL: missing video stream (got ${video:-empty})" >&2
    exit 1
  fi
  if [[ "$audio" != "audio,2" ]]; then
    echo "FAIL: expected stereo audio,2 (got ${audio:-empty})" >&2
    exit 1
  fi
}

if [[ -n "$OFFLINE_MP4" ]]; then
  probe_mp4 "$OFFLINE_MP4"
  exit 0
fi

# Live path only: require the locked 5.17 s graph. Do not start Docker or ComfyUI.
if [[ ! -f "$WORKFLOW" ]]; then
  echo "error: missing workflow $WORKFLOW" >&2
  exit 1
fi
if [[ -z "$PROMPT" || -z "$SEED" || -z "$NAME" ]]; then
  echo "error: live mode requires --prompt --seed --name" >&2
  exit 2
fi

out="$("$SUBMIT" "$WORKFLOW" --prompt "$PROMPT" --seed "$SEED" --name "$NAME" ${FORWARD[@]+"${FORWARD[@]}"})"
mp4=""
while IFS= read -r line; do
  case "$line" in
    OUTPUT\ *)
      mp4="${line#OUTPUT }"
      ;;
  esac
done <<< "$out"

if [[ -z "$mp4" ]]; then
  echo "error: submit-prompt.sh did not print OUTPUT <path>" >&2
  printf '%s\n' "$out" >&2
  exit 1
fi

probe_mp4 "$mp4"
