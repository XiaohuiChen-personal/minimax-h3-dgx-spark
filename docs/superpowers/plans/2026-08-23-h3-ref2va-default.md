# Ref2VA Default (Keep FL2VA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Fresh implementer per task, then a spec reviewer, then an **adversarial** reviewer that **fixes** issues, then **re-smoke**, then **commit + push**. Do **not** use executing-plans or implement in the parent’s own context.
>
> **Required subagent model:** Grok 4.6, xhigh effort, fast mode. Cursor Task slug: `cursor-grok-4.6-xhigh-fast`. Pass that slug on **every** implementer, spec reviewer, adversarial reviewer, and fixer. Do not inherit the parent model. Do not substitute Claude, GPT, or Composer.

**Goal:** Make **Ref2VA** the default H3 task when the container starts, while keeping the existing FL2VA graphs and submit path so a user can still ask for text-only / first-last-frame generates.

**Architecture:** Same long-lived ComfyUI on 8188. No new process and no invented DAG. Default start (`H3_TASK=ref2va`) fail-closes unless the Ref2VA DiT + Ref2V 4-step LoRA are on the host mount. The agent fills a **locked Ref2VA graph**, uploads reference images, `POST /prompt`, polls `/history/<id>`. FL2VA stays a second locked pair; selecting it is submitting those JSON files (and having those weights). ComfyUI loads whichever UNET the posted graph names. Do not preload a DiT in `entrypoint.sh`.

**Tech Stack:** Existing `h3-spark:local` image (ComfyUI `b78cec879b9460d5cb25228a83a942fb78d2cd24` already contains `MiniMaxH3ReferenceToVideo`), host weights under `$HOME/h3-weights`, `hf` 1.4.1, bash + Python 3 helpers, `pytest`.

## Global Constraints

- Follow `design/architecture.md`, `design/decisions.md`, `design/optimizations.md`, `design/operator.md`, `design/container.md`. Where this plan is more specific, **this plan wins**.
- Platform: `linux/arm64` only. Dockerfile keeps `FROM --platform=linux/arm64`.
- Never use the Spark system Python for GPU torch.
- Never bake `*.safetensors` / `*.pth` / `*.mp4` into git or a Docker layer.
- Never enable EasyCache, SageAttention 3, `--use-sage-attention`, Sol-Attn `flex_attention`, Turbo-SLA+Sol-Attn, or `--lowvram`.
- Do not require `H3_LICENSE_ACK` (D-13).
- One GPU job at a time. Do not start or restart ComfyUI except Task 7 (image rebuild / `H3_TASK` start). Tasks 1–6 must not `docker compose down` / `up` / `restart` / `kill`.
- Mount scheme stays subfolder binds. New DiT/LoRA files go into the existing `diffusion_models` and `loras` binds — no new volume for weights.
- Hugging Face: `hf download Comfy-Org/MiniMax-H3 <repo-relative-path> --local-dir DIR`. Never `huggingface-cli`. Never `--local-dir-use-symlinks`. Never `--include "*.safetensors"` on that repo.
- Do not switch the text encoder to NVFP4. Keep `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`.
- Do not use FL2VA Turbo LoRA on the Ref2VA DiT. Do not use Ref2VA Turbo LoRA on the FL2VA DiT.
- Official Comfy-Org R2V template is UI-format and **not** this product (INT8 Ref2VA + NVFP4 TE + 1344×768 + duration-math). Rebuild API-format graphs the way Task 7 of the FL2VA plan did.
- Prompt tags for Ref2VA are `<Picture 1>`, `<Picture 2>`, … (1-based). Do not write those tags in FL2VA graphs.
- Autogrow API encoding is a nested dict: `"ref_images": {"ref_image_0": ["24", 0], ...}`. Dotted keys also worked on this box; flattened `"ref_image_0"` **executes and crashes**. Lock the nested dict.
- `LoadImage` reads `/opt/ComfyUI/input`, **not** `/data`. `submit-prompt.py` must `POST /upload/image` then set the LoadImage filename. Do not write host paths or `/data/...` into `LoadImage.image`.
- Every new download appends `measurements/download-log.md` (same speed-log protocol as the FL2VA plan).
- Each task’s last “Commit” step is **commit only**. Parent close-out pushes. Never `--force`. Never `--no-verify` unless the operator said so.

## Feasibility already measured (2026-08-23, this Spark)

Do not redo these as a substitute for Task 8. They are why this plan is allowed.

| Probe | Result |
|---|---|
| ComfyUI | `deploy-comfyui-1` / `h3-spark:local` up; `/system_stats` 200 |
| Node in image | `GET /object_info/MiniMaxH3ReferenceToVideo` → required `clip, vae, audio_vae, prompt, width, height, length, ref_image_size`; optional autogrow `ref_images` (0–9) |
| Ref2VA weights on host | **absent**. Only `minimax_h3_fl2va_pruned_fp8_scaled.safetensors` |
| HF sizes | Ref2VA FP8 DiT `20958205608` B; Ref2V 4-step LoRA `1956193000` B (Comfy-Org) |
| Missing DiT fail-close | `POST` locked FL2VA graph with `unet_name=minimax_h3_ref2va_pruned_fp8_scaled.safetensors` → HTTP 400 `value_not_in_list` (combo is files on disk). Queue unchanged. |
| Nested `ref_images` | Condition+VAE-decode smoke, **no UNET**, `example.png` as `<Picture 1>`, length 5 → HTTP 200, `execution_success` in ~7 s, 5 PNGs under `~/h3-output/ref2va-schema-B_nested_*.png` |
| Dotted `ref_images.ref_image_0` | Also succeeded. Do not use it; lock nested. |
| Flat `ref_image_0` | History **error**: `unexpected keyword argument 'ref_image_0'` |
| `/upload/image` | `curl -F image=@...` → `{"name":"ref2va-upload-smoke.png","type":"input"}` in `/opt/ComfyUI/input` |
| `/data` mount | Empty; `LoadImage` cannot see it |
| Disk | 2.5 T free — enough for ~21 GB + 1.9 GB |
| What was **not** proven | A real Ref2VA **sample** (needs the DiT download + Task 8) |

