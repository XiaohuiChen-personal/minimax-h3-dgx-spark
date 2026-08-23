# MiniMax H3 ComfyUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Fresh implementer per task, then a spec reviewer, then an **adversarial** reviewer that **fixes** issues, then **re-smoke**, then **commit + push**. Do **not** use executing-plans or implement in the parent’s own context.
>
> **Required subagent model:** Grok 4.6, xhigh effort, fast mode. Cursor Task slug: `cursor-grok-4.6-xhigh-fast`. Pass that slug on **every** implementer, spec reviewer, adversarial reviewer, and fixer. Do not inherit the parent model. Do not substitute Claude, GPT, or Composer.

**Goal:** Ship a local, one-job-at-a-time ComfyUI path on this DGX Spark: locked FL2VA workflows, host-side D-02 weights, a reusable `h3-spark:local` image, and a submit/poll script an SSH’d agent can call.

**Architecture:** ComfyUI stays up on port 8188. Weights live in `$HOME/h3-weights` and are mounted read-only. The agent only patches prompt, seed, filename, and optional first/last-frame paths, then `POST /prompt` and polls `/history/<id>`. Generate at 960×544 / 8 steps / 8.00 s (smoke 5.17 s), SPAN 2× to 1080p. Do not invent a different stack.

**Tech Stack:** linux/arm64, GB10 sm_121, CUDA 13, NVIDIA PyTorch NGC image, ComfyUI (SHA newer than `bdcb886a`), Hugging Face `Comfy-Org/MiniMax-H3`, SageAttention 2.2.0, Sol-Attn `triton_ref`, FirstBlockCache `H3 Safe`, bash + Python 3 for helpers, `pytest` for unit tests.

## Global Constraints

- Follow `design/architecture.md`, `design/decisions.md` (D-01…D-14), `design/optimizations.md`, `design/operator.md`, `design/container.md` for product facts. Where this plan is more specific (mount scheme, Hugging Face CLI, lock tests), **this plan wins**.
- Platform: `linux/arm64` only. Never build or pull x86_64 as the product image. Dockerfile uses `FROM --platform=linux/arm64` (there is no `PLATFORM` instruction).
- Never use the Spark system Python for torch. It is CPU-only.
- Never bake `*.safetensors` / `*.pth` into git or into a Docker layer.
- Never enable EasyCache, SageAttention 3, `--use-sage-attention`, Sol-Attn `flex_attention`, Turbo-SLA+Sol-Attn, or `--lowvram`.
- Do not require `H3_LICENSE_ACK` (D-13). Entrypoint starts if the weight files are present.
- One GPU job at a time. Do not start or restart ComfyUI per video.
- **Mount scheme is locked:** bind each host weight *subfolder* under `/opt/ComfyUI/models/<name>` (Task 9). Do **not** copy `design/container.md`’s whole-`models` example — that was a shape sketch, not the chosen scheme.
- Hugging Face CLI on this Spark is **`hf`** (hub 1.4.1). `huggingface-cli` is **not** installed. Use `hf download REPO path/to/file --local-dir DIR`. Never `--local-dir-use-symlinks` (removed). Never `--include "*.safetensors"` on `Comfy-Org/MiniMax-H3` (that is the whole 471 G snapshot, including Ref2VA).
- Official Comfy-Org T2V JSON is a **UI-format template**, not the product: INT8 DiT + NVFP4 TE, 1344×768, 4 steps, `length` 73, node id `124` is a scheduler, no SPAN / Sol-Attn / FBC / `ModelSamplingAV`. Convert to API format and lock D-02. Do not ship the template unchanged.
- Every artifact download must be timed and appended to `measurements/download-log.md` (see Speed-log protocol).
- This box is on an **8 Gbps** ethernet plan (1000 MB/s = 1e9 B/s decimal line-rate ceiling). Record NIC link speed. Do not treat “GiB ≈ seconds” as exact.
- Each task’s last “Commit” step is **commit only**. Do **not** push there. After that commit, the parent runs **Per-task close-out**: spec review → adversarial fix → re-smoke → **`git push -u origin HEAD`**. Never `--force`. Never `--no-verify` unless the operator said so. Never push safetensors, pth, mp4, or wheels.

## Execution model — subagent-driven, Grok 4.6 xhigh fast

This plan is executed by **subagents**, not by the parent chatting the code in.

**Where to run it.** Open a **new Cursor chat** on this repo. Turn on **Multitask mode** so implementers can run in the background while the parent only coordinates. Point that chat at this file. The parent reads the plan, dispatches, reviews results, and marks checkboxes. The parent does not write `scripts/` or `deploy/` itself unless a subagent is blocked.

**Skill.** `superpowers:subagent-driven-development`, plus the close-out below. Do not stop to ask “should I continue?” between tasks unless BLOCKED.

### Per-task close-out (mandatory, in this order)

Do **not** start Task N+1 and do **not** push until this list is done for Task N.

1. **Implementer** (`cursor-grok-4.6-xhigh-fast`) — implements only Task N, runs that task’s tests, commits, self-reviews. No push yet.
2. **Spec reviewer** (`cursor-grok-4.6-xhigh-fast`, read-only) — diff vs this plan’s Task N and the design files. Reports spec ✅/❌ and quality. Does not edit.
3. **Fixer** (if spec reviewer found Critical/Important) — same model, implements only those fixes, re-runs the task tests, commits.
4. **Adversarial reviewer + fixer** (`cursor-grok-4.6-xhigh-fast`) — a **new** subagent. It must try to break the work: wrong facts vs `design/*.md`, off-by-one frames/steps, forbidden flags, tests that pass on empty stubs, missing speed-log rows, CPU-torch traps, baked weights, license gates, Ref2VA drift, racey submit/poll, unsafe `git`/`docker` commands. It **fixes** inaccuracies, errors, bugs, and bad practices it can prove. It does not invent a new stack. Commit fixes separately (`fix: … after adversarial review of Task N`).
5. **Re-smoke** (same adversarial agent, or a tiny follow-up of the same model) — run the suite below. If re-smoke fails, fix and re-smoke again. No push on red tests.
6. **Push** — `git push -u origin HEAD`. If the hook rejects, fix and make a **new** commit; do not `--no-verify` unless the operator said so.

**Re-smoke commands**

Always (once the files exist):

