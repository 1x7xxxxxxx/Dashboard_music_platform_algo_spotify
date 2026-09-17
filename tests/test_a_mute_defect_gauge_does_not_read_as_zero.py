"""Une jauge qui ne sait pas ne rend pas zero.

Type: Sub
Uses: prometheus_client, src.utils.defect_gauge
Triggers: pytest
Depends on: src/utils/defect_gauge.py
Persists in: —

Error class `a-gauge-that-reports-zero-when-it-cannot-read`.

Le defaut que ce garde empeche
------------------------------
`streamlytics_open_defects` est lue depuis `app_error_log` pour survivre aux
redeploiements, la ou le compteur d'exceptions repart vide. Mais une jauge lue depuis une
base a un mode d'echec propre, et il est pire que celui qu'elle corrige :

    base injoignable -> la jauge tombe a 0 -> le tableau affiche « aucun defaut ouvert »

C'est l'implementation naive, et c'est un mensonge dans le sens dangereux : il rassure.
Garder la derniere valeur connue ment autrement (elle se lit comme fraiche). Le depot a
deja paye cette forme — un tableau affichait un OK vert pour un signal qui n'etait pas
cable du tout, parce que le type BOOLEAN du stockage ne pouvait pas exprimer l'absence.

La propriete tenue ici : **quand la lecture echoue, AUCUN echantillon
`streamlytics_open_defects{...}` n'est produit, et `..._read_ok` vaut 0.** Le savoir et
l'ignorance vivent dans deux series distinctes, parce qu'une seule ne peut pas porter
les deux.

Mutation record — 2026-09-17, quatre mutations EXECUTEES et vues rouges :
  1. emettre les derniers labels connus a 0 dans la branche `except` (l'implementation
     naive, et le defaut nomme) -> rouge ;
  2. laisser `read_ok` a 1 dans la branche `except` -> rouge ;
  3. servir le snapshot perime au lieu de le jeter -> rouge ;
  4. retirer `WHERE resolved_at IS NULL` de la requete -> rouge.
0 apres remise en etat dans les quatre cas.

Deux mutations supplementaires sur les jauges de SESSION, le 2026-09-17 :
  5. le filtre canari/bac a sable retire de la requete -> rouge ;
  6. le bloc des sessions deplace AVANT le `return` anticipe -> rouge.

⚠️ Une septieme mutation est passee VERTE, et c'etait juste : remplacer
`if _SNAP.sessions is not None:` par `if True:` ne change rien, parce que le `return`
anticipe protege deja ce bloc. Ce `if` est redondant. Ce qui garde reellement est le
`return` — la note est dans le module, pour qu'on ne prenne pas cette ligne pour une
protection.
"""
from __future__ import annotations

import importlib

import pytest

prometheus_client = pytest.importorskip("prometheus_client")


@pytest.fixture()
def gauge_module():
    """Un module NEUF par test : il porte un snapshot d'etat de processus."""
    import src.utils.defect_gauge as mod
    return importlib.reload(mod)


class _FakeDb:
    """Une base qui rend ce qu'on lui dit, ou qui tombe.

    Elle distingue les requetes : le collecteur en pose trois sur la meme connexion
    (artistes vivants, sessions de la minute, defauts ouverts). Rendre les memes lignes
    aux trois ferait passer un test pour une mauvaise raison.
    """

    def __init__(self, rows=None, raises: bool = False,
                 artists: int = 0, sessions: int = 0):
        self._rows = rows or []
        self._raises = raises
        self._artists = artists
        self._sessions = sessions
        self.queries: list[str] = []
        self.closed = False

    def execute_query(self, sql, params=None):
        self.queries.append(sql)

    def fetch_query(self, sql, params=None):
        self.queries.append(sql)
        if self._raises:
            raise RuntimeError("connection refused")
        if "active_sessions" in sql:
            return [[self._artists]]
        if "usage_events" in sql:
            return [[self._sessions]]
        return self._rows

    def close(self):
        self.closed = True


def _samples(mod, db, name_suffix: str):
    """Collecte une fois et rend les echantillons du nom demande."""
    collector = mod.OpenDefectsCollector(lambda: db)
    out = []
    for family in collector.collect():
        for sample in family.samples:
            if sample.name.endswith(name_suffix):
                out.append(sample)
    return out


def test_a_failed_read_emits_no_defect_sample_at_all(gauge_module):
    """Le coeur du garde : pas de zero invente quand la base ne repond pas."""
    db = _FakeDb(raises=True)
    defects = _samples(gauge_module, db, "_open_defects")
    assert defects == [], (
        "Une lecture en echec a produit des echantillons `streamlytics_open_defects`. "
        "Quelle que soit leur valeur, ils se liront comme une mesure — et a 0 ils se "
        "liront comme « aucun defaut ouvert » pendant une panne de base. L'ignorance "
        "doit sortir par `_read_ok`, pas par une valeur inventee."
    )


def test_a_failed_read_says_so_in_read_ok(gauge_module):
    """`read_ok` est toujours emise, et elle vaut 0 quand on ne sait pas."""
    db = _FakeDb(raises=True)
    ok = _samples(gauge_module, db, "_open_defects_read_ok")
    assert len(ok) == 1, "`_read_ok` doit etre emise MEME en echec — c'est son role."
    assert ok[0].value == 0.0, (
        "`_read_ok` vaut 1 apres une lecture en echec : la seule serie qui porte "
        "l'ignorance affirme la connaissance. Plus rien ne distingue alors une base "
        "morte d'un depot sans defaut."
    )


