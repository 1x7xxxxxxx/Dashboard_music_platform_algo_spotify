# streaMLytics — developer Makefile
# Run from the repo root. Most targets assume Docker is up and the Windows venv
# at venv/Scripts/python.exe is in place (we are WSL-side calling Windows binaries).

# ── Pourquoi cette résolution et pas `venv/Scripts/python.exe` en dur (2026-09-15) ──
# Mesuré ce jour-là : `make test` ne lançait **aucun test**. Le venv Windows ne porte
# pas `pytest-xdist`, donc le hook `pytest_configure_node` déclaré dans
# `tests/conftest.py` y est un hook INCONNU — `pluggy` lève `PluginValidationError`,
# pytest sort en INTERNALERROR avec `rc=3` et « no tests ran in 0.05s ».
#
# Un rc non nul, donc pas un silence — mais un rc qui ne ressemble pas à un échec de
# test, sur une cible qu'on lance justement pour NE PAS lire la sortie en détail.
#
# Même forme que `GUIDE_PY` ci-dessous, qui avait déjà résolu le problème pour son
# propre besoin : préférer le venv Linux quand il est là, retomber sur le Windows
# sinon. Garde : `tests/test_the_make_target_uses_a_working_interpreter.py`.
PYTHON  := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo venv/Scripts/python.exe)
PG_CONT := $(shell docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)
# The guide PDF needs WeasyPrint's NATIVE stack (cairo/pango). The Windows venv in
# $(PYTHON) does not carry it; the Linux one does. Resolved here rather than in the
# recipe so `make guide` fails on its precondition (rule #10) and not mid-render.
# Also used by the artist-journey tools: the SYSTEM python3 carries a different
# Streamlit (1.54 vs 1.62 here), whose AppTest lacks `file_uploader` — which
# reported `upload_csv` as a dead end when it is not.
GUIDE_PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo $(PYTHON))
AUDIT_VENV := .audit-venv
PIP_AUDIT  := $(shell command -v pip-audit 2>/dev/null || echo $(AUDIT_VENV)/bin/pip-audit)

.PHONY: error-management-probe error-debt reopen-check-prod schema-declared dip-calibrate dip-calibrate-prod figure-contrast figure-contrast-baseline error-health error-health-check error-health-history roadmap-close roadmap-sync reopen-check night-status night-check night-start night-done night-park night-note loadtest-concurrency scale-check test-durations test-durations-missing catalogue-sync example-charts error-inbox error-inbox-check error-resolve gold-coverage gold-coverage-check error-families error-families-check help up down logs test test-changed lint migrate migrate-prod backup backup-test dashboard sync clean artist-sandbox graph graph-update graph-html hooks-install check-manifest audit audit-deps check-pipaudit config-check deploy artist-preflight artist-firstlook artist-firstlook-prod artist-preflight-prod canary tenant-check caddy-validate env-parity guide check-guide-deps roadmap-discipline

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
# d'être deux affirmations différentes.
#
# `--dist loadgroup` depuis le 2026-09-15, et le mot compte. `loadfile` gardait
# TOUS les tests d'un même fichier sur un même worker — une garantie donnée aux
# 367 fichiers pour les quelques-uns qui en ont besoin, et le prix était un long
# pôle : `tests/test_views_render_smoke.py` tenait 152,5 s à lui seul sur un
# worker pendant que les autres finissaient. Sous `loadgroup`, la distribution se
# fait test par test SAUF pour les fichiers portant `pytest.mark.xdist_group` —
# la liste explicite des exceptions, justifiée fichier par fichier (voir le
# marqueur dans `pyproject.toml`).
#
# Ce que ce changement retire : l'ordre intra-fichier n'est plus garanti. Un test
# qui dépendait de son voisin devient un échec INTERMITTENT, la pire forme.
# L'instrument qui le prouve est `pytest-randomly`, désactivé par défaut et
# rallumé à la demande : `.venv/bin/python -m pytest tests/ -q -p randomly`.
# ⚠️ CES DRAPEAUX SONT LA RAISON D'ETRE DES CIBLES `test*`. Un `pytest tests/` lance a la
# main les PERD et tourne en SERIE. Mesure le 2026-09-16, meme arbre et meme verdict des
# deux cotes (6 717 verts, 1 rouge) : **418 s avec, 1 146 s sans — ×2,74**. Il a ete lance six fois en une seance parce que `CLAUDE.md` le documentait
# ainsi — la doc est corrigee, et ce commentaire est ici pour que le prochain qui ouvre le
# Makefile voie le cout avant d'improviser.
#
# `--dist loadgroup` et pas `loadfile` : les tests marques `xdist_group` doivent tomber
# dans le meme worker (base partagee, port unique), sinon ils se marchent dessus.
#
# ⚠️ Et NE RIEN EDITER pendant qu'une suite complete tourne : son verdict decrira un arbre
# qui n'existe plus. Classe `a-verdict-from-a-tree-that-moved-under-it`, mesuree le
# 2026-09-12 — 3 « echecs » sur 4 n'existaient pas.
# ⚠️ `-n auto` A ETE REMPLACE le 2026-09-17, sur une suite TUEE PAR L'OOM en pleine
# seance longue — le noyau a choisi pytest. `auto` vaut `nproc` (8 ici), et chaque worker
# charge streamlit, plotly et pandas pour rendre des vues.
#
# ⚠️ Et la premiere mesure du cout etait FAUSSE, deux fois, de la meme facon : elle
# ECHANTILLONNAIT le RSS au lieu de lire le PIC. Ce depot a une lecon ecrite pour ca —
# « le plafond memoire se mesure en VmHWM, jamais en echantillonnant » — et je l'ai
# refaite. Pire, chercher « pytest » dans les lignes de commande ne voit AUCUN worker :
# xdist les lance par `execnet`, leur argv est un `python -c` anonyme. Deux essais ont
# rendu « 1 processus » puis « 2 » avant qu'on suive la FILIATION, qui ne ment pas.
#
# Les vrais chiffres, `tests/test_views_render_smoke.py` en `-n 2`, pics VmHWM :
#     508 Mo · 265 Mo (workers) + 126 Mo (controleur) = 899 Mo
# Un worker peut donc piquer a **508 Mo**, pas 300. Huit demandent ~4 Go avant de
# compter Postgres, Airflow, n8n et Ollama qui tournent a cote.
#
# Le compte se fait donc sur la memoire DISPONIBLE — la ressource qui manquait, pas les
# coeurs — moins une RESERVE, divisee par 700 Mo (le pic mesure, arrondi au-dessus),
# bornee entre 2 et `nproc`.
#
# ⚠️ **La reserve est passee de 2 a 4 Go apres une SECONDE mort par OOM, a `-n 6`.**
# Deux raisons mesurees, et aucune ne se devinait :
#
#   * `MemAvailable` SUR-PROMET en WSL2. Il compte le cache de pages comme disponible
#     (4,6 Go ici), mais le reclamer sous une rafale d'allocations est lent — le noyau
#     tue avant d'avoir fini. Le chiffre est vrai et inutilisable tel quel.
#   * Deux services legitimes tiennent **3,7 Go en permanence** sur ce poste :
#     `n8n-ollama` **2,53 Go** (un modele resident) et le serveur MCP `knowledge-rag`
#     **1,15 Go**. Ni l'un ni l'autre ne se tue pour lancer des tests.
#
# ⚠️ Reserve portee de 4 a 5 Go le 2026-09-17, sur un TROISIEME OOM — la suite tuee
# a **98 %**, apres 7 minutes. Le calcul avait bien baisse a `-n 3` ; ce qui manquait
# est ailleurs : il prend un instantane de `MemAvailable` AU LANCEMENT, et la memoire
# disponible PENDANT la course est plus basse — les derniers pourcents sont les rendus
# `AppTest` les plus lourds, et trois d'entre eux tombent ensemble.
#
# Un seuil calcule sur l'etat initial d'une ressource qui varie pendant l'usage est
# une mesure prise au mauvais instant. Le remede honnete serait de mesurer le PIC
# reel de la suite entiere ; en attendant, la reserve absorbe l'ecart. Une suite tuee rend un journal VIDE, et un journal
# vide se lit comme « rien ne tourne » — c'est le pire mode de panne pour une seance
# sans surveillance.
#
# `nproc` seul serait revenu au defaut ; la memoire seule pourrait demander 14 workers
# sur 8 coeurs. Les deux bornes comptent.
#
# ⚠️ 2026-09-25 : la réserve n'est PLUS fixe. n8n ne tourne plus que le dimanche et
# knowledge-rag décharge son modèle après 10 min : les 5 120 Mo réservaient pour deux
# croissances qui ne sont plus permanentes. `tools/dev/pytest_workers.py` réserve 1 536
# de base, +1 600 par serveur knowledge-rag dont le modèle peut encore charger, +3 600
# si Ollama ou une ingestion tourne — et imprime son raisonnement sur stderr. Une
# ingestion qui DÉMARRERAIT pendant la suite est exclue par `HEAVY_LOCK` (ci-dessous),
# pas détectée. Garde : tests/test_the_worker_count_follows_what_can_grow.py.
# `=` et non `:=` : calculé quand une cible de test s'en sert, pas à chaque `make`.
PYTEST_WORKERS = $(shell $(PYTHON) tools/dev/pytest_workers.py 2>/dev/null || echo 2)
PYTEST_DIST = -n $(PYTEST_WORKERS) --dist loadgroup

