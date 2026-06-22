# GWAS statistical worker release inputs

The worker image pins PLINK 2 `2.00a6.9`, `susieR` `0.12.35`, and `coloc` `5.2.3`. Builds require
an explicit PLINK archive URL and SHA-256; deployments refuse a worker whose runtime versions drift
from `GWAS_WORKER_REVISION`.

LD panels are deployment data, not image content. Copy `ld-panel-manifest.example.json` to the
read-only panel volume, replace the placeholder hash with the release panel's SHA-256, and keep each
PLINK 2 `.pgen/.pvar/.psam` prefix assembly- and ancestry-specific. A missing population or panel
fails closed.

SuSiE inputs are tab-separated summary statistics with `variant_id`, `beta`, and `se`, plus a
separate allele-harmonized square LD matrix. Coloc inputs additionally require `maf` and `n`, and
the worker requires at least 50 shared variants. The worker never substitutes identity LD or calls
an Open Targets score a p-value.

Run deterministic contracts with:

```sh
.venv/bin/python -m pytest tests/unit/test_gwas_worker.py tests/unit/test_gwas_production_backends.py -q
```

After deploying the worker and uploading release test inputs to the configured object store, run:

```sh
CELLXP_RUN_LIVE_GWAS_WORKER=1 GWAS_BACKEND=http \
GWAS_SERVICE_URL=http://localhost:8103 \
GWAS_SERVICE_VERSION='plink@2.00a6.9+susieR@0.12.35+coloc@5.2.3' \
CELLXP_GWAS_TEST_SUMMARY_STATS_REF=<key> CELLXP_GWAS_TEST_LD_MATRIX_REF=<key> \
CELLXP_GWAS_TEST_GWAS_STATS_REF=<key> CELLXP_GWAS_TEST_QTL_STATS_REF=<key> \
.venv/bin/python -m pytest -m live tests/integration/test_live_production_adapters.py -q
```
