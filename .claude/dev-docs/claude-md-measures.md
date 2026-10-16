# Les mesures datées de CLAUDE.md

Type: Sub — référence passive
Uses: rien ; lu à la demande depuis les renvois « §n » de `CLAUDE.md`
Persists in: ce fichier

Déplacé de `CLAUDE.md` par R631 (2026-10-16) : ces blocs portaient la PREUVE des règles
(mesures, historique, ce qui a été refusé), pas la règle elle-même. `CLAUDE.md` est
chargé à chaque séance ; à 688 lignes il dépassait le budget de 400 que mesure
`audit_fleet.py` de la baseline. Chaque règle garde son numéro et sa forme impérative
là-bas ; ici vit le « pourquoi » qu'on relit quand on veut la contester.
Texte déplacé tel quel — les dates sont celles de la mesure, pas de ce déplacement.

## §1 — Le temps de la suite
⚠️ **La forme nue n'est pas « la même en plus simple » : elle perd `-n auto`.** Elle a été
lancée six fois en une séance le 2026-09-16 parce que ce fichier la documentait, et elle
seule explique l'essentiel du temps d'attente de cette séance.

⚠️ **`-n auto` n'est plus le drapeau réel, et ce fichier l'a annoncé une demi-journée de
trop.** Le 2026-09-17, `make test` s'étant fait **tuer par l'OOM deux fois en une heure**,
`PYTEST_DIST` est passé à `-n` un nombre CALCULÉ (aujourd'hui `$W`, pris après le verrou lourd — R331),
`(MemAvailable_Mo − 5120) / 700`, borné à `[2, nproc]`. Ce poste porte `n8n-ollama` et le
serveur MCP `knowledge-rag` en permanence, qu'un runner GitHub n'a pas. Conséquence
contre-intuitive, mesurée : sur cette WSL plafonnée à 10 Go, **le calcul ne peut pas
atteindre 8** — il faudrait 10 720 Mo disponibles — et il tombe à **2** dès que la pile
Docker tourne. Un lecteur qui croyait la rangée du tableau annonçait à la fois un drapeau
et un temps que rien ne produisait. Garde :
`tests/test_local_and_ci_run_the_same_suite.py::test_claude_md_does_not_name_a_worker_count_the_makefile_refuses`.

⚠️ **Depuis le 2026-09-25 la réserve n'est plus fixe.** n8n ne tourne que le dimanche,
knowledge-rag décharge son modèle après 10 min : `tools/dev/pytest_workers.py` réserve
1 536 Mo de base, +(2 300 − RSS) par serveur knowledge-rag (R352),
+3 600 si Ollama ou une ingestion tourne, et dit pourquoi sur stderr. Une ingestion qui
démarrerait PENDANT la suite est exclue par un verrou (`~/.cache/heavy-memory.lock`) que
les cibles de test tiennent et que les crons d'ingestion respectent. Mesuré en alternance
4/2/4 workers : **179 · 269 · 180 s**, creux de `MemAvailable` **4 454 · 5 228 · 4 278 Mo**. Plafond cgroup : `SUITE_SCOPE` (R352).

Les deux mesures du 2026-09-16 étaient du **même soir, même arbre, même verdict**
(6 717 verts, 1 rouge) : `make test` **418 s** sur `/mnt/c`, la forme nue **1 146 s**.
**×2,74** — c'était alors le seul gain disponible sans changer de machine.

⚠️ **Le 2026-09-17, R117 a été livrée et le premier chiffre est tombé** : la même suite
rend **193,5 s** sur ext4 (6 921 verts, 66 skippés), soit **×2,2** de moins, sans toucher
à un seul test. Le ×2,74 de `-n auto` reste vrai et s'ajoute ; il n'a pas été remesuré
ici, et la ligne du tableau le dit plutôt que de recopier un chiffre d'un autre disque.

⚠️ **Savoir si une suite tourne demande un outil qui ne ment pas.** Le 2026-09-16 j'ai
conclu QUATRE FOIS qu'une suite était « morte en route » ; les quatre fois elle tournait
encore. Deux causes, cumulées : `| tail` ne rend rien avant la fin du tube — donc aucune
progression visible — et `ps … | grep` est intercepté par le wrapper RTK, qui rend une
sortie vide. Les commandes qui disent la vérité :
```bash
rtk proxy sh -c 'ps -eo pid,etimes,args | grep "[p]ytest tests/"'   # qui tourne
tail -3 .pytest-last.log                                            # où elle en est
```
`make test` écrit ce journal au fil de l'eau exactement pour ça.

**R117 est LIVRÉE le 2026-09-17** — le dépôt vit sur ext4 (`~/streamlytics`). Gain
remesuré le jour même, en ALTERNANCE et à périmètre égal (6 988 tests collectés des deux
côtés) :

| | `/mnt/c` | ext4 | rapport |
|---|---|---|---|
| collecte pytest | 39,53 · 38,08 s | **8,15 · 8,47 s** | **×4,6** |
| `make test` | 418 s | **193,5 s** | ×2,2 |

⚠️ Le premier tirage ext4 de la collecte a rendu **13,75 s** et aurait donné ×2,5 : le
cache de pages venait d'être rempli par `git clone` et `make sync`. En alternance il
tombe à 8,2. **C'est exactement ce que la règle d'alternance existe pour attraper**, et
sans elle le gain aurait été annoncé à la moitié de sa valeur.

Il ne reste donc plus de levier structurel sur le temps de la suite : R118/R120/R121
visaient la latence de l'APP pour un artiste, et les trois sont closes, réfutées par
leur propre mesure.

**Ce qui a été refusé, avec sa mesure** : alléger les rendus `AppTest` (62 % du temps,
`test_views_render_smoke.py` 193,5 s à lui seul). Le remède canonique existe — Humble
Object — et il est écarté parce que ces rendus attrapent des défauts que 4 737 tests
unitaires verts ne voyaient pas. Détail : `.claude/dev-docs/test-suite-performance.md`.

## §2 — Règle 15 : ce que les chiffres de récidive valent
⚠️ **Ce paragraphe a porté un second chiffre. Il est mort, et pas d'un cran : d'un
biais.** Il a annoncé successivement « 5,2× » (194 révisions), puis « 4,9× » avec
intervalles recouvrants (296 révisions, compteur corrigé). Les deux venaient d'une
strate `by_guard` qui étiquetait chaque classe avec son état **d'AUJOURD'HUI** et
appliquait cette étiquette à **toute sa vie** depuis son introduction. Une classe
née sans garde, récidivée, puis gardée versait ses jours entiers ET sa récidive
dans le bras « automatique » — et comme c'est la récidive qui fait écrire le garde,
la causalité était inversée. C'est un biais d'*immortal time*.
Mesuré sans lui le 2026-09-18, en découpant l'exposition de chaque classe à son
PREMIER garde et en attribuant chaque récidive par sa propre date :

| | avec garde | sans garde | rapport |
|---|---|---|---|
| `by_guard` — étiquette d'aujourd'hui, **confondu** | 0,144 | 0,703 | ×4,9 |
| `by_guard_since` — découpé au premier garde | **0,155** | **0,165** | **×1,1** |

**Le facteur était entièrement l'artefact.** Écrire un garde automatique reste la
bonne pratique — pour une raison de conception, pas de statistique : un garde
s'exécute, une prose ne s'exécute pas. Mais **aucune règle ne doit citer un chiffre
de récidive comme sa preuve** : ce jeu de données n'en produit aucun. Contrôle :
`make error-health` → section « Ce que le biais valait, en clair ». Garde :
`tests/test_the_guard_axis_is_measured_without_immortal_time.py`.
⚠️ **Le compteur comptait la MAUVAISE chose, et c'est la vraie leçon de la série.**
Jusqu'au 2026-09-18, toute ligne d'`History` ajoutée comptait comme une récidive.
Les 81 lignes concernées ont été classées une par une : **33 sont de vraies
récidives, 26 sont des défauts du GARDE** (signature dérivée, prédicat aveugle,
faux positif) et **22 sont du travail sur la classe**. Écrire le verdict d'un
balayage qui PROUVE qu'une classe est saine faisait donc monter sa récidive — mesuré
le jour même, deux balayages à zéro site vivant ont porté `ever_recurred_observed`
de 54 à 56. Une ligne d'`History` déclare désormais sa nature —
`- AAAA-MM-JJ (récidive):` ou `- AAAA-MM-JJ (garde):`, sans marque pour une note de
travail — et seule la première compte. Total corrigé : **32 évènements, pas 69**.
⚠️ Et l'axe `seen_red` ne discrimine pas non plus : les classes DATÉES récidivent
**deux fois plus** (0,210 contre 0,103), intervalles recouvrants, sur 7 évènements.
On continue de dater `seen_red` — décision du propriétaire le 2026-09-18, motif
explicite : le n est trop faible pour conclure, et remplir la colonne est ce qui
fera converger l'intervalle. Ce n'est donc pas un acquis, c'est un pari déclaré.
Contrôle : les cliquets `tests/test_the_error_class_health_only_improves.py` (calculés
sur l'arbre depuis R345). Évolution : `make error-health-history`.

## §3 — Règle 15bis : pourquoi un journal de nuit
La raison est mesurée, pas prudentielle : le contexte est COMPACTÉ plusieurs fois
sur une nuit, et après chaque compaction je sais *quoi* faire sans savoir *où j'en
étais*. La roadmap ne comble pas ce trou — elle bouge quand une brique est livrée,
pas quand un lot de six est à mi-chemin, et c'est exactement la granularité d'un
réveil. Le journal est `night-run.jsonl`, **append-only** : un tour qui meurt au
milieu ne peut pas corrompre ce qui précède.

## §4 — Règle 15ter : ce que la mutation a trouvé
seule façon de le savoir est de le mettre en défaut : ~40 mutations le 2026-09-18
ont trouvé **sept défauts vivants**, dont deux gardes P1 aveugles à leur propre
sujet. ⚠️ Il ne DATE rien tout seul : il rend « ce garde a rougi sur telle
mutation », et c'est un humain qui décide si la mutation INCARNE le défaut. Une
mutation qui casse autre chose ne prouve rien — et une mutation appliquée sur un
motif ABSENT du fichier ne modifie rien du tout, laisse la suite verte, et se lit
comme un garde vacant. Vérifier que la ligne a CHANGÉ.

## §5 — Règle 20 : dix prédicats faux au premier jet
La raison est mesurée, pas prudentielle. Nuit du 2026-09-17 au 18, ~30 balayages :
**dix prédicats étaient faux au premier jet**, d'un facteur 3 à 25, et **toujours en
sur-comptant** — 112 → 0, 688 → 16, 385 → 18, 13 → 1, 11 → 2, 9 → 0, 3 → 0. Aucune
de ces dix corrections n'est venue d'une relecture du prédicat ; les dix sont venues
d'une mutation ou d'une lecture site par site. La cause commune est toujours la même :
le prédicat cherche une FORME D'ÉCRITURE (`page == "x"`, `assert not …`, `^CONST =`)
là où la classe parle d'une PROPRIÉTÉ (« la page est-elle atteignable », « l'absence
est-elle ancrée », « ce plafond a-t-il un plancher »).

## §6 — Règle 21 : le groupement par famille, mesuré
Mesuré sur les balayages eux-mêmes, en croisant leur date et leur famille : le
2026-09-17, **271 des 273 classes balayées (99 %)** appartenaient à une famille
balayée plusieurs fois ce jour-là ; le 2026-09-18, **17 sur 18 (94 %)**. Le
groupement n'est donc pas une intention qu'on se donne — c'est ce qui se produit
quand on suit la cause, et le reconnaître évite de rouvrir une mesure déjà faite
pour la classe d'à côté.
⚠️ Ce que cette mesure NE dit pas : combien de mesures distinctes une famille a
coûté. J'ai d'abord écrit « quatre mesures pour dix classes » — une impression, pas
un relevé, c'est-à-dire précisément la règle 20 enfreinte dans le texte qui
l'introduit. Le chiffre ci-dessus est celui qu'on peut rejouer.
`error-class-families.md` (dev-docs/) est généré pour ça : il porte, pour
chaque famille, LA question qu'elle fait poser.

## §7 — Pourquoi les règles 12-13 ont cette forme
> Règles 12-13 ajoutées le 2026-07-28. Forme imposée :
> une flèche, un déclencheur **vérifiable mécaniquement**, le verbe littéral `Spawn`, un
> contrat de sortie. C'est le seul mécanisme mesuré qui produise des invocations — 33 spawns
> pour les agents nommés dans une règle impérative, **0 sur 23** pour ceux nommés dans un
> tableau ou un registre. Les tableaux d'agents ci-dessous sont de la documentation, pas un
> déclencheur.

## §7bis — Pourquoi les règles 18-19
> Règles 18-19 ajoutées le 2026-08-21 pour la raison mesurée ci-dessus, et pas pour
> gonfler un score : ces deux agents n'étaient nommés que dans un tableau, donc jamais
> déclenchés. Si un déclencheur ne se produit jamais en pratique, retirer l'agent est
> la bonne réponse — pas lui inventer une règle.

## §8 — Pourquoi des hooks et pas des règles
> **Pourquoi des hooks et pas des règles ici.** Ces trois comportements sont des gestes
> RÉFLEXES, et le dépôt a mesuré deux fois qu'une note ne les retient pas : le même
> `checkout` a détruit du travail deux fois le 2026-09-10, la leçon écrite entre les
> deux ; le même `kill` s'est tué trois fois le 2026-09-12. Un garde arrive au moment du
> geste et connaît un fait que la prose ne peut pas porter — y a-t-il du travail à
> perdre, une suite tourne-t-elle. Classes :
> `a-kill-pattern-that-matches-its-own-shell`, `a-verdict-from-a-tree-that-moved-under-it`,
> `a-bash-hook-that-blocks-the-prose-about-the-gesture`.
>
> ⚠️ Et un garde de Bash lit la **structure** : le geste doit être la COMMANDE de son
> segment, jamais un mot dans un argument. Sans ce filtre, écrire *sur* un défaut
> déclenche le garde du défaut — trois commandes bloquées d'affilée le 2026-09-12, toutes
> en train de documenter le geste. Contrôle :
> `tests/test_a_bash_guard_reads_the_command_not_the_prose.py`.

## §9 — La roadmap gardée (R196)
**Une action entre dans la roadmap AVANT d'être exécutée — et c'est gardé, pas conseillé
(R196, 2026-09-26).** Séquence, micro-demandes comprises : (1) ligne `| Rnnn | … |` dans
l'index + commit « Roadmap : Rnnn inscrite » ; (2) le code, commité avec « Rnnn : … » ;
(3) l'archive à la livraison. Trois barrières : le hook PreToolUse
`require_roadmap_entry.py` refuse toute modification de `src/`, `airflow/dags/`,
`migrations/` tant que l'index n'a aucune ligne ouverte ; le hook git `commit-msg`
(`tools/dev/require_roadmap_id.py`) refuse un commit de code produit qui ne cite pas un
Rnnn OUVERT dans le commit précédent — une ligne archivée ne compte pas ; le job CI
`roadmap` rejuge les commits poussés (`--no-verify` n'y passe pas). Limite : avec plusieurs
lignes ouvertes, rien ne prouve que le diff EST la tâche citée. Mesuré avant : 41 des 118
commits de code depuis le 2026-09-12 ne citaient aucun id.

## §9bis — Briques fondatrices (historique)
| Bricks | Topic | Status | Priority |
|---|---|---|---|
| 1–8 | SaaS DB migration, Auth, Admin, Credentials, CSV import, Parameterized DAGs, iMusician, Home KPI | ✅ | — |
| 9–11 | Error handling + retry, Unit tests, Monitoring + alerting | ✅ | P2 |
| 12–13 | PDF export (WeasyPrint), CSV export (ZIP) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16–17 | ML scoring DAG + ML dashboard views | ✅ | P3 |

## §10 — Graphify : tailles et résidu
The graph currently indexes **9520 nodes / 17884 edges across 1210 communities**
(regenerated 2026-09-11; it read 6393/12548/849 on 2026-08-28, 5468/10691/689 on
2026-08-23, and "1500+ nodes / 94 communities" before that — a figure from June that
was off by 3.6×).

⚠️ **`graphify update` ajoute, il ne retire pas.** Remesuré le 2026-09-11 **après une
régénération fraîche** — et c'est le point : **24 fichiers** y sont référencés alors
qu'ils n'existent plus sur le disque (177 nœuds, 1,9 % — c'était 17 / 145 le
2026-08-28, donc le résidu GRANDIT à chaque régénération). On y trouve d'anciens
modules devenus des paquets (`utils/pdf_exporter.py`, 56 nœuds ;
`views/trigger_algo/_common.py`, 24), un dossier `archive/` supprimé, des watchers
retirés (`meta_insight_watcher.py`, `s4a_csv_watcher.py`) et `tests/test_error_handler.py`.
Le rapport envoie vers des modules fantômes. Le compte se rejoue :
`python3 -c "import json,pathlib,collections; g=json.load(open('graphify-out/graph.json')); p=collections.Counter(n['source_file'] for n in g['nodes'] if n.get('source_file')); m={k:v for k,v in p.items() if not pathlib.Path(k).exists()}; print(len(m),'fichiers,',sum(m.values()),'nœuds')"`
Avant d'agir sur un chemin lu dans `GRAPH_REPORT.md`, vérifier qu'il existe — le graphe
oriente, il ne prouve pas. If you
add or rename modules, regenerate so future `Glob`/`Grep` calls see the new
structure.

**Visual exploration** : open `graphify-out/graph.html` **directly in your
browser** (double-click, or `file://` URL). The HTML is standalone — vis-network
JS is bundled inline, no server needed. Features : click-to-inspect panel,
search box, community filter, physics layout, edge-confidence styling
(`EXTRACTED` solid vs `INFERRED` dashed). Generated by `make graph-html`, which
wraps `python3 tools/dev/graphify_render_html.py` — that script calls
`graphify.export.to_html` directly (the CLI doesn't expose this).

## §2bis — Règle 14 : un constat de sécurité est une classe

Passage d'origine de la règle 14, verbatim :

Ligne 315 de l'original :

```markdown
    **Un constat de sécurité (gitleaks, secret exposé, CVE) EST une classe de défaut** :
    le 2026-09-25, 12 secrets trouvés sont partis en tri `security-specialist` et aucun
    balayage n'a couru avant que le propriétaire le demande. Ses surfaces publiques sont
    désormais balayées chaque nuit par `tools/dev/sweep_public_surfaces.py`.
```


## §11 — Autres passages déplacés (verbatim)

Tout passage retiré de CLAUDE.md par R631 et absent des sections ci-dessus, dans l'ordre
du fichier d'origine (`git show 2fce70e0:CLAUDE.md`). Rien n'a été réécrit.

Ligne 10 de l'original :

````markdown
```
External APIs / CSV files
        ↓
Airflow DAGs (Docker containers)
        ↓
PostgreSQL `spotify_etl` DB (port 5433 locally)
        ↓
Streamlit Dashboard (local, port 8501)
```
````

Ligne 21 de l'original :

```markdown
- **postgres** — PostgreSQL 17, port 5433→5432. Databases: `airflow_db` (Airflow metadata), `spotify_etl` (app data)
- **airflow-webserver** — port 8080, UI at http://localhost:8080
- **airflow-scheduler** — auto-picks up `airflow/dags/`
- **airflow-init** — one-shot DB init + admin user creation
```

Ligne 35 de l'original :

```markdown
  utils/        # config_loader, airflow_trigger, email_alerts, error_handler, retry
                # metrics.py (4 familles Prometheus), ops_alerts.py (lit les règles
                # d'alerte pour le mail du soir), daily_ops_metrics.py (résumé
                # quotidien en base — il survit aux redémarrages, pas Prometheus)
  api/          # FastAPI REST (brique 14, JWT) — main.py, auth.py, deps.py,
                # security.py, routers/. Il expose `/metrics` sur SON port HTTP, sans
                # serveur latéral : il a déjà un serveur, lui en ajouter un second
                # n'achèterait rien. C'est la SEULE différence de câblage avec le
                # dashboard, et elle est intentionnelle (ADR-026).
```

Ligne 45 de l'original :

```markdown
    serve.py    # ⚠️ L'ENTRÉE DU CONTENEUR (`CMD`) — démarre l'exportateur de métriques
                #    PUIS passe la main à `streamlit run`, dans le MÊME processus.
                #    Un `&` exposerait un registre vide : la cible serait `up` en ne
                #    mesurant rien, pire que `down`.
```

Ligne 51 de l'original :

```markdown
    utils/      # get_db_connection, airflow_monitor
      fragment_db.py   # la connexion d'un `@st.fragment` : RÉUTILISE celle de la page
                       # pendant un rendu complet, n'ouvre la sienne qu'au rerun de
                       # fragment. Un fragment qui capture celle de `show()` la
                       # ré-emprunte au pool sans jamais la rendre.
      metrics_seam.py  # la couture entre un rerun et les métriques (phases chrome/view)
```

Ligne 82 de l'original :

```markdown
# ⚠️ En conteneur c'est `python3 -m src.dashboard.serve` : il démarre l'exportateur
# de métriques AVANT Streamlit. Lancé à la main comme ci-dessus, seule la couture
# de rendu l'ouvre — donc au premier rendu, pas au démarrage.
# ⚠️ JAMAIS `pytest tests/` à la main — les drapeaux de parallélisme vivent dans le
# Makefile, et la forme nue les perd. Trois cibles, par ordre de fréquence d'usage :
```

Ligne 97 de l'original :

```markdown
**Mesuré sur ce poste le 2026-09-17, APRÈS R117 — le dépôt vit sur ext4
(`~/streamlytics`), plus sur `/mnt/c`.** Les chiffres sont là pour qu'on CHOISISSE, pas
pour décorer :
```

Ligne 176 de l'original :

```markdown
Two equivalent paths — pick by the shell you're in :
```

Ligne 178 de l'original :

````markdown
**From WSL / bash / macOS / CI** (preferred — single command, idempotent across all `migrations/*.sql`) :
```bash
make migrate
```
This iterates over `migrations/*.sql` and pipes each through `docker exec -i <pg> psql -U postgres -d spotify_etl`. Auto-detects the running postgres container.

**From Windows PowerShell** (when `make` isn't available; `psql` isn't installed locally either) :
````

Ligne 186 de l'original :

```markdown
# Step 1 — find the postgres container name
docker ps --format "table {{.Names}}`t{{.Status}}"

# Step 2 — run a single migration (replace <container> with the actual name)
```

Ligne 197 de l'original :

```markdown
Two mechanisms coexist:
1. `config/config.yaml` — dashboard DB credentials + API keys. Copy from `config/config.example.yaml`.
2. `.env` / `.env.local` — Docker Compose + python-dotenv. `.env.local` takes precedence locally.

Dashboard reads DB config from `config/config.yaml` exclusively (not `.env`).
```

Ligne 221 de l'original :

```markdown
| Dependency manifest | `pyproject.toml` | Canonical project deps + dev extras (pytest, ruff, pre-commit, detect-secrets). |
| Lock file | `uv.lock` | Reproducible installs via `uv sync --frozen` (or `make sync`). |
| Legacy install path | `requirements.txt` | Kept parallel for the existing Dockerfile + CI workflow. Dérivé de `pyproject.toml`. |
| Lint config | `ruff.toml` | Authoritative ruff config. CI blocks on `ruff check src/ tests/` since 2026-05-14. Version remontée avec le lock le 2026-08-24 (R49). |
| Ruff binary | `pip install ruff==0.15.17` (dev extra) | Available system-wide as `/home/timothe/.local/bin/ruff`. |
| Pre-commit hooks | `.pre-commit-config.yaml` + `make hooks-install` | Ruff + secret scan + hygiene on staged files. Chained from `make sync`. Bypass : `git commit --no-verify`. |
| Secret baseline | `.secrets.baseline` | Versioned acknowledged-matches list. New secrets fail commit; update baseline via `detect-secrets scan --baseline .secrets.baseline`. |
```

Ligne 237 de l'original :

```markdown
| `.claude/dev-docs/roadmap/checklist.md` | Live brick tracker — **open work only** |
| `.claude/dev-docs/roadmap/archive.md` | Delivered bricks + closed bugs (passive) |
| `docs/adr/ADR-001-*.md` | Roadmap-multi-files-conserved decision |
| `docs/adr/ADR-002-*.md` | Rejected msdr patterns (Alembic, repo pattern). ⚠️ Son §4 (observability) est **superseded par ADR-026** depuis le 2026-09-16 |
| `docs/adr/ADR-026-*.md` | Pourquoi Prometheus + Grafana sont adoptés — pour SURVEILLER les déclencheurs d'ADR-002/007/014, pas sur une plainte de latence |
```

Ligne 243 de l'original :

```markdown
| `.claude/dev-docs/refactor-audit-dashboard.md` | Prioritized dashboard refactor pain points |
| `.claude/dev-docs/refactor-audit-mlops.md` | MLOps audit + scope decisions |
| `.claude/dev-docs/meta-ads-credential-guide.md` | Meta/Instagram token setup + refresh behavior |
| `.claude/dev-docs/soundcloud-oauth-guide.md` | SoundCloud OAuth refresh_token mint runbook (real likes) |
| `.claude/dev-docs/token-management-bilan.md` | Cross-platform token/refresh matrix + admin/end-user no-manual-action criterion |
```

Ligne 250 de l'original :

```markdown
| `.claude/dev-docs/refactor-audit-2026-08.md` | Audit de refactor du 2026-08-20, commandé après les deux tests artiste ratés |
```

Ligne 253 de l'original :

```markdown
| `gold-coverage.md` (dev-docs/) | **Généré** par `make gold-coverage`. La carte de la couche or : pour chaque figure, chaque tuile et chaque figure du PDF, quelle donnée elle dessine et si elle passe par une vue or. Sa dernière section — les tables brutes encore agrégées **hors de tout cliquet** — est la liste des prochaines divergences. **Non versionné depuis R345** (ADR-031) |
| `.claude/dev-docs/roadmap/night-run.md` | **Le protocole d'une séance longue** — à lire EN PREMIER à chaque réveil, AVANT la roadmap. Une séance de plusieurs heures est compactée plusieurs fois : la roadmap dit *quoi*, elle ne dit pas *où j'en étais*. `make night-status` répond à ça en un écran. Porte la règle qui compte — **bloqué ⇒ on PARQUE et on passe**, jamais on ne s'arrête — et la liste de ce qu'on ne fait pas sans un humain |
| `error-class-health.md` (dev-docs/) | **Généré** par `make error-health`. La santé du catalogue : combien de classes ont une connaissance VÉRIFIABLE, et combien récidivent — mesuré depuis git, pas depuis un champ. Il porte une section « Ce que ce document corrige » qui liste les chiffres avancés avant vérification. Le JSON à côté est la donnée. **Non versionnés depuis R345** (ADR-031) : générés à la demande ; `make error-health-check` (CI) ne juge plus que le rangement |
```

Ligne 257 de l'original :

```markdown
| `.claude/dev-docs/studies/2026-10-12-mods-claude-code.md` | Les mods de Claude Code (M1–M6) : garde Stop R549, statusline R550 ; revue le 2026-10-26 (`make reopen-check`) |
| `.claude/dev-docs/studies/2026-10-10-outillage-et-lecteurs.md` | Études E1–E6 (mutmut, Pandera, babel, quarantaine, Dependabot `uv`, agents autonomes) : verdict intégrer / plus tard / rien, avec le déclencheur de réouverture |
```

Ligne 261 de l'original :

```markdown
| `error-class-families.md` (dev-docs/) | **Généré** par `make error-families`. Les 287 classes d'erreur regroupées en 12 familles, chacune avec **la question** qu'elle fait poser devant du code. À lire AVANT d'écrire une classe neuve : c'est là qu'on voit si la forme a déjà été payée |
```

Ligne 264 de l'original :

```markdown
| `.claude/dev-docs/error-inbox.md` | **Généré** par `make error-inbox` depuis `app_error_log` — une ligne par DÉFAUT (empreinte), pas par occurrence. Fermer : `make error-resolve FP=… NOTE="…"`. La roadmap n'en porte qu'une ligne de renvoi ancrée |
```

Ligne 294 de l'original :

```markdown
12. **≥5 tests rouges dans une même exécution → `Spawn build-error-resolver`.** Il renvoie
    la chaîne causale jusqu'à une cause **qu'on peut retirer**, les sites qu'elle touche, et
    le fix minimal — sans toucher au code non lié. Le seuil est celui que `session_summary.py`
    signale réellement (`failures >= 5`) : le changer suppose d'éditer les trois surfaces
    ensemble — cette règle, la description de l'agent, et le hook.
```

Ligne 325 de l'original :

```markdown
    tient, on écrit le test et on le dit. Le catalogue a gagné **365 classes en sept
    semaines** — ~10 par jour — et **91 % ne récidivent jamais** ; le billet en aurait
    retenu **1 sur 8**. ⚠️ Le seuil de 2 sites n'est pas justifié par une corrélation :
    le verdict de balayage sépare fortement (0,505 contre 0,112, IC disjoints) mais il
    est RÉTROSPECTIF — sur 37 classes, le balayage précède la récidive 0 fois et tombe
    le même jour 12 fois. Il tient sur un argument de décision : un défaut présent à
    deux endroits n'est pas un cas isolé, par définition. Contrôle bloquant :
    `python3 .claude/scripts/audit_runner.py --admission`.
```

Ligne 343 de l'original :

```markdown
    Mesuré le 2026-09-16 : une classe gardée sur le VERBE `pkill` a récidivé trois fois
    par `pgrep`, qui partageait la cause.
    ⚠️ **Ce paragraphe a porté un second chiffre. Il est mort, et pas d'un cran : d'un
    biais.** Il a annoncé successivement « 5,2× » (194 révisions), puis « 4,9× » avec
    intervalles recouvrants (296 révisions, compteur corrigé). Les deux venaient d'une
    strate `by_guard` qui étiquetait chaque classe avec son état **d'AUJOURD'HUI** et
    appliquait cette étiquette à **toute sa vie** depuis son introduction. Une classe
    née sans garde, récidivée, puis gardée versait ses jours entiers ET sa récidive
    dans le bras « automatique » — et comme c'est la récidive qui fait écrire le garde,
    la causalité était inversée. C'est un biais d'*immortal time*.
    Mesuré sans lui le 2026-09-18, en découpant l'exposition de chaque classe à son
    PREMIER garde et en attribuant chaque récidive par sa propre date :

    | | avec garde | sans garde | rapport |
    |---|---|---|---|
    | `by_guard` — étiquette d'aujourd'hui, **confondu** | 0,144 | 0,703 | ×4,9 |
    | `by_guard_since` — découpé au premier garde | **0,155** | **0,165** | **×1,1** |

    **Le facteur était entièrement l'artefact.** Écrire un garde automatique reste la
    bonne pratique — pour une raison de conception, pas de statistique : un garde
    s'exécute, une prose ne s'exécute pas. Mais **aucune règle ne doit citer un chiffre
    de récidive comme sa preuve** : ce jeu de données n'en produit aucun. Contrôle :
    `make error-health` → section « Ce que le biais valait, en clair ». Garde :
    `tests/test_the_guard_axis_is_measured_without_immortal_time.py`.
    ⚠️ **Le compteur comptait la MAUVAISE chose, et c'est la vraie leçon de la série.**
    Jusqu'au 2026-09-18, toute ligne d'`History` ajoutée comptait comme une récidive.
    Les 81 lignes concernées ont été classées une par une : **33 sont de vraies
    récidives, 26 sont des défauts du GARDE** (signature dérivée, prédicat aveugle,
    faux positif) et **22 sont du travail sur la classe**. Écrire le verdict d'un
    balayage qui PROUVE qu'une classe est saine faisait donc monter sa récidive — mesuré
    le jour même, deux balayages à zéro site vivant ont porté `ever_recurred_observed`
    de 54 à 56. Une ligne d'`History` déclare désormais sa nature —
    `- AAAA-MM-JJ (récidive):` ou `- AAAA-MM-JJ (garde):`, sans marque pour une note de
    travail — et seule la première compte. Total corrigé : **32 évènements, pas 69**.
    ⚠️ Et l'axe `seen_red` ne discrimine pas non plus : les classes DATÉES récidivent
    **deux fois plus** (0,210 contre 0,103), intervalles recouvrants, sur 7 évènements.
    On continue de dater `seen_red` — décision du propriétaire le 2026-09-18, motif
    explicite : le n est trop faible pour conclure, et remplir la colonne est ce qui
    fera converger l'intervalle. Ce n'est donc pas un acquis, c'est un pari déclaré.
    Contrôle : les cliquets `tests/test_the_error_class_health_only_improves.py` (calculés
    sur l'arbre depuis R345). Évolution : `make error-health-history`.
```

Ligne 421 de l'original :

```markdown
    raconter la leçon → `Spawn roadmap-keeper`.** La ROADMAP est en
    **deux fichiers** : `.claude/dev-docs/roadmap/checklist.md` (actif — ce qui est
    ouvert) et `.claude/dev-docs/roadmap/archive.md` (livré ou clos). Il renvoie les
    deux mis à jour : la brique retirée de l'actif **et** ajoutée à l'archive, jamais
    l'un sans l'autre, plus la ligne d'index `## 📋 Tâches ouvertes` retirée. Ces
    fichiers ne portent aucune statistique agrégée : il n'en invente pas.
    Contrôle : `python3 -m pytest tests/test_roadmap_two_files.py -q` échoue si la
    somme des deux fichiers rétrécit — une rotation qui perd un item améliore le
    pourcentage sans rien livrer.

18. **≥5 modules ajoutés, supprimés ou renommés sous `src/` dans une session, ou un
    diagramme de `.claude/dev-docs/architecture.md` touché → `Spawn
    code-architecture-reviewer`.** Il renvoie un tableau `| Diagramme | Constat |
    Sévérité | Action |` de dérive **factuelle** entre le diagramme et le code, jamais
    de suggestion de style. Déclencheur vérifiable : `git diff --name-status
    <base>..HEAD -- src/ | grep -cE '^(A|D|R)'`. La Views Map a déjà divergé deux fois
    sans que rien ne le signale.

19. **Un comportement d'API externe qu'aucun fichier de `.claude/dev-docs/` ne
    documente — code d'erreur inconnu, champ disparu, intégration qui cesse de
    fonctionner sans changement de notre côté → `Spawn web-research-specialist`.** Il
    renvoie ≤500 mots : ce que fait l'API / ses contraintes / ce qui s'applique ici /
    les liens, et signale explicitement deux sources qui se contredisent. Déclencheur
    vérifiable : `grep -rl "<le code d'erreur>" .claude/dev-docs/` ne renvoie rien.
    Le cas vivant est R13 — Meta répond `code-190` sur tout REST depuis des semaines.
```

Ligne 495 de l'original :

```markdown
Spec layout: each skill is a **directory**. The flat `<nom>.md` form was migrated away and
every path below was pointing beside the file until 2026-07-28 — a reference that misses
without complaining is the `.claude/skills/impact-analysis/SKILL.md` case of rule #11, which named
a file that had not existed for weeks.
```

Ligne 514 de l'original :

```markdown
Auto-injected by `inject_context.py` via their `keywords:` frontmatter. When one lands in
context, **run it; do not wait to be asked.**
```

Ligne 527 de l'original :

```markdown
Documentation, pas déclencheurs : `.claude/dev-docs/tooling-reference.md`.
Les agents réellement invoqués le sont par les règles 12, 13, 14, 17, 18, 19 ci-dessus
et par la règle de la boucle d'ingénierie (`code-critic`) — pas par un tableau.
```

Ligne 533 de l'original :

```markdown
- **PreToolUse (Bash)** → `guard_destructive.py` — bloque les gestes irréversibles. Deux
  gardes à **ÉTAT**, qui ne bloquent que s'il y a réellement à perdre et qui NOMMENT quoi :
  un rétablissement git sur un fichier portant du travail non commité, et un `kill` par
  motif suivi d'autre chose sur la même ligne (le motif matche la ligne du shell, qui se
  tue, et la suite ne part jamais — code 144).
- **PreToolUse (Edit|Write|MultiEdit|NotebookEdit)** → `require_roadmap_entry.py` —
  refuse une modification de code produit tant que l'index de la roadmap n'a aucune ligne
  ouverte, et donne le prochain id libre (R196).
- **PostToolUse** → `check_python_syntax.py` — ruff après chaque Write/Edit ; exit 2 bloque
  sur E9. Avertit aussi quand une **suite complète tourne** : le fichier qu'on vient
  d'écrire n'y sera pas, donc son verdict décrira un arbre qui n'existe plus.
- **Stop** → `session_summary.py` — git diff, Docker health, turn count, symptômes de défaut → `make defect-log`
- **Stop** → `require_verdict_after_edit.py` (R549) — code modifié après le départ de la dernière
  suite ⇒ fin de tour bloquée UNE fois. Un `.md` seul ne bloque pas.
```

Ligne 579 de l'original :

```markdown
**Deux fichiers, un seul actif** :

| Fichier | Contient | Lu par |
|---|---|---|
| `.claude/dev-docs/roadmap/checklist.md` | tâches et bugs **ouverts**, état de reprise | `/resume`, `/sprint`, hooks de fraîcheur |
| `.claude/dev-docs/roadmap/archive.md` | briques livrées, bugs clos — **passif** | personne en routine |

```

Ligne 588 de l'original :

```markdown
**Une action entre dans la roadmap AVANT d'être exécutée — et c'est gardé, pas conseillé
(R196, 2026-09-26).** Séquence, micro-demandes comprises : (1) ligne `| Rnnn | … |` dans
l'index + commit « Roadmap : Rnnn inscrite » ; (2) le code, commité avec « Rnnn : … » ;
(3) l'archive à la livraison. Trois barrières : le hook PreToolUse
`require_roadmap_entry.py` refuse toute modification de `src/`, `airflow/dags/`,
`migrations/` tant que l'index n'a aucune ligne ouverte ; le hook git `commit-msg`
(`tools/dev/require_roadmap_id.py`) refuse un commit de code produit qui ne cite pas un
Rnnn OUVERT dans le commit précédent — une ligne archivée ne compte pas ; le job CI
`roadmap` rejuge les commits poussés (`--no-verify` n'y passe pas). Limite : avec plusieurs
lignes ouvertes, rien ne prouve que le diff EST la tâche citée. Mesuré avant : 41 des 118
commits de code depuis le 2026-09-12 ne citaient aucun id.

**Roadmap flow**: the top `## 📋 Tâches ouvertes` table is the concise index of only
*still-open* tasks. When a task is completed, run `make roadmap-close ID=<id> NOTE="…"` (or `/roadmap-done`,
which calls it) — it **writes the archive entry**, retires the row and realigns the
anchor. For a batch of bricks, `Spawn roadmap-keeper` (règle 17). Never hand-delete an item: déplacement,
pas suppression — `tests/test_roadmap_two_files.py` échoue si le total des deux fichiers
rétrécit.

| Bricks | Topic | Status | Priority |
|---|---|---|---|
| 1–8 | SaaS DB migration, Auth, Admin, Credentials, CSV import, Parameterized DAGs, iMusician, Home KPI | ✅ | — |
| 9–11 | Error handling + retry, Unit tests, Monitoring + alerting | ✅ | P2 |
| 12–13 | PDF export (WeasyPrint), CSV export (ZIP) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16–17 | ML scoring DAG + ML dashboard views | ✅ | P3 |

```

Ligne 621 de l'original :

````markdown

This repo carries an indexed code graph in `graphify-out/` (**gitignored** — local
only). The MCP server in `.mcp.json` lets Claude Code query the graph; the
PreToolUse hook on `Glob|Grep` reminds to read `graphify-out/GRAPH_REPORT.md`
before brute-force searching files.

Refresh after significant code changes (≥ 5 files):

```bash
make graph                  # graph-update + graph-html in one shot
# OR step-by-step :
make graph-update           # refresh graph.json + GRAPH_REPORT.md (AST, no LLM)
make graph-html             # re-render graph.html from current graph.json
```

The graph currently indexes **9520 nodes / 17884 edges across 1210 communities**
(regenerated 2026-09-11; it read 6393/12548/849 on 2026-08-28, 5468/10691/689 on
2026-08-23, and "1500+ nodes / 94 communities" before that — a figure from June that
was off by 3.6×).

⚠️ **`graphify update` ajoute, il ne retire pas.** Remesuré le 2026-09-11 **après une
régénération fraîche** — et c'est le point : **24 fichiers** y sont référencés alors
qu'ils n'existent plus sur le disque (177 nœuds, 1,9 % — c'était 17 / 145 le
2026-08-28, donc le résidu GRANDIT à chaque régénération). On y trouve d'anciens
modules devenus des paquets (`utils/pdf_exporter.py`, 56 nœuds ;
`views/trigger_algo/_common.py`, 24), un dossier `archive/` supprimé, des watchers
retirés (`meta_insight_watcher.py`, `s4a_csv_watcher.py`) et `tests/test_error_handler.py`.
Le rapport envoie vers des modules fantômes. Le compte se rejoue :
`python3 -c "import json,pathlib,collections; g=json.load(open('graphify-out/graph.json')); p=collections.Counter(n['source_file'] for n in g['nodes'] if n.get('source_file')); m={k:v for k,v in p.items() if not pathlib.Path(k).exists()}; print(len(m),'fichiers,',sum(m.values()),'nœuds')"`
Avant d'agir sur un chemin lu dans `GRAPH_REPORT.md`, vérifier qu'il existe — le graphe
oriente, il ne prouve pas. If you
add or rename modules, regenerate so future `Glob`/`Grep` calls see the new
structure.

**Visual exploration** : open `graphify-out/graph.html` **directly in your
browser** (double-click, or `file://` URL). The HTML is standalone — vis-network
JS is bundled inline, no server needed. Features : click-to-inspect panel,
search box, community filter, physics layout, edge-confidence styling
(`EXTRACTED` solid vs `INFERRED` dashed). Generated by `make graph-html`, which
wraps `python3 tools/dev/graphify_render_html.py` — that script calls
`graphify.export.to_html` directly (the CLI doesn't expose this).
````
