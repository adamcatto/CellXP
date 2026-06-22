# Running GPU Workers

The structure worker serves ESMFold protein monomers and Boltz-2 complexes, nucleic acids, and
protein–ligand predictions on one NVIDIA GPU. It is isolated from the API, retains ESMFold in memory
after first use, bounds Boltz subprocesses with a hard timeout, and writes PDB/mmCIF coordinates to
the configured content-addressed object store.

## Pinned runtime

| Component | Pin |
|---|---|
| ESMFold weights | `facebook/esmfold_v1@75a3841ee059df2bf4d56688166c8fb459ddd97a` |
| Boltz package/default Boltz-2 weights | `boltz[cuda]==2.2.1` |
| Worker image | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime` |

The Boltz cache downloaded by 2.2.1 must remain paired with that package version. Runtime provenance
records the ESMFold commit or `boltz2@2.2.1`; coordinate payloads use immutable `cas/<sha256>` keys.

## Prepare models

Model acquisition is opt-in and is never part of default setup or CI:

```bash
scripts/download_models.sh --structure all --cache-dir /opt/cellxp/models
```

Use `--dry-run` to validate commands without network access. ESMFold downloads through the
Hugging Face CLI at its immutable commit. Boltz downloads through the exactly pinned package's
official downloader.

## Docker Compose

Prerequisites are Docker Compose, the NVIDIA Container Toolkit, one visible NVIDIA GPU, at least
24 GB VRAM for ordinary inputs (larger inputs can require substantially more), and adequate model
cache disk space.

```bash
docker compose -f infra/compose/docker-compose.gpu.yml up --build structure-worker
curl --fail http://localhost:8102/health
```

Configure the API with `STRUCTURE_BACKEND=http` and
`STRUCTURE_SERVICE_URL=http://structure-worker:8102` (or the reachable host URL). The default
`STRUCTURE_BACKEND=none` preserves an honest unsupported result when no worker is deployed.

The Compose volume persists `/models`; first inference downloads missing Boltz files if they were not
pre-seeded. Set `STRUCTURE_JOB_TIMEOUT_SECONDS` to the deployment budget. The worker uses one Uvicorn
process so the warm ESMFold model is not duplicated in VRAM.

## Live smoke tests

Live tests are T7 and explicitly excluded from default CI. Run them only after mounting the pinned
cache and activating the GPU runtime:

```bash
CELLXP_LIVE_STRUCTURE=1 \
MODEL_CACHE_DIR=/opt/cellxp/models \
STRUCTURE_DEVICE=cuda \
pytest -m "live and gpu" tests/live/test_structure_models.py
```

The ESMFold test folds a short monomer; the Boltz-2 test folds a short two-chain complex. A missing
CUDA runtime, missing pinned cache, timeout, non-zero Boltz exit, or missing coordinate/confidence
output fails loudly. The worker never opts into the remote MSA server; Boltz uses explicit local
single-sequence mode to prevent unannounced sequence egress.

## Kubernetes

`infra/k8s/worker-deployment.yaml` requests one `nvidia.com/gpu`, mounts the
`cellxp-structure-models` PVC, and reads `OBJECT_STORE_URL` from the `cellxp-runtime` Secret. Replace
the example image tag with an immutable registry digest before production deployment. Object storage
must be shared with the API; use the in-repo `s3://bucket/prefix` backend with AWS credentials or an
S3-compatible endpoint for separate Kubernetes nodes. A `file://` store is node-local and therefore
only suitable when the API and worker share the same persistent volume.
