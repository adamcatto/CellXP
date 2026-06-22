FROM python:3.12.4-slim-bookworm

ARG PLINK_VERSION=2.00a6.9
ARG SUSIER_VERSION=0.12.35
ARG COLOC_VERSION=5.2.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GWAS_WORKER_REVISION=plink@${PLINK_VERSION}+susieR@${SUSIER_VERSION}+coloc@${COLOC_VERSION} \
    GWAS_SCRIPT_DIR=/opt/cellxp/gwas \
    GWAS_LD_PANEL_MANIFEST=/data/ld-panels/manifest.json

RUN apt-get update \
    && apt-get install -y --no-install-recommends r-base ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Package versions are immutable release inputs. The PLINK archive checksum must be supplied by the
# build pipeline; a missing checksum fails the build instead of accepting mutable upstream bytes.
ARG PLINK_ARCHIVE_SHA256
ARG PLINK_ARCHIVE_URL
RUN test -n "${PLINK_ARCHIVE_SHA256}" \
    && test -n "${PLINK_ARCHIVE_URL}" \
    && curl -fsSL -o /tmp/plink.zip "${PLINK_ARCHIVE_URL}" \
    && echo "${PLINK_ARCHIVE_SHA256}  /tmp/plink.zip" | sha256sum -c - \
    && unzip /tmp/plink.zip plink2 -d /usr/local/bin \
    && rm /tmp/plink.zip

RUN Rscript -e "install.packages('remotes', repos='https://cloud.r-project.org'); remotes::install_version('susieR', version='${SUSIER_VERSION}', repos='https://cloud.r-project.org'); remotes::install_version('coloc', version='${COLOC_VERSION}', repos='https://cloud.r-project.org'); install.packages('jsonlite', repos='https://cloud.r-project.org')"

WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend
COPY infra/gwas /opt/cellxp/gwas
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 cellxp \
    && mkdir -p /artifacts /data/ld-panels \
    && chown -R cellxp:cellxp /artifacts /data/ld-panels

USER cellxp
EXPOSE 8103
CMD ["uvicorn", "cellxp.services.gwas.worker:app", "--host", "0.0.0.0", "--port", "8103", "--workers", "1"]
