"""Le type qu'un fichier DÉCLARE et le type que la base PORTE.

Type: Test
Uses: tools/dev/schema_declaration_check
Depends on: init_db.sql, migrations/*.sql, (optionnel) la base locale
Persists in: nothing

Pourquoi ce garde existe
------------------------
`init_db.sql` utilise `CREATE TABLE IF NOT EXISTS` **55 fois**. Sur une base où la table
existe déjà, la déclaration est IGNORÉE — sans un mot. Le fichier qui prétend décrire le
schéma décrit alors autre chose, et rien ne le dit.

Deux colonnes le portent, mesurées :

* `soundcloud_tracks_daily.track_id` — `bigint` en PRODUCTION, `character varying` ici
  (R135, parquée : corriger demande un `ALTER` sur une table vivante).
* `instagram_daily_stats.ig_user_id` — `bigint` **localement**, déclaré `VARCHAR`.
  Trouvé le 2026-09-19 en balayant la classe de R135. C'est une **identité de
  locataire**, et elle se lit `17841402151518986` — au-delà de 2^53.

⚠️ **Conséquence aujourd'hui : aucune, dans les deux cas.** Rien ne compare ces colonnes
à une chaîne. Elle apparaîtra au premier `WHERE col = %s` avec un paramètre texte, ou à
la première jointure : Postgres refusera (`operator does not exist: bigint = text`). Ce
garde ne corrige donc rien — il empêche le nombre de GRANDIR pendant qu'on regarde
ailleurs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dev.schema_declaration_check import (  # noqa: E402
    declarations, divergences, normaliser,
)

#: Mesuré le 2026-09-19 (44), descendu à 43 le 2026-09-20 par la migration 127, qui
#: rend `instagram_daily_stats.ig_user_id` à son type déclaré. PLAFOND : il descend.
_PLAFOND = 43


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                       # noqa: BLE001 — pas de base = pas de mesure
        return None


def test_the_declaration_parser_reads_types_not_lines() -> None:
    """ANTI-SUR-COMPTAGE. Le parseur doit isoler le TYPE de ses modificateurs.

    ⚠️ Son premier jet rendait **401** divergences au lieu de 44 : il prenait
    `text not null` pour un type. C'est la propriété « quel type cette colonne
    déclare-t-elle », pas la forme « qu'y a-t-il après le nom sur cette ligne ».
    """
    d = declarations()
    assert len(d) > 400, f"seulement {len(d)} colonnes déclarées lues — le parseur a raté"
    mauvais = {k: v for k, v in d.items()
               if any(m in v.lower() for m in ("not null", "default", "references",
                                               "primary key", "unique"))}
    assert not mauvais, (
        f"{len(mauvais)} type(s) déclaré(s) contenant un MODIFICATEUR : "
        f"{list(mauvais.items())[:3]}.\nLe parseur capture la ligne au lieu du type — "
        "c'est ce qui a rendu 401 au lieu de 44.")


def test_normalising_a_type_drops_its_size() -> None:
    """`VARCHAR(50)` et `VARCHAR` sont le même type.

    ⚠️ Écrit APRÈS que le garde d'auto-preuve a rougi dessus. `normaliser` ne retirait
    pas le calibre, donc `VARCHAR(50)` rendait `varchar(50)` — un type que rien ne
    reconnaît, et une comparaison qui échoue en silence. Le balayage n'en souffrait pas
    parce que son parseur sépare déjà le calibre ; le premier autre appelant, oui.
    """
    assert normaliser("VARCHAR(50)") == normaliser("VARCHAR") == "character varying"
    assert normaliser("NUMERIC(10, 2)") == "numeric"


@pytest.mark.parametrize("declare,attendu", [
    ("SERIAL", "integer"), ("BIGSERIAL", "bigint"), ("VARCHAR", "character varying"),
    ("TIMESTAMPTZ", "timestamp with time zone"), ("FLOAT", "double precision"),
    ("INT", "integer"), ("BOOL", "boolean"), ("DECIMAL", "numeric"),
])
def test_postgres_aliases_are_not_counted_as_divergences(declare: str, attendu: str) -> None:
    """FAUX POSITIF fabriqué : `SERIAL` n'est pas une divergence avec `integer`.

    Sans cette table d'alias, CHAQUE clé primaire du dépôt ressortirait comme un écart —
    122 faux positifs, et un rapport que personne ne lit.
    """
    assert normaliser(declare) == attendu


def test_a_migration_that_widens_a_column_is_not_a_divergence() -> None:
    """FAUX POSITIF nº2 : un `ALTER … TYPE` postérieur a le dernier mot.

    Sinon toute colonne légitimement élargie par une migration serait dénoncée, et le
    rapport apprendrait qu'il a tort.
    """
    d = declarations()
    # `collected_at` a été migré vers un timestamp par `019_collected_at_timestamp.sql`.
    migrees = [k for k, v in d.items()
               if k[1] == "collected_at" and "timestamp" in normaliser(v)]
    assert migrees, (
        "aucune colonne `collected_at` ne porte un type `timestamp` dans les "
        "déclarations — les `ALTER … TYPE` des migrations ne sont pas lus, donc toute "
        "migration de type ressortirait comme une divergence.")


def test_the_number_of_divergences_only_falls() -> None:
    """LE CLIQUET. 44 le 2026-09-19 ; il descend quand on corrige, jamais l'inverse."""
    db = _db()
    if db is None:
        pytest.skip("base injoignable — la mesure n'est pas possible")
    try:
        ecarts = divergences(db)
    finally:
        db.close()
    assert len(ecarts) <= _PLAFOND, (
        f"{len(ecarts)} divergence(s) déclaré↔base, contre {_PLAFOND} le 2026-09-19.\n"
        + "\n".join(f"  {e['table']}.{e['colonne']}: déclaré {e['declare']}, "
                    f"base {e['base']}" for e in ecarts[:10]) +
        "\n\n`CREATE TABLE IF NOT EXISTS` n'applique RIEN sur une table qui existe : une "
        "colonne ajoutée à `init_db.sql` sans migration ne changera aucune base déjà "
        "créée, et le fichier décrira un schéma qui n'existe nulle part.\n"
        "Le geste correct est une migration `ALTER TABLE`, pas une ligne de plus dans "
        "`init_db.sql`.")


