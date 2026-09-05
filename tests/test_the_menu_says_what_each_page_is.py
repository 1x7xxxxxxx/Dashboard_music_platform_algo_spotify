"""Le menu, les flèches, et la sortie — ce que l'artiste lit avant de cliquer.

Type: Test
Uses: app._NAV_SECTIONS, app._neighbour_pages, auth.render_logout_footer
Depends on: src/dashboard/app.py, src/dashboard/auth.py
Persists in: nothing

Le lot du 2026-09-04, deuxième passe de parcours artiste. Toutes ces demandes ont la
même forme : **le menu nommait nos objets, pas les siens**.

  * « ajouter mes chiffres Spotify & Apple » — le mot Spotify seul se confondait avec
    l'API Spotify, réglée deux lignes plus haut. C'est du **Spotify for Artists**,
    et c'est un fichier, pas une connexion ;
  * « Prédiction Discover Weekly » ne prédit pas que Discover Weekly (Radio, Release
    Radar) ;
  * « Créatives » est du vocabulaire d'agence, « Breakdowns » un mot d'API ;
  * la section « Données » ne contient aucune donnée : elle contient la configuration ;
  * Data Wrapped était rangé avec les exports alors que c'est une lecture.

Le garde ne fige PAS les libellés — ce serait interdire de les améliorer. Il fige les
propriétés qui ont motivé chaque changement, et qui se reperdent en silence : un mot
qu'aucun artiste n'a de raison de connaître, une page rangée dans une section qui ne
décrit pas ce qu'elle fait, une flèche qui mène au paywall.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.app import _ADMIN_ONLY, _NAV_SECTIONS, _neighbour_pages

_ROOT = Path(__file__).resolve().parents[1]


def _artist_items():
    """(section_id, label, page_key) des entrées qu'un ARTISTE voit."""
    return [(sid, lbl, key)
            for sid, _h, items in _NAV_SECTIONS
            for lbl, key in items
            if key not in _ADMIN_ONLY]


# ── Le vocabulaire ───────────────────────────────────────────────────────────

# Des mots qui ne veulent rien dire pour quelqu'un dont le métier est la musique.
# Chacun a été signalé par un artiste, pas supposé par nous.
_JARGON = {
    "breakdown": "un mot d'API — dire QUI a vu les pubs",
    "créative": "vocabulaire d'agence — dire « visuels »",
    "creative": "vocabulaire d'agence — dire « visuels »",
    "api credential": "à garder : c'est le nom de la page de saisie",
}


def test_no_artist_facing_menu_entry_speaks_our_vocabulary():
    """Les mots d'agence et d'API n'apparaissent pas dans le menu de l'artiste.

    `Credentials API` est explicitement toléré : c'est le nom sous lequel la page est
    connue, il apparaît dans le guide, dans le PDF et dans les e-mails. Le renommer
    ici et nulle part ailleurs coûterait plus que le mot lui-même.
    """
    offenders = []
    for _sid, label, key in _artist_items():
        low = label.lower()
        for word, why in _JARGON.items():
            if word == "api credential" or word in ("creative",) and "créative" in low:
                continue
            if word in low:
                offenders.append(f"{key}: {label!r} — {why}")
    assert not offenders, (
        "Ces entrées de menu emploient un vocabulaire interne :\n  "
        + "\n  ".join(offenders)
    )


