FROM continuumio/miniconda3:4.12.0 AS azimuth
ARG AZIMUTH_REV=73522accfde9d609563231efcc5f3b284af78566
ARG AZIMUTH_SHA256=95534ab72bb706ab9b9c86a60090cc2c9b761f08d1b977e36d25f512dfe3dfb7
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL "https://github.com/MicrosoftResearch/Azimuth/archive/${AZIMUTH_REV}.tar.gz" -o /tmp/azimuth.tar.gz \
    && echo "${AZIMUTH_SHA256}  /tmp/azimuth.tar.gz" | sha256sum -c - \
    && mkdir /tmp/azimuth-src && tar -xzf /tmp/azimuth.tar.gz -C /tmp/azimuth-src --strip-components=1 \
    && conda create -y -p /opt/azimuth python=2.7 numpy=1.16 scipy=1.2 pandas=0.24 scikit-learn=0.20 biopython=1.76 \
    && /opt/azimuth/bin/pip install --no-deps /tmp/azimuth-src

FROM python:3.12.11-slim-bookworm

ARG CAS_OFFINDER_REV=9816b94c20c4cba2e79b039e1e2a6dee684b7b66
ARG CAS_OFFINDER_SHA256=3505e2a6f37f4ca366cce0293c1ad1396ce2208ed44bfd2dde435df77dcc869b
ARG CRISPOR_REV=c221aff4bf1270eabda98f6e654f639b4c48fd0b
ARG CRISPOR_SHA256=0e460e704008b06eb7be8d461c860d0e8b941831475c88877c3658a5de04ab88

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CELLXP_CRISPR_WORKER_MODE=production \
    CRISPR_INDEX_MANIFEST=/indexes/manifest.json CRISPR_INDEX_ROOT=/indexes \
    CELLXP_CRISPR_RUNTIME_FACTORY=cellxp.services.crispr.runtime:create_runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl cmake g++ \
      libboost-program-options-dev ocl-icd-opencl-dev pocl-opencl-icd \
    && rm -rf /var/lib/apt/lists/* && mkdir -p /opt/crispr /indexes \
    && curl -fsSL "https://github.com/snugel/cas-offinder/archive/${CAS_OFFINDER_REV}.tar.gz" -o /tmp/cas.tar.gz \
    && echo "${CAS_OFFINDER_SHA256}  /tmp/cas.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/cas.tar.gz -C /opt/crispr \
    && cmake -S "/opt/crispr/cas-offinder-${CAS_OFFINDER_REV}" -B /tmp/cas-build \
    && cmake --build /tmp/cas-build --parallel \
    && cp /tmp/cas-build/cas-offinder /usr/local/bin/cas-offinder \
    && curl -fsSL "https://github.com/maximilianh/crisporWebsite/archive/${CRISPOR_REV}.tar.gz" -o /tmp/crispor.tar.gz \
    && echo "${CRISPOR_SHA256}  /tmp/crispor.tar.gz" | sha256sum -c - \
    && mkdir /opt/crispr/cfd \
    && tar -xzf /tmp/crispor.tar.gz -C /opt/crispr/cfd --strip-components=2 \
      "crisporWebsite-${CRISPOR_REV}/CFD_Scoring/mismatch_score.pkl" \
      "crisporWebsite-${CRISPOR_REV}/CFD_Scoring/pam_scores.pkl" \
    && rm -rf /tmp/cas.tar.gz /tmp/crispor.tar.gz /tmp/cas-build
COPY --from=azimuth /opt/azimuth /opt/azimuth
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python -m pip install --no-cache-dir . "fastapi==0.115.14" "uvicorn[standard]==0.34.3" \
    && useradd --create-home --uid 10001 cellxp && chown -R cellxp:cellxp /indexes
USER cellxp
EXPOSE 8105
CMD ["uvicorn", "cellxp.services.crispr.worker:app", "--host", "0.0.0.0", "--port", "8105", "--workers", "1"]
