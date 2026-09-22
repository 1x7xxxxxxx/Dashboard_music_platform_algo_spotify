"""La vue de campagne dit la vérité sur ce qu'elle trace, et sur ce qu'elle ne trace pas.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/views/meta_x_spotify.py, i18n_catalog, nav_sections,
            stripe_schema
Persists in: nothing

Ce que ce fichier garde, et pourquoi chaque assertion existe
-------------------------------------------------------------
La page s'appelait « Performance 360° » et promettait six séries. Mesuré le
2026-09-21 sur le locataire 1 : **elle ne pouvait en dessiner que deux.** Deux
causes, toutes deux silencieuses :

1. la courbe de streams comparait `s4a_song_timeline.song` (épelé depuis un NOM DE
   FICHIER, donc `_`) à `campaign_track_mapping.track_name` — zéro ligne pour
   3 titres sur 7, dont la campagne à 684,98 € ;
2. la courbe de popularité n'avait aucun point possible : le relevé commence le
   23/11/2025, la dernière campagne s'est terminée le 30/09/2024.

Une entrée de légende qui ne peut rien dessiner est pire qu'une phrase qui dit
pourquoi. Les gardes ci-dessous tiennent les deux moitiés du correctif : le
rattachement ne passe plus par un nom, et chaque série a un libellé.
"""
from __future__ import annotations

import ast
import functools
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VIEW = _ROOT / "src" / "dashboard" / "views" / "meta_x_spotify.py"


@functools.lru_cache(maxsize=1)
def _tree() -> ast.Module:
    """UN SEUL arbre, mis en cache — les `id()` de `_docstrings()` doivent venir
    du même `parse` que ceux de la boucle qui les consulte, sinon l'exclusion ne
    correspond à rien et le garde redevient aveugle à sa propre prose."""
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _docstrings() -> set[int]:
    """Les `id()` des constantes qui SONT des docstrings — module, classe, fonction."""
    out = set()
    for node in ast.walk(_tree()):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            corps = getattr(node, "body", None)
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant):
                out.add(id(corps[0].value))
    return out


def _series_columns() -> list[str]:
    """Les colonnes de `_SERIES`, lues dans l'AST — jamais importées.

    Importer la vue tirerait Streamlit et la base ; on lit la déclaration.
    """
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        cibles = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "_SERIES" not in cibles or not isinstance(node.value, ast.List):
            continue
        return [el.elts[0].value for el in node.value.elts
                if isinstance(el, ast.Tuple) and isinstance(el.elts[0], ast.Constant)]
    raise AssertionError("`_SERIES` est introuvable dans la vue")


def test_the_series_declaration_is_readable_and_not_empty() -> None:
    """NON-VACUITÉ. Tout ce fichier est paramétré par cette liste."""
    cols = _series_columns()
    assert len(cols) >= 6, (
        f"{len(cols)} série(s) déclarée(s) — il y en avait 8 le 2026-09-21. Une "
        "liste vide rendrait tous les cas ci-dessous vacants et verts.")


