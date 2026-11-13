# Adversarial prompt review

The author of a prompt reads their intent into it. A fresh reviewer sees only what is written, which is what H3 sees. Spawn one (Agent tool, `general-purpose`) with the brief below. Fill in the angle brackets.

Hand over the materials, not your conclusions. Do not tell the reviewer which parts you are unsure about. Do not tell it the prompt is "nearly done".

## Brief to paste

```text
You are reviewing a prompt for MiniMax H3, a video model that renders a <DURATION> s clip at 1344x768
(or <CANVAS>) from ONE structured English prompt plus identity stills. Facts about the model that matter
for the review:
- When the text and a still disagree, it follows the text (observed).
- Visible on-screen text is written in double quotes (official), so quoting a word that should NOT
  be visible is a risk.
- There is no negative prompt and no CFG. Short positive statements of absence are intended and
  are not defects: "wears no clothing", "its face has only ...", "Only one bear is in this shot",
  "No voices are heard" (without the last one, random speech is a known failure). A long list of
  visual objects the prompt does not want ("no lanterns, no plaque, no ...") is the risky case:
  flag it as a possible plant (unmeasured).
- One run costs about 85 minutes, so every real problem you find now saves a run.
Be adversarial: assume the prompt is wrong somewhere and find where. Do not rewrite the prompt.

Materials (open every file):
- The user's request, verbatim: <PASTE>
- Identity stills, in <Picture N> order: 1 = <PATH> (<character>, <view>), 2 = <PATH> (...), ...
- The prompt: <PATH>
- Format rules: <REPO>/design/prompting.md (digest); full official guide:
  ~/.claude/skills/h3-prompt-writing/references/ref-en.txt (or base-en.txt for FL2VA)
- Content rules: <REPO>/.claude/skills/h3-make-video/references/prompt-guide.md
- Linter output: <PASTE>

Check, in this order:
1. Request fidelity. Every beat and every concrete detail the user asked for is present, in order, at a
   time that leaves room to perform it. Nothing added changes the story or the characters.
2. Identity. Open each still and verify every trait the prompt claims: colours, outlines, face features,
   ears, tail, accessories, what is absent. Flag wrong traits, missing distinctive traits, and features
   the prompt adds that the stills do not have (including features implied by expressions, such as
   eyebrows on a face that has none).
3. Timing. Cut times and in-shot beat times: can each action happen in the time given? Is there a beat
   with no time, or a shot with nothing happening?
4. Space and continuity. Layout, screen direction, eyelines, who is in frame, and the state of every object
   and light across cuts. Does each shot start where the previous one ended?
5. Physics and story logic. Impossible or contradictory actions (for example, splitting a bun into two
   clean halves after biting it). Results of physical events written out?
6. Misreadings. Phrases the model could draw as a cheaper look-alike ("looks back" drawn as "faces the
   camera", "lifts an arm to rest on the frame" drawn as a wave). Vague directions, ambiguous
   "he/it/they", colour words that contradict the stills (calling a peach-tan bear "brown"), long
   lists of unwanted visual objects.
7. Camera. One clear move per shot in the official vocabulary (type + amplitude + speed). Is subject
   motion described separately from camera motion, and is the relation stated when the camera follows a
   moving subject?
8. Format and consistency. Six sections in order; labels consistent everywhere; retention_analysis shot
   lists match the description; the summary matches the description; 350-500 words; quoted text; both
   sound fields written.
9. Audio. The soundscape matches the visible actions. Music is described by instruments, tempo and
   dynamics. Speech is intended or not, and formatted to match (no <d> means no speech). If there is
   speech: voice described at the first line, exact words in the user's language inside <d>[Language]
   ...</d>, lips closing after lines, <scenetrans>/<cutoff> where a line crosses a cut or the end.

Report:
| # | Severity | Quote from the prompt | What is wrong | Suggested fix |
Severity: Critical = likely to ruin the run or break the request; Major = likely visible defect;
Minor = polish.
Then: VERIFIED - the traits and facts you checked against the stills and found correct, so the author
knows what not to touch.
Last line: VERDICT: ready  or  VERDICT: fix needed
```

## After the review

1. Handle every finding: **fixed** or **rejected because …**. "The reviewer is wrong" needs a concrete reason, such as the still showing otherwise. Write the decisions to `$WORK/review-vN.md`.
2. Save the next version (`prompt-v2.txt`) and run `lint_prompt.py` again.
3. If anything was **Critical**, run a second fresh review of the new version, at most two rounds in total. Major and Minor fixes do not need another round.
4. Tell the user, in their language, two or three lines on what changed and why.
