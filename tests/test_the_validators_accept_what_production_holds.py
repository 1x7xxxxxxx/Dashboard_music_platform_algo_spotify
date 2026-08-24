"""Un validateur qui LÈVE doit accepter tout ce que la production contient déjà.

Classe `validation-bound-invented-not-read-from-the-schema`.

`src/models/meta_ads_validators.py` est branché depuis le 2026-08-24 et **lève** :
un payload refusé arrête la collecte du locataire. Les tests unitaires du modèle ne
peuvent pas voir ce risque — ils lui présentent des payloads écrits à la main, donc
des payloads courts, propres et sans surprise.

Ce qui l'a montré, mesuré le 2026-08-24 avant tout déploiement :

  * `max_length=255` sur `campaign_name` / `adset_name` / `ad_name` était **inventé**
    (les colonnes sont des `text`, sans limite). La production contient une campagne
    de **313 caractères** — un nom généré, avec emoji. Le modèle l'aurait rejetée, et
    la collecte Meta de ce locataire se serait arrêtée dès la nuit suivante.
  * `targeting` était typé `str` alors que la colonne est `jsonb` : le collecteur y
    écrit `json.dumps(...)`, psycopg2 le relit en **dict**. 69 lignes sur 69
    rejetées à la relecture.

Le garde confronte donc les modèles aux LIGNES RÉELLES. Sans base, il skippe — comme
~160 autres tests de ce dépôt ; c'est pour ça que la suite se lance avec
`docker start postgres_spotify_airflow`.
"""
import pytest
from pydantic import ValidationError

from src.models.meta_ads_validators import MetaAd, MetaAdset, MetaCampaign, MetaInsight

# (table, modèle, colonnes exactement dans l'ordre des champs lus)
_CASES = [
    ("meta_campaigns", MetaCampaign,
     "campaign_id, campaign_name, artist_id, ad_account_id, status, objective, "
     "daily_budget, lifetime_budget, start_time, end_time, created_time, "
     "updated_time, collected_at"),
    ("meta_adsets", MetaAdset,
     "adset_id, adset_name, artist_id, ad_account_id, campaign_id, status, "
     "optimization_goal, billing_event, daily_budget, lifetime_budget, "
     "start_time, end_time, targeting, collected_at"),
    ("meta_ads", MetaAd,
     "ad_id, ad_name, artist_id, ad_account_id, adset_id, campaign_id, status, "
     "creative_id, created_time, updated_time, collected_at"),
    ("meta_insights", MetaInsight,
     "artist_id, ad_id, date, impressions, clicks, spend, reach, frequency, "
     "cpc, cpm, ctr, conversions, cost_per_conversion, collected_at"),
]


@pytest.fixture(scope="module")
def db():
    try:
        from src.database.postgres_handler import PostgresHandler
        handler = PostgresHandler.from_env_or_config()
        handler.fetch_query("SELECT 1")
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"pas de Postgres joignable ({type(exc).__name__})")
    return handler


@pytest.mark.parametrize("table,model,cols", _CASES, ids=[c[0] for c in _CASES])
def test_every_row_already_written_still_validates(db, table, model, cols):
    names = [c.strip() for c in cols.split(",")]
    rows = db.fetch_query(f"SELECT {cols} FROM {table}")  # noqa: S608 — table littérale
    if not rows:
        pytest.skip(f"{table} est vide — rien à confronter")

    rejected = []
    for row in rows:
        payload = dict(zip(names, row))
        try:
            model(**payload)
        except ValidationError as exc:
            rejected.append((
                payload.get(names[0]),
                [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                 for e in exc.errors()[:3]],
            ))

    assert not rejected, (
        f"{len(rejected)}/{len(rows)} lignes DÉJÀ ÉCRITES dans {table} sont refusées "
        f"par {model.__name__}. Le validateur lève : la prochaine collecte de ces "
        f"locataires s'arrêtera. Premiers cas : {rejected[:3]}"
    )


def test_no_length_bound_is_declared_without_a_column_to_justify_it():
    """Aucune borne de longueur inventée ne revient par la petite porte.

    Pur, sans base : la question « d'où vient ce 255 ? » n'a de réponse que dans le
    schéma, et une borne qu'aucune colonne ne porte est un refus arbitraire sur de
    la donnée légitime.
    """
    offenders = []
    for model in (MetaCampaign, MetaAdset, MetaAd, MetaInsight):
        for name, field in model.model_fields.items():
            for meta in field.metadata:
                if getattr(meta, "max_length", None) is not None:
                    offenders.append(f"{model.__name__}.{name} (max_length="
                                     f"{meta.max_length})")
    assert not offenders, (
        "borne(s) de longueur déclarée(s) sans colonne qui la porte : "
        f"{offenders}. Les colonnes de noms sont des `text`. Si une vraie limite "
        "apparaît un jour, la lire dans `information_schema`, ne pas la retaper."
    )
