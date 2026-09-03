# streaMLytics — developer Makefile
# Run from the repo root. Most targets assume Docker is up and the Windows venv
# at venv/Scripts/python.exe is in place (we are WSL-side calling Windows binaries).

PYTHON  := venv/Scripts/python.exe
PG_CONT := $(shell docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)
# The guide PDF needs WeasyPrint's NATIVE stack (cairo/pango). The Windows venv in
# $(PYTHON) does not carry it; the Linux one does. Resolved here rather than in the
# recipe so `make guide` fails on its precondition (rule #10) and not mid-render.
GUIDE_PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo $(PYTHON))
AUDIT_VENV := .audit-venv
PIP_AUDIT  := $(shell command -v pip-audit 2>/dev/null || echo $(AUDIT_VENV)/bin/pip-audit)

.PHONY: help up down logs test test-changed lint migrate migrate-prod backup backup-test dashboard sync clean artist-sandbox graph graph-update graph-html hooks-install check-manifest audit audit-deps check-pipaudit config-check deploy artist-preflight artist-firstlook artist-firstlook-prod canary tenant-check caddy-validate env-parity guide check-guide-deps

help:        ## List available targets
	@grep -E '^[a-z_-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*##' '{printf "  %-12s %s\n", $$1, $$2}'

up:          ## docker-compose up -d (postgres + airflow)
	docker-compose up -d
	@sleep 3 && docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'postgres_spotify|airflow'

down:        ## docker-compose down (keeps volumes)
	docker-compose down

logs:        ## Tail Airflow scheduler logs
	docker-compose logs -f airflow-scheduler

# Mêmes drapeaux de distribution que `.github/workflows/ci.yml`. Mesuré le
# 2026-08-30 sur ce dépôt : 238 s en sériel, 151 s ici (1,57x). Le gain n'est pas
# la raison principale — c'est que « vert en local » et « vert en CI » cessent
# d'être deux affirmations différentes. `--dist loadfile` garde les tests d'un
# même fichier sur le même worker, ce dont dépendent ceux qui portent un état de
# module.
PYTEST_DIST := -n auto --dist loadfile

test:        ## Pytest suite (mêmes drapeaux que la CI) — test_api.py auto-skips if dev extras absent
	$(PYTHON) -m pytest tests/ -q $(PYTEST_DIST)

test-changed: ## Seulement les tests atteignables depuis ce qui a changé (règle 16)
	@$(PYTHON) .claude/scripts/select_tests.py | grep -v '^#' | xargs $(PYTHON) -m pytest -q $(PYTEST_DIST)

check-guide-deps: ## (internal) fail fast if WeasyPrint is unavailable, rule #10
	@$(GUIDE_PY) -c "import weasyprint" >/dev/null 2>&1 || { \
	  echo "❌ WeasyPrint is not importable by $(GUIDE_PY)."; \
	  echo "   The guide PDF needs its native stack (cairo/pango), which CI deliberately"; \
	  echo "   does NOT install (.github/workflows/ci.yml: 'dashboard-only, not CI')."; \
	  echo "   Run: make sync"; exit 1; }

guide: check-guide-deps ## Rebuild docs/guides/*.pdf + .guide_fingerprint from the sources
	@# The ONLY way to refresh the guide. The fingerprint is written by the same command,
	@# never on its own: one updated alone would certify an artefact nobody rebuilt.
	@# Enforcement lives in tests/test_the_shipped_guide_is_the_current_guide.py, NOT here
	@# and not in `sync-check` — the check has to run where WeasyPrint is absent (CI), so
	@# it compares digests instead of rendering. This target is the remedy it names.
	@$(GUIDE_PY) -m src.dashboard.guides.guide_pdf

lint:        ## Ruff lint on src/ and tests/
	ruff check src/ tests/

migrate:     ## Apply every migrations/*.sql against the live PG, and NAME what errored
	@# The logic lives in tools/migrate.sh, not here, for the reason deploy.sh
	@# exists: `make` is not installed on the production server, so a recipe that
	@# only works through `make` cannot be run where it matters. See R37.
	@bash tools/migrate.sh