@pytest.mark.parametrize("col", _series_columns())
def test_every_plotted_series_is_named(col: str) -> None:
    """Une série tracée sans libellé s'affiche avec sa clé brute en anglais.

    La clé est construite en f-string (`t(f"meta_x_spotify.series_{col}")`), donc
    le détecteur d'orphelines de `test_i18n_orphans` ne peut pas la rapprocher du
    catalogue : ce test est la contrepartie qui empêche l'exemption de préfixe
    d'ouvrir une porte sans contrôle.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.i18n_catalog.meta_x_spotify import EN
    cle = f"meta_x_spotify.series_{col}"
    assert cle in EN, (
        f"la série '{col}' s'affichera avec sa clé brute en anglais — ajoute "
        f"'{cle}' au catalogue")


# Les noms de colonne, par ORTHOGRAPHE. C'est la seule chose qui compte : la
# classe ne parle pas de tables, elle parle de la façon dont un titre est épelé.
_COTE_FICHIER = ("song", "platform_title")      # dérivés d'un nom de fichier S4A
_COTE_API = ("track_name", "title")             # écrits par une API Spotify

# `<qualif.>?<colonne>` des deux côtés d'un `=`, TRIM/LOWER/TRIM() tolérés.
_ENVELOPPE = r"(?:TRIM|LOWER|UPPER)?\s*\(?\s*(?:\w+\.)?(\w+)\s*\)?"
_EGALITE = re.compile(rf"{_ENVELOPPE}\s*=\s*{_ENVELOPPE}", re.I)


def _compare_deux_orthographes(sql: str) -> str | None:
    """La requête met-elle une colonne FICHIER et une colonne API de part et
    d'autre d'un `=` ? Rend le fragment fautif, ou None.

    ⚠️ CE PRÉDICAT EST LE SECOND JET, et le premier a été pris au vert par une
    mutation. Il cherchait la CHAÎNE `TRIM(song)` — une forme d'écriture — et
    `TRIM(d.song) = TRIM(m.track_name)`, le défaut exact, lui échappait parce que
    la colonne y est qualifiée. C'est `a-sweep-predicate-that-matches-a-form-not-
    a-property`, la règle 20 de CLAUDE.md, enfreinte dans le test écrit POUR
    elle. Celui-ci lit les deux côtés d'une égalité et compare leurs
    ORTHOGRAPHES, quels que soient les qualificateurs et les enveloppes.
    """
    for gauche, droite in _EGALITE.findall(sql):
        g, d = gauche.lower(), droite.lower()
        if (g in _COTE_FICHIER and d in _COTE_API) or \
           (g in _COTE_API and d in _COTE_FICHIER):
            return f"{gauche} = {droite}"
    return None


def test_the_detector_sees_the_comparison_it_is_written_for() -> None:
    """NON-VACUITÉ, et elle est obligatoire ici.

    Les trois formes ci-dessous sont FABRIQUÉES : la nue, la qualifiée (celle qui
    a échappé au premier jet), et l'ordre inverse. La forme SAINE — une valeur
    liée, résolue par le lien confirmé — doit rester muette, sans quoi corriger
    le défaut rendrait la CI rouge.
    """
    for fautif in (
        "SELECT * FROM v_s4a_song_daily d JOIN campaign_track_mapping m "
        "ON TRIM(song) = TRIM(track_name)",
        "SELECT * FROM v_s4a_song_daily d JOIN campaign_track_mapping m "
        "ON TRIM(d.song) = TRIM(m.track_name)",
        "SELECT * FROM campaign_track_mapping m JOIN s4a_song_timeline s "
        "ON m.track_name = s.song",
    ):
        assert _compare_deux_orthographes(fautif), (
            f"forme fautive non détectée : {fautif}")

    for sain in (
        "SELECT day, streams FROM v_s4a_song_daily WHERE artist_id = %s AND song = %s",
        "SELECT ... JOIN track_platform_link s4a ON s4a.match_key = any_l.match_key "
        "AND s4a.platform = 's4a' AND s4a.status = 'confirmed'",
        "SELECT ... ON TRIM(any_l.platform_title) = TRIM(m.track_name)",
    ):
        if "platform_title" in sain and "track_name" in sain:
            continue      # traité ci-dessous, c'est l'exception NOMMÉE
        assert not _compare_deux_orthographes(sain), (
            f"le détecteur accuse une requête saine : {sain}")


def test_the_view_never_compares_a_song_name_to_a_track_name() -> None:
    """LE défaut du 2026-09-21, et il était muet.

    `v_s4a_song_daily.song` vient d'un NOM DE FICHIER (`_` à la place de
    `< > : " / \\ | ? *`) ; `campaign_track_mapping.track_name` vient tantôt de
    l'API, tantôt du fichier, selon le chemin d'écriture — mesuré : les deux
    orthographes coexistent en base chez le locataire 1. Les comparer rend zéro
    ligne, sans erreur : 3 titres sur 7, dont la campagne à 684,98 €.

    ⚠️ UNE SEULE comparaison de noms subsiste, et elle est NOMMÉE : le résolveur
    rapproche `campaign_track_mapping.track_name` du `platform_title` d'un lien,
    en essayant TOUTES les plateformes. C'est justement ce qui la rend sûre —
    elle ne présume pas l'orthographe, elle essaie les deux, puis redescend par
    `match_key`. Tout le reste doit passer par le lien confirmé.
    """
    interdits = []
    for node in ast.walk(_tree()):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in _docstrings():
            continue      # le garde ne doit pas rougir sur la prose qui l'explique
        sql = " ".join(node.value.split())
        faute = _compare_deux_orthographes(sql)
        if faute and "platform_title" not in faute:
            interdits.append(f"{faute}  —  dans : {sql[:90]}")
    assert not interdits, (
        "La vue compare de nouveau un nom de FICHIER à un nom d'API :\n  "
        + "\n  ".join(interdits)
        + "\nLe rattachement passe par `track_platform_link` (platform='s4a', "
          "status='confirmed'), jamais par un nom.")


def test_the_resolver_goes_through_the_confirmed_link() -> None:
    """Et la forme SAINE est présente — sans ça, le test ci-dessus passe sur du vide."""
    sqls = [" ".join(n.value.split()) for n in ast.walk(_tree())
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert any("track_platform_link" in s and "'s4a'" in s and "'confirmed'" in s
               for s in sqls), (
        "aucune requête ne passe par le LIEN CONFIRMÉ de `track_platform_link` : "
        "le rattachement est reparti par un nom, ou a disparu.")


def test_the_absences_are_explained_not_hidden() -> None:
    """Une source absente porte une PHRASE, pas un silence.

    Six sources annoncées, deux dessinables : ce qui manquait n'était pas la
    donnée, c'était la phrase qui dit laquelle manque et pourquoi.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.i18n_catalog.meta_x_spotify import EN
    for cle in ("meta_x_spotify.abs_unlinked", "meta_x_spotify.abs_streams",
                "meta_x_spotify.abs_pi", "meta_x_spotify.abs_hyp",
                "meta_x_spotify.abs_apple"):
        assert cle in EN, f"{cle} : une absence sans phrase est un silence"


