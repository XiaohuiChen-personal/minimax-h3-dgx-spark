# Reviewing every frame

The review checks the video against two things: the user's beats (Step 1) and the stills. Every claim in the report rests on frames you looked at, cited by frame number.

## 1. Read the pack in this order

1. **`report.md`**: frame count and length, cuts, the shot list, the measured camera motion per shot, flags, and audio levels.
2. **Every overview sheet (`sheets/`)**, in order, with no sampling: 30 frames per sheet, so 13 sheets for a 15.08 s clip. Each thumbnail shows:
   - the frame number and time;
   - `bg`: how far the background slid since the previous frame, as a percent of the width or height. Negative x means it slid left, so the camera moved right;
   - `z`: the zoom factor.

   These sheets show continuity, motion and cuts. Thumbnails are about a quarter of the full width, too small for faces or fine artifacts.
3. **Every detail sheet (`detail/`)**: one frame every 0.5 s at half resolution, six per sheet. Use these for identity, faces, hands and artifacts.
4. **`stabilized/shotK-strip.jpg` and `shotK-trail.jpg`** for every shot. The camera motion is undone, so the background holds still:
   - **strip:** six moments stacked;
   - **trail:** the same moments on one clean background, so whatever moved through the scene appears at each position it passed.

   Yellow outlines show where the camera was looking. Before trusting a stabilized view, check that static landmarks line up across the strip rows (roof edges, door frames, trees). If they swim, the estimate failed for that shot; judge it by eye.
5. **`keyframes/`**: the first, middle and last frame of each shot at full resolution. Compare them with the stills. For anything small or suspicious, pull full-res frames:
   ```bash
   ssh spark-2a60 "python3 - ~/h3-output/<file> /tmp/h3-review/<name> --dump 120,180 --crop 300,100,1100,700" < SKILL/scripts/review_video.py
   scp -q -r spark-2a60:/tmp/h3-review/<name>/dump WORK/review-<name>/
   ```

Write one line per sheet into `WORK/review-notes.md` as you read: frames covered, what you saw, defects with frame numbers. The report may say "no artifacts found" only after every overview and detail sheet has a line.

**Confirm every cut on the sheets.**

- A real cut with no `CUT` label (two similar shots, a dissolve) means the camera numbers and stabilized views for that shot span two shots. Rerun the pack with a lower `--cut` (for example `--cut 15`) and ignore that shot's measured camera until then.
- A `CUT` label where nothing cut (a flash, a whip pan) splits a shot. Say so in the report.

## 2. Camera vs subject: read this before judging any motion

**What went wrong before.** Reviewing the snowy-courtyard clip, I reported that Bubu "barely moves" in shot 1. He walked about 30% of the frame width toward the gate. The camera tracked left with him, so on screen he stayed nearly in place while the hall slid away to the right. The shot-1 trail image shows the walk at a glance: five Bubus in a row across the courtyard.

**Rules:**

- **Decide what the camera does first.** Use the report's camera line, background landmarks across the sheets, and the yellow footprints in the trail.
- **Judge every subject against the scene, not the frame edges.**
  - Same screen spot, background sliding: travelling (a tracking shot).
  - Drifting across the frame along with the background: standing still (a pan).
  - Growing on screen: first take out the measured zoom. A subject that grows only as much as the background does is the camera pushing in. A subject that grows faster is approaching. Both can happen at once.
- **Any motion claim needs two independent cues**, both "X walked to the gate" and "X did not move". One trail image is not enough on its own. The cues:
  - the stabilized trail;
  - changing distance to a landmark;
  - marks left behind (footprints, wakes);
  - a walking or limb cycle;
  - parallax between near and far objects.
- **Know the illusions the tools can create or miss:**
  - **Parallax.** The estimate is one flat transform. In a truck or arc shot, near objects slide against far ones, so in the stabilized view a motionless foreground subject can look as if it travels. Check its feet against the ground right next to it.
  - **Foot-sliding (skating).** The body travels but the feet do not plant: the legs barely move, or the prints do not match the steps. That is a defect, even though the trail shows travel.
  - **Arc shots** rotate the view around a subject. It can look as if the subject turned when the camera did. Check the background behind the subject.
  - **Coverage is not correctness.** "Measured on 100% of frame pairs" means a transform was found, not that it is the background's. When a subject fills most of the frame, or snow, rain or sparkles dominate, the estimate may follow the wrong thing. Trust aligned landmarks over the number.
- **Report the camera for every shot, as measured and seen, next to what the prompt asked for.** A mismatch is a finding.

## 3. What to check, shot by shot

- **Beats.** For each beat in the prompt: seen, partly, or missing, with the frame range, and when it happens compared with the prompt's timestamps. Cuts may land a few tenths of a second off: in the snowy-courtyard run, cuts prompted at 6.00 s and 10.00 s came at 5.71 s and 10.04 s. That is normal. A missing or extra cut is a finding.
- **Identity**, for each character in every view that appears (front, side, back): proportions, colours, outlines, face features, hair, ears and tail, clothing, accessories. Look for added features (eyebrows, clothes, marks), missing ones, and drift within a shot. Use the detail sheets and keyframes, not thumbnails.
- **Scene.** Layout, light, weather and props. Across cuts: screen direction, positions, object states (check the plan's state table).
- **Camera.** As measured and seen, against what the prompt asked for.
- **Artifacts.** Morphing, extra or missing limbs or fingers, melting outlines, foot-sliding, flicker, frozen frames, sudden colour shifts, garbled or unwanted text, tile seams, jumps at cuts.
- **Audio.** Report only what was measured: the stream exists, its length, levels per shot, quiet stretches, the loudest moments (footsteps, impacts and beats often show there). Say you did not listen; the user will.

## 4. Report template

Translate the headings into the user's language.

```text
Verdict: one or two sentences: usable or not, the biggest strength, the biggest problem.

Per shot:
| Shot | Time | The prompt asked for | The video shows | Camera (measured / seen) | Problems (frame #) |

Characters: per character, how closely each view matches its stills; any drift, with frame numbers.
Scene: layout, light, continuity across cuts.
Artifacts: list with frame numbers, or "none found in 13 overview + 6 detail sheets".
Audio (measured, not listened to): stream, length, levels, quiet or loud moments.
If we rerun: concrete prompt changes, each tied to a defect above.
Files: ~/Downloads/<file> (MacBook); server copy spark-2a60:~/h3-output/<file>
```

Mark uncertain observations as uncertain, and give frame numbers for every claim. Do not claim more than the frames show.
