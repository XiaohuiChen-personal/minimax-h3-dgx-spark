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
- Work on feature branch **`feat/h3-ref2va-default`**. Do not implement Tasks 1–9 on `main`. Push with `git push -u origin HEAD` (never `--force`).
- One GPU job at a time. Do not start or restart ComfyUI except Task 7 (image rebuild / `H3_TASK` start). Tasks 1–6 must not `docker compose down` / `up` / `restart` / `kill`. Tasks 8–9 must not restart. If Task 7/8/9 find the GPU busy with a leftover job, they may `POST /interrupt` or stop a **non-ComfyUI** leftover process. They must not start a second ComfyUI.
- Legal Ref2VA lengths in this plan: **5.17 s / 124**, **8.00 s / 192** (D-07 default), **15.08 s / 362**. Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04** graphs. D-07 rejected 15.08 as the everyday default — keep `h3-ref2va-default-8s.json` as the generate default.
- All locked Ref2VA graphs (smoke, default, **and** 15.08) ship nine `LoadImage` nodes titled `ref_image_0` … `ref_image_8`. Live Task 8 and Task 9 smokes still use the operator’s **six** stills (two birds × three views; N=6 of 9 slots), not a composite 3-view sheet. Submit wires only the first N `--ref-image` flags. Do not claim unbounded N (live `MiniMaxH3ReferenceToVideo` autogrow and submit max are 9; 10+ stay fail-close).
- Every task ends with **Parent close-out** (spec reviewer → fixer if needed → adversarial reviewer **and fixer** → re-smoke → push). Do not weaken that to “reviewer only.”
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
| `workflows/h3-ref2va-smoke-5s17.json` | 960×544, length 124, 4 steps, Ref2VA; nine `LoadImage` titles `ref_image_0`…`ref_image_8` |
| `workflows/h3-ref2va-default-8s.json` | 960×544, length 192, 4 steps, Ref2VA (D-07 default generate); nine titles |
| `workflows/h3-ref2va-long-15s08.json` | 960×544, length **362**, 4 steps, Ref2VA (15.08 s; not the default); nine titles |
| `workflows/h3-fl2va-*.json` | Unchanged product graphs |
| `tests/unit/test_check_weights.sh` | Shared / task / missing-file fixtures |
| `tests/unit/test_workflow_lock.py` | Split FL2VA vs Ref2VA forbidden strings |
| `tests/unit/test_submit_prompt.py` | `--ref-image` upload + nested wiring |
| `tests/fixtures/tiny-ref2va-workflow.json` | API graph with LoadImage + `MiniMaxH3ReferenceToVideo` |
| `deploy/compose.yaml` | `H3_TASK: ${H3_TASK:-ref2va}` |
| `deploy/Dockerfile` | `test -f` the **three** new Ref2VA workflow JSON files |
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

Locked Ref2VA lengths (all three graphs share the sampler / canvas / kernels above):

| Role | File | Seconds | Frames (`17n+5`) | `filename_prefix` |
|---|---|---|---|---|
| Fast smoke | `workflows/h3-ref2va-smoke-5s17.json` | 5.17 | 124 | `h3-ref2va-smoke` |
| Default generate | `workflows/h3-ref2va-default-8s.json` | 8.00 | 192 | `h3-ref2va` |
| Long (optional) | `workflows/h3-ref2va-long-15s08.json` | **15.08** | **362** | `h3-ref2va-15s08` |

**Why 4 steps.** Official Ref2V Turbo LoRA is 4-step. There is no Comfy-Org 8-step Ref2V LoRA. Do not strap the FL2V 8-step LoRA onto Ref2VA. D-06’s “8 steps for speech” stays on the FL2VA graphs.

**User selects FL2VA** by passing `workflows/h3-fl2va-default-8s.json` (or the 5.17 s smoke) to `submit-prompt.sh`. To make **start** require FL2VA instead of Ref2VA: `H3_TASK=fl2va` in `deploy/.env` or the compose environment, then recreate the container (Task 7). Both weight sets should already be on disk because the downloader defaults to `--task all`.

**User selects ~15 s Ref2VA** by passing `workflows/h3-ref2va-long-15s08.json`. Snap “15 s” / “15.04 s” to this file. Do not make it the default generate.

**Rejected.** Using `first_frame` for 3-view sheets. Preloading a UNET in the entrypoint. Requiring a license env flag. Shipping the stock R2V template unchanged. Inventing **15.00** or **15.04** graphs. A composite 3-view contact sheet as the primary smoke. Two GPU jobs (one per bird) for the same wiring proof. 15.08 s as the D-07 default.

---

## Operator amendments (2026-08-23)

Research notes, then the lock. Do not reopen these during Tasks 1–9.

**Sources cited**

