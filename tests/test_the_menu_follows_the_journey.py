"""Le menu suit le PARCOURS de l'artiste, pas l'organisation du code.

Type: Guard
Uses: ast, src.dashboard.utils.nav_sections
Depends on: src/dashboard/utils/nav_sections.py, src/dashboard/app.py
Persists in: nothing

NEUF DEMANDES, UNE SEULE RÈGLE — 2026-09-22
--------------------------------------------
Neuf corrections d'ordre formulées en regardant la barre latérale. Elles se ramènent
toutes à la même chose : le menu doit raconter ce qu'on FAIT, dans l'ordre où on le
fait.

    1. l'accueil, seul en tête        — trois gestes y étaient empilés
    2. je configure                   — et je vois COMBIEN il m'en reste
    3. je regarde mes chiffres        — AVANT la liste de ce qui se vend
    4. je vois ce que j'achète        — avec un cadenas par vue et sur la section

⚠️ POURQUOI UN GARDE ET PAS UNE NOTE. Un ordre de menu est la première chose qu'une
refonte casse, et la dernière qu'une relecture remarque : les entrées sont toutes
présentes, aucun test ne rougit, et l'écran ne raconte plus rien. Ce dépôt a déjà
déplacé « 📝 Saisie S4A » (2026-09-12), « 📱 Hypeddit » (2026-09-21) et les six pages
Premium (2026-09-21) pour cette raison — chaque fois en le voyant à l'œil, jamais par
un test.

CE QU'IL NE TIENT PAS
---------------------
* **Le rendu.** Il vérifie la STRUCTURE ; que le menu soit lisible se voit à l'œil, et
  `tests/test_the_menu_says_what_each_page_is.py` couvre les libellés.
* **Le geste voisin le plus proche : l'ordre DANS une section non nommée ici.** Les
  sections `revenue` et `admin` ne sont pas contraintes ; rien n'empêche d'y remonter
  une entrée sans que ce fichier le dise.
* **La JUSTESSE du pourcentage.** Il vérifie qu'il est CÂBLÉ, pas qu'il compte bien —
  `setup_completion` a ses propres tests.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"


def _sections() -> list[tuple[str, str, list[str]]]:
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    return [(sec, header, [k for _, k in items]) for sec, header, items in NAV_SECTIONS]


def _ordre() -> list[str]:
    return [sec for sec, _, _ in _sections()]


def _items(sec_id: str) -> list[str]:
    for sec, _, keys in _sections():
        if sec == sec_id:
            return keys
    raise AssertionError(f"section « {sec_id} » absente : {_ordre()}")


def _labels() -> dict[str, str]:
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    return {k: lbl for _, _, items in NAV_SECTIONS for lbl, k in items}


# ══════════════════════════════════════════════════════════════════════════
# NON-VACUITÉ
# ══════════════════════════════════════════════════════════════════════════

def test_the_menu_has_enough_sections_to_constrain() -> None:
    """Un menu réduit rendrait tout ce qui suit vrai pour rien."""
    o = _ordre()
    assert len(o) >= 6, f"seulement {o} — les contraintes ci-dessous ne disent plus rien"
    assert len({*o}) == len(o), f"une section apparaît deux fois : {o}"


# ══════════════════════════════════════════════════════════════════════════
# 1. L'ORDRE DES SECTIONS
# ══════════════════════════════════════════════════════════════════════════

def test_what_you_look_at_comes_before_what_you_buy() -> None:
    """« Analytics » AU-DESSUS de « Premium », et SOUS la configuration.

    Un artiste gratuit voyait six cadenas avant d'atteindre ses propres chiffres, ce
    qui inverse l'ordre des choses : on regarde d'abord ce qu'on a, on décide ensuite
    si on paie pour plus.
    """
    o = _ordre()
    for sec in ("data", "analytics", "premium"):
        assert sec in o, f"section « {sec} » absente : {o}"
    assert o.index("data") < o.index("analytics") < o.index("premium"), (
        f"l'ordre configuration → analytics → premium est rompu : {o}")


def test_no_section_holds_a_single_page_that_belongs_elsewhere() -> None:
    """Les deux sections d'un seul élément ont été dissoutes, et pas par hasard.

    « 🔮 Prédiction algos Spotify » (payante) a rejoint « 💎 Premium » ; « 📣 Publicité
    Meta Ads » (gratuite) a rejoint « 📊 Analytics plateformes ». Le critère est le
    même dans les deux cas : une section est un GROUPE, et un groupe d'un seul élément
    dit seulement qu'on n'a pas su où le mettre.
    """
    o = _ordre()
    for mort in ("advanced", "ads"):
        assert mort not in o, (
            f"la section « {mort} » est revenue. Elle ne portait qu'une page, et cette "
            "page a une maison : la prédiction est payante donc elle ouvre Premium, la "
            f"vue Meta Ads est gratuite donc c'est une plateforme. Ordre actuel : {o}")


# ══════════════════════════════════════════════════════════════════════════
# 2. L'ORDRE DANS LES SECTIONS
# ══════════════════════════════════════════════════════════════════════════

def test_the_assistant_comes_before_the_check_of_what_it_produced() -> None:
    """L'assistant, puis le contrôle de ce qu'il a installé. Dans cet ordre.

    En tête de menu, l'assistant proposait d'installer sans dire ce qui l'était déjà.
    """
    d = _items("data")
    for k in ("onboarding", "onboarding_health"):
        assert k in d, f"« {k} » a quitté la configuration : {d}"
    assert d.index("onboarding") + 1 == d.index("onboarding_health"), (
        f"l'assistant n'est plus juste avant la santé onboarding : {d}")


def test_the_ads_view_sits_right_under_spotify() -> None:
    """La source qu'on croise le plus souvent avec les écoutes vient juste après."""
    a = _items("analytics")
    for k in ("spotify_s4a_combined", "meta_ads_overview"):
        assert k in a, f"« {k} » n'est pas dans Analytics : {a}"
    assert a.index("spotify_s4a_combined") + 1 == a.index("meta_ads_overview"), (
        f"la vue Meta Ads n'est plus juste sous Spotify + S4A : {a}")


