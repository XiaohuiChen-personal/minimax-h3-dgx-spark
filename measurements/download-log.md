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

Task 6 D-02 + SPAN vs 8 Gbps (1000 MB/s): six files, **55,877,746,650** `stat` bytes (**52.04 GiB**), **85.97 s** wall-clock sum (not overlapping). Best file: INT8 TE **844.0 MiB/s** (88.5% of line rate). Worst file: SPAN **8.4 MiB/s** (0.9%; 8.5 MiB from Oracle Phoenix, RTT-bound). Aggregate **619.9 MiB/s** / **65.0%** of 1000 MB/s. A perfect 1e9 B/s line would need **~55.9 s**; Hugging Face on this path was faster than the NGC image pull (103.5 MiB/s) and slower than line rate, as expected.
