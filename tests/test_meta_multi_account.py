"""R53 / ADR-013 — un artiste, N comptes publicitaires Meta, séparés.

Ce que ces tests gardent, dans l'ordre où ça casse si on se trompe :

1. **Le miroir ne se désynchronise pas.** `account_ids` est canonique, `account_id`
   est son premier élément. Les six lecteurs existants lisent le scalaire ; un miroir
   faux, c'est un collecteur qui part sur le mauvais compte sans rien dire.
2. **La forme du 2ᵉ compte est vérifiée comme celle du 1ᵉʳ.** Ces valeurs entrent
   dans un chemin REST, et `requests` n'encode pas `/` dans un chemin qu'on
   construit soi-même.
3. **Un compte en panne n'emporte pas les autres**, et la tâche reste rouge.
4. **Chaque ligne écrite porte le compte dont elle vient**, et la clé d'unicité le
   contient — sans quoi deux campagnes « Release FR » s'écrasent.
5. **Aucun marqueur `{acct}` ne survit dans une chaîne qui n'est pas une f-string.**
   Défaut réellement commis pendant l'écriture de cette brique : le marqueur partait
   tel quel dans le SQL. `ruff` ne le voit pas, un test de rendu non plus.
"""
import ast
import pathlib

import pytest

from src.collectors._meta_constants import _ACCOUNT_STAMPED_TABLES, _CAMPAIGN_GRAIN_TABLES
from src.collectors._meta_upsert import _MetaUpsertMixin
from src.collectors.meta_ads_api_collector import MetaAdsApiCollector
from src.utils.tenant_identity import (
    malformed_meta_accounts,
    meta_ad_account_ids,
    normalise_meta_account,
    with_meta_accounts,
)


# ── 1. Stockage : la liste canonique et son miroir ───────────────────────────

class TestAccountStorage:

    def test_legacy_scalar_row_still_reads_as_one_account(self):
        """Une ligne écrite avant le multi-comptes ne perd pas son compte."""
        assert meta_ad_account_ids({'account_id': '567214713853881'}) == \
            ['act_567214713853881']

    def test_prefix_is_added_once_and_only_once(self):
        assert normalise_meta_account('act_123') == 'act_123'
        assert normalise_meta_account('123') == 'act_123'
        assert normalise_meta_account('  ') == ''

    def test_duplicates_collapse_and_order_is_kept(self):
        extra = with_meta_accounts({}, ['123', 'act_123', '456'])
        assert extra['account_ids'] == ['act_123', 'act_456']

    def test_mirror_is_always_the_first_element(self):
        extra = with_meta_accounts({}, ['act_9', 'act_8'])
        assert extra['account_id'] == extra['account_ids'][0] == 'act_9'

    def test_clearing_every_account_clears_the_mirror_too(self):
        """Sinon l'artiste reste « connecté » pour tout ce qui lit le scalaire."""
        extra = with_meta_accounts({'account_id': 'act_1', 'account_ids': ['act_1']}, [])
        assert 'account_id' not in extra and 'account_ids' not in extra

    def test_a_hand_written_string_list_is_accepted(self):
        """Une ligne éditée à la main ou importée porte du texte, pas une liste."""
        assert meta_ad_account_ids({'account_ids': '111, 222\n333'}) == \
            ['act_111', 'act_222', 'act_333']

    def test_other_keys_survive(self):
        extra = with_meta_accounts({'ig_user_id': '17841400000000000'}, ['1'])
        assert extra['ig_user_id'] == '17841400000000000'


# ── 2. Forme : le 2ᵉ compte est contrôlé comme le 1ᵉʳ ────────────────────────

class TestAccountShape:

    @pytest.mark.parametrize("payload", [
        'me/accounts', '123/me', '../../me', '123 456', 'act_12a',
    ])
    def test_a_malformed_second_account_is_reported(self, payload):
        extra = {'account_ids': ['act_123', payload]}
        assert malformed_meta_accounts(extra), (
            f"{payload!r} entre dans un chemin REST sans contrôle de forme"
        )

    def test_well_formed_accounts_report_nothing(self):
        assert malformed_meta_accounts({'account_ids': ['act_1', '567214713853881']}) == []


# ── 3. Le collecteur parcourt tous les comptes ───────────────────────────────

class _FakeDB:
    def __init__(self):
        self.upserts = []
        self.deletes = []

    def upsert_many(self, table, data, conflict_columns=None, update_columns=None):
        self.upserts.append((table, [dict(r) for r in data]))
        return len(data)

    def execute_query(self, query, params=None):
        self.deletes.append((query, params))

    def fetch_query(self, query, params=None):
        return []


def _collector(accounts, db=None):
    return MetaAdsApiCollector(
        1, db=db or _FakeDB(), ad_account=object(),
        creds={'ad_account_ids': accounts, 'ad_account_id': accounts[0]},
    )