- D-07 legal lengths and “rejected 15.08 as the default”: `design/decisions.md`
- Frame grid `17n+5` at 24 fps: `design/architecture.md`
- Comfy-Org node tags are 1-based `<Picture N>` / `<Video N>` / `<Audio N>` in **connection order**: [MiniMaxH3ReferenceToVideo](https://docs.comfy.org/built-in-nodes/MiniMaxH3ReferenceToVideo), [Comfy MiniMax H3 tutorial (R2V prompting tips)](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- Official full-reference rewrite (six sections; `<Subject N>` may cite `<Picture N>`): [VIDEO_PROMPT_WRITING_GUIDE_ref_en.md](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md), [h3-prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/SKILL.md)
- Visible scene text is preserved / H3 renders spelled-out text cleanly: same MiniMax rewrite guide (“text visibly present in the scene”) and the Comfy tutorial (“Accurate text rendering”)
- Operator stills (pixels verified 2026-08-23): six portrait JPEGs, all **1024 px tall**, printed `Front` / `Side` / `Back` in grey at the bottom. Chat captions match the pixels.

Pixel probe of the six files (Pillow + row scan, near-white threshold 240):

| Locked name | Source basename | Pixels | View word | Label ink `y` | Bird lowest `y` | Gap bird→label |
|---|---|---|---|---|---|---|
| `blue-front.jpg` | `78E74295-…_3-b4506c74-….jpg` | 386×1024 | Front | 936–956 | 882 | 53 px |
| `blue-side.jpg` | `78E74295-…_2-963ed79f-….jpg` | 474×1024 | Side | 935–955 | 879 | 55 px |
| `blue-back.jpg` | `78E74295-…-27107fe0-….jpg` | 313×1024 | Back | 935–955 | 883 | 51 px |
| `yellow-front.jpg` | `A54A17AE-…_3-2d36df87-….jpg` | 356×1024 | Front | 947–967 | 903 | 43 px |
| `yellow-side.jpg` | `A54A17AE-…_2-09becfd0-….jpg` | 519×1024 | Side | 947–967 | 900 | 46 px |
| `yellow-back.jpg` | `A54A17AE-…-91af16e7-….jpg` | 306×1024 | Back | 946–967 | 904 | 41 px |

An 80 px bottom crop (`ih-80` → height 944) keeps every bird. Tightest leftover above the crop line: yellow-back (904 < 944).

### A. Duration snap

| Option | Pros | Cons |
|---|---|---|
| **15.08 s / 362** (`17×21+5`, 362/24 = 15.0833 s) | Legal D-07 length. Matches the operator’s “~15.04 s” ask. Same encoding as `5s17`. | Slower than 8.00 s. D-07 says this is where “bad audio” stories pile up. |
| 15.04 s / ~361 frames | Matches the spoken number | **Illegal.** 15.04×24 = 360.96. Not `17n+5`. |
| 15.00 s / 360 frames | Round number | **Illegal.** 360 = 17×20+20, not `17n+5`. |
| Keep only 5.17 / 8.00 | Faster plan | Operator required a generatable, smoke-tested ~15 s path. |

**Chosen:** `workflows/h3-ref2va-long-15s08.json`, `length` **362**, `filename_prefix` `h3-ref2va-15s08`. The `long` token marks role (like `smoke` / `default`); `15s08` matches the `5s17` fractional encoding. Default generate stays the 8.00 s file (D-07).

### B. Where the 15.08 graph is built vs smoked

| Option | Pros | Cons |
|---|---|---|
| **Build + lock-test in Task 4; live GPU 15.08 in new Task 9** | First live proof stays the cheap 5.17 s wiring test. 15.08 cannot hide a Task 4 JSON bug — lock tests catch `362` before GPU time. | Extra task. |
| Fold 15.08 live into Task 8 | Fewer tasks | A 15-minute GPU job sitting behind the first 5.17 proof. If 5.17 fails you still burned the long job, or you skip the long proof. |
| Build the 15.08 JSON in Task 9 | Isolates the long file | Dockerfile `test -f` (Task 5) and AGENTS (Task 6) would mention a file that does not exist yet. |

**Chosen:** Task 4 builds and lock-tests all three JSONs (same `test_workflow_lock.py`). Task 5 `test -f` includes the 15.08 file. Task 6 lists it as the “~15 seconds / 15.08 s” path. Task 8 lives **only** 5.17 s. **Task 9** is the live 15.08 s proof.

### C. Six reference images (wiring + smoke)

| Option | Pros | Cons |
|---|---|---|
| **Six `LoadImage` nodes on every Ref2VA graph; six `--ref-image` flags; six host files** | Product path the operator asked for. No JSON edit to attach 6 refs. | Larger graphs. Prompt must name all six tags. |
| One composite 3-view sheet, one `--ref-image` | Fewer uploads | Operator forbade this as the **primary** smoke. Loses per-view `<Picture N>` control. |
| Two LoadImage nodes (one bird) | Smaller | Cannot prove two-identity wiring. |

**Chosen (smoke recipe, still in force):** Task 8/9 use six `--ref-image` flags and the six host files below. Default prompts still document `<Picture 1>`…`<Picture 6>`. Do **not** commit a `ref_images` dict (submit writes the nested dict).

**Title count superseded by J:** the product lock is nine slots (`ref_image_0`…`ref_image_8`), not six. C is the six-bird smoke, not the graph ceiling.

**`--ref-image` / `<Picture N>` order** (1-based tags = upload order = title suffix + 1). Confirmed against pixels, not chat captions:

| Flag order | `$HOME/h3-data` name | `<Picture N>` | Identity + view |
|---|---|---|---|
| 1 | `blue-front.jpg` | `<Picture 1>` | blue Front |
| 2 | `blue-side.jpg` | `<Picture 2>` | blue Side |
| 3 | `blue-back.jpg` | `<Picture 3>` | blue Back |
| 4 | `yellow-front.jpg` | `<Picture 4>` | yellow Front |
| 5 | `yellow-side.jpg` | `<Picture 5>` | yellow Side |
| 6 | `yellow-back.jpg` | `<Picture 6>` | yellow Back |

Cursor asset → dest mapping (copy/crop in Task 8 Step 1; **do not commit**):

```text
…/assets/78E74295-FF28-40F5-9002-C3AAFF8608E3_3-b4506c74-a621-488f-842a-f474247bcd5a.jpg  →  $HOME/h3-data/blue-front.jpg
…/assets/78E74295-FF28-40F5-9002-C3AAFF8608E3_2-963ed79f-7e20-4cd9-8474-1a282c80c508.jpg  →  $HOME/h3-data/blue-side.jpg
…/assets/78E74295-FF28-40F5-9002-C3AAFF8608E3-27107fe0-4aad-44f5-b78c-f82b7a204def.jpg     →  $HOME/h3-data/blue-back.jpg
…/assets/A54A17AE-824F-4899-B252-54DF46DE1340_3-2d36df87-8570-44c7-be8f-4507298db573.jpg  →  $HOME/h3-data/yellow-front.jpg
…/assets/A54A17AE-824F-4899-B252-54DF46DE1340_2-09becfd0-dd8a-4da8-b974-fdd279d9b37a.jpg  →  $HOME/h3-data/yellow-side.jpg
…/assets/A54A17AE-824F-4899-B252-54DF46DE1340-91af16e7-ae0f-4714-993f-7719229ec008.jpg     →  $HOME/h3-data/yellow-back.jpg
```

**Prompt language.** Official Comfy R2V tip: name each input with `<Picture N>` in connection order and assign a job (identity). Official MiniMax rewrite: six sections; a character is `<Subject N>` whose appearance comes from `<Picture N>`. Live Task 8 / Task 9 prompts use that six-section form (quality). Committed JSON default prompts may stay shorter and still mention `<Picture 1>`…`<Picture 6>` so the tag language is documented. First smokes stay **quiet / no speech**: D-06 says 4 steps smear dialogue; Comfy’s own R2V turbo note says the 4-step LoRA trades audio quality; a 15.08 proof is length + identity + wiring, not a speech demo.

### D. One video with both birds vs two videos

| Option | Pros | Cons |
|---|---|---|
| **One 5.17 s smoke and one 15.08 s smoke, both with all six refs** | Harder real product path. Proves two-identity nested `ref_images`. One GPU job per length. | If identity collapses, you cannot tell which bird the graph “prefers” without a second run. |
| Two 5.17 s jobs (one bird each) plus 15.08 | Cleaner A/B | Operator asked to use both birds, not to burn the GPU twice for the same wiring proof. No evidence that quality **requires** split jobs. |
| 15.08 only | Saves a 5.17 job | Loses the cheap first live proof (B). |

**Chosen:** one two-bird 5.17 s (Task 8) and one two-bird 15.08 s (Task 9). No second GPU job per bird.

### E. Printed labels on the stills

| Option | Pros | Cons |
|---|---|---|
| Use as-is + prompt “ignore Front/Side/Back” | Operator’s default preference. Zero pixel loss. | MiniMax rewrite guide **preserves visible scene text**. Comfy tutorial advertises accurate text rendering. The words can burn into the mp4. |
| **Crop the clean 80 px footer** | Label ink is a 21–22 px grey word on white, 41–55 px below the tail. 80 px crop never hits feathers (measured). Highest identity quality: no caption tokens. | Slightly tighter framing. Extra Task 8 command. |
| Manual per-file crop | Could shave less white | Six different recipes. Easy to clip a tail. |

**Chosen:** crop. Quality > the as-is shortcut. Footer is a clean white strip (not a graphic bar on the bird). Exact command (ffmpeg 7.x is on this Spark at `~/.local/bin/ffmpeg`; ImageMagick `convert` is also present):

```bash
ffmpeg -y -i "$src" -vf "crop=iw:ih-80:0:0" "$dest"
# equivalent: convert "$src" -gravity North -crop x944+0+0 +repage "$dest"
```

Outputs live under `$HOME/h3-data/*.jpg` only. Never git-add them. Prompts still say the printed words are captions, in case a later generate uses an uncropped still.

### F. Branching

| Option | Pros | Cons |
|---|---|---|
| **`feat/h3-ref2va-default` from current `main`** | Matches the operator. Later workers stay off `main`. | One extra checkout. |
| Implement on `main` | Fewer git steps | Operator forbade it. |

**Chosen:** `feat/h3-ref2va-default`. `git push -u origin HEAD`. Never `--force`.

### G. Old SDD ledger

| Option | Pros | Cons |
|---|---|---|
| **Archive `progress.md` → `progress-h3-comfyui-implement.md`; new `progress.md` for this plan** | FL2VA Tasks 1–11 stay readable. This plan gets a clean ledger. | `.superpowers/sdd/.gitignore` is `*`, so ledgers stay **on disk only**. |
| Reuse the FL2VA ledger | One file | Mixes two plans. Easy to mark Task 1 “complete” by accident. |

**Chosen:** archive + new ledger. Header names this plan, workspace `/home/xiaohui_chen/Projects/minimax-h3-dgx-spark`, branch `feat/h3-ref2va-default`, start HEAD = the plan-amendment commit. Do not force-add ignored files.

### H. Adversarial close-out

| Option | Pros | Cons |
|---|---|---|
| **Copy-paste Parent close-out = AGENTS.md sequence, adversarial agent may fix** | Same contract as the FL2VA implement plan. Catches illegal lengths and Ref2VA drift. | More subagent turns. |
| Spec reviewer only | Faster | Operator forbade weakening this. |

**Chosen:** the **Parent close-out** section below. Every task ends with “Then parent close-out”.

### I. Stopping ComfyUI

| Option | Pros | Cons |
|---|---|---|
| **Tasks 1–6 no compose down/up/restart; Task 7 may recreate once; Task 8–9 no restart; interrupt leftover GPU jobs** | Matches D-08 and the operator’s “you may free the GPU” note without a second server. | Task 7 is the only allowed recreate. |
| Restart whenever the GPU looks busy | Simple | Reloads weights. Violates D-08. |

**Chosen:** the Global Constraints bullet above. `POST http://127.0.0.1:8188/interrupt` if a leftover **ComfyUI** job holds the GPU. Stop a non-ComfyUI leftover process if that is what is busy. Never start a second ComfyUI.

### J. Variable reference-image count

Real apps have undetermined N. The live node does not: `GET /object_info/MiniMaxH3ReferenceToVideo` autogrow is **0–9** (`ref_image_` prefix). `submit-prompt.py` already hard-caps `--ref-image` at 9. **10+ stay fail-close.** Do not claim unbounded N.

Audit (`.superpowers/sdd/ref-image-count-audit.md`, 2026-08-23): leftover unlinked `LoadImage` nodes stay `example.png`, are omitted from the nested `ref_images` dict, and are **not** in the SaveVideo DAG — they do not execute and do not condition the video.

| Option | Pros | Cons |
|---|---|---|
| **B. Ship 9 titles (`ref_image_0`…`ref_image_8`) on all three graphs** | Matches the node max and Task 3’s `ref_image_0`…`ref_image_8` interface. Submit already wires 1–N without inventing nodes. Unused extras are the same class as today’s unused `ref_image_3`…`5` when N=3. | Three idle `LoadImage` nodes in each JSON. |
| A. Keep 6 titles; fail-close at 7–9 | Already shipped with Task 4 | Node-legal 7–9 stills need a JSON edit. Freezes the six-bird smoke as the product cap. |
| C. Dynamically inject `LoadImage` nodes in submit when N > titles | No JSON edit for 7–9 | Invents DAG nodes. Conflicts with “fill a **locked** graph.” Task 3 already fail-closes instead of growing. More moving parts. |
| D. Unbounded N | — | **False.** Autogrow `max: 9`. Submit `MAX_REF_IMAGES = 9`. |

**Chosen: B.** Reject D. Reject C unless a proven bug in B (none found).

| When | Graph titles | What submit does |
|---|---|---|
| Pre-this-change | 6 (`ref_image_0`…`ref_image_5`, nodes `24`–`29`) | 1–6 wire. **7–9 fail-close** (not enough titles). 10+ fail-close at the cap. |
| After this change | 9 (`ref_image_0`…`ref_image_8`, nodes `24`–`32`) | Wires only the first N nested keys. Leftover `LoadImage`s stay unlinked `example.png` and are **not** in the SaveVideo DAG. 10+ still fail-close. |

Zero refs: still POST without a `ref_images` dict (existing Task 3 behavior: omit `--ref-image`). That is node-legal, not a proven identity generate. **Identity tasks should pass ≥1 `--ref-image`.** 0 identity stills → submit an FL2VA graph, not 0-ref Ref2VA.

`<Picture N>` is **1-based** and matches `--ref-image` order for whatever N was passed (1–9). Write `<Picture 1>`…`<Picture N>` only. Tags for k > N are empty theater (no leftover `example.png` pixels).

Task 6 docs / `AGENTS.md` must say **variable 1–9**, not “six only” / “this product locks 6 LoadImage titles.” Task 8/9 smokes still use the six bird stills (N=6 of 9 slots). Do not require 9 stills for smoke. Default committed prompts may keep `<Picture 1>`…`<Picture 6>` as that smoke example; lock tests must **not** require `<Picture 9>`.

---

## Parent close-out

Copy this after every task. Do **not** start Task N+1 and do **not** push until this list is done for Task N. Do not weaken step 4 to “reviewer only.”

**Required model** on every implementer, spec reviewer, adversarial reviewer, and fixer: Cursor slug `cursor-grok-4.6-xhigh-fast`. Do not inherit the parent model. Do not substitute Claude, GPT, or Composer. If the slug is missing, **stop**.

1. **Implementer** (`cursor-grok-4.6-xhigh-fast`): implement only Task N, TDD as specified, **commit only**. No push.
2. **Spec reviewer** (`cursor-grok-4.6-xhigh-fast`, read-only): diff vs this plan’s Task N and `design/*.md`. Spec ✅/❌. Does not edit.
3. **Fixer** if Critical/Important: same model; implement only those fixes; commit; re-run the covering tests.
4. **Adversarial reviewer AND fixer** (new subagent, same model): hunt inaccuracies, bugs, silent fallbacks, forbidden flags, tests that pass on stubs, CPU-torch traps, baked weights, license gates, Ref2VA drift, illegal lengths (**15.04 / 15.00 / 10.00**), FL2VA LoRA on Ref2VA, flat `ref_image_0` keys, host paths in `LoadImage`. Fix what you can prove. Commit `fix: … after adversarial review of Task N`. Do not invent a new stack.
5. **Re-smoke** (do not `|| true`). If re-smoke fails, fix and re-smoke again. No push on red tests.
   - Tasks 1–6:

```bash
cd /home/xiaohui_chen/Projects/minimax-h3-dgx-spark
[[ -f tests/unit/test_check_weights.sh ]] && bash tests/unit/test_check_weights.sh
[[ -f tests/unit/test_download_weights_help.sh ]] && bash tests/unit/test_download_weights_help.sh
[[ -f tests/unit/test_entrypoint_flags.sh ]] && bash tests/unit/test_entrypoint_flags.sh
compgen -G 'tests/unit/test_*.py' >/dev/null && python3 -m pytest tests/unit -v
```

   - Task 7:

```bash
curl -fsS http://127.0.0.1:8188/system_stats
docker compose -f deploy/compose.yaml ps
```

   - Task 8: offline 5.17 mp4; **also** a live 5.17 re-run if graphs, scripts, or the image changed:

```bash
./scripts/smoke-test.sh --offline-mp4 "$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4"
```

   - Task 9: offline 15.08 mp4 only (do not restart ComfyUI; do not run a second 15.08 unless the long graph/scripts/image changed — then re-run the Task 9 submit):

```bash
./scripts/smoke-test.sh --offline-mp4 "$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4"
```

6. **`git push -u origin HEAD`**. Never `--force`. Never `--no-verify` unless the operator said so.

**Adversarial prompt (parent must include).**

- You are an adversarial reviewer **and fixer** on Grok 4.6 xhigh fast (`cursor-grok-4.6-xhigh-fast`).
- Scope: Task N diff + the files it touched + this plan’s Decision lock and Operator amendments.
- Hunt the list in step 4. Fix what you can prove. Re-run the re-smoke commands. Commit. Do not push (close-out step 6 pushes).
- Return: finding → fix → test evidence.

**Dispatch slug (parent must copy):**

```text
Task.model = cursor-grok-4.6-xhigh-fast
```

**Order.** Do not start Task N+1 until Task N close-out (including push) is done, except: Task 2 download and Task 3 `--ref-image` may overlap after Task 1 if only one writer is active (Task 3 does not need the new weights). Task 4 may start after Task 3 (needs the submit contract) and does not need the download. Task 5 needs Task 1. Task 6 may start after Task 4 (docs name the three JSONs). Task 7 needs Tasks 2 + 4 + 5. Task 8 needs Task 7. Task 9 needs Task 8.

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

Then parent close-out (copy **Parent close-out**).

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

Then parent close-out (copy **Parent close-out**). After this task the **running** container can see the new files (same binds) without a rebuild. Do not submit a Ref2VA sample yet — graphs do not exist.

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

Then parent close-out (copy **Parent close-out**).

---

### Task 4: Locked Ref2VA graphs and lock tests

**Files:**
- Create: `workflows/h3-ref2va-smoke-5s17.json`
- Create: `workflows/h3-ref2va-default-8s.json`
- Create: `workflows/h3-ref2va-long-15s08.json`
- Modify: `tests/unit/test_workflow_lock.py`
- Modify: `scripts/smoke-test.sh`

**Interfaces:**
- Consumes: `workflows/h3-fl2va-default-8s.json` as the structural template (same Sage / Sol-Attn / FBC / SPAN / SaveVideo chain)
- Produces: **three** API-format Ref2VA graphs. Smoke `length=124`, default `length=192`, long `length=362`. All three: width 960, height 544, steps 4, Ref2VA FP8 UNET, Ref2V 4-step LoRA, `MiniMaxH3ReferenceToVideo` with `audio_vae` linked to the audio VAE loader, `ref_image_size=match`, nine `LoadImage` nodes titled `ref_image_0` … `ref_image_8` (so **1–9** `--ref-image` flags work without editing JSON). Do **not** put a `ref_images` dict in the committed JSON (0 refs until submit wires it). Default prompt documents `<Picture 1>` … `<Picture 6>` in the locked blue-then-yellow front/side/back order (the six-bird smoke example; graphs accept up to nine stills).

- [ ] **Step 1: Write lock tests first**

Add to `tests/unit/test_workflow_lock.py` (keep the existing FL2VA tests and their forbidden list, including `ref2va` and `MiniMaxH3ReferenceToVideo` **only on the FL2VA files**):

```python
REF2VA_GRAPHS = (
    "h3-ref2va-smoke-5s17.json",
    "h3-ref2va-default-8s.json",
    "h3-ref2va-long-15s08.json",
)


def test_ref2va_smoke_default_and_long():
    smoke = load("h3-ref2va-smoke-5s17.json")
    default = load("h3-ref2va-default-8s.json")
    long = load("h3-ref2va-long-15s08.json")
    assert 124 in int_inputs(smoke, "length")
    assert 192 not in int_inputs(smoke, "length")
    assert 362 not in int_inputs(smoke, "length")
    assert 192 in int_inputs(default, "length")
    assert 124 not in int_inputs(default, "length")
    assert 362 not in int_inputs(default, "length")
    assert 362 in int_inputs(long, "length")
    assert 124 not in int_inputs(long, "length")
    assert 192 not in int_inputs(long, "length")
    assert 360 not in int_inputs(long, "length")
    assert 361 not in int_inputs(long, "length")
    for name in REF2VA_GRAPHS:
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
        assert "<Picture 1>" in raw
        assert "<Picture 6>" in raw
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
        assert titles == [f"ref_image_{i}" for i in range(9)]
        ref2va_nodes = [
            node
            for node in prompt_graph(g).values()
            if node.get("class_type") == "MiniMaxH3ReferenceToVideo"
        ]
        assert len(ref2va_nodes) == 1
        assert "ref_images" not in (ref2va_nodes[0].get("inputs") or {})
        for key in (ref2va_nodes[0].get("inputs") or {}):
            assert not str(key).startswith("ref_image_"), key


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

- [ ] **Step 3: Build the three JSON files**

Copy `workflows/h3-fl2va-default-8s.json` to all three new names, then apply **all** of these edits. Only `length` and `filename_prefix` differ across the three files.

1. Node `1` `_meta.title` → `Load Ref2VA DiT (D-15 FP8)` and `unet_name` → `minimax_h3_ref2va_pruned_fp8_scaled.safetensors`
2. Node `5` `_meta.title` → `Comfy-Org Ref2V Turbo 4-step LoRA` and `lora_name` → `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors`
3. Node `13` `_meta.title` → `simple scheduler: 4 steps / 5 sigma points (includes final zero)` and `steps` → `4`
4. Replace node `10` with the block below. Use the `length` / `filename_prefix` row for that file.

`workflows/h3-ref2va-smoke-5s17.json` — `"length": 124`, SaveVideo `filename_prefix` `h3-ref2va-smoke`.

`workflows/h3-ref2va-default-8s.json` — `"length": 192`, SaveVideo `filename_prefix` `h3-ref2va`.

`workflows/h3-ref2va-long-15s08.json` — `"length": 362`, SaveVideo `filename_prefix` `h3-ref2va-15s08`.

Smoke node `10`:

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
    "prompt": "<Picture 1> <Picture 2> <Picture 3> are front, side, and back stills of the blue monk parakeet. <Picture 4> <Picture 5> <Picture 6> are front, side, and back stills of the yellow monk parakeet. Printed Front/Side/Back words are captions, not plumage. A quiet scene. No speech.",
    "width": 960,
    "height": 544,
    "length": 124,
    "ref_image_size": "match"
  }
}
```

Default node `10` (same keys; only `length` changes):

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
    "prompt": "<Picture 1> <Picture 2> <Picture 3> are front, side, and back stills of the blue monk parakeet. <Picture 4> <Picture 5> <Picture 6> are front, side, and back stills of the yellow monk parakeet. Printed Front/Side/Back words are captions, not plumage. A quiet scene. No speech.",
    "width": 960,
    "height": 544,
    "length": 192,
    "ref_image_size": "match"
  }
}
```

Long node `10`:

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
    "prompt": "<Picture 1> <Picture 2> <Picture 3> are front, side, and back stills of the blue monk parakeet. <Picture 4> <Picture 5> <Picture 6> are front, side, and back stills of the yellow monk parakeet. Printed Front/Side/Back words are captions, not plumage. A quiet scene. No speech.",
    "width": 960,
    "height": 544,
    "length": 362,
    "ref_image_size": "match"
  }
}
```

