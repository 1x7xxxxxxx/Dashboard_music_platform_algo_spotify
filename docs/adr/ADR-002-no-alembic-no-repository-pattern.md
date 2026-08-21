# ADR-002 — No Alembic, no repository pattern, no observability stack

- **Status:** Accepted — **§Migrations ré-examiné le 2026-08-21, conclusion maintenue,
  prémisse corrigée** (voir « Ré-évaluation » en fin de document)
- **Date:** 2026-05-14
- **Deciders:** @1x7xxxxxxx

## Context

A reference architecture from an internal Airbus project (`msdr_predictive_maintenance`, industrial safety-critical) was reviewed against the current streaMLytics layout. That reference uses, among other things:

- Alembic-managed schema migrations with versioned Python scripts
- A repository pattern in `database/repositories/` (one file per domain object)
- A `domain/` DDD layer separating business rules from data access
- A full observability stack (Prometheus + Grafana + OpenTelemetry collector)
- An `infra/` directory grouping all IaC and Docker configs
- A streaming pipeline (Redis Streams + MQTT + finite-state-machine consumers)
- Disaster Recovery automation (nightly pg_dump rotation, NAS rsync, DR rehearsal CI)

The question was whether streaMLytics should adopt any of these. The two projects are not comparable: msdr is hardware-attached, has machine-safety constraints, must replay deterministically against fixtures, and runs on customer IPCs with no operator on call. streaMLytics is a multi-tenant SaaS dashboard on top of a CRUD-heavy Postgres schema; it has no real-time control loop, no SLA below "best-effort", and 1 deploy target.

## Decision

streaMLytics rejects the following msdr patterns and continues with the existing simpler equivalents:

1. **Migrations**: keep flat `migrations/NNN_<topic>.sql` files (26 in place, all idempotent `CREATE … IF NOT EXISTS` / `ALTER TABLE IF EXISTS`). No Alembic.
2. **Data access**: keep `PostgresHandler` (psycopg2 wrapper with `_ALLOWED_TABLES` allowlist) called directly from views and collectors. No `database/repositories/` layer.
3. **Domain**: no `domain/` DDD layer. Business rules (artist filter, plan gate, role check) live in `src/dashboard/auth.py` and the views themselves.
4. **Observability**: keep `docker-compose logs` + the existing email alert system. No Prometheus / Grafana / OpenTelemetry.
5. **Infra dir**: keep the 3 Dockerfiles + `docker-compose.yml` at the repo root. No `infra/` subdir.
6. **Streaming**: no Redis Streams, MQTT, or FSM consumers. Data arrives by API polling (Airflow DAGs) or CSV upload — both batch, both already implemented.
7. **DR automation**: no nightly `pg_dump` rotation, NAS rsync, or DR rehearsal workflow. The current Postgres volume is on local Docker; backup/restore is operator-driven.

Three msdr patterns are **adopted** in the same review (see Brick 32 Phase B DEVLOG entry): `Makefile`, `pyproject.toml + uv`, and a split CI/CD into three workflows. Those carry low cost and clear benefit regardless of project criticality.

## Consequences

### Positive

- **Zero migration cost** on existing schema: 26 SQL files keep working; no risk of an Alembic env desync silently dropping a column.
- **Onboarding stays cheap**: one mental model (`db.fetch_df(sql, params)`), no repository / domain / service indirection to navigate.
- **No infra bloat**: a junior dev can boot the stack with `make up` and read everything in 30 minutes.
- **No false confidence**: the rejected items (DR rehearsal, Prometheus alerts) would *look* enterprise-grade without delivering value here — refusing them keeps expectations honest.

### Negative / Trade-offs

- **Schema rollback is manual**: reverting a botched migration means writing a reverse SQL by hand, no `alembic downgrade -1`.
- **Mocking in tests is heavier**: without a repository layer, tests mock `PostgresHandler` directly (cf. `test_postgres_handler.py`, `test_live_pulse.py`). Refactor cost grows with schema size — revisit if `_ALLOWED_TABLES` passes 100 entries (current: ~50).
- **Observability is reactive**: a slow query or rising error rate is only visible by tailing logs. If user complaints start arriving for latency reasons, this ADR is the first to revisit.
- **Coupling**: business rules sit next to render code (in views), so a non-trivial policy change touches the UI file. Acceptable while the policy set is small (artist filter, plan gate, role check); reconsider if the count doubles.