# Tenu pendant une suite ; `run_book_drop.sh` (knowledge-rag) et `rag-mail-run.sh` (n8n)
# sautent leur passe horaire tant qu'il l'est — une ingestion charge 1,5 à 3,5 Go, et un
# instantané pris au lancement ne peut pas la voir arriver. Non bloquant côté tests :
# si une ingestion le tient déjà, la suite part quand même, avec la réserve élargie.
# `$$HOME` résolu par bash, jamais `$(HOME)` : make importe l'environnement dans ses
# variables (tests/test_a_make_variable_does_not_collide_with_the_environment.py).
HOLD_HEAVY_LOCK = mkdir -p "$$HOME/.cache"; exec 9>"$$HOME/.cache/heavy-memory.lock"; flock -n 9 || echo "ingestion en cours : verrou non pris, reserve elargie";

# ── Les tests qui ne lisent QUE des documents (2026-09-15) ──
# Portés par `pytestmark = pytest.mark.docs`. La liste est ici en clair parce que
# `--ignore` doit l'avoir AVANT la collecte : `-m "not docs"` collecte d'abord et
# désélectionne ensuite, donc il ne fait pas économiser le coût dominant.
#
# Ce que ça retire, mesuré : 38,2 s, dont **32 s pour le seul
# `test_the_gold_coverage_only_improves.py`**, qui recalcule toute la carte de la
# couche or.
#
# La ROADMAP n'y est PAS, à dessein : `test_roadmap_index_is_honest.py`,
# `test_roadmap_two_files.py` et `test_the_resume_header_is_checked.py` tiennent
# l'état que `/resume` lit en premier — et le 2026-09-15 au matin, ce fichier
# annonçait une tâche ouverte close depuis cinq jours. Ils tournent toujours.
#
# Garde de cohérence : `tests/test_the_doc_marker_matches_what_make_skips.py`
# échoue si un fichier marqué `docs` manque à cette liste, ou l'inverse.
DOC_TESTS := tests/test_error_class_index_is_complete.py \
             tests/test_the_error_class_families_only_improve.py \
             tests/test_the_error_class_health_only_improves.py \
             tests/test_the_gold_coverage_only_improves.py \
             tests/test_the_views_map_lists_every_view.py
DOC_IGNORE := $(foreach f,$(DOC_TESTS),--ignore=$(f))

test:        ## [180 s mesuré le 2026-09-25 — 4 workers, pile Docker up] Suite COMPLÈTE, drapeaux de la CI — la barrière avant de livrer
	@# La sortie va DANS UN FICHIER, et ce n'est pas du confort. Le 2026-09-16, j'ai
	@# conclu QUATRE FOIS qu'une suite etait « morte en route » ; les quatre fois elle
	@# tournait encore. Les executions passaient par `| tail -6`, qui ne rend rien avant
	@# la fin du tube : aucune progression, donc rien pour distinguer « avance » de
	@# « morte ». Avec ce journal, `tail -3 .pytest-last.log` tranche en une seconde.
	@#
	@# ⚠️ `$${PIPESTATUS[0]}` et bash EXPLICITE : `cmd | tee f` rend le code de `tee`,
	@# c'est-a-dire 0 quoi qu'il arrive. Une barriere avant de livrer qui rend toujours
	@# vert serait infiniment pire que lente.
	@bash -c '$(HOLD_HEAVY_LOCK) set -o pipefail; $(PYTHON) -m pytest tests/ -q $(PYTEST_DIST) 2>&1 | tee .pytest-last.log'; \
	  rc=$$?; echo "   journal complet : .pytest-last.log"; exit $$rc

test-fast:   ## [= test −38 s] La suite SANS les tests de documents — avant de commiter
	@echo '⏩ sans les tests de documents — make test-docs les lance, make test lance tout.'
	@bash -c '$(HOLD_HEAVY_LOCK) $(PYTHON) -m pytest tests/ -q $(PYTEST_DIST) $(DOC_IGNORE)'

test-docs:   ## [~38 s] Seulement les tests de documents — après avoir touché un document généré
	$(PYTHON) -m pytest $(DOC_TESTS) -q

