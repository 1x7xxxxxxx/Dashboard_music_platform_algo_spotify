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


# ── 6. L'alerte nomme le geste, pas seulement le symptôme ────────────────────

class TestFailureReasonReachesTheOperator:
    """Mesuré le 2026-09-03, sur cinq nuits d'échec réel.

    `etl_run_log` et le mail consolidé disaient `act_65390907
    (FacebookRequestError)`. La phrase qui dit quoi faire — *(#200) Ad account owner
    has NOT grant ads_management or ads_read permission* — ne vivait que dans le log
    Airflow du conteneur. Un nom de classe envoie le lecteur le chercher ; ADR-011
    demande qu'une alerte porte le symptôme **et** l'action.

    La contrainte qui rend ces tests non triviaux : `str(exc)` reste interdit — la
    SDK Meta stringifie la REQUÊTE PRÉPARÉE, token compris. On lit donc les champs
    d'erreur de l'API, où la requête ne figure pas.
    """

    class _FakeMetaError(Exception):
        """La forme que `facebook_business.exceptions.FacebookRequestError` expose.

        Reproduite plutôt qu'importée : le paquet n'est pas installé partout où cette
        suite tourne, et c'est le CONTRAT d'accesseurs qui est gardé ici.
        """

        def __init__(self, code, message, subcode=None, text="<prepared request>"):
            super().__init__(text)
            self._code, self._message, self._subcode = code, message, subcode

        def api_error_code(self):
            return self._code

        def api_error_subcode(self):
            return self._subcode

        def api_error_message(self):
            return self._message

    def _raise(self, exc):
        return lambda self, **kw: (_ for _ in ()).throw(exc)

    def test_the_real_2026_09_03_failure_says_what_to_do(self, monkeypatch):
        c = _collector(['act_65390907'])
        monkeypatch.setattr(type(c), '_run_one_account', self._raise(
            self._FakeMetaError(
                200,
                "(#200) Ad account owner has NOT grant ads_management or ads_read "
                "permission, refer to https://developers.facebook.com/docs/",
            )))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        msg = str(exc.value)
        assert 'act_65390907' in msg
        assert '#200' in msg, "le code de l'API est ce qui se cherche dans la doc Meta"
        assert 'ads_management' in msg, (
            "la permission manquante EST le geste : sans elle le lecteur doit ouvrir "
            "le conteneur pour savoir quoi demander au propriétaire du compte"
        )

    def test_the_subcode_is_kept_when_meta_sends_one(self, monkeypatch):
        """190/460 (mot de passe changé) et 190 nu appellent des gestes différents."""
        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account', self._raise(
            self._FakeMetaError(190, "Error validating access token", subcode=460)))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        assert '#190/460' in str(exc.value)

    def test_a_meta_message_is_still_redacted(self, monkeypatch):
        """Un message qu'on n'écrit pas est un message dont on ne présume rien."""
        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account', self._raise(
            self._FakeMetaError(
                1,
                "failed calling ?access_token=SECRET",  # pragma: allowlist secret
            )))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        msg = str(exc.value)
        assert 'SECRET' not in msg
        # Sans cette seconde moitié le test est vert quoi qu'il arrive : un message
        # vide ne contient pas le secret non plus. Il faut que la prose de Meta soit
        # ARRIVÉE, et qu'elle soit arrivée caviardée.
        assert 'failed calling' in msg and 'access_token=***' in msg

    def test_the_prepared_request_never_reaches_the_message(self, monkeypatch):
        """`str(exc)` reste interdit : c'est lui qui porte le token."""
        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account', self._raise(
            self._FakeMetaError(
                200, "no permission",
                text="GET https://graph.facebook.com/v23.0/act_1?access_token=LEAK",
            )))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        msg = str(exc.value)
        assert 'LEAK' not in msg
        assert 'graph.facebook.com' not in msg
        # Même raison qu'au-dessus : c'est le couple « la raison passe, la requête
        # ne passe pas » qui est gardé. Un nom de classe seul satisferait les deux
        # premières assertions sans rien prouver.
        assert 'no permission' in msg

    def test_a_non_meta_exception_still_degrades_to_its_class_name(self, monkeypatch):
        """Le comportement d'avant, conservé pour tout ce qui n'est pas une erreur API.

        Vert avant comme après le correctif, et c'est voulu : ce test garde une
        NON-régression, pas le correctif. Les deux premiers de cette classe sont
        ceux qui tombent si `_account_failure_reason` disparaît.
        """
        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account',
                            self._raise(ConnectionError("dns")))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        assert 'ConnectionError' in str(exc.value)

    def test_a_malformed_sdk_error_does_not_mask_the_outage(self, monkeypatch):
        """Un accesseur qui lève ne doit pas remplacer une panne par une autre."""
        class _Broken(Exception):
            def api_error_code(self):
                raise KeyError('code')

        c = _collector(['act_1'])
        monkeypatch.setattr(type(c), '_run_one_account', self._raise(_Broken()))
        with pytest.raises(RuntimeError) as exc:
            c.run()
        assert '_Broken' in str(exc.value)