```bash
cd /home/xiaohui_chen/Projects/minimax-h3-dgx-spark
# Do not `|| true` these — that hides real failures. Skip only when the file is absent.
[[ -f tests/unit/test_check_weights.sh ]] && bash tests/unit/test_check_weights.sh
[[ -f tests/unit/test_speedlog.sh ]] && bash tests/unit/test_speedlog.sh
[[ -f tests/unit/test_smoke_audio.sh ]] && bash tests/unit/test_smoke_audio.sh
[[ -f tests/unit/test_entrypoint_flags.sh ]] && bash tests/unit/test_entrypoint_flags.sh
compgen -G 'tests/unit/test_*.py' >/dev/null && python3 -m pytest tests/unit -v
```

After Task 9 (image is up):

```bash
curl -fsS http://127.0.0.1:8188/system_stats
docker compose -f deploy/compose.yaml ps
```

After Task 10 (a live mp4 exists):

```bash
./scripts/smoke-test.sh --offline-mp4 "$HOME/h3-output/smoke-5s17.mp4"
# If adversarial review changed workflows, scripts, entrypoint, or the image:
./scripts/smoke-test.sh --prompt "A quiet kitchen, morning light, a glass of water on the table." --seed 42 --name smoke-5s17-re
```

Do not restart ComfyUI for re-smoke. One GPU job at a time; wait if a generate is running.

**Adversarial prompt (parent must include).**

- You are an adversarial reviewer **and fixer** on Grok 4.6 xhigh fast.
- Scope: Task N diff + the files it touched + the design claims it must obey.
- Hunt: inaccuracies, errors, bugs, missing tests, bad practices, silent fallbacks, speed-log gaps, anything that would make a later agent implement the wrong stack.
- Fix what you find. Re-run the re-smoke commands. Commit. Do not push (parent or close-out Step 6 pushes).
- Return a short list: finding → fix → test evidence.

**Spec reviewers** stay read-only. **Adversarial reviewers** may edit. Both use `cursor-grok-4.6-xhigh-fast`.

**Model (mandatory on every Task call).**

| Human name | Cursor `model` slug |
|---|---|
| Grok 4.6, xhigh effort, fast mode | `cursor-grok-4.6-xhigh-fast` |

Example dispatch (parent must copy the slug):

```text
Task.subagent_type = generalPurpose   # or the implementer type the skill names
Task.model          = cursor-grok-4.6-xhigh-fast
Task.run_in_background = true         # required in Multitask mode
```

If the slug is unavailable, **stop and tell the operator**. Do not silently switch models.

**What to put in each implementer prompt.**

- Repo root: `/home/xiaohui_chen/Projects/minimax-h3-dgx-spark`
- This plan path and the **exact Task N** to do (no other tasks)
- Global Constraints + Speed-log protocol
- Design files: `design/architecture.md`, `design/decisions.md`, `design/optimizations.md`, `design/operator.md`, `design/container.md`
- “Do not invent a different stack. Do not download weights unless you are Task 6. Do not commit `*.safetensors` / `*.pth` / `*.mp4`.”
- “You are Grok 4.6 xhigh fast. Finish the task’s tests before you commit. Do not push; close-out pushes after adversarial review and re-smoke.”

**Order.** Tasks are mostly a chain. Do not start Task N+1 until Task N’s close-out has finished, except this safe overlap in Multitask mode:

| After | May start in parallel | Must wait |
|---|---|---|
| Task 1 close-out | Tasks 2, 3, and 4 together | Task 5+ (Task 5 edits Task 2’s manifest) |
| Task 2 close-out | — | Task 5 (needs `required-weights.txt`) |
| Tasks 2 + 3 + 5 close-out | — | Task 6 (real download) |
| Task 5 close-out | — | Task 7 (needs the real SPAN filename + `COMFYUI_SHA`) |
| Task 4 close-out | **Task 8 offline only** | Task 8 live path needs Task 7’s workflow JSON; Task 8 must **not** `test -f` that JSON unless `--offline-mp4` is absent |
| Tasks 1 + 2 + 3 + 4 + 5 + 7 + 8 close-out | Task 9 **image build** + **negative** start (empty weights) | Task 9 must not `COPY` workflows/scripts before those tasks exist |
| Task 6 + Task 9 build close-out | — | Task 9 **positive** `compose up` (entrypoint checks real weights) |
| Task 6 + 7 + 8 + 9 positive close-out | — | Task 10 live smoke |
| Task 10 smoke close-out | — | Task 11 default 8.00 s |

Do **not** start Task 9 build beside Task 7 or Task 8 — the image `COPY`s those files. Do **not** start Task 6 beside Task 5 (SPAN line still `SPAN2X`).

Each of those “close-out” cells means **all six steps** finished: implementer commit, spec review, adversarial fix, re-smoke, and **push**.

## Speed-log protocol (every download)

Before the first artifact pull, create `measurements/download-log.md` with this table header and keep appending one row per file or image layer set:

```markdown
# Download speed log — DGX Spark ethernet

Plan: 8 Gbps (1000 MB/s line-rate ceiling).
NIC (from Task 1): <fill link speed, driver, iface>
Method: wall-clock around the transfer; bytes from the finished file or `docker image inspect`.

| When (UTC) | Artifact | Source | Bytes | Seconds | MiB/s | % of 1000 MB/s | Notes |
|---|---|---|---:|---:|---:|---:|---|
```

Compute MiB/s as `bytes / seconds / 1048576`. Compute `% of 1000 MB/s` as `(bytes / seconds / 1e6) / 1000 * 100` (decimal MB, not MiB). These two columns use different byte bases on purpose.

If `seconds < 0.01` (cache-hit), **do not divide by zero**. Write `MiB/s` as `n/a`, `%` as `n/a`, Notes `cache-hit`, and still record `Bytes`.

Time transfers with:

```bash
# file download
start=$(date +%s.%N)
# ... the download command ...
end=$(date +%s.%N)
bytes=$(stat -c%s "$dest")
python3 - "$start" "$end" "$bytes" <<'PY'
import sys
start, end, bytes_ = map(float, sys.argv[1:])
secs = end - start
if secs < 0.01:
    print(f"bytes={int(bytes_)} seconds={secs:.4f} MiB/s=n/a pct_line=n/a")
else:
    mib = bytes_ / secs / 1048576
    pct = (bytes_ / secs / 1e6) / 1000 * 100
    print(f"bytes={int(bytes_)} seconds={secs:.2f} MiB/s={mib:.1f} pct_line={pct:.1f}")
PY
```

Do this for Hugging Face weights, the SPAN file, the NGC base image, the ComfyUI clone (git objects), SageAttention 2.2.0, and any custom-node clones. Do **not** skip “it was cached” — if Docker or HF cache hits, write `cache-hit` in Notes and still record bytes + ~0 s.