def test_the_report_opens_what_the_subscription_sells() -> None:
    """Le rapport est ce que l'abonnement donne de plus TANGIBLE : il ouvre Premium.

    ⚠️ CE TEST EXIGEAIT L'INVERSE pendant quelques heures, et la différence entre les
    deux n'est pas une correction — c'est un arbitrage entre deux récits, tranché par le
    propriétaire le 2026-09-22 au soir.

      * en DERNIER d'« Analytics », l'ordre disait « voilà tes plateformes, voilà leur
        résumé ». Le rapport était près de ce qu'il résume ;
      * en TÊTE de « Premium », il répond à « qu'est-ce que j'achète » avant les cinq
        pages d'analyse, qu'il faut ouvrir pour comprendre. Un document qu'on emporte
        est plus tangible qu'une page qu'on visite.

    Ce qu'on perd est écrit dans `nav_sections.py` : le résumé est désormais loin de ce
    qu'il résume. Les deux placements se défendaient ; celui-ci est le choix fait.
    """
    # ⚠️ RENVERSÉ LE 2026-09-26 (ADR-029, décision du propriétaire) : le rapport à la
    # demande est redevenu GRATUIT — c'est une lecture de ses données. Il retourne donc
    # près de ce qu'il résume, en fin d'« Analytics », et la section Premium s'ouvre sur
    # l'APERÇU gratuit de ce qu'elle vend, juste au-dessus de Road to Algo.
    from src.dashboard.utils.nav_badges import FREE_PREVIEW_PAGES
    p = _items("premium")
    assert p[0] in FREE_PREVIEW_PAGES and p[1] == "trigger_algo", (
        f"la section Premium ne s'ouvre plus sur l'aperçu puis Road to Algo : {p}")
    assert "export_pdf" not in p, (
        f"le rapport PDF est revenu dans Premium : {p} — ADR-029 l'a rendu gratuit")
    a = _items("analytics")
    assert a[-2:] == ["export_pdf", "service"], (
        f"le rapport ne clôt plus les analyses, juste avant « Faire piloter mes "
        f"campagnes » : {a[-2:]}")


def test_the_raw_export_is_an_account_gesture() -> None:
    """Sortir ses propres données brutes se cherche sous « Compte », pas en analyse."""
    c = _items("account")
    assert "export_csv" in c, f"« Export CSV » a quitté la section Compte : {c}"
    assert "service" not in c, (
        "« Faire piloter mes campagnes » est revenue sous Compte : elle y était rangée "
        "par facturation plutôt que par usage.")


def test_the_home_stands_alone_at_the_top() -> None:
    """Trois gestes y étaient empilés — l'accueil, l'assistant et les deux exports."""
    assert _items("start") == ["home"], (
        f"la tête du menu porte autre chose que l'accueil : {_items('start')}")


# ══════════════════════════════════════════════════════════════════════════
# 3. CE QUE LES LIBELLÉS DISENT
# ══════════════════════════════════════════════════════════════════════════

def test_the_report_is_named_by_what_it_gives_not_by_its_format() -> None:
    """« Export PDF » décrit un format ; « Rapport de carrière » décrit ce qu'on obtient.

    C'est le second qu'on cherche dans un menu.
    """
    lbl = _labels().get("export_pdf", "")
    assert "Rapport" in lbl and "carri" in lbl, (
        f"le rapport s'appelle encore « {lbl} » : un format n'est pas un résultat.")


