---
name: h3-make-video
description: Make a video with MiniMax H3 on the DGX Spark at the highest quality this repo has (the 25-step, no-Turbo Ref2VA graph, ~85 min for 15 s), end to end. Plan and write H3's structured prompt, have a fresh reviewer attack it and fix what it finds, generate, report progress every 10 minutes, review every frame (camera motion vs subject motion included), report the findings, and put the mp4 in the MacBook's ~/Downloads. Use it whenever the user asks to make, generate, render or shoot a video, clip, short or animation (生成视频, 做个视频, 出片, 拍一段), especially with character reference images or three-view sheets, even if they never say "H3", "ComfyUI" or "highest quality", and also to review an existing H3 mp4 frame by frame. Not for requests that ask for speed (quick test, smoke test, draft, Turbo, "just check the server") or name a specific graph; those follow AGENTS.md.
---

# Make a video with H3, highest quality

This skill is the long form of AGENTS.md → **Generate a video**, and every rule there still holds. The main ones:

- never start, restart, or kill ComfyUI unless the user asked;
- never print `/opt/ComfyUI/output`;
- no mp4 in git;
- legal lengths only;
- one prompt, with no negative prompt and no CFG.

The operator made this skill so that full video requests get the max-quality graph by default; AGENTS.md points here for that reason. When the user asks for speed (a test, a draft, "quick", Turbo) or names a graph, follow AGENTS.md instead.

**Composing with other skills.**

- **Style-specific creative skills** (hand-drawn live-action, papercraft, music-video, …): if one also matches, let it shape the creative brief. This skill still does the prompt rules, review, generation, monitoring and delivery.
- **Reviewing an existing mp4:** run Steps 7–8 only.

## Ground rules for commands