## File map

| Path | Responsibility |
|---|---|
| `measurements/download-log.md` | Real-world ethernet download speeds |
| `measurements/prereq.md` | Box identity: aarch64, GB10, Docker GPU, NIC link |
| `scripts/required-weights.txt` | Relative paths the checker and downloader share |
| `scripts/check-weights.sh` | Exit 1 + missing names if the host tree is incomplete |
| `scripts/download-weights.sh` | Fetch D-02 + SPAN into `$H3_WEIGHTS`; append speed rows |
| `scripts/lib/speedlog.sh` | Append one speed-log row |
| `scripts/submit-prompt.py` | Patch free fields, POST /prompt, poll /history, print output path |
| `scripts/submit-prompt.sh` | Thin wrapper so agents can call a `.sh` as designed |
| `scripts/smoke-test.sh` | Submit 5.17 s graph; fail if mp4 has no stereo audio |
| `scripts/entrypoint.sh` | Container start: check weights, launch ComfyUI |
| `tests/unit/test_check_weights.sh` | Fixture trees, no GPU |
| `tests/unit/test_submit_prompt.py` | Mock HTTP ComfyUI, no GPU |
| `tests/unit/test_workflow_lock.py` | Locked knobs present in both JSON graphs |
| `tests/unit/test_speedlog.sh` | Speed-log row format |
| `workflows/h3-fl2va-smoke-5s17.json` | 960×544, 124 frames, 8 steps |
| `workflows/h3-fl2va-default-8s.json` | 960×544, 192 frames, 8 steps |
| `deploy/Dockerfile` | ARM64 image, no weights |
| `deploy/compose.yaml` | Port 8188, three mounts, one GPU |
| `deploy/README.md` | Pins recorded at implement time + start commands |

---

### Task 1: Prerequisite validation (this Spark)

**Files:**
- Create: `measurements/prereq.md`
- Create: `measurements/download-log.md` (header only)

**Interfaces:**
- Consumes: none
- Produces: a written gate. Later tasks must not start if `uname -m` is not `aarch64` or `nvidia-smi` does not show GB10 / compute 12.1

**Deliverable:** `measurements/prereq.md` with command output pasted, all checks PASS.

- [ ] **Step 1: Collect identity**

Run and paste into `measurements/prereq.md`:

```bash
date -u
uname -a
uname -m
nvidia-smi
python3 -c "import torch; print('sys-python-torch', getattr(torch, '__version__', None), 'cuda', torch.cuda.is_available())" || echo "sys-python-no-torch"
docker version --format '{{.Server.Version}}'
docker info --format 'Runtimes={{.Runtimes}} DefaultRuntime={{.DefaultRuntime}}'
ip -br link
ethtool "$(ip -br route show default | awk '{print $5; exit}')" 2>/dev/null | egrep 'Speed|Duplex|Link detected' || true
```

Expected:
- `uname -m` = `aarch64`
- `nvidia-smi` shows driver **580.x**, CUDA **13**, a GB10
- System python torch is **CPU or missing** (this is the known trap — PASS if CPU)
- Docker talks to a GPU runtime
- NIC Speed is **8000Mb/s** or **10000Mb/s** if the drop is 10 GbE; record the actual number

- [ ] **Step 2: GPU-in-container smoke (no H3)**

```bash
docker run --rm --gpus all --platform linux/arm64 \
  nvcr.io/nvidia/pytorch:25.12-py3 \
  python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If `25.12-py3` does not exist or is x86-only, list tags and pick the newest **linux/arm64 / CUDA 13** PyTorch tag. Record the chosen tag as `BASE_IMAGE` in `measurements/prereq.md`.

Time the pull (even if you have to `docker rmi` first to measure a cold pull). Append a speed-log row for `nvcr.io/nvidia/pytorch:<tag>`.

Expected: `True` and a GB10-like name. If `False`, stop — do not implement ComfyUI on CPU torch.

- [ ] **Step 3: Disk headroom**

```bash
df -h "$HOME" /var/lib/docker
```

Need about **60 GiB** free for weights + **30 GiB** for images. If not, stop and say so.

- [ ] **Step 4: Commit only (no push)**

```bash
git add measurements/prereq.md measurements/download-log.md
git commit -m "$(cat <<'EOF'
Record Spark prerequisite checks and the download-log header.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 2: Weight manifest + `check-weights.sh` (unit tested, no download)

**Files:**
- Create: `scripts/required-weights.txt`
- Create: `scripts/check-weights.sh`
- Create: `tests/unit/test_check_weights.sh`
- Create: `tests/fixtures/weights-complete/` (empty placeholder files with the required names)
- Create: `tests/fixtures/weights-missing-dit/` (same minus the DiT file)

**Interfaces:**
- Consumes: directory path
- Produces: `check-weights.sh <dir>` exit 0 if every line in `required-weights.txt` exists as a file under `<dir>`; else exit 1 and print `MISSING <relpath>` one per line

`scripts/required-weights.txt` contents (exact):

```text
diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors
text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
vae/minimax_h3_video_vae_fp16.safetensors
vae/minimax_h3_audio_vae_fp32.safetensors
loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
upscale_models/SPAN2X
```

`SPAN2X` is a sentinel. Task 5 replaces that line with the real SPAN filename after resolution. Until then the checker treats a file literally named `SPAN2X` as satisfying the fixture; the downloader must not leave that sentinel on the host.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_check_weights.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK="$ROOT/scripts/check-weights.sh"

# missing script → fail the test runner if not implemented
test -x "$CHECK"

# complete fixture
"$CHECK" "$ROOT/tests/fixtures/weights-complete"

# missing DiT — do NOT pipe the checker into grep under `set -o pipefail`.
# The checker exits 1 on purpose; a pipeline would fail the test even when correct.
if out="$("$CHECK" "$ROOT/tests/fixtures/weights-missing-dit")"; then
  echo "expected failure on missing DiT"; exit 1
fi
printf '%s\n' "$out" | grep -q 'MISSING diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors'
echo OK
```

- [ ] **Step 2: Run test to verify it fails**

```bash
chmod +x tests/unit/test_check_weights.sh
bash tests/unit/test_check_weights.sh
```

Expected: FAIL (`test -x` or missing script).

- [ ] **Step 3: Write `scripts/check-weights.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="${1:?usage: check-weights.sh <weights-dir>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
LIST="$ROOT/required-weights.txt"
missing=0
while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -z "$rel" || "$rel" == \#* ]] && continue
  if [[ ! -f "$DIR/$rel" ]]; then
    echo "MISSING $rel"
    missing=1
  fi
