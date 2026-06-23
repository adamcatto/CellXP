FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ARG EVO2_VERSION=0.6.0
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CELLXP_SEQUENCE_WORKER_MODE=production EVO2_WEIGHT_PATH=/models/evo2_7b.pt
ENV CELLXP_EVO2_RUNTIME_FACTORY=cellxp.services.alphagenome.sdk_backends:create_evo2_backend
WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python -m pip install --no-cache-dir . "evo2==${EVO2_VERSION}" \
    "fastapi==0.115.14" "uvicorn[standard]==0.34.3" \
    && useradd --create-home --uid 10001 cellxp && mkdir -p /models && chown cellxp:cellxp /models
USER cellxp
EXPOSE 8104
CMD ["uvicorn", "cellxp.services.alphagenome.evo_worker:app", "--host", "0.0.0.0", "--port", "8104", "--workers", "1"]
