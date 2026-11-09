# Prompting — write H3's structured prompt, not a one-liner

**Status:** adopted (2026-11-09). Applies to every generate, on the Spark or remote.

H3 was trained on prompts that a rewriter ("H3-Context-IR") turned into a fixed structure. MiniMax's README says: "**H3-Context-IR is critical to the quality of the final output, so we strongly recommend incorporating it into your generation pipeline or following the 'Prompting Guidance' to build your own context-processing system.**" ([MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3)). Context-IR itself is a hosted, paid API. On this box **the agent is the context processor**: it rewrites the user's request into the structure below, then submits that text as the one `prompt`.

Evidence this is the trained format, not a style preference:

- MiniMax's official guides: `VIDEO_PROMPT_WRITING_GUIDE_base_en.md` and `VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` on the [HF model card](https://huggingface.co/MiniMaxAI/MiniMax-H3), mirrored as the `h3-prompt-writing` skill in [MiniMax-AI/MiniMax-H3/skills](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing). Their reproducible 768p request scripts send exactly this structure as `prompt`.
- The ComfyUI H3 tokenizer in this image (`comfy/text_encoders/minimax.py`) registers dedicated tokens from the released tokenizer config: `<d>`, `</d>`, `<|cutoff|>`, `<|lyrics_start|>`, `<|lyrics_end|>`, `<|caption_start|>`, `<|caption_end|>`. It prefixes every attached still with `<Picture N>: ` before the prompt text. Dialogue written as plain quotes never hits the `<d>` tokens.
- Comfy-Org's R2V template note: "Ref2va's output is very sensitive to prompt wording."

A one-line prompt ("A quiet scene. No speech.") leaves timeline, camera, sound, and music to the model's prior. That is where off-prompt motion, random speech, and identity drift come from.

## Rules for every task

0. **Describe what the stills actually show.** When the text and a reference still disagree, H3 follows the text. On 2026-11-09 a prompt that called the cream-faced yellow bird “pale grey” produced a grey-faced bird. Look at every still before writing `subject_definitions`.
1. **One `prompt` string.** H3 is CFG-distilled: no negative prompt, no `guidance_scale`. State the wanted look positively ("a plain white face with no cheek spots") instead of a "negative" list.
2. **English body.** Keep dialogue, lyrics, and visible on-screen text in their original language.
3. **Fill the whole clip.** Timeline length matches the graph `length`: 5.17 / 8.00 / 10.13 / 15.08 s. `[Shot 1]` has no timestamp. Later shots start `[Shot N] At MM:SS.mmm, the camera cuts to …` with strictly increasing times inside the clip. Do not cut just to change distance — use camera motion.
4. **Concrete, observable detail.** Composition, subject look and position, environment and light, actions, camera move, and what is heard. Avoid empty words like "cinematic" or "beautiful" unless they name the style at the start of `[Shot 1]` ("Live-action, cinematic, a medium-wide shot …").
5. **Camera moves** = type + optional amplitude + optional speed, written as a sentence: "The camera pushes in with small amplitude at slow speed toward …". Types: Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll Clockwise/Counterclockwise.
6. **Speech** uses speaker IDs and `<d>` blocks: `The middle-aged baker with a calm, slightly raspy voice (S1) says: <d>[English] First batch of the morning.</d>` Keep the user's words verbatim inside `<d>`. Voiceover: `says in an off-screen voiceover: <d>[English] …</d> while his lips remain completely closed.` No `<d>` block means no intended speech.
7. **On-screen text** goes in double quotes: `A red neon sign reading "OPEN" glows above the door.`
8. **Sound fields are never empty by accident.** `overall_soundscape`: 1–4 sentences of ambience, action sounds, and non-verbal human sounds (no dialogue). Write `N/A` only if the user asked for total silence. `non_diegetic_music`: 1–3 sentences of instrumentation, tempo, and dynamics, or `N/A` for no score. If unwanted speech or music shows up, describe both fields explicitly.
9. **`<Picture N>` is 1-based in attach order.** It must match an attached still. `submit-prompt.py` fails before upload if a tag has no image behind it.
10. **Multi-line prompts go in a file.** Write the prompt to a scratch file and pass `--prompt-file FILE`. Do not fight shell quoting.