done < "$LIST"
exit "$missing"
```

Create the two fixture trees with `mkdir -p` and `touch` of the six paths (complete has all six; missing-dit omits the DiT file).

- [ ] **Step 4: Run test to verify it passes**

```bash
bash tests/unit/test_check_weights.sh
```

Expected: `OK`

- [ ] **Step 5: Commit only (no push)**

```bash
git add scripts/required-weights.txt scripts/check-weights.sh tests/unit/test_check_weights.sh tests/fixtures
git commit -m "$(cat <<'EOF'
Add a shared weight manifest and a unit-tested checker.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 3: Speed-log helper (unit tested)

**Files:**
- Create: `scripts/lib/speedlog.sh`
- Create: `tests/unit/test_speedlog.sh`

**Interfaces:**
- CLI: `scripts/lib/speedlog.sh append <log> <artifact> <source> <bytes> <seconds> <notes>`
- Internally that may call a function `speedlog_append` — the **test invokes the script**, not a sourced-only function. The file must be executable.
- Produces: one markdown table row appended to `<log>` and printed to stdout
- Math: same as Speed-log protocol. 104857600 bytes in 1.0 s → `MiB/s=100.0` and `% of 1000 MB/s=10.5` (not 100). Cache-hit `seconds=0` → `n/a`, no crash.

- [ ] **Step 1: Write the failing test**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp)
echo '| When (UTC) | Artifact | Source | Bytes | Seconds | MiB/s | % of 1000 MB/s | Notes |' > "$tmp"
echo '|---|---|---|---:|---:|---:|---:|---|' >> "$tmp"
"$ROOT/scripts/lib/speedlog.sh" append "$tmp" "probe.bin" "https://example.test" 104857600 1.0 "unit"
grep -q 'probe.bin' "$tmp"
grep -q '| 100.0 |' "$tmp"   # 100 MiB in 1 s = 100.0 MiB/s
grep -q '| 10.5 |' "$tmp"    # 104.8576 MB/s ÷ 1000 MB/s = 10.5%, not 100
"$ROOT/scripts/lib/speedlog.sh" append "$tmp" "cached.bin" "https://example.test" 104857600 0 "cache-hit"
grep -q 'n/a' "$tmp"
echo OK
```

- [ ] **Step 2: Run to verify fail** (script missing)

- [ ] **Step 3: Implement `scripts/lib/speedlog.sh`**

Must compute MiB/s and `% of 1000 MB/s` as in the Speed-log protocol. Print the row to stdout as well as the file.

- [ ] **Step 4: Run test — expect `OK`**

- [ ] **Step 5: Commit only (no push)**

```bash
git add scripts/lib/speedlog.sh tests/unit/test_speedlog.sh
git commit -m "$(cat <<'EOF'
Add a download speed-log helper compared to the 8 Gbps ceiling.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 4: `submit-prompt.py` against a mock ComfyUI (unit tested, no GPU)

**Files:**
- Create: `scripts/submit-prompt.py`
- Create: `scripts/submit-prompt.sh`
- Create: `tests/unit/test_submit_prompt.py`
- Create: `tests/fixtures/tiny-workflow.json`

**Interfaces:**
- Consumes: workflow JSON path; `--prompt`; `--seed`; `--name`; optional `--first-frame`; optional `--last-frame`; `--base-url` default `http://127.0.0.1:8188`; `--output-root` default `$H3_OUTPUT` or `$HOME/h3-output`
- Produces: exit 0 and one line `OUTPUT <abs-host-path-to-mp4>` after `/history/<prompt_id>` reports success
- Must **not** start Docker or ComfyUI
- Must only change free fields: prompt text, seed, filename, optional image paths. Leave canvas, frames, steps, checkpoint names untouched
- Keyframe paths: if the caller passes a host path under `$H3_DATA` / `$HOME/h3-data`, rewrite it to the container path `/data/<rel>` in the posted graph. Print the **host** output path (`$H3_OUTPUT/<name>.mp4`), not `/opt/ComfyUI/output/...`
- `POST /prompt` body is `{"prompt": <api-format-graph>, ...}` — not the UI `nodes`/`links` document
- `/history` parser must walk real ComfyUI outputs (`images` / `gifs` / `videos` lists of `{filename, subfolder, type}`). Do **not** teach a parser that only reads `outputs["9"]["filename"]` as a string list — that shape is not what ComfyUI returns, and Task 10 would then fail

`tests/fixtures/tiny-workflow.json` is a minimal **API-format** graph (`{"<id>": {"class_type": "...", "inputs": {...}}}`) with prompt / seed / `filename_prefix` / `width`. Document the patched input names at the top of `submit-prompt.py`.

- [ ] **Step 1: Write the failing pytest**

`tests/unit/test_submit_prompt.py` must:

1. Start `http.server` or a `threading` HTTP handler that:
   - `POST /prompt` → `200 {"prompt_id":"abc","number":1,"node_errors":{}}`
   - `GET /history/abc` → first call empty `{}`, second call a **realistic** payload:

```json
{"abc":{"status":{"status_str":"success","completed":true},"outputs":{"9":{"videos":[{"filename":"tiny.mp4","subfolder":"","type":"output"}]}}}}
```

2. Copy `tiny-workflow.json` to a temp file
3. Run `python3 scripts/submit-prompt.py <tmp.json> --prompt hello --seed 7 --name unit --base-url http://127.0.0.1:<port> --output-root <tmp>`
4. Assert exit 0, stdout contains `OUTPUT` and ends with `tiny.mp4` under `--output-root`, and the posted JSON body has prompt `hello` and seed `7` but still has the fixture’s locked `960` width

Also add `test_does_not_change_locked_canvas` that puts `"width": 960` in the fixture and asserts it is still 960 after submit.

- [ ] **Step 2: Run**

```bash
python3 -m pytest tests/unit/test_submit_prompt.py -v
```

Expected: FAIL (import / file missing).

- [ ] **Step 3: Implement `scripts/submit-prompt.py` and the `.sh` wrapper**

Wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/submit-prompt.py" "$@"
```

Poll every 2 s, timeout 3600 s. On `/history` error, print the body and exit 1.

- [ ] **Step 4: Pytest PASS**

- [ ] **Step 5: Commit only (no push)**

```bash
git add scripts/submit-prompt.py scripts/submit-prompt.sh tests/unit/test_submit_prompt.py tests/fixtures/tiny-workflow.json
git commit -m "$(cat <<'EOF'
Add a unit-tested ComfyUI submit/poll helper that only patches free fields.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 5: Resolve SPAN filename + pin ComfyUI SHA (no full clone of weights)

