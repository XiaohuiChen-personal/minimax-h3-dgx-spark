# Optimizations — go faster without breaking sound

This is the **product speed-up list**, not a buffet. Turn these on in the order below. Do not “enable every node at max.” That still fits in memory and can still ruin the audio.

Kernel checks on this GB10 (2026-08-23), no full H3 clip yet:

| Check | Result |
|---|---|
| FP8 `_scaled_mm` vs BF16, big matrix | **2.09×** |
| SageAttention 2.2.0 vs SDPA at H3-like length (S=25120) | cosine **1.000**, **1.62×** |

## Bind in this order

| # | Lever | In the first image? | How |
|---|---|---|---|
| 1 | Smaller weights (D-02) | Required | FP8 DiT + INT8 prompt reader. Capacity first; FP8 is also faster here. |
| 2 | Small frame + SPAN | Always | Generate 960×544, enlarge after. Also keeps tokens ~25k, under Sage’s ~160k “pure noise” cliff. |
| 3 | Turbo LoRA, **8 steps** | Yes | Comfy-Org 8-step file on the **pruned** DiT. Not 4 steps for talking. |
| 4 | SageAttention **2.2** | Yes | Install the 2.2.0 wheel built for this chip (`sm_121`). Never version 3. |
| 5 | Sol-Attn | Yes, pinned | Kernel **`triton_ref` only**. |
| 6 | FirstBlockCache | Yes, gentle | Preset **`H3 Safe`**. Expect little skip at 8 Turbo steps. That is OK. |

## Never turn on

| Switch | Why |
|---|---|
| EasyCache | H3 uses two clocks. EasyCache watches the video clock and replays the leftover onto audio → muffled sound. A later fix stopped *corruption*, not the bad skip rule. |
| EasyCache **and** FirstBlockCache together | Two caches fighting. |
| SageAttention **3** | Broken on GB10. |
| `--use-sage-attention` as a launch flag | Blind flag; H3 noise reports. Wire Sage through the known-good 2.2 path instead. |
| Sol-Attn `flex_attention` | Numerically wrong on sm_121 (cosine ≈ 0.92 vs the correct attention). |
| Turbo-SLA LoRA **plus** Sol-Attn | Two sparsities. Pick Sol-Attn, not both. |
| `--lowvram` / `--novram` | On unified memory this copies the slow way and buys no extra room. |

## Why “all at once” is not automatically safe

**Two clocks.** Video and audio do not share one noise schedule. A cache that only looks at video will lie to the audio track.

**Two sparsities.** A Turbo-SLA LoRA already throws away most attention. Sol-Attn throws away more. One sparse router is enough.

**Pruned AdaLN.** The pruned DiT collapsed a huge “how noisy are we?” table. A LoRA built for the full table drops 51 pieces. That is why we use the Comfy-Org 8-step file and **8 steps**, not 4. ([ModelTC/Minimax-H3-Turbo#7](https://github.com/ModelTC/Minimax-H3-Turbo/issues/7))

**Sage cliff.** Some FP8 attention kernels have emitted pure noise above ~160k packed tokens ([Comfy-Org/ComfyUI#15263](https://github.com/Comfy-Org/ComfyUI/issues/15263)). Native 1920×1088 / 15 s is ~186k. **960×544 / 8.00 s is ~25k.** Generating small is what makes Sage safe here.

**Cache vs Turbo.** On a 20-step Spark run, FirstBlockCache at 0.08 skipped **zero** steps. At 8 distilled steps there is even less to skip. Keep `H3 Safe`. Do not promise a 4× cache headline.

## Memory

A lean ComfyUI H3 load is about **41 GiB** on **121.7 GiB** unified memory, with tens of GiB free. The LoRA and attention wheels are small next to that. The combined stack **fits**. The risk is quality, not running out of memory, at 960×544 / 8 s.

## First real-clip experiment (after weights exist)

Same seed, 5.17 s, 960×544, 8 steps. Change **one** thing at a time:

1. Quant + SPAN only (baseline)
2. + Turbo 8-step
3. + Sage 2.2
4. + Sol-Attn `triton_ref`
5. + FirstBlockCache `H3 Safe`

Score **picture** and **sound** separately. Never add EasyCache to that series.

If step 3 or 4 looks like noise or dead audio, fall back to the previous rung and record it. Do not keep stacking.
