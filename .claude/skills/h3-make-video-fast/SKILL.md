---
name: h3-make-video-fast
description: The DEFAULT way to make a video with MiniMax H3 on the DGX Spark, end to end. Use it whenever the user asks to make, generate, render or shoot a video, clip, short or animation (生成视频, 做个视频, 出片, 拍一段), with or without character reference images or three-view sheets, and also when the video should follow a given piece of music or exact sound effects. It keeps every step of h3-make-video (structured prompt, two fresh adversarial review rounds, progress reports, every-frame review, delivery to the MacBook's ~/Downloads) but renders the max-quality settings on a quarter canvas (672x384, or 384x672 vertical), then enlarges 2x with SPAN and a mild sharpen inside the graph, about 13 minutes for 15 s instead of about 2 hours. Use h3-make-video instead only when the user explicitly asks for the slow or native version (质量高且慢的版本, 慢的版本, 原生分辨率, "the slow version", "native resolution"); 高质量 or "best" alone is not enough. Not for requests that ask for Turbo, a smoke test or a quick draft, or that name a specific graph; those follow AGENTS.md.
---

# Make a video with H3, fast default

**Operator decision (2026-11-17):** every full video request uses this skill. The slow path, `.claude/skills/h3-make-video/` (called SLOW below), is used only when the user explicitly asks for the slow or native version. If they say only "高质量" or "best", stay here and mention the slow option in one line.

**Why it is the default** (measured on this GB10, 2026-11-17, 《布布的天鹅湖》):

| | Fast (this skill) | SLOW |
|---|---|---|
| Canvas | 672x384 or 384x672 rendered; SPAN 2x and `ImageSharpen` give 1344x768 or 768x1344 | 1344x768 or 768x1344 native |
| Reference stills | `ref_image_size=match` (scaled to the canvas area) | `max` (up to a 2048 px short edge) |
| Sampling | identical: no Turbo, 25 steps, `res_multistep` + `beta`, shifts 12 / 3, Sol-Attn off (exact Sage 2.2) | same |
| Time, 15.08 s, six stills | 26.7 s/step, about 12 min sampling + ~1 min load and decode + ~40 s SPAN | 310 s/step, 2 h 12 min |

The user watched both versions and chose the fast one; its composition was also better. What has been measured so far:
- SPAN of a downscaled native frame against the native frame: SSIM 0.981.
- Bear outline sharpness, an index from 0 to ~4:

  | Version | Index |
  |---|---|
  | Native render | 3.52 |
  | Fast render, SPAN only | 3.15 |
  | Fast render, SPAN plus the graph's `ImageSharpen` (alpha 0.1) | 3.60 |

No same-prompt A/B against native has been run yet.

**Everything in AGENTS.md and SLOW still holds:**
- never start, restart or kill ComfyUI unless asked;
- never print `/opt/ComfyUI/output`;
- no mp4 in git;
- legal `17n+5` lengths only;
- one prompt, with no negative prompt and no CFG.

## What to follow

Run SLOW's Steps 0–8 (`.claude/skills/h3-make-video/SKILL.md`) with the values below. SLOW's references and scripts are shared, so do not copy them. `SKILL` in SLOW's commands means `.claude/skills/h3-make-video`.

| Step | Change for the fast path |
|---|---|
| Time budget (tell the user first) | prompt + two reviews ~15–25 min; **generation ~13 min** for 15.08 s with six stills (less with fewer stills or a shorter clip); every-frame review ~15 min |
| 0 Preflight | same |
| 1 Inputs | same: stills are cropped, split and ordered exactly as in SLOW, and `match` scales them down on its own. Vertical when the user mentions TikTok, Reels, Shorts or a phone (the 一二布布 series is vertical). |
| 2 Prompt | same rules: `references/prompt-guide.md`, `design/prompting.md`, lint; long, detailed prompts are fine. Also follow **Keep it sharp** below. |
| 3 Review | same brief (`references/prompt-review.md`), with `<RUN TIME>` set to "~13 minutes". This operator wants **two fresh review rounds every time**, even without a Critical finding. Then tell the user the prompt details in their language and submit **without waiting** for approval. |
| 4 Generate | a copy of a graph below; `--timeout 3600` |
| 5 Progress | same watcher, `--window 600`. Expect about 27 s/step for 15.08 s with six stills, so a window sees about 22 steps. |
| 6 Deliver | same |
| 7 Review every frame | same pack and checklist; the output is 768x1344 or 1344x768 |
| 8 Report | same. A revision costs ~13 min, so offering 2–3 seeds to choose from is reasonable. Still ask before starting another run, unless the user asked for automatic revisions. |

## Graphs

Never edit the shipped JSON. Copy it to `WORK/graph.json` and edit the copy.

| Use | Shipped graph | Out |
|---|---|---|
| Default | `workflows/h3-ref2va-fast-15s08-672-span2x.json` | 1344x768, 15.08 s |
| The video follows a fixed soundtrack (given music, sound effects at exact times) | `workflows/h3-ref2va-fast-locked-audio-15s08-672-span2x.json` | same, with your soundtrack as the audio |

| Change | Default graph | Locked-audio graph |
|---|---|---|
| Vertical 768x1344 | node `10`: `width` 384, `height` 672 | same |
| 5.17 / 8.00 / 10.13 s | node `10` `length` → 124 / 192 / 243 | node `50` `value` → 124 / 192 / 243 (the audio mask follows) |
| Sharpen strength | node `20` `alpha`: 0.1 by default; 0.0 turns it off; 0.2 is crisper but starts to ring on fine textures such as rope | same |

Do not add an `ImageScale` after SPAN. SPAN is exactly 2x, and a fixed size lock would squash a vertical copy. Leave `SaveVideo` at its default encoding: CRF 16 made the file 3x larger with the same outline sharpness (3.58 vs 3.60).

**No identity stills.** These are Ref2VA graphs and need 1–9 stills. With none, follow SLOW's routing (FL2VA, Turbo 8-step) and say so.

**An exact opening frame** (the user gives a scene picture "as the first frame", or a frame the clip must pass through): keep the Ref2VA graph, attach the picture as one more `--ref-image`, and add `MiniMaxH3AddGuide` on that `ref_image_K` LoadImage (`workflows/README.md` § Ref2VA + an exact frame). Tested 2026-11-20 on the locked-audio graph (《无限月读》, 8 stills, two 15.08 s seeds, ~14.4 min each): frame 0 had the picture's composition, regenerated a little darker; the soundtrack stayed locked. Make a 124-frame pilot first when the opening matters (~4–5 min).

**Submit** (remote from the Mac; every value literal, as in SLOW):

```bash
./scripts/submit-prompt.sh /ABS/WORK/graph.json \
  --base-url http://spark-2a60:8188 --prompt-file /ABS/WORK/prompt-v3.txt --seed 42 --name dance-v1 \
  --ref-image /ABS/WORK/refs/bubu-front.png --ref-image /ABS/WORK/refs/bubu-side.png --ref-image /ABS/WORK/refs/bubu-back.png \
  --ref-image /ABS/WORK/refs/yier-front.png --ref-image /ABS/WORK/refs/yier-side.png --ref-image /ABS/WORK/refs/yier-back.png \
  --timeout 3600
```

## Keep it sharp

On 2026-11-17 the user found the upscaled test render a little soft. Measured causes, from largest to smallest:

1. **A low-res render's outlines are softer** than a downscaled native render's. After SPAN the index is 3.15–3.27, against 3.52 native. The graph's `ImageSharpen` (radius 1, sigma 1.0, alpha 0.1) brings it to 3.60, with no visible halo at alpha 0.1. Do not remove it unless the user asks.
2. **Small characters.** In the test, Bubu was 13% of the frame height. At 384x672 his eyes and mouth were a few pixels, and no upscaler can invent that detail. Frame the main characters at about a quarter of the frame height or more ("medium-wide shot", "each bear about a quarter to a third of the frame height"). In the frame review, flag any main face under ~15% of the frame height.
3. **An mp4 in the middle.** Upscaling a CRF-23 mp4 instead of the raw decode cost about 7% in a controlled test (3.79 → 3.51). The shipped graphs upscale the raw decode. Never take a fast render's 384-wide mp4 and upscale it afterwards.

An already-delivered render can be fixed afterwards: sharpen only the luma, leave chroma untouched, and encode at CRF 16. Use `scripts/sharpen_video.py` (Spark, CPU, writes under `/tmp/h3-review/`), then add the audio with `mux_audio.py`. It took 《布布的天鹅湖》's test from 3.10 to 3.52 with a 0.16/255 colour shift. Prefer re-rendering through the shipped graph.

## Longer than 15.08 s

- **Separate shots, cut together:** run several fast clips, each through Steps 1–8. Share the subject definitions and the style sentence, and use a new `--name` per clip.
- **One continuous take:** the only tested chain graphs are SLOW's max-quality 1344 pair, at about 2 hours per segment. A fast chain has not been built or tested. Ask the operator whether to build and smoke-test one, or to use the slow chain.

## Videos that follow a soundtrack (locked audio)

Use this when the user gives music the picture must follow (a dance on the beat), or wants sound effects at exact moments. H3 normally generates its own audio. On this graph the whole soundtrack is VAE-encoded and masked as kept, so H3 only draws the picture, conditioned on that sound.

Measured 2026-11-17 (two 384x672 tests + the final):
- Hops landed on the beat: 20/20, 20/20 and 19/20, with the jump's apex 0.05–0.10 s before each beat.
- A fart reaction landed at 9.42 s for a 9.40 s sound, and a grin started at 10.04 s for a 10.10 s giggle. Without the lock, actions land 1.5–2.5 s late.
- The output audio is the locked track after a VAE round trip (corr 0.8–0.98, lag 0). Replace it with the lossless mix at the end.

1. **Get a WAV.** Convert other formats on the Mac: `afconvert -f WAVE -d LEI16 in.mov WORK/audio/music.wav`. A phone recording may carry hiss. Measure its spectrum before deciding to denoise, and keep anything below ~1 kHz untouched. For sound effects with no music, use a silent WAV of the clip's length as the "music": the effects are then set to an absolute `target_lufs` (default −16).
2. **Sound effects, if any.** Get them from a cheap H3 clip on the default fast graph:
   - 124 frames, the same stills;
   - a prompt that shows the action and its sound, with `non_diegetic_music: N/A`;
   - about 3 minutes.

   Find the events on its audio (envelope, pitch) and confirm each on the frames. Write `WORK/audio/events.json`; the format is in `scripts/prepare_soundtrack.py`, and a relative `wav` path is resolved next to the JSON file. Keep separate events about 0.7 s apart or more: with 0.5 s, the reaction to the first event merged into the second.
3. **Build the soundtrack**, then read its report:
   ```bash
   python3 .claude/skills/h3-make-video-fast/scripts/prepare_soundtrack.py WORK/audio/music.wav \
     --out-dir WORK/audio --name story --frames 362 --auto-start --events WORK/audio/events.json
   ```
   - Outputs: `story-32k.wav`, for `--soundtrack`; and `story-final.wav`, for the finished mp4.
   - Report (stdout; warnings go to stderr): `bpm`, `beats_s`, each effect's gain and mode, the limiter's span, and `changed_regions_s`. Only the effect windows may change the music.
   - Effects default to +6 LU over the music (momentary, BS.1770 K-weighted). The user asked for effects clearly louder than the music; +4 dB by peak RMS measured 4 LU *under* it.
   - The script stops on a silent effect window, a cut shorter than 0.1 s, a gain beyond ±30 dB, or an effect that does not fit inside the clip.
   - The beat finder can pick half or double tempo, and drops beats in passages quieter than −45 dBFS. Check `beats_s` against the music before you write the dance.
4. **Prompt.** Every time in the text must equal the soundtrack:
   - `non_diegetic_music`: instruments, tempo in BPM, when parts enter, the fade at the end;
   - `overall_soundscape`: each effect at its exact second, "clearly louder than the music", then "No other voices are heard";
   - dance: "one hop on each beat, about every 0.6 s";
   - reactions: "exactly as the sound plays".

   Tell the reviewer the audio is locked, and give it the beat list and the event times.
5. **Submit** a copy of the locked-audio graph with `--soundtrack /ABS/WORK/audio/story-32k.wav`. Submit fails before any upload in these cases:
   - the file is not 32 kHz stereo PCM;
   - it is not exactly `round(length/24*40)*800` samples (482,400 for 362 frames);
   - the length is not 17n+5;
   - the graph has no `soundtrack` loader;
   - a locked graph gets no `--soundtrack`.
6. **After the render, put the lossless mix on it.** CPU only on the Spark, writing only under `/tmp/h3-review/` (AGENTS.md allows this). `<file>` is the render's file name as submit printed it, `.mp4` included:
   ```bash
   ssh spark-2a60 'mkdir -p /tmp/h3-review/<name>-mux'
   scp WORK/audio/story-final.wav spark-2a60:/tmp/h3-review/<name>-mux/
   ssh spark-2a60 "python3 - ~/h3-output/<file> /tmp/h3-review/<name>-mux/story-final.wav /tmp/h3-review/<name>-mux/<name>-music.mp4 --expect-locked" < .claude/skills/h3-make-video-fast/scripts/mux_audio.py
   ```
   It must print `MUX_OK`, which means:
   - the WAV is the locked soundtrack (corr ≥ 0.5 with the render's audio; a wrong one measured 0.007);
   - the durations match;
   - the video packets and timestamps are unchanged;
   - the audio has lag 0, corr ≥ 0.99, and a level within 0.5 dB.

   Then `scp` the `-music.mp4` to `~/Downloads` (never overwrite; compare sha256 on both sides). Deliver both the raw render and the `-music` file. To add music to a render that was **not** locked, leave out `--expect-locked`.
7. **Review.** Add these to SLOW's Step 7:
   - beat sync: track the dancer on the frames and pair the apexes with `beats_s`, per beat; a shuffled-grid p-value is weak for very regular motion;
   - each event's visible reaction against its sound time.

**Known limits, measured on 一二布布:**
- A grin held 1.3–1.5 s for a 0.4 s giggle, even with "only a quick flash" in the prompt.
- A puff cloud lasted ~1.8 s against 1 s prompted.

## Files

- `scripts/prepare_soundtrack.py`: cut and fade the music, measure the beats, place sound effects by loudness (relative or absolute), run a −1 dBFS lookahead limiter that ramps in, and write the exact-length 32 kHz track plus the final mix. Needs numpy and scipy (the Mac has them).
- `scripts/mux_audio.py`: replace an mp4's audio without touching the video, then prove it (`MUX_OK`). Needs PyAV (the Spark's system python3). Live-tested 2026-11-17 for four cases: the right WAV, a wrong length, the wrong music, and an unlocked render.
- `scripts/sharpen_video.py`: sharpen the luma of an already-rendered mp4 after the fact (see **Keep it sharp**). Needs PyAV + OpenCV (the Spark).
- `tests/test_prepare_soundtrack.py`: synthetic music and effects, the BS.1770 reference sine, silence handling, and error cases. Run `python3 -m pytest -q .claude/skills/h3-make-video-fast/tests`.
- Shared from SLOW: `lint_prompt.py`, `watch_progress.py`, `review_video.py`, `references/`.
- `scripts/submit-prompt.py --soundtrack`: unit tests are in `tests/unit/test_submit_prompt.py`. The graphs (including SPAN, the sharpen and the audio lock) are locked in `tests/unit/test_workflow_lock.py`.