**Files:**
- Modify: `scripts/required-weights.txt` (replace `SPAN2X` with the real relative path)
- Modify: `measurements/prereq.md` (add `COMFYUI_SHA` and `SPAN_FILE`)
- Modify: fixture trees so unit tests still pass

**Interfaces:**
- Produces: exact SPAN filename and a ComfyUI commit SHA newer than `bdcb886a` that contains `ModelSamplingAV` and `MiniMaxH3ImageToVideo`

- [ ] **Step 1: Resolve SPAN 2×**

Prefer a **2×** SPAN checkpoint that `spandrel` / `ImageUpscaleWithModel` can load. Search OpenModelDB / Hugging Face for `SPAN` 2x, `linux` not required (it’s a small `.pth`). If only 4× SPAN exists, choose the smallest 4× SPAN and note in `measurements/prereq.md` that the workflow must downscale 1920×1088 after a 4× pass — **prefer 2× so the graph is a single 2.00×**.

Write the chosen `upscale_models/<filename>` into `scripts/required-weights.txt`. Update fixtures.

- [ ] **Step 2: Pin ComfyUI**

```bash
git ls-remote https://github.com/comfyanonymous/ComfyUI.git HEAD
```

Do **not** `git clone --depth 1` and then `merge-base --is-ancestor bdcb886a` — a shallow clone does not contain `bdcb886a`, so that check fails even when HEAD is newer.

Clone with history (blobs can stay lazy) and time it (speed-log row `ComfyUI.git`):

```bash
git clone --filter=blob:none --single-branch https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui-pin
git -C /tmp/comfyui-pin merge-base --is-ancestor bdcb886a HEAD && echo ancestor-ok
rg -n "class MiniMaxH3ImageToVideo|class ModelSamplingAV" /tmp/comfyui-pin | head
```

If `--filter=blob:none` is too heavy, skip the ancestry check and instead: record `COMFYUI_SHA`, assert it is **not** `bdcb886a`, and assert those two class names exist in the tree. Do not float on `master` in the Dockerfile.

Record `COMFYUI_SHA=$(git -C /tmp/comfyui-pin rev-parse HEAD)` in `measurements/prereq.md`. If H3 nodes are not in that SHA, walk tags/releases until they are.

- [ ] **Step 3: Re-run `bash tests/unit/test_check_weights.sh` — PASS**

- [ ] **Step 4: Commit only** (manifest + prereq pins only, no clone, no push)

```bash
git add scripts/required-weights.txt measurements/prereq.md tests/fixtures
git commit -m "$(cat <<'EOF'
Pin ComfyUI SHA and the SPAN checkpoint name for the first image.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 6: Download D-02 weights + SPAN (record real ethernet speed)

**Files:**
- Create: `scripts/download-weights.sh`
- Modify: `measurements/download-log.md` (one row per file)
- Host dest: `$HOME/h3-weights` (not git)

**Interfaces:**
- Consumes: `download-weights.sh <dir>`
- Produces: files listed in `required-weights.txt`; appends speed rows; then runs `check-weights.sh`

Do **not** pass `--quiet`. Do not embed tokens. On this Spark the command is `hf` (not `huggingface-cli`). `--local-dir-use-symlinks` is **removed** and must not appear.

Expected sizes (briefing GiB are binary; `hf download --dry-run` shows decimal G):

| Repo path | Briefing GiB | HF dry-run (decimal G) |
|---|---:|---:|
| `diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors` | 19.52 | 21.0G |
| `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 25.28 | 27.1G |
| `vae/minimax_h3_video_vae_fp16.safetensors` | 4.85 | 5.2G |
| `vae/minimax_h3_audio_vae_fp32.safetensors` | 0.56 | 605.3M |
| `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.82 | 2.0G |
| SPAN (Task 5 repo/file) | a few MiB | measure |

Sum ≈ **52.03 GiB ≈ 55.9×10⁹ bytes**. At a perfect 8 Gbps (1000 MB/s = 1e9 B/s) that is **~56 s**, not ~52 s. Hugging Face will be slower. **Write `stat` bytes.** If a dest file is already present and the size is within 1% of the dry-run size, skip and log `cache-hit` (seconds `n/a`).

Never download the other DiTs (Ref2VA, unpruned, INT8 DiT) or the NVFP4 text encoder.

- [ ] **Step 1: Write `download-weights.sh`**

Use **positional repo paths** (basename `--include` does not match `diffusion_models/...`):

```bash
command -v hf >/dev/null || { echo "hf not installed; install huggingface_hub CLI"; exit 1; }

hf download Comfy-Org/MiniMax-H3 \
  diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors \
  --local-dir "$DIR"
```

Repeat for the other four D-02 paths. `hf download --local-dir` already recreates the repo folders under `$DIR`. Time each file separately, then `speedlog.sh append`. SPAN: `hf download <repo> <file> --local-dir "$DIR/upscale_models"` (or the path Task 5 recorded).

End with `"$SCRIPT_DIR/check-weights.sh" "$DIR"` (do not assume an undefined `$ROOT`).

- [ ] **Step 2: Dry-run unit check (no network)**

Add `tests/unit/test_download_weights_help.sh` that runs `download-weights.sh` with no args and expects a usage line and exit ≠ 0.

- [ ] **Step 3: Real download on this Spark**

```bash
mkdir -p "$HOME/h3-weights" "$HOME/h3-output" "$HOME/h3-data"
./scripts/download-weights.sh "$HOME/h3-weights"
./scripts/check-weights.sh "$HOME/h3-weights"
```

Fill `measurements/download-log.md`. Add a short “how this compares to 8 Gbps” paragraph under the table (best file MiB/s, worst, total bytes, total seconds, % of line rate).

- [ ] **Step 4: Commit only the log + script** (never the weights, no push)

```bash
git add scripts/download-weights.sh measurements/download-log.md tests/unit/test_download_weights_help.sh
git commit -m "$(cat <<'EOF'
Download host weights with per-file ethernet speed measurements.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step. Never `git add` `*.safetensors` / `*.pth`.

---

### Task 7: Locked workflow JSON + lock tests

**Files:**
- Create: `workflows/h3-fl2va-smoke-5s17.json`
- Create: `workflows/h3-fl2va-default-8s.json`
- Create: `tests/unit/test_workflow_lock.py`