ComfyUI does **not** load a DiT at process start. “Default Ref2VA at start” means: entrypoint requires Ref2VA files, default locked graphs and AGENTS generate path are Ref2VA. First Ref2VA `/prompt` pays the UNET load. Switching to FL2VA is posting the FL2VA graph; if VRAM is tight ComfyUI should evict. If a switch OOMs, restart once — do not restart per video.

## File map

| Path | Responsibility |
|---|---|
| `scripts/required-weights-shared.txt` | TE + both VAEs + SPAN (always required) |
| `scripts/required-weights-ref2va.txt` | Ref2VA FP8 DiT + Ref2V 4-step LoRA |
| `scripts/required-weights-fl2va.txt` | FL2VA FP8 DiT + FL2V 8-step LoRA |
| `scripts/required-weights.txt` | Compatibility wrapper: shared + **default task** (`H3_TASK` or `ref2va`) so old `check-weights.sh DIR` callers still work after the parser change |
| `scripts/check-weights.sh` | `check-weights.sh DIR [--task ref2va\|fl2va\|all]` |
| `scripts/download-weights.sh` | Same `--task`; default **`all`** so both DiTs land and FL2VA stays selectable |
| `scripts/entrypoint.sh` | `check-weights.sh /opt/ComfyUI/models --task "${H3_TASK:-ref2va}"` then the same ComfyUI argv |
| `scripts/submit-prompt.py` | `--ref-image` (repeatable, max 9): upload + LoadImage filename + nested `ref_images` |
| `scripts/smoke-test.sh` | Optional `--workflow`; default Ref2VA 5.17 s graph |
| `workflows/h3-ref2va-smoke-5s17.json` | 960×544, length 124, 4 steps, Ref2VA |
| `workflows/h3-ref2va-default-8s.json` | 960×544, length 192, 4 steps, Ref2VA |
| `workflows/h3-fl2va-*.json` | Unchanged product graphs |
| `tests/unit/test_check_weights.sh` | Shared / task / missing-file fixtures |
| `tests/unit/test_workflow_lock.py` | Split FL2VA vs Ref2VA forbidden strings |
| `tests/unit/test_submit_prompt.py` | `--ref-image` upload + nested wiring |
| `tests/fixtures/tiny-ref2va-workflow.json` | API graph with LoadImage + `MiniMaxH3ReferenceToVideo` |
| `deploy/compose.yaml` | `H3_TASK: ${H3_TASK:-ref2va}` |
| `deploy/Dockerfile` | `test -f` the two new workflow JSON files |
| `design/decisions.md` | New **D-15** |
| `AGENTS.md` | Default generate = Ref2VA graph + `--ref-image` |

## Decision lock (D-15) — implement this, do not reopen

**What we do.** Default task is **Ref2VA**. Files:

| Role | File |
|---|---|
| DiT | `diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors` |
| LoRA | `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` |
| TE / VAEs / SPAN | unchanged D-02 / D-04 |

Sampler for Ref2VA: Euler + simple, **4 steps** (5 sigma points including the final zero), shifts **6 / 3**, canvas **960×544**, SPAN 2×, Sage / Sol-Attn `triton_ref` / FBC `H3 Safe` unchanged.

**Why 4 steps.** Official Ref2V Turbo LoRA is 4-step. There is no Comfy-Org 8-step Ref2V LoRA. Do not strap the FL2V 8-step LoRA onto Ref2VA. D-06’s “8 steps for speech” stays on the FL2VA graphs.

**User selects FL2VA** by passing `workflows/h3-fl2va-default-8s.json` (or the 5.17 s smoke) to `submit-prompt.sh`. To make **start** require FL2VA instead of Ref2VA: `H3_TASK=fl2va` in `deploy/.env` or the compose environment, then recreate the container (Task 7). Both weight sets should already be on disk because the downloader defaults to `--task all`.

**Rejected.** Using `first_frame` for 3-view sheets. Preloading a UNET in the entrypoint. Requiring a license env flag. Shipping the stock R2V template unchanged.

---

### Task 1: Dual-task weight lists and `check-weights.sh`

**Files:**
- Create: `scripts/required-weights-shared.txt`
- Create: `scripts/required-weights-ref2va.txt`
- Create: `scripts/required-weights-fl2va.txt`
- Modify: `scripts/required-weights.txt`
- Modify: `scripts/check-weights.sh`
- Modify: `tests/unit/test_check_weights.sh`

**Interfaces:**
- Consumes: existing one-file list used by `check-weights.sh DIR`
- Produces: `check-weights.sh DIR [--task ref2va|fl2va|all]` ; default task is `$H3_TASK` if set, else `ref2va`. Exit 1 prints one `MISSING <rel>` line per missing file.