def test_the_two_identity_columns_stay_text() -> None:
    """Les deux colonnes de R135, CORRIGÉES — ce test garde le correctif, plus le défaut.

    ⚠️ Sa version du 2026-09-19 affirmait l'inverse : elle exigeait que `ig_user_id` SOIT
    divergente, et se contentait d'un `skip` le jour où quelqu'un la corrigerait. C'était
    juste tant que le défaut vivait, et ça devenait un trou dès qu'il mourait — un test
    qui décrit un état plutôt qu'un INVARIANT se périme avec l'état.

    Corrigées par `migrations/127_identity_columns_are_text_not_integers.sql`, vérifiée
    sur l'état de la PRODUCTION reproduit en local (`track_id` remis en `bigint`, les
    deux vues déposées et recréées, 349 lignes intactes, définitions identiques au
    caractère près).
    """
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        divergentes = {(e["table"], e["colonne"]) for e in divergences(db)}
    finally:
        db.close()
    fautives = {c for c in (("soundcloud_tracks_daily", "track_id"),
                            ("instagram_daily_stats", "ig_user_id"))
                if c in divergentes}
    assert not fautives, (
        f"identifiant(s) de plateforme redevenu(s) numérique(s) : {sorted(fautives)}.\n"
        "Ce ne sont pas des nombres — on ne les additionne ni ne les ordonne, on les "
        "compare et on les transmet. `ig_user_id` vaut `17841402151518986`, au-delà de "
        "2^53 : tout passage par JSON ou JavaScript l'arrondirait en silence.\n"
        "Rejouer `make migrate` (migration 127, idempotente).")
