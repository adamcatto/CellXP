# Running the CRISPR Worker

The CRISPR worker isolates actionable guide scoring and genome-wide off-target work from the API.
It fails closed unless its executable revisions and assembly indexes attest successfully.

## Pinned runtime

`infra/docker/crispr-worker.Dockerfile` packages three upstream source snapshots recorded in
`cellxp/services/crispr/worker_manifest.json`:

- Cas-OFFinder 2.4.1 (`9816b94…`), compiled with an OpenCL CPU runtime;
- Azimuth/Rule Set 2 v2.0 (`73522ac…`) in an isolated Python 2.7 compatibility environment;
- CRISPOR CFD tables (`c221aff…`) consumed by the Python 3 worker adapter.

Every source archive is checked against its recorded SHA-256 during the image build. The runtime
self-attests these revisions before `/health` returns `status=ok`.

## Assembly indexes

Production requires `CRISPR_INDEX_MANIFEST=/indexes/manifest.json`. Each entry binds an organism,
assembly, topology (`linear` or `circular`), and file role to a SHA-256. Example:

```json
{
  "schema_version": "1.0",
  "indexes": [{
    "organism": "Escherichia coli",
    "assembly": "GCF_000005845.2",
    "topology": "circular",
    "files": [{
      "path": "GCF_000005845.2/reference.fa",
      "role": "reference_fasta",
      "sha256": "<64 lowercase hex characters>"
    }]
  }]
}
```

Validate it before deployment:

```bash
PYTHONPATH=src/backend python scripts/verify_crispr_index_manifest.py /indexes/manifest.json
```

The worker rejects organism/assembly pairs absent from this manifest and passes topology metadata
to the runtime, so microbial circular references are not silently treated as human/linear indexes.

Rule Set 2 requests carry `genomic_contexts`, keyed by guide sequence. Each value must be the real
assembly-derived 30-mer: 4 upstream bases, the 20-bp spacer, the 3-bp PAM, and 3 downstream bases.
The worker verifies spacer placement and the NGG PAM and returns HTTP 422 when context is missing or
inconsistent. It never manufactures flanks or a PAM from the guide alone.

## Deploy and accept

Use `infra/compose/docker-compose.crispr.yml` or `infra/k8s/crispr-worker-deployment.yaml`. Point the
API at port 8105 with `CRISPR_BACKEND=http` and `CRISPR_SERVICE_URL=http://...:8105`.

`CELLXP_CRISPR_WORKER_MODE=contract_fixture` is only for deterministic contract tests. Its
sequence-QC heuristic refuses requests labeled `rule_set_2`, performs no genome-wide search, and
never reports Cas-OFFinder or CFD as active.

After deploying real human and microbial indexes:

```bash
CELLXP_LIVE_CRISPR_URL=http://localhost:8105 \
CELLXP_CRISPR_TEST_30BP_CONTEXT=<real-assembly-derived-30mer> \
pytest -m live tests/live/test_live_crispr_worker.py
```

A skipped test or contract-fixture result is not acceptance evidence.

The packaged worker resolves `GenomicInterval` targets against the attested FASTA, enumerates SpCas9
NGG sites on both strands, extracts real strand-oriented 30-mers, and composes Rule Set 2 with
Cas-OFFinder/CFD into ranked guides. Coordinates remain canonical 0-based: the reported cut site is
the cleavage boundary three bases 5' of the PAM. Circular references support origin-crossing target,
site, and context windows with cut coordinates normalized onto the contig.

Gene-string targets fail until the API/reference layer resolves them to a `GenomicInterval`.
Base/prime edit-outcome models are not packaged and fail explicitly; no efficiency is fabricated.
