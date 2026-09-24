#!/usr/bin/env python3
"""Ce que le dépôt DÉCLARE contre ce que la base PORTE, colonne par colonne.

Type: Utility
Uses: src/database/postgres_handler
Triggers: `make schema-declared` (lecture seule)
Depends on: init_db.sql, migrations/*.sql, la base joignable
Persists in: nothing

Pourquoi cet outil existe
-------------------------
`init_db.sql` utilise `CREATE TABLE IF NOT EXISTS` — **55 fois**. Sur une base où la
table existe déjà, la déclaration n'est pas appliquée : elle est IGNORÉE, sans un mot.
Une table créée avant que sa ligne n'entre dans `init_db.sql`, ou créée à la main, garde
donc sa forme pour toujours, et le fichier qui prétend décrire le schéma décrit autre
chose.

C'est ainsi que `soundcloud_tracks_daily.track_id` est `bigint` en production et
`character varying` ici (R135), et — trouvé le 2026-09-19 par ce balayage —
`instagram_daily_stats.ig_user_id` est `bigint` **localement** alors que `init_db.sql`
le déclare `VARCHAR`. Deux colonnes, même cause, et la seconde est une **identité de
locataire** : elle se lit `17841402151518986`, un entier au-delà de 2^53.

⚠️ **Conséquence aujourd'hui : aucune, dans les deux cas** — rien ne compare ces colonnes
à une chaîne. Elle apparaîtra à la première jointure ou au premier `WHERE col = %s` avec
un paramètre texte : Postgres refusera (`operator does not exist: bigint = text`), et un
test vert ici échouera là-bas.

⚠️ **Le chiffre brut de ce balayage a été faux au premier jet — 401 au lieu de 44.** Le
parseur prenait `text not null` pour un type : il capturait la ligne, pas la PROPRIÉTÉ
« quel type cette colonne déclare-t-elle ». C'est la même cause que les dix autres
sur-comptages mesurés cette semaine, et elle se corrige en isolant le token de type de
ses modificateurs.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src.database.postgres_handler import PostgresHandler  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[2]

# Le TYPE seul. Le 1er token est le nom de colonne, le 2e le type — éventuellement en
# deux mots (`double precision`, `character varying`, `timestamp with time zone`) — et
# tout ce qui suit est un MODIFICATEUR (`NOT NULL`, `DEFAULT …`, `REFERENCES …`).
_TYPE = re.compile(
    r"^(\w+)\s+"
    r"(double\s+precision|character\s+varying|timestamptz|timestamp(?:\s+with(?:out)?\s+time\s+zone)?|\w+)"
    r"(\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?(\s*\[\s*\])?", re.I)
_MOTS_CLES = {"UNIQUE", "PRIMARY", "FOREIGN", "CONSTRAINT", "CHECK", "EXCLUDE", "LIKE"}

#: Les alias que Postgres normalise. Comparer `serial` à `integer` sans cette table
#: produirait un écart sur chaque clé primaire du dépôt — 122 faux positifs.
FAMILLE = {
    "serial": "integer", "bigserial": "bigint", "smallserial": "smallint",
    "varchar": "character varying", "character varying": "character varying",
    "char": "character", "text": "text",
    "timestamp": "timestamp without time zone",
    "timestamptz": "timestamp with time zone",
    "timestamp without time zone": "timestamp without time zone",
    "timestamp with time zone": "timestamp with time zone",
    "date": "date", "time": "time without time zone",
    "bool": "boolean", "boolean": "boolean",
    "int": "integer", "int4": "integer", "integer": "integer",
    "int8": "bigint", "bigint": "bigint", "int2": "smallint", "smallint": "smallint",
    "numeric": "numeric", "decimal": "numeric", "real": "real", "float4": "real",
    "float": "double precision", "float8": "double precision",
    "double precision": "double precision",
    "jsonb": "jsonb", "json": "json", "uuid": "uuid", "array": "ARRAY",
}


def normaliser(t: str) -> str:
    """Le type, sans son calibre ni ses espaces superflus.

    ⚠️ La première version ne retirait PAS le `(50)` de `VARCHAR(50)`, donc elle rendait
    `varchar(50)` au lieu de `character varying` — un type que rien ne reconnaît. Le
    balayage n'en souffrait pas, parce que `declarations()` sépare déjà le calibre du
    type ; mais tout autre appelant — et le premier fut le garde d'auto-preuve, écrit
    quelques minutes plus tard — recevait un faux négatif silencieux. Une fonction
    publique ne doit pas dépendre du soin de son unique appelant d'aujourd'hui.
    """
    t = re.sub(r"\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\)", "", t)
    return FAMILLE.get(re.sub(r"\s+", " ", t).strip().lower(), t.strip().lower())


def declarations(racine: pathlib.Path = RACINE) -> dict[tuple[str, str], str]:
    """Le type que le dépôt DÉCLARE pour chaque `(table, colonne)`.

    `init_db.sql` d'abord, puis les `ALTER … TYPE` des migrations dans l'ordre — une
    migration postérieure a le dernier mot, sinon toute colonne légitimement élargie
    ressortirait comme une divergence.

    ⚠️ `timestamptz` EST LISTÉ AVANT `timestamp`, et ce n'est pas cosmétique. Une
    alternance d'expression régulière prend la PREMIÈRE branche qui matche, jamais la
    plus longue : `timestamp` ou `mot` avalait le préfixe de `TIMESTAMPTZ` et laissait
    « TZ » derrière lui. Neuf colonnes du dépôt étaient DÉCLARÉES « sans fuseau »
    alors que leur migration dit le contraire, et elles ressortaient en divergence
    permanente — un faux positif qui occupait quatre lignes du plafond.

    Mesuré le 2026-09-22, en ajoutant une dixième colonne qui a rejoint la famille.
    ⚠️ Le cas `TIMESTAMPTZ` de `test_postgres_aliases_are_not_counted_as_divergences`
    passait déjà : il éprouve `normaliser()`, PAS ce lecteur-ci. Le défaut vivait dans
    l'espace entre les deux gardes, chacun vert sur sa moitié.
    """
    out: dict[tuple[str, str], str] = {}
    init = racine / "init_db.sql"
    if init.exists():
        texte = init.read_text(encoding="utf-8")
        for m in re.finditer(
                r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\);", texte, re.S):
            table, corps = m.group(1), m.group(2)
            for ligne in corps.splitlines():
                mm = _TYPE.match(ligne.strip().rstrip(","))
                if mm and mm.group(1).upper() not in _MOTS_CLES:
                    # `TEXT[]` est un tableau : `information_schema` le nomme `ARRAY`,
                    # quel que soit l'élément. Lu comme `text`, `artists.genres`
                    # ressortait en divergence sur TOUTE base, neuve comprise
                    # (2026-09-24 — la seule divergence d'une base provisionnée à neuf).
                    out[(table, mm.group(1))] = "ARRAY" if mm.group(4) else mm.group(2)
    for f in sorted((racine / "migrations").glob("*.sql")):
        for m in re.finditer(
                r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)[\s\S]{0,200}?"
                r"ALTER\s+(?:COLUMN\s+)?(\w+)\s+(?:SET\s+DATA\s+)?TYPE\s+"
                r"(double\s+precision|character\s+varying|timestamptz|timestamp(?:\s+with(?:out)?\s+time\s+zone)?|\w+)",
                f.read_text(encoding="utf-8", errors="replace"), re.I):
            out[(m.group(1), m.group(2))] = m.group(3)
        for m in re.finditer(
                r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)\s+ADD\s+COLUMN\s+"
                r"(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+"
                r"(double\s+precision|character\s+varying|timestamptz|timestamp(?:\s+with(?:out)?\s+time\s+zone)?|\w+)",
                f.read_text(encoding="utf-8", errors="replace"), re.I):
            out.setdefault((m.group(1), m.group(2)), m.group(3))
    return out


def divergences(db, declare: dict | None = None) -> list[dict]:
    declare = declarations() if declare is None else declare
    reels = {(r[0], r[1]): r[2] for r in db.fetch_query(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public'")}
    out = []
    for (table, col), d in sorted(declare.items()):
        reel = reels.get((table, col))
        if reel is not None and normaliser(d) != reel:
            out.append({"table": table, "colonne": col,
                        "declare": normaliser(d), "base": reel})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    db = PostgresHandler.from_env_or_config()
    if db is None:
        print("❌ base injoignable. Lancer : make up", file=sys.stderr)
        return 2
    try:
        ecarts = divergences(db)
    finally:
        db.close()
    if args.json:
        print(json.dumps(ecarts, indent=2, ensure_ascii=False))
        return 0
    print(f"▶ **{len(ecarts)} divergence(s)** entre le type DÉCLARÉ et le type en base\n")
    for e in ecarts:
        print(f"  {e['table']}.{e['colonne']:<24} déclaré {e['declare']:<28} base {e['base']}")
    print("\nRAPPORT SEUL. Corriger demande un `ALTER` sur une table vivante — décision "
          "du propriétaire, pas un effet de bord de séance (R135).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
