---
name: h3-make-video
description: The slow, highest-quality way to make a video with MiniMax H3 on the DGX Spark (the 25-step, no-Turbo Ref2VA graph at native 1344x768 / 768x1344, about 2 h 10 min for 15 s with six stills), end to end. Plan and write H3's structured prompt, have a fresh reviewer attack it and fix what it finds, generate, report progress every 10 minutes, review every frame (camera motion vs subject motion included), report the findings, and put the mp4 in the MacBook's ~/Downloads. Use it ONLY when the user explicitly asks for the slow or native version (质量高且慢的版本、慢的版本、原生分辨率, "the slow version", "native resolution"; 高质量 or "best" alone is not enough), or to review an existing H3 mp4 frame by frame. Every other make-a-video request goes to h3-make-video-fast, the operator's default since 2026-11-17. Not for requests that ask for Turbo, a smoke test or a draft, or name a specific graph; those follow AGENTS.md.
---

# Make a video with H3, highest quality

**Since 2026-11-17 this is the slow path.** The default for full video requests is `.claude/skills/h3-make-video-fast/`: the same settings on a quarter canvas plus SPAN 2x and a mild sharpen, about 13 min instead of about 2 h 10 min. On 一二布布 the operator preferred it to the native render (SPAN of a downscaled native frame vs native: SSIM 0.981; no same-prompt A/B yet). Use this skill when the user asks for the high-quality slow version. The fast skill reuses Steps 0–8 below, so keep them general.

This skill is the long form of AGENTS.md → **Generate a video**, and every rule there still holds. The main ones:

- never start, restart, or kill ComfyUI unless the user asked;
- never print `/opt/ComfyUI/output`;
- no mp4 in git;
- legal lengths only;
- one prompt, with no negative prompt and no CFG.

When the user asks for Turbo, a test, a draft, or names a graph, follow AGENTS.md instead.

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
| Generation, 15.08 s with six ~1.5k px stills on this GB10 | ~2 h 10 min (310 s/step, measured 2026-11-17) |
| Every-frame review and report | ~20 min |

## The pipeline, and when it does not apply

`workflows/h3-ref2va-maxq-15s08-25step-1344.json` (Ref2VA) is the best-quality graph in the repo:

- **Model:** no Turbo LoRA.
- **Sampling:** 25 steps, `res_multistep` with the `beta` scheduler, shifts 12 / 3.
- **Attention:** Sol-Attn off, so every block runs exact Sage 2.2 attention.
- **Output:** 1344×768, 362 frames = 15.08 s.
- **References:** `ref_image_size=max`, so stills keep their own resolution up to a 2048 px short edge and are never upscaled.
- **No** FBC, EasyCache, or SPAN.

Measured: 310 s/step, 2 h 12 min end to end, with six ~1.5k px stills at `max` (《布布的天鹅湖》, 2026-11-17). The older 196.85 s/step / 85.4 min figure was measured before 2026-11-15, when submit sent the stills in a nested dict that ComfyUI silently ignored, so that run had no reference tokens. The 25 steps and the `beta` scheduler follow Comfy's R2V guidance; they were not A/B-tested here against 20 steps.

Never edit the shipped JSON. When something must change, copy it to `WORK/graph.json` and edit the copy:

| Need | Change on the copy | Tested here? |
|---|---|---|
| 5.17 / 8.00 / 10.13 s | node `10` `length` → 124 / 192 / 243. Never invent 15.00 or 10.00. | no; fewer frames means faster |
| Vertical (TikTok, Reels, Shorts, phone) | node `10` `width` 768, `height` 1344 | no; same token count as landscape |

Tell the user when you use an untested variant. The clip length in seconds is `length / 24`; use it wherever a step below needs the duration.

**When this pipeline does not fit**, tell the user and route as follows:

