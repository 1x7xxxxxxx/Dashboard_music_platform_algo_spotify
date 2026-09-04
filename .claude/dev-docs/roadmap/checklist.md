# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | tâches ouvertes, bugs ouverts, état de reprise | `/roadmap-done`, `roadmap-keeper` |
| `archive.md` | briques livrées, bugs clos | `roadmap-keeper` (rotation seule) |

`tests/test_roadmap_two_files.py` échoue si la somme des items des deux fichiers change :
une rotation qui rétrécit le dénominateur améliore le pourcentage sans rien livrer.

Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## 📋 Tâches ouvertes (index — détail plus bas)

Index concis des tâches **qu'on peut commencer maintenant**. À la complétion d'une tâche :
`/roadmap-done <id>` la coche dans son bloc détaillé ET la retire de ce tableau **vers
`archive.md`** (CLAUDE.md — flux roadmap).

**Aucune.** R58 — la dernière — a été livrée le 2026-09-04 (voir `archive.md`).

Ne reste que ce qui attend un geste humain, dans la section « 🙋 En attente de toi »
plus bas : **R1**, inviter la bêta. Aucune ligne de code ne la débloque.

---

## 🔖 REPRISE — état au 2026-09-04, aucune tâche de développement ouverte (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R1 -->

**▶️ Une seule tâche ouverte, R58**, ouverte le 2026-09-04 au soir et différée par
celui qui l'a demandée : « on le garde pour maintenant mais on devra y revenir plus tard
après le set up initial validé ». Elle n'attend aucun travail de plomberie — elle attend
un locataire qui ait des données à montrer, donc R1.

**Le reste : zéro `- [ ]` dans ce fichier.** Les 19 derniers ont été **rotés dans
`archive.md` le 2026-09-03 au soir**, marqués `[CLOS — décision, non livré]` : aucun
n'était un travail qu'on pouvait commencer. Huit étaient des décisions de performance
conditionnées par ADR-007 — dont les quatre déclencheurs ont été lus contre la
production et ne sont pas tirés — et trois d'entre elles étaient **dupliquées** entre
deux blocs. Cinq étaient bloquées par l'accumulation de temps (des paires étiquetées
qu'aucune saisie ne fabrique d'avance). Les deux derniers, E1 et E2, étaient la
redite de **R1**, le geste humain porté par la table « En attente de toi » ci-dessous.

Ce qui rouvre chacun est écrit dans son bloc, dans l'archive. Ne reste donc qu'**un**
geste, et lui seul : **R1** — inviter la bêta.

### Ce que le 2026-09-04 (soir) a changé sous cette ligne

Deux lots de parcours artiste, traités et déployés le même jour — DEVLOG « suite 10 »
et « suite 11 ». Vingt remarques, une seule famille : **l'app parlait d'elle-même**.
Les gestes qui la fermaient sont, dans l'ordre de ce qu'ils ont coûté à un artiste :

- un **verdict de connexion calculé et jamais montré** (le `st.rerun()` effaçait le
  message juste avant qu'il s'affiche) ;
- **Apple Music cochable et ne menant nulle part** — aucun onglet, aucun repli, aucun
  message, et éternellement « Suivante » ;
- un **sélecteur d'OS** en tête de chaque onglet alors qu'aucun guide ne dépend plus
  du clavier ;
- une **alerte DAG** qui envoyait remplir `SPOTIFY_ARTIST_IDS`, variable qui doit
  rester vide sous peine de réarmer la fuite de locataire du 2026-08-20 ;
- un **bac à sable qui masquait un conflit d'identité entre deux vrais locataires**
  (classe `exempt-row-hides-others-conflict`, P2).

### Ce que le 2026-09-04 avait déjà changé

Rien n'a été rouvert ; trois choses ont été **retirées ou rendues prouvables**.

- **ADR-014** tranche la stack data moderne (dbt, ClickHouse, DuckDB, dlt, Dagster,
  Parquet/R2, Supabase, ECharts) : tout différé, chaque refus avec un déclencheur
  **calculable**. Le chiffre qui tranche : 43 Mo de base, agrégat à 18,5 ms.
