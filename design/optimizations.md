# Optimization stack (working note)

Research recommendation for this GB10. Not a locked product default. HTML skeleton is still empty.

**Combined verdict:** the six levers can run together on this machine if we pair them carefully. A naive “enable every node at max aggression” stack will fit in memory and can still ruin audio.

## What this box just confirmed

| Test | Result | Date |
|---|---|---|
| `torch._scaled_mm` FP8 E4M3 vs BF16, 8192³ | 173.8 vs 83.3 TFLOP/s (**2.09×**) | 2026-08-23 |
| SageAttention **2.2.0** import from the local `sm_121a` wheel | Works in `~/.vllm` torch 2.10.0+cu130 | 2026-08-23 |
| Sage vs SDPA, S=25120 (8.00 s @ 960×544 token scale), H=8, D=128 | cosine **1.000**, **1.62×** | 2026-08-23 |
| Sage vs SDPA, S=16384 | cosine 0.996, **1.63×** | 2026-08-23 |

No full H3 clip was generated. ComfyUI is not installed in this repo and H3 weights are not downloaded.

## Bind them in this order

| # | Lever | Bind? | How on this Spark |
|---|---|---|---|
| 1 | Quant (D-02) | Required | FP8 DiT + INT8 ConvRot text encoder. Capacity first; FP8 also has a real compute win here. |
| 2 | Generate 960×544 + SPAN 2× | Always | After the sampler. Independent of the other kernels. Also keeps packed tokens far below the Sage ~160k noise cliff. |
| 3 | Turbo LoRA, **8 steps** | Yes | Use a ComfyUI conversion aimed at the *pruned* checkpoint. Do not use 4-step as the dialogue default. |
| 4 | SageAttention **2.2** | Yes | Local wheel is now runtime-tested at H3-like lengths. Never SageAttention 3. Do not blindly pass `--use-sage-attention` (H3 noise reports). |
| 5 | Sol-Attn | Yes, with a kernel pin | `triton_ref` only. `flex_attention` is numerically wrong on sm_121 (cos ≈ 0.92). Do not also load Turbo-SLA (second sparsity). |
| 6 | Cross-step cache | Yes, but not EasyCache | Prefer H3-specific FirstBlockCache (`H3 Safe` / `H3 Fast`). EasyCache still muffles H3 audio even after the corruption fix. At 8 Turbo steps, expect small skip rates. |

Do **not** combine EasyCache with FBC. Do **not** enable `--lowvram`.

## Why “all at once” is not automatically safe

- **Two clocks.** H3 video and audio use different flow shifts. EasyCache decides skips from video and replays the residual onto audio → muffled / half-amplitude audio ([Comfy-Org/ComfyUI#15326](https://github.com/Comfy-Org/ComfyUI/issues/15326)). PR #15390 stopped *corruption*; it did not make the skip policy correct.
- **Two sparsities.** `Minimax-h3-Turbo-SLA` already drops ~85% of attention. Sol-Attn is another sparse router. Pick one.
- **Pruned AdaLN.** ComfyUI pruned checkpoints use 8-d AdaLN vs 2688-d on the full model. Converted Turbo LoRAs **drop 51 AdaLN pairs**. That is why 8 steps, not 4, on the D-02 DiT ([ModelTC/Minimax-H3-Turbo#7](https://github.com/ModelTC/Minimax-H3-Turbo/issues/7)).
- **Sage cliff.** FP8 PV kernels have produced pure noise above ~160k packed tokens ([Comfy-Org/ComfyUI#15263](https://github.com/Comfy-Org/ComfyUI/issues/15263)). Native 1920×1088 / 15 s is ~186k. **960×544 / 8.00 s is ~25k.** Generate-small is what makes Sage safe here.
- **Cache vs Turbo.** FirstBlockCache at threshold 0.08 skipped **zero** steps in a 20-step Spark Sol Engine run. At 8 distilled steps the cache has even less room. Keep it on `H3 Safe`; do not expect the 3.9× TeaCache headline.

## Memory

Lean ComfyUI H3 was estimated ~41 GiB resident with ~49 GiB headroom on 121.7 GiB. LoRA (~1.8 GiB) and attention kernels are small next to that. The combined stack is a **capacity fit**. The risk is quality, not OOM, at 960×544 / 8 s.

## First host experiment (when weights exist)

One variable at a time, fixed seed, 5.17 s / 960×544 / 8 steps:

1. Quant + SPAN only (baseline)
2. + Turbo 8-step
3. + Sage 2.2
4. + Sol-Attn `triton_ref`
5. + FBC `H3 Safe`

Score video and audio separately. Do not turn on EasyCache in that series.