### Neutral / Operational

- Any new contributor reading this ADR should know: simpler is *deliberate*, not lazy. The msdr patterns are real, useful, and rejected here because the criticality budget doesn't justify them.
- If streaMLytics ever moves toward (a) regulated data (health/finance) or (b) multi-region with hard SLAs, this ADR is the trigger to re-evaluate Alembic + observability first.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Adopt msdr fully | Multi-week refactor with no user-visible benefit; risks breaking the 26-migration history. |
| Adopt Alembic only, keep the rest | Alembic shines when migrations are large and need rollback; here they are <50 lines each and the project has never needed a rollback in 32 bricks. |
| Adopt observability only | A Prometheus+Grafana stack here would be ~5 services in `docker-compose.yml` for two dashboards nobody watches. Defer until there is an actual operator role to consume them. |
| Adopt the repository pattern only | The win is mockability for tests — already achieved with `MagicMock(db.fetch_query)` (cf. `test_live_pulse.py`). Net zero benefit at this scale. |

---

## Ré-évaluation du §1 (Migrations) — 2026-08-21

L'ADR disait : *« keep flat `migrations/NNN_<topic>.sql` files (26 in place, **all
idempotent** `CREATE … IF NOT EXISTS` / `ALTER TABLE IF EXISTS`). No Alembic. »*

**Cette prémisse est fausse aujourd'hui, et l'était déjà en partie.** Mesuré :