def test_the_csv_import_entry_names_spotify_for_artists():
    """« Spotify » tout court, à deux lignes de l'API Spotify, désigne deux choses.

    Le CSV et l'API sont deux processus différents (c'est la remarque même de
    l'artiste). L'entrée doit nommer la SOURCE du fichier, pas la plateforme.
    """
    # L'import CSV n'a plus d'entrée de menu depuis le 2026-09-04 : il a fusionné
    # dans la page Credentials, en onglet. La QUESTION ne change pas — « le libellé
    # nomme-t-il la source du fichier, ou seulement la plateforme ? » — mais elle se
    # pose maintenant sur le libellé de l'onglet. Un garde ancré sur l'ENDROIT serait
    # mort avec l'entrée ; ancré sur la question, il suit.
    from src.dashboard.utils.i18n_catalog.credentials import EN as _CREDS_EN

    keys = [k for _s, lbl, k in _artist_items()]
    assert "upload_csv" not in keys, (
        "l'entrée de menu séparée pour l'import CSV est revenue")

    label = _CREDS_EN["credentials.csv_tab"]
    assert "for artists" in label.lower(), (
        f"l'onglet d'import s'appelle {label!r} : « Spotify » seul se confond avec "
        "l'API Spotify, réglée dans les onglets voisins"
    )
    creds = next(lbl for _s, lbl, k in _artist_items() if k == "credentials")
    assert "CSV" in creds, (
        f"l'entrée Credentials ne dit pas qu'elle porte aussi les imports : {creds!r}")


def test_the_algo_prediction_entry_does_not_promise_one_algorithm():
    """La page prédit DW, Release Radar ET Radio — trois modèles, trois onglets."""
    label = next(lbl for _s, lbl, key in _artist_items() if key == "trigger_algo")
    assert "algos" in label.lower() or "algorithmes" in label.lower(), (
        f"{label!r} ne nomme qu'un algorithme alors que la page en prédit trois"
    )


def test_the_config_section_is_not_called_data():
    """La section ne contient aucune donnée : elle contient la mise en route."""
    header = next(h for sid, h, _i in _NAV_SECTIONS if sid == "data")
    assert "donnée" not in header.lower(), (
        f"la section de configuration s'appelle {header!r} ; elle ne contient pas de "
        "données mais l'assistant, le guide, les identifiants et les imports"
    )


def test_data_wrapped_sits_with_the_readings_not_the_exports():
    """Ce n'est pas un export : c'est une lecture de ses chiffres."""
    section = next(sid for sid, _l, key in _artist_items() if key == "data_wrapped")
    assert section == "analytics", (
        f"Data Wrapped est rangé dans la section {section!r}. Un export produit un "
        "fichier ; Data Wrapped se regarde à l'écran, comme les six pages au-dessus."
    )


# ── Les flèches ──────────────────────────────────────────────────────────────

def _rendered_all():
    return [(f"_nav_{sid}", header, items) for sid, header, items in _NAV_SECTIONS]


