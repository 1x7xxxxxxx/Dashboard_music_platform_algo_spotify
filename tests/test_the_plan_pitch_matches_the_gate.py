"""Ce que la page de prix PROMET est ce que le verrou OUVRE. Dérivé, pas recopié.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/utils/plan_pitch.py, src/database/stripe_schema.py,
            src/dashboard/utils/nav_sections.py, i18n_catalog/plan_pitch.py
Persists in: nothing

Le défaut, mesuré le 2026-09-21
--------------------------------
Le catalogue des plans était écrit TROIS fois — `billing.py`, `upgrade.py`,
`onboarding.py` — et les trois se contredisaient :

    surface          Export PDF        « génération vidéo 60+ par campagne »
    billing.py       dans FREE   ❌    annoncée en Premium   ❌
    upgrade.py       absent            absente
    onboarding.py    dans PREMIUM ✅   absente

Les deux erreurs sont de natures différentes, et il faut les nommer séparément :

* **Export PDF a QUITTÉ Free le 2026-09-04**, décision explicite portée par le
  commit 5fdc65a (« ce qui se vend n'est pas la donnée … c'est le RAPPORT »).
  `onboarding.py` a suivi, `billing.py` ne l'a jamais su : la page de facturation
  a donc promis gratuitement, **dix-sept jours durant**, ce que le menu affichait
  cadenassé.
* **La « génération de créatives vidéo » n'a jamais existé.** Balayé le
  2026-09-21 sur tout l'arbre : aucun `ffmpeg`, aucun `moviepy`, aucun module de
  rendu vidéo. C'est une prestation humaine, et elle est descendue dans le
  panneau de service, où elle est vraie.

Classe : `a-price-page-that-restates-a-gate-instead-of-reading-it`. Elle ne lève
jamais, elle ne se voit pas en test de rendu, et elle se paie en confiance — un
artiste qui clique sur ce qu'on lui a promis trouve un cadenas.

Ce que ce garde tient
---------------------
1. chaque ligne d'argumentaire nomme une page qui EXISTE dans la navigation ;
2. le plan d'affichage est LU dans `page_is_locked`, donc une page qui change de
   tiers déplace sa ligne toute seule ;
3. aucune page payante n'est absente de l'argumentaire — c'est la moitié qu'on
   oublie : vendre moins que ce qu'on ouvre ;
4. chaque clé a sa traduction anglaise ;
5. les trois surfaces lisent bien CE module, et pas leur propre liste.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Les trois pages qui affichent le catalogue. Si l'une reconstruit sa liste, la
# divergence recommence — et c'est exactement comme ça qu'elle a commencé.
_SURFACES = {
    "src/dashboard/views/billing.py",
    "src/dashboard/views/upgrade.py",
    "src/dashboard/views/onboarding.py",
}

# Pages hors argumentaire, chacune avec sa raison. Une page non vendue n'est pas
# forcément un oubli — mais l'exemption doit être NOMMÉE, jamais implicite.
_HORS_ARGUMENTAIRE = {
    "home": "l'accueil n'est pas un argument, c'est la porte",
    "onboarding": "la mise en route ; on ne vend pas le fait de pouvoir démarrer",
    "onboarding_health": "diagnostic de mise en route, même raison",
    "account": "gestion du compte, accessible à tous les plans par construction",
    "billing": "la page de prix elle-même",
    "db_health": "diagnostic de données, pas une promesse commerciale",
    "upload_csv": "route héritée, fusionnée dans `credentials` le 2026-09-04",
    "process_guide": "route héritée qui redirige vers `onboarding_health`",
}


def _nav_pages() -> set[str]:
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    return {k for _s, _l, items in NAV_SECTIONS for _lab, k in items}


def _routable_pages() -> set[str]:
    """Les pages qu'un `?page=…` atteint — entrée de menu ou non.

    ⚠️ CE N'EST PAS `_nav_pages()`, et le premier jet de ce garde faisait
    l'erreur : il a rougi sur `data_wrapped` le 2026-09-21. Cette page a quitté le
    MENU ce jour-là — son contenu est rendu replié dans « Spotify + Spotify for
    Artists » — mais **sa route vit toujours**, et la fonctionnalité avec. La
    vendre est donc parfaitement honnête.

    Le prédicat cherchait une FORME (« y a-t-il une entrée de menu ? ») là où la
    propriété est « la fonctionnalité est-elle atteignable ? ». C'est la classe
    `a-sweep-predicate-that-matches-a-form-not-a-property`, règle transverse 20,
    attrapée par une mutation involontaire : la vraie donnée du dépôt.
    """
    src = (_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out: set[str] = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Compare)
                and isinstance(n.left, ast.Name) and n.left.id == "page"
                and len(n.comparators) == 1
                and isinstance(n.comparators[0], ast.Constant)
                and isinstance(n.comparators[0].value, str)):
            out.add(n.comparators[0].value)
    return out | _nav_pages()


def _admin_pages() -> set[str]:
    src = (_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_ADMIN_ONLY":
            return set(ast.literal_eval(n.value))
    raise AssertionError("`_ADMIN_ONLY` introuvable : le garde ne sait plus "
                         "distinguer une page d'exploitant d'une page vendue")


# ── 1. Chaque ligne nomme une page réelle ──────────────────────────────────
def test_every_pitch_line_names_a_page_that_exists() -> None:
    from src.dashboard.utils.plan_pitch import _PITCH

    atteignables = _routable_pages()
    fantomes = [p for p, _c, _t in _PITCH
                if p is not None and p not in atteignables]
    assert not fantomes, (
        f"ligne(s) d'argumentaire pour une page absente du menu : {fantomes}. "
        "Vendre une page supprimée est la forme la plus coûteuse de cette classe : "
        "l'artiste paie, puis cherche.")


# ── 2. Le tiers est LU, jamais écrit ───────────────────────────────────────
def test_the_tier_is_read_from_the_gate() -> None:
    """La preuve par le cas qui a produit le défaut : `export_pdf`.

    Il a quitté Free le 2026-09-04. Si `tier_of` le rendait encore « free », le
    module recopierait une décision au lieu de la lire.
    """
    from src.dashboard.utils.plan_pitch import tier_of

    assert tier_of("export_pdf") == "premium", (
        "`export_pdf` est vendu comme gratuit. Il a quitté Free le 2026-09-04 "
        "(commit 5fdc65a) : `tier_of` doit LIRE `page_is_locked`.")
    assert tier_of("spotify_s4a_combined") == "free"
    assert tier_of("billing") == "free", "ALWAYS_ACCESSIBLE doit primer"


# ── 3. Aucune page payante n'est oubliée ───────────────────────────────────
def test_no_paid_page_is_missing_from_the_pitch() -> None:
    """Vendre MOINS que ce qu'on ouvre est l'autre moitié du défaut.

    Elle ne fait crier personne — l'artiste reçoit plus que promis — mais elle
    coûte la vente : quatre pages Premium n'étaient nommées nulle part le
    2026-09-21 (Impact de mes campagnes, Visuels de campagne, Qui a vu tes pubs,
    et la page d'argent avec son point mort).
    """
    from src.dashboard.utils.plan_pitch import pages_of, tier_of

    payantes = {p for p in _nav_pages()
                if p not in _admin_pages() and tier_of(p) == "premium"}
    oubliees = sorted(payantes - pages_of("premium") - set(_HORS_ARGUMENTAIRE))
    assert not oubliees, (
        f"page(s) payante(s) que l'argumentaire ne nomme pas : {oubliees}. "
        "Soit on les vend, soit on inscrit la raison dans `_HORS_ARGUMENTAIRE`.")


def test_every_exemption_carries_its_reason() -> None:
    vides = [k for k, why in _HORS_ARGUMENTAIRE.items() if not (why or "").strip()]
    assert not vides, f"exemption(s) sans raison : {vides}"


# ── 4. Chaque clé a sa traduction ──────────────────────────────────────────
def test_every_pitch_key_has_an_english_entry() -> None:
    """Le préfixe `pitch.` est exempté du balayage des orphelines — les clés sont
    des DONNÉES, pas des littéraux d'appel. C'est ici que le trou se bouche."""
    from src.dashboard.utils.i18n_catalog.plan_pitch import EN
    from src.dashboard.utils.plan_pitch import _HORS_PAGE, _PITCH

    attendues = {c for _p, c, _t in _PITCH}
    attendues |= {c for lignes in _HORS_PAGE.values() for c, _t in lignes}
    manquantes = sorted(attendues - set(EN))
    assert not manquantes, (
        f"clé(s) d'argumentaire sans traduction : {manquantes}. Sans entrée, "
        "l'artiste anglophone lit la version française dans sa page de prix.")


def test_the_service_credentials_are_translated() -> None:
    from src.database.stripe_schema import SERVICE_CREDENTIALS
    from src.dashboard.utils.i18n_catalog.billing import EN

    manquantes = [i for i in range(len(SERVICE_CREDENTIALS))
                  if f"billing.service_credential.{i}" not in EN]
    assert not manquantes, (
        f"argument(s) de service sans traduction : {manquantes}")


# ── 5. Les trois surfaces LISENT le module ─────────────────────────────────
@pytest.mark.parametrize("rel", sorted(_SURFACES))
def test_each_price_surface_reads_the_shared_pitch(rel: str) -> None:
    """Une surface qui reconstruit sa liste redémarre la divergence.

    Par l'AST et non par le texte : le nom du module DOIT pouvoir être cité en
    prose — c'est là qu'on explique pourquoi les copies ont disparu.
    """
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    lit = any(
        isinstance(n, ast.ImportFrom)
        and (n.module or "").endswith("plan_pitch")
        for n in ast.walk(tree))
    assert lit, (
        f"{rel} n'importe pas `utils.plan_pitch` : il reconstruit son propre "
        "catalogue. C'est exactement la forme qui a laissé « Export PDF » en "
        "Free pendant dix-sept jours après la décision de le faire payer.")


def test_the_pitch_does_not_sell_what_the_product_cannot_do() -> None:
    """La « génération de créatives vidéo » ne doit pas revenir dans un PLAN.

    Balayé le 2026-09-21 : rien dans `src/` ni `airflow/` ne produit de vidéo.
    L'argument est vrai de la PRESTATION, pas du logiciel — il vit dans
    `SERVICE_CREDENTIALS`, et c'est là qu'il doit rester.
    """
    from src.dashboard.utils.plan_pitch import _PITCH

    coupables = [c for _p, c, txt in _PITCH
                 if "génération" in txt.lower() and "vidéo" in txt.lower()]
    assert not coupables, (
        f"{coupables} vend une génération de vidéo dans un PLAN. Aucune ligne de "
        "code ne la fait : c'est du travail humain, et il est déjà décrit dans "
        "`SERVICE_CREDENTIALS`.")


def test_the_routable_scan_sees_more_than_the_menu() -> None:
    """NON-VACUITÉ de la correction ci-dessus.

    Si `_routable_pages()` se réduisait au menu, le garde redeviendrait le
    prédicat de FORME qu'il était, et rougirait de nouveau sur une page dont la
    route survit à son entrée de menu. Au moins une telle page doit exister —
    `data_wrapped` en est une depuis le 2026-09-21.
    """
    hors_menu = _routable_pages() - _nav_pages()
    assert hors_menu, (
        "aucune page routable hors du menu : soit `_routable_pages()` ne lit plus "
        "le routeur, soit le dépôt n'en a plus — dans les deux cas ce garde ne "
        "prouve plus ce que sa docstring annonce")
    assert "data_wrapped" in hors_menu, (
        f"`data_wrapped` n'est plus routable hors menu (hors menu : {sorted(hors_menu)}). "
        "Si sa route a disparu, retire sa ligne d'argumentaire — on ne vend pas "
        "ce qu'on ne peut plus atteindre.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """NON-VACUITÉ, sur la forme EXACTE du défaut — et sur la forme corrigée.

    Les deux moitiés comptent. Sans la seconde, corriger le défaut ferait rougir
    son propre garde : ce dépôt l'a mesuré le 2026-08-03, et la seule façon de
    garder la CI verte était alors d'arrêter de documenter.

    Le défaut reproduit ici est celui du 2026-09-21 : une ligne d'argumentaire qui
    AFFIRME son plan au lieu de le lire, et qui se retrouve donc en Free pour une
    page que le verrou a fait passer payante.
    """
    from src.dashboard.utils.plan_pitch import tier_of

    def _colonnes_fautives() -> tuple[set[str], set[str]]:
        """Le catalogue tel qu'il était : le tiers ÉCRIT à la main."""
        return ({"export_pdf", "spotify_s4a_combined"}, {"trigger_algo"})

    def _colonnes_saines() -> tuple[set[str], set[str]]:
        pages = {"export_pdf", "spotify_s4a_combined", "trigger_algo"}
        return ({p for p in pages if tier_of(p) == "free"},
                {p for p in pages if tier_of(p) == "premium"})

    def _detecte(colonnes) -> bool:
        libres, payantes = colonnes
        return any(tier_of(p) != ("free" if p in libres else "premium")
                   for p in libres | payantes)

    assert _detecte(_colonnes_fautives()), (
        "le détecteur ne voit pas `export_pdf` vendu en Free alors que le verrou "
        "le dit payant — c'est le défaut EXACT du 2026-09-21")
    assert not _detecte(_colonnes_saines()), (
        "le détecteur rougit sur la forme CORRIGÉE : un correctif ferait échouer "
        "son propre garde, et la seule sortie serait de cesser de corriger")
