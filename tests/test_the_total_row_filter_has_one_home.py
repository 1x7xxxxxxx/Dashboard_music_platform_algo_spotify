"""Le filtre de la ligne « Total » de S4A s'écrit à UN seul endroit.

Type: Test
Uses: ast, re
Depends on: src/utils/artist_name_filter.py
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
CLAUDE.md déclare la règle **obligatoire** : « every query on `s4a_song_timeline` must
add `AND song NOT ILIKE '%1x7xxxxxxx%'` ». Elle était écrite **sept fois** en constante
de module, sous trois orthographes (`ARTIST_NAME_FILTER`, `_ARTIST_FILTER`,
`_S4A_FILTER`) et deux formes (avec ou sans les jokers `%`).

⚠️ **Et les trois copies de `src/api/` avaient une RAISON.** Importer depuis
`kpi_helpers` aurait tiré `streamlit` dans le processus `uvicorn` — ce module l'importe
à sa ligne 5. Un développeur qui refuse cette dépendance et recopie la constante fait le
bon arbitrage avec les mauvais outils. Le remède n'était donc pas « importez la
canonique » mais **un domicile que les deux couches peuvent atteindre** : `src/utils/`,
que `src/api/` importe déjà. Vérifié après coup : l'API ne charge toujours pas
`streamlit`.

⚠️ **Le rapport de balayage annonçait 6 sites ; il y en avait ~18.** Son prédicat ne
cherchait qu'une orthographe. Compté par le LITTÉRAL, en séparant les formes :
7 constantes de module, 12 requêtes SQL en ligne, 8 mentions en prose — et **9
occurrences qui ne sont pas le filtre du tout** mais l'adresse de contact du
propriétaire, qui contient la même chaîne. Les confondre aurait produit un troisième
chiffre faux.

Ce que ce garde couvre, et ce qu'il ne couvre PAS
--------------------------------------------------
Il couvre la forme **constante de module**. Il ne couvre PAS les **12 littéraux en
ligne dans du SQL** (`ILIKE '%1x7xxxxxxx%'` écrit dans la requête) : les migrer demande
de toucher douze requêtes, ce qui n'est pas un effet de bord de séance. Ils sont
mesurés, listés dans le champ `siblings` de
`a-rule-copied-is-a-rule-that-will-diverge`, et parqués.
Il ne couvre pas non plus l'adresse de contact, qui est une autre grandeur.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_LITTERAL = "1x7xxxxxxx"
_COURRIEL = f"{_LITTERAL}@gmail.com"
_DOMICILE = "src/utils/artist_name_filter.py"


def _est_une_constante(nom: str) -> bool:
    """Un nom de CONSTANTE de module : majuscules, éventuellement préfixé d'un `_`."""
    corps = nom[1:] if nom.startswith("_") else nom
    return bool(corps) and corps == corps.upper() and corps[0].isalpha()


def _constantes(root: Path | None = None, motif: str = "src/**/*.py") -> dict[str, list[int]]:
    """{fichier: lignes} pour toute CONSTANTE de module valant le littéral.

    ⚠️ Lu à l'AST, jamais au texte. Trois méta-gardes du dépôt ont refusé la première
    version de ce fichier, qui comparait des chaînes contre le source ligne à ligne —
    et ils avaient raison : un commentaire, une docstring ou un exemple auraient suffi
    à la satisfaire, y compris la prose de CE fichier, qui cite le littéral six fois.
    """
    root = ROOT if root is None else root
    out: dict[str, list[int]] = {}
    for p in sorted(root.glob(motif)):
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel = str(p.relative_to(root))
        for n in arbre.body:                       # niveau MODULE seulement
            if not isinstance(n, ast.Assign):
                continue
            if not isinstance(n.value, ast.Constant) or \
                    not isinstance(n.value.value, str):
                continue
            valeur = n.value.value
            if _COURRIEL in valeur:
                continue                 # l'adresse de contact est une AUTRE grandeur
            # La constante doit ÊTRE le filtre, pas le CONTENIR. Une requête SQL qui
            # porte `ILIKE '%1x7xxxxxxx%'` en son milieu est l'autre catégorie —
            # 12 sites, mesurés et PARQUÉS dans le champ `siblings` de la classe :
            # les migrer demande de toucher douze requêtes. Sans cette frontière, ce
            # garde rougirait sur du travail explicitement remis à plus tard, et la
            # seule façon de le calmer serait de le désarmer.
            if valeur.strip("%") != _LITTERAL:
                continue
            noms = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(_est_une_constante(x) for x in noms):
                out.setdefault(rel, []).append(n.lineno)
    return out


