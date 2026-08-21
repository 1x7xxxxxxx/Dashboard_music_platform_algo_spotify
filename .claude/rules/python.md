---
globs: ["**/*.py"]
rex:
  - date: 2026-07-06
    issue: "Ingest-latency instrumentation did a SYNCHRONOUS Redis XADD on the ingestion hot path (acquisition._persist_frame with a PG pool conn checked out; rib_reader.persist inside sync_joiner's budget); and the 11 redis.Redis.from_url sites passed no retry= → a redis-py 8.x bump would turn socket_timeout into a 30s+ blocking call."
    fix: "Sink made fire-and-forget (bounded queue + background daemon thread, drop-on-full — zero network I/O on the hot path); centralized infra/redis_client.py::make_redis_client factory pinning retry=Retry(NoBackoff(),0)+retry_on_timeout=False across all 11 sites; error-class redis-retry-policy-unpinned + grep gate + tests/test_redis_client_factory.py."
    ref: "DEVLOG#2026-07-06; error-classes.md redis-retry-policy-unpinned"
    severity: crit
  - date: 2026-08-20
    issue: "This file was a verbatim copy from the MSDR Predictive Maintenance repo and bound conventions this project does not have: a Redis client factory, an 'ingestion hot path' naming five non-existent modules, and — actively wrong — SQL placeholders written as `?` (SQLite/QuestDB) while every query here uses psycopg2 `%s`."
    fix: "Rewritten against this codebase: foreign conventions removed, placeholder rule corrected to `%s`, and the multi-tenant rules that actually caused two failed beta sessions written down. The 2026-07-06 entry above is kept — it is the history of the rule, not of this project — but its conventions no longer bind here."
    ref: "error-classes.md tenant-identity-falls-back-to-admin; column-name-is-not-its-meaning"
    severity: crit
---

# Python conventions — streaMLytics

> Les deux entrées REX ci-dessus viennent de deux projets différents. La première
> décrit le dépôt d'où ce fichier a été copié ; seules les conventions ci-dessous
> s'appliquent ici.

## Style

- PEP8 ; ruff (E, F, W) est le linter — la CI exécute `ruff check src/ tests/`
- Annotations de type sur toute signature (arguments + retour)
- Jamais `except:` nu — toujours une classe d'exception précise
- 40 lignes maximum par fonction ; au-delà, extraire des helpers
- Pas d'argument par défaut mutable (`def f(x=[])` → `def f(x=None)`)
- Imports : stdlib → tiers → local, une ligne vide entre les groupes
- Docstring d'une ligne, seulement quand le nom ne suffit pas

## SQL

- **Requêtes paramétrées uniquement — placeholders `%s`** (psycopg2). Jamais de
  f-string, `.format()` ni `%` pour une VALEUR.
- Un nom de table ou de colonne interpolé dans une f-string se valide d'abord
  contre un `frozenset` d'allowlist (règle transverse #8).
- Lire les données d'un locataire porte toujours `WHERE artist_id = %s`. Toute
  requête sur `s4a_song_timeline` porte en plus `AND song NOT ILIKE '%1x7xxxxxxx%'`.

## Le locataire — la classe qui a coûté deux sessions de test artiste

- **L'identité d'un locataire n'a jamais de valeur par défaut.** `user_id`,
  `channel_id`, `account_id`, `ig_user_id`, `spotify_artist_id` : absente (chaîne
  vide comprise) ⇒ on saute cet artiste avec un message qui nomme le geste. Jamais
  `x or os.getenv(...)` — l'environnement porte l'identité de l'**admin**. Le repli
  sur l'env reste correct pour les credentials **d'app** (ADR-006).
- **Toute écriture nomme son locataire.** Un payload d'upsert sans `artist_id` sur
  une table scopée laisse la base choisir le propriétaire.
  Garde : `python3 .claude/scripts/audit_tenant_writes.py`.
- **`artist_id` n'est pas toujours le locataire** : sur `artists`, `artist_history`
  et `tracks`, c'est l'identifiant Spotify (VARCHAR) — le locataire y est
  `saas_artist_id` (INTEGER). On raisonne sur le **type**, jamais sur le nom.
- **Un upsert ne transfère jamais la propriété d'une ligne** : `artist_id` n'entre
  pas dans `update_columns`, et la clé de conflit inclut le locataire.
- **Un déclenchement de DAG depuis le dashboard porte `conf={'artist_id': …}`.**

## Erreurs et absences

- **Une lecture qui échoue ne se déguise pas en « rien à lire ».** Une panne de base
  lève (`CredentialLoadError`) au lieu de renvoyer `{}` ; un artiste inconnu lève
  (`UnknownArtistError`) au lieu de retomber sur l'artiste 1.
- Un `except Exception` qui enjambe une lecture de données doit distinguer
  « absent » de « échec », et le dire à l'utilisateur. `except: pass` est réservé à
  l'affichage facultatif.
- Les collecteurs **lèvent** (règle transverse #6) : jamais de `return None` / `[]`
  silencieux dans un `except`.

## Temps

- Les horodatages écrits en base ou renvoyés par l'API sont UTC-aware :
  `datetime.now(timezone.utc).isoformat(timespec="milliseconds")`. `datetime.now()`
  nu est réservé au cosmétique qui ne persiste pas (corps d'e-mail, en-tête PDF,
  suffixe de nom de fichier).
