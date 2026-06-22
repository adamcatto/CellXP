FROM python:3.12.11-slim-bookworm

ARG ALPHAGENOME_VERSION=0.6.1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CELLXP_SEQUENCE_WORKER_MODE=production
WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python -m pip install --no-cache-dir . "alphagenome==${ALPHAGENOME_VERSION}" \
    "fastapi==0.115.14" "uvicorn[standard]==0.34.3" \
    && useradd --create-home --uid 10001 cellxp
USER cellxp
EXPOSE 8103
CMD ["uvicorn", "cellxp.services.alphagenome.alphagenome_worker:app", "--host", "0.0.0.0", "--port", "8103", "--workers", "1"]
