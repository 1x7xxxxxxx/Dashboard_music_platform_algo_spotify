"""L'activation se lit dans la DONNÉE, jamais dans le journal d'exécution.

Type: Guard
Uses: ast, src.utils.activation, src.utils.source_registry, live Postgres (optionnel)
Depends on: src/utils/activation.py, src/utils/source_registry.py
Persists in: nothing

LE CHIFFRE QUI A DÉCIDÉ — relevé EN PRODUCTION le 2026-09-22
-------------------------------------------------------------
`activation_sql` comptait la livraison avec `status = 'success' AND rows_inserted > 0`.
Le docstring du module se contredisait lui-même en le justifiant : il citait l'artiste 13
(« trente `success` à zéro ligne sur SoundCloud ») pour prouver qu'il fallait exiger
`rows_inserted > 0`, **et il annonçait UNE plateforme pour l'artiste 12, qui en a DEUX.**

Les deux cas, côte à côte, en base de production :

    (12, youtube)           32 `success`, rows_inserted=0 partout  →  95 LIGNES, du JOUR
    (13, soundcloud)        31 `success`, rows_inserted=0 partout  →  0 ligne
    (12, soundcloud)        31 `success`, 31 à >0                  →  672 lignes

Sur les deux paires où le compteur est à zéro partout, **UNE SUR DEUX est un mensonge.**
`rows_inserted = 0` dit « cette exécution n'a rien inséré » — vrai d'un upsert idempotent
qui ne trouve rien de neuf — et jamais « cette plateforme ne livre pas ».

Le prédicat corrigé, rejoué en production le même jour, **diverge sur 3 locataires sur 8** :

    artiste 1 (propriétaire)   5 → 6
    artiste 12 (Benken)        1 → 2
    artiste 18 (bac à sable)   0 → 4

Le titre (2 activés sur 5) ne bouge pas, parce que `ACTIVATION_MIN_PLATFORMS = 1` et que
Benken comptait déjà par SoundCloud. **Ce qui bouge est le mécanisme** : un locataire dont
la seule plateforme vivante livre par upsert idempotent serait listé DORMANT tout en
recevant de la donnée fraîche chaque jour.

CE QUE CE GARDE TIENT
---------------------
1. **Aucune lecture d'`etl_run_log` dans le SQL rendu** — le geste qui ramènerait la classe.
2. **Chaque branche est scopée sur le locataire** : une branche sans scope compterait la
   flotte et activerait tout le monde.
3. **Le SQL est VALIDE**, exécuté contre la base quand elle est là. C'est le test qui
   aurait attrapé le défaut réel du premier jet : `SELECT … LIMIT 1` dans une branche
   d'`UNION ALL` est refusé par Postgres (« syntax error at or near UNION »), et retirer
   le `LIMIT` sans rien d'autre aurait été PIRE que l'erreur — le `COUNT(*)` extérieur
   aurait compté les LIGNES, et une source à 672 lignes aurait rendu une activation de 672.
4. **On compte des PLATEFORMES, pas des lignes** : le compte ne peut pas dépasser le
   nombre de sources du registre. C'est la borne qui distingue les deux erreurs ci-dessus.
5. **Les identifiants viennent d'une allowlist dérivée du registre** (règle transverse 8).

⚠️ CE QU'IL NE TIENT PAS
------------------------
* **La JUSTESSE de la fenêtre de 30 jours.** Un seuil se calibre sur la distribution ;
  celui-ci est aligné sur les compteurs d'inscription pour qu'un ratio garde un sens, et
  rien ici ne le mesure.
* **Le geste voisin le plus proche : les AUTRES surfaces qui concluent sur la donnée en
  lisant le journal.** Le balayage du 2026-09-22 n'en a trouvé aucune vivante — les usages
  restants de `rows_inserted` sont l'écrivain (`dag_run_logger`) et deux écrans qui
  l'affichent comme un volume, étiqueté « Lignes insérées ». Un troisième lecteur qui
  reviendrait à `etl_run_log` pour une question de DONNÉE ne serait pas vu ici.
* **Qu'une source du registre soit la bonne table.** Le registre est tenu à la main.
"""
from __future__ import annotations

import re

import pytest

from src.utils.activation import (
    ACTIVATION_MIN_PLATFORMS,
    ACTIVATION_WINDOW_DAYS,
    activation_sql,
    dormant_tenants_sql,
)
from src.utils.source_registry import SOURCES

_SQLS = {"activation_sql": activation_sql(), "dormant_tenants_sql": dormant_tenants_sql()}


def test_the_registry_has_enough_sources_to_guard() -> None:
    """NON-VACUITÉ. Un registre vide rendrait tout ce qui suit vert pour rien."""
    assert len(SOURCES) >= 5, (
        f"seulement {len(SOURCES)} source(s) au registre — les tests ci-dessous ne "
        "vérifient presque rien.")
    assert ACTIVATION_MIN_PLATFORMS >= 1 and ACTIVATION_WINDOW_DAYS >= 1


@pytest.mark.parametrize("nom", sorted(_SQLS))
def test_no_activation_query_reads_the_execution_log(nom: str) -> None:
    """LE geste qui ramènerait la classe.

    ⚠️ Sur le SQL RENDU, pas sur la source du module : son docstring nomme
    `etl_run_log` et `rows_inserted` une dizaine de fois pour expliquer POURQUOI ils
    sont partis. Un garde textuel sur le fichier rougirait sur sa propre explication —
    c'est `a-bash-hook-that-blocks-the-prose-about-the-gesture`, mesuré trois fois sur
    ce dépôt le 2026-09-12.
    """
    sql = _SQLS[nom]
    for interdit in ("etl_run_log", "rows_inserted"):
        assert interdit not in sql, (
            f"`{nom}` lit encore `{interdit}`. Le journal d'exécution dit ce qu'une "
            "exécution a INSÉRÉ, jamais ce que la base CONTIENT : mesuré en production "
            "le 2026-09-22, l'artiste 12 porte 32 `success` à zéro ligne sur YouTube et "
            "95 lignes fraîches du jour dans `youtube_channel_history`. Lire la table de "
            "données, via `src.utils.source_registry`.")