# ══════════════════════════════════════════════════════════════════════════
# 4. LE POURCENTAGE, ET LE CADENAS
# ══════════════════════════════════════════════════════════════════════════

def test_the_setup_section_shows_how_far_it_is() -> None:
    """Le % répond à une question que les sept entrées ne posent pas : *combien reste-t-il*.

    Par l'AST : `render_navigation` appelle le lecteur en cache, et il le fait pour la
    section `data`. Un prédicat textuel serait satisfait par le commentaire qui
    explique le calcul.
    """
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "render_navigation"), None)
    assert fn is not None, "`render_navigation` a disparu d'`app.py`"
    appelle = any(isinstance(n, ast.Call)
                  and getattr(n.func, "id", None) == "setup_pct"
                  for n in ast.walk(fn))
    assert appelle, (
        "la barre latérale ne lit plus l'avancement de la configuration : le % a "
        "disparu de l'en-tête de section.")
    vise_data = any(isinstance(n, ast.Constant) and n.value == "data"
                    for n in ast.walk(fn))
    assert vise_data, (
        "le % n'est plus attaché à la section `data` : il s'afficherait ailleurs ou "
        "nulle part.")


def test_the_percentage_is_cached_and_closes_its_connection() -> None:
    """Sans cache, une connexion par rerun — et les vues sont plafonnées à UNE.

    Même raison, même horizon que `auth._cached_plan_row` : soixante secondes, pour que
    les deux chiffres de la barre latérale ne décrivent pas deux instants différents.

    ⚠️ ELLE N'EST PLUS DANS `app.py`, et ce sont DEUX cliquets qui l'ont fait sortir —
    écrite là d'abord, le 2026-09-22. `test_a_file_only_gets_shorter` gèle `app.py` à
    997 lignes et le pourcentage l'a porté à 1 015 ;
    `test_a_connection_is_closed_on_every_path` a nommé le défaut à la ligne près :
    « `db` is opened and no try/finally closes it. Use `with project_db() as db:` ».
    Les deux avaient raison, et le remède était le même — un module à elle.
    """
    mod = _ROOT / "src" / "dashboard" / "utils" / "setup_progress.py"
    assert mod.is_file(), f"{mod.name} a disparu : le % n'a plus de calcul"
    tree = ast.parse(mod.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "setup_pct"), None)
    assert fn is not None, "`setup_pct` a disparu de `setup_progress.py`"
    assert any("cache_data" in ast.unparse(d) for d in fn.decorator_list), (
        "`setup_pct` n'est plus en cache : elle ouvrirait une connexion à chaque "
        "rerun, et un rendu est plafonné à une seule sans aucune exemption.")
    assert any(isinstance(n, ast.With) and "project_db" in ast.unparse(n.items[0])
               for n in ast.walk(fn)), (
        "`setup_pct` n'ouvre plus sa connexion par `with project_db()` : elle peut "
        "la laisser ouverte, et `max_connections=100` est partagé avec Airflow et "
        "l'API.")


def test_an_unreadable_setup_shows_no_percentage_rather_than_zero() -> None:
    """« On ne sait pas » n'est pas « rien n'est fait ».

    Un zéro affiché sur une base injoignable annoncerait à un artiste qui a tout
    branché qu'il n'a rien fait.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.setup_progress import setup_pct

    assert setup_pct(None, None, "free") is None


@pytest.mark.parametrize("plan,attendu", [("free", "🔒"), ("premium", "🔓")])
def test_the_premium_section_carries_the_padlock_of_the_plan(plan, attendu) -> None:
    """Un cadenas sur l'EN-TÊTE, et un sur chaque vue. Fermé ou ouvert selon le plan.

    C'est la seule façon pour un abonné de voir ce qu'il paie, et pour un compte
    gratuit de voir ce que l'abonnement contient. Vérifié au rendu réel les 2026-09-21
    et 2026-09-22 (AppTest + `_view_as`) ; figé ici pour que ça le reste.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.database.stripe_schema import page_is_locked
    from src.dashboard.utils.nav_badges import badge, section_badge

    from src.dashboard.utils.nav_badges import FREE_PREVIEW, FREE_PREVIEW_PAGES

    all_keys = _items("premium")
    # L'APERÇU gratuit (R193) est la seule page gratuite admise ici : il porte son propre
    # cadenas OUVERT vert, pour tous les plans — vérifié à part ci-dessous.
    keys = [k for k in all_keys if k not in FREE_PREVIEW_PAGES]
    payantes = {k for k in keys if page_is_locked("free", k)}
    assert payantes == set(keys), (
        f"des pages GRATUITES vivent dans la section Premium : {set(keys) - payantes}. "
        "Le critère est le PLAN, pas le thème.")
    for k in set(all_keys) & FREE_PREVIEW_PAGES:
        assert badge(k, is_locked=lambda x: page_is_locked(plan, x),
                     paid_pages=payantes) == FREE_PREVIEW, (
            f"l'aperçu « {k} » ne porte pas le cadenas ouvert vert en plan « {plan} »")

    def _locked(k: str) -> bool:
        return page_is_locked(plan, k)

    entete = section_badge(keys, is_locked=_locked, paid_pages=payantes)
    assert attendu in entete, (
        f"l'en-tête Premium ne porte pas {attendu} pour un plan « {plan} » : {entete!r}")
    for k in keys:
        m = badge(k, is_locked=_locked, paid_pages=payantes)
        assert attendu in m, f"« {k} » ne porte pas {attendu} en plan « {plan} » : {m!r}"