**Interfaces:**
- Consumes: Comfy-Org T2V template `https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json`
- Produces: two API-format graphs (the JSON `POST /prompt` expects — ComfyUI “API format”, not the UI-only format if they differ)

Locked values both graphs must contain as **API-format** node inputs (not a UI `nodes`/`links` document):

- width `960`, height `544` on `MiniMaxH3ImageToVideo` (or the SHA’s current name) as **integer literals** in `inputs` — drop `ResolutionSelector`
- `length` **124** (smoke) or **192** (default) as an **integer literal** — 17n+5 at 24 fps. Drop the template’s duration-math node (`length` 73). Linked `[node_id, 0]` values will fail the lock test on purpose
- checkpoints: the five D-02 MiniMax names + the SPAN filename from Task 5 (`scripts/required-weights.txt`)
- LoRA `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16` from **Comfy-Org**, not the template’s `lightx2v` URL
- Sampler **Euler + simple**, **8** steps. Request **9** sigma points when the scheduler exposes them (grid includes the final zero). The stock template is `res_multistep` + **4** steps — replace it
- `ModelSamplingAV` shifts **6** and **3** (add this node; it is not in the stock T2V template)
- Sol-Attn kernel name `triton_ref` (add if missing)
- FirstBlockCache preset containing `H3 Safe` (add if missing)
- SPAN 2× to 1920×1088, then crop to 1920×1080 (add; stock template has no upscale)
- no `EasyCache`, `flex_attention`, `lowvram`, `<Picture `, `ref2va`, `MiniMaxH3ReferenceToVideo`, `nvfp4`, `minimax_h3_fl2va_pruned_int8_convrot`

- [ ] **Step 1: Write `tests/unit/test_workflow_lock.py` first**

Parse JSON. **Do not** use `assert "192" not in raw` — the upscale width `1920` contains `192`, and the stock UI template has **node id 124** (`BasicScheduler`) so `assert "124" in raw` can pass without smoke frames. **Do not** use `assert "192" in raw` on the default graph either (`1920` would satisfy it with the wrong frame count).

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((ROOT / "workflows" / name).read_text())


def prompt_graph(doc: dict) -> dict:
    if "prompt" in doc and isinstance(doc["prompt"], dict):
        doc = doc["prompt"]
    nodes = [v for v in doc.values() if isinstance(v, dict)]
    assert nodes and all("class_type" in n for n in nodes), (
        "workflow must be ComfyUI API format for POST /prompt, not UI nodes/links"
    )
    return doc


def int_inputs(graph: dict, key: str) -> list[int]:
    out = []
    for node in prompt_graph(graph).values():
        if not isinstance(node, dict):
            continue
        val = (node.get("inputs") or {}).get(key)
        if isinstance(val, int):
            out.append(val)
    return out


def test_smoke_frames_and_canvas():
    g = load("h3-fl2va-smoke-5s17.json")
    assert 960 in int_inputs(g, "width")
    assert 544 in int_inputs(g, "height")
    assert 124 in int_inputs(g, "length")
    assert 192 not in int_inputs(g, "length")
    raw = json.dumps(g)
    assert "1920" in raw and "1088" in raw


def test_default_frames():
    g = load("h3-fl2va-default-8s.json")
    assert 192 in int_inputs(g, "length")
    assert 124 not in int_inputs(g, "length")
    assert 960 in int_inputs(g, "width")
    assert 8 in int_inputs(g, "steps")


def test_forbidden_and_required_strings():
    span = next(
        line.strip()
        for line in (ROOT / "scripts" / "required-weights.txt").read_text().splitlines()
        if line.startswith("upscale_models/")
    )
    span_name = Path(span).name
    for name in ("h3-fl2va-smoke-5s17.json", "h3-fl2va-default-8s.json"):
        raw = (ROOT / "workflows" / name).read_text()
        g = load(name)
        assert 8 in int_inputs(g, "steps")
        for bad in (
            "EasyCache",
            "flex_attention",
            "lowvram",
            "<Picture ",
            "ref2va",
            "MiniMaxH3ReferenceToVideo",
            "nvfp4",
            "minimax_h3_fl2va_pruned_int8_convrot",
        ):
            assert bad not in raw, bad
        assert "triton_ref" in raw
        assert "H3 Safe" in raw or "H3Safe" in raw or "h3_safe" in raw
        assert "ModelSamplingAV" in raw
        assert "minimax_h3_fl2va_pruned_fp8_scaled" in raw
        assert "qwen3vl_32b_minimax_h3_int8_convrot" in raw
        assert span_name in raw
```

- [ ] **Step 2: Run pytest — FAIL** (files missing)

- [ ] **Step 3: Fetch the official T2V template (speed-log the raw GitHub file), then rebuild**

```bash
curl -fsSL -o /tmp/video_minimax_h3_t2v.json \
  https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_minimax_h3_t2v.json
```

That file is **UI format** plus a subgraph. It is **not** POST-able. Convert to API format (`ComfyUI/script_examples` or UI “Save (API format)”). Then **replace** the template’s product choices — do not “change only a few knobs and ship”:

- INT8 DiT + NVFP4 TE → D-02 FP8 DiT + INT8 TE
- 1344×768 / `length` 73 / 4 steps / `res_multistep` → 960×544 / 124 or 192 / 8 steps / Euler+simple
- Drop `ResolutionSelector` and the duration `ComfyMathExpression`; write literal `width` / `height` / `length` / `steps`
- Add `ModelSamplingAV` 6/3, SPAN 2×, Sol-Attn `triton_ref`, FirstBlockCache `H3 Safe`
- Do not add Ref2VA or `<Picture N>`

If a node name in current ComfyUI differs (`MiniMaxH3ImageToVideo`), use the name that exists at `COMFYUI_SHA`.

- [ ] **Step 4: Pytest PASS**

- [ ] **Step 5: Commit only (no push)**

```bash
git add workflows/h3-fl2va-smoke-5s17.json workflows/h3-fl2va-default-8s.json tests/unit/test_workflow_lock.py
git commit -m "$(cat <<'EOF'
Add locked 5.17 s and 8.00 s FL2VA workflows with lock tests.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 8: `smoke-test.sh` (unit test the audio check; live H3 later)

**Files:**
- Create: `scripts/smoke-test.sh`
- Create: `tests/unit/test_smoke_audio.sh`
- Create: `tests/fixtures/silent-video-only.mp4` **or** generate it in the test with `ffmpeg`
- Create: `tests/fixtures/stereo-tone.mp4` generated in the test