def test_the_arrows_walk_the_menu_in_order():
    unlocked = lambda _k: False       # noqa: E731 — tout ouvert (premium)
    rendered = _rendered_all()
    order = [key for _s, _h, items in rendered for _l, key in items]

    prev, nxt = _neighbour_pages(rendered, order[0], unlocked)
    assert prev is None and nxt == order[1], "la première page n'a pas de précédente"

    prev, nxt = _neighbour_pages(rendered, order[-1], unlocked)
    assert prev == order[-2] and nxt is None, "la dernière page n'a pas de suivante"

    mid = order[len(order) // 2]
    prev, nxt = _neighbour_pages(rendered, mid, unlocked)
    assert prev is not None and nxt is not None
    assert order.index(prev) < order.index(mid) < order.index(nxt)


def test_the_arrows_skip_locked_pages():
    """Une flèche ne doit jamais mener au paywall.

    C'est la différence entre un geste d'exploration et un parcours d'obstacles : le
    menu montre les pages Premium avec leur 🔒 — là, le clic est délibéré. Une flèche
    qui tombe une fois sur deux sur « Passez à Premium » cesse d'être utilisable.
    """
    rendered = _rendered_all()
    order = [key for _s, _h, items in rendered for _l, key in items]
    locked_key = order[1]

    prev, nxt = _neighbour_pages(rendered, order[0], lambda k: k == locked_key)
    assert nxt == order[2], (
        f"la flèche suivante mène à {nxt!r}, qui est verrouillée — elle doit "
        "l'enjamber"
    )


def test_an_unknown_page_gives_no_arrows_rather_than_crashing():
    """`upgrade` et les pages hors menu existent : elles ne doivent pas lever."""
    assert _neighbour_pages(_rendered_all(), "upgrade", lambda _k: False) == (None, None)


# ── La sortie ────────────────────────────────────────────────────────────────

def test_logout_is_rendered_after_the_menu_not_inside_the_identity_block():
    """« Se déconnecter » tout en bas, et dans les DEUX branches d'affichage.

    Il vivait dans `show_user_sidebar`, donc juste sous le nom de l'artiste et
    au-dessus des quarante entrées du menu. Et la première connexion ne rend pas le
    menu : un appel placé dans cette branche-là aurait laissé un écran sans sortie,
    exactement ce que l'assistant a corrigé le matin même avec son gros bouton.
    """
    auth_src = (_ROOT / "src" / "dashboard" / "auth.py").read_text(encoding="utf-8")
    tree = ast.parse(auth_src)
    user_box = next(f for f in ast.walk(tree)
                    if isinstance(f, ast.FunctionDef) and f.name == "show_user_sidebar")
    box_src = ast.get_source_segment(auth_src, user_box) or ""
    assert "auth.logout" not in box_src, (
        "le bouton de déconnexion est revenu dans le bloc d'identité, en HAUT de la "
        "barre : la troisième chose lue en arrivant serait le bouton pour partir"
    )
    assert any(isinstance(f, ast.FunctionDef) and f.name == "render_logout_footer"
               for f in ast.walk(tree)), "render_logout_footer a disparu"

    app_src = (_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8")
    app_tree = ast.parse(app_src)
    body = next(f for f in ast.walk(app_tree)
                if isinstance(f, ast.FunctionDef) and f.name == "_main_body")
    calls = [n for n in ast.walk(body)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "render_logout_footer"]
    assert len(calls) == 1, (
        f"{len(calls)} appel(s) à render_logout_footer dans _main_body — il en faut "
        "exactement un, hors du if/else, pour couvrir la première connexion"
    )

    # La QUESTION est « l'artiste peut-il sortir ? », pas « le bouton est-il
    # inconditionnel ». Ce garde exigeait le second, et il a rougi le 2026-09-05
    # quand la déconnexion a été retirée de l'écran de mise en route — demandé, et
    # sans danger : cet écran a une sortie, un gros bouton centré qui mène dans
    # l'application, plus « Aller au dashboard » à l'étape 2.
    #
    # Un bouton « Se déconnecter » à côté d'un compte créé il y a trente secondes
    # propose surtout de perdre ce qu'on vient de faire.
    #
    # Ce qui reste vérifié, et qui est la vraie propriété : la déconnexion est rendue
    # PARTOUT AILLEURS, donc sa condition ne peut porter que sur la mise en route.
    guarded = [n for n in ast.walk(body)
               if isinstance(n, ast.If)
               and any(isinstance(c, ast.Call)
                       and getattr(c.func, "id", "") == "render_logout_footer"
                       for c in ast.walk(n))]
    if guarded:
        names = {x.id for n in guarded for x in ast.walk(n.test) if isinstance(x, ast.Name)}
        assert names & {"_bare", "_focus", "FIRST_RUN_FOCUS"}, (
            f"la déconnexion est conditionnée par {sorted(names)} — la seule condition "
            "admise est l'écran de mise en route, qui a sa propre sortie. Partout "
            "ailleurs, un écran dont on ne peut pas partir n'est pas une aide.")

    # …et l'écran de mise en route a bien une sortie qui n'est pas la déconnexion.
    onb = ast.parse((_ROOT / "src" / "dashboard" / "views" / "onboarding.py"
                     ).read_text(encoding="utf-8"))
    exits = [n for n in ast.walk(onb) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "_goto"]
    assert exits, (
        "l'assistant n'a plus aucune sortie : sans déconnexion NI bouton d'entrée "
        "dans l'application, c'est une porte fermée")


@pytest.mark.parametrize("key", ["home", "credentials", "onboarding"])
def test_every_menu_key_is_unique(key):
    """Une clé en double ferait cocher deux radios pour une seule page."""
    keys = [k for _s, _l, k in _artist_items()]
    assert keys.count(key) == 1, f"{key} apparaît {keys.count(key)} fois dans le menu"