5. Add LoadImage nodes `24`–`32` to **every** Ref2VA file (unlinked until `submit-prompt.py` writes `ref_images`; leftover titles after N stills stay `example.png` and out of the SaveVideo DAG):

```json
"24": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_0" },
  "inputs": { "image": "example.png" }
},
"25": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_1" },
  "inputs": { "image": "example.png" }
},
"26": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_2" },
  "inputs": { "image": "example.png" }
},
"27": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_3" },
  "inputs": { "image": "example.png" }
},
"28": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_4" },
  "inputs": { "image": "example.png" }
},
"29": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_5" },
  "inputs": { "image": "example.png" }
},
"30": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_6" },
  "inputs": { "image": "example.png" }
},
"31": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_7" },
  "inputs": { "image": "example.png" }
},
"32": {
  "class_type": "LoadImage",
  "_meta": { "title": "ref_image_8" },
  "inputs": { "image": "example.png" }
}
```

6. Keep nodes 6–9, 11–23, SPAN crop, SaveVideo. Set `filename_prefix` as in the length table above.
7. Do not add `first_frame` / `last_frame`. Do not add EasyCache / `flex_attention` / NVFP4. Do not add a `ref_images` key. Do not write host paths into `LoadImage.image`.

- [ ] **Step 4: Point smoke-test.sh at the Ref2VA 5.17 s graph by default**

