"""La durée des DAG entre dans le résumé quotidien — et une absence n'y devient pas zéro.

Type: Test
Uses: src.utils.daily_ops_metrics
Depends on: migrations/126_daily_ops_metrics_carries_dag_durations.sql
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
La durée d'un DAG n'était exposée **nulle part** : aucune métrique Prometheus, aucune
colonne, aucune règle d'alerte. Elle vit dans `airflow_db.dag_run`, que seule
`views/airflow_kpi.py:173` lit — à la volée, sans rien persister. Relevé en production
sur sept jours :

    meta_ads_api_daily   61,1 s de moyenne · 69,3 s au pic
    instagram_daily      37,2 · 53,2
    soundcloud_daily      9,9 · 10,5
    les six autres       sous 11 s

La question que cette colonne sert, et la seule qui justifie de l'écrire : **la collecte
d'un locataire coûte-t-elle plus cher qu'hier ?** Un DAG dont la durée double est
l'indicateur AVANCÉ de la croissance de données que surveillent les déclencheurs
d'ADR-002 et ADR-007 — bien avant qu'une lecture devienne lente ou qu'un quota saute.

Ce que ce fichier tient
-----------------------
Deux propriétés, et la seconde est celle qui a une histoire dans ce dépôt :

1. la colonne est écrite, et elle est déclarée dans l'allowlist (règle transverse #8) ;
2. **un DAG qui n'est pas parti n'écrit pas `0`.** Un zéro inventé se lit « instantané »
   là où il veut dire « jamais parti ». Ce dépôt a payé cette confusion sur les figures
   (`a-gap-rendered-as-a-zero-by-the-stack`, `absence devient un pixel`) et il n'y a
   aucune raison de la réintroduire dans une table.

⚠️ Et ce que la colonne NE dit PAS, écrit ici parce qu'un lecteur pressé le déduira :
**une durée courte n'est pas une collecte réussie.** Un DAG qui saute tous ses
locataires finit en 2 s et remplit cette colonne comme un succès. Le verdict par
locataire est dans `etl_run_log`, pas ici.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dom():
    import sys
    sys.path.insert(0, str(ROOT))
    from src.utils import daily_ops_metrics
    return daily_ops_metrics


def test_the_column_is_declared_before_it_is_written(dom) -> None:
    """Règle transverse #8 : l'allowlist d'abord, la migration ensuite."""
    assert "dag_durations_s" in dom._WRITABLE_COLUMNS, (
        "`dag_durations_s` n'est pas dans l'allowlist : `write()` lèverait plutôt que "
        "d'écrire, et la colonne resterait vide sans qu'aucun message ne le dise.")
    mig = ROOT / "migrations" / "126_daily_ops_metrics_carries_dag_durations.sql"
    assert mig.exists(), "la migration qui crée la colonne a disparu"
    assert "dag_durations_s" in mig.read_text(encoding="utf-8")


def test_an_absent_dag_writes_no_key_rather_than_a_zero(dom, monkeypatch) -> None:
    """La propriété qui compte : une absence reste une absence.

    On fabrique la réponse de la base de métadonnées — deux DAG qui ont tourné, un
    troisième qui n'apparaît pas du tout, et une ligne dont la durée est `None`
    (exécution commencée et jamais finie).
    """
    class _Session:
        def execute(self, _q):
            class _R:
                @staticmethod
                def fetchall():
                    return [("meta_ads_api_daily", 69.3),
                            ("soundcloud_daily", 10.5),
                            ("weekly_digest", None)]
            return _R()

        def close(self):
            pass

    import sys
    import types
    faux_settings = types.ModuleType("airflow.settings")
    faux_settings.Session = _Session
    faux_airflow = types.ModuleType("airflow")
    faux_airflow.settings = faux_settings
    faux_sa = types.ModuleType("sqlalchemy")
    faux_sa.text = lambda q: q
    precedents = {k: sys.modules.get(k)
                  for k in ("airflow", "airflow.settings", "sqlalchemy")}
    sys.modules.update({"airflow": faux_airflow, "airflow.settings": faux_settings,
                        "sqlalchemy": faux_sa})
    try:
        out = dom._dag_durations()
    finally:
        for k, v in precedents.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    assert out == {"meta_ads_api_daily": 69.3, "soundcloud_daily": 10.5}, (
        f"rendu : {out}. Attendu : les deux DAG qui ont FINI, et eux seuls.")
    assert "ml_scoring_daily" not in out, (
        "un DAG qui n'est pas parti reçoit une clé — un zéro inventé se lit "
        "« instantané » là où il veut dire « jamais parti ».")
    assert "weekly_digest" not in out, (
        "un DAG commencé et jamais fini (`end_date IS NULL`, donc durée `None`) reçoit "
        "une clé. C'est le cas le plus trompeur : il a bien démarré, et lui donner un "
        "chiffre ferait croire qu'il a abouti.")


def test_an_unreachable_metadata_db_yields_an_empty_dict_not_a_crash(dom) -> None:
    """La sonde ne doit jamais faire tomber le résumé quotidien.

    Le module promet dans son en-tête d'écrire la ligne même quand une source est
    muette, avec `complete` honnête. Une sonde qui lève renverrait ce contrat.
    """
    assert dom._dag_durations() == {} or isinstance(dom._dag_durations(), dict), (
        "hors d'un conteneur Airflow, `_dag_durations()` doit rendre `{}` — pas lever.")


def test_the_json_column_reaches_psycopg2_as_a_string(dom, monkeypatch) -> None:
    """`errors_by_page` est déjà du JSONB : la nouvelle colonne suit le même chemin.

    ⚠️ La première version de ce test LISAIT le source et y cherchait
    `json.dumps(values[c])`. `test_a_guard_reads_structure_not_text` l'a refusée — et
    elle avait raison : une chaîne présente dans un fichier ne dit rien de ce que le
    code en fait, et ce dépôt a passé la journée à s'en faire attraper. On appelle donc
    `write()` avec un faux `db` et on regarde ce qui arrive VRAIMENT à psycopg2.

    Sans cela, un `dict` Python partirait tel quel sur une colonne JSONB, et l'échec
    tomberait dans le DAG de 23 h — la nuit, là où personne ne regarde.
    """
    vu: dict = {}

    class _Db:
        def execute_query(self, sql, params=None):
            vu["sql"], vu["params"] = sql, list(params or [])

    monkeypatch.setattr(dom, "collect", lambda db, day=None: {
        "day": "2026-09-18",
        "dag_durations_s": {"meta_ads_api_daily": 69.3},
        "errors_by_page": {"home": 2},
        "complete": True,
    })
    dom.write(_Db())

    assert vu.get("params"), "`write()` n'a rien envoyé à la base"
    cols = [c.strip() for c in vu["sql"].split("(", 1)[1].split(")", 1)[0].split(",")]
    assert "dag_durations_s" in cols, (
        f"la colonne n'est pas écrite du tout. Colonnes vues : {cols}")
    valeur = vu["params"][cols.index("dag_durations_s")]
    assert isinstance(valeur, str), (
        f"`dag_durations_s` part comme {type(valeur).__name__}, pas comme une chaîne "
        "JSON. psycopg2 refuserait un dict Python sur une colonne JSONB.")
    assert "meta_ads_api_daily" in valeur, (
        f"la chaîne envoyée ne porte pas la donnée : {valeur!r}")