loadtest-concurrency: ## La concurrence RÉELLE, par navigateurs. URL=… [LOGIN=… PASSWORD=…]
	@# Le seul chiffre que `loadtest_dashboard.py` ne peut pas produire : il rend en
	@# SÉRIE puis divise, et il le dit lui-même (lignes 27-40). Ici N onglets cliquent
	@# ENSEMBLE, ce qui est la définition de la concurrence.
	@[ -n "$(URL)" ] || { echo "❌ set URL=https://…"; exit 1; }
	$(PYTHON) tools/loadtest_concurrency.py --url "$(URL)" \
	  $(if $(LEVELS),--levels $(LEVELS),) $(if $(REPS),--reps $(REPS),) \
	  $(if $(LOGIN),--user $(LOGIN),) $(if $(PASSWORD),--password $(PASSWORD),)

# ⚠️ `LOGIN=` et non `USER=` — trouvé le 2026-09-17 en lançant la mesure R114.
# `USER` est une variable d'ENVIRONNEMENT standard du shell, et `make` importe
# l'environnement dans ses variables. `make loadtest-concurrency URL=…` sans autre
# argument partait donc avec `--user timothe`, silencieusement : la cible basculait
# en mode AUTHENTIFIÉ sans qu'on le demande, avec un identifiant qui n'est pas un
# compte de l'application et sans mot de passe.
#
# Ce n'est pas cosmétique sur CETTE cible : le mode authentifié « mesure une vraie
# page et ÉCRIT dans `usage_events` » (docstring de l'outil). Une mesure de charge
# qui se croit anonyme et qui écrit dans les données d'usage pollue précisément la
# table que `scale_check.sh` interroge pour décider s'il faut des répliques.
#
# Garde : `tests/test_a_make_variable_does_not_collide_with_the_environment.py`.

scale-check: ## Les 2 déclencheurs de R87 (répliques), rejoués. PROD_SSH=user@host
	@# Une décision qu'on ne sait pas relire se périme en silence. ADR-014 § « Comment
	@# relire cette décision » liste ses commandes sans les avoir outillées ; ici elles
	@# s'exécutent. La requête exclut canaris et bac à sable depuis le 2026-09-16 —
	@# l'ancienne comptait notre propre locataire d'essai comme un utilisateur, et le
	@# pic passait de 6 à 12 pour cette seule raison.
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@PROD_SSH=$(PROD_SSH) bash tools/scale_check.sh

test-durations: ## Régénère .test_durations — SORT EN ERREUR 1 QUAND ELLE RÉUSSIT, voir ci-dessous
	@# EN SÉRIE, à dessein : `--store-durations` sous xdist n'agrège pas proprement,
	@# et ce fichier sert à RÉPARTIR — une durée fausse déséquilibre un shard entier.
	@# Quand le lancer : quand `test_the_shards_are_balanced_by_real_durations.py`
	@# rougit, c'est-à-dire quand trop de fichiers neufs n'ont aucune durée connue.
	@# Puis commiter `.test_durations`.
	@#
	@# ⚠️ ELLE SORT EN ERREUR 1 QUAND ELLE RÉUSSIT, et ce n'est pas un défaut :
	@# `test_the_shards_are_balanced_by_real_durations` fait partie de la suite qu'on
	@# lance ici. Il s'exécute AVANT que `--store-durations` n'écrive le fichier en fin
	@# de session, il voit donc l'ANCIEN et rougit. Le fichier est écrit juste après, et
	@# il passe au lancement suivant.
	@#
	@# Mesuré le 2026-09-17 : 1 rouge sur 6 987, et ce rouge-là est exactement le garde
	@# qui a motivé la commande. Ne PAS le désélectionner pour « faire vert » : on
	@# perdrait le seul signal qui dit que le fichier est périmé. Lire le rouge,
	@# vérifier qu'il n'y en a qu'UN et que c'est celui-là, puis commiter.
	@#
	@# Coût sur ext4 : **297 s en série** pour 7 054 tests (1 146 s sur /mnt/c avant R117).
	$(PYTHON) -m pytest tests/ -q --store-durations

catalogue-sync: error-health error-families gold-coverage test-durations-missing ## Tout ce qu'une édition du catalogue ou un test NEUF périme, en une commande (~60 s)
	@# Le 2026-09-26, en /loop R169 : chaque lot touchait le catalogue et/ou ajoutait un
	@# test, et chacun des quatre documents générés a fait rougir la CI ou la porte au
	@# moins une fois, un par un — santé, familles, carte or, durées. Les régénérer
	@# ensemble est le geste ; les oublier un par un était le défaut.
	@echo "✅ catalogue-sync : santé, familles, carte or et durées régénérées — commiter les quatre"

error-management-probe: ## [MINUTES] Chaque porte du catalogue d'erreurs refuse-t-elle son défaut ? (R184)
	@# Un défaut fabriqué par porte, dans un worktree jetable, contre les VRAIES portes. Tourne
	@# aussi chaque nuit (security-nightly.yml, job error-management-probe).
	@[ -x "$(PYTHON)" ] || { echo "❌ $(PYTHON) introuvable. Run: make sync"; exit 1; }
	@$(PYTHON) tools/dev/probe_error_management.py

test-durations-missing: ## [SECONDES] Durées des SEULS fichiers de tests inconnus de .test_durations
	@# Le 2026-09-26, la CI de main est restée ROUGE toute une nuit — 60 exécutions —
	@# sur un seul garde : `test_the_durations_file_still_describes_this_suite`, plafond
	@# 0, et chaque fichier de test NEUF arrivait sans durée. Le remède documenté,
	@# `test-durations`, relance la suite entière en série (297 s) ; celui-ci ne lance
	@# que les fichiers manquants. `pytest-split` FUSIONNE (sans `--clean-durations`) :
	@# les durées connues restent, les neuves s'ajoutent. En série, comme l'autre.
	@test -x $(PYTHON) || { echo "❌ interpréteur absent. Run: make sync"; exit 1; }
	@# Au niveau du TEST, pas du fichier : la CI vérifie aussi chaque node-id
	@# (`check_durations_are_collectable.py`), et un test ajouté à un fichier connu,
	@# ou renommé, n'est vu que là. `--fix` retire les fantômes, mesure les manquants,
	@# puis REFAIT la collecte pour rendre le verdict.
	$(PYTHON) tools/dev/check_durations_are_collectable.py --fix

