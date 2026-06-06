# VALKYRIE baked earth2studio image — kills the per-pod install tax + bakes the makani fix.
# Build ONCE, push to GHCR, register as a RunPod template. Pods then boot ready (~1 min vs 15-25).
#
#   docker build -t ghcr.io/<you>/valk-e2s:1.0 -f ~/.valkyrie/Dockerfile ~/.valkyrie
#   echo $GHCR_TOKEN | docker login ghcr.io -u $GHCR_USER --password-stdin
#   docker push ghcr.io/<you>/valk-e2s:1.0
#   # RunPod: New Template -> Container Image = ghcr.io/<you>/valk-e2s:1.0
#
# ROOT-CAUSE FIX baked in: `makani` is NOT on PyPI; earth2studio resolves it via [tool.uv.sources]
# git pins that PLAIN PIP IGNORES -> FCN3/SFNO/StormCast raise OptionalDependencyError. We install
# makani + torch-harmonics from git BY HAND, pin nvidia-physicsnemo==2.0.0 (NOT 2.1.0 -> needs torch 2.10),
# then earth2studio. The build-time smoke test FAILS the build if px import is not clean.

FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_CONSTRAINT= \
    EARTH2STUDIO_PACKAGE_TIMEOUT=1200 \
    FORCE_CUDA_EXTENSION=1 \
    TORCH_CUDA_ARCH_LIST=8.6

# system deps: git (git installs), cmake/build (torch-harmonics + makani CUDA kernels), eccodes (GRIB/GFS)
RUN apt-get update && apt-get install -y --no-install-recommends \
      git cmake build-essential ninja-build curl libeccodes-dev libeccodes-tools \
    && rm -rf /var/lib/apt/lists/*

# 1) physicsnemo 2.0.0 — the unifying pin (StormCast/CorrDiff need >=2.0; makani works on it; torch>=2.4 ok)
RUN pip install --no-cache-dir "nvidia-physicsnemo==2.0.0"

# 2) torch-harmonics WITH CUDA kernels (git pin from earth2studio uv.sources) — FCN3/SFNO disco extension
RUN pip install --no-cache-dir --no-build-isolation \
      "torch-harmonics @ git+https://github.com/NVIDIA/torch-harmonics.git@a632ca748a12bd9f74dbc1e00653317810991f74"

# 3) makani from git (NOT on PyPI — this is the missing piece that caused OptionalDependencyError)
RUN pip install --no-cache-dir --no-build-isolation \
      "makani @ git+https://github.com/NVIDIA/modulus-makani.git@b38fcb2799d7dbc146fa60459f3f9823394a8bf1"

# 4) earth2studio — the makani + onnx + physicsnemo-compatible core (serve/Dockerfile set).
#    graphcast(jax), aurora, aifs are separate dep families -> their own images, NOT here.
RUN pip install --no-cache-dir \
      "earth2studio[data,pangu,fengwu,fuxi,dlwp,sfno,fcn3,stormcast,dlesym]" \
      "onnxruntime-gpu>=1.20.1" "more_itertools>=10"

# 5) BUILD-TIME SMOKE TEST — fail the build now if the makani fix didn't take (no wasted pod runs later)
RUN python -c "import torch, physicsnemo; from physicsnemo.models import Module; \
from earth2studio.models.px import FCN, FCN3, SFNO, StormCast, Pangu6, FuXi, DLWP; \
print('PX IMPORT OK · torch', torch.__version__, '· physicsnemo', physicsnemo.__version__)"

WORKDIR /root