- [ ] **Step 1: Write the failing test**

Replace `tests/unit/test_check_weights.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK="$ROOT/scripts/check-weights.sh"

test -x "$CHECK"

SHARED=(
  text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
  vae/minimax_h3_video_vae_fp16.safetensors
  vae/minimax_h3_audio_vae_fp32.safetensors
  upscale_models/2x-spanx2-ch48.pth
)
REF2VA=(
  diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors
  loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
)
FL2VA=(
  diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors
  loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
)

FIX="$ROOT/tests/fixtures/weights-tasks"
rm -rf "$FIX"
for tree in complete-ref2va complete-fl2va complete-all missing-ref2va-dit; do
  mkdir -p "$FIX/$tree"/{diffusion_models,text_encoders,vae,loras,upscale_models}
done

touch_list() {
  local dest="$1"; shift
  local rel
  for rel in "$@"; do
    touch "$dest/$rel"
  done
}

touch_list "$FIX/complete-ref2va" "${SHARED[@]}" "${REF2VA[@]}"
touch_list "$FIX/complete-fl2va" "${SHARED[@]}" "${FL2VA[@]}"
touch_list "$FIX/complete-all" "${SHARED[@]}" "${REF2VA[@]}" "${FL2VA[@]}"
touch_list "$FIX/missing-ref2va-dit" "${SHARED[@]}" "${REF2VA[1]}" "${FL2VA[@]}"

"$CHECK" "$FIX/complete-ref2va" --task ref2va
"$CHECK" "$FIX/complete-fl2va" --task fl2va
"$CHECK" "$FIX/complete-all" --task all

if out="$("$CHECK" "$FIX/complete-fl2va" --task ref2va)"; then
  echo "expected failure: fl2va tree is not enough for ref2va"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

if out="$("$CHECK" "$FIX/missing-ref2va-dit" --task ref2va)"; then
  echo "expected failure on missing Ref2VA DiT"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

# default task is ref2va (no --task, no H3_TASK)
if out="$("$CHECK" "$FIX/complete-fl2va")"; then
  echo "expected default task ref2va to reject fl2va-only tree"; exit 1
fi

H3_TASK=fl2va "$CHECK" "$FIX/complete-fl2va"
echo OK
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
bash tests/unit/test_check_weights.sh
```

Expected: missing new list files and/or `--task` not parsed.

- [ ] **Step 3: Write the lists and checker**

`scripts/required-weights-shared.txt`:

```
text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
vae/minimax_h3_video_vae_fp16.safetensors
vae/minimax_h3_audio_vae_fp32.safetensors
upscale_models/2x-spanx2-ch48.pth
```

`scripts/required-weights-ref2va.txt`:

```
diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors
loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

`scripts/required-weights-fl2va.txt`:

```
diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors
loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
```

`scripts/required-weights.txt` (keep for humans and any old reader; checker must **not** treat this as the only source after the split):

```
# Default start set = shared + ref2va. Prefer --task.
# shared
text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
vae/minimax_h3_video_vae_fp16.safetensors
vae/minimax_h3_audio_vae_fp32.safetensors
upscale_models/2x-spanx2-ch48.pth
# ref2va (default H3_TASK)
diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors
loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

`scripts/check-weights.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
  echo "usage: check-weights.sh <weights-dir> [--task ref2va|fl2va|all]" >&2
  exit 1
}

DIR=""
TASK="${H3_TASK:-ref2va}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)
      TASK="${2:-}"; shift 2 ;;
    -h|--help)
      usage ;;
    *)
      if [[ -z "$DIR" && "$1" != --* ]]; then
        DIR="$1"; shift
      else
        usage
      fi ;;
  esac
done
[[ -n "$DIR" ]] || usage
case "$TASK" in
  ref2va|fl2va|all) ;;
  *) echo "error: unknown --task $TASK" >&2; exit 1 ;;
esac

lists=("$ROOT/required-weights-shared.txt")
case "$TASK" in
  ref2va) lists+=("$ROOT/required-weights-ref2va.txt") ;;
  fl2va) lists+=("$ROOT/required-weights-fl2va.txt") ;;
  all) lists+=("$ROOT/required-weights-ref2va.txt" "$ROOT/required-weights-fl2va.txt") ;;
esac

missing=0
for list in "${lists[@]}"; do
  while IFS= read -r rel || [[ -n "$rel" ]]; do
    [[ -z "$rel" || "$rel" == \#* ]] && continue
    if [[ ! -f "$DIR/$rel" ]]; then
      echo "MISSING $rel"
      missing=1
    fi
  done < "$list"
done
exit "$missing"
```

- [ ] **Step 4: Run the test and confirm it passes**

```bash
bash tests/unit/test_check_weights.sh
```

Expected: `OK`

- [ ] **Step 5: Commit only**

```bash
git add scripts/required-weights.txt scripts/required-weights-shared.txt \
  scripts/required-weights-ref2va.txt scripts/required-weights-fl2va.txt \
  scripts/check-weights.sh tests/unit/test_check_weights.sh
git commit -m "$(cat <<'EOF'
Split weight checks so Ref2VA is the default start task.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke unit tests → push).

---

### Task 2: Download Ref2VA weights (script + this Spark)

**Files:**
- Modify: `scripts/download-weights.sh`
- Modify: `tests/unit/test_download_weights_help.sh`
- Modify: `measurements/download-log.md` (after the real pull)

**Interfaces:**
- Consumes: the three list files from Task 1
- Produces: `download-weights.sh DIR [--task ref2va|fl2va|all]`. Default `--task all`. Still `usage` + exit ≠ 0 when DIR is missing.

- [ ] **Step 1: Extend the help test**

Append to `tests/unit/test_download_weights_help.sh`:

```bash
if out="$("$SCRIPT" --task ref2va 2>&1)"; then
  echo "expected failure with --task and no dir"; exit 1
