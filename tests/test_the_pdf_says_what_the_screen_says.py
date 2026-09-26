"""
Guard — le PDF de l'artiste ne peut pas annoncer « configuré » quand l'écran dit non.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/utils/pdf_exporter/_collectors.py
Persists in: nothing

Error class: two-surfaces-two-truths.

Mesuré le 2026-08-23, remonté par un artiste en test (« Configuré api alors qu'on avait
fait que youtube »). `_collect_credentials_status` calculait son propre verdict :

    return [(label, (key in have) or app_level_configured(key)) ...]

Deux faux verts indépendants, dans un document que l'artiste GARDE :

1. `key in have` teste l'existence d'une ligne dans `artist_credentials` — un onglet
   ouvert puis enregistré vide crée cette ligne. C'est précisément ce que
   `declared_identities` avait été écrit pour tuer.
2. `or app_level_configured(key)` rend les plateformes vertes **à partir du `.env` de
   l'administrateur**, pour un locataire qui n'a rien déclaré.

Le contraste est ce qui rend la classe intéressante : la matrice à l'écran est CORRECTE.
Elle passe par `artist_readiness` → `tenant_identity`, où un `.env` admin ne peut rien
rendre vert. Deux surfaces, deux vérités, et c'est la surface imprimée — celle qui survit
à la session — qui mentait.

Le garde est structurel : le PDF ne doit pas RECALCULER le verdict, il doit le LIRE là où
l'écran le lit. Un test de valeur exigerait une base ; celui-ci tient dans l'AST et tourne
partout, y compris en CI sans Postgres.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PDF = _ROOT / "src" / "dashboard" / "utils" / "pdf_exporter" / "_collectors.py"
_MATRIX = _ROOT / "src" / "dashboard" / "utils" / "status_matrix.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(node: ast.AST) -> set[str]:
    return {
        (getattr(n.func, "id", "") or getattr(n.func, "attr", ""))
        for n in ast.walk(node) if isinstance(n, ast.Call)
    }


def second_truth(fn: ast.FunctionDef, source: str) -> list[str]:
    """Why a collector computes its OWN verdict instead of reading the screen's. Pure."""
    calls = _calls(fn)
    why = []
    if "artist_readiness" not in calls:
        why.append("ne lit pas artist_readiness")
    if "app_level_configured" in calls:
        why.append("lit la configuration de l'admin")
    if "FROM artist_credentials" in (ast.get_source_segment(source, fn) or ""):
        why.append("compte des lignes d'artist_credentials")
    return why


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the 2026-08 collector (rows counted, admin `.env` consulted, readiness
    never read) is refused on all three counts; one reading readiness is accepted."""
    defect = ("def _collect_credentials_status(db, aid):\n"
              "    rows = db.fetch_query('SELECT platform FROM artist_credentials "
              "WHERE artist_id = %s', (aid,))\n"
              "    return {p: bool(r) or app_level_configured(p) for p, r in rows}\n")
    fn = next(n for n in ast.walk(ast.parse(defect)) if isinstance(n, ast.FunctionDef))
    assert second_truth(fn, defect) == [
        "ne lit pas artist_readiness", "lit la configuration de l'admin",
        "compte des lignes d'artist_credentials"]
    fixed = ("def _collect_credentials_status(db, aid):\n"
             "    return {m['key']: m['status'] != 'todo' for m in artist_readiness(db, aid)}\n")
    fn = next(n for n in ast.walk(ast.parse(fixed)) if isinstance(n, ast.FunctionDef))
    assert second_truth(fn, fixed) == []


def test_the_pdf_has_one_truth():
    source = _PDF.read_text(encoding="utf-8")
    assert not second_truth(_fn(_PDF, "_collect_credentials_status"), source)


def test_the_pdf_reads_the_same_source_as_the_screen():
    fn = _fn(_PDF, "_collect_credentials_status")
    assert "artist_readiness" in _calls(fn), (
        "_collect_credentials_status doit lire `artist_readiness`, la source de la "
        "colonne « Configuré » affichée à l'écran. Recalculer le verdict ici l'a fait "
        "diverger : le PDF disait « configuré », l'écran « à connecter »."
    )


def test_the_pdf_never_reads_the_admin_environment():
    """`app_level_configured` répond « la PLATEFORME est prête », pas « TU es prêt »."""
    fn = _fn(_PDF, "_collect_credentials_status")
    assert "app_level_configured" not in _calls(fn), (
        "le PDF de l'artiste ne doit pas consulter la configuration de l'ADMIN : elle "
        "rendrait Spotify/YouTube/SoundCloud/Meta verts pour un locataire qui n'a rien "
        "déclaré. C'est le défaut d'origine."
    )


def test_the_pdf_does_not_count_a_row_as_a_declaration():
    """Un onglet enregistré vide crée une ligne ; ce n'est pas une identité déclarée."""
    src = ast.get_source_segment(_PDF.read_text(encoding="utf-8"),
                                 _fn(_PDF, "_collect_credentials_status")) or ""
    assert "FROM artist_credentials" not in src, (
        "compter les lignes d'`artist_credentials` revient à confondre « l'onglet a été "
        "ouvert » avec « une identité a été déclarée » — le défaut que `declared_identities` "
        "existe pour empêcher."
    )


def test_the_screen_predicate_is_still_the_one_we_mirror():
    """Si l'écran change de prédicat, ce garde doit tomber plutôt que mentir.

    La colonne « Configuré » vaut `status != "todo"`. On ne recopie pas la règle dans le
    PDF, mais on épingle ici qu'elle n'a pas bougé — sinon les deux surfaces
    redivergeraient en silence, ce qui est exactement la classe.
    """
    text = _MATRIX.read_text(encoding="utf-8")
    assert 'r["status"] != "todo"' in text, (
        "le prédicat de la colonne « Configuré » a changé dans status_matrix.py : "
        "vérifier que le PDF suit toujours, puis mettre ce test à jour."
    )