test-changed: ## [SECONDES] Seulement les tests atteignables depuis le diff — LA cible de la boucle de code (règle 16)
	@# Journal comme `make test` : le 2026-09-25 le verdict de cette cible a été tronqué
	@# (« 281 lines truncated ») par un filtre de sortie, même à travers `tee`. Un
	@# fichier ne se tronque pas ; `tail -3 .pytest-last.log` rend le verdict entier.
	@# `xargs -r` : une sélection VIDE (aucun fichier modifié) lançait `pytest -q` sans
	@# cible, c'est-à-dire la suite entière. `|| true` : sous pipefail, un `grep` qui
	@# ne trouve rien sortirait 1 et ferait passer « rien à tester » pour un échec.
	@# Durations BEFORE the tests (2026-09-26): main went red three times that day on « test
	@# collecté sans durée », which only CI measured, and the suite's own file-level check
	@# fails first — a step after a green run never ran. Any test file changed (tree or
	@# unpushed commits, subfolders included) ⇒ one collection (~8 s) + the new tests only.
	@if { git status --porcelain -- tests; git diff --name-only @{u}.. -- tests 2>/dev/null; } \
	   | grep -qE '(^|/)test_[^/]*\.py$$'; then \
	  $(MAKE) --no-print-directory test-durations-missing; fi
	@bash -c '$(HOLD_HEAVY_LOCK) set -o pipefail; $(PYTHON) .claude/scripts/select_tests.py | { grep -v "^#" || true; } \
	  | xargs -r $(PYTHON) -m pytest -q $(PYTEST_DIST) 2>&1 | tee .pytest-last.log'; \
	  rc=$$?; echo "   journal complet : .pytest-last.log"; [ $$rc -eq 0 ] || exit $$rc; \
	  bash -c 'set -o pipefail; $(PYTHON) .claude/scripts/check_guards_are_env_independent.py \
	    --changed 2>&1 | tee -a .pytest-last.log'

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

index-report: ## Index jamais parcourus, séparés en « intouchables » et « à arbitrer »
	@if [ -z "$(PG_CONT)" ]; then echo "❌ Postgres n'est pas en marche. Lancer : make up"; exit 1; fi
	@bash tools/index_report.sh

db-app-role: ## Pose le mot de passe du rôle applicatif. APP_DB_PASSWORD='…' make db-app-role
	@if [ -z "$(PG_CONT)" ]; then echo "❌ Postgres n'est pas en marche. Lancer : make up"; exit 1; fi
	@bash tools/db_app_role.sh set

db-role-check: ## Vérifie que le rôle applicatif n'est pas superutilisateur et suffit
	@if [ -z "$(PG_CONT)" ]; then echo "❌ Postgres n'est pas en marche. Lancer : make up"; exit 1; fi
	@bash tools/db_app_role.sh check

backup:      ## Dump spotify_etl → backups/*.sql.gz (+ retention)
	@if [ -z "$(PG_CONT)" ]; then echo "Postgres container not running. Run 'make up' first."; exit 1; fi
	@bash tools/db_backup.sh

backup-test: ## Restore the latest backup into a throwaway DB + verify (drill)
	@if [ -z "$(PG_CONT)" ]; then echo "Postgres container not running. Run 'make up' first."; exit 1; fi
	@bash tools/db_restore_test.sh

example-charts: ## Régénère les 3 figures d'exemple de la mise en route (PNG committés)
	@python3 tools/dev/make_example_charts.py

error-inbox: check-db ## Registre des erreurs applicatives → .claude/dev-docs/error-inbox.md
	@python3 tools/error_inbox.py

# ⚠️ SEULE cible `*-check` de document qui dépende d'une ressource EXTERNE : ses trois
# sœurs dérivent du dépôt et peuvent donc comparer n'importe où, y compris en CI ;
# celle-ci a besoin de `app_error_log`. D'où un troisième code de sortie, **2**, pour
# « je n'ai RIEN pu vérifier » — un contrôle qui rendrait 0 sur une base injoignable
# ressemblerait à un contrôle qui a vérifié quelque chose. Elle ne déclare donc PAS
# `check-db` en prérequis : ce serait déléguer à `make` un échec que le script sait
# nommer beaucoup mieux, et écraser le code 2 par un code 1 indistinct.
error-inbox-check: ## Le registre décrit-il encore la base ? 0 à jour · 1 périmé · 2 RIEN vérifié (base injoignable) — le blocage hors-base vient de tests/test_the_error_inbox_and_its_pointer_agree.py
	@python3 tools/error_inbox.py --check

gold-coverage: ## Carte de la couche or → .claude/dev-docs/gold-coverage.md
	@python3 tools/dev/gold_coverage.py

# ⚠️ CE COMMENTAIRE A ÉTÉ CORRIGÉ LE 2026-09-18, ET L'HISTOIRE VAUT D'ÊTRE LUE.
#
# Il disait, à juste titre au 2026-09-17, que les trois cibles `*-check` n'étaient
# lancées par AUCUN workflow et que le blocage réel passait par les tests pytest.
# C'était vrai, et c'était le problème : les deux tests qui tenaient la fraîcheur
# RÉGÉNÉRAIENT le document entier à chaque exécution locale — 23,06 s et 6,97 s, soit
# **30,0 s de la suite** pour deux assertions.
#
# Depuis le 2026-09-18, `gold-coverage-check` et `error-health-check` sont lancées par
# `.github/workflows/ci.yml` (étape « Portes statiques »), et les deux tests coûteux
# sont retirés de la suite. La propriété est payée une fois par commit, et elle bloque
# la CI au lieu de ne bloquer que le développeur qui lançait la suite complète.
#
# `error-families-check` reste un geste manuel : son cliquet dans la suite coûte 0,07 s,
# il n'y avait rien à déplacer.
gold-coverage-check: ## Échoue si la carte ne décrit plus le dépôt — LANCÉE EN CI (étape « Portes statiques ») depuis le 2026-09-18
	@python3 tools/dev/gold_coverage.py --check

# ── R133 : les figures qu'un daltonien ne peut pas attribuer ──────────────────
# Stdlib seule (la colorimétrie est dans `src/dashboard/utils/colorimetry.py`, pas de
# dépendance d'exécution) — donc pas de précondition, règle transverse #10.
# ── R134 : le seuil du détecteur de creux, dérivé et non deviné ───────────────
# Lecture seule sur la base. Précondition explicite (règle transverse #10) : l'outil
# sort 2 avec « Lancer : make up » si la base est injoignable.
# ── R143 : ce que le depot declare contre ce que la base porte ────────────────
# Lecture seule. Precondition explicite : l'outil sort 2 avec « Lancer : make up ».
schema-declared: ## Divergences type declare (init_db + migrations) <-> base — lecture seule
	@python3 tools/dev/schema_declaration_check.py

dip-calibrate: ## Dérive le seuil de creux PAR TABLE sur les données réelles — lecture seule
	@python3 tools/dev/calibrate_dip_thresholds.py

# ⚠️ EN PRODUCTION, PAS `python3` SUR L'HÔTE — mesuré le 2026-09-20 : le serveur n'a
# pas `psycopg2`, tout y tourne en conteneur, et §17 du runbook prescrivait pourtant
# `python3 tools/dev/…` sur la machine. Le scheduler bind-monte `tools/`, donc il est
# le seul endroit où l'outil trouve à la fois le code ET la dépendance.
dip-calibrate-prod: ## Le même, contre la base de PRODUCTION. PROD_SSH=user@host
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'docker exec airflow_scheduler python3 /opt/airflow/tools/dev/calibrate_dip_thresholds.py'