fi
printf '%s\n' "$out" | grep -qi usage
echo OK
```

Keep the existing no-args usage check.

- [ ] **Step 2: Run the help test (expect fail until the parser exists)**

```bash
bash tests/unit/test_download_weights_help.sh
```

- [ ] **Step 3: Parse `--task` and union the list files**

In `scripts/download-weights.sh`:

- Usage becomes: `download-weights.sh <dir> [--task ref2va|fl2va|all]`
- Default `TASK=all` (not `H3_TASK`) so one pull leaves FL2VA selectable
- Build `hf_paths` / the fetch loop from `required-weights-shared.txt` plus the task file(s). Do **not** read the comment-y `required-weights.txt` as the fetch list (it omits FL2VA).
- SPAN still uses the existing `fetch_span` / `SPAN_REL` path
- End with `"$CHECK" "$DIR" --task "$TASK"` (when TASK is `all`, that is `--task all`)

Keep `hf download "$HF_REPO" "$rel" --local-dir "$DIR"`. No `--include "*.safetensors"`.

- [ ] **Step 4: Re-run the help test**

```bash
bash tests/unit/test_download_weights_help.sh
```

Expected: `OK`

- [ ] **Step 5: Real download on this Spark**

```bash
./scripts/download-weights.sh "$HOME/h3-weights" --task all
./scripts/check-weights.sh "$HOME/h3-weights" --task all
```

Append one speed-log row per file (cache-hit rows for files already present). New files that must appear:

- `diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors` (expected 20958205608 B)
- `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` (expected 1956193000 B)

Do not download INT8 Ref2VA, unpruned, NVFP4 TE, or the 471 G snapshot.

- [ ] **Step 6: Commit only the script + log (never the weights)**

```bash
git add scripts/download-weights.sh tests/unit/test_download_weights_help.sh \
  measurements/download-log.md
git commit -m "$(cat <<'EOF'
Download Ref2VA DiT and LoRA without dropping the FL2VA set.

EOF
)"
```

Then parent close-out. After this task the **running** container can see the new files (same binds) without a rebuild. Do not submit a Ref2VA sample yet — graphs do not exist.

---

### Task 3: `submit-prompt.py` `--ref-image`

**Files:**
- Create: `tests/fixtures/tiny-ref2va-workflow.json`
- Modify: `scripts/submit-prompt.py`
- Modify: `tests/unit/test_submit_prompt.py`

**Interfaces:**
- Consumes: API graph with `LoadImage` nodes whose `_meta.title` is `ref_image_0` … `ref_image_8`, and a `MiniMaxH3ReferenceToVideo` node
- Produces: `--ref-image PATH` repeatable (max 9). For each path: `POST {base}/upload/image` as multipart field `image`, then set that LoadImage `inputs.image` to the uploaded `name` (not a host path, not `/data/...`). Rewrite the Ref2VA node’s `inputs.ref_images` to a nested dict `{ "ref_image_0": ["<load-node-id>", 0], ... }` in upload order. Fail-close if `--ref-image` is set and there are not enough `ref_image_*` LoadImage nodes, or if upload is not HTTP 200. Keep `--first-frame` / `--last-frame` behavior on FL2VA graphs unchanged.

- [ ] **Step 1: Add the fixture**

`tests/fixtures/tiny-ref2va-workflow.json`:

```json
{
  "10": {
    "class_type": "MiniMaxH3ReferenceToVideo",
    "inputs": {
      "prompt": "LOCKED_PLACEHOLDER",
      "width": 960,
      "height": 544,
      "length": 124,
      "ref_image_size": "match"
    }
  },
  "11": {
    "class_type": "RandomNoise",
    "inputs": { "noise_seed": 0 }
  },
  "23": {
    "class_type": "SaveVideo",
    "inputs": { "filename_prefix": "LOCKED_PLACEHOLDER" }
  },
  "24": {
    "class_type": "LoadImage",
    "_meta": { "title": "ref_image_0" },
    "inputs": { "image": "example.png" }
  },
  "25": {
    "class_type": "LoadImage",
    "_meta": { "title": "ref_image_1" },
    "inputs": { "image": "example.png" }
  }
}
```

- [ ] **Step 2: Write failing pytest**

Add to `tests/unit/test_submit_prompt.py` (extend `MockComfyHandler.do_POST` so `/upload/image` returns `{"name": "<original-filename>", "subfolder": "", "type": "input"}` and records `self.server.uploads`):

```python
def test_ref_images_upload_and_nested_wiring(tmp_path, mock_comfy):
    workflow = tmp_path / "tiny-ref2va-workflow.json"
    shutil.copy(REPO / "tests/fixtures/tiny-ref2va-workflow.json", workflow)
    output_root = tmp_path / "out"
    output_root.mkdir()
    img0 = tmp_path / "blue.png"
    img1 = tmp_path / "yellow.png"
    img0.write_bytes(b"x")
    img1.write_bytes(b"y")
    port = mock_comfy.server_address[1]
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), str(workflow),
            "--prompt", "<Picture 1> blue bird. <Picture 2> yellow bird.",
            "--seed", "7", "--name", "unit",
            "--base-url", f"http://127.0.0.1:{port}",
            "--output-root", str(output_root),
            "--ref-image", str(img0), "--ref-image", str(img1),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    graph = mock_comfy.posted[0]["prompt"]
    assert graph["24"]["inputs"]["image"] == "blue.png"
    assert graph["25"]["inputs"]["image"] == "yellow.png"
    assert graph["10"]["inputs"]["ref_images"] == {
        "ref_image_0": ["24", 0],
        "ref_image_1": ["25", 0],
    }
    assert "ref_image_0" not in graph["10"]["inputs"]
    assert mock_comfy.uploads == ["blue.png", "yellow.png"]