Replace `scripts/smoke-test.sh` with this file (offline probe unchanged; live default is the Ref2VA 5.17 graph; `--workflow` and `--ref-image` are first-class):

```bash
#!/usr/bin/env bash
# Submit a locked 5.17 s smoke graph, or probe an existing mp4.
# Exit 0 only if the file has a video stream and stereo audio (ffprobe audio,2).
# --offline-mp4: probe only. Do not test -f the workflow, call submit-prompt, or start Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKFLOW="$ROOT/workflows/h3-ref2va-smoke-5s17.json"
SUBMIT="$ROOT/scripts/submit-prompt.sh"

OFFLINE_MP4=""
PROMPT=""
SEED=""
NAME=""
FORWARD=()

usage() {
  echo "usage: $0 --offline-mp4 <path>" >&2
  echo "       $0 --prompt TEXT --seed N --name PREFIX [--workflow PATH] [submit-prompt flags]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline-mp4)
      OFFLINE_MP4="${2:?usage: --offline-mp4 <path>}"
      shift 2
      ;;
    --workflow)
      WORKFLOW="${2:?}"
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
    --first-frame|--last-frame|--base-url|--output-root|--ref-image)
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

if [[ ! -f "$WORKFLOW" ]]; then
  echo "error: missing workflow $WORKFLOW" >&2
  exit 1
fi
if [[ -z "$PROMPT" || -z "$SEED" || -z "$NAME" ]]; then
  echo "error: live mode requires --prompt --seed --name" >&2
  exit 2
fi

set +e
out="$("$SUBMIT" "$WORKFLOW" --prompt "$PROMPT" --seed "$SEED" --name "$NAME" ${FORWARD[@]+"${FORWARD[@]}"})"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  printf '%s\n' "$out"
  exit "$rc"
fi

printf '%s\n' "$out"

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
  exit 1
fi

probe_mp4 "$mp4"
```