migrate-prod: ## Apply migrations on PROD over ssh (no `make` needed there). PROD_SSH=user@host
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host (e.g. make migrate-prod PROD_SSH=root@1.2.3.4)"; exit 1; }
	@echo "⚠️  Migrations run AFTER the code that expects them (class migration-ahead-of-its-code)."
	@echo "   Deploy first if you have not: make deploy PROD_SSH=$(PROD_SSH)"
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cd $(PROD_REPO) && bash tools/migrate.sh'

backup:      ## Dump spotify_etl → backups/*.sql.gz (+ retention)
	@if [ -z "$(PG_CONT)" ]; then echo "Postgres container not running. Run 'make up' first."; exit 1; fi
	@bash tools/db_backup.sh

backup-test: ## Restore the latest backup into a throwaway DB + verify (drill)
	@if [ -z "$(PG_CONT)" ]; then echo "Postgres container not running. Run 'make up' first."; exit 1; fi
	@bash tools/db_restore_test.sh

check-env:   ## Verify critical imports + pip dep coherence (canary check)
	@python3 -c "import isodate, streamlit, plotly, pandas, psycopg2" 2>/dev/null \
		|| { echo "❌ Missing dashboard deps. Run: make sync"; exit 1; }
	@python3 -m pip check 2>&1 | grep -E "^[^[:space:]]" | head -10 || true
	@python3 -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(('127.0.0.1',5433)))" 2>/dev/null \
		|| { echo "❌ PostgreSQL unreachable on localhost:5433. Run: make up"; exit 1; }
	@echo "✅ env check passed"

canary:      ## Create/refresh the canary tenant preflight needs. NAME="…" SPOTIFY=… YOUTUBE=… SOUNDCLOUD=… META=…
	@[ -n "$(NAME)" ] || { echo '❌ set NAME="…", e.g. make canary NAME="Canary 1x7" SPOTIFY=<artist id>'; exit 1; }
	@python3 tools/create_canary.py --name "$(NAME)" \
		$(if $(SLUG),--slug "$(SLUG)",) \
		$(if $(SPOTIFY),--spotify "$(SPOTIFY)",) \
		$(if $(YOUTUBE),--youtube "$(YOUTUBE)",) \
		$(if $(SOUNDCLOUD),--soundcloud "$(SOUNDCLOUD)",) \
		$(if $(META),--meta "$(META)",) \
		$(if $(DRY_RUN),--dry-run,)

artist-firstlook: check-db ## Show what a BRAND-NEW artist sees, page by page. ARTIST=<id> optional
	@# Not "did it raise" — the render-smoke already answers that, and it was green
	@# through both failed beta sessions. This prints what is ON THE SCREEN: titles,
	@# buttons, messages, and whether the page offers anything to do at all. The six
	@# defects of 2026-08-23 were all correct code that nothing reached.
	@python3 tools/artist_first_look.py $(if $(ARTIST),--artist $(ARTIST),)

artist-firstlook-prod: ## Same, but against the code RUNNING IN PRODUCTION. PROD_SSH=user@host
	@# `artist-firstlook` renders the LOCAL working tree against the LOCAL database
	@# on 127.0.0.1:5433 (see check-db). That answers "what will my change show an
	@# artist", not "what does the live app show one" — and this session measured a
	@# 15x gap between the two environments on import time alone.
	@test -n "$(PROD_SSH)" || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@scp -q tools/artist_first_look.py $(PROD_SSH):/tmp/afl.py
	@ssh $(PROD_SSH) 'docker cp /tmp/afl.py streamlytics_dashboard:/tmp/afl.py >/dev/null \
		&& docker exec streamlytics_dashboard python3 /tmp/afl.py 2>/dev/null; \
		rm -f /tmp/afl.py; docker exec streamlytics_dashboard rm -f /tmp/afl.py'

artist-sandbox: check-db ## Locataire d'essai pour rejouer l'onboarding avec TES identifiants. RESET=1 / DELETE=1
	@$(PYTHON) tools/create_sandbox.py \
	  $(if $(SLUG),--slug $(SLUG),) $(if $(RESET),--reset,) $(if $(DELETE),--delete,)