- elles sont **70**, pas 26 ;
- elles ne sont **pas** toutes idempotentes. `024_s4a_song_playlist_adds_redesign.sql`
  fait `DROP CONSTRAINT` **sans garde** puis échoue à recréer la clé (sa version à trois
  colonnes est devenue impossible depuis que `044` l'a rendue window-aware). Cinq
  fichiers émettent une erreur à chaque passage ;
- **rien n'enregistre quelles migrations ont été appliquées** : aucune table
  `schema_migrations`, aucun `alembic_version`. La stratégie est donc de **tout
  réappliquer à chaque fois**, ce qui est précisément pourquoi `024` échoue à chaque
  exécution ;
- deux incidents de production en découlent, tous deux catalogués :
  `migration-ahead-of-its-code` (065 appliquée avant son code → collecte YouTube cassée
  en minutes) et `migrate-heals-only-if-run-to-completion` (le cycle complet répare
  024 via 044 — un cycle interrompu laisse la table sans clé primaire) ;
- et une dérive silencieuse côté développeur : `local-db-drifts-from-canonical`.

### La conclusion tient quand même : toujours pas Alembic

Trois raisons, dont une est décisive :

1. **L'`autogenerate` d'Alembic — sa fonction phare — exige des modèles SQLAlchemy. Ce
   dépôt n'en a aucun** (`grep -rl sqlalchemy src/` → vide) : l'accès aux données passe
   par `PostgresHandler` en SQL brut. Adopter Alembic sans ORM revient à écrire le même
   SQL dans `op.execute("…")`, avec une couche de cérémonie en plus et aucun des
   bénéfices annoncés.
2. **Le `downgrade` serait une fiction.** Écrire un `downgrade()` juste pour 70
   révisions rétroactives coûte des jours, et personne ne le testerait — un rollback
   jamais exécuté est un rollback qui ne marche pas le jour où on en a besoin.
3. Le risque que l'ADR nommait — *« an Alembic env desync silently dropping a column »* —
   reste réel et non compensé.

### Mais le vrai défaut n'est pas « pas de framework », c'est « pas de registre »

Aucun des cinq problèmes ci-dessus ne vient de l'absence d'Alembic. Ils viennent tous du
fait que **rien ne sait quelles migrations ont déjà tourné**. C'est une table et une
boucle, pas un framework :

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT NOT NULL
);
```

`tools/migrate.sh` n'applique alors que les fichiers absents de la table, dans l'ordre,
chacun dans **sa** transaction, et enregistre le passage. Conséquences directes :

- `024` cesse d'échouer — elle a tourné il y a des mois, on ne la rejoue plus ;
- `migration-ahead-of-its-code` reste possible mais devient visible : on voit ce qui
  n'est pas encore appliqué ;
- un fichier modifié après coup est détecté par le `checksum`, ce qu'Alembic ne fait pas
  non plus ;
- la dérive locale se lit d'un coup d'œil : `SELECT filename FROM schema_migrations`
  comparé à `ls migrations/`.

Coût estimé : la table, ~30 lignes dans `tools/migrate.sh`, un amorçage qui insère les 70
fichiers existants comme déjà appliqués, et un test. À faire **avant** la prochaine
migration, pas pendant.

### Les autres déclencheurs de cet ADR, relevés au passage

| §  | Déclencheur que l'ADR s'est donné | État au 2026-08-21 |
|----|-----------------------------------|--------------------|
| 2 (repository) | « revisiter si `_ALLOWED_TABLES` dépasse 100 » (≈50 à l'écriture) | **75** — pas atteint |
| 4 (observabilité) | « si des plaintes utilisateurs arrivent pour la latence » | aucune plainte ; requêtes mesurées à 0,4 ms |
| 7 (DR) | rejeté : « backup/restore is operator-driven » | **dépassé par les faits** : cron `pg_dump` actif en production, 17 sauvegardes sur disque, plus `make backup-test` (restauration à blanc). L'ADR n'avait pas été mis à jour. |

### Le registre a été construit le 2026-08-21 — et ce qu'il a révélé

Fait le jour même de cette ré-évaluation. `schema_migrations(filename, applied_at,
checksum)` + une boucle dans `tools/migrate.sh` qui n'applique que l'absent. Mesuré,
avant / après :

| | avant | après |
|---|---|---|
| fichiers appliqués à chaque exécution | **70** | **0** (`✅ nothing to apply`) |
| fichiers en erreur à chaque exécution | 1 réel + 4 de bruit | 0 |
| fichier modifié après coup | invisible | détecté au `checksum`, **non rejoué** |

L'adoption n'est **pas** silencieuse : sur une base déjà peuplée dont le registre est
neuf, on ne suppose pas que les fichiers ont tourné — on fait un dernier passage complet
et on enregistre ce qui passe. Adopter sur la foi figerait pour toujours une base
partiellement migrée, ce qui n'est pas théorique : la base locale de cette machine avait
justement dérivé du canonique (`local-db-drifts-from-canonical`).

**Ce que le registre a cassé en s'installant, et qu'il faut retenir.** Le changement
paraissait purement additif — il ne fait que *sauter* du travail. En réalité il a modifié
le **contexte de rejeu** dont une instruction non gardée dépendait en silence depuis des
mois : `024` fait un `DROP CONSTRAINT` nu puis échoue à recréer sa clé, ce qui n'était
survivable que parce que `044` repassait derrière. Rejouée **seule** — ce que fait un
registre pour tout fichier qui n'aboutit jamais — elle a détruit la clé de `044` à chaque
exécution, et `s4a_song_playlist_adds` s'est retrouvée **sans clé primaire**. Le mécanisme
de sûreté a commencé par casser ce qu'il protégeait.

Trouvé uniquement parce que la clé a été vérifiée **directement dans `pg_constraint`**
après le passage, au lieu de faire confiance au `✅ no unexpected psql error` du runner.
Le runner disait vrai sur psql et manquait le dégât : l'effet était un cran en dessous de
ce qu'il mesurait. Classe `unguarded-drop-replayed-alone`, gardée par
`tests/test_migrations_are_replay_safe.py`, qui parse chaque migration.

Avant de changer la façon dont un jeu de scripts est **exécuté**, demander ce que chacun
supposait de ses voisins.