## FL2VA graphs (`MiniMaxH3ImageToVideo`): T2VA, I2VA, FL2VA, L2VA

Three fields, in this order, separated by blank lines. Keyframe tasks put one alignment line first.

| Task | Graph | First line |
|---|---|---|
| T2VA (text only) | `h3-fl2va-default-8s.json`, `h3-fl2va-smoke-5s17.json` | none — start with `integrated_multimodal_description:` |
| I2VA (first frame) | `h3-fl2va-keyframes-8s.json` + `--first-frame` | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| FL2VA (first + last) | `h3-fl2va-keyframes-8s.json` + `--first-frame` + `--last-frame` | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.` |
| L2VA (last frame only) | `h3-fl2va-keyframes-8s.json` + `--last-frame` | `How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 8.00-second mark of the target video.` |

Use the graph's real duration with two decimals (`5.17`, `8.00`, `10.13`, `15.08`). Picture numbering follows what is attached: first frame is `<Picture 1>`; last frame is `<Picture 2>` when both are attached, `<Picture 1>` when only the last frame is.

- **I2VA:** anchor the first frame's style, subjects, layout, then the action that starts from it.
- **FL2VA:** prefer one shot. Describe the path from the first to the last state, ending "settles into the pose and composition established by Picture 2".
- **L2VA:** invent a plausible earlier state and converge on `<Picture 1>` at the end.

T2VA with speech (8.00 s, FL2VA 8 steps — the path for dialogue):

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, a medium shot frames a young woman in a navy apron standing behind a wooden café counter in soft morning window light, a chalkboard menu blurred behind her. The camera pushes in with small amplitude at slow speed as she sets down a ceramic cup, looks up at the lens, and smiles. The young woman with a warm, clear voice and an unhurried pace (S1) says: <d>[English] Good morning. The first pot is almost ready.</d> She wipes her hands on the apron. [Shot 2] At 00:05.000, the camera cuts to a close-up of coffee streaming from a glass carafe into the cup, steam curling up through the window light.

overall_soundscape: Low café room tone with the soft clink of ceramic on wood, the rustle of the apron, and coffee pouring into the cup. A distant espresso machine hisses once.

non_diegetic_music: N/A
```

## Ref2VA graphs (`MiniMaxH3ReferenceToVideo`): six sections

Order is fixed: `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`. Labels keep one meaning across all six.

- **`subject_definitions`** — one line per reusable thing. `<Subject N>` is the content (a bird, a person, a room). Identity stills are cited inside the subject: `<Subject 1> is the blue monk parakeet in <Picture 1>, <Picture 2>, and <Picture 3>, with …`. Give a standalone `<Picture N>` line only when the still is a concrete frame or storyboard anchor. List the identity traits that must survive, in positive words.
- **`summary`** — one paragraph that starts with the task tag. Identity stills only: `[reference generation] …`. Do not introduce new labels here.
- **`retention_analysis`** — one line per label: `<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - …`. Markers: `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`.
- **`detailed_description`** — style sentence(s) first, then `[Shot 1] …`. **350–500 words** for a generate. Re-state each subject's key traits where it first appears in a shot. Use `<Subject N> (S1)` when a subject speaks.
- **`overall_soundscape`** / **`non_diegetic_music`** — as above.

Ref2VA Turbo is the 4-step LoRA. It is weak for dialogue (D-06). For speech, use FL2VA 8 steps or the no-Turbo quality graph.

Ref2VA, two birds, 8.00 s (`h3-ref2va-default-8s.json`, six stills: blue front/side/back, then yellow front/side/back):