def test_the_premium_section_lists_exactly_what_is_sold() -> None:
    """La section « Premium » du menu et le catalogue de prix ne divergent pas.

    Les six pages payantes vivaient dans CINQ sections différentes. Les
    rassembler n'a de valeur que si le critère reste le PLAN — pas le thème de la
    page. `meta_ads_overview` touche à Meta et reste gratuite : elle n'entre pas.

    Les deux sens sont vérifiés, et c'est le point : une section « Premium » qui
    contient une page gratuite ment au visiteur, et une page payante laissée
    ailleurs rend le regroupement inutile.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.database.stripe_schema import page_is_locked
    from src.dashboard.utils.nav_sections import NAV_SECTIONS

    admin_only = {"airflow_kpi", "admin", "ml_performance", "useful_links", "etl_logs",
                  "referral_kpi", "promo_admin", "usage_analytics", "alerts", "db_health"}
    sections = {sec: [k for _, k in items] for sec, _, items in NAV_SECTIONS}
    assert "premium" in sections, "la section « premium » a disparu du menu"

    gratuites_dans_premium = [k for k in sections["premium"] if not page_is_locked("free", k)]
    assert not gratuites_dans_premium, (
        f"la section « Premium » contient des pages GRATUITES : {gratuites_dans_premium}. "
        "Le critère est le plan, pas le thème.")

    # `trigger_algo` est payante et garde sa propre section : c'est la promesse du
    # produit, elle vient AVANT ce que l'abonnement ouvre. Toute autre page payante
    # atteignable par un artiste appartient à « premium ».
    #
    # ⚠️ `export_pdf` a rejoint la tête de menu le 2026-09-22, sur demande explicite
    # (« export csv et export pdf à déplacer car accueil et ensuite guide de
    # démarrage »). Elle est payante et elle vit dans « start », à côté d'`home`,
    # `onboarding` et `export_csv` — c'est le parcours d'un artiste neuf, et le
    # rapport en fait partie même quand il faut payer pour l'ouvrir.
    #
    # Ce que ce garde défendait — « un 🔒 semé au milieu de pages gratuites ne dit
    # pas ce que l'abonnement contient » — est désormais tenu par AUTRE CHOSE : les
    # cadenas colorés posés sur les noms de section le même jour (🔒 rouge / 🔓 vert,
    # `utils/nav_badges.py`). Le signal est passé du REGROUPEMENT à la PASTILLE.
    #
    # L'exemption nomme la PAGE, pas la section. Exempter « start » en entier
    # laisserait n'importe quelle page payante future s'y ranger sans que rien ne le
    # dise — et c'est exactement la dérive que ce test existe pour attraper.
    _PAYANTES_HORS_PREMIUM = {"export_pdf"}
    ailleurs = [k for sec, keys in sections.items()
                if sec not in ("premium", "advanced", "admin")
                for k in keys
                if k not in admin_only and k not in _PAYANTES_HORS_PREMIUM
                and page_is_locked("free", k)]
    assert not ailleurs, (
        f"page(s) payante(s) hors de la section « Premium » : {ailleurs}. Un 🔒 semé "
        "au milieu de pages gratuites ne dit pas ce que l'abonnement contient.")


def test_the_prediction_opens_what_the_subscription_sells() -> None:
    """La prédiction est la PROMESSE du produit : elle ouvre la liste de ce qu'on paie.

    ⚠️ CE TEST EXIGEAIT AUTRE CHOSE, et son remplacement est le point. Il demandait
    que la section « premium » soit **juste sous** une section « advanced ». Le
    2026-09-22, « 🔮 Prédiction algos Spotify » a cessé d'être une section — demandé
    en regardant l'écran — parce qu'elle n'en portait qu'une, et que cette page est
    PAYANTE : une section d'un seul élément payant posée à côté de « 💎 Premium — ce
    que l'abonnement ouvre » séparait la promesse du produit de la liste de ce qu'on
    achète.

    L'INTENTION n'a pas changé : la prédiction vient en premier parce que c'est ce
    que l'abonnement vend d'abord. Elle s'exprime maintenant sur la place de la PAGE
    dans la section, et non sur la place d'une section dans le menu — donc un
    regroupement de sections ne peut plus la casser par accident.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    sections = dict((sec, [k for _, k in items]) for sec, _, items in NAV_SECTIONS)
    assert "premium" in sections, f"la section « premium » a disparu : {list(sections)}"
    assert sections["premium"], "la section « premium » est vide"
    assert sections["premium"][0] == "trigger_algo", (
        "la prédiction de déclenchement n'ouvre plus la section Premium : "
        f"{sections['premium']}. C'est la promesse du produit ; elle vient en tête de "
        "ce que l'abonnement vend.")
    assert "advanced" not in sections, (
        "une section « advanced » est revenue. Elle a été retirée le 2026-09-22 : une "
        "section d'un seul élément payant, posée à côté de la liste de ce qu'on paie, "
        "sépare la promesse du produit de son prix.")


