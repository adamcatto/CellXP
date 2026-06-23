# Configuring AlphaGenome and Evo 2 Workers

CellXP calls sequence foundation models through a stable HTTP adapter. Model weights and GPU runtime
remain in a separately deployed worker; the API process only needs network access to that worker.

## Configuration

Set these variables in the API process environment:

| Variable | Required | Default | Meaning |
|---|---:|---|---|
| `ALPHAGENOME_SERVICE_URL` | yes | unset | AlphaGenome worker URL, such as `http://localhost:8106` |
| `EVO2_SERVICE_URL` | yes | unset | Evo 2 worker URL, such as `http://localhost:8107` |
| `ALPHAGENOME_SERVICE_TOKEN` | no | unset | Bearer token sent to the worker |
| `EVO2_SERVICE_TOKEN` | no | unset | Bearer token sent to the Evo 2 worker |
| `SEQUENCE_MODEL_SERVICE_TIMEOUT_SECONDS` | no | `120` | Per-request HTTP timeout |
| `ALPHAGENOME_MODEL_REVISION` | no | `remote` | Pinned model/worker revision recorded in provenance |
| `EVO2_MODEL_REVISION` | no | `remote` | Pinned Evo 2 revision recorded in provenance |

Construct the backend at composition time; do not read deployment configuration in agent nodes:

```python
from cellxp.services.alphagenome import AlphaGenomeService, RoutedHttpModelBackend

backend = RoutedHttpModelBackend.from_environment()
service = AlphaGenomeService(model_backend=backend)
```

Both URLs are required for the routed backend. Missing configuration returns `None`, so operations
report `unsupported`. Transport and response-contract errors become recoverable backend failures.

## Images and model acquisition

AlphaGenome and Evo 2 use separate Dockerfiles (`infra/docker/alphagenome-worker.Dockerfile` on
port 8106 and `infra/docker/evo-worker.Dockerfile` on port 8107). Their machine-readable manifests
live under `cellxp/services/alphagenome/model_manifests/`. Acquire the pinned Evo checkpoint with
checksum verification:

```bash
python scripts/acquire_sequence_model.py \
  src/backend/cellxp/services/alphagenome/model_manifests/evo2.json /models
```

The images now select packaged runtime factories by default:

- `create_alphagenome_backend` uses the official `alphagenome==0.6.1` API client and requires
  `ALPHAGENOME_API_KEY`. It calls the documented `dna_client.create`, `score_variant`, and
  `predict_interval` APIs with AlphaGenome's 1-based `genome.Variant` and supported fixed windows.
- `create_evo2_backend` uses the official `evo2==0.6.0` `Evo2('evo2_7b', local_path=...)` SDK and
  its `score_sequences` method. `EVO2_WEIGHT_PATH` defaults to the checksum-verified manifest file.

These mappings were verified against the pinned upstream sources:
[AlphaGenome v0.6.1](https://github.com/google-deepmind/alphagenome/tree/v0.6.1), including its
[`DnaClient` source](https://github.com/google-deepmind/alphagenome/blob/v0.6.1/src/alphagenome/models/dna_client.py),
and Arc Institute's
[`Evo2` 0.6.0 source](https://github.com/ArcInstitute/evo2/blob/53f195997257c56c00e5ef8d33a54f5baad143a6/evo2/models.py).
The Evo checkpoint URL, repository revision, size, and SHA-256 are immutable fields in
`model_manifests/evo2.json`.
Operator factory overrides remain available through `CELLXP_ALPHAGENOME_RUNTIME_FACTORY` and
`CELLXP_EVO2_RUNTIME_FACTORY`, but are not required for the packaged images.

AlphaGenome provider-hosted weights are not redistributed. Evo 2 coordinate-only variant and track
requests fail closed because its official SDK requires sequence context while the current CellXP
request carries only coordinates. AlphaGenome four-way splice gain/loss also fails closed until a
pinned scorer policy maps official score outputs to that calibrated contract; no score is invented.

## Worker contract

The worker implements JSON `POST` endpoints under `/v1`:

- `/score-variants`
- `/score-sequences`
- `/predict-tracks`
- `/score-splicing`

Request and response bodies match the Pydantic schemas in
`cellxp.services.alphagenome.schemas`. The worker must validate the selected model against organism
and assembly, pin its weights/revision, and return confidence and provenance fields. Track arrays too
large for inline delivery must be persisted by the worker and returned through `storage_ref`.

## Verification

The network-free unit suite uses `httpx.MockTransport`:

```bash
.venv/bin/pytest -q tests/unit/test_alphagenome_http_backend.py
```

`GET /health` exposes readiness, mode, revisions, and manifest digest; `GET /version` returns the
non-secret manifest. `CELLXP_SEQUENCE_WORKER_MODE=fixture` enables deterministic contract fixtures
only. Production readiness additionally requires `ALPHAGENOME_API_KEY` or the verified Evo checkpoint.
Fixture output is not live acceptance evidence.

Live worker checks must be opt-in and marked `live` (and `gpu` when applicable); they must never run
in the default unit suite:

```bash
CELLXP_LIVE_ALPHAGENOME_URL=http://localhost:8106 \
CELLXP_LIVE_EVO2_URL=http://localhost:8107 \
pytest -m "live and gpu" tests/live/test_live_sequence_model_workers.py
```

The opt-in suite performs real AlphaGenome variant scoring and Evo 2 sequence likelihood in addition
to health/version checks. Do not claim T7 acceptance from skipped tests; archive the actual command,
worker manifests, model revisions, hardware, and results.