**Interfaces:**
- Consumes: running ComfyUI optional; `--offline-mp4 <path>` for unit tests
- Produces: exit 0 only if the file has a video stream **and** an audio stream with 2 channels (or 1 is fail). Live mode calls `submit-prompt.sh` on `workflows/h3-fl2va-smoke-5s17.json`
- **Offline must not require Task 7/9 files.** If `--offline-mp4` is set, do not `test -f` the workflow JSON, do not call `submit-prompt.sh`, and do not start Docker. Task 8 may run in parallel with Task 7.

Audio probe:

```bash
ffprobe -v error -select_streams a:0 -show_entries stream=codec_type,channels \
  -of csv=p=0 "$mp4"
```

Expected live later: `audio,2`. Unit: stereo fixture PASS, video-only FAIL.

- [ ] **Step 1: Failing test** that calls `smoke-test.sh --offline-mp4`

- [ ] **Step 2: Implement `smoke-test.sh`**

- [ ] **Step 3: Unit PASS** (no ComfyUI)

- [ ] **Step 4: Commit only (no push)**

```bash
git add scripts/smoke-test.sh tests/unit/test_smoke_audio.sh tests/fixtures
git commit -m "$(cat <<'EOF'
Add a smoke-test script that fails mp4s without stereo audio.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 9: Docker image + compose (no weights in the layer)

**Files:**
- Create: `deploy/Dockerfile`
- Create: `deploy/compose.yaml`
- Create: `scripts/entrypoint.sh`
- Modify: `deploy/README.md` with `BASE_IMAGE` and `COMFYUI_SHA` from Task 1/5

**Interfaces:**
- Consumes: pins from `measurements/prereq.md`
- Produces: image `h3-spark:local` that listens on 8188 when weights are mounted

Dockerfile rules:

- `FROM --platform=linux/arm64 ${BASE_IMAGE}` (the tag from Task 1). There is no Dockerfile `PLATFORM` instruction.
- Also set `platform: linux/arm64` on the compose service.
- Clone ComfyUI at `COMFYUI_SHA`
- Install SageAttention **2.2.0** (not 3). Time the pip/wheel; speed-log.
- Install Sol-Attn node pack that exposes `triton_ref`, plus H3 FirstBlockCache. Time git clones; speed-log.
- `COPY` workflows + scripts (this is why Task 9 build waits for Tasks 7 and 8)
- `ENTRYPOINT ["/opt/h3/scripts/entrypoint.sh"]` — run `check-weights.sh /opt/ComfyUI/models` (subfolder mounts still land files under that tree), then:

```bash
python main.py --listen 0.0.0.0 --port 8188 \
  --fast fp8_matrix_mult --disable-pinned-memory
```

Forbidden flags must not appear in the entrypoint.

- `LABEL comfyui.git_sha=... base.image=... h3.decision_set=D-01..D-14`

Mount scheme (**locked** — subfolder binds so ComfyUI’s stock extras survive):

```yaml
# Nested ${H3_WEIGHTS:-${HOME}/h3-weights} needs Compose v2 and HOME in the environment.
# If a mount is empty, write deploy/.env with absolute H3_WEIGHTS / H3_OUTPUT / H3_DATA.
services:
  comfyui:
    image: h3-spark:local
    platform: linux/arm64
    build: .
    gpus: all
    ports:
      - "8188:8188"
    volumes:
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/diffusion_models:/opt/ComfyUI/models/diffusion_models:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/text_encoders:/opt/ComfyUI/models/text_encoders:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/vae:/opt/ComfyUI/models/vae:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/loras:/opt/ComfyUI/models/loras:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/upscale_models:/opt/ComfyUI/models/upscale_models:ro
      - ${H3_OUTPUT:-${HOME}/h3-output}:/opt/ComfyUI/output
      - ${H3_DATA:-${HOME}/h3-data}:/data:ro
    restart: unless-stopped
```

- [ ] **Step 1: Unit-test the entrypoint without Docker**

`tests/unit/test_entrypoint_flags.sh`: require the file to exist, then:

```bash
grep -q -- '--fast fp8_matrix_mult' "$ENTRY"
grep -q -- '--disable-pinned-memory' "$ENTRY"
# grep -v is NOT a "must not contain" check — it exits 0 if any line lacks the pattern.
if grep -E -- 'lowvram|novram|use-sage-attention|H3_LICENSE_ACK' "$ENTRY"; then
  echo "forbidden flag or license gate in entrypoint"; exit 1
fi
```

Missing file → fail.

- [ ] **Step 2: Write entrypoint + Dockerfile + compose**

- [ ] **Step 3: Build and time it**

```bash
docker compose -f deploy/compose.yaml build
docker image inspect h3-spark:local --format '{{.Size}}'
```

Append a speed-log row for “image build context + base already pulled”. If `Size` is ≥ 40 GiB, weights were baked — **fail the task and fix**.

- [ ] **Step 4: Negative start (empty models)**

Do **not** pass `true` (that replaces CMD; an `exec "$@"` entrypoint then skips ComfyUI and may skip the check). Do **not** override only `diffusion_models` while other compose mounts still point at real `~/h3-weights`.

```bash
mkdir -p /tmp/empty-h3-weights/{diffusion_models,text_encoders,vae,loras,upscale_models}
H3_WEIGHTS=/tmp/empty-h3-weights docker compose -f deploy/compose.yaml run --rm --no-deps comfyui
```

Expect printed `MISSING ...` lines and a **non-zero** exit. That invokes the image `ENTRYPOINT`. Do not leave a crashed `up` service.

- [ ] **Step 5: Positive start** (only after Task 6 weights exist)

```bash
docker compose -f deploy/compose.yaml up -d
for i in $(seq 1 60); do curl -fsS http://127.0.0.1:8188/system_stats && break; sleep 5; done
curl -fsS http://127.0.0.1:8188/system_stats
```

Expected: HTTP 200. Leave it up for Task 10. Do not `compose down`.

- [ ] **Step 6: Commit only (no push)**

```bash
git add deploy/Dockerfile deploy/compose.yaml deploy/README.md scripts/entrypoint.sh tests/unit/test_entrypoint_flags.sh
git commit -m "$(cat <<'EOF'
Add the Spark ComfyUI image and compose mounts without baking weights.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 10: Live smoke test (5.17 s) + queue check

**Files:**
- Modify: `measurements/prereq.md` (add smoke wall-clock, audio probe)
- Host output: `$HOME/h3-output/smoke-5s17.mp4` (gitignored)