```text
subject_definitions:
<Subject 1> is the blue monk parakeet in <Picture 1>, <Picture 2>, and <Picture 3>: a stocky Quaker parrot with a white face and forehead, a white breast with faint pale-grey scalloping, pale powder-blue wings and back, a long tapered pale-blue tail, a short hooked peach-colored beak, pink feet, and a plain face with no cheek spots.
<Subject 2> is the yellow monk parakeet in <Picture 4>, <Picture 5>, and <Picture 6>: the same stocky Quaker build with a pale cream-yellow face and breast, bright lemon-yellow wings, back, and long tail, a short hooked peach-colored beak, pink feet, and a plain face with no cheek spots.
<Subject 3> is a weathered wooden backyard perch beside a green hedge in soft overcast daylight.

summary:
[reference generation] <Subject 1> and <Subject 2> sit side by side on <Subject 3>. <Subject 1> preens its wing while <Subject 2> sidesteps closer and the two touch beaks once, in a single continuous shot.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - white face and breast, pale powder-blue wings and tail, peach beak, plain unmarked face.
<Subject 2> (appears in [Shot 1]): fully_preserved - cream-yellow face and breast, bright lemon-yellow wings and tail, peach beak, plain unmarked face.
<Subject 3> (appears in [Shot 1]): partially_preserved - weathered perch and hedge kept; exact framing is new.

detailed_description:
The target video is live-action nature footage with soft, even overcast light, natural colors, and a shallow depth of field.
[Shot 1] A static medium close-up frames <Subject 3>, the weathered wooden perch, running left to right across the lower third, with the green hedge softly out of focus behind it. <Subject 1>, the blue monk parakeet with a white face, a white breast with faint pale-grey scalloping, pale powder-blue wings, and a long pale-blue tail, grips the perch on the left. <Subject 2>, the yellow monk parakeet with a pale cream-yellow face and breast and bright lemon-yellow wings and tail, grips the perch on the right, about a body length away. Both faces stay plain, with no cheek spots and no barred markings on the nape. <Subject 1> turns its head and runs its peach-colored beak along the edge of its blue wing, feathers lifting and settling. <Subject 2> tilts its head, then sidesteps twice along the perch toward <Subject 1>, its yellow tail swinging for balance. The camera pushes in with small amplitude at slow speed, keeping both birds whole in frame from beak to tail tip. Their dark round eyes and short pink legs stay clearly visible against the brown wood. Its claws shift on the grain of the wood and the fine scalloped edges of its white breast feathers catch the flat daylight. Around the midpoint, <Subject 1> stops preening, lowers its wing, and turns to face <Subject 2>. The two birds lean toward each other and touch beaks once, briefly, their peach-colored beaks meeting in the middle of the frame. <Subject 2> then fluffs its cream-yellow breast feathers, shakes out its lemon-yellow wings with a quick flutter, and smooths them back against its body. <Subject 1> bobs its head twice and tucks one foot up under its breast. In the final seconds both birds settle side by side on the perch, the blue and yellow wings almost touching, and look past the camera toward the hedge as a light breeze moves its leaves and ruffles the feathers on their heads. The overcast light stays soft and even, with no harsh shadows, and the focus stays on the two birds until the end of the shot.

overall_soundscape: Soft backyard ambience with a light breeze through the hedge, the scratch of small claws on wood, rustling feathers, and two short, soft chirps when the birds touch beaks. No human voices.

non_diegetic_music: N/A
```

## Species and identity drift

Operator finding (`../measurements/turbo-vs-base.md` §15–16): monk parakeets drift toward a budgerigar-like prior (cheek spots, barred nape, yellow cere). Counter it in **every** section that names the subject — list the true traits positively in `subject_definitions`, `retention_analysis`, and at the first appearance in each shot. That raises the odds; it does not guarantee a lock. Turbo-off (`h3-ref2va-quality-15s08-20step-1344.json`) is still the stronger identity path.

## Quick checklist before submit

- Right graph family: `<Subject N>` sections only on Ref2VA; alignment line only on keyframe graphs; no `<Picture N>` on text-only FL2VA.
- Every `<Picture N>` has an attached still, in order.
- Shot times fit inside the clip; the description fills the whole duration.
- Dialogue (if any) is inside `<d>[Language] …</d>` with a stable `(S1)` ID.
- Both sound fields are written (or `N/A` on purpose).
- Prompt saved to a file and passed with `--prompt-file`.
