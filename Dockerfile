# VALKYRIE baked earth2studio image — matched-CUDA base so makani/torch-harmonics COMPILE.
# Built by GitHub Actions (native amd64), pushed to ghcr.io/venly104w/valk-e2s:1.0.
# Root fix: NVIDIA px models need torch==CUDA-toolkit match at compile (live runpod base mismatched).
# pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel is matched. uv resolves earth2studio uv.sources
# (matched makani+physicsnemo revs); per-package no-build-isolation compiles CUDA vs the base torch.
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_CONSTRAINT= \
    EARTH2STUDIO_PACKAGE_TIMEOUT=1800 \
    FORCE_CUDA_EXTENSION=1 \
    TORCH_CUDA_ARCH_LIST=8.6

RUN apt-get update && apt-get install -y --no-install-recommends \
      git cmake build-essential ninja-build curl libeccodes-dev libeccodes-tools \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -U uv ninja setuptools wheel packaging

# uv honors earth2studio's [tool.uv.sources] (matched makani + torch-harmonics + physicsnemo git pins
# that plain pip ignores). --no-build-isolation-package on the CUDA pkgs compiles them vs the base torch;
# everything else builds normally so hatchling etc auto-resolve.
RUN uv pip install --system \
      --no-build-isolation-package makani \
      --no-build-isolation-package torch_harmonics \
      --no-build-isolation-package torch-harmonics \
      "earth2studio[fcn,pangu,fuxi,aurora,dlwp,sfno,fcn3,stormcast,dlesym,data]@git+https://github.com/NVIDIA/earth2studio.git@0.15.0" \
      onnxruntime-gpu "more_itertools>=10"

# warp-lang>=1.5 removed `warp.context` which earth2studio imports -> pin to the last 1.4.x.
RUN uv pip install --system 'warp-lang<1.5'

# BUILD-TIME SMOKE TEST — fail the build (in free CI) if the makani fix didn't take.
RUN python -c "import torch, physicsnemo, makani; \
from earth2studio.models.px import FCN, FCN3, SFNO, Pangu6, FuXi, DLWP; \
print('PX IMPORT OK · torch', torch.__version__, '· physicsnemo', physicsnemo.__version__, '· makani+FCN3+SFNO import clean')"

WORKDIR /root