def test_ref_image_fails_on_fl2va_fixture_without_loadimage(tmp_path, mock_comfy):
    img = tmp_path / "blue.png"
    img.write_bytes(b"x")
    port = mock_comfy.server_address[1]
    result, _output_root, _workflow = _run_submit(
        tmp_path, port, extra=["--ref-image", str(img)]
    )
    assert result.returncode != 0
    assert "ref-image" in (result.stderr + result.stdout).lower()
    assert not mock_comfy.posted
```

- [ ] **Step 3: Run pytest and confirm the new tests fail**

```bash
python3 -m pytest tests/unit/test_submit_prompt.py::test_ref_images_upload_and_nested_wiring \
  tests/unit/test_submit_prompt.py::test_ref_image_fails_on_fl2va_fixture_without_loadimage -v
```

- [ ] **Step 4: Implement the flags**

In `scripts/submit-prompt.py`:

- Add `--ref-image` with `action="append"`, default `None`
- Cap at 9 paths
- Implement `upload_input_image(base_url: str, host_path: str) -> str` using `urllib.request` multipart (stdlib only; no new dependency). POST `{base}/upload/image`. Return the JSON `name`.
- `load_image_nodes_by_title(graph) -> list[tuple[str, dict]]` sorted by the integer suffix of `ref_image_N`
- After prompt/seed/name patches: if `--ref-image` is set, upload each file, patch that many LoadImage `image` scalars, set **exactly one** `MiniMaxH3ReferenceToVideo` node’s `inputs["ref_images"]` nested dict, and delete any flat `ref_image_*` keys on that node
- If no matching LoadImage titles or no Ref2VA node: print an error and exit 1 (do not POST `/prompt`)

Keep rewriting `--first-frame` / `--last-frame` as today (scalar path → `/data/...`). Those flags stay FL2VA-only.

- [ ] **Step 5: Run the unit file**

```bash
python3 -m pytest tests/unit/test_submit_prompt.py -v
```

Expected: all PASS. Do not `|| true`.

- [ ] **Step 6: Commit only**

```bash
git add scripts/submit-prompt.py tests/unit/test_submit_prompt.py \
  tests/fixtures/tiny-ref2va-workflow.json
git commit -m "$(cat <<'EOF'
Wire Ref2VA reference images through upload and nested autogrow.

EOF
)"
```

Then parent close-out.

---

### Task 4: Locked Ref2VA graphs and lock tests

**Files:**
- Create: `workflows/h3-ref2va-smoke-5s17.json`
- Create: `workflows/h3-ref2va-default-8s.json`
- Modify: `tests/unit/test_workflow_lock.py`
- Modify: `scripts/smoke-test.sh`

**Interfaces:**
- Consumes: `workflows/h3-fl2va-default-8s.json` as the structural template (same Sage / Sol-Attn / FBC / SPAN / SaveVideo chain)
- Produces: two API-format Ref2VA graphs. Smoke `length=124`, default `length=192`. Both: width 960, height 544, steps 4, Ref2VA FP8 UNET, Ref2V 4-step LoRA, `MiniMaxH3ReferenceToVideo` with `audio_vae` linked to the audio VAE loader, `ref_image_size=match`, six `LoadImage` nodes titled `ref_image_0` … `ref_image_5` (so `--ref-image` can attach up to 6 without editing JSON). Do **not** put a `ref_images` dict in the committed JSON (0 refs until submit wires it). Default prompt may contain `<Picture 1>` / `<Picture 2>` as documentation of the tag language.

- [ ] **Step 1: Write lock tests first**

Add to `tests/unit/test_workflow_lock.py` (keep the existing FL2VA tests and their forbidden list, including `ref2va` and `MiniMaxH3ReferenceToVideo` **only on the FL2VA files**):

```python
def test_ref2va_smoke_and_default():
    smoke = load("h3-ref2va-smoke-5s17.json")
    default = load("h3-ref2va-default-8s.json")
    assert 124 in int_inputs(smoke, "length")
    assert 192 not in int_inputs(smoke, "length")
    assert 192 in int_inputs(default, "length")
    assert 124 not in int_inputs(default, "length")
    for name in ("h3-ref2va-smoke-5s17.json", "h3-ref2va-default-8s.json"):
        raw = (ROOT / "workflows" / name).read_text()
        g = load(name)
        assert 960 in int_inputs(g, "width")
        assert 544 in int_inputs(g, "height")
        assert 4 in int_inputs(g, "steps")
        assert 8 not in int_inputs(g, "steps")
        assert "MiniMaxH3ReferenceToVideo" in raw
        assert "minimax_h3_ref2va_pruned_fp8_scaled" in raw
        assert "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16" in raw
        assert "qwen3vl_32b_minimax_h3_int8_convrot" in raw
        assert "triton_ref" in raw
        assert "H3 Safe" in raw or "H3Safe" in raw
        assert "ModelSamplingAV" in raw
        for bad in (
            "EasyCache",
            "flex_attention",
            "lowvram",
            "nvfp4",
            "minimax_h3_fl2va_pruned_fp8_scaled",
            "minimax_h3_fl2v_turbo_8step",
            "minimax_h3_ref2va_pruned_int8_convrot",
            "MiniMaxH3ImageToVideo",
        ):
            assert bad not in raw, bad
        titles = [
            (node.get("_meta") or {}).get("title")
            for node in prompt_graph(g).values()
            if node.get("class_type") == "LoadImage"
        ]
        assert titles == [f"ref_image_{i}" for i in range(6)]