figure-contrast: ## Rapport des figures sous le plancher d'attribution — NE BLOQUE RIEN
	@python3 tools/dev/figure_contrast_report.py

# ⚠️ À lancer SEULEMENT après avoir corrigé une figure, jamais pour faire taire la porte.
# Le cliquet `test_the_baseline_only_shrinks` refuse un total qui remonte.
figure-contrast-baseline: ## Régénère le plafond après une CORRECTION de figure
	@python3 tools/dev/figure_contrast_report.py --baseline

error-families: ## Familles de classes d'erreur → .claude/dev-docs/error-class-families.md
	@python3 tools/dev/error_class_families.py

# ── Séance longue ─────────────────────────────────────────────────────────────
# Le protocole : .claude/dev-docs/roadmap/night-run.md — à lire à CHAQUE réveil.
# `night_run.py` n'utilise que la stdlib et `git` ; pas de dépendance d'exécution,
# donc pas de précondition (règle transverse #10, cibles « fichier seul »).

# ⚠️ Ces deux cibles ne rédigent RIEN. Elles font le geste MÉCANIQUE d'une rotation —
# retirer la ligne d'index, recaler l'ancre de reprise — et refusent de fermer une tâche
# dont l'entrée d'archive n'est pas écrite dans une forme que le test de conservation
# reconnaît. Le texte reste écrit à la main : une rotation qui rédigerait aussi la leçon
# produirait des leçons de machine.
#
# Mesuré le 2026-09-17, et c'est la raison d'être de ces cibles : la procédure en prose
# (`.claude/commands/roadmap-done.md`) est correcte et détaillée, et elle a laissé passer
# DEUX erreurs dans une seule séance parce qu'elle ne nomme ni l'ancre ni le format
# d'archive. Les tests les ont rattrapées — après coup. Ici, l'outil refuse avant.
reopen-check: ## Les conditions de RÉOUVERTURE des tâches closes sont-elles remplies ? — exit 1 si oui
	@python3 tools/dev/reopen_check.py

# ⚠️ DEUX conditions portent sur du TRAFIC (`daily_ops_metrics`, alimentée par le DAG de
# production). Sans `PROD_SSH` elles rendent INDÉCIDABLE — c'est voulu : jusqu'au
# 2026-09-20 elles mesuraient la base LOCALE et rendaient un chiffre qui ne décrivait
# rien (R116 : 0 en local contre 2 en prod ; R131 : 5 contre 4).
reopen-check-prod: ## Le même, avec les conditions de TRAFIC mesurées en prod. PROD_SSH=user@host
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@PROD_SSH=$(PROD_SSH) python3 tools/dev/reopen_check.py

roadmap-close: ## LE geste de livraison (R199) : écrit l'entrée d'archive si besoin, retire la ligne, recale l'ancre — make roadmap-close ID=R128 [NOTE="…"]
	@test -n "$(ID)" || { echo "❌ ID= manquant. Ex : make roadmap-close ID=R128"; exit 1; }
	@python3 tools/dev/roadmap.py close "$(ID)" --note "$(NOTE)"

roadmap-sync: ## Remet l'ancre de reprise d'accord avec les deux tables d'index
	@python3 tools/dev/roadmap.py sync

night-status: ## Où j'en suis : unité en cours, arbre, roadmap, parkings, journal (~1 s)
	@python3 tools/dev/night_run.py status
	@python3 tools/dev/roadmap_discipline.py || true

roadmap-discipline: ## R197 — actions de dev sans ligne de roadmap AVANT, critic, âge des lignes ; ≠ 0 si à redire. DAYS=14 BASELINE=1 WRITE=1
	@command -v git >/dev/null 2>&1 || { echo "❌ git introuvable — installer git"; exit 1; }
	@python3 tools/dev/roadmap_discipline.py --days $(or $(DAYS),14) $(if $(BASELINE),--baseline,) $(if $(WRITE),--write,)

night-check: ## Les invariants d'une séance longue ; ≠ 0 s'il y a à redire (~1 s)
	@python3 tools/dev/night_run.py check

night-start: ## J'ouvre une unité — make night-start TASK=R122 W="lot 6"
	@test -n "$(TASK)" || { echo "❌ TASK= manquant. Ex: make night-start TASK=R122 W=\"lot 6\""; exit 1; }
	@python3 tools/dev/night_run.py start "$(TASK)" "$(W)"

night-done: ## Je la ferme — make night-done TASK=R122 W="plafond 332 → 326"
	@test -n "$(TASK)" || { echo "❌ TASK= manquant."; exit 1; }
	@python3 tools/dev/night_run.py done "$(TASK)" "$(W)"

night-park: ## Bloqué : j'écris la question et je passe — make night-park TASK=R116 W="…"
	@test -n "$(TASK)" || { echo "❌ TASK= manquant."; exit 1; }
	@python3 tools/dev/night_run.py park "$(TASK)" "$(W)"

night-note: ## Un fait à ne pas perdre — make night-note TASK=R122 W="…"
	@test -n "$(TASK)" || { echo "❌ TASK= manquant."; exit 1; }
	@python3 tools/dev/night_run.py note "$(TASK)" "$(W)"

error-families-check: ## Échoue si la taxonomie ne décrit plus le catalogue — geste MANUEL ; le blocage vient de tests/test_the_error_class_families_only_improve.py
	@python3 tools/dev/error_class_families.py --check

error-debt: ## Les classes à payer d'abord (récidivées sans garde auto-prouvant, puis cause inconnue) + plafonds resserrables
	@# La dette du catalogue était FIGÉE : 306 gardes non prouvés et 140 causes inconnues,
	@# inchangés sur six commits (mesuré 2026-09-25). Les cliquets empêchent la hausse ;
	@# ceci propose la baisse. Aucun plafond n'est resserré automatiquement (code-critic).
	@python3 tools/dev/error_debt.py $(or $(N),10)