artist-preflight: check-db ## Prove a NON-admin tenant works BEFORE inviting an artist. ARTIST=<id> optional
	@# Five steps, stops at the first red: central apps present+authenticating,
	@# tenant identity declared, connection tests, data landed, no contaminated rows.
	@# Two beta sessions failed on things every one of these would have caught.
	@python3 tools/artist_preflight.py $(if $(ARTIST),--artist $(ARTIST),)

tenant-check: check-db ## Report rows sitting under a tenant they cannot belong to (read-only)
	@python3 tools/tenant_contamination_check.py

check-db:    ## Fail fast if the app database is unreachable (prerequisite, rule #10)
	@python3 -c "import os,sys,socket;\
u=os.environ.get('DATABASE_URL');\
host,port=('127.0.0.1',5433) if not u else (u.split('@')[1].split(':')[0], int(u.split('@')[1].split(':')[1].split('/')[0]));\
s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex((host,port)))" 2>/dev/null \
		|| { echo "❌ Database unreachable. Run: make up  (or set DATABASE_URL)"; exit 1; }

chart-budget: ## Charts in the viewer's eye span per view (report-only; Few, IDD p.27)
	@python3 tools/dev/chart_budget.py

check-pipaudit: ## (internal) fail fast with the install command, rule #10
	@command -v pip-audit >/dev/null 2>&1 || test -x $(AUDIT_VENV)/bin/pip-audit || { \
	  echo "❌ pip-audit absent. Run: python3 -m venv $(AUDIT_VENV) && $(AUDIT_VENV)/bin/pip install pip-audit"; \
	  exit 1; }

audit-deps: check-pipaudit ## Known CVEs in requirements.txt (R22). Fails on anything not named below.
	@# PYSEC-2026-1325 (ecdsa 0.19.2) is ignored NAMED, not by lowering the bar:
	@# it is a Minerva timing attack on ECDSA *signing*, python-ecdsa has declared
	@# side channels out of scope so no fix version exists, and ecdsa arrives here
	@# only transitively via python-jose while our JWTs pin HS256 at both encode
	@# and decode (src/api/auth.py). Re-check that pin before extending this list.
	@$(PIP_AUDIT) -r requirements.txt --ignore-vuln PYSEC-2026-1325 \
	  && echo "✅ no actionable dependency vulnerability"

check-manifest: ## Assert pin parity across pyproject/requirements/uv.lock
	@python3 tools/dev/check_manifest_consistency.py && echo "✅ manifests consistent"

audit:       ## Sweep ALL error-class signatures (heuristic, non-blocking) — delegates to the catalogue
	@# Single source of truth: .claude/dev-docs/error-classes.md. audit_runner.py
	@# parses every class signature and runs it — adding a class to the catalogue
	@# sweeps it automatically (no hand-synced greps here anymore). Deterministic
	@# classes also block CI (ci.yml); this `--all` run is the nightly heuristic pass.
	@python3 .claude/scripts/audit_runner.py --all

config-check: ## Check the .claude/ config itself: dangling paths, class schema, prose-only signatures
	@# python3 + stdlib only — no runtime dependency, so no fail-fast prerequisite
	@# is required (CLAUDE.md rule 10 exempts file-only targets).
	@python3 .claude/scripts/check_config_refs.py
	@python3 .claude/scripts/audit_runner.py --prose
	@python3 .claude/scripts/audit_runner.py --coverage
	@# --fields is advisory: RED on 29/29 legacy classes. `|| true` keeps this target
	@# usable while still printing what is missing. Drop the `|| true` when it reaches 0.
	@python3 .claude/scripts/audit_runner.py --fields || true

# Prod connection for schema-check (override on the CLI; not committed to keep the
# host out of version control): make schema-check PROD_SSH=root@HOST PROD_PG=container
PROD_SSH  ?=
PROD_PG   ?= postgres_spotify_airflow
PROD_REPO ?= /opt/streamlytics
LOCAL_PG  ?= postgres_spotify_airflow
SERVICE   ?= api dashboard

