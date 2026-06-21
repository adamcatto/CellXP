# Configuring AlphaGenome and Evo 2 Workers

CellXP calls sequence foundation models through a stable HTTP adapter. Model weights and GPU runtime
remain in a separately deployed worker; the API process only needs network access to that worker.

## Configuration

Set these variables in the API process environment:

| Variable | Required | Default | Meaning |
|---|---:|---|---|
| `ALPHAGENOME_SERVICE_URL` | yes | unset | Worker base URL, such as `http://localhost:8101` |
| `ALPHAGENOME_SERVICE_TOKEN` | no | unset | Bearer token sent to the worker |
| `ALPHAGENOME_SERVICE_TIMEOUT_SECONDS` | no | `120` | Per-request HTTP timeout |
| `ALPHAGENOME_MODEL_REVISION` | no | `remote` | Pinned model/worker revision recorded in provenance |

Construct the backend at composition time; do not read deployment configuration in agent nodes:

```python
from cellxp.services.alphagenome import AlphaGenomeService, HttpModelBackend

backend = HttpModelBackend.from_environment()
service = AlphaGenomeService(model_backend=backend)
```

When `ALPHAGENOME_SERVICE_URL` is unset, `from_environment()` returns `None` and service operations
report `unsupported`. Authentication failures, timeouts, non-success HTTP responses, and malformed
payloads are returned as recoverable backend failures by `AlphaGenomeService`.

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

Live worker checks must be opt-in and marked `live` (and `gpu` when applicable); they must never run
in the default unit suite.