`chmod 0755 scripts/smoke-test.sh`

Do **not** run a live generate in this task. Do **not** run the 15.08 graph here.

- [ ] **Step 5: Run lock tests**

```bash
python3 -m pytest tests/unit/test_workflow_lock.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit only**

```bash
git add workflows/h3-ref2va-smoke-5s17.json workflows/h3-ref2va-default-8s.json \
  workflows/h3-ref2va-long-15s08.json tests/unit/test_workflow_lock.py \
  scripts/smoke-test.sh
git commit -m "$(cat <<'EOF'
Lock Ref2VA 5.17 s, 8.00 s, and 15.08 s graphs next to the FL2VA pair.

EOF
)"
```

Then parent close-out (copy **Parent close-out**).

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
    && test -f /opt/h3/workflows/h3-ref2va-default-8s.json \
    && test -f /opt/h3/workflows/h3-ref2va-long-15s08.json
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

Then parent close-out (copy **Parent close-out**). **Still do not recreate the container** until Task 7.

---

### Task 6: Design and agent docs (D-15)

**Files:**
- Modify: `design/decisions.md` (add D-15; do not reopen D-01…D-14)
- Modify: `design/architecture.md` (Ref2VA is now a shipped second graph, default generate path)
- Modify: `design/operator.md` (default graph, `--ref-image`, `H3_TASK`, `/upload/image`, no `<Picture N>` on FL2VA)
- Modify: `design/container.md` (required start set is shared + Ref2VA; FL2VA optional on disk)
- Modify: `design/README.md` (D-01…D-15; point at this plan)
- Modify: `AGENTS.md` (Generate a video table: default = `workflows/h3-ref2va-default-8s.json`; add the 15.08 row; replace “Do not add a third graph”; FL2VA still listed; `--ref-image`; still no negative prompt)
- Modify: `README.md` (same “Do not add a third graph” replacement; five locked graphs)
- Modify: `workflows/README.md` (five locked graphs: two FL2VA + three Ref2VA; Ref2VA files may contain `<Picture N>` and `MiniMaxH3ReferenceToVideo`)
- Modify: `scripts/README.md`
- Modify: `deploy/README.md` (default generate command uses the Ref2VA 8 s graph)
- Modify: `docs/design/*.html` to match the markdown (same content, no new stack)

**Interfaces:**
- Consumes: D-15 text from this plan’s “Decision lock”
- Produces: docs that tell an agent to default to Ref2VA 8.00 s, how to select the 15.08 s graph, and how to select FL2VA

- [ ] **Step 1: Write D-15 into `design/decisions.md`**

Copy the “Decision lock (D-15)” section from this plan into a card with Status **adopted for implementation**. Include the file table, the 5.17 / 8.00 / **15.08** length table, 4-step reason, how to select FL2VA, how to select the 15.08 graph, and the Rejected list (15.00 / 15.04 graphs, composite sheet as primary smoke, FL2V LoRA on Ref2VA).

- [ ] **Step 2: Update AGENTS.md generate table**

Replace the “Pick a locked workflow” table **and** the sentence `Do not add a third graph.` with:

```markdown
| User ask | File | Length |
|---|---|---|
| Default / “about 8 seconds” | `workflows/h3-ref2va-default-8s.json` | **8.00 s / 192** |
| Fast smoke / “about 5 seconds” | `workflows/h3-ref2va-smoke-5s17.json` | **5.17 s / 124** |
| “15 seconds” / “15.04 s” / “about 15 seconds” | `workflows/h3-ref2va-long-15s08.json` | **15.08 s / 362** |
| Text-only / no identity images, about 8 seconds | `workflows/h3-fl2va-default-8s.json` | **8.00 s / 192** |
| Text-only fast smoke | `workflows/h3-fl2va-smoke-5s17.json` | **5.17 s / 124** |

Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04**. If they say “10 seconds,” snap to **10.13 s** or refuse. Never invent **10.00 s**. There is no locked 10.13 s JSON in this repo — refuse or ask them to accept 8.00 s.
```

Add `--ref-image` to the inputs table (optional, host files, uploaded via `POST /upload/image`, **variable 1–9**; this product ships nine `LoadImage` titles `ref_image_0`…`ref_image_8`. Do **not** say “six only.” 10+ refuse. 0 refs → FL2VA, not 0-ref Ref2VA). State that identity stills are Ref2VA `--ref-image` + 1-based `<Picture N>` tags in `--ref-image` order, **not** `first_frame`. Do not write `<Picture N>` on FL2VA graphs. Task 8/9 smokes still use the six bird stills (N=6).

- [ ] **Step 3: Update the other markdown files listed above**

In root `README.md` replace `Use the two locked workflows… Do not add a third graph.` with: five locked graphs (the AGENTS table), default generate is Ref2VA 8.00 s, ~15 s uses `h3-ref2va-long-15s08.json`.

In `workflows/README.md` list all five JSON filenames. Allow `<Picture N>` and `MiniMaxH3ReferenceToVideo` **only** on the three Ref2VA files.

Copy the D-15 length table (5.17 / 8.00 / 15.08) into `design/operator.md` and `design/architecture.md` (Ref2VA is now a shipped default generate path, not “we do not ship first”).

Do not claim a live Ref2VA mp4 exists yet.

- [ ] **Step 4: Mirror HTML under `docs/design/`**

- [ ] **Step 5: Commit only**

```bash
git add design AGENTS.md README.md workflows/README.md scripts/README.md \
  deploy/README.md docs/design
git commit -m "$(cat <<'EOF'
Document Ref2VA as the default task and keep FL2VA selectable.

EOF
)"
```

Then parent close-out (copy **Parent close-out**).

---

### Task 7: Rebuild the image and start default Ref2VA

**Files:** none in git except a download-log row if the build clone timings are appended (optional; do not invent rows).

**Interfaces:**
- Consumes: Task 2 weights on the host (`--task all`), Task 5 compose/entrypoint/Dockerfile, Task 4 JSON copied into the image
- Produces: `h3-spark:local` rebuilt; container recreated with `H3_TASK=ref2va`; `/system_stats` 200

The operator asked for this change, so this task **may** `docker compose down` / `build` / `up -d`. Do it once. Do not restart again for Task 8 or Task 9. If a leftover ComfyUI job is on the GPU before `down`, free it first:

```bash
curl -fsS -X POST http://127.0.0.1:8188/interrupt || true
```

(`|| true` is allowed here only because the server may already be down. Do not use `|| true` on unit tests.) Do not start a second ComfyUI.

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

Confirm the image copied all three Ref2VA graphs:

```bash
docker compose -f deploy/compose.yaml exec -T comfyui \
  test -f /opt/h3/workflows/h3-ref2va-smoke-5s17.json
docker compose -f deploy/compose.yaml exec -T comfyui \
  test -f /opt/h3/workflows/h3-ref2va-default-8s.json
docker compose -f deploy/compose.yaml exec -T comfyui \
  test -f /opt/h3/workflows/h3-ref2va-long-15s08.json
```

Expected: three silent exits 0.

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

If nothing changed in git, do not create an empty commit. Then parent close-out (copy **Parent close-out**; `curl /system_stats` is the re-smoke).

---

### Task 8: Live Ref2VA 5.17 s (both birds), then prove FL2VA is still selectable

**Files:**
- None required. Optional: a line in `measurements/prereq.md` for the live Ref2VA 5.17 s smoke, modeled on the existing FL2VA Task 10 paragraph.

**Interfaces:**
- Consumes: running server from Task 7, `workflows/h3-ref2va-smoke-5s17.json`, six `$HOME/h3-data/*.jpg` files, `--ref-image`
- Produces: host mp4 `~/h3-output/smoke-ref2va-5s17_00001_.mp4` with video + stereo audio; FL2VA graph still accepted by `/prompt` validation. Does **not** run the 15.08 graph.

Do **not** restart ComfyUI. If a leftover job holds the GPU:

```bash
curl -fsS -X POST http://127.0.0.1:8188/interrupt
```

Do not start a second ComfyUI. Do not `docker compose down` / `up`.

- [ ] **Step 1: Crop the six operator stills into `$HOME/h3-data`**

Do not commit these JPEGs. Decision E: drop the 80 px caption footer.

```bash
ASSET="/home/xiaohui_chen/.cursor/projects/home-xiaohui-chen-Projects-minimax-h3-dgx-spark/assets"
mkdir -p "$HOME/h3-data"

crop_ref() {
  local src="$1" dest="$2"
  test -f "$src"
  ffmpeg -y -i "$src" -vf "crop=iw:ih-80:0:0" "$dest"
}

crop_ref "$ASSET/78E74295-FF28-40F5-9002-C3AAFF8608E3_3-b4506c74-a621-488f-842a-f474247bcd5a.jpg" \
  "$HOME/h3-data/blue-front.jpg"
crop_ref "$ASSET/78E74295-FF28-40F5-9002-C3AAFF8608E3_2-963ed79f-7e20-4cd9-8474-1a282c80c508.jpg" \
  "$HOME/h3-data/blue-side.jpg"
crop_ref "$ASSET/78E74295-FF28-40F5-9002-C3AAFF8608E3-27107fe0-4aad-44f5-b78c-f82b7a204def.jpg" \
  "$HOME/h3-data/blue-back.jpg"
crop_ref "$ASSET/A54A17AE-824F-4899-B252-54DF46DE1340_3-2d36df87-8570-44c7-be8f-4507298db573.jpg" \
  "$HOME/h3-data/yellow-front.jpg"
crop_ref "$ASSET/A54A17AE-824F-4899-B252-54DF46DE1340_2-09becfd0-dd8a-4da8-b974-fdd279d9b37a.jpg" \
  "$HOME/h3-data/yellow-side.jpg"
crop_ref "$ASSET/A54A17AE-824F-4899-B252-54DF46DE1340-91af16e7-ae0f-4714-993f-7719229ec008.jpg" \
  "$HOME/h3-data/yellow-back.jpg"

for f in blue-front blue-side blue-back yellow-front yellow-side yellow-back; do
  test -f "$HOME/h3-data/${f}.jpg"
done
```

- [ ] **Step 2: Live Ref2VA 5.17 s with both birds**

Do **not** restart ComfyUI. Do **not** run `h3-ref2va-long-15s08.json` here.

```bash
PROMPT="$(cat <<'EOF'
subject_definitions:
<Subject 1> is the blue monk parakeet whose appearance comes from <Picture 1> (front), <Picture 2> (side), and <Picture 3> (back): powder-blue wings and tail, silvery-grey face and scalloped breast, horn-colored hooked beak, grey feet. Any printed word Front, Side, or Back at the bottom of those stills is a studio caption, not plumage, not a perch, and must not appear in the video.
<Subject 2> is the yellow monk parakeet whose appearance comes from <Picture 4> (front), <Picture 5> (side), and <Picture 6> (back): bright yellow wings and tail, creamy-yellow face and chest, horn-colored hooked beak, pale feet, a small red leg band. The same printed Front/Side/Back captions are labels only and must not appear.

summary:
A 5.17-second quiet indoor two-shot of both parakeets on one pale wooden perch. Identity is taken from all six stills. No speech and no lyric music.

retention_analysis:
<Subject 1> (whole clip): fully_preserved — keep the blue mutation colors, beak, and body shape from <Picture 1>, <Picture 2>, and <Picture 3>.
<Subject 2> (whole clip): fully_preserved — keep the yellow mutation colors, beak, red band, and body shape from <Picture 4>, <Picture 5>, and <Picture 6>.
Printed captions: not preserved.

detailed_description:
[Shot 1] 0.00-5.17s. Medium two-shot, eye-level, a very slow gentle push-in. Soft morning window light, a plain white wall, one pale wooden perch. <Subject 1> sits on the left end of the perch and <Subject 2> sits on the right, a hand-width of empty perch between them. They face slightly toward each other. <Subject 1> blinks and shifts its weight. <Subject 2> turns its head and takes one small hop closer. Feathers stay the studio colors. No on-screen text, logos, or caption bars.

overall_soundscape:
Quiet furnished room. Soft stereo room tone, a faint distant HVAC hush, one or two tiny claw clicks on wood. No speech, no spoken words, no song with lyrics.

non_diegetic_music:
None.
EOF
)"

./scripts/smoke-test.sh \
  --prompt "$PROMPT" \
  --seed 42 \
  --name smoke-ref2va-5s17 \
  --ref-image "$HOME/h3-data/blue-front.jpg" \
  --ref-image "$HOME/h3-data/blue-side.jpg" \
  --ref-image "$HOME/h3-data/blue-back.jpg" \
  --ref-image "$HOME/h3-data/yellow-front.jpg" \
  --ref-image "$HOME/h3-data/yellow-side.jpg" \
  --ref-image "$HOME/h3-data/yellow-back.jpg"
```

Wait for `OUTPUT /home/xiaohui_chen/h3-output/smoke-ref2va-5s17_00001_.mp4` (SaveVideo suffix; jobs take minutes; poll timeout is already 3600 s). Then:

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
                int_req = urllib.request.Request(
                    "http://127.0.0.1:8188/interrupt",
                    data=b"",
                    method="POST",
                )
                urllib.request.urlopen(int_req, timeout=10).read()
except urllib.error.HTTPError as exc:
    raise SystemExit(exc.read().decode())
PY
```

Expected: HTTP 200 and empty `node_errors` (UNET name is on disk). If `/queue` delete is not supported, the script already `POST`s `/interrupt`. Do not leave a surprise FL2VA job running.

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

Then parent close-out (copy **Parent close-out**). Do not commit the mp4 or the `$HOME/h3-data` JPEGs.

---

### Task 9: Live Ref2VA 15.08 s (both birds)

**Files:**
- None required. Optional: a second line in `measurements/prereq.md` for the 15.08 s wall-clock.

**Interfaces:**
- Consumes: the same running ComfyUI from Task 7 (do **not** rebuild or restart), `workflows/h3-ref2va-long-15s08.json`, the six `$HOME/h3-data/*.jpg` files from Task 8
- Produces: host mp4 `~/h3-output/smoke-ref2va-15s08_00001_.mp4` with 24 fps video + stereo audio

Do **not** restart ComfyUI. If a leftover job holds the GPU:

```bash
curl -fsS -X POST http://127.0.0.1:8188/interrupt
```

Do not start a second ComfyUI. Do not invent a new process. `submit-prompt.py` already polls `/history/<id>` every 2 s with a 3600 s timeout — a 15.08 s job is minutes-to-tens-of-minutes, not a new serving path.

- [ ] **Step 1: Confirm the six cropped stills still exist**

```bash
for f in blue-front blue-side blue-back yellow-front yellow-side yellow-back; do
  test -f "$HOME/h3-data/${f}.jpg"
done
```

If any file is missing, re-run Task 8 Step 1 (crop only). Do not start Task 9 without all six.

- [ ] **Step 2: Live 15.08 s / 362-frame generate**

```bash
PROMPT="$(cat <<'EOF'
subject_definitions:
<Subject 1> is the blue monk parakeet whose appearance comes from <Picture 1> (front), <Picture 2> (side), and <Picture 3> (back): powder-blue wings and tail, silvery-grey face and scalloped breast, horn-colored hooked beak, grey feet. Any printed word Front, Side, or Back at the bottom of those stills is a studio caption, not plumage, not a perch, and must not appear in the video.
<Subject 2> is the yellow monk parakeet whose appearance comes from <Picture 4> (front), <Picture 5> (side), and <Picture 6> (back): bright yellow wings and tail, creamy-yellow face and chest, horn-colored hooked beak, pale feet, a small red leg band. The same printed Front/Side/Back captions are labels only and must not appear.

summary:
A 15.08-second quiet indoor two-shot of both parakeets sharing one pale wooden perch in morning light. Identity is taken from all six stills. No speech and no lyric music.

retention_analysis:
<Subject 1> (whole clip): fully_preserved — keep the blue mutation colors, beak, and body shape from <Picture 1>, <Picture 2>, and <Picture 3>.
<Subject 2> (whole clip): fully_preserved — keep the yellow mutation colors, beak, red band, and body shape from <Picture 4>, <Picture 5>, and <Picture 6>.
Printed captions: not preserved.

detailed_description:
[Shot 1] 0.00-5.00s. Wide-to-medium, eye-level, static then a very slow dolly in. Soft morning side-window light, a plain white wall, one pale wooden perch. <Subject 1> sits on the left, <Subject 2> on the right. Both look around the quiet room. No on-screen text.
[Shot 2] 5.00-10.00s. Hold a closer two-shot. <Subject 1> preens one wing feather. <Subject 2> hops one step toward <Subject 1> and settles. They glance at each other. No fighting, no flight off the perch.
[Shot 3] 10.00-15.08s. Hold the two-shot. Both birds stay on the perch with small natural head turns and blinks, then still. End with both faces visible. No captions.

overall_soundscape:
Quiet furnished room. Soft stereo room tone, occasional claw ticks on wood, a brief feather rustle when <Subject 1> preens. No speech, no spoken words, no song with lyrics.

non_diegetic_music:
None.
EOF
)"

./scripts/submit-prompt.sh workflows/h3-ref2va-long-15s08.json \
  --prompt "$PROMPT" \
  --seed 42 \
  --name smoke-ref2va-15s08 \
  --ref-image "$HOME/h3-data/blue-front.jpg" \
  --ref-image "$HOME/h3-data/blue-side.jpg" \
  --ref-image "$HOME/h3-data/blue-back.jpg" \
  --ref-image "$HOME/h3-data/yellow-front.jpg" \
  --ref-image "$HOME/h3-data/yellow-side.jpg" \
  --ref-image "$HOME/h3-data/yellow-back.jpg"
```

Wait for `OUTPUT /home/xiaohui_chen/h3-output/smoke-ref2va-15s08_00001_.mp4`.

- [ ] **Step 3: Offline mp4 check**

```bash
./scripts/smoke-test.sh --offline-mp4 "$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4"
```

Expected: exit 0, `ffprobe` video stream + `audio,2`. Record wall-clock in `measurements/prereq.md` if you touch that file.

- [ ] **Step 4: Commit measurements only if you wrote them**

```bash
git add measurements/prereq.md
git commit -m "$(cat <<'EOF'
Record the live Ref2VA 15.08 s smoke on this Spark.

EOF
)"
```

If nothing changed in git, do not create an empty commit. Then parent close-out (copy **Parent close-out**). Do not commit the mp4.

---

## Self-review

**Spec coverage**

| Requirement | Task |
|---|---|
| Default start = Ref2VA weights | 1, 5, 7 |
| User can still specify FL2VA | 2 (`--task all`), 4 (graphs kept), 5 (`H3_TASK=fl2va`), 6 (docs), 8 (validation) |
| Variable **1–9** identity stills + `<Picture N>` (smoke uses N=6) | 3 (`--ref-image`, max 9), 4 (nine LoadImage titles on all three graphs), 6 (AGENTS says 1–9), 8–9 (live six-bird recipe) |
| Nested autogrow only | 3 tests + feasibility table |
| No first_frame-as-3view | 6, Global Constraints, Operator amendment C |
| Same canvas / kernels / no NVFP4 / 4-step Ref2VA | 4 lock tests |
| Docker image change | 5, 7 (`test -f` the 15.08 JSON) |
| Live 5.17 s two-bird proof | 8 |
| Live 15.08 s / 362 two-bird proof | **9** |
| AGENTS generate table lists 15.08; old “no third graph” gone | 6 |
| Adversarial fix + push every task | Parent close-out |

**Placeholder scan:** no TBD / “implement later” / “similar to Task 4”.

**Type consistency:** `H3_TASK` is `ref2va|fl2va` at start; `check-weights --task` also allows `all`; downloader defaults to `all`; `--ref-image` uploads to `LoadImage.image` filenames; `ref_images` is `dict[str, [node_id, 0]]`; long graph `length` is int **362**; `--name smoke-ref2va-15s08` → host `smoke-ref2va-15s08_00001_.mp4`.

## Execution handoff

Already chosen — **Subagent-Driven Development, continuous, no human check-in**.

Parent: `superpowers:subagent-driven-development`. Fresh implementer per task on `cursor-grok-4.6-xhigh-fast`, then **Parent close-out** (spec → fixer if needed → adversarial reviewer **and fixer** → re-smoke → `git push -u origin HEAD`). Do not use executing-plans. Do not implement in the parent’s own context. Do not stop between tasks unless BLOCKED.

Plan file: `docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`. Branch: `feat/h3-ref2va-default`. Do not start Task 1 in the same turn as this amendment.
