PYTHONPATH := src/backend
PYTHON ?= python
PNPM ?= pnpm

.PHONY: dev-api dev-frontend worker test lint typecheck frontend-build eval-smoke render-graph

dev-api:
	PYTHONPATH=$(PYTHONPATH) uvicorn cellxp.api.main:app --reload

dev-frontend:
	cd src/frontend && pnpm dev

worker:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.jobs.worker

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -m "not slow and not live and not gpu and not eval"

lint:
	$(PYTHON) -m ruff check src/backend tests evals

typecheck:
	$(PYTHON) -m mypy src/backend

frontend-build:
	$(PNPM) --dir src/frontend build

eval-smoke:
	$(PYTHON) evals/run_evals.py validate

render-graph:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.cli.render_graph
