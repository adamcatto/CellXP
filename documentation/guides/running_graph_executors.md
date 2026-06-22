# Running Graph Executors

Production API processes persist and enqueue run commands; they do not invoke LangGraph. Start the
local Postgres, Redis, API, and graph-executor stack with:

```bash
docker compose -f infra/compose/docker-compose.runtime.yml up --build
```

The API uses `RUNTIME_BACKEND=queued`. Executor containers use `RUNTIME_BACKEND=durable` and run
`python -m cellxp.jobs.graph_worker`. All executors for a deployment share `GRAPH_JOB_STREAM` and
`GRAPH_CONSUMER_GROUP`. Redis append-only persistence and Postgres durable checkpoints are required.
Commands use stable IDs, are reclaimed after an executor crash, retry up to their bounded attempt
limit, and then move to `<GRAPH_JOB_STREAM>:dead` for operator inspection.

The deterministic T2 lifecycle test uses SQLite and a recording queue, so it needs no services:

```bash
.venv/bin/pytest -q tests/integration/test_queued_graph_runtime.py
```

Queue lifecycle coverage is similarly network-free:

```bash
.venv/bin/pytest -q tests/unit/test_job_queue.py
```
