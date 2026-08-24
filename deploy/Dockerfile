# MiniMax H3 ComfyUI image for DGX Spark (linux/arm64).
# Weights stay on the host (D-10). Never COPY or download *.safetensors / MiniMax *.pth.
ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:25.12-py3
FROM --platform=linux/arm64 ${BASE_IMAGE}

ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:25.12-py3
ARG COMFYUI_SHA=b78cec879b9460d5cb25228a83a942fb78d2cd24
ARG KJNODES_SHA=3f20054214fec9f9234fd3841ae6f1e4287948f6
ARG SOL_ATTN_SHA=930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf
ARG FBC_SHA=725973c3bfd9de6dce249bc93dc5fe27f820df31
ARG SAGEATTENTION_SHA=eb615cf6cf4d221338033340ee2de1c37fbdba4a

LABEL comfyui.git_sha="${COMFYUI_SHA}" \
      base.image="${BASE_IMAGE}" \
      h3.decision_set="D-01..D-14" \
      h3.kjnodes.git_sha="${KJNODES_SHA}" \
      h3.sol_attn.git_sha="${SOL_ATTN_SHA}" \
      h3.fbc.git_sha="${FBC_SHA}" \
      h3.sageattention="2.2.0"

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

SHELL ["/bin/bash", "-c"]

RUN mkdir -p /opt/h3

# Pin ComfyUI. Do not float on master.
RUN set -euxo pipefail; \
    start=$(date +%s.%N); \
    git clone --filter=blob:none https://github.com/comfyanonymous/ComfyUI.git /opt/ComfyUI; \
    git -C /opt/ComfyUI checkout --detach "${COMFYUI_SHA}"; \
    test "$(git -C /opt/ComfyUI rev-parse HEAD)" = "${COMFYUI_SHA}"; \
    end=$(date +%s.%N); \
    bytes=$(du -sb /opt/ComfyUI | awk '{print $1}'); \
    secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "ComfyUI.git" "https://github.com/comfyanonymous/ComfyUI.git" \
      "$bytes" "$secs" "pin=${COMFYUI_SHA}" >> /opt/h3/build-timings.txt; \
    rm -rf /opt/ComfyUI/.git

WORKDIR /opt/ComfyUI

# NGC image Python is GPU torch. Drop unpinned torch/vision/audio so pip cannot replace it.
RUN set -euxo pipefail; \
    grep -vE '^(torch|torchvision|torchaudio)([<>=!~[:space:]]|$)' requirements.txt > /tmp/comfy-reqs.txt; \
    python -m pip install --no-cache-dir -r /tmp/comfy-reqs.txt; \
    python -c "import torch; assert 'nv25.12' in torch.__version__, torch.__version__"

