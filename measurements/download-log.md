# Download speed log — DGX Spark ethernet

Plan: 8 Gbps (1000 MB/s line-rate ceiling).
NIC (from Task 1): 10000Mb/s Full, driver r8127 11.014.00-NAPI, iface enP7s7
Method: wall-clock around the transfer; bytes from the finished file or `docker image inspect`.

| When (UTC) | Artifact | Source | Bytes | Seconds | MiB/s | % of 1000 MB/s | Notes |
|---|---|---|---:|---:|---:|---:|---|
| 2026-08-23T22:26:46Z | nvcr.io/nvidia/pytorch:25.12-py3 | nvcr.io | 19727354200 | 181.82 | 103.5 | 10.9 | linux/arm64; inspect Size; some layers already existed from local 25.11-py3 |
| 2026-08-23T23:20:31Z | ComfyUI.git | https://github.com/comfyanonymous/ComfyUI.git | 63448475 | 2.69 | 22.5 | 2.4 | git clone --filter=blob:none --single-branch → /tmp/comfyui-pin; bytes=du -sb; ancestor-ok; HEAD b78cec879b9460d5cb25228a83a942fb78d2cd24 |
| 2026-08-23T23:31:34Z | diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors | https://huggingface.co/Comfy-Org/MiniMax-H3 | 20958205608 | 40.16 | 497.7 | 52.2 | hf download positional; stat bytes |
| 2026-08-23T23:32:05Z | text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors | https://huggingface.co/Comfy-Org/MiniMax-H3 | 27141342152 | 30.67 | 844.0 | 88.5 | hf download positional; stat bytes |
| 2026-08-23T23:32:12Z | vae/minimax_h3_video_vae_fp16.safetensors | https://huggingface.co/Comfy-Org/MiniMax-H3 | 5207808496 | 7.86 | 631.9 | 66.3 | hf download positional; stat bytes |
| 2026-08-23T23:32:15Z | vae/minimax_h3_audio_vae_fp32.safetensors | https://huggingface.co/Comfy-Org/MiniMax-H3 | 605254808 | 2.17 | 266.0 | 27.9 | hf download positional; stat bytes |
| 2026-08-23T23:32:19Z | loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors | https://huggingface.co/Comfy-Org/MiniMax-H3 | 1956193000 | 4.10 | 455.0 | 47.7 | hf download positional; stat bytes |
| 2026-08-23T23:32:20Z | upscale_models/2x-spanx2-ch48.pth | https://objectstorage.us-phoenix-1.oraclecloud.com/n/ax6ygfvpvzka/b/open-modeldb-files/o/2x-spanx2-ch48.pth | 8942586 | 1.01 | 8.4 | 0.9 | OpenModelDB curl; stat bytes |
| 2026-08-23T23:46:38Z | video_minimax_h3_t2v.json | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_minimax_h3_t2v.json | 66335 | 0.09 | 0.7 | 0.1 | official Comfy-Org T2V UI+subgraph template; converted then rebuilt (not shipped unchanged) |
| 2026-08-24T00:26:30Z | h3-spark:local | docker compose -f deploy/compose.yaml build | 20997479065 | 109.34 | 183.1 | 19.2 | image build context + base already pulled; linux/arm64; inspect Size |
| 2026-08-24T00:26:30Z | ComfyUI.git | https://github.com/comfyanonymous/ComfyUI.git | 65463718 | 3.10 | 20.1 | 2.1 | pin=b78cec879b9460d5cb25228a83a942fb78d2cd24; docker build |
| 2026-08-24T00:26:30Z | ComfyUI-KJNodes.git | https://github.com/kijai/ComfyUI-KJNodes.git | 4634610 | 1.38 | 3.2 | 0.3 | pin=3f20054214fec9f9234fd3841ae6f1e4287948f6; docker build |
| 2026-08-24T00:26:30Z | ComfyUI-sol-attn.git | https://github.com/Saganaki22/ComfyUI-sol-attn.git | 332351 | 0.80 | 0.4 | 0.0 | pin=930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf; docker build |
| 2026-08-24T00:26:30Z | ComfyUI-MiniMaxH3-FirstBlockCache.git | https://github.com/duckyshell/ComfyUI-MiniMaxH3-FirstBlockCache.git | 1733055 | 0.94 | 1.8 | 0.2 | pin=725973c3bfd9de6dce249bc93dc5fe27f820df31; docker build |
| 2026-08-24T00:26:30Z | SageAttention.git | https://github.com/thu-ml/SageAttention.git | 97773559 | 2.49 | 37.4 | 3.9 | pin=eb615cf6cf4d221338033340ee2de1c37fbdba4a; tag=v2.2.0; docker build |
| 2026-08-24T00:26:30Z | sageattention-2.2.0 | thu-ml/SageAttention@v2.2.0 pip --no-build-isolation | 14815972 | 75.29 | 0.2 | 0.0 | wheel size=14815972; TORCH_CUDA_ARCH_LIST=12.0; no sageattn3 |
| 2026-08-24T00:32:01Z | pytorch-audio.git | https://github.com/pytorch/audio.git | 152781757 | 2.31 | 63.1 | 6.6 | branch=v2.9.0; docker build |
| 2026-08-24T00:32:01Z | torchaudio-2.9.0 | pytorch/audio@v2.9.0 source --no-build-isolation | 11240823 | 81.31 | 0.1 | 0.0 | NGC torch kept; BUILD_SOX=0 USE_FFMPEG=0; package bytes |

Task 6 D-02 + SPAN vs 8 Gbps (1000 MB/s): six files, **55,877,746,650** `stat` bytes (**52.04 GiB**), **85.97 s** wall-clock sum (not overlapping). Best file: INT8 TE **844.0 MiB/s** (88.5% of line rate). Worst file: SPAN **8.4 MiB/s** (0.9%; 8.5 MiB from Oracle Phoenix, RTT-bound). Aggregate **619.9 MiB/s** / **65.0%** of 1000 MB/s. A perfect 1e9 B/s line would need **~55.9 s**; Hugging Face on this path was faster than the NGC image pull (103.5 MiB/s) and slower than line rate, as expected.
