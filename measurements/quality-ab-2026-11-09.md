# Quality A/B — shift, structured prompt, Sol dense blocks, VAE seam fix (2026-11-09)

Live on this GB10. Submitted **from the operator's MacBook over Tailscale** (`H3_COMFY_URL=http://spark-2a60:8188`), which also proves the remote path: six local stills uploaded, mp4 downloaded with `GET /view`, SHA-256 of the laptop copy equal to the Spark copy.

Image: `h3-spark:local` rebuilt from `feat/remote-generate-quality-fixes` (ComfyUI pin `b78cec87` + backport `h3-vae-tile-blend(fc584aaa)`). The rebuild took 3 s; every SageAttention / torchaudio layer was cached. The in-build CPU test printed `OK: tiled_decode matches the separable overlap-add reference`.

Common to every run: `workflows/h3-ref2va-smoke-5s17.json` (Ref2VA, 4-step Ref2V Turbo v0.1, 960×544 → SPAN → 1920×1080, 5.17 s / 124 frames), seed **42**, the six bird stills (`sheet-{blue,yellow}-{front,side,back}.jpg`) in that order. The ComfyUI log confirmed the Sol change: `[MiniMax H3 Sol] patched 46 of 50 attention blocks (tau=1.30 …)` (blocks 0–2 and 49 dense).

| Job | Shift | Prompt | ComfyUI s | Result |
|---|---|---|---|---|
| `ab-shift6-structured` | 6 / 3 (old) | six-section (v1) | 149.76 (includes cold model load) | Scene and action follow the prompt. Softer detail; blue tint bleeds into the blue bird's white crown. |
| `ab-shift12-structured` | **12 / 3** | six-section (v1) | 105.32 | Same composition and action, visibly sharper feathers, eyes, beaks, and hedge. |
| `ab-shift12-oneline` | 12 / 3 | old one-liner (`<Picture 1> <Picture 2> <Picture 3> are front, side, and back stills …`) | 107.32 | **Off-prompt.** Copies the reference-sheet layout: three birds in a row, printed “Front/Side/Back” captions on screen, a hard cut from a blue trio to a yellow trio. |
| `ab-shift12-structured-v2` | 12 / 3 | six-section, bird traits corrected to match the stills | 111.06 | Yellow bird now has the stills' cream-yellow face and breast (v1 text said “pale grey face” and the model followed the text). Blue bird face lighter; breast still greyer than the white reference. |

Sharpness proxy (variance of the Laplacian on the same 800×600 1:1 crop around the birds' heads; higher = more fine detail). One seed, crude metric — supporting evidence, not a benchmark:

| Frame | shift 6 / 3 | shift 12 / 3 |
|---|---|---|
| t = 2.5 s | 68.4 | **143.2** |
| t = 4.8 s | 51.0 | **71.2** |

All four mp4s: 1920×1080, 124 frames at 24 fps (5.17 s), stereo 32 kHz audio, RMS −32 to −35 dBFS (room tone, no speech), 6.4–7.8 Mbit/s. Host files: `$HOME/h3-output/ab-*_00001_.mp4` on the Spark and the laptop. Do not commit them.

## What this settles

1. **Structured prompts are the largest lever.** Same graph, same seed: the one-liner produced a sheet-copy with captions; the six-section prompt produced the described shot. This matches MiniMax's “H3-Context-IR is critical to the quality of the final output.” Rules: [`../design/prompting.md`](../design/prompting.md).
2. **Shift 12 / 3 is right for the shipped 544p LoRAs** (D-06 corrected). It matches the LoRA author's training spec and looked sharper here. Wall time is unchanged.
3. **The prompt beats the stills when they disagree.** Describe what the stills show. v1 → v2 changed only the bird descriptions and fixed the yellow bird's face.
4. **Turbo Ref2VA identity is still imperfect** (blue bird breast greyer than the reference). The no-Turbo quality graph remains the identity path; it has not been re-run with structured prompts yet.

Not measured here: the VAE seam fix on a real clip (every run above used the patched image; the CPU test against the real pinned class is the proof — unpatched max error 2.75, patched 5e-15), and the newer lightx2v 768p LoRAs (not downloaded).
