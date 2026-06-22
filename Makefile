PYTHONPATH := src/backend
PYTHON ?= python
PNPM ?= pnpm

.PHONY: setup download-models dev-api dev-frontend worker test test-browser lint typecheck frontend-build eval-smoke release-gates render-graph

setup:
	./scripts/setup.sh

download-models:
	./scripts/download_models.sh

dev-api:
	PYTHONPATH=$(PYTHONPATH) uvicorn cellxp.api.main:app --reload

dev-frontend:
	cd src/frontend && pnpm dev

worker:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.jobs.worker

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -m "not slow and not live and not gpu and not eval"

test-browser:
	corepack $(PNPM) --dir src/frontend test:browser

lint:
	$(PYTHON) -m ruff check src/backend tests evals

typecheck:
	$(PYTHON) -m mypy src/backend

frontend-build:
	$(PNPM) --dir src/frontend build

eval-smoke:
	$(PYTHON) evals/run_evals.py validate

release-gates:
	$(PYTHON) -m evals.release_gates $(EVIDENCE) $(if $(OUTPUT),--output $(OUTPUT),)

render-graph:
	PYTHONPATH=$(PYTHONPATH) python -m cellxp.cli.render_graph
