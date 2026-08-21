# Audit de refactor — 2026-08-20

Commandé après deux sessions de test artiste ratées. La question n'est pas « quel
code est laid » mais **« quel refactor empêche une nouvelle session de rater »**.
Tout ce qui suit est mesuré sur le dépôt, pas estimé.

## Ce que le corpus apporte, et ce qu'il n'apporte pas

Le RAG (`knowledge-rag`, 24 domaines) **ne contient aucun ouvrage de génie
logiciel, de refactoring ni de multi-tenant** — `algo-dev` traite de trading
algorithmique, pas d'architecture. Un seul passage s'applique directement, et il
vaut d'être cité parce qu'il décrit exactement ce qui s'est passé ici :

> « Whenever possible, work with software engineers to fix data-quality issues **at
> the source**. It's surprising how many data-quality issues can be handled by
> respecting basic best practices in software engineering, such as logs to capture
> the history of data changes, **checks (nulls, etc.)**, and exception handling. »
> — Reis & Housley, *Fundamentals of Data Engineering*, p. 387

Et p. 270 : *« Set up checks to ensure that data from the source system conforms
with expectations for downstream usage. »* C'est la description littérale du
préflight ajouté ce jour : les vérifications existaient, elles n'étaient
simplement branchées sur rien.

Le reste de cet audit s'appuie sur la mesure du code, pas sur la bibliothèque.
**Le domaine `ux-frontend` reste vide** (R17) : tant qu'il l'est, les arbitrages
d'ergonomie de ce dépôt sont des choix d'ingénierie, pas des positions sourcées.

---

## A. Ce qui a réellement cassé — corrigé, gardé

Six mécanismes, une seule règle implicite : *identité illisible ⇒ celle de
l'admin ; locataire inconnu ⇒ `artist_id = 1`*. Détail et preuves dans
`error-classes.md` (4 classes P1 + `ast-guard-blind-to-bom`). Les gardes :

| Garde | Ce qu'il empêche | Preuve |
|---|---|---|
| `tests/test_e2e_two_tenants.py` | qu'un locataire reçoive les données d'un autre | 7 rouges avant / 9 verts après |
| `.claude/scripts/audit_tenant_writes.py` | qu'une écriture omette son locataire | 1 manquant avant / 0 après |
| `tests/test_views_render_smoke.py` (+15 vues non-admin) | qu'une vue casse pour un compte vide | 57 vues rendues |
| `tests/test_freshness_and_readiness_db.py` | que le voyant mente | 3 rouges avant / 7 verts après |
| `make artist-preflight` | qu'on invite quelqu'un sur une prod cassée | 5 étapes, arrêt au 1er rouge |

## B. Le refactor qui vaut le coût — par ordre de rentabilité

### B1. ~~Supprimer les `DEFAULT 1` sur `artist_id`~~ — ✅ **FAIT** (migration 068)