def test_a_successful_empty_read_is_not_the_same_as_a_failure(gauge_module):
    """Zero defaut est un FAIT : read_ok vaut 1, et aucune serie de defaut n'existe."""
    db = _FakeDb(rows=[])
    ok = _samples(gauge_module, db, "_open_defects_read_ok")
    defects = _samples(gauge_module, db, "_open_defects")
    assert ok[0].value == 1.0, "une lecture reussie a 0 ligne reste une lecture reussie"
    assert defects == [], "aucune ligne ouverte : il n'y a rien a emettre"


def test_a_successful_read_exposes_one_series_per_page_and_exception(gauge_module):
    db = _FakeDb(rows=[("home", "KeyError", 3), ("kpis", "TimeoutError", 1)])
    defects = _samples(gauge_module, db, "_open_defects")
    got = {(s.labels["page"], s.labels["error_class"]): s.value for s in defects}
    assert got == {("home", "KeyError"): 3.0, ("kpis", "TimeoutError"): 1.0}


def test_a_failure_after_a_success_discards_the_stale_snapshot(gauge_module):
    """Un snapshot perime ne se sert pas : il se lirait comme une mesure fraiche."""
    mod = gauge_module
    good = _FakeDb(rows=[("home", "KeyError", 3)])
    assert _samples(mod, good, "_open_defects"), "la premiere lecture doit reussir"

    mod._SNAP.taken_at = 0.0          # force l'expiration du TTL
    bad = _FakeDb(raises=True)
    assert _samples(mod, bad, "_open_defects") == [], (
        "Apres un echec, les valeurs de la lecture PRECEDENTE sont encore servies. "
        "Elles portent l'horodatage de la scrutation courante, donc elles se lisent "
        "comme fraiches — c'est un mensonge plus difficile a voir qu'un zero."
    )
    assert _samples(mod, bad, "_open_defects_read_ok")[0].value == 0.0


def test_the_query_only_counts_unresolved_defects(gauge_module):
    """Un defaut ferme ne compte plus — sinon la jauge ne redescend jamais."""
    db = _FakeDb(rows=[])
    _samples(gauge_module, db, "_open_defects")
    sql = " ".join(db.queries)
    assert "resolved_at IS NULL" in sql, (
        "La requete ne filtre plus sur `resolved_at IS NULL` : la jauge compterait les "
        "defauts DEJA FERMES, ne redescendrait jamais, et `make error-resolve` "
        "n'aurait plus aucun effet visible."
    )


def test_the_statement_timeout_stays_under_the_scrape_timeout(gauge_module):
    """2 s < 10 s — sinon une requete pendue emporte TOUTES les autres metriques.

    `collect()` tourne dans le thread de l'exportateur : si elle depasse le
    `scrape_timeout` de Prometheus (10 s, `deploy/prometheus/prometheus.yml`), la
    scrutation entiere expire et le dashboard cesse d'etre mesure — pour un panneau
    d'erreurs. Le `statement_timeout` du pool vaut 15 s et ne protege donc pas ici.
    """
    assert gauge_module._STATEMENT_TIMEOUT_MS <= 5000, (
        f"statement_timeout={gauge_module._STATEMENT_TIMEOUT_MS} ms laisse trop peu de "
        f"marge sous le scrape_timeout de 10 s. Une requete lente ferait disparaitre "
        f"toutes les metriques du dashboard, pas seulement cette jauge."
    )


def test_the_tail_is_folded_not_truncated(gauge_module):
    """Au-dela du plafond, la somme reste EXACTE — tronquer perdrait des defauts."""
    mod = gauge_module
    rows = [(f"page{i}", "KeyError", 1) for i in range(mod._MAX_SERIES + 25)]
    folded = mod._fold(rows)
    assert len(folded) == mod._MAX_SERIES + 1
    assert sum(n for _p, _e, n in folded) == sum(n for _p, _e, n in rows), (
        "Le repliement a perdu des defauts. Une troncature silencieuse ferait mentir "
        "`sum(streamlytics_open_defects)` sans que rien ne le signale."
    )
    assert folded[-1][0] == mod._OTHER


def test_the_session_gauges_are_emitted_only_after_a_successful_read(gauge_module):
    """Les deux comptes de gens suivent la meme regle que les defauts.

    Un « 0 utilisateur connecte » invente pendant une panne de base se lirait comme un
    creux de trafic — et c'est precisement le genre de chiffre sur lequel on decide de
    ne PAS mettre de replique.
    """
    db = _FakeDb(rows=[], artists=3, sessions=7)
    artists = _samples(gauge_module, db, "_active_artists")
    sessions = _samples(gauge_module, db, "_sessions_1m")
    assert artists and artists[0].value == 3.0
    assert sessions and sessions[0].value == 7.0

    gauge_module._SNAP.taken_at = 0.0
    bad = _FakeDb(raises=True)
    assert _samples(gauge_module, bad, "_active_artists") == [], (
        "Une lecture en echec a quand meme produit un compte d'utilisateurs. A 0, il se "
        "lit comme « personne n'est connecte » — l'inverse d'une alerte."
    )
    assert _samples(gauge_module, bad, "_sessions_1m") == []


def test_the_session_query_excludes_canary_and_sandbox(gauge_module):
    """La meme exclusion que `tools/scale_check.sh`, pour la meme raison mesuree.

    Le 2026-09-16, l'ancienne requete du script comptait tout : 320 des 1 043 evenements
    d'une journee — 31 % — venaient du bac a sable. Une jauge qui les compterait
    surestimerait la charge reelle du meme facteur.
    """
    db = _FakeDb(rows=[])
    _samples(gauge_module, db, "_sessions_1m")
    sql = " ".join(db.queries)
    assert "is_canary" in sql and "is_sandbox" in sql, (
        "La requete des sessions ne filtre plus canari/bac a sable. Elle surestimerait "
        "la charge, et c'est elle qui informe la decision de repliquer."
    )