def test_fl2va_graphs_still_forbid_ref2va():
    for name in ("h3-fl2va-smoke-5s17.json", "h3-fl2va-default-8s.json"):
        raw = (ROOT / "workflows" / name).read_text()
        assert "MiniMaxH3ReferenceToVideo" not in raw
        assert "ref2va" not in raw
        assert "<Picture " not in raw
```

- [ ] **Step 2: Run lock tests (expect fail — files missing)**

```bash
python3 -m pytest tests/unit/test_workflow_lock.py -v
```

- [ ] **Step 3: Build the two JSON files**

Copy `workflows/h3-fl2va-default-8s.json` to both new names, then apply **all** of these edits (smoke uses `length` 124; default uses 192):

1. Node `1` `unet_name` → `minimax_h3_ref2va_pruned_fp8_scaled.safetensors`
2. Node `5` `lora_name` → `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors`
3. Node `13` `steps` → `4`
4. Replace node `10` with:

```json
"10": {
  "class_type": "MiniMaxH3ReferenceToVideo",
  "_meta": {
    "title": "Ref2VA condition + AV latent"
  },
  "inputs": {
    "clip": ["2", 0],
    "vae": ["3", 0],
    "audio_vae": ["4", 0],
    "prompt": "<Picture 1> is the blue monk parakeet identity. <Picture 2> is the yellow monk parakeet identity. A quiet scene. No speech.",
    "width": 960,
    "height": 544,
    "length": 192,
    "ref_image_size": "match"
  }
}
```

(Smoke file: `"length": 124`.)

5. Add LoadImage nodes `24`–`29`:

```json
"24": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_0" },
  "inputs": { "image": "example.png" }
}
```

Same for `25`–`29` with titles `ref_image_1` … `ref_image_5`. They stay **unlinked** until `submit-prompt.py` writes `ref_images`.

6. Keep nodes 6–9, 11–23, SPAN crop, SaveVideo. Default `filename_prefix`: `h3-ref2va` (smoke: `h3-ref2va-smoke`).
7. Do not add `first_frame` / `last_frame`. Do not add EasyCache / `flex_attention` / NVFP4.

- [ ] **Step 4: Point smoke-test.sh at the Ref2VA 5.17 s graph by default**

In `scripts/smoke-test.sh`:

- Add `--workflow PATH` (optional)
- Default `WORKFLOW` to `$ROOT/workflows/h3-ref2va-smoke-5s17.json`
- Keep `--offline-mp4` behavior unchanged (no workflow read)
- Forward `--ref-image` the same way `--first-frame` is forwarded today

Live invocation becomes:

```bash
./scripts/smoke-test.sh --prompt "<Picture 1> A quiet kitchen." --seed 42 --name smoke-ref2va-5s17 \
  --ref-image "$HOME/h3-data/blue.png"
```

Do **not** run that live command in this task.

- [ ] **Step 5: Run lock tests**

```bash
python3 -m pytest tests/unit/test_workflow_lock.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit only**

```bash
git add workflows/h3-ref2va-smoke-5s17.json workflows/h3-ref2va-default-8s.json \
  tests/unit/test_workflow_lock.py scripts/smoke-test.sh
git commit -m "$(cat <<'EOF'
Lock Ref2VA 5.17 s and 8.00 s graphs next to the FL2VA pair.

EOF
)"
```

Then parent close-out.

---

### Task 5: `H3_TASK` at container start

**Files:**
- Modify: `scripts/entrypoint.sh`
- Modify: `tests/unit/test_entrypoint_flags.sh`
- Modify: `deploy/compose.yaml`
- Modify: `deploy/Dockerfile`

**Interfaces:**
- Consumes: Task 1 `check-weights.sh --task`
- Produces: start requires Ref2VA unless `H3_TASK=fl2va`. Same ComfyUI argv. No UNET warmup. No license gate.

- [ ] **Step 1: Extend the entrypoint flag test**

Append to `tests/unit/test_entrypoint_flags.sh`:

```bash
grep -q 'H3_TASK' "$ENTRY"
grep -q -- '--task' "$ENTRY"
if grep -E -- 'lowvram|novram|use-sage-attention|H3_LICENSE_ACK' "$ENTRY"; then
  echo "forbidden flag or license gate in entrypoint"; exit 1
fi
```

- [ ] **Step 2: Run it (expect fail until entrypoint reads `H3_TASK`)**

```bash
bash tests/unit/test_entrypoint_flags.sh
```

- [ ] **Step 3: Change the entrypoint weight check**

