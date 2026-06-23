FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel

ARG EVO2_VERSION=0.6.0
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CELLXP_SEQUENCE_WORKER_MODE=production EVO2_WEIGHT_PATH=/models/evo2_7b.pt
ENV CELLXP_EVO2_RUNTIME_FACTORY=cellxp.services.alphagenome.sdk_backends:create_evo2_backend
WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python -m pip install --no-cache-dir . "evo2==${EVO2_VERSION}" \
    "fastapi==0.115.14" "uvicorn[standard]==0.34.3" ninja psutil wheel \
    && VORTEX_OPS="$(python -c 'import importlib.util, pathlib; print(pathlib.Path(importlib.util.find_spec("vortex").origin).parent / "ops")')" \
    && MAX_JOBS=8 python -m pip install --no-cache-dir --no-build-isolation \
         "${VORTEX_OPS}/depr_attn" "${VORTEX_OPS}/conv" \
    && python -c 'import torch, flash_attn_2_cuda, local_causal_conv1d_cuda' \
    && useradd --create-home --uid 10001 cellxp && mkdir -p /models && chown cellxp:cellxp /models
USER cellxp
EXPOSE 8107
CMD ["uvicorn", "cellxp.services.alphagenome.evo_worker:app", "--host", "0.0.0.0", "--port", "8107", "--workers", "1"]
