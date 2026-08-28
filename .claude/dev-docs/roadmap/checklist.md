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

---

## 🔖 REPRISE — état au 2026-08-28, séance close (à lire EN PREMIER au `/resume`)

**▶️ L'index de code est VIDE. Zéro tâche machine ouverte.** Ne restent que **deux**
geste humain, et lui seul : **R1** — inviter la bêta. Il est détaillé au § « En attente
de toi » ci-dessous. R54 est close le 2026-08-28 : l'avatar animé est en place et vérifié
par son destinataire.

> ⚠️ Ce bloc nommait encore R13, R17 et R55 le 2026-08-28 alors que les trois étaient
> closes — R13 le 2026-08-22, R17 le 2026-08-21, R55 le 2026-08-26. Le corps du fichier
> le disait déjà ; c'est l'en-tête qui n'avait pas suivi. Une roadmap se périme comme un
> commentaire, et son en-tête plus vite que son corps : c'est la seule partie que
> `/resume` recopie sans la relire.

### Séance du 2026-08-28 — quatre mails en deux nuits, deux causes

✅ **DÉPLOYÉ ET VÉRIFIÉ EN PRODUCTION** (commit `4b940fe`, migration 078 appliquée).
Point de départ : quatre alertes apportées telles quelles. Le tri d'abord — le lien
`localhost:8080` ne prouve rien (l'UI Airflow de prod est liée à 127.0.0.1), c'est
**l'absence de préfixe `[LOCAL]`** qui tranche : les quatre venaient de la production.
Deux mails par nuit, deux causes distinctes.

| | |
|---|---|
| **Le plantage** | `PostgresHandler()` sans argument dans `_mirrored_identities`, arrivé avec `350ed8d`. Seul site du dépôt. Plus grave que le mail : `xcom_pull` rendant None, la section « credentials manquants » a **disparu des deux alertes consolidées** sans que rien ne le dise, et le dé-bruitage par le miroir n'a jamais tourné. Garde AST lisant la **vraie** signature par `inspect` — un `grep` aurait trébuché sur les commentaires du correctif lui-même |
| **La redite** | Le récapitulatif repartait chaque nuit à l'identique. Mesuré sur les XCom de prod des 25 et 26 : **identiques à deux champs près**, `age_h` (1945.0 → 1969.0) et `when`. Le registre montre **cinq** nuits de suite avec le même sujet, pas deux. `src/utils/alert_repetition.py` empreinte les constats en ignorant la MESURE et en gardant l'IDENTITÉ ; migration 078 |

**Ce que la suppression ne peut pas faire**, et c'est le point : un constat nouveau,
disparu ou de raison changée part la nuit même ; au-delà de `ALERT_REPEAT_SILENCE_DAYS`
(7) le même constat repart, parce qu'un silence permanent est indiscernable d'un moniteur
mort. La nuit supprimée s'écrit `delivery_expected = FALSE`, comme une nuit calme, pour
que `infra_health_cron.sh` ne la lise pas comme une panne du canal d'alerte.

**Le fil : la liste des champs volatils est une liste NOIRE, pas blanche.** Un champ de
constat ajouté demain entre par défaut dans l'empreinte — au pire un mail de trop. Une
liste blanche aurait fait qu'un champ oublié rende deux constats différents
indiscernables, donc supprime un mail dû. Entre trop de courrier et un constat perdu, le
biais est choisi une fois et il va toujours du même côté.

**Et la fixture est le vrai XCom des deux nuits**, pas une forme inventée par le test :
une règle écrite de mémoire aurait laissé passer `age_h` et n'aurait rien supprimé. Un
test garde la RÉALITÉ mesurée, jamais la constante qu'on vient d'écrire.

---

### Archive — séance du 2026-08-26

✅ **DÉPLOYÉ ET VÉRIFIÉ EN PRODUCTION** le 2026-08-26 (commit `350ed8d`).
`prod == origin/main`, aucune reconstruction d'image nécessaire — le scheduler
bind-monte `src/` et `airflow/dags/`. Trois preuves prises **dans le conteneur de
prod** : `diagnosis_text` importable, le rendu produit `<b>`/`<br>`, et
`instance_env() == production` (donc la porte anti-mail hors-prod ne peut pas rendre
la production muette). Puis la preuve sur les **données réelles**, appels API compris :
les diagnostics de Benken (Meta) et GRiNCH (SoundCloud) portent enfin leur moitié
actionnable, dont l'instruction Business Manager qui débloque `act_65390907`.

### Ce que la séance a livré

Sept défauts, sept classes d'erreur, chacune avec un garde **vu rouge par mutation**.
Point de départ : une alerte nocturne de production, puis deux mails d'une instance
LOCALE — provoqués par cette séance même, en redémarrant le Postgres local pour la suite.

| | |
|---|---|
| Diagnostic amputé | `platform_probes` gardait `splitlines()[0]` : les **2 lignes rouges sur 2** perdaient le geste qui répare, dont l'instruction Business Manager qui débloque `act_65390907` |
| Action impossible | « relancer le DAG » sur des sources alimentées par CSV — **2 stale sur 2** |
| Doublons | « Inscrits sans rien connecter » et « Credentials manquants » posent le MÊME prédicat : 11 lignes sur 12 dites deux fois |
| Faux positif | l'admin réclamé chaque nuit pour une identité Spotify **présente sur son miroir** — et c'était la seule ligne que le dé-bruitage laissait |
| Mails de dev | hors production, le silence est désormais le défaut, sur les **deux** chemins d'envoi |
| Montage manquant | `./tools` absent du compose du dépôt ⇒ deux faux rouges en ligne de sujet |
| Import muet | un CSV en `;` n'importait rien et le refus ne nommait rien ; **9 `except:` nus** balayés dans `src/` |

### Deuxième passe — les gardes rouges de la CI (2026-08-26, soir)

`audit_runner --deterministic` signalait **6 classes en HIT**, toutes bloquantes en CI.
Deux causes, aucune dans le code applicatif :

- **Un diff non commité supprimait 4 tests** de `test_claude_config_floor.py`, dont
  **trois sont le `guard:` ou la `signature:`** de classes cataloguées. Le catalogue
  affichait toujours `guarded`. Restaurés (l'amélioration de commentaire du diff est
  conservée), et le catalogue est désormais **parsé par la suite** : un nœud pytest
  nommé qui ne résout plus fait échouer le build. Ce garde a trouvé **13 références
  mortes de plus** — 11 vers la forme À PLAT des skills, migrée le 2026-07-28.
- **La suite tournait avec le mauvais interpréteur.** `/usr/bin/python3` n'a ni
  `apache-airflow`, ni `googleapiclient`, ni `spotipy` : 28 rouges qui disaient
  « environnement », pas « code ». `tests/dep_gate.py` (jumeau de `db_gate`) les
  transforme en skips **criés**, avec l'appariement qui rend ça sûr : `CI` présent ⇒
  aucune porte ne peut sauter. En posant les portes, `test_e2e_two_tenants` s'est
  révélé porter **deux `pytestmark`**, le second écrasant le premier sans bruit.

**Suite : 2 échecs → 0.** De 32 rouges ce matin à zéro, sans toucher au code applicatif.

### Le fil, et il vise les gardes eux-mêmes

**Quatre fois dans la journée, un garde que je venais d'écrire est passé sur sa propre
documentation** — la dernière étant le garde des références mortes, qui trébuchait sur
l'exemple `tests/x.py::TestFoo` écrit dans sa PROPRE fiche — le commentaire français qui expliquait le correctif contenait le nom
recherché. Chaque fois, la réponse a été l'AST. Et deux gardes étaient **vacants** :
l'un ne matchait rien (`status_matrix` n'a pas de f-string), l'autre couvrait deux fois
la même branche. Corollaire : après avoir écrit un garde, le muter n'est pas une
formalité — c'est la seule chose qui prouve qu'il garde quelque chose.