**Interfaces:**
- Consumes: running `h3-spark:local`, complete `$HOME/h3-weights`
- Produces: one mp4 with video + stereo audio; documented seconds

- [ ] **Step 1: Submit smoke (ComfyUI already up)**

```bash
./scripts/smoke-test.sh \
  --prompt "A quiet kitchen, morning light, a glass of water on the table." \
  --seed 42 \
  --name smoke-5s17
```

Record wall-clock. Probe:

```bash
ffprobe -hide_banner "$HOME/h3-output/smoke-5s17.mp4"
```

PASS only if there is a video stream and `channels=2` audio. FAIL (and do not start the 8 s default as “green”) if audio is missing, mono, silent-NaN, or the process crashed.

- [ ] **Step 2: Queue behavior**

While a dummy long poll is not available, submit smoke again immediately in the background and a second `POST /prompt` with `--name smoke-queue`. Assert both finish, `docker compose ps` still shows **one** container, and logs do not show a second `main.py`.

- [ ] **Step 3: Forbidden-flag audit on the live process**

```bash
docker compose -f deploy/compose.yaml exec comfyui ps aux | tee /tmp/h3-ps.txt
# Fail if a forbidden flag is present. `grep -v` would pass as long as any other line exists.
if grep -E -- 'lowvram|novram|use-sage-attention' /tmp/h3-ps.txt; then
  echo "forbidden flag in live process"; exit 1
fi
```

- [ ] **Step 4: Optional same-seed FP8 check (D-02 reverse line)**

If smoke PASSed and time allows: one run with `--fast fp8_matrix_mult` already on (baseline). Document step time from ComfyUI logs. A second run without the flag is a **manual** follow-up, not required to merge the image. Record whether you did it.

- [ ] **Step 5: Commit measurements only (no push)**

```bash
git add measurements/prereq.md measurements/download-log.md
git commit -m "$(cat <<'EOF'
Record the first 5.17 s smoke-test result and remaining download rows.

EOF
)"
```

Do **not** commit the mp4. Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step.

---

### Task 11: Default 8.00 s path + docs pins

**Files:**
- Modify: `deploy/README.md` (exact start commands, pins, speed-log pointer)
- Modify: `design/container.md` only if the mount scheme or SPAN filename must be recorded (keep design truthful)
- Modify: `design/README.md` to point at this plan as executed / remaining

- [ ] **Step 1: Run default workflow once** (only if Task 10 smoke PASSed)

```bash
./scripts/submit-prompt.sh workflows/h3-fl2va-default-8s.json \
  --prompt "A quiet kitchen, morning light, a glass of water on the table." \
  --seed 42 \
  --name default-8s
```

Same audio/video probe. Record wall-clock in `measurements/prereq.md`.

- [ ] **Step 2: Write `deploy/README.md`** with `BASE_IMAGE`, `COMFYUI_SHA`, SPAN filename, `docker compose up -d`, no license env.

- [ ] **Step 3: Re-run unit tests**

```bash
bash tests/unit/test_check_weights.sh
bash tests/unit/test_speedlog.sh
bash tests/unit/test_smoke_audio.sh
python3 -m pytest tests/unit -v
```

All PASS.

- [ ] **Step 4: Commit only (no push)**

```bash
git add deploy/README.md design/README.md measurements/prereq.md
git commit -m "$(cat <<'EOF'
Document image pins and record the 8.00 s default generate.

EOF
)"
```

Then parent close-out (spec → adversarial fix → re-smoke → push). Do not `git push` in this step. This is the last task; close-out still pushes.

---

## Deliverables checklist

| Deliverable | Task | Done when |
|---|---|---|
| Prerequisite evidence | 1 | `measurements/prereq.md` all PASS |
| Download speed log vs 8 Gbps | 1, 5, 6, 9 | `measurements/download-log.md` has a row per artifact |
| Weight checker | 2 | unit test PASS |
| Submit/poll helper | 4 | mock HTTP tests PASS |
| Host D-02 + SPAN tree | 6 | `check-weights.sh ~/h3-weights` exit 0 |
| Two locked workflows | 7 | lock tests PASS |
| Smoke script | 8 | offline audio unit PASS |
| `h3-spark:local` + compose | 9 | image well under 40 GiB; `/system_stats` 200 |
| Live 5.17 s mp4 with stereo | 10 | ffprobe channels=2 |
| Live 8.00 s mp4 (if smoke passed) | 11 | ffprobe channels=2 |
| Agent-callable command | 4, 10 | `./scripts/submit-prompt.sh workflows/h3-fl2va-default-8s.json --prompt …` |

## Out of scope (do not do in this plan)

- vLLM-Omni
- Ref2VA / `<Picture N>` graphs
- Multi-user HTTP
- Baking weights
- EasyCache / Sage 3 / `--lowvram`
- Publishing the image to a registry (local tag only)
- Committing mp4s or safetensors

## Spec coverage (self-review)

| Design rule | Task |
|---|---|
| D-01 ComfyUI first | 9–10 |
| D-02 files + launch flags | 2, 6, 9 |
| D-04 / D-05 960×544 + SPAN | 5, 7 |
| D-06 8 steps, two clocks | 7, 9 |
| D-07 5.17 / 8.00 | 7, 10, 11 |
| D-08 one job, no restart | 4, 10 |
| D-09 NGC GPU torch | 1, 9 |
| D-10 host weights | 2, 6, 9 |
| D-11 ComfyUI pin | 5, 9 |
| D-12 Sage 2.2 / triton_ref / H3 Safe | 7, 9 |
| D-13 no license gate | 9 |
| D-14 compose paths | 9 |
| Keyframe attach, not VAE-invent | 4 (optional flags only) |
| Record download speed on 8 Gbps ethernet | Speed-log protocol + Tasks 1, 5, 6, 9 |

## How to start (operator)

1. New Cursor chat on this repo, **Multitask mode** on.
2. Tell the parent: implement [`docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](2026-08-23-h3-comfyui-implement.md) with subagent-driven development.
3. Every subagent must be **Grok 4.6 / xhigh / fast** (`cursor-grok-4.6-xhigh-fast`).
4. After each task, run **all six close-out steps** in order: implementer commit → spec review → fixer (if needed) → adversarial review **and fix** → re-smoke → **`git push -u origin HEAD`** (never `--force`, never `--no-verify` unless the operator said so). The task “Commit” step is not the end.
5. Parent begins at Task 1. Do not skip prerequisite validation.
