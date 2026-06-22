# Configuring AlphaGenome and Evo 2 Workers

CellXP calls sequence foundation models through a stable HTTP adapter. Model weights and GPU runtime
remain in a separately deployed worker; the API process only needs network access to that worker.

## Configuration

Set these variables in the API process environment:

| Variable | Required | Default | Meaning |
|---|---:|---|---|
| `ALPHAGENOME_SERVICE_URL` | yes | unset | AlphaGenome worker URL, such as `http://localhost:8103` |
| `EVO2_SERVICE_URL` | yes | unset | Evo 2 worker URL, such as `http://localhost:8104` |
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
port 8103 and `infra/docker/evo-worker.Dockerfile` on port 8104). Their machine-readable manifests
live under `cellxp/services/alphagenome/model_manifests/`. Acquire the pinned Evo checkpoint with
checksum verification:

```bash
python scripts/acquire_sequence_model.py \
  src/backend/cellxp/services/alphagenome/model_manifests/evo2.json /models
```

AlphaGenome's package is an API client; provider-hosted weights are not redistributed. Its image
requires an authorized production runtime/API binding.

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
only. Production mode fails closed until a real runtime is bound, and fixture output is not live
acceptance evidence.

Live worker checks must be opt-in and marked `live` (and `gpu` when applicable); they must never run
in the default unit suite:

```bash
CELLXP_LIVE_ALPHAGENOME_URL=http://localhost:8103 \
CELLXP_LIVE_EVO2_URL=http://localhost:8104 \
pytest -m "live and gpu" tests/live/test_live_sequence_model_workers.py
```