# Custom nodes the locked graphs actually call. Pin SHAs. Time each clone.
RUN set -euxo pipefail; \
    record_clone() { \
      local name="$1" url="$2" dest="$3" sha="$4"; \
      local start end bytes secs; \
      start=$(date +%s.%N); \
      git clone --filter=blob:none "$url" "$dest"; \
      git -C "$dest" checkout --detach "$sha"; \
      test "$(git -C "$dest" rev-parse HEAD)" = "$sha"; \
      end=$(date +%s.%N); \
      bytes=$(du -sb "$dest" | awk '{print $1}'); \
      secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
      printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$url" "$bytes" "$secs" "pin=${sha}" >> /opt/h3/build-timings.txt; \
      rm -rf "$dest/.git"; \
    }; \
    record_clone "ComfyUI-KJNodes.git" \
      "https://github.com/kijai/ComfyUI-KJNodes.git" \
      /opt/ComfyUI/custom_nodes/ComfyUI-KJNodes "${KJNODES_SHA}"; \
    record_clone "ComfyUI-sol-attn.git" \
      "https://github.com/Saganaki22/ComfyUI-sol-attn.git" \
      /opt/ComfyUI/custom_nodes/ComfyUI-sol-attn "${SOL_ATTN_SHA}"; \
    record_clone "ComfyUI-MiniMaxH3-FirstBlockCache.git" \
      "https://github.com/duckyshell/ComfyUI-MiniMaxH3-FirstBlockCache.git" \
      /opt/ComfyUI/custom_nodes/ComfyUI-MiniMaxH3-FirstBlockCache "${FBC_SHA}"; \
    grep -q 'class PathchSageAttentionKJ' /opt/ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/model_optimization_nodes.py; \
    grep -q 'class MiniMaxH3MemoryEfficientSolAttentionPatch' /opt/ComfyUI/custom_nodes/ComfyUI-sol-attn/minimax.py; \
    grep -q 'class ApplyMiniMaxH3FirstBlockCache' /opt/ComfyUI/custom_nodes/ComfyUI-MiniMaxH3-FirstBlockCache/nodes.py; \
    grep -q 'H3 Safe' /opt/ComfyUI/custom_nodes/ComfyUI-MiniMaxH3-FirstBlockCache/nodes.py; \
    python -m pip install --no-cache-dir -r /opt/ComfyUI/custom_nodes/ComfyUI-KJNodes/requirements.txt; \
    python -c "import torch; assert 'nv25.12' in torch.__version__, torch.__version__"

# SageAttention 2.2.0 only. Official SUPPORTED_ARCHS has 12.0, not 12.1.
# Delete the vendored Sage 3 tree before install. --no-build-isolation keeps NGC torch.
RUN set -euxo pipefail; \
    start=$(date +%s.%N); \
    git clone --filter=blob:none https://github.com/thu-ml/SageAttention.git /tmp/SageAttention; \
    git -C /tmp/SageAttention checkout --detach "${SAGEATTENTION_SHA}"; \
    test "$(git -C /tmp/SageAttention rev-parse HEAD)" = "${SAGEATTENTION_SHA}"; \
    end=$(date +%s.%N); \
    bytes=$(du -sb /tmp/SageAttention | awk '{print $1}'); \
    secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "SageAttention.git" "https://github.com/thu-ml/SageAttention.git" \
      "$bytes" "$secs" "pin=${SAGEATTENTION_SHA};tag=v2.2.0" >> /opt/h3/build-timings.txt; \
    rm -rf /tmp/SageAttention/sageattention3_blackwell /tmp/SageAttention/.git; \
    test ! -d /tmp/SageAttention/sageattention3_blackwell; \
    start=$(date +%s.%N); \
    export TORCH_CUDA_ARCH_LIST=12.0 CUDA_HOME=/usr/local/cuda MAX_JOBS=8; \
    python -m pip install --no-build-isolation --no-cache-dir --no-deps /tmp/SageAttention; \
    end=$(date +%s.%N); \
    bytes=$(python -c 'import importlib.metadata as m, pathlib; print(sum(p.stat().st_size for p in pathlib.Path(m.distribution("sageattention").locate_file("")).rglob("*") if p.is_file()))' || du -sb /usr/local/lib/python3.12/dist-packages/sageattention | awk '{print $1}'); \
    secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "sageattention-2.2.0" "thu-ml/SageAttention@v2.2.0 pip --no-build-isolation" \
      "$bytes" "$secs" "TORCH_CUDA_ARCH_LIST=12.0; no sageattn3" >> /opt/h3/build-timings.txt; \
    python -c "import importlib.metadata as m; v=m.version('sageattention'); assert v=='2.2.0', v"; \
    python -c "from sageattention import sageattn_qk_int8_pv_fp16_triton"; \
    python -c "import importlib.util; assert importlib.util.find_spec('sageattn3') is None"; \
    python -c "import torch; assert 'nv25.12' in torch.__version__, torch.__version__"; \
    rm -rf /tmp/SageAttention /root/.cache /tmp/pip-*

# NGC 25.12 does not ship torchaudio. PyPI / cu130 wheels ABI-mismatch this torch.
# v2.10.0 source needs torch/csrc/stable/device.h (absent here). v2.9.0 builds
# and provides resample / MelSpectrogram that ComfyUI H3 imports. Do not replace torch.
RUN set -euxo pipefail; \
    start=$(date +%s.%N); \
    git clone --depth 1 --branch v2.9.0 https://github.com/pytorch/audio.git /tmp/audio; \
    end=$(date +%s.%N); \
    bytes=$(du -sb /tmp/audio | awk '{print $1}'); \
    secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "pytorch-audio.git" "https://github.com/pytorch/audio.git" \
      "$bytes" "$secs" "branch=v2.9.0" >> /opt/h3/build-timings.txt; \
    start=$(date +%s.%N); \
    export BUILD_SOX=0 USE_FFMPEG=0 BUILD_KALDI=0 MAX_JOBS=8; \
    python -m pip install --no-deps --no-build-isolation /tmp/audio; \
    end=$(date +%s.%N); \
    bytes=$(python -c 'import pathlib,torchaudio; p=pathlib.Path(torchaudio.__file__).parent; print(sum(x.stat().st_size for x in p.rglob("*") if x.is_file()))'); \
    secs=$(awk -v s="$start" -v e="$end" 'BEGIN{printf "%.4f\n", e-s}'); \
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "torchaudio-2.9.0" "pytorch/audio@v2.9.0 source --no-build-isolation" \
      "$bytes" "$secs" "NGC torch kept; BUILD_SOX=0 USE_FFMPEG=0" >> /opt/h3/build-timings.txt; \
    python -c "import torchaudio,torch; assert torchaudio.__version__.startswith('2.9.0'), torchaudio.__version__; assert 'nv25.12' in torch.__version__, torch.__version__"; \
    python -c "from torchaudio.transforms import MelSpectrogram; import torchaudio.functional as F"; \
    rm -rf /tmp/audio /root/.cache /tmp/pip-*

# Fail the image if MiniMax-sized weights landed in a layer.
RUN set -euxo pipefail; \
    python - <<'PY'
import os
bad = []
for base in ("/opt", "/usr/local", "/root"):
    if not os.path.isdir(base):
        continue
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            path = os.path.join(root, name)
            if name.endswith(".safetensors"):
                bad.append(path)
                continue
            if name.endswith((".pth", ".pt")):
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size >= 50 * 1024 * 1024:
                    bad.append(f"{path} ({size})")
if bad:
    raise SystemExit("baked weight-like files:\n" + "\n".join(bad))
print("no baked MiniMax weight files")
PY

COPY scripts /opt/h3/scripts
COPY workflows /opt/h3/workflows

RUN chmod 0755 /opt/h3/scripts/entrypoint.sh /opt/h3/scripts/check-weights.sh \
    && test -f /opt/h3/scripts/required-weights.txt \
    && test -f /opt/h3/workflows/h3-fl2va-smoke-5s17.json \
    && test -f /opt/h3/workflows/h3-fl2va-default-8s.json

WORKDIR /opt/ComfyUI
EXPOSE 8188
ENTRYPOINT ["/opt/h3/scripts/entrypoint.sh"]