def test_the_padlock_says_what_the_plan_opens_not_only_what_it_blocks() -> None:
    """🔒 fermé, 🔓 ouvert — deux faits, deux marques.

    Avant le 2026-09-21, un 🔒 marquait « verrouillé » et l'absence de 🔒
    marquait TOUT le reste : une page gratuite et une page Premium que l'artiste
    PAIE s'écrivaient exactement pareil. Un abonné n'avait donc aucun moyen de
    voir ce que son abonnement lui ouvre — c'est-à-dire ce qu'on lui facture.

    Le test lit `_fmt` tel que `render_navigation` le construit, en remplaçant
    la seule chose qui dépend de la base : le plan. Vérifié au rendu réel le
    2026-09-21 (AppTest + `_view_as`), et figé ici pour que ça le reste.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    from src.database.stripe_schema import page_is_locked

    admin_only = {"airflow_kpi", "admin", "ml_performance", "useful_links", "etl_logs",
                  "referral_kpi", "promo_admin", "usage_analytics", "alerts", "db_health"}
    pages = [k for sec, _, items in NAV_SECTIONS if sec != "admin"
             for _, k in items if k not in admin_only]
    premium = {k for k in pages if page_is_locked("free", k)}
    assert premium, "aucune page payante — le cliquet ci-dessous ne mesurerait rien"

    def badge(plan: str, key: str) -> str:
        if page_is_locked(plan, key):
            return "🔒 "
        return "🔓 " if key in premium else ""

    for key in pages:
        attendu_free = "🔒 " if key in premium else ""
        attendu_prem = "🔓 " if key in premium else ""
        assert badge("free", key) == attendu_free, (
            f"{key} : un artiste Free voit « {badge('free', key)} » au lieu de "
            f"« {attendu_free} »")
        assert badge("premium", key) == attendu_prem, (
            f"{key} : un artiste Premium voit « {badge('premium', key)} » au lieu "
            f"de « {attendu_prem} » — une page payante qu'il a doit se voir.")


def test_the_app_builds_the_badge_the_same_way() -> None:
    """Le test ci-dessus recopie une règle ; celui-ci vérifie que le CODE la porte.

    Sans lui, le menu pourrait perdre le 🔓 sans qu'une seule assertion bouge —
    c'est la forme exacte de `a-guard-that-tests-its-own-copy-of-the-rule`.

    La règle est APPELÉE, pas réécrite : on la fait tourner sur les quatre cas
    (gratuit/payant × Free/Premium). `nav_badges.badge` est pure — ni Streamlit,
    ni session, ni base — et c'est précisément ce que son extraction hors
    d'`app.py` a acheté le 2026-09-21.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.nav_badges import badge
    from src.database.stripe_schema import page_is_locked

    # ⚠️ Les cadenas portent une COULEUR depuis le 2026-09-22 — « rouge et vert
    # mais léger ». Les valeurs attendues sont donc du markdown Streamlit, et non
    # l'emoji nu. La couleur enveloppe le seul cadenas : un libellé de menu
    # entièrement teinté se lirait comme une page en panne.
    payantes = {"meta_x_spotify"}
    assert badge("meta_x_spotify", is_locked=lambda k: page_is_locked("free", k),
                 paid_pages=payantes) == ":red[🔒] "
    assert badge("meta_x_spotify", is_locked=lambda k: page_is_locked("premium", k),
                 paid_pages=payantes) == ":green[🔓] "
    assert badge("home", is_locked=lambda k: page_is_locked("free", k),
                 paid_pages=payantes) == ""

    # L'EN-TÊTE de section, ajouté le même jour. Une section ENTIÈREMENT payante
    # porte l'état du plan ; une section mixte se tait, parce qu'un cadenas qui
    # parle pour la majorité ment à la minorité.
    from src.dashboard.utils.nav_badges import section_badge

    assert section_badge(["meta_x_spotify"],
                         is_locked=lambda k: page_is_locked("free", k),
                         paid_pages=payantes) == ":red[🔒]"
    assert section_badge(["meta_x_spotify"],
                         is_locked=lambda k: page_is_locked("premium", k),
                         paid_pages=payantes) == ":green[🔓]"
    assert section_badge(["home", "meta_x_spotify"],
                         is_locked=lambda k: page_is_locked("free", k),
                         paid_pages=payantes) == "", (
        "une section mixte porte une marque : elle affirmerait pour toutes ses "
        "pages ce qui n'est vrai que pour certaines")

    # Et `app.py` appelle bien CETTE règle, plutôt que d'en garder une copie.
    arbre = ast.parse((_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8"))
    importe = any(isinstance(n, ast.ImportFrom) and n.module
                  and n.module.endswith("nav_badges") for n in ast.walk(arbre))
    assert importe, (
        "`app.py` n'importe plus `nav_badges` : le menu a repris une copie locale "
        "de la règle, et les assertions ci-dessus ne décrivent plus ce que "
        "l'artiste voit.")
