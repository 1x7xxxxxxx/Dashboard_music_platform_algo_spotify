"""Ce qu'un artiste coche à la mise en route doit le mener quelque part.

Type: Test
Uses: platform_value (le registre des cases à cocher), credentials.router (les onglets)
Depends on: src/dashboard/content/platform_value.py,
    src/dashboard/views/credentials/router.py
Persists in: nothing

Le défaut que ça ferme
----------------------
Signalé le 2026-09-04, après un vrai parcours : « j'avais sélectionné spotify, insta
et soundcloud, et il me montre uniquement spotify & meta ». La sélection est faite sur
des plateformes LOGIQUES (six), la page de saisie est faite d'ONGLETS (quatre), et la
traduction entre les deux vivait dans un dictionnaire d'une ligne qui ne couvrait
qu'un cas — Instagram → Meta. Les deux autres écarts n'étaient couverts par rien :

  * `apple_music` n'a aucun onglet (c'est un import de fichier). Cochée, elle
    disparaissait complètement : ni onglet, ni ligne dans le repli « les autres
    plateformes » (qui se construit à partir des onglets), ni message. Et comme elle
    n'est jamais « connectée » au sens des identités, elle restait éternellement en
    tête de `remaining()` — le bandeau annonçait donc « Suivante : 🎎 Apple Music »
    en promettant un onglet qui n'existe pas.
  * rien ne vérifiait la couverture. Ajouter une septième plateforme au registre
    aurait produit le même trou, en silence.

Ce que ce fichier affirme, et pourquoi c'est structurel
--------------------------------------------------------
Que la traduction est TOTALE : toute clé cochable a une destination, et cette
destination existe vraiment (un onglet du registre, ou une page routée par `app.py`).
Le test lit le registre des cases, pas une liste recopiée ici — une plateforme
ajoutée demain est couverte par construction, ou le test devient rouge le jour de son
ajout plutôt que le jour du premier test artiste.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.content.platform_value import PLATFORM_VALUES, CREDENTIALS, CSV
from src.dashboard.views.credentials._registry import PLATFORMS
from src.dashboard.views.credentials.router import platform_destination

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"


def _routed_pages() -> set[str]:
    """Les clés de page que `app.py` sait rendre — lues dans les `_NAV_SECTIONS`.

    Comparer à une liste écrite ici ferait exactement ce que ce fichier reproche au
    reste : une deuxième copie qui dérive.
    """
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    pages: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "_NAV_SECTIONS" for t in node.targets):
            continue
        for const in ast.walk(node.value):
            if isinstance(const, ast.Constant) and isinstance(const.value, str):
                pages.add(const.value)
    return pages


def test_every_checkbox_leads_somewhere_that_exists():
    """Chaque plateforme cochable → un onglet réel ou une page réellement routée."""
    routed = _routed_pages()
    assert "credentials" in routed, (
        "la lecture des pages de app.py n'a rien trouvé — le test ne prouverait rien"
    )

    broken = []
    for pv in PLATFORM_VALUES:
        dest = platform_destination(pv.key)
        kind, target = dest.split(":", 1)
        if kind == "tab" and target not in PLATFORMS:
            broken.append(f"{pv.key} → onglet '{target}' (inexistant)")
        elif kind == "page" and target not in routed:
            broken.append(f"{pv.key} → page '{target}' (non routée)")

    assert not broken, (
        "Ces plateformes sont cochables à la mise en route et ne mènent nulle part :\n  "
        + "\n  ".join(broken)
        + "\n\nAjoute son onglet dans `_registry.PLATFORMS`, ou sa page dans "
          "`router._PAGE_FOR_PLATFORM`. Une case à cocher sans destination laisse "
          "l'artiste avec un plan dont une ligne s'est évaporée."
    )


def test_where_says_credentials_the_destination_is_a_tab():
    """`PlatformValue.where` et la destination doivent dire la même chose.

    Deux registres qui décrivent le même fait : ils s'accordent (ADR-009) ou l'un des
    deux ment. `where=CSV` avec une destination d'onglet est la forme exacte du bug
    d'Apple Music, à l'envers.
    """
    mismatched = []
    for pv in PLATFORM_VALUES:
        kind = platform_destination(pv.key).split(":", 1)[0]
        expected = "tab" if pv.where == CREDENTIALS else "page"
        if kind != expected:
            mismatched.append(f"{pv.key}: where={pv.where!r} mais destination={kind!r}")
    assert not mismatched, "\n".join(mismatched)


def test_the_reported_selection_yields_its_three_destinations():
    """Le cas signalé, tel qu'il a été vécu : spotify + instagram + soundcloud.

    Ce qui doit sortir : TROIS onglets — Spotify, SoundCloud et Meta / Instagram —
    et jamais les deux qu'il a vus.
    """
    selection = ["spotify", "instagram", "soundcloud"]
    tabs = {platform_destination(k).split(":", 1)[1] for k in selection}
    assert tabs == {"spotify", "soundcloud", "meta"}, (
        f"la sélection {selection} donne les onglets {sorted(tabs)}; "
        "SoundCloud doit y être, et Instagram doit passer par l'onglet Meta"
    )


def test_a_csv_platform_is_never_announced_as_the_next_tab():
    """Apple Music ne doit jamais être « la suivante » sur la page des identifiants.

    C'est la moitié du défaut qui rendait le bandeau faux en permanence : une
    plateforme qui ne peut pas être connectée ici reste indéfiniment en tête de ce
    qui reste à faire.
    """
    csv_keys = [pv.key for pv in PLATFORM_VALUES if pv.where == CSV]
    assert csv_keys, "aucune plateforme CSV : ce test ne prouverait rien"
    for key in csv_keys:
        assert platform_destination(key).startswith("page:"), (
            f"{key} s'importe par fichier mais pointe vers un onglet de saisie"
        )


def test_the_guard_goes_red_on_the_shape_that_shipped():
    """Mutation : la table de traduction d'avant, celle qui ne couvrait qu'Instagram.

    Sans cette assertion, les quatre au-dessus passeraient aussi bien sur un
    `platform_destination` qui renvoie « onglet » pour tout — c'est-à-dire sur le
    code qui a produit le défaut.
    """
    def old_destination(key: str) -> str:
        return f"tab:{ {'instagram': 'meta'}.get(key, key) }"

    offenders = {pv.key for pv in PLATFORM_VALUES
                 if old_destination(pv.key).split(":", 1)[1] not in PLATFORMS}
    csv_keys = {pv.key for pv in PLATFORM_VALUES if pv.where == CSV}
    assert offenders == csv_keys, (
        "la mutation ne reproduit plus le défaut d'origine : elle devrait perdre "
        f"exactement les plateformes qui s'importent par fichier. Attendu {csv_keys}, "
        f"trouvé {offenders}."
    )
    assert csv_keys, "plus aucune plateforme CSV : la mutation ne prouverait rien"


# ── L'onglet qui S'OUVRE après un enregistrement ────────────────────────────

def _tab_order(focus, connected):
    """L'ordre des onglets tel que `router.show()` le calcule.

    Recopié ici plutôt qu'importé, parce que le tri vit dans le corps de `show()` —
    une fonction Streamlit qu'on ne peut pas appeler sans rendre une page entière.
    Ce qui est figé est donc la RÈGLE ; la mutation en fin de fichier prouve que la
    règle recopiée est bien celle qui distingue le bon comportement du défaut.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS

    head = [k for k in focus if k not in connected
            and platform_destination(k).startswith("tab:")][:1]

    def tab_of(k):
        dest = platform_destination(k)
        return dest.split(":", 1)[1] if dest.startswith("tab:") else ""

    wanted = [tab_of(k) for k in head + [f for f in focus if f not in head]]
    rank: dict = {}
    for i, tab in enumerate(t for t in wanted if t):
        rank.setdefault(tab, i)
    out = list(PLATFORMS.items())
    out.sort(key=lambda kv: (rank.get(kv[0], len(rank)),))
    return [k for k, _ in out]


