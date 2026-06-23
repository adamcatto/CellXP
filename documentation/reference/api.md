# API Reference

The FastAPI application exposes health at `/health` and the versioned client contract under
`/api/v1`. Normative resource and wire schemas live in `specs/interface/api_contracts.md`;
interactive OpenAPI documentation is available at `/docs` while the API is running.

## Local development lifecycle

The current single-user development adapter provides executable session and run lifecycle routes:

- create/list/get/update/delete sessions, with optimistic revision checks;
- create/list/get/reproduce/cancel runs, with session-scoped `client_request_id` deduplication;
- list run steps and evidence;
- list hash-chain-verified run audit records;
- answer blocking clarification and review interactions;
- fetch artifact manifests/content and create review-enforced exports;
- consume ordered SSE events and replay after `Last-Event-ID` or `last_event_id`.

Start it with `make dev-api`. A minimal request flow is:

```bash
curl -sS -X POST http://localhost:8000/api/v1/sessions \
  -H 'content-type: application/json' \
  -d '{"type":"variant_interpretation","title":"Variants","defaults":{"organism":"human","assembly":"GRCh38"}}'
```

Use the returned session ID with `POST /api/v1/sessions/{session_id}/runs`, including a non-empty
`client_request_id`. The response contains the run ID and SSE stream URL.

## Deployment boundary

`cellxp.api.runtime.LocalRuntime` is process-local and suitable only for deterministic contract
tests. Production uses the queued runtime with Postgres/Redis graph executors. Artifact export
descriptors and audit records are durable; payload bytes use the configured file or S3-compatible
object store. Actionable export returns `409` until approval. `GET /runs/{run_id}/audit` returns
entries plus `chain_valid`; `false` is an integrity failure.

## Verification

The T4 network-free lifecycle tests use FastAPI's in-process client and the real supervisor graph:

```bash
python -m pytest tests/e2e/test_chat_variant_query.py tests/e2e/test_artifact_generation.py
python -m pytest tests/e2e/test_artifact_review_api.py
```

They require no Ollama, database, Redis, or external biological services.