C'est le filet qui a laissé `track_popularity_history` écrire tous les locataires
sous l'admin pendant des mois. `audit_tenant_writes.py` attrape désormais l'oubli
côté code ; le `DEFAULT` le rattrape encore côté base. Les deux doivent tomber.
**Livré** : `migrations/068_drop_artist_id_defaults.sql` retire le DEFAULT sur les
55 colonnes concernées **et** pose `NOT NULL` sur 81 — l'oubli du locataire devient
fatal, donc visible. Vérifié : la suite complète (805 tests) passe contre une base
portant la migration. ⚠️ Elle attend le déploiement du code (bannière d'ordre) :
appliquée maintenant, elle ferait échouer le DAG Spotify encore en production.

Deux enseignements en sont sortis : `tracks.saas_artist_id` reste **volontairement**
nullable (un titre que personne ne revendique appartient au catalogue, pas à un
propriétaire inventé), et `artist_id` **n'est pas toujours le locataire** — sur
`artists`, `artist_history` et `tracks` c'est l'identifiant Spotify (VARCHAR).
Classe `column-name-is-not-its-meaning` : on raisonne sur le TYPE, pas sur le nom.

### B2. ~~Un seul `_db_ready()`~~ — ✅ **FAIT** (`tests/db_gate.py`)

**Livré** : `tests/db_gate.py` — `pytestmark = requires_live_db()` en une ligne.
Les trois nouveaux modules DB l'utilisent ; les deux anciens (`test_api_db_smoke`,
`test_views_render_smoke`) gardent leur copie tant qu'on ne les touche pas
(au fil de l'eau).

### B3. Une seule fabrique de connexion — **P3**

**5 modules** appellent `psycopg2.connect` directement (`credential_loader`,
`circuit_breaker`, `dag_run_logger`, `stripe_webhook`, `postgres_handler`), chacun
relisant `DATABASE_*` à sa façon. `credential_loader` en a trois copies dans le
même fichier. → une fonction unique qui honore `DATABASE_URL` **puis** les
`DATABASE_*`. *Gain concret* : c'est cette divergence qui a fait que mes tests E2E
devaient réinjecter `DATABASE_HOST` à la main pour que le code DAG voie la même
base que le test.

### B4. Les 35 `except Exception: pass` — **P2 sur le chemin de données, P4 ailleurs**

307 `except Exception` dans `src/`, dont **35 suivis d'un `pass` nu**. Tous ne se
valent pas :

- **À traiter** : ceux du chemin de données ou de credentials —
  `views/credentials/_core.py:258`, `views/onboarding.py:46` (celui-là avale
  l'échec de lecture des plateformes configurées : l'artiste voit « non connecté »
  sans savoir pourquoi), `transformers/s4a_csv_parser.py:135`.
- **Acceptables** : les `except: pass` d'affichage (un graphique optionnel qui ne
  s'affiche pas ne corrompt rien).

La règle utile n'est pas « interdire `except Exception` » mais : *un `except` qui
enjambe une lecture de données doit distinguer « absent » de « échec »* — la
correction faite ce jour sur `credential_loader` et `freshness_monitor`.

### B5. Migration `view_session()` — **P4, différé, et c'est justifié**

18 vues utilisent encore `get_db_connection()`. Ce n'est **pas** une fuite : c'est
une non-conformité à la règle #9. Le déclencheur reste ≥50 artistes. À faire au fil
de l'eau quand on touche déjà le fichier — jamais en balayage dédié.

### B6. Les 201 fonctions > 40 lignes — **P4, au fil de l'eau uniquement**

| Fonction | Lignes |
|---|---|
| `_show_meta_ads` (meta_ads_overview) | 502 |
| `show` (admin) | 405 |
| `show` (data_wrapped) | 367 |
| `_show_tab_budget_roi` | 351 |
| `send_consolidated_alert` (alert_monitor) | 304 |

Ce sont presque tous des `show()` Streamlit — de la mise en page séquentielle, pas
de la logique enchevêtrée. Les découper en masse est un risque de régression pour
un gain de lisibilité seul. **Une exception mérite d'être traitée** :
`send_consolidated_alert` (304 l.) est de la logique, pas de l'affichage, et c'est
le seul canal d'alerte du système — s'il casse, plus rien ne remonte.

## C. Les erreurs encore possibles, honnêtement

Ce qu'aucun garde ne couvre aujourd'hui :

1. ✅ **RÉSOLU** — deux locataires ne peuvent plus déclarer le même identifiant :
   `find_identity_conflict()` refuse à l'enregistrement, sur les 4 plateformes, en
   nommant le champ et la valeur. Un test vérifie qu'**aucune plateforme du registre
   ne peut être ajoutée sans règle d'unicité**.
2. ✅ **RÉSOLU** — le déclenchement rend son résultat :
   `src/dashboard/utils/collection_progress.py` garde le `run_id`, lit l'état à
   chaque rerun et **traduit l'échec en geste** (chaîne « … - Topic », partage de
   compte pub, token expiré…). Un échec non reconnu renvoie `None` plutôt qu'une
   explication inventée.
3. **`meta_campaigns/adsets/ads`** gardent leur PK plateforme (15 FK). Deux
   locataires sur le même compte pub n'auront qu'une ligne au lieu de deux. Plus de
   vol de propriété, mais pas encore de duplication légitime (R24).
4. ✅ **RÉSOLU** — `make schema-check` compare désormais les **contraintes et les
   index uniques**, par définition et non par nom. Premier passage : trois dérives
   réelles inconnues (migrations 066 et 067, appliquées en prod). Il ne reste que la
   divergence YouTube, attendue et tracée (R25).
5. ✅ **RÉSOLU** — `tests/test_signup_funnel_db.py` couvre la création de compte :
   paire user/tenant atomique et liée, compte non vérifié avec jeton, mot de passe
   non stocké en clair, slug unique, et surtout **le locataire frais est cohérent**
   (aucune ligne, readiness « à connecter »).

## D. Ce qu'il ne faut PAS refactorer

- Les `show()` Streamlit longs (B6) : risque > gain, sauf au fil de l'eau.
- **B3 (fabrique de connexion unique)** reste ouvert : 5 modules appellent
  `psycopg2.connect` directement. C'est de la duplication, pas un défaut de
  correction — à faire quand on touchera l'un d'eux, pas en balayage.
- Le repli sur l'environnement pour les credentials **d'app** : c'est ADR-006, et
  c'est correct. Seule l'identité du locataire n'a pas de défaut.
- Les 10 classes heuristiques qui remontent dans `make audit` : arbitrées P4 et
  différées avec un déclencheur écrit. Les rouvrir sans déclencheur, c'est refaire
  le débat au lieu du travail.
