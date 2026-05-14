# streaMLytics — developer Makefile
# Run from the repo root. Most targets assume Docker is up and the Windows venv
# at venv/Scripts/python.exe is in place (we are WSL-side calling Windows binaries).

PYTHON  := venv/Scripts/python.exe
PG_CONT := $(shell docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)

.PHONY: help up down logs test lint migrate dashboard sync clean graph graph-update graph-html hooks-install

help:        ## List available targets
	@grep -E '^[a-z_-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*##' '{printf "  %-12s %s\n", $$1, $$2}'

up:          ## docker-compose up -d (postgres + airflow)
	docker-compose up -d
	@sleep 3 && docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'postgres_spotify|airflow'

down:        ## docker-compose down (keeps volumes)
	docker-compose down

logs:        ## Tail Airflow scheduler logs
	docker-compose logs -f airflow-scheduler

test:        ## Pytest suite — test_api.py auto-skips if dev extras absent
	$(PYTHON) -m pytest tests/ -q

lint:        ## Ruff lint on src/ and tests/
	ruff check src/ tests/

migrate:     ## Apply every migrations/*.sql idempotently against the live PG
	@if [ -z "$(PG_CONT)" ]; then echo "Postgres container not running. Run 'make up' first."; exit 1; fi
	@for f in migrations/*.sql; do \
		echo ">> $$f"; \
		docker exec -i $(PG_CONT) psql -U postgres -d spotify_etl < $$f; \
	done

dashboard:   ## Launch Streamlit dashboard (foreground, port 8501)
	cd src/dashboard && streamlit run app.py

sync:        ## uv sync --frozen + install pre-commit hooks (one-shot dev setup)
	uv sync --frozen
	@$(MAKE) --no-print-directory hooks-install

clean:       ## Remove Python and ruff caches
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .ruff_cache .pytest_cache

hooks-install: ## Install pre-commit hooks (ruff + secret scan + hygiene)
	@if ! command -v pre-commit >/dev/null 2>&1; then \
		echo "→ Installing pre-commit via pip..."; \
		pip install --user pre-commit >/dev/null || pip install pre-commit; \
	fi
	@pre-commit install
	@echo "✅ pre-commit hooks installed. Bypass once with: git commit --no-verify"
	@echo "   Run on all files manually: pre-commit run --all-files"

graph-update: ## Refresh graphify-out/graph.json + GRAPH_REPORT.md (AST only, no LLM)
	graphify update .
	@echo "graph.json updated: $$(stat -c '%y' graphify-out/graph.json)"

graph-html:   ## Re-render graphify-out/graph.html (standalone, no server needed)
	python3 tools/dev/graphify_render_html.py
	@echo "Open graphify-out/graph.html directly in your browser (file://)"

graph: graph-update graph-html ## Refresh graph.json + GRAPH_REPORT.md + graph.html in one shot
