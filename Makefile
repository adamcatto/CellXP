PYTHONPATH := src/backend

.PHONY: dev-api dev-frontend worker test lint typecheck render-graph

dev-api:
	PYTHONPATH=$(PYTHONPATH) uvicorn cellxp.api.main:app --reload

dev-frontend:
	cd src/frontend && pnpm dev

worker:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.jobs.worker

test:
	PYTHONPATH=$(PYTHONPATH) pytest

lint:
	ruff check src/backend tests

typecheck:
	mypy src/backend

render-graph:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.cli.render_graph