def test_the_next_platform_is_the_tab_that_opens():
    """`st.tabs` ouvre TOUJOURS le premier : l'ordre EST la redirection.

    Défaut vu au navigateur le 2026-09-04. Après avoir enregistré Spotify, le bandeau
    annonçait « Suivante : 📸 Instagram » et la page rouvrait… l'onglet Spotify.

    Le rang était calculé sur les clés LOGIQUES de la sélection, qui contient
    `instagram` — or `instagram` n'est jamais une clé d'onglet : il se saisit dans
    celui de `meta`. Son rang 0 ne s'appliquait donc à personne, `meta` tombait au
    rang par défaut, et `spotify` restait en tête. Même classe que le défaut
    `_TAB_FOR_PLATFORM` de la veille : une traduction logique → onglet posée à un
    endroit et oubliée à l'autre.
    """
    focus = ["spotify", "instagram"]
    assert _tab_order(focus, set())[0] == "spotify", (
        "avant toute connexion, l'onglet ouvert doit être la première plateforme "
        "choisie"
    )
    assert _tab_order(focus, {"spotify"})[0] == "meta", (
        "après avoir connecté Spotify, l'onglet ouvert doit être celui d'Instagram — "
        "c'est-à-dire « 📱 Meta / Instagram ». Sinon le bandeau annonce une suivante "
        "que la page n'ouvre pas."
    )


def test_the_tab_order_guard_goes_red_on_the_shape_that_shipped():
    """Mutation : le rang calculé sur les clés logiques, comme avant le correctif.

    Nom distinct de la mutation du haut de fichier — deux fonctions homonymes dans un
    module Python, c'est la seconde qui écrase la première : le garde des destinations
    n'aurait plus jamais tourné. Ruff l'a vu (F811) ; sans lui, un test aurait
    disparu en silence, ce qui est précisément le genre de perte que ce fichier
    existe pour empêcher ailleurs.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS

    def buggy(focus, connected):
        head = [k for k in focus if k not in connected][:1]
        rank = {k: i for i, k in enumerate(head + [f for f in focus if f not in head])}
        out = list(PLATFORMS.items())
        out.sort(key=lambda kv: (rank.get(kv[0], len(rank)),))
        return [k for k, _ in out]

    assert buggy(["spotify", "instagram"], {"spotify"})[0] == "spotify", (
        "la mutation ne reproduit plus le défaut — vérifie qu'Instagram n'a toujours "
        "pas d'onglet à lui"
    )
