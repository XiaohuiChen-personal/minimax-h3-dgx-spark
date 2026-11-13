# What to write so an 85-minute run lands

The format rules are in `design/prompting.md`: section order, timestamps, labels, speech blocks, examples. That file is a digest. The full official guides are `ref-en.txt` (Ref2VA) and `base-en.txt` (FL2VA). Both live in the `h3-prompt-writing` skill (`~/.claude/skills/h3-prompt-writing/references/`) and on the [HF model card](https://huggingface.co/MiniMaxAI/MiniMax-H3). This file covers **content**: the choices that decide whether the video matches the request.

Evidence tags:

| Tag | Means |
|---|---|
| **[official]** | In MiniMax's guides. |
| **[observed]** | Seen in a run on this box. The cause, if one is given, may be an inference. |
| **[recommended]** | Judgement. Not yet measured. |

Most observations come from one max-quality run, the snowy-courtyard clip with two cartoon bears. Generalise with care. The rules below are written for any subject, live action or animation.

## 1. Plan before you write prose

Write two small tables into `WORK/plan.md`.

**Shot plan:**

| Shot | Time | Framing and camera | Who is in frame | Starts with | Ends with | Sounds |
|---|---|---|---|---|---|---|

**State table:** every object or condition that changes, with its value at the start and end of each shot. Examples: a door open or shut, food bitten or whole, a candle lit or out, lights on or off, who holds what, where each character stands and which way they face.

Then check that every shot starts where the previous one ended: positions, facing, object states, light. A story that breaks its own physics cannot be drawn consistently. For example, a bun bitten in shot 2 cannot become two clean halves in shot 3. **[recommended; the user caught that one while planning]**

How many shots:

- A 15 s clip usually has 1–4 shots.
- Cut only when the new shot brings new information: a new subject, place, state, viewpoint or time. To change framing distance, move the camera instead of cutting. **[official]**
- Leave at least ~1.5 s after the last cut. The linter flags shorter shots. **[recommended]**

## 2. Describe what the stills show, and keep saying it

- **Look at each still before you describe it.** When the text and a still disagree, H3 follows the text. A prompt that called a cream-faced bird "pale grey" produced a grey-faced bird. **[observed 2026-11-09]**
- **List traits in a fixed order:**
  1. build and proportions;
  2. exact colours ("peach-tan", not "brown", if peach-tan is what is drawn);
  3. outline or rendering style;
  4. which face features exist;
  5. hair, ears, tail, clothing, accessories;
  6. details only visible from the side or back;
  7. what is absent, said positively ("wears no clothing", "plain peach-tan feet like the rest of him").
- **Name which still shows which view:** `<Subject 1> is … in <Picture 1> (front view), <Picture 2> (side view), and <Picture 3> (back view)`.
- **Repeat the 3–5 most distinctive traits** at the subject's first appearance in every shot, and in `retention_analysis`.
  - Identity drifts toward the model's prior for the species or genre. **[observed: monk parakeets drifted toward budgerigar features; `measurements/turbo-vs-base.md` §15–16]**
  - Repeating the true traits is the counter-measure. **[recommended: raises the odds, not proven to lock]**
- **Express emotion with the face the character actually has.**
  - For dot eyes and a tiny mouth: "its small dot eyes look downcast and its ω mouth flattens into a small downturned curve".
  - In the snowy-courtyard run, the white bear's worried look came out with **added eyebrows**, though the expression used only its own features. **[observed]**
  - Its definition did not say what the face consists of. For every character whose expression changes, add "its face has only the dot eyes, the tiny mouth, and the cheek blushes" (adapted to the design). **[recommended: untested]**

## 3. Style and light come first

Write one or two sentences before `[Shot 1]`: the medium that matches the stills, and the scene drawn in that same medium. **[official]**

> The target video is a 2D hand-drawn cartoon animation in the same flat style as the reference character art, with clean thick outlines and flat colors, and the snowy courtyard is drawn in the same soft 2D style.

When the scene is dark (night, candlelight, a cave), say how the characters stay readable:

> It is night, but the snow glows bright under moonlight, and both bears keep their exact flat reference colors, evenly lit and clearly readable. **[observed: the bears stayed readable and on-model]**

## 4. Space, direction, eyelines, head count

- **Fix the layout once in shot 1** (what is on the left, right and in the back), then keep it. **[recommended]**
- **In side-on shots, keep screen direction:** a character heading for a gate on the left walks right-to-left in every lateral shot of that walk (the 180° rule). A shot from behind, walking into depth toward the gate, is fine; the snowy-courtyard shot 3 did exactly that and came out well. **[observed]**
- **Give the direction of every look at someone off-screen**, naming them by their true traits: "looks toward frame left, where the peach-tan bear stands off-screen".
- **State who is in frame:** "Only one bear is in this shot." Otherwise the model may add the other character. **[recommended]**

## 5. Subject motion and camera motion: separately, then how they relate

- **The subject:** the action, its direction, its pace, and a time anchor inside the shot. "About two seconds into the shot he stops and turns his head to the right."
- **The camera:** type, plus amplitude and speed when they matter, written as a sentence. **[official]**
  > The camera pushes in with small amplitude at slow speed toward the doorway.
  - Types: Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake, POV, Roll.
  - Keep one main move per shot. **[recommended]**
- **The relation:** when the camera follows a moving subject, say so.
  - "The camera tracks left at slow speed alongside him" produced a real tracked walk across the courtyard. **[observed]**
  - Adding what the frame will look like ("…so he stays mid-frame while the courtyard slides past to the right") tells the model and the frame reviewer the same thing. **[recommended]**
- **Close off cheaper look-alikes.** Some actions have a cheaper version that is easier to draw.
  - "Turns his head and body to look back toward the hall at frame right" came out as the bear turning to face the camera. **[observed]**
  - Pin the head direction to the frame and to the target: "turns his head to the right, toward the hall, so his face points right, away from the gate". **[recommended: untested]**

## 6. Contact and hands

- **Hands that must stay put get a held state, not a motion verb.**
  - "Stands right against the door frame and lifts one short stubby arm to rest on its edge" came out as a **wave**. **[observed]** The verb "lifts" is the likely cue. **[inference]**
  - Write the state and its duration instead: "rests one short stubby arm flat against the red wooden post, holding it; the arm stays on the post for the whole shot". **[recommended: untested]**
- **Small or stubby hands hold objects that are big and held in both hands.** Avoid thin tools (chopsticks, strings, pens, needles) unless the story needs them. **[recommended]**

## 7. Expression timing

- When it was written without a time, the worried look appeared only about three seconds into a four-second shot. **[observed]**
- If an emotion should read for the whole shot, put it at the first frame: "From the first frame, <Subject 2> looks worried …". **[recommended: untested]**

## 8. Write the result of every physical event

The model does not reliably infer consequences. Write them out:

> the cake is squashed flat between them, cream smears over both bears' bellies, the candle tips over and goes out with a thin curl of smoke

Then check what follows from that result: a candle going out in a dark room means darkness, so keep the room lights on. **[recommended]**

## 9. Text on screen

- **Visible text goes in double quotes,** verbatim, in its own language: `A red neon sign reading "营业中" glows above the doorway.` **[official]**
- **The reverse is a risk, not a certainty.** Quoting a word that is not meant to be visible tells H3 it may be on-screen text. The snowy-courtyard prompt quoted `"ω"` twice and no ω appeared on screen. Still, write symbols without quotes ("an ω-shaped mouth"). **[recommended]**
- **Titles and captions are added after generation**, not in the prompt.

## 10. Sound and speech

- **`overall_soundscape`:** 1–4 sentences, one paragraph. Ambience, the physical sounds of the visible actions, and non-verbal human sounds (breathing, laughter). No dialogue, singing, or diegetic music; those go in the description. Write `N/A` only for total silence. **[official]**
- **`non_diegetic_music`:** 1–3 sentences of instruments, tempo, rhythm and dynamics. No mood words. `N/A` for no score. **[official]** Music the characters can hear (a radio, a band in the room) is diegetic and belongs in the description. **[official]**
- **No speech:** write no `<d>` blocks, and say "No voices are heard" in the soundscape. Random speech is a known failure when sound is left unspecified. **[recommended]**
- **Speech** **[official]**:
  - Give each speaker a stable ID: `(S1)`, `(S2)`, or `(S1,S2)` together. In Ref2VA, write `<Subject N> (S1)`.
  - At the first line, describe the voice outside `<d>`: who, roughly age and gender, on- or off-screen, pitch, timbre, pace, accent.
  - Inside `<d>`, put only the language tag and the exact words, in the language the user gave them: `<d>[Chinese] 等我回来。</d>`. Never translate.
  - After a line, say the mouth closes: "She closes her lips and smiles."
  - Voiceover uses the exact phrase `says in an off-screen voiceover: <d>[…] …</d>`, followed by "while his lips remain completely closed".
  - A line that crosses a cut uses `<scenetrans>` on both sides, plus "continues seamlessly across the cut". A line cut off by the end of the clip uses `<cutoff>`.
  - Examples with people and dialogue: the café example in `design/prompting.md`, and the sitcom example in `ref-en.txt` §7.
- **Music-driven videos (dances):** give the tempo in words ("a brisk, steady drum-and-xylophone beat"), and tie the moves to it in the description ("each pose lands on a beat"). **[recommended, untested]**

## 11. Length

- `detailed_description` should be **350–500 words** for a generation. The linter counts plain words and leaves out labels. **[official]**
- Dialogue-heavy clips fit the spoken timeline first. **[official]**
- Spend the words where the beats are. Adjective padding does not help.

## 12. Skeleton: 15.08 s, two characters, three shots

This shape fits animated characters. For live action and people, adapt it with the official examples named in §10.

```text
subject_definitions:
<Subject 1> is NAME, the … in <Picture 1> (front view), <Picture 2> (side view), and <Picture 3> (back view): BUILD; COLOURS; OUTLINE/RENDERING; FACE (only these features); HAIR/EARS/TAIL/CLOTHING; BACK-VIEW DETAILS; ABSENT THINGS said positively.
<Subject 2> is NAME, the … in <Picture 4> (front view), <Picture 5> (side view), and <Picture 6> (back view): …

summary:
[reference generation] One paragraph: who does what where, in shot order, using only the labels above.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - the traits that must survive; new actions are new.
<Subject 2> (appears in [Shot 2]): fully_preserved - …

detailed_description:
STYLE SENTENCE. LIGHT / READABILITY SENTENCE.
[Shot 1] FRAMING + LAYOUT (left / right / back). <Subject 1>, KEY TRAITS, POSITION, ACTION with direction and a time anchor. CAMERA sentence + how it relates to the subject. SOUND of the action.
[Shot 2] At 00:05.500, the camera cuts to FRAMING. <Subject 2>, KEY TRAITS … EXPRESSION from the first frame … CONTACT as a held state … WHO IS IN FRAME. CAMERA.
[Shot 3] At 00:10.000, the camera cuts to … END STATE in the final frame.

overall_soundscape:
AMBIENCE + ACTION SOUNDS. No voices are heard.

non_diegetic_music:
INSTRUMENTS, TEMPO, DYNAMICS (or N/A).
```

## 13. Self-check before the review

- Every user beat is present, in order, at a time that leaves room to perform it.
- Every trait was checked against a still, not against memory or the user's wording.
- The state table holds across every cut.
- Each shot has one camera sentence, and says how the camera relates to any moving subject.
- Speech is either absent on purpose ("No voices are heard") or fully formatted.
- `lint_prompt.py` shows no errors, and every warning is understood.