Replace the check line in `scripts/entrypoint.sh` with:

```bash
TASK="${H3_TASK:-ref2va}"
case "$TASK" in
  ref2va|fl2va) ;;
  *) echo "error: H3_TASK must be ref2va or fl2va (got $TASK)" >&2; exit 1 ;;
esac
"${ROOT}/check-weights.sh" /opt/ComfyUI/models --task "$TASK"
```

Do not accept `all` here. Start needs one default task. Both files can still be on disk.

`deploy/compose.yaml` — under `comfyui` add:

```yaml
    environment:
      H3_TASK: ${H3_TASK:-ref2va}
```

Do not add a new weight volume.

`deploy/Dockerfile` — after the existing workflow `test -f` lines add:

```
    && test -f /opt/h3/workflows/h3-ref2va-smoke-5s17.json \
    && test -f /opt/h3/workflows/h3-ref2va-default-8s.json
```

- [ ] **Step 4: Re-run entrypoint tests**

```bash
bash tests/unit/test_entrypoint_flags.sh
```

Expected: `OK`

- [ ] **Step 5: Commit only**

```bash
git add scripts/entrypoint.sh tests/unit/test_entrypoint_flags.sh \
  deploy/compose.yaml deploy/Dockerfile
git commit -m "$(cat <<'EOF'
Default container start to Ref2VA weights via H3_TASK.

EOF
)"
```

Then parent close-out. **Still do not recreate the container** until Task 7.

---

### Task 6: Design and agent docs (D-15)

**Files:**
- Modify: `design/decisions.md` (add D-15; do not reopen D-01…D-14)
- Modify: `design/architecture.md` (Ref2VA is now a shipped second graph, default generate path)
- Modify: `design/operator.md` (default graph, `--ref-image`, `H3_TASK`, `/upload/image`, no `<Picture N>` on FL2VA)
- Modify: `design/container.md` (required start set is shared + Ref2VA; FL2VA optional on disk)
- Modify: `design/README.md` (D-01…D-15; point at this plan)
- Modify: `AGENTS.md` (Generate a video table: default = `workflows/h3-ref2va-default-8s.json`; FL2VA still listed; `--ref-image`; still no negative prompt)
- Modify: `workflows/README.md` (four locked graphs; Ref2VA pair may contain `<Picture N>` and `MiniMaxH3ReferenceToVideo`)
- Modify: `scripts/README.md`
- Modify: `deploy/README.md` (default generate command uses the Ref2VA 8 s graph)
- Modify: `docs/design/*.html` to match the markdown (same content, no new stack)

**Interfaces:**
- Consumes: D-15 text from this plan’s “Decision lock”
- Produces: docs that tell an agent to default to Ref2VA and how to select FL2VA

- [ ] **Step 1: Write D-15 into `design/decisions.md`**

Copy the “Decision lock (D-15)” section from this plan into a card with Status **adopted for implementation**. Include the file table, 4-step reason, how to select FL2VA, and Rejected list.

- [ ] **Step 2: Update AGENTS.md generate table**

Replace the “Pick a locked workflow” table so the **default / about 8 seconds** row is `workflows/h3-ref2va-default-8s.json`. Keep the FL2VA 8 s and 5.17 s rows as “text-only / no identity images”. Add `--ref-image` to the inputs table (optional, host files, uploaded). State that 3-view sheets are Ref2VA identity, **not** `first_frame`.

- [ ] **Step 3: Update the other markdown files listed above**

Do not claim a live Ref2VA mp4 exists yet.

- [ ] **Step 4: Mirror HTML under `docs/design/`**

- [ ] **Step 5: Commit only**

```bash
git add design AGENTS.md workflows/README.md scripts/README.md \
  deploy/README.md docs/design
git commit -m "$(cat <<'EOF'
Document Ref2VA as the default task and keep FL2VA selectable.

EOF
)"
```

Then parent close-out.

---

### Task 7: Rebuild the image and start default Ref2VA

**Files:** none in git except a download-log row if the build clone timings are appended (optional; do not invent rows).

**Interfaces:**
- Consumes: Task 2 weights on the host (`--task all`), Task 5 compose/entrypoint/Dockerfile, Task 4 JSON copied into the image
- Produces: `h3-spark:local` rebuilt; container recreated with `H3_TASK=ref2va`; `/system_stats` 200

The operator asked for this change, so this task **may** `docker compose down` / `build` / `up -d`. Do it once. Do not restart again for Task 8.

- [ ] **Step 1: Confirm host weights**

```bash
./scripts/check-weights.sh "$HOME/h3-weights" --task all
```

Expected: exit 0.

- [ ] **Step 2: Rebuild and recreate from the repository root**

```bash
docker compose -f deploy/compose.yaml down
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
```

Do not set `H3_LICENSE_ACK`. Do not pass `--lowvram`. Time the build if layers actually transfer; cache-hit → `n/a` in the speed log.

- [ ] **Step 3: Health**

```bash
curl -fsS http://127.0.0.1:8188/system_stats
docker compose -f deploy/compose.yaml ps
```

Expected: JSON with `cuda:0 NVIDIA GB10`; service `Up`.

- [ ] **Step 4: Confirm both UNETs are now in the combo**

```bash
curl -fsS http://127.0.0.1:8188/object_info/UNETLoader \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["UNETLoader"]["input"]["required"]["unet_name"][0])'
```