schema-check: canon-pg ## Diff PROD schema vs canonical (init_db.sql + migrations) — needs Docker + SSH to prod
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host (e.g. make schema-check PROD_SSH=root@1.2.3.4)"; exit 1; }
	@echo "▶ dumping prod schema via ssh…"
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'docker exec -i $(PROD_PG) psql -U postgres -d spotify_etl -tA' < tools/dev/schema_fingerprint.sql > /tmp/_prod.tsv 2>/dev/null
	@python3 tools/dev/schema_drift_check.py /tmp/_prod.tsv /tmp/_canon.tsv

schema-check-local: canon-pg ## Diff the LOCAL dev database vs canonical — the drift no CI run can see
	@# CI and a throwaway database both start from canonical, so neither can ever
	@# report this. The developer's own database predates migrations and drifts in
	@# silence: measured 2026-08-21, soundcloud_tracks_daily.track_id was bigint
	@# locally against VARCHAR(50) canonical, and 7 tests failed with a type error
	@# on this machine only. Same fingerprint as `schema-check`, local side.
	@docker exec -i $(LOCAL_PG) psql -U postgres -d spotify_etl -tA < tools/dev/schema_fingerprint.sql > /tmp/_local.tsv 2>/dev/null \
		|| { echo "❌ local Postgres unreachable ($(LOCAL_PG)). Run: make up"; exit 1; }
	@python3 tools/dev/schema_drift_check.py /tmp/_local.tsv /tmp/_canon.tsv local