def test_the_filter_has_exactly_one_home():
    trouve = _constantes()
    intrus = {k: v for k, v in trouve.items() if k != _DOMICILE}
    assert not intrus, (
        f"le filtre de la ligne « Total » est redéfini hors de `{_DOMICILE}` : {intrus}. "
        "Chaque copie est une divergence latente — elle se déclenchera à la première "
        "modification d'une seule d'entre elles. Importer "
        "`ARTIST_NAME_FILTER` (la valeur nue) ou `ARTIST_NAME_LIKE` (le motif avec ses "
        "jokers) depuis `src/utils/`, que le dashboard ET l'API peuvent atteindre.")


def test_the_home_still_declares_it():
    """Non-vacuité : sans la déclaration, le test ci-dessus passe sur rien."""
    assert _DOMICILE in _constantes(), (
        f"`{_DOMICILE}` ne déclare plus le littéral — soit il a bougé, soit le prédicat "
        "est cassé, et dans les deux cas l'exclusivité ne garde plus rien.")


def test_the_two_forms_agree():
    """La valeur nue et le motif `LIKE` décrivent la MÊME chaîne."""
    from src.utils.artist_name_filter import ARTIST_NAME_FILTER, ARTIST_NAME_LIKE

    assert ARTIST_NAME_LIKE == f"%{ARTIST_NAME_FILTER}%", (
        f"les deux formes ont divergé : {ARTIST_NAME_LIKE!r} contre "
        f"{ARTIST_NAME_FILTER!r} — c'est la classe, à l'intérieur de son propre remède")


def test_the_api_does_not_drag_streamlit():
    """La RAISON des trois copies de l'API : elles évitaient cette dépendance.

    Si importer le domicile ramenait `streamlit` dans `uvicorn`, le remède serait pire
    que le mal et les copies reviendraient — avec raison.
    """
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-c",
         "import src.api.routers.kpis, src.api.routers.ml, src.api.routers.streams; "
         "import sys; print('streamlit' in sys.modules)"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f"les routeurs ne s'importent plus : {r.stderr[-400:]}"
    assert r.stdout.strip() == "False", (
        "importer les routeurs de l'API charge maintenant `streamlit` — c'est "
        "exactement ce que les trois copies évitaient, et le remède vient de le "
        "réintroduire")


def test_the_predicate_separates_the_filter_from_the_contact_address(tmp_path):
    """Le littéral apparaît aussi dans l'adresse du propriétaire — autre grandeur.

    Neuf occurrences dans `src/`. Les compter comme des copies de la règle aurait
    produit un troisième chiffre faux pour la même question.
    """
    f = tmp_path / "exemple.py"
    f.write_text(
        f'CONTACT = "{_COURRIEL}"\n'
        f'_ARTIST_FILTER = "%{_LITTERAL}%"\n'
        f'# _AUTRE = "{_LITTERAL}" dans un commentaire\n'
        f'minuscule = "{_LITTERAL}"\n'
        f'_SQL = "SELECT 1 WHERE song NOT ILIKE \'%{_LITTERAL}%\'"\n',
        encoding="utf-8")
    # Le VRAI prédicat du garde, pas une copie : le 2026-09-26 cette preuve portait
    # sa propre boucle, et retirer l'exclusion de l'adresse de contact dans
    # `_constantes` la laissait verte (balayage `sibling-sweeper`).
    trouve = _constantes(tmp_path, "*.py")
    lignes = trouve.get("exemple.py", [])
    vus = [f.read_text(encoding="utf-8").splitlines()[ln - 1].split(" =")[0] for ln in lignes]
    assert vus == ["_ARTIST_FILTER"], (
        f"le prédicat ne sépare plus les CINQ formes : {vus}. Il doit voir la "
        "CONSTANTE qui EST le filtre, et ignorer l'adresse de contact, le commentaire, "
        "la minuscule, et la REQUÊTE SQL qui ne fait que le contenir — cette dernière "
        "est l'autre catégorie, mesurée et parquée.")