- **Le seul trou de robustesse réel a été comblé** — les 21 sauvegardes vivaient sur le
  disque de la base, et le drill de restauration n'avait aucun appelant depuis juin.
  **Refermé pour de bon le 2026-09-04** : R57 attendait un bucket, donc une carte
  bancaire ; elle est partie sur un dépôt privé chiffré (ADR-015), 22 archives
  distantes, et la restauration a été prouvée **sans le serveur** — archive tirée de
  GitHub, déchiffrée localement, 93 tables. Le geste humain a disparu avec la tâche.
- **Airflow a maigri** : parsing 30 → 300 s, métadonnées 246 → 91 Mo, et les 4
  `*_csv_watcher` **supprimés** — 98,4 % des lignes de métadonnées pour sonder des
  répertoires vides. La page d'import garde désormais le fichier 14 jours, ce qui
  était la seule moitié utile d'un watcher.

**R1 a commencé le 2026-08-30** : premier parcours d'onboarding fait en entier, ~20
remarques de terrain, toutes traitées et déployées (PR #115, migration 079). Aucune ne
portait sur la lenteur — la classe dominante était du texte adressé au mauvais lecteur.
R1 reste ouverte parce que le test n'est pas fini : l'artiste reprend là où il s'était
arrêté.

### Audit du 2026-09-03 — trois jours de tourne sans intervention

La prod tourne depuis 64 jours (`postgres` 2 mois, `dashboard`/`api` 3 jours). **Rien
n'a cassé pendant l'absence** et, pour la première fois, ce n'est pas une déduction :
les surfaces de preuve construites en août ont toutes répondu.

| Ce qui a été lu | Verdict |
|---|---|
| 16 DAGs, 4 jours de runs | **0 tâche Airflow en échec** ; les 4 DAGs sans run récent sont hebdomadaires (`0 * * 1`), pas muets |
| `etl_run_log`, par locataire × plateforme | 1 seule défaillance : `meta_ads_api_daily` / Benken (12), 5 nuits d'affilée, `act_65390907` — **le blocage connu de partage de compte, pas une régression** |
| `check_tenant_contamination` | **0 constat** — aucune ligne sous un locataire qui ne peut pas la porter |
| `check_canary_health` (locataire 14) | 0 problème, et il redit lui-même qu'il ne couvre ni Meta ni Instagram (ADR-010) |
| `check_row_dips` | 0 collecte partielle |
| Sources périmées | 2 : **S4A (88 j) et Apple Music (79 j)** — les deux alimentées par CSV, que personne ne dépose. Attendu, pas un incident (R46) |
| Meta Ads « silencieux » | qualifié `expected_silence` : 34 campagnes connues, aucune active — la vue distingue enfin « pas de données » de « pas de campagne » |
| `app.` / `api.` / apex `streamlytics.fr` | 200, ~0,2 s ; `/health` → `{"status":"ok"}` |
| Sauvegardes | quotidiennes à 03:00, 4 dernières présentes et **croissantes** (1,52 → 1,79 Mo) |
| Disque / RAM | 42 % de 150 Go ; 4,5 Go dispo sur 7,7 |

**Le point le plus utile de l'audit** : le mail nocturne n'est pas parti, et c'est
**décidé**. Le log dit `✉️ not re-sent (constats inchangés depuis le dernier envoi
(2j), renvoi dans 4j ou dès qu'un constat change)`. Un silence obtenu par dédup nommée,
pas un silence par accident — exactement ce que le commit `5d22bd2` visait.

**Ce qui attend une décision, pas un correctif** : `STREAMLYTICS_ALLOW_ARTIST_EMAIL`
n'est posée dans aucun conteneur de prod. Le garde d'audience de PR #121 est donc actif,
et **aucun e-mail ne partira jamais vers un locataire** tant qu'elle n'est pas posée.
C'est l'état voulu aujourd'hui ; c'est aussi la variable à poser le jour où R1 passe à
l'invitation réelle. `verification_email` n'est pas concernée — l'inscription vaut
consentement, et elle part depuis `streamlytics_dashboard`, qui porte bien
`STREAMLYTICS_ENV=production` et ses trois variables SMTP.

> `streamlytics_api` n'a pas `STREAMLYTICS_ENV`. Sans effet aujourd'hui : `src/api/`
> n'importe ni `email_alerts` ni `instance_identity`, donc aucun chemin d'envoi n'y
> passe. À reposer si l'API se met un jour à écrire à quelqu'un.

> La ligne `<!-- reprise: open=… -->` ci-dessus n'est pas décorative : c'est la même
> affirmation que le paragraphe, sous une forme que `tests/test_the_resume_header_is_checked.py`
> peut comparer aux deux tableaux d'index. Une prose ne se vérifie pas ; une prose
> **ancrée** se vérifie.

> ⚠️ Ce bloc nommait encore R13, R17 et R55 le 2026-08-28 alors que les trois étaient
> closes. Le corps du fichier le disait déjà ; c'est l'en-tête qui n'avait pas suivi.
> Une roadmap se périme comme un commentaire, et son en-tête plus vite que son corps :
> c'est la seule partie que `/resume` recopie sans la relire. Les comptes rendus des
> séances du 26 au 30 août ont été **rotés dans `archive.md` le 2026-09-03** — le
> fichier actif était à 42 Ko dont ~80 % d'historique.

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

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
| R1 | E1 — beta privée avec des proches sur `streamlytics.fr` | P3 | **un seul geste : inviter.** Tout le reste est fait au 2026-08-22, déployé et vérifié (`prod == canonique`, 75 migrations, Caddy inclus — l'empreinte de schéma courante est en tête de fichier, un seul chiffre fait foi). Le filet a trois épaisseurs désormais : **(a)** le canari prouve Spotify/YouTube/SoundCloud chaque nuit ; **(b)** Meta et Instagram — qu'aucun canari ne peut couvrir (ADR-010) — sont sondés **chaque nuit sur le compte réel de chaque locataire**, et le message de l'alerte est celui de l'API, plus une devinette ; **(c)** l'artiste voit lui-même sa **matrice Configuré / Répond / Données** sur la page Credentials, l'onboarding et l'accueil, avec un bouton « Vérifier maintenant ». Après chaque inscription, garder le réflexe `make artist-preflight ARTIST=<son id>` — c'est le contrôle avant-données que la sonde nocturne ne peut pas faire. Runbook §5. |

## 🔍 Ce que le graphe de code a sorti (2026-08-23)

Graphe régénéré après 71 jours de péremption (**5468 nœuds / 10691 arêtes / 689
communautés**, contre « 1500+ / 94 » annoncés). Trois constats l'ont justifié ; le
premier concerne l'outil lui-même.

**Le graphe référence 15 fichiers qui n'existent plus** (135 nœuds, 2 %) — `graphify
update` ajoute et ne retire pas. Parmi eux d'anciens modules devenus des paquets
(`views/trigger_algo.py`, `utils/pdf_exporter.py`) et un dossier `archive/` supprimé.
Comme `CLAUDE.md` désigne `GRAPH_REPORT.md` comme la première lecture « avant de
grepper », la mise en garde y est désormais écrite : le graphe **oriente**, il ne prouve
pas. Mon propre inventaire d'orphelins en a été contaminé avant vérification.

**`.claude/dev-docs/architecture.md` annonçait une dépendance inexistante** —
`error_handler.py | Utility | email_alerts`. `error_handler.py` n'est importé par rien
en production. Corrigé sur place.

## 🎨 Notes des tests artistes — ce qui reste (2026-08-23)

~30 notes de terrain (Benken 19/06, GRiNCH 12/08). Plan approuvé :
`~/.claude/plans/unified-mapping-teapot.md`. **Quatre tracks sur cinq sont livrés,
déployés et archivés** sous « R50 · R51 · R52 » et « R53 (1/3) ». Ne restent ici que la
suite de R53 et les questions auxquelles je ne peux pas répondre seul.

### Le fil commun, à relire avant de reprendre

La plupart des notes ne décrivaient **pas du code faux, mais du code correct que rien
n'atteignait** — six occurrences en une séance : la page d'onboarding hors navigation, les
étapes de l'accueil dont la clé de page était jetée, le sélecteur Mac/Windows branché sur
une fonction sans appelant, `secondary_analyses()` écrit le jour de la remarque et
appliqué sur aucune vue dense, les titres SoundCloud déclarés que le DAG n'atteignait
jamais, le PDF des identifiants livré seulement par e-mail.

**Un test de rendu ne dit jamais si une page est atteignable**, et un DAG qui saute un
locataire le journalise proprement. C'est pourquoi rien ne le signalait.

### Les questions, tranchées (2026-08-24)

Les quatre questions qui bloquaient du travail réel ont leur réponse. Deux ont
produit du code ; deux se règlent hors du dépôt, et le dire est la réponse.

**1. Meta multi-comptes : SÉPARÉS.** Chaque compte a son budget, son CPR, ses
campagnes ; un total les mélange sans le dire. C'est ce qui a décidé la forme des
clés d'unicité — voir **ADR-013**, qui traite dans la foulée la question née de
celle-ci : *faut-il faire pareil pour Spotify ?* **Non**, et la raison n'est pas le
volume de travail : ce qui est pluriel chez Meta, c'est l'identité du **payeur**
sous une credential unique ; chez Spotify, ce serait l'identité **artistique**, et
additionner les streams de deux alias ne décrit personne. Un deuxième projet est
déjà un deuxième locataire ; ce qui manquerait le jour où le besoin se présente,
c'est qu'une même connexion en possède plusieurs et bascule entre eux — brique de
comptes, aucune table métier touchée.

**2. Le sélecteur avant l'export PDF : livré**, avec la portée qui a un sens — le
**compte publicitaire**, dès qu'il y en a deux. Le PDF part à un tiers : un CPR qui
mélange deux annonceurs n'est le CPR d'aucun des deux, et le lecteur n'a aucun
moyen de s'en apercevoir. Côté profil d'artiste, il n'y a rien à choisir : le
rapport porte sur le locataire connecté (le sélecteur d'artiste reste admin).

**3. Le « taux de trigger » : trois taux, un par algorithme** — la part OBSERVÉE
des titres de la cohorte d'entraînement, dans ce panier de Popularity Index, qui
ont déclenché Discover Weekly / Release Radar / Radio (`threshold_tables.json`).
Aucun ne « fait foi » sur les autres. **Et le graphique mentait** : un panier dont
`prob` vaut `null` et `n` vaut 0 — aucun titre observé — était dessiné comme une
barre à **0 %**, que le lecteur lit « aucune chance de déclencher ». Cas réel :
Release Radar, panier « 50+ ». De même, 66,7 % mesuré sur **3** titres s'affichait
aussi net que 99,4 % sur 172. Corrigé : effectif écrit sous chaque barre, paniers
peu peuplés atténués, paniers jamais observés non dessinés.
Garde : `tests/test_an_empty_bracket_is_not_a_zero.py`.

**4. La « valeur de démo » : deux candidats trouvés et corrigés, la note d'origine
reste non confirmée.** Aucun KPI codé en dur n'existe dans le dépôt — vérifié.
Mais deux valeurs fausses étaient bien affichées : le compteur public « **N**
artistes utilisent streaMLytics », sur la page d'inscription, comptait **les
canaris que nous créons nous-mêmes** pour surveiller la collecte ; et le nom
d'artiste du **propriétaire de la plateforme** servait d'exemple dans le champ
« Nom d'artiste » de chaque inscription. Les deux sont corrigés parce qu'ils sont
faux, pas parce qu'on est sûr que c'était ça. Si la note visait autre chose, une
capture suffira. Garde : `tests/test_public_counters_count_humans.py`.

**5. Le GIF animé dans les messageries : il ne vient pas de l'application.**
Vérifié : **aucune** balise `<img>`, aucun `MIMEImage`, aucune URL d'image dans le
moindre corps de mail — les trois expéditeurs (`email_alerts`,
`verification_email`, `onboarding_report`) n'envoient que du texte et du HTML sans
ressource distante, pied de désinscription compris. C'est donc le relais (Brevo)
ou l'avatar du compte expéditeur affiché par la messagerie du destinataire —
exactement le même cas que le nom d'expéditeur « Music Cross Platform Dashboard »
tranché le 2026-08-23, qui venait du compte Brevo et écrasait celui du code. Geste
dans Brevo, § « En attente de toi ».


### Ce qui attend un fichier, pas une décision

- **Le CSV de Benj.** Les deux causes probables sont fermées — séparateur `;` (celui
  d'Excel FR) désormais supporté de bout en bout, et l'export « Depuis le début » refusé à
  la détection avec la vraie raison. **Sa cause à lui n'est pas confirmée** : quand le
  fichier arrive, le passer dans `_detect_platform` et corriger la règle qui l'a manqué.

### Une vérification que je n'ai pas pu faire

Le parcours **post-connexion** n'a pas été joué dans un navigateur, faute de compte de test
local : l'atterrissage première connexion sur l'assistant, les étapes cliquables et le
sélecteur d'OS sont couverts par des gardes AST, pas par un clic réel. À faire à la
prochaine session artiste.

---

## Open Bugs

### 🔍 Audit 2026-06-13 — deep multi-dimension (suite 19)

Audit profond post-red-team (perf · correctness · supply-chain · tests · tech-debt), **vérifié en live contre le schéma + données prod**. **Bilan : 1 vrai bug prod + 1 gap de test systémique ; le reste = tech-debt P4 basse urgence. Aucun nouveau risque sécurité/critique.**

**P3 — CORRIGÉ (suite 19b, déployé + vérifié live) :**
- [x] **`/youtube/videos` API cassé (HTTP 500) — schema drift, MÊME CLASSE que `/kpis`** — sélectionnait `views/likes/comments/title` sur `youtube_video_stats` (vraies colonnes `view_count/like_count/comment_count`, pas de `title`). **FIXÉ** : requête sur `youtube_videos` (catalogue par-vidéo : title + view_count/like_count/comment_count). Mergé PR #62, déployé, `/youtube/videos` = **200** confirmé live. *(8 routers audités, youtube était le dernier cassé.)*
- [x] **Gap de test systémique = cause racine `/kpis` + `/youtube`** — les 2 bugs avaient échappé aux tests (routers testés **DB mockée**). **FIXÉ** : `tests/test_api_db_smoke.py` — smoke-test **DB-gated** (comme `test_views_render_smoke`) qui exécute chaque endpoint data contre le vrai schéma (token admin+tenant forgé) et assert no-500 → attrape toute la classe en CI. Aurait fait échouer /kpis ET /youtube.

**P3/P4 — correctness borderline :**
- [x] **2 collectors `return None`** ✅ (2026-06-14) — `youtube_collector.py:45` (chaîne introuvable) **escaladé en `raise ValueError`** (vrai échec → plus de 0-rows-DAG-SUCCESS) + test de non-régression `test_get_channel_stats_raises_on_channel_not_found`. `instagram_api_collector.py:294` (insights code-100, 1 média) **confirmé skip par-item légitime** (l'appelant filtre `None` L322) + commenté explicitement. `_meta_config_fetch.py:168 return []` = 0-créative valide, hors-scope.

**Mesuré & ÉCARTÉ (FP / non pertinent — ne pas re-auditer) :**
- Index `s4a_song_timeline(artist_id, song, date)` → **prématuré** : EXPLAIN ANALYZE = **0.4ms** sur 13794 lignes via l'index `(artist_id,date)` existant. Revisiter à ~10× volume.
- `API_SECRET_KEY` → **SET (64 chars) en prod** : JWT stables au restart, non-issue.
- Sweep schema-drift : 132 candidats bruts → **tous FP sauf le router youtube** (alias `col AS x`, vars f-string `{filt}/{frag}`, fonctions SQL, littéraux, commentaires FR, ON CONFLICT/EXCLUDED).
- Deps `uv.lock` **0 CVE** ; imports morts **0** (ruff F401) ; data-integrity (filtre 1x7 / scoping tenant / clés upsert) **clean** ; secrets git history **0**.

## Brick Status

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.

### Standing ops — incident-driven (no code action)

These are not roadmap bricks; they are operational standing instructions kept here for visibility.

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---

## Long-term ML hardening (roadmap)

- [x] **Phase-2 data acquisition — CLOSED AS MANUAL (2026-06-10, ADR-004).** The 2 ex-imputed features are now sourced from manual entry: `NonAlgoStreams28Days` → `s4a_song_nonalgo_streams`, `HowManySongsDoYouHaveInRadioRightNow` → `s4a_artist_radio_count` (migration 052), captured in the Saisie S4A form, read by `ml_inference.build_features` (default 0 when no entry). **Automatic capture rejected:** the artist confirmed S4A shows the source split on-screen only (no CSV export → parser+watcher impossible), and scraping the authed S4A UI is ToS-violating + per-tenant-credential-heavy + fragile (see ADR-004). **Reopen only if** Spotify exposes the split via a CSV export or official API → then a cheap DistroKid-style parser+watcher. 416 tests pass.
- [x] **Discovery Mode manual input** — DONE 2026-05-31. `migrations/040_s4a_song_discovery_mode.sql` (table mirrors `s4a_song_playlist_adds`: per-song dated opt-in, latest `recorded_at` wins) + `init_db.sql` + `_ALLOWED_TABLES`. `ml_inference.build_features` sources `IsThisSongOptedIntoSpotifyDiscoveryMode` from the latest manual entry (default 0.0). `trigger_algo` gains a "🔭 Discovery Mode" metric + manual opt-in form (after Ajouts playlist). Kept in `_IMPUTED_FEATURES` (drift-excluded) — bounded binary flag, z-score drift is meaningless. End-to-end verified (feature flips 0→1 on opt-in); render-smoke + 321 pytest green. Marginal SHAP weight (rank 13) but un-imputes one of the 3 sourceless features with zero external API.

---

## Pré-déploiement program (2026-06-09)

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.


## Deferred — revisit ONLY if migrating to React (ADR-003 reversal)

Items that are currently irrelevant / worked-around **because of Streamlit** and would become
natural (or need redoing) under a React/Next.js front-end. Parked here per user request
(2026-06-09) so a future migration picks them up. ADR-003 currently keeps Streamlit.

> **PARKED — not open backlog.** Listed as plain bullets (no `[ ]`) **on purpose** so `/resume`
> does not recount them as actionable items. They re-activate only on an ADR-003 reversal
> (migration to React/Next.js). Do not treat them as a to-do until then.

- **PostHog full client-side analytics** — autocapture, **session replay**, heatmaps,
  client funnels/retention. Blocked today: Streamlit strips `<script>` and sandboxes
  `components.html` iframes, and re-runs the whole script (no stable DOM / client event model).
  Under React the standard JS snippet drops in → reconsider PostHog (cloud-w/-consent or
  self-host) and likely retire the homegrown event log's *capture* layer (the `usage_events`
  table can remain as a server-side sink). Needs RGPD consent banner for a 3rd-party processor.
- **Interactive / exact-parity report charts (PDF & in-app)** — the PDF export rebuilds
  every chart in **matplotlib→PNG** (`pdf_charts.py`) because `kaleido` (Plotly→image) is absent
  and Streamlit can't headless-render its Plotly figures. Under React, reports could share the
  *same* chart components (client-side render / a proper reporting service), giving interactive
  + pixel-parity charts and removing the matplotlib duplication. ref: export-pdf overhaul
  2026-06-09.
- **Cold-start bundle / perf** — already audited (line ~295): the #1 cold-start bottleneck
  is the **Streamlit JS bundle** (~532 KiB), not Python. React+Next (code-splitting → ~100–150
  KiB initial) is the structural fix. Python-side caching/lazy-import work stays valid for
  subsequent renders only.
- **Rich client interactions** — anything that fought the rerun model (live event hooks,
  drag/drop, fine-grained widget state, real-time updates without full reruns) becomes
  first-class under React; revisit UX patterns that were simplified to fit Streamlit.