- **Shell state does not survive between Bash calls.** A variable you `export` or set in one call is gone in the next. So write **literal values** into every command: the server URL, the job name, file paths, the start time. Keep them on a run card (`WORK/run.md`) and copy from it.
- In this file, `WORK` stands for a new folder for this video inside your scratchpad directory, and `SKILL` for `.claude/skills/h3-make-video`. Substitute the real paths.
- Run commands from the repository root.
- **Server URL:**

  | Where you are | Pass |
  |---|---|
  | Remote (the Mac) | `--base-url http://spark-2a60:8188` to `submit-prompt.sh`, `--url http://spark-2a60:8188` to the watcher |
  | On the Spark | `http://127.0.0.1:8188` (both scripts' default) |

  Drop the `ssh spark-2a60` wrappers below when you are on the Spark.
- **Git:** this skill lives in the repo. The Spark's clone only has it after it is committed, pushed and pulled there. Commit only when the user asks.

Tell the user the time budget, in their language, before you start:

| Phase | Time |
|---|---|
| Prompt, adversarial review, fixes | ~15–25 min |
| Generation, 15.08 s with six ~1.5k px stills on this GB10 | ~85 min |
| Every-frame review and report | ~20 min |

## The pipeline, and when it does not apply

`workflows/h3-ref2va-maxq-15s08-25step-1344.json` (Ref2VA) is the best-quality graph in the repo:

- **Model:** no Turbo LoRA.
- **Sampling:** 25 steps, `res_multistep` with the `beta` scheduler, shifts 12 / 3.
- **Attention:** Sol-Attn off, so every block runs exact Sage 2.2 attention.
- **Output:** 1344×768, 362 frames = 15.08 s.
- **References:** `ref_image_size=max`, so stills keep their own resolution up to a 2048 px short edge and are never upscaled.
- **No** FBC, EasyCache, or SPAN.

Measured: 196.85 s/step, 85.4 min end to end, with six stills. The 25 steps and the `beta` scheduler follow Comfy's R2V guidance; they were not A/B-tested here against 20 steps.

Never edit the shipped JSON. When something must change, copy it to `WORK/graph.json` and edit the copy:

| Need | Change on the copy | Tested here? |
|---|---|---|
| 5.17 / 8.00 / 10.13 s | node `10` `length` → 124 / 192 / 243. Never invent 15.00 or 10.00. | no; fewer frames means faster |
| Vertical (TikTok, Reels, Shorts, phone) | node `10` `width` 768, `height` 1344 | no; same token count as landscape |

Tell the user when you use an untested variant. The clip length in seconds is `length / 24`; use it wherever a step below needs the duration.

**When this pipeline does not fit**, tell the user and route as follows:

- **No identity stills.** This graph needs 1–9. AGENTS.md routes 0 stills to FL2VA. The only tested FL2VA path is the 8-step Turbo graph `workflows/h3-fl2va-default-8s.json`: good, but not this quality. Offer it, or ask the user for reference images. Do not quietly build an untested no-Turbo FL2VA graph. On the FL2VA path, the three-field prompt from `design/prompting.md` applies. The linter handles it, and the watcher works the same way, but expect about 5 min, not 85.
- **The picture is a frame of the shot, not an identity reference.** "Animate this picture", "start or end on this image" are keyframe tasks on `workflows/h3-fl2va-keyframes-8s.json` (8-step Turbo; AGENTS.md §4). Identity stills and keyframes are different graphs. Say it is not the max-quality path.
- **Longer than 15.08 s.** H3 tops out at 15.08 s per clip. Offer several clips that share the same subject definitions and style sentence, each a separate ~85-minute run, cut together afterwards.
- **Dialogue.** Speech has not been measured on this graph. Ref2VA Turbo is weak for speech (D-06). This graph has no Turbo, which should help. Tell the user it is unverified, and follow the speech rules in `references/prompt-guide.md` §10.

**Reference-token budget.** Each still costs `(w/32) × (h/32)` tokens after scaling down to at most a 2048 px short edge, in **every** step. The video itself is 107,856 tokens at 1344×768×362.

| Stills | Reference tokens |
|---|---|
| The six measured stills (~1.4–1.5k × 1.6–2.0k px) | ~15,200 |
| One 2048×2730 still | 5,440 |
| Nine 2048×2730 stills | ~49,000 |

At nine large stills, the total of ~157k tokens sits near the ~160k region where some FP8 attention kernels have produced pure noise (`design/optimizations.md`). Keep the reference total around 30k or less: crop tight to the character, and use about 1.5k px short edges or fewer stills. The time cost per still is moderate (a 4000 px photo versus a 1500 px crop adds ~2–3k tokens, a few percent), but tight crops also keep backgrounds and props out of the identity. The ~85 min figure applies to six ~1.5k px stills.

## Step 0: Preflight

1. **Server.** Check it answers:
   ```bash
   curl -fsS http://spark-2a60:8188/system_stats
   ```
   If it fails, run `ssh spark-2a60 'curl -fsS http://127.0.0.1:8188/system_stats'` to tell "ComfyUI down" apart from "Tailscale path down". If ComfyUI is down, tell the user, and start it only if they ask (AGENTS.md §1).
2. **GPU and queue.**
   ```bash
   ssh spark-2a60 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader; echo ---; docker top deploy-comfyui-1 -eo pid,comm 2>/dev/null | head -5; echo ---; free -g | sed -n 2p'
   curl -fsS http://spark-2a60:8188/queue
   ```
   Compare the GPU PIDs with `docker top`: ComfyUI's PIDs are fine, any other PID is another project. If there is another GPU process, or a job already running or queued, tell the user what you saw and ask whether to wait or go ahead. An 85-minute job that shares the GPU can run out of memory or take much longer. Never stop someone else's process.

## Step 1: Inputs

- **Story beats.** List them in the user's words, numbered, keeping every concrete detail ("one hand on the door frame", "a footprint at every step"). They are the acceptance criteria for the frame review.
- **Defaults.** State them and move on; ask only when the story itself is ambiguous.
  - 15.08 s.
  - Landscape, or vertical if the user mentions TikTok, Reels, Shorts or a phone.
  - No speech unless the user wants lines.
  - A seed: reuse the user's, otherwise pick one and say it.
- **Stills.** Open every image and write down what it shows: which character, which view, colours, details. Then prepare working copies in `WORK/refs/`; the originals stay untouched.
  - **Split** a composite turnaround sheet (front | side | back on one image) into one crop per view. Each crop is its own `<Picture N>`. A whole sheet gets copied as a grid, captions included.
  - **Crop** away printed labels, captions, logos and borders. Text in a still can leak into the video.
  - **Convert and flatten.** Convert HEIC (`sips -s format png IN.heic --out OUT.png` on the Mac). Flatten transparent PNGs onto a plain background, because `LoadImage` keeps only RGB and transparent areas can turn black.
  - **Never upscale.**
  - **Order** them per character (front, side, back). That order is `<Picture N>` and the `--ref-image` order.
- **When the user's words and the stills disagree** (they say "brown bear", the drawing is peach-tan), the prompt follows the stills, and you tell the user. H3 obeys the text over the stills, so a wrong word in the prompt becomes a wrong colour in the video.

## Step 2: Plan, then write the prompt

1. Read `SKILL/references/prompt-guide.md` (content) and `design/prompting.md` (format digest and examples). For anything those do not cover (dialogue crossing a cut, voiceover, environment or style subjects, audio references), read the official guide:
   - `~/.claude/skills/h3-prompt-writing/references/ref-en.txt` (Ref2VA) or `base-en.txt` (FL2VA), if that skill is installed;
   - otherwise `VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` / `_base_en.md` on the [HF model card](https://huggingface.co/MiniMaxAI/MiniMax-H3).
2. Write the shot plan and the state table into `WORK/plan.md`. Write the prompt to `WORK/prompt-v1.txt`.
3. Lint it:
   ```bash
   python3 SKILL/scripts/lint_prompt.py WORK/prompt-v1.txt --duration 15.08 --refs 6
   ```
   Use the real duration and still count. Fix every ERROR. For each WARNING, fix it or note in `plan.md` why it is intended.

## Step 3: Adversarial review (fresh reviewer), then fix

You wrote the prompt, so you read your intent into it. A reviewer that sees only the materials does not.

1. Spawn a fresh subagent (`general-purpose`) with the brief in `SKILL/references/prompt-review.md`, filled in. Give it the materials, not your opinion of the prompt.
2. For every finding, fix it or reject it with a reason. Log the decisions in `WORK/review-v1.md`, save the next version (`prompt-v2.txt`), and lint again.
3. If anything was **Critical**, review the new version once more with a new fresh reviewer (at most two rounds).
4. The prompt you submit is the **latest reviewed version**. Tell the user, in two or three lines, what the review changed.

## Step 4: Generate

1. **Check the queue again** (`curl -fsS http://spark-2a60:8188/queue`). Step 0 was 20 minutes ago.
2. **Get the start time** with a foreground `date +%s`.
3. **Fill in the run card** (`WORK/run.md`):
   - graph path;
   - prompt version;
   - seed;
   - a **new** `--name` for this attempt: short, no `/`, for example `dance-v1`, then `dance-v2` for a revision. The watcher finds the job by it.
   - the start time;
   - the still list in order.
4. **Submit** with `run_in_background`. It blocks until the mp4 exists. Every value is literal:

```bash
./scripts/submit-prompt.sh workflows/h3-ref2va-maxq-15s08-25step-1344.json \
  --base-url http://spark-2a60:8188 --prompt-file /ABS/WORK/prompt-v2.txt --seed 42 --name dance-v1 \
  --ref-image /ABS/WORK/refs/bubu-front.png --ref-image /ABS/WORK/refs/bubu-side.png --ref-image /ABS/WORK/refs/bubu-back.png \
  --ref-image /ABS/WORK/refs/yier-front.png --ref-image /ABS/WORK/refs/yier-side.png --ref-image /ABS/WORK/refs/yier-back.png \
  --timeout 14400
```

A seed does not carry over between graphs or canvas sizes. The same seed with a changed prompt is a different video.

## Step 5: Report progress every 10 minutes

Launch the watcher with `run_in_background`, values literal:

```bash
python3 SKILL/scripts/watch_progress.py --url http://spark-2a60:8188 --name dance-v1 --started 1763020000 --window 600 --wait-queued 180
```

It waits up to `--wait-queued` seconds for the job to appear, because stills upload before the job is queued. Then it watches for `--window` seconds, prints one `STATE …` line, and exits. It exits sooner if the job ends.

Each time it exits:

- **`running` / `queued`:** tell the user in one short line (step k/25, s/step, ETA), then launch it again.
- **`done`:** expect the submit task to finish with `OUTPUT …` within seconds.
- **`unreachable`:** a Tailscale blip is common. Relaunch once or twice before you escalate.
- **`error`, or `missing` after the first window:** stop. Show the user the line and `ssh spark-2a60 'docker logs --tail 60 deploy-comfyui-1'`. Do not resubmit or restart anything without asking.

On this graph, expect about 197 s/step, so a window sees about three steps. Model loading and text encoding at the start, and decoding at the end, produce no step events. More than 20 minutes mid-run with no step at all means it may be stuck: check the logs and tell the user.

**If the submit task exits non-zero while the watcher says `running`:** its connection dropped, but the job lives on the Spark. **Never resubmit**, because that queues a duplicate 85-minute job. Keep watching. When the watcher says `done`, fetch the file (Step 6) and continue.

## Step 6: Put the mp4 in the MacBook's ~/Downloads

Do this before the frame review, so the user can watch while you review.

1. **Find the file name.** Take it from submit's `REMOTE_OUTPUT` / `OUTPUT` lines. If submit died, use the watcher's `done` line, which gives `<name>_0000N_.mp4`; the counter is not always `00001`. Record it on the run card.
2. **On the Mac:**
   1. Pick the target `~/Downloads/<file>`. If that exists with different content, use a `-runN` suffix; never overwrite.
   2. Copy the local `OUTPUT` file. If submit died, run `scp spark-2a60:'~/h3-output/<file>' <target>` instead.
   3. Compare `shasum -a 256 <target>` with `ssh spark-2a60 "sha256sum ~/h3-output/<file>"`.
3. **On the Spark:** you cannot write to the Mac. Give the user `scp spark-2a60:~/h3-output/<file> ~/Downloads/` to run on the Mac.

## Step 7: Review every frame

Read `SKILL/references/frame-review.md` first: the camera-motion trap, the order of reading, and the checklist. Then build the review pack on the Spark (system `python3` has OpenCV and PyAV; CPU only, output only under `/tmp/h3-review/`, as AGENTS.md allows) and copy it back:

```bash
ssh spark-2a60 "python3 - ~/h3-output/<file> /tmp/h3-review/<name>" < SKILL/scripts/review_video.py
scp -q -r spark-2a60:/tmp/h3-review/<name> WORK/review-<name>
```

Read:

- `report.md`;
- **every** overview sheet (`sheets/`);
- **every** detail sheet (`detail/`, a frame every 0.5 s at half resolution);
- each shot's stabilized strip and trail;
- the full-res keyframes, next to the stills.

Write one line per sheet into `WORK/review-notes.md` as you go (`sheet-03: frames 90–119, …`), so the notes prove every sheet was read. A 15.08 s clip has 13 overview and 6 detail sheets.

## Step 8: Report, then stop

Write the report in the user's language with the template in `frame-review.md`:

- verdict;
- per-shot table;
- identity, scene, camera, artifacts;
- audio (measured, not listened to);
- what to change if rerun;
- file locations.

Then ask whether to revise. Do not start another 85-minute run unless the user asks, or asked up front for automatic revisions (then follow their count). Each revision repeats Steps 2–8, with a fresh review and a new `--name`.

## Files

- `scripts/lint_prompt.py`: format checks (sections, shot markers and timestamps, labels, `<d>`, keyframe marks, word count, quoted text). Stdlib only. Exit 1 = errors.
- `scripts/watch_progress.py`: one status line per window. Steps come from the websocket, the end from `/history` + `/queue`. With `--started`, older jobs with the same name are ignored. Needs `websocket-client` (the Spark and this MacBook have it). Exit codes:

  | Exit | Meaning |
  |---|---|
  | 0 | running, queued, or done |
  | 1 | error |
  | 2 | bad arguments (for example an empty `--started`) |
  | 4 | missing |
  | 5 | unreachable |
- `scripts/review_video.py`: overview and detail sheets, cuts (a fast camera move is not counted as a cut), camera motion, stabilized views, keyframes, audio levels, truncation and audio-length flags. Needs OpenCV + PyAV (the Spark).
- `tests/test_scripts.py`: offline lint and watcher tests; the watcher runs against a fake ComfyUI. Run `python3 -m pytest -q .claude/skills/h3-make-video/tests`.
- `tests/test_review_video.py`: synthetic pan, cut and static clips for `review_video.py`. It needs OpenCV, so run it on the Spark (the command is in its docstring); under pytest on the Mac it skips.