canon-pg: ## (internal) build the throwaway canonical database and fingerprint it
	@command -v docker >/dev/null 2>&1 || { echo "❌ docker required for the throwaway canonical DB."; exit 1; }
	@echo "▶ provisioning throwaway canonical Postgres from init_db.sql + migrations…"
	@docker rm -f canon_pg >/dev/null 2>&1 || true
	@docker run -d --name canon_pg -e POSTGRES_PASSWORD=x -e POSTGRES_DB=spotify_etl postgres:17 >/dev/null
	@for i in $$(seq 1 30); do docker exec canon_pg pg_isready -U postgres -d spotify_etl >/dev/null 2>&1 && break; sleep 1; done; sleep 2
	@docker exec -i canon_pg psql -U postgres -d spotify_etl -v ON_ERROR_STOP=0 -q < init_db.sql >/dev/null 2>&1
	@for f in $$(ls migrations/*.sql | sort); do docker exec -i canon_pg psql -U postgres -d spotify_etl -v ON_ERROR_STOP=0 -q < "$$f" >/dev/null 2>&1; done
	@docker exec -i canon_pg psql -U postgres -d spotify_etl -tA < tools/dev/schema_fingerprint.sql > /tmp/_canon.tsv 2>/dev/null
	@docker rm -f canon_pg >/dev/null 2>&1

env-parity:  ## Are the central-app credentials present in the containers that read them?
	@# Presence only — never a value. Runs against whatever containers are up locally;
	@# on the box it is a gate inside tools/deploy.sh. `make sync-check` compares the
	@# schema, the ledger, the tools mount and the Caddyfile — but no env var, and it
	@# cannot: the production docker-compose.yml is gitignored.
	@command -v docker >/dev/null 2>&1 || { echo "❌ docker not found — Run: install Docker"; exit 1; }
	@python3 tools/check_env_parity.py

caddy-validate: ## Validate deploy/Caddyfile with a real Caddy binary (docker, no prod access)
	@# Added 2026-08-23. `sync-check` proves the repo copy MATCHES what prod serves; nothing
	@# proved it is VALID. The 2026-08-22 edit was reloaded on the box and never checked by a
	@# Caddy binary from this repo — "image unavailable here" was assumed, not measured. It is
	@# available: this target pulls it. Certs are stood in with a throwaway self-signed pair so
	@# `tls <file> <file>` resolves; we validate SYNTAX, not the production certificates.
	@command -v docker >/dev/null 2>&1 || { echo "❌ docker not found — Run: install Docker, or validate on the box with 'caddy validate'"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "❌ Docker daemon unreachable — Run: docker-compose up -d"; exit 1; }
	@[ -f deploy/Caddyfile ] || { echo "❌ deploy/Caddyfile missing"; exit 1; }
	@tmp=$$(mktemp -d); \
	  openssl req -x509 -newkey rsa:2048 -nodes -keyout $$tmp/origin.key -out $$tmp/origin.pem \
	    -days 1 -subj "/CN=caddy-validate.invalid" >/dev/null 2>&1; \
	  out=$$(docker run --rm \
	    -v "$$(pwd)/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
	    -v "$$tmp/origin.pem:/etc/caddy/origin.pem:ro" \
	    -v "$$tmp/origin.key:/etc/caddy/origin.key:ro" \
	    caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile 2>&1); \
	  rm -rf $$tmp; \
	  if echo "$$out" | grep -q "Valid configuration"; then \
	    echo "  ✅ deploy/Caddyfile is a valid Caddy config"; \
	    echo "$$out" | grep -q "is not formatted" && \
	      echo "  ⚠ not gofmt-clean per 'caddy fmt' — do NOT reformat: sync-check compares this file BYTE-FOR-BYTE with what prod serves. Reformat on the box first, or accept the warning."; \
	    exit 0; \
	  else \
	    echo "  ❌ INVALID Caddy config:"; echo "$$out" | tail -20; exit 1; \
	  fi

sync-check: schema-check ## Full repo↔prod sync: schema-drift + migration-ledger + deploy-drift
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@echo "▶ migration-ledger + tool reachability on the target…"
	@bash tools/dev/check_prod_ledger.sh $(PROD_SSH) $(PROD_PG)
	@echo "▶ caddy-drift: deploy/Caddyfile vs /etc/caddy/Caddyfile on the target…"
	@# Added 2026-08-22. The repo copy had been stale since June — it still described
	@# Let's Encrypt while prod had moved to Cloudflare origin certs, and it lacked the
	@# log-redaction block. Nobody knew, because nothing compared them: this target
	@# checked the SCHEMA and the git HEAD, and a reverse proxy is neither. A patch was
	@# written into the repo copy believing it was the live one.
	@# Compared from the first `{` so the repo file may carry a comment header.
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cat /etc/caddy/Caddyfile' > /tmp/_caddy_live 2>/dev/null || 	  { echo "  ⚠ no /etc/caddy/Caddyfile on the target — skipped"; true; }
	@if [ -s /tmp/_caddy_live ]; then 	  sed -n '/^{/,$$p' deploy/Caddyfile > /tmp/_caddy_repo; 	  if diff -q /tmp/_caddy_repo /tmp/_caddy_live >/dev/null; then 	    echo "  ✅ deploy/Caddyfile == what Caddy is serving"; 	  else 	    echo "  ⚠ CADDY DRIFT — the repo copy is not what runs:"; 	    diff /tmp/_caddy_repo /tmp/_caddy_live | head -20; 	    echo "  Reconcile before editing either one (see deploy/Caddyfile header)."; 	    exit 1; 	  fi; 	fi
	@echo "▶ deploy-drift: $(PROD_REPO) HEAD vs origin/main…"
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cd $(PROD_REPO) && git fetch -q origin main && if [ "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" ]; then echo "  ✅ deployed code == origin/main"; else echo "  ⚠ DEPLOY DRIFT: server HEAD != origin/main — run on prod: git pull --ff-only origin main && docker compose up -d --build api dashboard"; git -C $(PROD_REPO) log --oneline HEAD..origin/main | head -5; exit 1; fi'

deploy:      ## Deploy origin/main to prod (pull --ff-only + --build + health). SERVICE="api dashboard"
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host (e.g. make deploy PROD_SSH=root@1.2.3.4 SERVICE=api)"; exit 1; }
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cd $(PROD_REPO) && bash tools/deploy.sh $(SERVICE)'

dashboard: check-env   ## Launch Streamlit dashboard (foreground, port 8501)
	streamlit run src/dashboard/app.py

sync:        ## uv sync --frozen --extra dev + pre-commit hooks (one-shot dev setup)
	# `--extra dev` comme la CI (.github/workflows/ci.yml). Sans lui, la cible
	# annoncée « one-shot dev setup » produisait un environnement SANS pytest,
	# ruff ni pre-commit — et enchaînait ensuite sur `hooks-install`, qui a besoin
	# de pre-commit. Constaté le 2026-08-24 en réinstallant le lock : la suite ne
	# démarrait plus (`unrecognized arguments: -n auto`).
	uv sync --frozen --extra dev
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
