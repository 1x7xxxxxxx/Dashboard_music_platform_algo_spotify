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
    """Les clés de page que `app.py` sait RENDRE — lues sur les `page == "…"`.

    Elles étaient lues dans `_NAV_SECTIONS` jusqu'au 2026-09-04, c'est-à-dire dans le
    MENU. La question de ce fichier n'a jamais été « peut-on cliquer dessus ? » mais
    « la case à cocher mène-t-elle quelque part ? » — et `upload_csv` a fusionné dans
    Credentials le même jour : plus d'entrée de menu, route conservée parce que six
    pointeurs la visent. Le garde est devenu rouge sur une destination parfaitement
    valide.

    Deuxième fois le même jour, sur deux fichiers : `test_the_setup_landing_beats_a_
    stale_url` portait le même prédicat et a été corrigé une heure plus tôt, SANS
    balayer ses frères — la règle #14 dit de balayer avant d'écrire le fix, et je ne
    l'ai pas fait. Les cinq fichiers qui lisent `_NAV_SECTIONS` ont été balayés cette
    fois : les quatre autres interrogent bien le menu (un libellé, une entrée
    attendue), et gardent donc leur lecture.
    """
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    return {n.comparators[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Compare) and getattr(n.left, "id", "") == "page"
            and n.comparators and isinstance(n.comparators[0], ast.Constant)
            and isinstance(n.comparators[0].value, str)}


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


# ── Après un enregistrement réussi, l'onglet SUIVANT s'ouvre ─────────────────

def test_a_successful_save_opens_the_next_tab():
    """`st.tabs` n'expose pas d'onglet actif : l'ORDRE est la redirection.

    Demandé le 2026-09-05 : « quand c'est marqué Suivante : SoundCloud, il faudrait
    que ça redirige directement vers l'onglet SoundCloud ».

    `st.tabs(default=…)` existe en 1.54 et A ÉTÉ ESSAYÉ EN PREMIER. Sa docstring dit
    « the default tab to select » — vrai au premier MONTAGE du widget ; sur un rerun,
    Streamlit conserve l'onglet sélectionné, et l'enregistrement passe précisément par
    un rerun. Vu au navigateur : l'onglet restait sur Spotify, `default` posé.

    Ce qui marche est de mettre la suivante EN TÊTE pour ce rerun-là. Le test fige la
    RÈGLE de ce réordonnancement, pas la séquence de clics.
    """
    import ast
    from pathlib import Path as _P

    router = _P(__file__).resolve().parents[1] / "src/dashboard/views/credentials/router.py"
    tree = ast.parse(router.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "show")

    reorders = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "ordered" for t in n.targets)]
    assert len(reorders) >= 2, (
        "la page ne réordonne plus ses onglets : après un enregistrement, elle "
        "rouvrirait celui qu'on vient de quitter")

    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "VERDICT_KEY" in names, (
        "le réordonnancement n'est plus conditionné au verdict : la page se "
        "réorganiserait sous les yeux de l'artiste à chaque rerun")


def test_only_one_tab_renders_the_verdict():
    """`pop` consomme le verdict — deux appelants et il disparaît au mauvais endroit.

    Le routeur désigne UN propriétaire (`verdict_owner`) et l'onglet ne rend que s'il
    l'est. Sans ce filtre, le premier onglet rendu par Streamlit — qui n'est pas celui
    qu'on regarde — mangerait le message.
    """
    import ast
    from pathlib import Path as _P

    base = _P(__file__).resolve().parents[1] / "src/dashboard/views/credentials"
    tree = ast.parse((base / "_render.py").read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_render_platform_tab")

    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "render_save_verdict"]
    assert len(calls) == 1, f"{len(calls)} appels au verdict dans un onglet"

    guarded = any(
        isinstance(n, ast.If)
        and any(getattr(x, "id", "") == "verdict_owner" for x in ast.walk(n.test))
        and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "render_save_verdict"
                for c in ast.walk(n))
        for n in ast.walk(fn))
    assert guarded, (
        "le verdict n'est plus filtré par `verdict_owner` : les cinq onglets "
        "l'appelleraient, et `pop` le ferait disparaître dans le premier rendu")


def test_the_soundcloud_failure_points_at_the_page_that_holds_the_panel():
    """Le message nommait « plus haut dans cet onglet » — le panneau n'y est plus.

    Il a été déplacé sur ☁️ SoundCloud — Performance le 2026-09-04, et le message a
    survécu au déplacement : il envoyait chercher, dans l'onglet Credentials, une
    section qui n'y était plus. Une direction relative ne survit pas au déplacement de
    ce qu'elle désigne — quatrième fois dans ce dépôt.

    Les DEUX langues, parce que l'anglaise avait perdu la moitié du message : elle ne
    disait que « vérifie que c'est ton profil » et taisait le recours pour un artiste
    signé sur un label — c'est-à-dire le cas qui a motivé la fonctionnalité.
    """
    from pathlib import Path as _P

    from src.dashboard.utils.i18n_catalog.credentials import EN

    src = (_P(__file__).resolve().parents[1]
           / "src/dashboard/views/credentials/_platform_soundcloud.py"
           ).read_text(encoding="utf-8")
    import ast as _ast
    fr = " ".join(n.value for n in _ast.walk(_ast.parse(src))
                  if isinstance(n, _ast.Constant) and isinstance(n.value, str))
    assert "plus haut dans cet onglet" not in fr, (
        "le message renvoie de nouveau « plus haut dans cet onglet » : le panneau des "
        "titres revendiqués vit sur ☁️ SoundCloud — Performance depuis le 2026-09-04")
    assert "SoundCloud — Performance" in fr, (
        "le message ne nomme plus la page qui porte le panneau")

    en = EN.get("credentials.soundcloud.no_public_tracks", "")
    assert en, "la traduction du message a disparu"
    assert "Performance" in en, (
        "la traduction ne nomme pas la page qui porte le panneau — un anglophone "
        "signé sur un label lirait « ton ID est peut-être faux » alors qu'il est juste")
