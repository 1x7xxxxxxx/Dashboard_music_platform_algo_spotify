# Étude R606 — l'architecture de REA contre la nôtre (2026-10-15)

**Suite de** `.claude/dev-docs/studies/2026-10-15-rea.md` (R605, la configuration). Celle-ci
compare l'**architecture** : couches, contrats, erreurs, configuration, isolation, tests,
observabilité, versionnage.

**Source** : lecture de morluto/rea par `gh api` le 2026-10-15 (v6.5.0, ~4 000 fichiers
suivis, sans clone ni installation) ; nos faits relevés dans le dépôt le même jour.

**Règle de ce document** : une différence où REA est **mieux optimisé** devient une ligne
de roadmap qui MESURE avant de décider (forme commune : mesurer → décider oui/non sur le
long terme → si oui, design revu par `code-critic` avant le code). Une différence
équivalente ou sans objet chez nous est écrite ici avec sa raison, sans ligne.

## REA en un schéma

```
CLI (src/cli) · MCP (src/server, src/main)        ← adaptateurs d'entrée
        ↓
composition (src/composition — seul point de câblage) · application (services)
        ↓
fournisseurs (ghidra, hopper, ida, kuna, android/JADX, browser…)
        ↓
process (OwnedCommand, prlimit, Job Objects)
        ↓
domain + contracts (purs : n'importent rien d'autre)
```

Imposé par `scripts/lib/module-boundaries.mjs` (analyse Babel des imports, chaînée dans
`npm run lint`), `.oxlintrc.json` (`no-restricted-imports`) et
`scripts/verify/architecture-guards.mjs`.

## Comparaison axe par axe

| # | Axe | REA (fichier) | Nous (fichier) | Mieux optimisé chez eux ? | Ligne |
|---|---|---|---|---|---|
| A1 | Frontières entre couches | 5 règles imposées en lint : `pure-layer`, `application-composition`, `provider-construction`… (`scripts/lib/module-boundaries.mjs`) | frontières de **données** gardées (bronze/argent/or : `tests/test_the_bronze_boundary_only_tightens.py`, `test_the_metrics_layer_only_grows.py`) ; frontières d'**import** non gardées — arcs montants `src/utils/platform_probes.py:109` → `src.dashboard.views`, `src/api/deps.py:9` → `src.dashboard.utils` | **Oui** | R616 |
| A2 | Un contrat, plusieurs consommateurs | `ToolContract` zod (`src/contracts/toolContractTypes.ts`) → enregistrement MCP, catalogue, digest, métadonnées de skills | Pydantic dans `src/models/meta_ads_validators.py` (écriture collecteur), modèles en ligne dans chaque `src/api/routers/*.py`, dashboard sans contrat ; métriques : `src/utils/metric_registry.py` (un registre, déjà) | **Oui**, pour les objets hors métriques | R617 |
| A3 | Erreurs | base `AnalysisError` à 27 `_tag`, type `Result`, projection stable `{code, category, retryable, remediation}` exportée en JSON Schema (`src/domain/analysisErrorBase.ts`, `src/contracts/errorSchemas.ts`) | 11 exceptions typées sans base commune (`CredentialLoadError`, `UnknownArtistError`, `PermanentFailure`…) ; un registre unique `app_error_log` alimenté par dashboard, API et DAGs (`src/utils/error_registry.py`) | **Oui**, sur la projection stable | R618 |
| A4 | Configuration | variables d'environnement validées par zod au démarrage, `Result<AppConfig, ConfigurationError>` (`src/config/environment.ts`, `parseConfig.ts`) | `config/config.yaml` + `.env` ; contrat env↔compose testé (`tests/test_env_contract.py`) ; pas de validation de schéma au démarrage | **Oui** | R619 |
| A5 | Architecture des tests | 12 projets Vitest par profondeur, chaque fichier dans un seul ; seuils de couverture par couche (85 % sur les contrats) (`scripts/lib/test-projects.mjs`, `vitest.config.ts`) | 876 fichiers sous `tests/` ; 3 marqueurs (`xdist_group`, `docs`, `real_http`) ; 6 éclats CI ; aucun seuil de couverture | **Oui**, sur les seuils par couche | R620 |
| A6 | Versionnage et compatibilité | release-please, digest SHA-256 du catalogue, détection de décalage client, guide de migration par rupture (`src/catalogIdentity.ts`, `docs/releasing.md`) | `pyproject.toml` en `0.1.0`, API en `1.0.0` (`src/api/main.py:78`), pas de CHANGELOG ni de `/v1` | **Oui**, mais sans consommateur externe connu | R621 |
| A7 | Messages d'erreur visibles | catalogue `docs/user-visible-errors.csv` | messages dispersés dans les vues et catalogues i18n ; défaut déjà payé : 14 messages qui nommaient un DAG | **Oui** | R622 |
| A8 | Isolation des appels externes | sous-processus avec délai, plafond de sortie, `prlimit` (1 Gio, 30 s CPU), Job Objects (`src/process/`) | aucun sous-processus ; délais gardés (`tests/test_every_network_call_has_a_deadline.py`), retry (`src/utils/retry.py`), disjoncteur en base (`src/utils/circuit_breaker.py`), `dagrun_timeout` dérivé (`src/utils/dag_timeouts.py`) | Non — équivalent pour notre surface | — |
| A9 | Budgets | budgets de **taille** de réponse MCP testés ; mesures temps/tokens hors tests | budgets **structurels** testés (graphiques, connexions, jauges du premier écran, connexion) | Non — équivalent ; aucun des deux n'a de budget de latence en test | — |
| A10 | Observabilité | journaux JSON pino sur stderr ; pas de métriques | Prometheus + Grafana (ADR-026), 4 familles de métriques, registre d'erreurs | Non — plus complet chez nous | — |
| A11 | Cache | cache des lectures « instantané » seulement, clé cible + profil | `st.cache_data` + couche or | Non — sans objet comparable | — |
| A12 | Contenu non fiable | marquage `untrusted_content` contre l'injection de prompt | aucun LLM ne lit les données des locataires | Non — sans objet | — |
| A13 | Enveloppe de preuve | `confidence` observé/dérivé/inféré + `limitations[]` dans chaque résultat (`src/domain/evidence.ts`) | `cause_evidence` sur les classes d'erreur ; rien sur les figures | Oui, côté produit | R614 (note R605, point 8) |

