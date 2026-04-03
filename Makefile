FRONTEND_DIR := frontend
BACKEND_DIR := backend

.PHONY: frontend-install frontend-dev frontend-build backend-dev backend-install backend-check validate-manifest evaluate-baseline

frontend-install:
	npm --prefix $(FRONTEND_DIR) install

frontend-dev:
	npm --prefix $(FRONTEND_DIR) run dev -- --host

frontend-build:
	npm --prefix $(FRONTEND_DIR) run build

backend-install:
	uv sync --project $(BACKEND_DIR)

backend-dev:
	uv run --project $(BACKEND_DIR) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-check:
	uv run --project $(BACKEND_DIR) python -m compileall $(BACKEND_DIR)/app

validate-manifest:
	uv run --project $(BACKEND_DIR) python scripts/validate_manifest.py $(MANIFEST)

evaluate-baseline:
	uv run --project $(BACKEND_DIR) python scripts/evaluate_baseline.py $(MANIFEST)