# ══════════════════════════════════════════════════════════════════════════
# 5. LES FLÈCHES — on ne laisse personne coincé
# ══════════════════════════════════════════════════════════════════════════

def _rendered(sans_admin: bool = True):
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    return [(f"_nav_{s}", h, items) for s, h, items in NAV_SECTIONS
            if not (sans_admin and s == "admin")]


def _libre(_k: str) -> bool:
    return False


def _gratuit(k: str) -> bool:
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.database.stripe_schema import page_is_locked
    return page_is_locked("free", k)


def test_the_arrows_skip_the_pages_the_plan_blocks() -> None:
    """Le comportement VOULU, et il reste vrai.

    Une flèche est un geste d'exploration : l'envoyer buter sur le paywall une entrée
    sur deux transforme l'exploration en parcours d'obstacles. Les pages verrouillées
    restent atteignables par le menu, avec leur cadenas — là le clic est délibéré.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_badges import _neighbour_pages

    vus = set()
    cur = "home"
    for _ in range(60):
        _prev, nxt = _neighbour_pages(_rendered(), cur, _gratuit)
        if nxt is None:
            break
        vus.add(nxt)
        cur = nxt
    bloquees = {k for k in vus if _gratuit(k)}
    assert not bloquees, (
        f"la flèche ▶ mène sur des pages verrouillées : {sorted(bloquees)}")
    assert len(vus) >= 8, f"la traversée s'arrête trop tôt : {sorted(vus)}"


# `export_pdf` en est sorti le 2026-09-26 : il est gratuit depuis ADR-029.
@pytest.mark.parametrize("page", ["trigger_algo", "meta_cpr_optimizer", "revenue_forecast"])
def test_a_locked_page_is_never_a_dead_end(page: str) -> None:
    """LE DÉFAUT MESURÉ LE 2026-09-22 : les deux flèches mouraient.

    L'ancien code construisait la liste SANS les pages verrouillées, puis
    `if current not in order: return None, None`. Un compte gratuit qui CLIQUE une
    entrée 🔒 — ce que le cadenas l'invite à faire, puisqu'il annonce ce que
    l'abonnement contient — atterrissait sur le mur de montée en gamme avec **les deux
    flèches mortes**, sans autre sortie que le menu.

    « Ne pas y MENER » n'est pas « ne pas en SORTIR », et les deux avaient été
    confondus.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_badges import _neighbour_pages

    assert _gratuit(page), (
        f"« {page} » n'est plus payante : ce test ne vérifie plus le cas verrouillé.")
    prev, nxt = _neighbour_pages(_rendered(), page, _gratuit)
    assert not (prev is None and nxt is None), (
        f"depuis « {page} », verrouillée, les DEUX flèches sont mortes : un compte "
        "gratuit y est coincé sans autre sortie que le menu.")
    for voisin in (prev, nxt):
        if voisin is not None:
            assert not _gratuit(voisin), (
                f"la sortie proposée depuis « {page} » est elle-même verrouillée : "
                f"{voisin}")


def test_an_unknown_page_still_offers_nothing() -> None:
    """NON-VACUITÉ inverse : une clé inconnue ne doit PAS inventer de voisines.

    Sans ce test, « ne jamais rendre (None, None) » se satisferait en proposant
    n'importe quoi depuis une URL périmée.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_badges import _neighbour_pages

    assert _neighbour_pages(_rendered(), "page_qui_nexiste_pas", _libre) == (None, None)


def test_the_first_and_last_page_have_one_arrow_each() -> None:
    """Les bornes : pas de ◀ sur la première, pas de ▶ sur la dernière."""
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_badges import _neighbour_pages

    tout = [k for _, _, items in _rendered() for _, k in items]
    prem, der = tout[0], tout[-1]
    assert _neighbour_pages(_rendered(), prem, _libre)[0] is None, (
        f"« {prem} » a une page précédente alors qu'elle ouvre le menu")
    assert _neighbour_pages(_rendered(), der, _libre)[1] is None, (
        f"« {der} » a une page suivante alors qu'elle ferme le menu")