## Exigence d'architecture agentique — la machine se gère dans la baseline

**La mémoire WSL (VmmemWSL, page cache), le stockage (C:, D:, `ext4.vhdx`,
`docker_data.vhdx`), le CPU/GPU et les caches partagés (uv, Docker, LanceDB) se gèrent dans
`claude_code_deployment_baseline`, jamais dans un dépôt projet.**

Raison : une seule machine sert les 10 projets du parc (`tools/dev/fleet.json` de la
baseline). Une sonde ou une purge écrite ici ne verrait que streaMLytics, et une purge du
cache uv décidée par un projet coûte un re-téléchargement à tous les autres. REA n'a pas
cet axe (outil local sans parc) ; c'est une exigence propre à notre façon de travailler
avec des agents.

Ce que streaMLytics garde : les **consommateurs** de cette ressource, qui disent ce que
CE dépôt demande à la machine — le verrou `~/.cache/heavy-memory.lock` (`Makefile`,
`tools/dev/heavy_lock.py`), le plafond `SUITE_SCOPE`, `tools/dev/mem_trace.py` et le
calcul de workers `tools/dev/pytest_workers.py`.

Ce qui part dans la baseline (section « Machine : stockage, mémoire, caches » de son
`NEXT.md`) : les sondes d'espace et de mémoire reprises de `optimisation_own_machine`
(`sonde_espace.py`, `alerte_pc.py`), l'archivage des fichiers obsolètes avec son
inventaire généré et testé, la purge des caches, la compaction des vhdx et le `.wslconfig`
versionné.

## Ce que nous faisons mieux qu'eux

- **Frontière de données** (bronze/argent/or) gardée par cliquets — REA n'a pas de données
  persistées à protéger de cette façon.
- **Observabilité de production** (Prometheus, registre d'erreurs par empreinte, mails ops).
- **Discipline de décision** : roadmap gardée par hooks (R196), ADR (33), classes d'erreur
  avec preuves ; REA n'a ni ADR ni journal de décision.

## Bilan

13 axes comparés : **7 mieux optimisés chez REA** → R616–R622 ; 1 déjà en roadmap par la
note de configuration (A13 → R614) ; 5 équivalents ou sans objet, sans ligne.
