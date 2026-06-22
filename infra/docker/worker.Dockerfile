FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ARG BOLTZ_VERSION=2.2.1
ARG TRANSFORMERS_VERSION=4.52.4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/models \
    STRUCTURE_DEVICE=cuda \
    STRUCTURE_JOB_TIMEOUT_SECONDS=1800

WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend

RUN python -m pip install --no-cache-dir . \
    "boltz[cuda]==${BOLTZ_VERSION}" \
    "transformers==${TRANSFORMERS_VERSION}" \
    "accelerate==1.7.0"

RUN useradd --create-home --uid 10001 cellxp \
    && mkdir -p /models /artifacts \
    && chown -R cellxp:cellxp /models /artifacts

USER cellxp
EXPOSE 8102
CMD ["uvicorn", "cellxp.services.structure.worker:app", "--host", "0.0.0.0", "--port", "8102", "--workers", "1"]
