FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG EVO2_VERSION=0.6.0
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CELLXP_SEQUENCE_WORKER_MODE=production EVO2_WEIGHT_PATH=/models/evo2_7b.pt
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python3 -m pip install --no-cache-dir . "evo2==${EVO2_VERSION}" \
    "fastapi==0.115.14" "uvicorn[standard]==0.34.3" \
    && useradd --create-home --uid 10001 cellxp && mkdir -p /models && chown cellxp:cellxp /models
USER cellxp
EXPOSE 8104
CMD ["uvicorn", "cellxp.services.alphagenome.evo_worker:app", "--host", "0.0.0.0", "--port", "8104", "--workers", "1"]