- **No identity stills.** This graph needs 1–9. AGENTS.md routes 0 stills to FL2VA. The only tested FL2VA path is the 8-step Turbo graph `workflows/h3-fl2va-default-8s.json`: good, but not this quality. Offer it, or ask the user for reference images. Do not quietly build an untested no-Turbo FL2VA graph. On the FL2VA path, the three-field prompt from `design/prompting.md` applies. The linter handles it, and the watcher works the same way, but expect about 5 min, not two hours.
- **The picture is a frame of the shot, not an identity reference.** "Animate this picture", "start or end on this image" are keyframe tasks on `workflows/h3-fl2va-keyframes-8s.json` (8-step Turbo; AGENTS.md §4). Identity stills and keyframes are different graphs. Say it is not the max-quality path. Exception: when the clip needs identity stills **and** an exact frame (open on the user's scene picture), add `MiniMaxH3AddGuide` to a copy of this graph instead (`workflows/README.md` § Ref2VA + an exact frame; tested on the fast locked-audio graph 2026-11-20, not yet on this one).
- **Longer than 15.08 s.** H3 tops out at 15.08 s per clip. Offer several clips that share the same subject definitions and style sentence, each a separate ~2-hour run, cut together afterwards. For one continuous take without cuts, chain the clips instead; see **Continuous video across several clips** below.
- **Dialogue.** Speech has not been measured on this graph. Ref2VA Turbo is weak for speech (D-06). This graph has no Turbo, which should help. Tell the user it is unverified, and follow the speech rules in `references/prompt-guide.md` §10.

**Reference-token budget.** Each still costs `(w/32) × (h/32)` tokens after scaling down to at most a 2048 px short edge, in **every** step. The video itself is 107,856 tokens at 1344×768×362.

| Stills | Reference tokens |
|---|---|
| The six measured stills (~1.4–1.5k × 1.6–2.0k px) | ~15,200 |
| One 2048×2730 still | 5,440 |
| Nine 2048×2730 stills | ~49,000 |

At nine large stills, the total of ~157k tokens sits near the ~160k region where some FP8 attention kernels have produced pure noise (`design/optimizations.md`). Keep the reference total around 30k or less: crop tight to the character, and use about 1.5k px short edges or fewer stills. The time cost per still is moderate (a 4000 px photo versus a 1500 px crop adds ~2–3k tokens, a few percent), but tight crops also keep backgrounds and props out of the identity. The ~2 h 10 min figure applies to six ~1.5k px stills.

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
   Compare the GPU PIDs with `docker top`: ComfyUI's PIDs are fine, any other PID is another project. If there is another GPU process, or a job already running or queued, tell the user what you saw and ask whether to wait or go ahead. A two-hour job that shares the GPU can run out of memory or take much longer. Never stop someone else's process.

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

On this graph, expect about 310 s/step with six stills, so a window sees about two steps. Model loading and text encoding at the start, and decoding at the end, produce no step events. More than 20 minutes mid-run with no step at all means it may be stuck: check the logs and tell the user.

**If the submit task exits non-zero while the watcher says `running`:** its connection dropped, but the job lives on the Spark. **Never resubmit**, because that queues a duplicate two-hour job. Keep watching. When the watcher says `done`, fetch the file (Step 6) and continue.

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

Then ask whether to revise. Do not start another two-hour run unless the user asks, or asked up front for automatic revisions (then follow their count). Each revision repeats Steps 2–8, with a fresh review and a new `--name`.

## Continuous video across several clips (Masked AV chain)

Use this when the user wants **one continuous take** longer than one clip (for example TikTok's over-60-second rule), or asks for clips that join without a cut. A single clip still follows Steps 0–8 unchanged. Separate shots that are simply cut together need none of this: make each one as a single clip.

**How it works.**

- **Graphs:** `workflows/h3-ref2va-maxq-chain-start-1344.json` makes segment 1, and `workflows/h3-ref2va-maxq-chain-continue-1344.json` makes every later segment. Both have the max-quality settings above, and both also save the sampled latents (`<name>-latent-video_00001_.latent` and `<name>-latent-audio_00001_.latent` in the Spark's `~/h3-output`).
- **The continuation:** the continue graph copies the previous segment's last **39 frames** into its own first 39 frames. That is 12 video latent slots plus 65 audio ticks, which is 1.625 s of picture and sound. It then locks them with H3's native per-stream denoise masks (ComfyUI PR #15375, included in our pin). The model generates everything after them. The picture, the motion and the music therefore continue across the joint, with no re-encode in between.
- **Length:** set it on node `50` (`value`), not on node `10`. Every later segment adds `length − 39` new frames:

  | Segment length | New frames per later segment |
  |---|---|
  | 192 (8.00 s) | 153 (6.375 s) |
  | 243 (10.13 s) | 204 (8.50 s) |
  | 362 (15.08 s) | 323 (13.46 s) |

  Example: 4 × 362 + 1 × 243 = 1535 frames = 63.96 s.
- **Keep these identical across a chain:** canvas, graph family, stills, and their order. The latent shapes must match. Use the same seed unless the user asks otherwise.

**Measured on this box (2026-11-15, smoke tests at 384×384):**

- The locked head re-decodes almost identically: mean difference 1.9–4.5 of 255. The audio head matches the previous tail to 11–19 dB below the signal level.
- With a generic prompt and 6 steps, the newly generated part changed the colour grade at the joint (ΔE 24.8, saturation −43 %).
- With 20 steps and the **same explicit scene description in both prompts**, the joint was invisible: ΔE 0.24, luma +0.3 %, saturation −0.5 %.
- Rule that follows: the locked frames carry motion, but the prompt must carry the look.

**Measured on the first real chain (《滚球》, 2 × 8.00 s, 768×1344, maxq, 2026-11-15):**

- **Render time:** 30:45 for segment 1 and 32:34 for segment 2. That is 69.7 vs 74.0 s/step, so the masks add about 6 %.
- **Picture across the joint:**
  - Overlap re-decode difference 1.8/255.
  - Colour ΔE 0.44.
  - Frame change at the joint 0.34, against a 0.39 median. Motion before and after the joint was 0.93 and 1.20, so there was no freeze. The ball kept rolling straight through it.
  - The seam-ratio column showed 4.77, but the cause was a jump that segment 1 already had at its own VAE group boundary (frame 188). Single clips have these jumps too.
- **Identity:** both bears stayed on-model across the joint, with no bow-tie bleed.
- **Drift:** on the static background, sharpness (Laplacian variance) rose about 30 % over the first 2–4 s after the joint, then held. The carpet went from 320 to 423. Side by side the change is subtle: a crisper carpet pile. This matches Continuum issue #13 after a single joint, so expect it to compound over many joints.
- **Audio:** continuous, with no click (step ratio 0.12). Two defects:
  - Segment 1's music tapered in its last ~0.2 s even though the prompt said "without ending". That taper is inside the locked latent, so a 0.2 s lull sits at the joint.
  - The generated music was ~7 dB quieter (beat peaks −18.7 vs −11.3 dBFS). `stitch_segments.py` now matches the level by default: +5.4 dB here, with 0.085 % of samples soft-limited.
- **Ideas, untested:**
  - End the locked context ~0.7 s before a segment's end (a "safe handover") to skip the end-of-clip taper.
  - Write the music level explicitly ("as loud as before, beat peaks strong") in the continuation prompt.

**Steps.**

1. **Plan the whole story by segment.** Give each segment its own beats table. Put each joint inside an action, ideally a continuous motion such as a walk, a roll or a pour. A joint during a frozen pose hides problems, and a joint at an action's start invites a stutter. Tell the user the total time: a segment costs as much as a single clip of the same length.
2. **Segment 1** = Steps 1–7 on a copy of the chain-start graph, named `--name <story>-s1`.
   - The prompt ends mid-action.
   - The music is "still playing at the last frame, without slowing down or ending".
   - Submit prints two `LATENT …` lines; record them on the run card.
3. **Read segment 1's last 1.625 s before you write anything for segment 2.** Those frames (`length − 39` to `length − 1`) get locked into segment 2 exactly as rendered, picture and sound.
   - Write down the state at the **first** locked frame and at the **last** one: positions, facing, poses, arms, objects and their motion (where they are, which way they move, how fast), expressions, light, real bear sizes (measured, not guessed), and what the music is doing.
   - Note what changes between the two. In 《滚球》 2026-11-15 the ball was mid-gap at the first locked frame and at the bear's foot by the last.
   - The plan's intended end state does not count. Beats land early or late, so the real end state often differs from it.
   - If segment 1 is wrong, stop and ask the user whether to redo it. Every later segment inherits it.
4. **Segment k+1 prompt.**
   - Copy `subject_definitions`, the style sentence and the light sentence **verbatim** from segment 1.
   - Describe the room or scene **as rendered** (objects segment 1 added, the real light).
   - "From the first frame …" means the **first** locked frame, not the last.
   - **No new beat before 1.625 s.** Describe what the locked frames already do, at the times they do it, and continue what is already moving.
     - [observed] A first draft for 《滚球》 stopped the ball at 0.6 s. The locked frames had it still rolling at 1.6 s. The reviewer rated it Critical, because the model would fix the contradiction with a jump right at the joint.
   - Keep music and ambience the same instruments and tempo, and let only the last segment end the music.
   - Run the two review rounds. Give the reviewer the locked window's sheets and the last-frame keyframe, and say that the first 1.625 s are fixed, audio included.
5. **Submit** a copy of the chain-continue graph (same canvas, same node `50` value or another legal length) with `--continue-from <previous --name>`. The flag fails before upload when the graph and the flag do not match. The server fails closed if the latent file is missing.
6. **Review segment k+1** with Step 7, as a single clip.
7. **Stitch and measure on the Spark.** This step is CPU only and writes only under `/tmp/h3-review/`:
   ```bash
   ssh spark-2a60 "python3 - /tmp/h3-review/<story>-chain <story>-chain ~/h3-output/<story>-s1_00001_.mp4 ~/h3-output/<story>-s2_00001_.mp4" < SKILL/scripts/stitch_segments.py
   scp -q -r spark-2a60:/tmp/h3-review/<story>-chain WORK/
   ```
   1. Read `report.md`, every `seam-K.jpg` (stitched frames around each joint) and every `overlap-K.jpg` (segment k's tail next to segment k+1's head).
   2. Check each seam against these thresholds (all from the smoke tests above):

      | Check | Seamless |
      |---|---|
      | Overlap MAE | below about 6 |
      | ΔE | below 2 |
      | Motion after the joint | about the same as before it (much lower means a freeze) |
      | Seam ratio | below about 2; judge it on the sheet when motion is small, because the ratio of two small numbers is noisy |
      | Audio overlap difference | at least 10 dB below the level |
      | Audio step ratio | not far above the clip's normal steps |

   3. Run Step 7 on the stitched mp4 as well (`/tmp/h3-review/<story>-chain/<story>-chain.mp4`).
8. **Deliver** each segment and the stitched mp4 to `~/Downloads` (Step 6; the stitched file comes from `/tmp/h3-review/…` by `scp`). Report per segment, then per seam, then the chain as a whole: identity in the first vs the last segment, and drift.

**Limits.**

- **Drift accumulates over many joints.** In ComfyUI-H3-Continuum issue #13, contrast and sharpness rise chunk by chunk, and it has no fix there. Prefer fewer, longer segments. Cut to a new scene every 2–3 segments: a cut restarts from the stills, while a joint inherits the previous frames.
- **A/V offset:** a segment length whose audio is not a whole number of ticks (`length × 40 / 24`) shifts the audio by up to ±8 ms per joint. That applies to 362 and 124; 192 and 243 are exact. The stitch report prints the offset.

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
- `scripts/stitch_segments.py`: stitches Masked AV chain segments and measures each seam. It drops each later segment's locked head. The picture switches at the end of the overlap with a 4-frame crossfade. The sound switches in the middle of the overlap with a 15 ms crossfade, because a segment's last ~0.2 s of audio carry the decoder's fade, measured at −36 dBFS on 2026-11-15. Both switch points are flags. The audio is aligned on latent ticks. It reports overlap re-decode difference, seam ratio, colour ΔE, motion before and after the joint, audio levels, steps and overlap difference, and per-segment drift. It writes `seam-K.jpg` and `overlap-K.jpg`. Needs OpenCV + PyAV (the Spark).
- `tests/test_scripts.py`: offline lint and watcher tests; the watcher runs against a fake ComfyUI. Run `python3 -m pytest -q .claude/skills/h3-make-video/tests`.
- `tests/test_review_video.py`: synthetic pan, cut and static clips for `review_video.py`. It needs OpenCV, so run it on the Spark (the command is in its docstring); under pytest on the Mac it skips.
