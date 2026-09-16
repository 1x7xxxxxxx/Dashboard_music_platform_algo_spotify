"""Une table de TÉLÉMÉTRIE déclare sa rétention. Une table métier garde tout.

Type: Test
Uses: pytest, re
Depends on: migrations/*.sql
Persists in: nothing

Le défaut, mesuré
-----------------
Inventaire du 2026-09-16, fait avant d'adopter Prometheus : **13 tables de télémétrie
dans ce dépôt, UNE SEULE purgée**. `rate_limit_hits` est la seule, et elle n'existe que
parce que `code-critic` a posé la purge en condition bloquante. `usage_events` (une
ligne par interaction), `etl_run_log` (2 196 lignes), `app_error_log` et `monitoring_run`
croissent indéfiniment, sans qu'aucune rétention soit écrite nulle part.

Rien n'échoue jamais. Le jour où un tableau ralentit ou où le disque se remplit, la
cause a des mois d'avance sur le symptôme.

Le distinguo, qui est tout le sujet
------------------------------------
* une table **métier** garde tout — c'est ADR-018, « rien de ce qui est écrasé n'est
  perdu ». La purger serait une perte de donnée ;
* une table de **télémétrie** est un journal, et un journal se rogne.

Confondre les deux fait soit perdre de la donnée, soit garder des traces pour toujours.
Ce test ne devine pas de quel côté une table tombe : **il exige qu'on le dise**, dans le
`COMMENT ON TABLE` de sa migration, au moment où elle naît.

⚠️ Ce test n'impose aucune rétention. Il impose une DÉCLARATION. « Cette table garde
tout, et voici pourquoi » est une réponse parfaitement valide — c'est celle de la
plupart des tables métier.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = sorted((_ROOT / "migrations").glob("*.sql"))

# Les tables que ce test regarde : celles dont le NOM annonce un journal. Le registre
# est explicite parce que « est-ce de la télémétrie ? » est un jugement, pas une
# propriété syntaxique — `artist_history` porte de la donnée métier historisée.
_TELEMETRY = {
    "usage_events", "app_error_log", "etl_run_log", "monitoring_run",
    "rate_limit_hits", "admin_audit_log", "gdpr_erasure_log", "csv_upload_log",
    "etl_circuit_breaker", "etl_daily_metrics", "tenant_platform_probe",
    "active_sessions", "subscription_plan_history",
}

# Une déclaration de rétention, dans un COMMENT ON TABLE ou un commentaire SQL adjacent.
_DECLARES = re.compile(
    r"rétention|retention|purg|efface|conserv[eé]|garde tout|append-only|"
    r"ne grossit pas|une ligne par artiste|jamais effac",
    re.I)


def _created_in(table: str) -> Path | None:
    """La migration qui CRÉE cette table."""
    pat = re.compile(rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{table}\b", re.I)
    for path in _MIGRATIONS:
        if pat.search(path.read_text(encoding="utf-8")):
            return path
    return None


def _retention_comment(table: str) -> str | None:
    """Le `COMMENT ON TABLE` de cette table, où qu'il vive dans les migrations.

    La déclaration n'est PAS forcément dans la migration qui crée la table : une table
    née avant cette règle ne peut pas être corrigée sur place — `schema_migrations`
    détecte au checksum tout fichier modifié après coup et refuse de le rejouer. La
    déclaration arrive donc par une migration ultérieure, et c'est légitime.

    ⚠️ Le DERNIER, pas le premier. `COMMENT ON TABLE` ÉCRASE : c'est le commentaire
    appliqué en dernier qui vit en base. Une version antérieure de ce helper rendait le
    premier trouvé, et quatre tables — `usage_events`, `app_error_log`, `monitoring_run`,
    `tenant_platform_probe` — restaient rouges alors que leur déclaration existait, plus
    loin. Le test lisait un commentaire que la base n'a plus.
    """
    # `;$` en fin de LIGNE, pas le premier `;` venu : une version antérieure utilisait
    # `(.*?);` et coupait la déclaration au premier point-virgule — y compris celui qui
    # vit À L'INTÉRIEUR du littéral SQL (« Une ligne par interaction ; c'est la table
    # qui grossit le plus vite »). Elle lisait donc une demi-phrase et concluait que la
    # rétention n'était pas déclarée. Un délimiteur cherché sans tenir compte des
    # chaînes est un parseur qui se trompe sur le texte le plus soigné.
    pat = re.compile(rf"COMMENT\s+ON\s+TABLE\s+{table}\s+IS\s+(.*?);\s*$",
                     re.I | re.S | re.M)
    last: str | None = None
    for path in _MIGRATIONS:                      # `_MIGRATIONS` est trié
        for m in pat.finditer(path.read_text(encoding="utf-8")):
            last = m.group(1)
    return last


def test_the_migrations_are_readable() -> None:
    """Non-vacuité : un glob vide rendrait l'assertion suivante vraie de rien."""
    assert len(_MIGRATIONS) > 100, f"{len(_MIGRATIONS)} migrations — le chemin a changé ?"
    assert _created_in("rate_limit_hits") is not None, (
        "la table de référence n'est pas trouvée — la détection de `CREATE TABLE` est "
        "cassée, et tout ce fichier serait vert à vide."
    )


def test_every_telemetry_table_declares_what_happens_to_old_rows() -> None:
    """Chaque table de télémétrie DIT ce qu'il advient de ses vieilles lignes."""
    silent: list[str] = []
    for table in sorted(_TELEMETRY):
        if _created_in(table) is None:
            continue                      # table d'un autre âge, ou renommée
        comment = _retention_comment(table)
        if comment is None:
            silent.append(f"{table} — aucun COMMENT ON TABLE")
        elif not _DECLARES.search(comment):
            silent.append(f"{table} — commenté, mais ne dit rien de ses vieilles lignes")
    assert not silent, (
        "table(s) de télémétrie dont la migration ne dit RIEN de ses vieilles lignes :\n  "
        + "\n  ".join(silent)
        + "\n\nCe n'est pas une exigence de purge : « cette table garde tout, et voici "
        "pourquoi » est une réponse valide, et c'est celle de la plupart des tables "
        "métier (ADR-018). Ce qui est refusé, c'est le SILENCE — parce qu'alors "
        "personne n'a tranché, et la table grossit par défaut.\n\n"
        "Mesuré le 2026-09-16 : 13 tables de télémétrie, UNE SEULE purgée, et la seule "
        "ne l'est que parce qu'une critique l'avait exigé en condition bloquante.\n"
        "Remède : une phrase dans le `COMMENT ON TABLE` de la migration."
    )


def test_the_reference_table_really_declares_it() -> None:
    """Contrôle positif : `rate_limit_hits` est l'exemple, il doit passer POUR LA BONNE
    RAISON — sa migration parle vraiment de purge, pas par accident de vocabulaire."""
    path = _created_in("rate_limit_hits")
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "PURGE" in text.upper(), (
        "`122_rate_limit_hits.sql` ne parle plus de purge — le seul exemple correct du "
        "dépôt a disparu, et le détecteur passerait alors sur un autre mot."
    )
