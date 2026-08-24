"""Meta Ads collector — upsert mixin (config + insight persistence).

Type: Sub
Uses: PostgresHandler (via self.db), validate_table (lazy, in-method)
Depends on: _meta_constants (leaf module)

Mixed into MetaAdsApiCollector; methods cut verbatim from the original god-module.
"""
import logging

from ._meta_constants import _ACCOUNT_STAMPED_TABLES, _CAMPAIGN_GRAIN_TABLES

logger = logging.getLogger(__name__)


class _MetaUpsertMixin:
    """Persistence methods for MetaAdsApiCollector."""

    @staticmethod
    def _validate(model, rows: list, table: str) -> list:
        """Refuse un payload que le modèle Pydantic de la table rejette.

        R47 — branché le 2026-08-24. Ces modèles existaient depuis des mois sans
        appelant : `CLAUDE.md` annonçait une couche de validation, `models/` la
        contenait, et rien ne l'exécutait. Une couche écrite et débranchée donne la
        confiance sans la propriété.

        **Lève, jamais ne filtre.** Écarter la ligne fautive et continuer donnerait
        une tâche verte avec des données manquantes — la panne la plus chère de ce
        dépôt (règle transverse #6). Le message nomme l'identifiant fautif, pas la
        ligne entière : un payload d'insight embarque des valeurs de compte.
        """
        from pydantic import ValidationError
        for row in rows:
            try:
                model(**row)
            except ValidationError as exc:
                # Du plus fin au plus grossier : un payload d'ad set nommé par son
                # `campaign_id` envoie chercher au mauvais endroit.
                ident = (row.get('ad_id') or row.get('adset_id')
                         or row.get('campaign_id') or '?')
                errors = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:5])
                raise ValueError(
                    f"{table}: payload refusé pour {ident} "
                    f"(artist_id={row.get('artist_id')}) — {errors}"
                ) from None
        return rows

    def _tag_account(self, table: str, rows: list) -> list:
        """Stamp `ad_account_id` on rows of a table that carries the column.

        **Un seul endroit stampe.** L'alternative — que chaque constructeur de
        payload ajoute la clé dans `_meta_config_fetch` / `_meta_insight_fetch` —
        met la correction à la merci du prochain constructeur écrit : un payload
        non stampé part avec `ad_account_id = NULL`, entre en conflit avec les
        lignes historiques de l'autre compte (`NULLS NOT DISTINCT`, migration 077)
        et se fait écraser. Ici, la question « cette table porte-t-elle la
        colonne ? » a une seule réponse, dérivée de la migration.
        """
        if table not in _ACCOUNT_STAMPED_TABLES:
            return rows
        # `getattr`, comme `_prune_renamed_campaigns` : ce mixin est instancié nu
        # par les tests (jamais via `MetaAdsApiCollector.__init__`), et un attribut
        # supposé présent y lève au lieu de collecter.
        account = getattr(self, "_current_ad_account_id", None)
        return [{**r, 'ad_account_id': account} for r in rows]

    def _upsert_config(self, campaigns: list, adsets: list, ads: list, creatives: list):
        """Upsert the 4 config tables (campaigns/adsets/ads + creative enrichment).

        Called before the insight fetch so a later throttle cannot discard config work.
        """
        from src.models.meta_ads_validators import MetaAd, MetaAdset, MetaCampaign
        try:
            if campaigns:
                self.db.upsert_many(
                    'meta_campaigns', self._validate(
                        MetaCampaign,
                        self._tag_account('meta_campaigns', campaigns),
                        'meta_campaigns'),
                    conflict_columns=['campaign_id'],
                    # artist_id is NOT updatable: a row keeps its first owner.
                    # The conflict key stays campaign_id (its PK is referenced by
                    # 15 FKs — see migration 064's note), so a shared ad account no
                    # longer STEALS a row; it simply does not create a second one.
                    update_columns=[
                        'campaign_name', 'status', 'objective',
                        'daily_budget', 'lifetime_budget', 'start_time',
                        'end_time', 'created_time', 'updated_time',
                        # Provenance: a campaign MOVED between ad accounts (Meta
                        # allows it) must follow, or the UI filters it under the
                        # account it no longer belongs to.
                        'ad_account_id',
                        # See _insight_upsert_maps: an upsert that refreshes the row
                        # and not its timestamp freezes every "last updated" reading.
                        'collected_at',
                    ],
                )

            if adsets:
                self.db.upsert_many(
                    'meta_adsets', self._validate(
                        MetaAdset, self._tag_account('meta_adsets', adsets),
                        'meta_adsets'),
                    conflict_columns=['adset_id'],
                    update_columns=[  # artist_id excluded — see meta_campaigns above
                        'adset_name', 'campaign_id', 'status',
                        'optimization_goal', 'billing_event', 'daily_budget',
                        'lifetime_budget', 'start_time', 'end_time', 'targeting',
                        'countries', 'cities', 'gender', 'age_min', 'age_max',
                        'flexible_inclusions', 'advantage_audience',
                        'publisher_platforms', 'instagram_positions', 'device_platforms',
                        'ad_account_id', 'collected_at',
                    ],
                )

            if ads:
                self.db.upsert_many(
                    'meta_ads', self._validate(
                        MetaAd, self._tag_account('meta_ads', ads), 'meta_ads'),
                    conflict_columns=['ad_id'],
                    update_columns=[  # artist_id excluded — see meta_campaigns above
                        'ad_name', 'adset_id', 'campaign_id',
                        'status', 'creative_id', 'created_time', 'updated_time',
                        'ad_account_id', 'collected_at',
                    ],
                )

            # Enrich meta_ads with creative content (separate upsert, subset of columns)
            if creatives:
                for cr in creatives:
                    self.db.execute_query(
                        """
                        UPDATE meta_ads
                        SET title          = %(title)s,
                            body           = %(body)s,
                            call_to_action = %(call_to_action)s
                        WHERE ad_id = %(ad_id)s
                          AND (%(title)s IS NOT NULL OR %(body)s IS NOT NULL)
                        """,
                        cr,
                    )
        except Exception:
            logger.exception("_upsert_config failed")
            raise

    def _prune_renamed_campaigns(self, campaigns: list):
        """Delete campaign-grain insight rows whose campaign_name no longer exists.

        Campaign-grain tables key by campaign_name, so a campaign RENAME orphans stale
        rows under the old name (ad/adset grains key by id and are immune). Guarded: an
        empty campaign list (failed/partial fetch) is a no-op — never a mass delete.

        **Portée par COMPTE PUBLICITAIRE (R53, 2026-08-23).** Ce `DELETE` était scopé au
        seul `artist_id`. Le jour où la boucle collecteur passera sur deux comptes du
        même artiste — le cas d'une agence — la passe du SECOND aurait effacé tout ce que
        le premier venait d'écrire : sa liste de campagnes ne contient évidemment pas
        celles de l'autre compte. Ce n'est pas une collision, c'est une suppression de
        masse, silencieuse, sur des données de production.

        Le correctif est posé AVANT que le multi-comptes existe, et c'est délibéré : une
        fois la boucle livrée, le défaut aurait été impossible à voir autrement qu'en
        constatant des données manquantes.

        Tant que `ad_account_id` est NULL (toute la flotte aujourd'hui), le prédicat
        `ad_account_id IS NOT DISTINCT FROM %s` avec NULL se comporte exactement comme
        avant — d'où la rétro-compatibilité.
        """
        from src.database.postgres_handler import validate_table
        names = sorted({c['campaign_name'] for c in campaigns if c.get('campaign_name')})
        if not names:
            return
        # Le compte dont ces campagnes viennent. `None` tant que la flotte est
        # mono-compte : `IS NOT DISTINCT FROM NULL` ne touche alors que les lignes
        # elles-mêmes NULL, c'est-à-dire toutes.
        account = getattr(self, "_current_ad_account_id", None)
        try:
            for tbl in _CAMPAIGN_GRAIN_TABLES:
                validate_table(tbl)
                self.db.execute_query(
                    f"DELETE FROM {tbl} WHERE artist_id = %s "
                    f"AND ad_account_id IS NOT DISTINCT FROM %s "
                    f"AND campaign_name <> ALL(%s)",
                    (self.artist_id, account, names),
                )
            logger.info(
                f"  campaign-name prune ran across {len(_CAMPAIGN_GRAIN_TABLES)} "
                f"campaign-grain tables ({len(names)} current campaigns)"
            )
        except Exception:
            logger.exception("_prune_renamed_campaigns failed")
            raise

    @staticmethod
    def _insight_upsert_maps() -> tuple:
        """Return (insight_cols, conflict_cols) for every insight table.

        Single source of truth for the upsert column/key config, shared by the
        per-chunk persistence path (_persist_insights).
        """
        # Columns allowed in each insight table (INSERT uses only these keys)
        _insight_cols = {
                'meta_insights_performance': [
                    'spend', 'impressions', 'reach', 'frequency', 'results',
                    'custom_conversions', 'cpr', 'cpm', 'link_clicks', 'cpc', 'ctr', 'lp_views',
                ],
                'meta_insights_performance_day': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                    'collected_at',
                ],
                'meta_insights_performance_age': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_performance_country': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_performance_placement': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_engagement': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_day': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_age': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_country': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_placement': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights': [
                    'impressions', 'clicks', 'spend', 'reach', 'frequency',
                    'cpc', 'cpm', 'ctr', 'conversions', 'cost_per_conversion',
                ],
            }

        _conflict_cols = {
            'meta_insights_performance':           ['artist_id', 'campaign_name', 'date_start'],
            'meta_insights_performance_day':       ['artist_id', 'campaign_name', 'day_date'],
            'meta_insights_performance_age':       ['artist_id', 'campaign_name', 'age_range'],
            'meta_insights_performance_country':   ['artist_id', 'campaign_name', 'country'],
            'meta_insights_performance_placement': ['artist_id', 'campaign_name', 'platform', 'placement'],
            'meta_insights_engagement':            ['artist_id', 'campaign_name', 'date_start'],
            'meta_insights_engagement_day':        ['artist_id', 'campaign_name', 'day_date'],
            'meta_insights_engagement_age':        ['artist_id', 'campaign_name', 'age_range'],
            'meta_insights_engagement_country':    ['artist_id', 'campaign_name', 'country'],
            'meta_insights_engagement_placement':  ['artist_id', 'campaign_name', 'platform', 'placement'],
            'meta_insights':                       ['artist_id', 'ad_id', 'date'],
        }

        # Ad/adset-level breakdown tables share column sets — generate their 12 entries.
        _perf_bd_cols = ['spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr']
        _eng_bd_cols = ['page_interactions', 'post_reactions', 'comments',
                        'saves', 'shares', 'link_clicks', 'post_likes']
        _bd_dim_keys = {'country': ['country'],
                        'placement': ['platform', 'placement'],
                        'age': ['age_range']}
        for _lvl, _idf in (('ad', 'ad_id'), ('adset', 'adset_id')):
            for _dim, _dimcols in _bd_dim_keys.items():
                _key = ['artist_id', _idf, *_dimcols]
                _insight_cols[f'meta_insights_performance_{_lvl}_{_dim}'] = _perf_bd_cols
                _insight_cols[f'meta_insights_engagement_{_lvl}_{_dim}'] = _eng_bd_cols
                _conflict_cols[f'meta_insights_performance_{_lvl}_{_dim}'] = _key
                _conflict_cols[f'meta_insights_engagement_{_lvl}_{_dim}'] = _key

        # `collected_at` on EVERY table, derived rather than typed 25 times.
        #
        # Measured 2026-08-22: `pg_stat_user_tables` showed 17 545 UPDATEs and 0
        # INSERTs on `meta_insights` that morning — the rows were refreshed and
        # `collected_at` still said May, because the column was not in the update
        # list. Any surface reading MAX(collected_at) on those tables was three
        # months wrong.
        #
        # Exactly one table already had it: `meta_insights_performance_day`. That is
        # also the only Meta table `freshness_monitor` watches — the monitor was
        # pointed at the one table whose clock moved, which is why the discrepancy
        # never surfaced as an alert. The payloads all carry the key already
        # (`_meta_insight_fetch.py:157`, `_meta_config_fetch.py:51,113,148`), so this
        # only stops the value being discarded on conflict.
        for _tbl, _cols in _insight_cols.items():
            if 'collected_at' not in _cols:
                _cols.append('collected_at')

        # `ad_account_id` entre dans la CLÉ des 10 tables à la maille campagne
        # (R53 / ADR-013, migration 077). Dérivé du même `frozenset` que la
        # migration et que `_tag_account`, pas retapé : trois listes de dix tables
        # écrites à la main, ce sont trois listes qui divergent — et la divergence
        # se lit ici comme « ON CONFLICT ne correspond à aucun index unique »,
        # c'est-à-dire un crash, ou pire, comme un écrasement silencieux si c'est
        # l'index qui est en retard.
        for _tbl in _CAMPAIGN_GRAIN_TABLES:
            if 'ad_account_id' not in _conflict_cols[_tbl]:
                _conflict_cols[_tbl] = [*_conflict_cols[_tbl], 'ad_account_id']

        return _insight_cols, _conflict_cols

    def _persist_insights(self, insights: dict):
        """Upsert a subset of insight tables (per-chunk durability).

        Called after each fetched chunk/breakdown so a later throttle never discards
        already-fetched insights — replaces the old all-or-nothing end-of-run upsert.
        """
        from src.models.meta_ads_validators import MetaInsight
        try:
            insight_cols, conflict_cols = self._insight_upsert_maps()
            for tbl, rows in insights.items():
                if not rows:
                    continue
                allowed = set(conflict_cols[tbl]) | set(insight_cols[tbl])
                stamped = self._tag_account(tbl, rows)
                # `meta_insights` est la seule table qu'un modèle décrit. Les 25
                # autres n'en ont pas : leur inventer un ici serait une couche de
                # plus à garder d'accord avec `_insight_upsert_maps`, et c'est
                # cette carte qui fait déjà foi sur les colonnes.
                if tbl == 'meta_insights':
                    self._validate(MetaInsight, stamped, tbl)
                trimmed = [{k: v for k, v in r.items() if k in allowed} for r in stamped]
                self.db.upsert_many(
                    tbl, trimmed,
                    conflict_columns=conflict_cols[tbl],
                    update_columns=insight_cols[tbl],
                )
        except Exception:
            logger.exception("_persist_insights failed")
            raise
