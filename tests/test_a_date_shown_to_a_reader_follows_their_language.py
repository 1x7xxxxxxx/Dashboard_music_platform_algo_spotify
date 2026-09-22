"""Une date montrée à un lecteur ne peut pas se lire à l'envers dans sa langue.

Type: Guard
Uses: ast
Depends on: src/dashboard/utils/date_format.py
Persists in: nothing

LE DÉFAUT, ET POURQUOI IL EST PASSÉ INAPERÇU TROIS MOIS
--------------------------------------------------------
`%d/%m/%Y` était la convention du dépôt : **49 sites, 28 fichiers**, mesurés le
2026-09-22. En français elle se lit sans peine. En anglais — livré depuis le 2026-06-10,
`i18n._LANGS` porte `en`, et le PDF est bilingue — elle se lit **à l'envers** :

    04/03/2025   →   4 mars     pour un lecteur français
                 →   3 avril    pour un lecteur anglais

Le même écran, le même pixel, un mois d'écart, et rien pour trancher. ⚠️ **Le cas ne
saute aux yeux que pour un jour au-dessus de 12** — donc **environ deux tiers des dates
de l'année sont lues correctement par accident**. C'est la pire fréquence possible :
assez rare pour qu'on ne le remarque jamais, assez fréquente pour que ça arrive.

CE QUE CE GARDE TIENT
---------------------
Aucun `%d/%m/%Y` dans du code qui FORMATE une date pour un lecteur. Le remède est
`src/dashboard/utils/date_format.format_date`, qui rend `30/09/2024` en français et
`30 Sep 2024` en anglais : **un nom de mois supprime l'ambiguïté**, là où passer
l'anglais en `%m/%d/%Y` ne ferait que la déplacer.

LES TROIS EXEMPTIONS, ET CHACUNE A SA RAISON
---------------------------------------------
Elles sont nommées et vérifiées — une liste de noms qui survivrait à sa raison est
exactement ce que ce dépôt a vidé le matin du 2026-09-22 dans `audit_runner.py`.

* `date_format.py` — **c'est le formateur**. Il PRODUIT `%d/%m/%Y` en français ; le lui
  interdire reviendrait à interdire le remède.
* `sacem_parser.py` — **c'est une LECTURE**, pas un affichage : `strptime("%d/%m/%Y")`
  décrit le format du fichier SACEM. Une propriété de la source, pas une décision
  d'écran. Le test ci-dessous vérifie que ce site est bien un `strptime`, pas un
  `strftime` — l'exemption ne couvre donc pas un affichage qui s'y glisserait.
* `freshness_monitor.py` — sa phrase est **du français écrit en dur**, non traduite
  (« aucune sortie depuis le dernier import »). Son format de date est cohérent avec sa
  langue. Traduire cette phrase est un autre travail, porté en roadmap.

⚠️ CE QU'IL NE TIENT PAS
------------------------
1. **Les autres formats ambigus.** `%m/%d/%Y` et `%d-%m-%Y` posent le même problème et
   ne sont pas cherchés : ils n'existent pas dans ce dépôt aujourd'hui, et un garde qui
   interdit ce qui n'existe pas ne se vérifie jamais.
2. **Le geste voisin le plus proche : une date construite à la main**
   (`f"{d.day}/{d.month}/{d.year}"`). Elle est invisible à ce prédicat, et elle produit
   exactement la même ambiguïté.
3. **La JUSTESSE du fuseau.** `to_local_datetime` reste la porte pour ça et s'applique
   AVANT le formateur ; rien ici ne vérifie qu'on l'a appelée.
4. **Les heures.** `format_datetime` garde le 24 h dans les deux langues — non ambigu
   partout — mais rien n'empêche d'écrire un `%I:%M %p` ailleurs.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Les trois exemptions, chacune avec la raison qui la rend vérifiable plus bas.
_LE_FORMATEUR = "src/dashboard/utils/date_format.py"
_LE_PARSER = "src/transformers/sacem_parser.py"
_L_ALERTE_FR = "src/utils/freshness_monitor.py"
_EXEMPTES = frozenset({_LE_FORMATEUR, _LE_PARSER, _L_ALERTE_FR})

_MOTIF = "%d/%m/%Y"


def _chaines(tree) -> list[tuple[int, str]]:
    """Les littéraux de chaîne du module, avec leur ligne. Les f-strings comprises.

    ⚠️ PAR L'AST, PAS PAR LES LIGNES DU FICHIER. Le premier jet lisait le texte ligne
    par ligne : `test_a_guard_reads_structure_not_text` l'a refusé, et il avait raison
    deux fois. (1) Une assertion sur du texte source est satisfaite par un COMMENTAIRE —
    trois gardes ont été pris au vert sur leur propre défaut le 2026-09-04, dont deux
    sur le commentaire expliquant le correctif. (2) Le symétrique est aussi vrai et
    c'est celui qui m'aurait mordu : **écrire `%d/%m/%Y` dans un commentaire pour
    expliquer POURQUOI il a disparu aurait fait rougir ce garde.** C'est
    `a-bash-hook-that-blocks-the-prose-about-the-gesture` transposé à un test, et ce
    dépôt a bloqué trois commandes d'affilée pour ça le 2026-09-12.

    Un format de date vit dans une CHAÎNE, jamais dans un commentaire. L'AST ne voit que
    les chaînes, donc la prose est libre par construction.
    """
    # ⚠️ UN ENSEMBLE, PAS UNE LISTE. `ast.walk` visite la `JoinedStr` **et** la
    # `Constant` de son `format_spec` : un `f"{d:%d/%m/%Y}"` était compté DEUX fois, et
    # mon propre test de non-vacuité l'a dit (« 3 des deux formes »). Un balayage qui
    # sur-compte publie un nombre faux — le mode d'échec mesuré dix fois sur ce dépôt.
    out: set[tuple[int, str]] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add((n.lineno, n.value))
        elif isinstance(n, ast.JoinedStr):
            # Un `f"{d:%d/%m/%Y}"` porte son format dans le `format_spec` du champ,
            # pas dans une `Constant` du corps : il faut descendre.
            for partie in ast.walk(n):
                if isinstance(partie, ast.FormattedValue) and partie.format_spec:
                    for c in ast.walk(partie.format_spec):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            out.add((n.lineno, c.value))
    return sorted(out)


def _sites() -> list[str]:
    out = []
    for f in sorted((_ROOT / "src").rglob("*.py")):
        rel = f.relative_to(_ROOT).as_posix()
        if rel in _EXEMPTES:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for lineno, valeur in _chaines(tree):
            if _MOTIF in valeur:
                out.append(f"{rel}:{lineno}  {valeur[:80]!r}")
    return out


def test_no_view_formats_a_date_day_first() -> None:
    """LE CLIQUET, à zéro. 49 sites corrigés le 2026-09-22."""
    sites = _sites()
    assert not sites, (
        f"{len(sites)} site(s) formatent encore une date en `{_MOTIF}` :\n"
        + "\n".join(f"    {s}" for s in sites)
        + "\n\nEn mode anglais, `04/03/2025` se lit « 3 avril » au lieu de « 4 mars ». "
          "Utiliser `src.dashboard.utils.date_format.format_date`, qui rend "
          "`30/09/2024` en français et `30 Sep 2024` en anglais.")


def test_the_formatter_actually_disambiguates() -> None:
    """LE REMÈDE DOIT MARCHER, et sur la date qui sépare les deux lectures.

    Un garde qui interdit une forme sans vérifier que son remplaçant vaut mieux a déjà
    coûté cher ici : on remplace partout, et le défaut survit sous un autre nom.
    """
    import datetime

    from src.dashboard.utils.date_format import format_date

    ambigue = datetime.date(2025, 3, 4)          # 4 mars — le 4 est ≤ 12
    fr = format_date(ambigue, lang="fr")
    en = format_date(ambigue, lang="en")
    assert fr == "04/03/2025", fr
    assert not re.fullmatch(r"[\d/]+", en), (
        f"la forme anglaise « {en} » est encore entièrement numérique : elle reste "
        "ambiguë, elle a seulement changé d'ordre.")
    assert "Mar" in en, f"le mois ne porte pas son nom en anglais : {en}"
    assert "2025" in en and "04" in en, en


def test_the_two_languages_do_not_render_the_same_string() -> None:
    """NON-VACUITÉ : si les deux langues rendaient pareil, le module ne sert à rien."""
    import datetime

    from src.dashboard.utils.date_format import format_date

    d = datetime.date(2024, 9, 30)
    assert format_date(d, lang="fr") != format_date(d, lang="en"), (
        "les deux langues rendent la même chaîne — le formateur ne suit plus la langue.")


def test_a_missing_date_is_not_a_crash() -> None:
    """Une date absente n'est pas une panne d'écran.

    49 sites l'appellent désormais, dont plusieurs sur des colonnes qui portent des
    `NaT`. Lever ici ferait tomber une vue entière pour une case vide.
    """
    from src.dashboard.utils.date_format import format_date, format_datetime

    assert format_date(None) == "—"
    assert format_date("pas une date") == "—"
    assert format_datetime(None) == "—"
    assert format_date(None, vide="") == ""


def test_the_parser_exemption_is_a_parser_not_a_display() -> None:
    """L'EXEMPTION SE VÉRIFIE. `sacem_parser` LIT le format, il ne l'écrit pas.

    Si un `strftime("%d/%m/%Y")` s'y glissait, l'exemption le couvrirait en silence —
    c'est la forme exacte d'« une exemption qui survit à sa raison ».
    """
    src = (_ROOT / _LE_PARSER).read_text(encoding="utf-8")
    tree = ast.parse(src)
    ecritures = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", None) == "strftime"]
    assert not ecritures, (
        f"`{_LE_PARSER}` FORMATE une date (`strftime`) alors qu'il est exempté parce "
        "qu'il en LIT une. L'exemption ne couvre plus ce qu'elle disait couvrir.")
    # Par l'AST aussi : `"strptime" in src` serait satisfait par un commentaire.
    lectures = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "strptime"]
    assert lectures, (
        f"`{_LE_PARSER}` n'appelle plus `strptime` : il ne parse plus de date, son "
        "exemption n'a plus d'objet et doit être retirée.")


def test_the_french_alert_exemption_is_still_untranslated() -> None:
    """L'EXEMPTION SE VÉRIFIE (2). L'alerte est exemptée parce qu'elle est EN FRANÇAIS.

    Le jour où sa phrase passera par `t()`, sa date devra suivre la langue comme les
    autres — et ce test rougira pour le rappeler.
    """
    src = (_ROOT / _L_ALERTE_FR).read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert any(_MOTIF in v for _l, v in _chaines(tree)), (
        f"`{_L_ALERTE_FR}` ne porte plus `{_MOTIF}` dans une CHAÎNE : son exemption "
        "n'a plus d'objet et doit être retirée de `_EXEMPTES`.")

    # ⚠️ PAR L'AST, PAS PAR LE TEXTE. Le premier jet cherchait `"t(" not in voisinage`
    # sur 800 caractères autour du motif, avec deux `replace()` pour écarter `format(`
    # et `import(`. `test_a_guard_reads_structure_not_text` l'a refusé — et il avait
    # raison deux fois : un tel prédicat est satisfait par un commentaire, et ma liste
    # de `replace` aurait grandi à chaque nouveau faux positif.
    #
    # La propriété est vérifiable sans ambiguïté : ce module IMPORTE-t-il de quoi
    # traduire ? Une phrase ne passe pas par `t()` sans que `t` entre dans le module.
    traducteurs = {"t", "translate", "get_lang"}
    importe = sorted({
        a.asname or a.name
        for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        for a in n.names
        if (a.asname or a.name) in traducteurs
    })
    assert not importe, (
        f"`{_L_ALERTE_FR}` importe {importe} : sa phrase est désormais traduisible, "
        "donc sa date doit suivre la langue. Retirer l'exemption et utiliser "
        "`format_date`.")


def test_the_formatter_exemption_is_the_formatter() -> None:
    """L'EXEMPTION SE VÉRIFIE (3). Le formateur doit exposer ce qu'on exempte pour lui."""
    from src.dashboard.utils import date_format

    for nom in ("format_date", "format_datetime", "format_serie"):
        assert hasattr(date_format, nom), (
            f"`{_LE_FORMATEUR}` n'expose plus `{nom}` : il n'est plus le formateur, et "
            "son exemption couvre un fichier quelconque.")


def test_the_sweep_would_see_a_new_offender() -> None:
    """NON-VACUITÉ DU PRÉDICAT, sur la forme exacte qu'il doit refuser."""
    # Les DEUX formes que le dépôt portait, plus la prose qui doit rester libre.
    fautif = ast.parse('x = d.strftime("%d/%m/%Y")\ny = f"{d:%d/%m/%Y}"\n')
    trouve = [v for _l, v in _chaines(fautif) if _MOTIF in v]
    assert len(trouve) == 2, (
        f"le prédicat ne voit que {len(trouve)} des deux formes fautives ("
        "`strftime` et le format d'une f-string) : il en laisserait passer une.")

    # ⚠️ ET LA PROSE RESTE LIBRE. Un commentaire qui NOMME le format doit être
    # invisible, sinon documenter le correctif ferait rougir le garde du défaut.
    prose = ast.parse('# on n\'écrit plus %d/%m/%Y ici\nx = format_date(d)\n')
    assert not [v for _l, v in _chaines(prose) if _MOTIF in v], (
        "le prédicat voit un commentaire : écrire SUR le défaut le déclencherait.")


@pytest.mark.parametrize("rel", sorted(_EXEMPTES))
def test_every_exemption_still_exists(rel: str) -> None:
    """Une exemption sur un fichier disparu est une ligne morte dans un garde."""
    assert (_ROOT / rel).is_file(), (
        f"`{rel}` est exempté et n'existe plus : retirer l'entrée de `_EXEMPTES`.")
