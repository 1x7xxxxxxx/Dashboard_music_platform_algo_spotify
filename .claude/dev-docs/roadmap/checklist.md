# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | index des tâches ouvertes, reprise, tâches parquées, consignes | l'inscription d'une tâche (R196), `make roadmap-close` |
| `archive.md` | tâches livrées ou closes, récits, historique de l'actif | `make roadmap-close` (R199), `roadmap-keeper` pour un lot |

**Le cycle d'une action (R196 · R198 · R199)** : (1) une ligne `| Rnnn | … <!-- critic: requis|non — raison --> | P | mesure |`
dans l'index, commitée seule ; (2) le code, commité avec « Rnnn : … » — refusé sinon, avant
l'édition et au commit ; (3) `make roadmap-close ID=Rnnn NOTE="…"`. La discipline est MESURÉE :
`make roadmap-discipline` (R197), chaque nuit et dans le récap du matin.

Ce fichier reste court (R200, 2026-09-26) : la prose d'historique qui l'avait porté à 499
lignes vit dans l'archive, sous « 🗄️ Historique de l'actif ». Plafond gardé par
`tests/test_the_resume_header_is_checked.py`.

Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next open row."*

---


## 📋 Tâches ouvertes (index — détail plus bas)

Index des tâches **qu'on peut commencer maintenant** — chaque ligne décide de son
code-critic. À la livraison : `make roadmap-close ID=Rnnn` (écrit l'archive, retire la ligne).

| id | Tâche | P | Mesuré par |
|---|---|---|---|
| R620 | REA·A5 — niveaux de tests + seuils de couverture par couche : MESURER la couverture actuelle par couche (collectors, transformers, utils, api, dashboard) → décider oui/non sur le long terme (critère ci-contre, écrit AVANT la mesure) → si oui, design revu par code-critic AVANT le code ; si non, clore avec la mesure <!-- critic: requis --> <!-- scope: pyproject.toml, Makefile, .github/workflows/, tests/, .claude/dev-docs/ --> | P4 | oui si une couche est sous 60 % ; plancher par couche |
| R626 | Retirer les 8 arcs montants cliquetés par R616 (`python3 tools/dev/layer_arcs.py`) : `src/api/deps.py` → `src.dashboard.utils` au niveau module d'abord (l'import de l'API tire la porte du dashboard), puis les modules du dashboard lus par `src/utils` (`i18n`, `platform_timeseries`, `algo_preview_data`, `throttle`, `guide_pdf`, `credentials._registry`) et `src.api.security` vers une couche basse ; puis les 3 DAGs qui importent `src.dashboard.utils.{status_matrix, pdf_exporter, i18n}`, hors cliquet aujourd'hui. Chaque déplacement retire sa clé de `tests/layer_arcs_baseline.json`. **Critic 2026-10-16 : ACCEPT WITH CHANGES** — ordre : arc 5 (fenêtres → `request_throttle`), arc 6 (`output_pdf_path` → `src/utils/guide_paths.py`), arc 2 (plancher ML → `src/utils/ml_floor.py`), arc 1 (`open_db()` sous `src/database/`, la porte du dashboard l'enveloppe), `save_probe` → `src/utils/probe_store.py`, arc 7 (`translate` sans Streamlit, langue explicite), arc 3 (`git mv` platform_timeseries), arc 4 NE PAS déplacer (`CONNECTION_TESTS` appartient au registre : baseline avec sa raison ou dépendance inversée), puis `layer_arcs.py` balaie `airflow/dags/` (onboarding_report → pdf_exporter en baseline avec sa raison). Un commit par arc, importeurs et chaînes `patch()` dans le même commit <!-- critic: requis --> <!-- scope: src/, airflow/dags/, tools/dev/, tests/ --> | P4 | baseline réduite aux arcs justifiés (raison écrite) ; DAGs balayés |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R620, R626, R608, R624, R628, R627 -->

**État au 2026-10-10 (fin de nuit)** : toutes les recos portées en roadmap — R507 tranchée (a), R509 mutmut, R510 inachevés, R511 YouTube Analytics. **État au 2026-10-10 (nuit)** : R501-R508 — passe défauts produit (Hypothesis : iMusician P1, rejets comptés, locale par fichier, bornes), propriétés vague 2, portes de documents allégées, Dependabot uv, cibles make ; études E1-E6 dans `.claude/dev-docs/studies/`. **État au 2026-10-10 (soir)** : R497-R500 — moins de rouges auto-infligés (analyse : 42 % des ids testent le processus, 1 rouge CI sur 15 est un défaut produit) : porte des durées, deux voies, pilote Hypothesis, admission du catalogue. **État au 2026-10-10** : R494-R496 — restes vivants des balayages de R493 et R495 (résolution d’imports au nom importé ; un plantage n’est pas un verdict ; déclencheur p50 non lu). **État au 2026-10-09** : 2ᵉ lot de retours vocaux (W1-W14, `revue/notes-vocales-2026-10-09.md`) → R474-R489, à faire en séance de nuit dans l'ordre de l'index (bugs P2/P3, puis les deux vues réceptrices R476/R477 et le filtre commun R478, puis vue par vue). Avant :  retours vocaux du propriétaire sur l'app → R437-R443 (assistant, mapping, saisie S4A, Hypeddit), toutes livrées et déployées le 2026-10-07 (R442 en option A : le pari du modèle est un onglet admin, les grilles restent chez l’artiste). R116 (ADR-027) et R131
(seuils de charge dérivés par Prometheus) sont livrées le 2026-10-12 : plus aucun bloc ⏸️.
Le récit des journées précédentes est dans l'archive (« 🗄️ Historique de l'actif »).

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Chercher un 3ᵉ worker pytest en baissant la réserve mémoire | `MemAvailable` au repos dépasse durablement **7 220 Mo** SANS éteindre Airflow — c'est-à-dire si le RAG paresseux tient sa promesse (`ps -eo rss` sur `knowledge-rag` après un redémarrage de session) |
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

---

## 🙋 En attente de toi (aucune ne se débloque sans une action humaine)

Elles restent comptées comme ouvertes — rien n'est supprimé — mais elles ne sont pas dans
l'index ci-dessus parce qu'aucune ne peut commencer sans toi. Chacune dit exactement quel
geste elle attend.

📋 **Procédures pas à pas, avec leur vérification :
`.claude/dev-docs/runbook-actions-utilisateur.md`** — classées par ce qu'elles
débloquent, chacune avec la commande qui prouve que c'est fait. `tests/test_roadmap_index_is_honest.py`
échoue si une ligne d'ici n'a pas sa section là-bas.

| id | tâche | prio | le geste qu'elle attend |
|----|-------|------|--------------------------|
| R608 | REA·2 — SECURITY.md — **DÉCIDÉ OUI 2026-10-15** : dépôt PUBLIC, aucune voie de signalement de vulnérabilité (seul contact : l'adresse RGPD de la page confidentialité), signalement privé GitHub (PVR) `{"enabled":false}`. code-critic BUILD-MODIFIED : le fichier ne part JAMAIS avant le canal (sinon le lecteur tombe sur un bouton absent et ouvre une issue publique) ; aucune adresse e-mail dans le fichier ; pas de sonde nocturne (le `GITHUB_TOKEN` ne lit pas ce réglage). Fichier prêt, commité dès que le canal répond `true` <!-- critic: fait --> <!-- scope: SECURITY.md, tests/, .claude/dev-docs/ --> | P3 | **activer le signalement privé** : `gh api -X PUT repos/1x7xxxxxxx/Dashboard_music_platform_algo_spotify/private-vulnerability-reporting` (ou Settings → Security → Private vulnerability reporting → Enable) — runbook §42 |
| R624 | Aucune LICENCE sur un dépôt PUBLIC — **MESURÉ 2026-10-16, décision au propriétaire** : 2 080 fichiers suivis dont 2 jeux de modèles entraînés (`machine_learning/models/v2_noscaler`, `v3`, `.ubj`), 3 PDF d'analyse ML, l'avatar de marque (`assets/brand/`), 5 captures Spotify Wrapped (`docs/spotify_wrapped/`, contenu tiers), aucune donnée locataire. Trois issues : (a) LICENSE propriétaire « tous droits réservés » (recommandé : la marque et les modèles sont l'actif d'un SaaS payant), (b) licence ouverte (le code seul ; modèles et marque à exclure), (c) dépôt privé (Actions : 2 000 min/mois gratuites, le cliquet R608 SECURITY.md devient sans objet). Ton geste : choisir a/b/c ; je rédige ensuite le fichier et sa garde. Avant : (relevé par code-critic sur R608) : par défaut « tous droits réservés », chaque copie publique est non licenciée. MESURER ce que le dépôt contient qui ne doit pas être réutilisé (modèles, données anonymisées, marque) → décider : licence propriétaire explicite, licence ouverte, ou dépôt privé → design revu par code-critic <!-- critic: requis --> <!-- scope: LICENSE, README.md, .claude/dev-docs/ --> | P3 | une décision écrite ; garde : présence de LICENSE si le dépôt reste public |
| R628 | Environnement de PROD conforme au schéma R619 AVANT tout déploiement du dashboard : `serve.py` refuse désormais de démarrer en production si une clé requise manque, et la prod n'a pas `ALERT_EMAIL` (dashboard) ni `STREAMLYTICS_ENV`, `API_STRICT_BOOT`, `FERNET_KEY`, `APP_BASE_URL` (api) — mesuré le 2026-10-15, noms seuls. ⚠️ Tant qu'elle est ouverte : **aucun `deploy.sh dashboard`** <!-- critic: non — geste d'exploitation, aucun code --> <!-- scope: .claude/dev-docs/ --> | P1 | ajouter les clés dans `/opt/streamlytics/docker-compose.yml`, puis `python -m src.utils.env_schema <service>` rend 0 sans ligne dans chaque conteneur (runbook §44) |
| R627 | Accueil : UNE ligne de légende « niveau du dernier relevé reporté » sous la figure d'évolution (le dernier site de R614 ; la fonction pure `carried_level_note` et sa note PDF sont livrées). L'accueil est gelé (R425) : la photo `tests/fixtures/home_snapshot.json` change, ce qui exige `<!-- home: oui -->` sur cette ligne <!-- critic: requis --> <!-- scope: src/dashboard/utils/platform_chart.py, tests/, .claude/dev-docs/ --> | P3 | **ta décision** : l'accueil peut-il porter cette ligne de légende ? oui ⇒ j'ajoute `home: oui` et je livre ; non ⇒ close — runbook §43 |