error-health: ## Santé du catalogue de classes → .claude/dev-docs/error-class-health.{json,md}
	@# UN SEUL COMMIT depuis le 2026-09-18 — et ce qui a change vaut d'etre lu.
	@#
	@# Ce bloc disait « DEUX COMMITS, et ce n'est pas un defaut » : le document tirant
	@# ses faits de l'historique GIT du catalogue, commiter le catalogue les changeait,
	@# donc l'instantane commite a cote etait perime d'exactement un. Le remede etait
	@# correct. Il coutait **50 des 104 commits du 2026-09-18** — 48 % du journal —
	@# chacun demarrant une execution de CI complete aussitot annulee.
	@#
	@# La cause n'etait pas le commit, c'etait le NOMBRE : `_revisions()` ignorait
	@# l'etat du disque. Il compte desormais l'arbre de travail comme une revision EN
	@# ATTENTE, donc le total vaut N+1 des deux cotes du commit. C'est aussi la lecture
	@# honnete de la grandeur — « combien d'etats distincts de ce catalogue ont existe ».
	@#
	@# Garde : tests/test_a_snapshot_survives_the_commit_of_its_source.py, trois
	@# mutations vues rouges.
	@# L'historique GIT de ce JSON EST la série temporelle — rien de temporel n'est
	@# stocké dedans. Il rejoue les révisions du catalogue et compte les commits qui
	@# AJOUTENT une ligne d'historique à une classe : une récidive mesurée, qu'aucun
	@# champ tenu à la main ne peut contredire.
	@$(PYTHON) tools/dev/error_class_health.py

error-health-check: ## Échoue si l'instantané de santé ne décrit plus le catalogue — LANCÉE EN CI (étape « Portes statiques ») depuis le 2026-09-18
	@$(PYTHON) tools/dev/error_class_health.py --check

error-health-history: ## L'évolution d'une métrique, lue dans l'historique git du JSON
	@# Ne stocke RIEN : stocker la série créerait une seconde définition de la même
	@# grandeur, et ce dépôt sait ce que ça coûte.
	@git log -L '/"recurrence": {/','/^    }/':.claude/dev-docs/error-class-health.json \
	  --format='%C(yellow)%h %ad%Creset' --date=short | head -200

error-resolve: check-db ## Ferme une entrée du registre. FP=<12 car.> NOTE="..."
	@test -n "$(FP)" || { echo "❌ FP manquant. Ex: make error-resolve FP=a1b2c3d4e5f6 NOTE=\"corrigé par …\""; exit 1; }
	@test -n "$(NOTE)" || { echo "❌ NOTE manquant : une entrée fermée sans raison est une entrée perdue."; exit 1; }
	@python3 tools/error_inbox.py --resolve "$(FP)" --note "$(NOTE)"

check-env:   ## Vérifie imports + base joignable (BLOQUANT) ; incohérences pip RAPPORTÉES seulement
	@# ⚠️ Deux corrections du 2026-09-17, trouvées en auditant les refus du dépôt sous
	@# la question « ce critère peut-il être faux dans l'usage prévu ? ».
	@#
	@# 1. LE PORT ÉTAIT EN DUR. `check-db` lit `DATABASE_URL` et en déduit hôte et port ;
	@#    celui-ci codait `127.0.0.1:5433`. Sur une machine où la base écoute ailleurs,
	@#    `make dashboard` échouait sur sa précondition pendant que `make error-inbox`
	@#    passait — même question, deux vérités. `deux-surfaces-deux-nombres`, appliqué
	@#    à un port. Les deux lisent désormais la même source.
	@#
	@# 2. LE NOM PROMETTAIT PLUS QUE LE CODE. L'aide disait « Verify … pip dep
	@#    coherence » alors que la ligne se termine par `|| true` : elle imprime et
	@#    continue, TOUJOURS. La moitié de la promesse était un rapport, pas un
	@#    contrôle. C'est délibéré — `pip check` remonte des conflits transitifs qu'on
	@#    ne peut pas tous corriger — mais ce n'était écrit nulle part, et un nom qui
	@#    promet une vérification qu'il ne fait pas est ce qui fait cesser de chercher.
	@python3 -c "import isodate, streamlit, plotly, pandas, psycopg2" 2>/dev/null \
		|| { echo "❌ Missing dashboard deps. Run: make sync"; exit 1; }
	@echo "— incohérences pip (RAPPORTÉES, non bloquantes) :"
	@python3 -m pip check 2>&1 | grep -E "^[^[:space:]]" | head -10 || true
	@python3 -c "import os,sys,socket;\
u=os.environ.get('DATABASE_URL');\
host,port=('127.0.0.1',5433) if not u else (u.split('@')[1].split(':')[0], int(u.split('@')[1].split(':')[1].split('/')[0]));\
s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex((host,port)))" 2>/dev/null \
		|| { echo "❌ Database unreachable. Run: make up  (or set DATABASE_URL)"; exit 1; }
	@# A fresh clone has NO hooks: its first commit would skip both secret scanners.
	@[ -n "$$CI" ] || [ -f "$$(git rev-parse --git-path hooks/pre-commit)" ] \
		|| { echo "❌ pre-commit hooks absent — a commit would skip the secret scan. Run: make hooks-install"; exit 1; }
	@echo "✅ env check passed (imports + base ; pip : voir au-dessus)"

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
	@$(GUIDE_PY) tools/artist_first_look.py $(if $(ARTIST),--artist $(ARTIST),)

artist-firstlook-prod: ## Same, against the code RUNNING IN PROD. PROD_SSH=user@host ARTIST=<id>
	@# `artist-firstlook` renders the LOCAL working tree against the LOCAL database
	@# on 127.0.0.1:5433 (see check-db). That answers "what will my change show an
	@# artist", not "what does the live app show one" — and this session measured a
	@# 15x gap between the two environments on import time alone.
	@test -n "$(PROD_SSH)" || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@scp -q tools/artist_first_look.py $(PROD_SSH):/tmp/afl.py
	@ssh $(PROD_SSH) 'docker cp /tmp/afl.py streamlytics_dashboard:/tmp/afl.py >/dev/null \
		&& docker exec streamlytics_dashboard python3 /tmp/afl.py $(if $(ARTIST),--artist $(ARTIST),) 2>/dev/null; \
		rm -f /tmp/afl.py; docker exec streamlytics_dashboard rm -f /tmp/afl.py'