Second fil : **R50/R51/R52 étaient en grande partie déjà faites.** Leurs notes
décrivaient un état d'avant le 2026-08-23. Vérifier chaque point dans le code avant de
cocher a évité de refaire trois briques — et a montré que la roadmap se périme comme
n'importe quel commentaire.


---

### Archive de la séance précédente

#### REPRISE` ci-dessous.

> **L'index de code est VIDE au 2026-08-26.** R49b, R50, R51 et R52 sont descendues
> dans `archive.md`. R50/R51/R52 étaient en grande partie déjà faites : leurs notes
> décrivaient un état antérieur au 2026-08-23, et chaque point a été vérifié dans le
> code avant d'être coché — jamais sur la foi du texte de la roadmap.
>
> Ce qui restait réellement et a été livré ce jour : le séparateur CSV mesuré et le
> refus qui nomme sa raison (R52), le bouton de téléchargement du guide (R50),
> `secondary_analyses()` sur la cinquième vue dense (R51).
>
> Ne restent que des **gestes humains**, ci-dessous. Aucun ne se code.

| id | tâche | prio | statut / déclencheur |
|----|-------|------|----------------------|
| — | *(aucune tâche machine ouverte)* | — | — |


---


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

**P4 — tech-debt / opportunités (basse urgence) :**
- [ ] **Caching** — 4 vues requêtent la DB sans `@st.cache_data` (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). Bénéfice **modeste** à l'échelle actuelle (requêtes <1ms mesurées) ; vrai levier LCP = cache Cloudflare (en cours). Effort M.
- [ ] **`view_session()` migration** — 16 vues encore en `get_db_connection()` legacy (valide mais non-conforme rule #9). Tech-debt, **pas un leak**. Effort M.
- [ ] **171 fonctions >40 lignes** (règle projet) — surtout des `show()` Streamlit (jusqu'à 502 l. `meta_ads_overview`). Lisibilité. Effort L. (cf. `refactor-audit-dashboard.md`)

**Mesuré & ÉCARTÉ (FP / non pertinent — ne pas re-auditer) :**
- Index `s4a_song_timeline(artist_id, song, date)` → **prématuré** : EXPLAIN ANALYZE = **0.4ms** sur 13794 lignes via l'index `(artist_id,date)` existant. Revisiter à ~10× volume.
- `API_SECRET_KEY` → **SET (64 chars) en prod** : JWT stables au restart, non-issue.
- Sweep schema-drift : 132 candidats bruts → **tous FP sauf le router youtube** (alias `col AS x`, vars f-string `{filt}/{frag}`, fonctions SQL, littéraux, commentaires FR, ON CONFLICT/EXCLUDED).
- Deps `uv.lock` **0 CVE** ; imports morts **0** (ruff F401) ; data-integrity (filtre 1x7 / scoping tenant / clés upsert) **clean** ; secrets git history **0**.

### 🚀 Base d'optimisation différée (P4 — déclencheur : ÉCHELLE, pas maintenant)

**FAIT (gratuit, via Cloudflare, ROI élevé, zéro risque)** : cache edge du bundle JS Streamlit (`cf-cache-status: HIT` → attaque le LCP 5.7s), **HTTP/3 + Early Hints + 0-RTT**, Brotli, min TLS 1.2. → *Le vrai levier perf (livraison) est en place.*

**DIFFÉRÉ — à réévaluer à ≥ ~50 artistes actifs / trafic multi-tenant concurrent réel.** Sur la prod actuelle (mono-tenant sain, requêtes <1ms), ces items sont **faible ROI + risque de régression** → on ne refactore pas pour des micro-gains. Cataloguées dans `error-classes.md` (`view-session-adoption`, etc.) + visibles dans graphify (god-nodes).

- [ ] **Caching `@st.cache_data(ttl=300)` sur les 4 vues lourdes** (`spotify_s4a_combined`, `meta_ads_overview`, `export_pdf/csv`, `usage_analytics`). *Gain* : évite la re-requête à chaque rerun Streamlit. *Risque* : cacher la donnée pure (pas `db`/connexion → unhashable), staleness TTL. *Déclencheur* : trafic concurrent / re-renders fréquents ressentis. Effort M.
- [ ] **Migration `view_session()` (16 vues legacy `get_db_connection()`)** — classe `view-session-adoption`. *Gain* : robustesse connexions (graphify : `get_db_connection` = 57 edges). *Risque* : refactor mécanique 16 fichiers = régression. *Déclencheur* : ≥50 artistes / si un leak de connexion apparaît. Effort M.
- [ ] **Splitter les god-functions** (`collect_report_data()` = 69 edges, + 171 fonctions >40 l. règle projet). *Gain* : lisibilité/maintenabilité, **pas perf**. *Risque* : élevé si fait en masse. *Déclencheur* : **au fil de l'eau** quand on touche déjà le fichier (jamais en sweep dédié). Effort L.
- [ ] **Lazy imports** (plotly/sklearn/shap en tête de vue → différer dans les fonctions). *Gain* : cold-start par vue. *Risque* : faible mais large. *Déclencheur* : si latence par-vue ressentie. Effort M.
- [ ] **Index composite `s4a_song_timeline(artist_id, song, date)`** — **prématuré aujourd'hui** (mesuré 0.4ms / 13794 lignes). *Déclencheur* : **~10× le volume de données** (≈140k lignes) ou EXPLAIN qui régresse. Effort S.

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
> **Framing (2026-06-11): input-feature data is DONE — these 4 are TIME-ACCRUAL-blocked, not input-blocked.**
> Manual S4A entry (mig 052) + fresh stream CSVs closed the *input-feature* gap: a single prediction now has all 13 real features. What remains needs data that **accumulates over time / across tenants** and cannot be backfilled by entering today's values: more labelled rows, several tenants, forward trigger-outcomes, a long saves history. Do **not** re-scope these as "blocked on data entry" — the entry is done.

- [ ] **More training data + per-tenant evaluation** — model trained on N=508 / 102 test (single anonymised set). **Blocker = tenant count + label volume, not features:** still one live tenant; entering your own data does not create cross-tenant generalisation evidence. Accumulate live labelled data across artists before trusting absolute probabilities.
- [ ] **Automated retraining on live outcomes** — `data_anon.csv` is a one-time snapshot. **Blocker = forward outcomes accruing in time:** needs `ml_song_predictions` to gather real trigger results (score → submit to playlists → observe DW/RR/Radio weeks later).
  - [x] **Outcome-labelling loop — BUILT 2026-06-12** (the "next concrete sub-step"). `migrations/060_ml_outcome_labeling.sql`: `s4a_song_algo_outcomes` (manual capture of realized DW/RR/Radio 28d streams per song — S4A has no source-split export, ADR-004) + `ml_prediction_outcomes` (training-ready labelled pairs). Pure engine `src/utils/ml_outcome_labeling.py` (`bin_label` with training thresholds 137/130/639, `match_outcome` = earliest snapshot ≥28d post-prediction, `label_predictions` idempotent join). Weekly DAG `ml_outcome_labeling` (Mon 06:00 UTC) + debug. Saisie S4A view extended with a realized-outcome grid (the capture surface). 10 tests, end-to-end verified live (labels (1,0,1) + idempotent re-run), DAG parses in-container. **Labels now accrue whenever you enter realized outcomes** — closes the input half.
    - [x] **Windowed capture + chart 2026-06-12** — `migrations/061`: `s4a_song_algo_outcomes` made window-aware (`time_window` 7d/28d/custom + `period_start/end`; columns renamed `dw_streams`/`rr_streams`/`radio_streams`). Saisie S4A grid now captures 7j+28j + a custom-period section. New Road-to-Algo tab "📈 Streams algos générés" (`_tab_algo_streams.py`): stacked bar = cumulative total + per-playlist (DW/RR/Radio) contribution, with a 7d/28d/custom selector + KPI cards. **The labelling engine still reads ONLY `time_window='28d'`** (model horizon) — 7d/custom are tracking-only. Verified live: labelling ignores 7d/custom decoys, uses 28d. The reframed need (per user): not predicting *when* algos trigger, but measuring *how many streams* they generate once triggered.
  - [ ] **Champion/challenger retraining DAG** — consume accumulated `ml_prediction_outcomes` pairs to retrain + compare vs the live model. Still genuinely blocked: needs enough labelled cycles to have accumulated (forward time + entries). Build once `ml_prediction_outcomes` has a meaningful row count.
- [ ] **RR volume regressor** — suppressed (R²=0.23 group-CV on the log target, notification-CTR noise — v3 honest figure, was misreported ≈0.55). **Phase-2 features have now landed (mig 052) but did NOT lift this:** R²=0.23 is measured on the training set, which already contained both features — serving them live changes serving, not the fit. Revisit needs more/better training *volume* (ties to the two items above); stays classification-only meanwhile.
- [ ] **Resurrection tuning** — thresholds in `detect_saves_resurrection` (min_age 180d, 2x baseline, min_spark 50) are heuristic; recalibrate once a real **saves time-series** exists (an old song's saves spiking months later) — a longitudinal history, not a snapshot.

---

## Pré-déploiement program (2026-06-09)

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.

### E — Post-déploiement : beta privée → growth (séquencé, 2026-06-11)

> **Ordre imposé par l'utilisateur** : déployer (D) → **tester l'app avec des proches (beta privée)** →
> **seulement ensuite** landing + marketing payant. On ne lance pas d'acquisition payante sur une app
> non éprouvée. Détail archi : ADR-005 (déploiement) + `deployment.md`.

- [ ] **E1 — Beta privée avec des proches** (P3, AVANT tout marketing) — `streamlytics.fr` déployé mais
  diffusion **restreinte** (lien partagé à la main, pas de pub). Objectif = éprouver le funnel réel
  (register → vérif email → connexion credentials → upload CSV → KPIs → export) sur des comptes tiers
  réels, détecter les frictions d'onboarding et les bugs multi-tenant que le seul tenant `1x7xxxxxxx`
  ne révèle pas. Sortie = liste de frictions corrigées avant E2.
  Leviers déjà en place : compteur « Live Activity » (`register.py`), onboarding tracker (Brick 29).
  ✅ **PRÉ-REQUIS VALIDÉS 2026-06-13** (test beta réel `127bpmin@gmail.com`, plusieurs passes) : D fait (HTTPS
  live) ; **délivrabilité email résolue** → Brevo + domaine authentifié (DKIM/DMARC), `noreply@streamlytics.fr`
  → **boîte de réception** (le Gmail perso tombait en spam) ; funnel **complet et poli** : inscription allégée
  (nom+email+mdp, slug/username auto-cachés), **login email OU username**, vérif instantanée, welcome + **2 PDF
  FR+EN** en PJ. Bugs corrigés : SMTP env-first (#35), page vérif bloquante (#36), expéditeur dédié (#37),
  app-password Gmail, rebrand (#40), guide bilingue (#43). **Reste** : décider le moment d'inviter + i18n du
  *contenu* des emails (anglais, non bloquant).

- [ ] **E2 — Landing page marketing + pixel + CAPI** (P3 growth, APRÈS E1) — promouvoir l'app via
  campagnes (Meta/Google/TikTok). **Contrainte structurante : Streamlit ne peut pas héberger de pixels
  client** (strippe `<script>`, sandbox iframes `components.html`, re-run complet — cf. item PostHog
  différé § « Deferred »). Donc :
  - [ ] **Landing statique SÉPARÉE de l'app** : `streamlytics.fr` (racine + `www`) → landing **statique**
    (reco **Astro/HTML+Tailwind servi par Caddy** sur Box A = 0 €, contrôle total des `<script>` ;
    alternative no-code Framer/Webflow ~10-25 €/mo). `app.streamlytics.fr` = Streamlit (inchangé),
    `api.streamlytics.fr` = FastAPI. **Ne jamais mettre de pixel dans l'app Streamlit.**
  - [ ] **Pixel client sur la LANDING uniquement** : Meta Pixel + GA4 `gtag` + (option) TikTok pixel →
    `PageView`, `ViewContent`, `Lead` (clic CTA « Essai gratuit »). **Bannière de consentement RGPD +
    Consent Mode v2 AVANT chargement** (UE ; processeur tiers à déclarer dans la privacy policy).
  - [ ] **CAPI server-side depuis FastAPI** (obligatoire ici, pas optionnel) pour les conversions
    profondes que le pixel client rate (cross-domain, ad-block, iOS14) : `CompleteRegistration` à
    l'inscription, `Subscribe`/`Purchase` **branchés sur le webhook Stripe existant**
    (`checkout.session.completed`). Réutilise le SDK `facebook-business` déjà dans `requirements.txt`
    (POST `graph.facebook.com/{PIXEL_ID}/events` + `access_token`). Idem GA4 Measurement Protocol.
  - [ ] **Pont d'attribution (stitching)** — GRATUIT grâce aux sous-domaines : le pixel pose `_fbp`/`_fbc`
    (contient `fbclid`) sur le **domaine parent `streamlytics.fr`** → **lisibles par FastAPI sur
    `api.streamlytics.fr`**. Au register : persister `_fbp`/`_fbc` + `UTM`/`fbclid`/`gclid` (passés en
    query string landing→app) + **email hashé SHA-256** + IP + user-agent sur la ligne user. **Dédup
    pixel↔CAPI par `event_id` partagé.** Jamais d'email en clair (Meta exige SHA-256).
  - **Mapping d'événements exact** (quel event à quelle étape) à préciser au moment de l'implémentation.
  - Note : le `usage_events` server-side (first-party) peut rester comme sink interne ; PostHog
    client-side reste différé (Streamlit) — cf. § « Deferred ».

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