Expected list includes **both** `minimax_h3_ref2va_pruned_fp8_scaled.safetensors` and `minimax_h3_fl2va_pruned_fp8_scaled.safetensors`.

- [ ] **Step 5: Confirm start still fail-closes if Ref2VA is missing (offline, no second compose)**

Already covered by Task 1. Do not delete host weights to retest live.

- [ ] **Step 6: Commit only if compose/docs pins changed**

If `deploy/README.md` or download-log gained build timings:

```bash
git add deploy/README.md measurements/download-log.md
git commit -m "$(cat <<'EOF'
Record the Ref2VA-default image rebuild.

EOF
)"
```

If nothing changed in git, do not create an empty commit. Then parent close-out (`curl /system_stats` is the re-smoke).

---

### Task 8: Live Ref2VA smoke, then prove FL2VA is still selectable

**Files:**
- None required. Optional: a line in `measurements/prereq.md` for the live Ref2VA smoke, modeled on the existing Task 10 FL2VA paragraph.

**Interfaces:**
- Consumes: running server from Task 7, `workflows/h3-ref2va-smoke-5s17.json`, `--ref-image`
- Produces: host mp4 under `~/h3-output` with video + stereo audio; FL2VA graph still accepted by `/prompt` validation

- [ ] **Step 1: Put a reference still in `~/h3-data`**

Use any real PNG/JPEG the operator cares about (the blue 3-view sheet is fine for this smoke). Example:

```bash
mkdir -p "$HOME/h3-data"
# copy the operator's blue 3-view into $HOME/h3-data/blue-3view.jpg
test -f "$HOME/h3-data/blue-3view.jpg"
```

Do not commit the image.

- [ ] **Step 2: Live Ref2VA 5.17 s**

Do **not** restart ComfyUI.

```bash
./scripts/smoke-test.sh \
  --prompt "<Picture 1> is the only bird. A quiet kitchen, morning light. No speech. Soft room tone only." \
  --seed 42 \
  --name smoke-ref2va-5s17 \
  --ref-image "$HOME/h3-data/blue-3view.jpg"
```

Wait for `OUTPUT /home/xiaohui_chen/h3-output/smoke-ref2va-5s17_00001_.mp4` (SaveVideo suffix). Then:

```bash
./scripts/smoke-test.sh --offline-mp4 "$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4"
```

Expected: exit 0, `ffprobe` video 1920x1080 24 fps + `audio,2`. Record wall-clock in `measurements/prereq.md` if you touch that file.

- [ ] **Step 3: FL2VA still selectable (validation, no second 8 s job unless the operator asks)**

```bash
python3 - <<'PY'
import json, urllib.request, urllib.error
from pathlib import Path
g = json.loads(Path("workflows/h3-fl2va-smoke-5s17.json").read_text())
req = urllib.request.Request(
    "http://127.0.0.1:8188/prompt",
    data=json.dumps({"prompt": g}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        print("HTTP", resp.status, "prompt_id", body.get("prompt_id"), "node_errors", body.get("node_errors"))
        # Immediately interrupt so we do not steal the GPU for an unsolicited FL2VA sample.
        pid = body.get("prompt_id")
        if pid:
            del_req = urllib.request.Request(
                "http://127.0.0.1:8188/queue",
                data=json.dumps({"delete": [pid]}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(del_req, timeout=10).read()
            except Exception as exc:
                print("queue delete skipped", exc)
except urllib.error.HTTPError as exc:
    raise SystemExit(exc.read().decode())
PY
```

Expected: HTTP 200 and empty `node_errors` (UNET name is on disk). If `/queue` delete is not supported on this ComfyUI, **do not** leave a surprise 5.17 s job running — interrupt via `POST /interrupt` and tell the operator.

If the operator explicitly wants a live FL2VA re-smoke, use the existing command (do not invent a graph):

```bash
./scripts/submit-prompt.sh workflows/h3-fl2va-smoke-5s17.json \
  --prompt "A quiet kitchen, morning light, a glass of water on the table." \
  --seed 42 --name smoke-5s17-fl2va-re
```

- [ ] **Step 4: Commit measurements only if you wrote them**

```bash
git add measurements/prereq.md
git commit -m "$(cat <<'EOF'
Record the first live Ref2VA smoke on this Spark.

EOF
)"
```

Then parent close-out. Do not commit the mp4.

---

## Self-review

**Spec coverage**

| Requirement | Task |
|---|---|
| Default start = Ref2VA weights | 1, 5, 7 |
| User can still specify FL2VA | 2 (`--task all`), 4 (graphs kept), 5 (`H3_TASK=fl2va`), 6 (docs), 8 (validation) |
| 3-view / identity images | 3 (`--ref-image`), 4 (LoadImage titles), 6 (AGENTS) |
| Nested autogrow only | 3 tests + feasibility table |
| No first_frame-as-3view | 6, Global Constraints |
| Same canvas / kernels / no NVFP4 | 4 lock tests |
| Docker image change | 5, 7 |
| Live proof | 8 |

**Placeholder scan:** no TBD / “implement later”.

**Type consistency:** `H3_TASK` is `ref2va|fl2va` at start; `check-weights --task` also allows `all`; downloader defaults to `all`; `--ref-image` uploads to `LoadImage.image` filenames; `ref_images` is `dict[str, [node_id, 0]]`.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task (`cursor-grok-4.6-xhigh-fast`), review between tasks, close-out + push
2. **Inline Execution** — execute tasks in this session using executing-plans, with checkpoints

Which approach?