class TestCollectorLoop:

    def test_every_declared_account_is_collected(self, monkeypatch):
        c = _collector(['act_1', 'act_2', 'act_3'])
        seen = []
        monkeypatch.setattr(
            type(c), '_run_one_account',
            lambda self, **kw: (seen.append(self._current_ad_account_id), 5)[1])
        assert c.run() == 15
        assert seen == ['act_1', 'act_2', 'act_3']

    def test_a_failing_account_does_not_cancel_the_others(self, monkeypatch):
        """Le partage d'asset manquant est la panne Meta la plus fréquente."""
        c = _collector(['act_ok', 'act_broken', 'act_ok2'])
        done = []

        def _run(self, **kw):
            if self._current_ad_account_id == 'act_broken':
                raise RuntimeError("asset not shared")
            done.append(self._current_ad_account_id)
            return 7

        monkeypatch.setattr(type(c), '_run_one_account', _run)
        with pytest.raises(RuntimeError) as exc:
            c.run()
        assert done == ['act_ok', 'act_ok2'], "les comptes sains doivent avoir collecté"
        assert 'act_broken' in str(exc.value)
        assert '1/3' in str(exc.value)

    def test_the_run_still_fails_so_the_dag_goes_red(self, monkeypatch):
        """Règle transverse #6 : un collecteur lève. Un succès partiel muet est pire."""
        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account',
                            lambda self, **kw: (_ for _ in ()).throw(ValueError("boom")))
        with pytest.raises(RuntimeError):
            c.run()

    def test_the_failure_message_never_carries_the_exception_text(self, monkeypatch):
        """La SDK Meta met l'URL préparée — donc le token — dans ses messages."""
        c = _collector(['act_1'])
        # Faux token, écrit exprès sous la forme que la SDK produit — c'est ce
        # que le test doit voir disparaître du message d'erreur.
        secret = "https://graph.facebook.com/x?access_token=SECRET"  # pragma: allowlist secret
        monkeypatch.setattr(
            type(c), '_run_one_account',
            lambda self, **kw: (_ for _ in ()).throw(ValueError(secret)))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        assert 'SECRET' not in str(exc.value)
        assert 'ValueError' in str(exc.value)


# ── 4. Chaque ligne porte son compte, et la clé le contient ──────────────────

class TestAccountStamp:

    def test_campaign_grain_rows_are_stamped(self):
        c = _collector(['act_42'])
        c._current_ad_account_id = 'act_42'
        rows = c._tag_account('meta_insights_performance', [{'campaign_name': 'X'}])
        assert rows[0]['ad_account_id'] == 'act_42'

    def test_ad_grain_tables_are_left_alone(self):
        """Elles n'ont PAS la colonne : la stamper ferait échouer l'upsert."""
        c = _collector(['act_42'])
        rows = c._tag_account('meta_insights_performance_ad_country', [{'ad_id': 'A'}])
        assert 'ad_account_id' not in rows[0]

    def test_stamped_table_set_matches_the_migration(self):
        assert _CAMPAIGN_GRAIN_TABLES <= _ACCOUNT_STAMPED_TABLES
        assert _ACCOUNT_STAMPED_TABLES - _CAMPAIGN_GRAIN_TABLES == {
            'meta_campaigns', 'meta_adsets', 'meta_ads'}

    def test_every_campaign_grain_key_carries_the_account(self):
        """Sans ça, « Release FR » de deux comptes écrit LA MÊME ligne."""
        _cols, conflict = _MetaUpsertMixin._insight_upsert_maps()
        for tbl in _CAMPAIGN_GRAIN_TABLES:
            assert 'ad_account_id' in conflict[tbl], tbl

    def test_ad_grain_keys_do_not_carry_it(self):
        _cols, conflict = _MetaUpsertMixin._insight_upsert_maps()
        assert 'ad_account_id' not in conflict['meta_insights_performance_ad_country']

    def test_prune_is_scoped_to_the_account_being_collected(self):
        """Le DELETE du 2ᵉ compte effacerait sinon ce que le 1ᵉʳ vient d'écrire."""
        db = _FakeDB()
        c = _collector(['act_1', 'act_2'], db=db)
        c._current_ad_account_id = 'act_2'
        c._prune_renamed_campaigns([{'campaign_name': 'Release FR'}])
        assert db.deletes, "le prune doit s'exécuter"
        for query, params in db.deletes:
            assert 'ad_account_id IS NOT DISTINCT FROM' in query
            assert 'act_2' in params


# ── 5. Aucun marqueur de format ne part tel quel dans le SQL ─────────────────

_QUERY_CALLS = {'fetch_df', 'fetch_query', 'execute_query'}


def _plain_string_markers(path: pathlib.Path) -> list:
    """Marqueurs `{acct…}` dans une chaîne NON-f passée à une requête.

    AST, jamais une recherche de texte : une f-string et une chaîne ordinaire se
    ressemblent au caractère près, et c'est justement la différence qui décide si
    `{acct}` devient un prédicat SQL ou huit caractères littéraux envoyés à
    Postgres. Une constante de module marquée puis `.format()`-ée plus loin est
    légitime — d'où la restriction aux arguments passés DIRECTEMENT à une requête.
    """
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _QUERY_CALLS):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if '{acct' in arg.value or '{_acct' in arg.value:
                    found.append((path.name, arg.lineno))
    return found


def test_no_account_marker_survives_in_a_plain_string():
    hits = []
    for path in pathlib.Path("src").rglob("*.py"):
        hits.extend(_plain_string_markers(path))
    assert hits == [], (
        "marqueur de compte dans une chaîne non-f : il partira tel quel dans le SQL "
        f"→ {hits}"
    )