@pytest.mark.parametrize("nom", sorted(_SQLS))
def test_every_branch_is_scoped_to_one_tenant(nom: str) -> None:
    """Une branche sans scope compterait la flotte, donc activerait tout le monde."""
    sql = _SQLS[nom]
    branches = [b for b in sql.split("UNION ALL") if "EXISTS" in b or "FROM" in b]
    interessantes = [b for b in branches if re.search(r"\bFROM\s+[a-z_0-9]+", b)]
    assert len(interessantes) >= len(SOURCES), (
        f"`{nom}` ne porte que {len(interessantes)} branche(s) de table pour "
        f"{len(SOURCES)} sources au registre : des sources ont cessé d'être comptées.")
    for b in interessantes:
        if "saas_artists a" in b and "EXISTS" not in b:
            continue                      # la table des locataires elle-même
        assert ("a.id" in b), (
            "une branche ne se corrèle pas au locataire courant (`a.id`) :\n"
            f"{b.strip()[:200]}\n\nElle compterait la FLOTTE, donc tout locataire "
            "serait activé dès qu'un seul reçoit de la donnée.")


def test_only_registry_tables_reach_the_sql() -> None:
    """Règle transverse 8 : les identifiants viennent d'une allowlist dérivée."""
    connues = {s.table for s in SOURCES} | {"saas_artists", "artists"}
    lues = set(re.findall(r"FROM\s+([a-z_0-9]+)", _SQLS["activation_sql"]))
    intruses = lues - connues
    assert not intruses, (
        f"tables hors registre dans le SQL : {sorted(intruses)}. Un nom de table "
        "interpolé se valide contre un `frozenset` dérivé du registre.")


def test_the_sql_follows_the_registry_and_nothing_else() -> None:
    """La composition SUIT le registre — elle ne porte aucune table de son cru.

    ⚠️ CE TEST S'APPELAIT `..._a_table_outside_the_registry_is_refused` pendant dix
    minutes, et ce nom affirmait ce qu'il ne vérifie pas : l'allowlist est DÉRIVÉE du
    registre, donc une source du registre est par construction dans l'allowlist et rien
    ne la « refuse ». Ce qui est vérifiable est que la composition ne connaît AUCUNE
    table en dehors de celles du registre. C'est exactement
    `a-diagram-is-verified-by-looking-at-it` dans sa forme de nommage, corrigé sur
    `tests/test_the_image_ships_with_the_app.py` le matin même : un nom qui promet plus
    que son prédicat est pire qu'un test absent, parce qu'on cesse de vérifier.
    """
    from unittest.mock import patch

    from src.utils import activation as mod
    from src.utils.source_registry import Source

    faux = (Source("Intruse", "table_qui_nexiste_pas", "collected_at", "api"),)
    with patch("src.utils.source_registry.SOURCES", faux), \
         patch("src.utils.source_registry.PAR_CLE", {"Intruse": faux[0]}):
        # La table de la fausse source est dans SA propre allowlist dérivée, donc la
        # composition passe — c'est attendu : l'allowlist protège contre un nom qui
        # n'est PAS dans le registre, pas contre un registre faux.
        sql = mod._livraisons_cte(30)
        assert "table_qui_nexiste_pas" in sql, (
            "la composition ne lit plus le registre : elle ne peut donc plus le suivre.")


@pytest.mark.parametrize("nom", sorted(_SQLS))
def test_the_sql_is_valid_postgres(nom: str) -> None:
    """LE TEST QUI AURAIT ATTRAPÉ LE DÉFAUT RÉEL DU PREMIER JET.

    `SELECT … FROM t WHERE … LIMIT 1` dans une branche d'`UNION ALL` est refusé par
    Postgres — « syntax error at or near UNION ». Aucune relecture ne l'a vu ; la base
    l'a dit en une seconde. Un SQL composé se fait VALIDER par le moteur, pas par l'œil.
    """
    from tests.db_gate import db_ready, dsn

    if not db_ready():
        pytest.skip("Postgres injoignable — la validité d'un SQL ne se lit pas dans le "
                    "code")
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**dsn(), connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(_SQLS[nom])
            lignes = cur.fetchall()
    finally:
        conn.close()
    assert lignes is not None


def test_the_count_is_platforms_not_rows() -> None:
    """LA BORNE qui distingue les deux erreurs possibles du premier jet.

    Retirer le `LIMIT 1` sans passer à `EXISTS` aurait fait compter les LIGNES : une
    source à 672 lignes aurait rendu une activation de 672. Le compte ne peut donc pas
    dépasser le nombre de sources du registre — et il doit être atteignable.
    """
    from tests.db_gate import db_ready, dsn

    if not db_ready():
        pytest.skip("Postgres injoignable — un compte ne se lit pas dans le code")
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**dsn(), connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(dormant_tenants_sql())
            for ligne in cur.fetchall():
                n = ligne[-1]
                assert 0 <= n <= len(SOURCES), (
                    f"un locataire porte {n} « plateformes » pour {len(SOURCES)} sources "
                    "au registre : la requête compte des LIGNES, pas des plateformes.")
            cur.execute(activation_sql())
            actives, total = cur.fetchone()
            assert 0 <= actives <= total, f"actives={actives} total={total}"
    finally:
        conn.close()