artist-preflight-prod: ## Preflight contre la PRODUCTION. PROD_SSH=user@host ARTIST=<id>
	@# Ajoutee le 2026-09-03, apres avoir refait l incantation a la main. `tools/`
	@# n est monte dans AUCUN conteneur (contrainte connue), donc il faut l y copier
	@# avant de lancer — quatre commandes que personne ne retient, et dont l oubli
	@# fait croire que le preflight ne marche pas.
	@test -n "$(PROD_SSH)" || { echo "❌ set PROD_SSH=user@host"; exit 1; }
	@tar czf /tmp/_afp_tools.tgz tools/*.py
	@scp -q /tmp/_afp_tools.tgz $(PROD_SSH):/tmp/_afp_tools.tgz
	@ssh $(PROD_SSH) 'docker cp /tmp/_afp_tools.tgz streamlytics_dashboard:/tmp/ >/dev/null \
		&& docker exec -w /app streamlytics_dashboard sh -c "tar xzf /tmp/_afp_tools.tgz -C /app \
		&& python3 tools/artist_preflight.py $(if $(ARTIST),--artist $(ARTIST),) --diagnose"; \
		rm -f /tmp/_afp_tools.tgz'
	@rm -f /tmp/_afp_tools.tgz

artist-sandbox: check-db ## Locataire d'essai pour rejouer l'onboarding avec TES identifiants. RESET=1 / DELETE=1
	@$(PYTHON) tools/create_sandbox.py \
	  $(if $(SLUG),--slug $(SLUG),) $(if $(RESET),--reset,) $(if $(DELETE),--delete,)

artist-preflight: check-db ## Prove a NON-admin tenant works BEFORE inviting an artist (base LOCALE). ARTIST=<id>
	@# Five steps, stops at the first red: central apps present+authenticating,
	@# tenant identity declared, connection tests, data landed, no contaminated rows.
	@# Two beta sessions failed on things every one of these would have caught.
	@# Cette cible lit la base LOCALE (voir `check-db`). Passer PROD_SSH n'y change
	@# rien, et le croire coûte une séance : le 2026-09-03 elle a été lancée avec
	@# PROD_SSH et a testé le locataire 471, un canari LOCAL, pas la production.
	@# Un argument silencieusement ignoré est pire qu'un argument refusé.
	@test -z "$(PROD_SSH)" || { echo "❌ artist-preflight lit la base LOCALE — PROD_SSH est ignoré."; \
	  echo "   Pour la production : make artist-firstlook-prod PROD_SSH=$(PROD_SSH)"; \
	  echo "   Ou relancez sans PROD_SSH pour viser la base locale."; exit 1; }
	@$(GUIDE_PY) tools/artist_preflight.py $(if $(ARTIST),--artist $(ARTIST),)

dossier:     ## Régénère le dossier d'architecture (PDF, non versionné). Requiert mmdc.
	@command -v mmdc >/dev/null || { echo "❌ mermaid-cli absent. Run: npm i -g @mermaid-js/mermaid-cli"; exit 1; }
	@python3 tools/dev/architecture_dossier/main.py docs/streamlytics-architecture-et-qualite-des-donnees.pdf

metric-check: check-db ## Les nombres que le produit CALCULE s'accordent-ils entre eux ?
	@python3 tools/metric_check.py

tenant-check: check-db ## Report rows sitting under a tenant they cannot belong to (read-only)
	@$(GUIDE_PY) tools/tenant_contamination_check.py

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
	@echo "▶ exec bit (git index, not the disk — /mnt/c never reports it back)…"
	@python3 .claude/scripts/check_exec_bit.py || true
	@echo "▶ mermaid blocks…"
	@# In `audit` (nightly) and NOT in the PR gate: `mmdc` is a dev-only dependency CI
	@# does not install, so a blocking signature would go red on every machine without
	@# it — `permanently-red-guard-reports-nothing`, which is how a check gets deleted.
	@python3 .claude/scripts/check_mermaid.py || true

config-check: ## Check the .claude/ config itself: dangling paths, class schema, prose-only signatures
	@# python3 + stdlib only — no runtime dependency, so no fail-fast prerequisite
	@# is required (CLAUDE.md rule 10 exempts file-only targets).
	@python3 .claude/scripts/check_config_refs.py
	@# Un outil que rien n'invoque n'est pas neutre : c'est une AFFIRMATION qu'une
	@# chose est couverte. Ce depot l'a mesure ailleurs — 33 spawns pour les agents
	@# nommes dans une regle imperative, 0 sur 23 pour ceux nommes dans un tableau.
	@python3 .claude/scripts/audit_unreachable_tools.py
	@# La meme affirmation pour un AGENT, prouvee par l'EXECUTION et non par le texte :
	@# `test_every_declared_agent_has_a_trigger_that_can_fire` prouve que l'arete est
	@# DESSINEE ; ceci prouve qu'elle LIE (un Spawn reel dans les transcriptions). Rouge
	@# sur « DECLARED, NEVER INVOKED » ; SKIP sans transcriptions (CI). Ajoute le
	@# 2026-09-25 : strategic-plan-architect etait a 0 sur 51 sessions, rien ne le disait.
	@python3 .claude/scripts/usage_report.py --check
	@python3 .claude/scripts/audit_runner.py --prose
	@python3 .claude/scripts/audit_runner.py --coverage
	@# ⚠️ Ajoute le 2026-09-16 : le plan de R122 disait « `error-health-check`
	@# entre dans `make config-check` pour la boucle locale », et il n'y etait pas.
	@# Une etape annoncee et non cablee se lit comme une etape qui tourne — c'est
	@# `a-runbook-that-names-a-command-nobody-can-run`, un cran plus haut.
	@python3 tools/dev/error_class_health.py --check
	@# ⚠️ `audit_runner --fields` a ete RETIRE d'ici le 2026-09-16, et pas rendu vert.
	@# Le commentaire qui le justifiait (« RED on 29/29 legacy classes ») etait PERIME :
	@# le catalogue porte `<!-- fields-ratchet: 0 -->` depuis longtemps, la dette est a
	@# zero. J'ai repete ce commentaire comme un fait sans lire le marqueur deux lignes
	@# plus loin.
	@#
	@# Le vrai defaut etait ailleurs et le `|| true` le cachait : `_fields()` appelle
	@# `_write_ratchet()`, donc cette cible ECRIVAIT dans `error-classes.md` — un gate
	@# qui modifie l'artefact qu'il juge. La meme question est posee par classe, SANS
	@# ecrire, par `tests/test_every_error_class_is_complete.py`.
	@#
	@# `--fields --strict` reste disponible a la main.
	@$(PYTHON) tools/dev/error_class_health.py --check

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
	@# Compare des DEUX cotes a partir du premier `{`. Le depliage etait asymetrique
	@# jusqu'au 2026-09-16 : il retirait l'en-tete du depot et pas celui de la cible.
	@# Or la procedure de deploiement ecrite en tete de `deploy/Caddyfile` fait un `scp`
	@# du fichier ENTIER : des que la prod a recu l'en-tete, la porte a vu 89 lignes de
	@# divergence pour ZERO ligne fonctionnelle. Une porte qui ne peut plus passer est
	@# une porte qu'on apprend a ignorer — classe `a-gate-that-can-never-be-green`.
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cat /etc/caddy/Caddyfile' > /tmp/_caddy_live 2>/dev/null || 	  { echo "  ⚠ no /etc/caddy/Caddyfile on the target — skipped"; true; }
	@if [ -s /tmp/_caddy_live ]; then 	  sed -n '/^{/,$$p' deploy/Caddyfile > /tmp/_caddy_repo; 	  sed -n '/^{/,$$p' /tmp/_caddy_live > /tmp/_caddy_live_body; 	  if diff -q /tmp/_caddy_repo /tmp/_caddy_live_body >/dev/null; then 	    echo "  ✅ deploy/Caddyfile == what Caddy is serving"; 	  else 	    echo "  ⚠ CADDY DRIFT — the repo copy is not what runs:"; 	    diff /tmp/_caddy_repo /tmp/_caddy_live_body | head -20; 	    echo "  Reconcile before editing either one (see deploy/Caddyfile header)."; 	    exit 1; 	  fi; 	fi
	@echo "▶ host-config drift: deploy/host/ vs la cible…"
	@# Ajouté le 2026-09-16, même raison que la comparaison du Caddyfile juste au-dessus :
	@# un fichier d'HÔTE modifié directement sur la cible n'est comparé à rien. Le
	@# Caddyfile du dépôt était resté périmé depuis juin sans que personne le sache, et
	@# un correctif y avait été écrit en croyant toucher le fichier vivant.
	@# `daemon.json` est plus discret encore : son absence ne casse rien, elle laisse
	@# seulement les journaux grossir sans borne.
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cat /etc/docker/daemon.json 2>/dev/null' > /tmp/_daemon_live || true
	@if [ -s /tmp/_daemon_live ]; then \
	  if diff -q deploy/host/docker-daemon.json /tmp/_daemon_live >/dev/null; then \
	    echo "  ✅ deploy/host/docker-daemon.json == /etc/docker/daemon.json"; \
	  else \
	    echo "  ⚠ HOST-CONFIG DRIFT — /etc/docker/daemon.json diffère du dépôt:"; \
	    diff deploy/host/docker-daemon.json /tmp/_daemon_live | head -20; \
	    exit 1; \
	  fi; \
	else \
	  echo "  ⚠ /etc/docker/daemon.json ABSENT sur la cible — les journaux de conteneurs"; \
	  echo "     grossissent SANS LIMITE. Voir deploy/host/README.md pour l'appliquer."; \
	  exit 1; \
	fi
	@echo "▶ deploy-drift: $(PROD_REPO) HEAD vs origin/main…"
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cd $(PROD_REPO) && git fetch -q origin main && if [ "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" ]; then echo "  ✅ deployed code == origin/main"; else echo "  ⚠ DEPLOY DRIFT: server HEAD != origin/main — run on prod: git pull --ff-only origin main && docker compose up -d --build api dashboard"; git -C $(PROD_REPO) log --oneline HEAD..origin/main | head -5; exit 1; fi'

deploy:      ## Deploy origin/main to prod. SERVICE="api dashboard" · MIGRATE=1 applique les migrations en attente avant le build
	@[ -n "$(PROD_SSH)" ] || { echo "❌ set PROD_SSH=user@host (e.g. make deploy PROD_SSH=root@1.2.3.4 SERVICE=api)"; exit 1; }
	@ssh -o ConnectTimeout=10 $(PROD_SSH) 'cd $(PROD_REPO) && MIGRATE=$(MIGRATE) bash tools/deploy.sh $(SERVICE)'

dashboard: check-env   ## Launch Streamlit dashboard (foreground, port 8501)
	streamlit run src/dashboard/app.py

sync:        ## uv sync --frozen --extra dev + pre-commit hooks (one-shot dev setup)
	# `--extra dev` comme la CI (.github/workflows/ci.yml). Sans lui, la cible
	# annoncée « one-shot dev setup » produisait un environnement SANS pytest,
	# ruff ni pre-commit — et enchaînait ensuite sur `hooks-install`, qui a besoin
	# de pre-commit. Constaté le 2026-08-24 en réinstallant le lock : la suite ne
	# démarrait plus (`unrecognized arguments: -n auto`).
	@# ⚠️ Règle transverse #10 : une cible d'exécution NOMME sa commande de réparation.
	@# `sync` était la SEULE cible de ce fichier sans prérequis NI garde en ligne à
	@# l'ajouter (mesuré le 2026-09-17 : 34 lignes brutes → 16 cibles → 12 sans
	@# prérequis → 4 sans aucun garde, dont 3 déjà triées P3 en mai). Sans ça, un
	@# poste neuf reçoit `uv: command not found` et doit deviner.
	@command -v uv >/dev/null 2>&1 || { \
		echo "❌ uv absent — c'est lui qui installe l'environnement de ce dépôt."; \
		echo "   Réparer : pip install uv"; exit 1; }
	uv sync --frozen --extra dev
	@$(MAKE) --no-print-directory hooks-install

clean:       ## Remove Python and ruff caches
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .ruff_cache .pytest_cache

hooks-install: ## Install pre-commit hooks (ruff + secret scan + hygiene)
	@# ⚠️ Le repli se décide sur le RÉSULTAT, pas sur le code de sortie.
	@# `pip install --user` RÉUSSIT en posant le binaire dans un répertoire qui n'est
	@# pas sur le PATH : `||` ne se déclenche donc jamais, et `pre-commit install`
	@# tombait à la ligne suivante sur un « command not found » qui n'accuse pas la
	@# bonne étape. Classe `a-fallback-that-runs-when-the-first-branch-succeeded`,
	@# trouvée le 2026-09-22 — et le balayage de 2026-09-18 l'avait ÉCARTÉE comme faux
	@# positif de `pre-commit`/`commit` : le motif matchait, sur le mauvais mot.
	@# Le patron est celui de `tools/db_backup.sh:207` — on relit ce qu'on vient de
	@# faire au lieu de croire le code de sortie.
	@if ! command -v pre-commit >/dev/null 2>&1; then \
		echo "→ Installing pre-commit via pip..."; \
		pip install --user pre-commit >/dev/null 2>&1 || true; \
		command -v pre-commit >/dev/null 2>&1 || pip install pre-commit || true; \
	fi
	@command -v pre-commit >/dev/null 2>&1 || { \
		echo "❌ pre-commit toujours introuvable après installation."; \
		echo "   'pip install --user' peut réussir en écrivant hors du PATH."; \
		echo "   Réparer : pip install pre-commit   (ou ajouter ~/.local/bin au PATH)"; \
		exit 1; }
	@pre-commit install
	@# gitleaks (provider formats) next to detect-secrets (entropy) — pinned, checksummed.
	@bash tools/dev/install_gitleaks.sh
	@echo "✅ pre-commit hooks installed. Bypass once with: git commit --no-verify"
	@echo "   Run on all files manually: pre-commit run --all-files"

graph-update: ## Refresh graphify-out/graph.json + GRAPH_REPORT.md (AST only, no LLM)
	graphify update .
	@echo "graph.json updated: $$(stat -c '%y' graphify-out/graph.json)"

graph-html:   ## Re-render graphify-out/graph.html (standalone, no server needed)
	python3 tools/dev/graphify_render_html.py
	@echo "Open graphify-out/graph.html directly in your browser (file://)"

graph: graph-update graph-html ## Refresh graph.json + GRAPH_REPORT.md + graph.html in one shot
