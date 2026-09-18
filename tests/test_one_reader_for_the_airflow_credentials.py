"""Un seul endroit du dépôt lit les identifiants de l'API Airflow.

Type: Test
Uses: ast, tests/code_text.py
Depends on: src/utils/airflow_trigger.py
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
Le dépôt entretenait **quatre** précédences pour les mêmes identifiants :

| site | précédence | conséquence |
|---|---|---|
| `app.py:75` | `AIRFLOW_*` puis `config.yaml` | correcte |
| `credentials/_render.py:1116` | `AIRFLOW_ADMIN_*` puis `AIRFLOW_*`, sans `config.yaml` | latente ; et `os.getenv('AIRFLOW_PASSWORD', '')` rendait une chaîne VIDE |
| `views/home.py:763` | **aucune** — `AirflowTrigger()` nu | **HTTP 401**, bouton « Lancer les collectes » mort |
| `dashboard/utils/airflow_monitor.py:50` | environnement seul | `session.auth = (None, None)` — client NON authentifié rapportant « Aucun DAG trouvé » |

Et c'était une **récidive** : `archive.md:1958` (HIGH-05, juin 2026) annonce déjà ce
correctif — « RuntimeError raised if AIRFLOW_PASSWORD is falsy ». Il avait été écrit
dans un APPELANT plutôt que dans la classe, donc la classe a gardé ses défauts
littéraux `admin`/`admin` et trois appelants sont nés depuis.

**Une vérification d'identifiant qui vit dans un appelant sur quatre n'est pas une
vérification.** Ce fichier épingle la propriété au bon niveau : un seul lecteur.

Ce qu'il ne couvre PAS — à lire avant de s'y fier
--------------------------------------------------
* des identifiants arrivant sous un nom qui ne commence pas par `AIRFLOW_` : une clé
  de `config.yaml`, une ligne en base, une valeur passée en paramètre d'un helper ;
* un nom CALCULÉ (`os.getenv("AIRFLOW_" + "PASSWORD")`) — le prédicat lit une
  constante, et il le dit ;
* un SECOND client HTTP vers la même API qui n'utiliserait jamais ces noms ;
* la JUSTESSE de la valeur. Aucun garde ne distingue `admin` du vrai mot de passe —
  c'est le 401 mesuré, et seule une sonde de démarrage le voit.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_NOM = re.compile(r"^AIRFLOW_.*(USERNAME|PASSWORD)$")

# LE propriétaire, et lui seul.
_PROPRIETAIRE = "src/utils/airflow_trigger.py"

_ARBRES = ("src/**/*.py", "airflow/**/*.py", "tools/**/*.py", ".claude/scripts/**/*.py")


def _lectures_denv(chemin: Path) -> list[str]:
    """Les noms `AIRFLOW_*_(USERNAME|PASSWORD)` que ce fichier LIT dans son code.

    On parcourt l'AST : un nom cité dans un commentaire ou une docstring n'est pas une
    lecture. Ce dépôt a mesuré six fois en une séance qu'une assertion de présence se
    satisfait de la prose du fichier qu'elle inspecte.
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    trouves = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        nom = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        if nom not in ("getenv", "get"):
            continue
        # `os.environ.get("X")` et `os.getenv("X")` — la cible doit être environ/os.
        cible = ast.unparse(n.func)
        if "environ" not in cible and "getenv" not in cible:
            continue
        for a in n.args[:1]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                    and _NOM.match(a.value):
                trouves.append(a.value)
    # `os.environ["X"]`
    for n in ast.walk(arbre):
        if isinstance(n, ast.Subscript) and "environ" in ast.unparse(n.value):
            s = n.slice
            if isinstance(s, ast.Constant) and isinstance(s.value, str) \
                    and _NOM.match(s.value):
                trouves.append(s.value)
    return trouves


def _lecteurs() -> dict[str, list[str]]:
    out = {}
    for motif in _ARBRES:
        for p in ROOT.glob(motif):
            rel = str(p.relative_to(ROOT))
            noms = _lectures_denv(p)
            if noms:
                out[rel] = sorted(set(noms))
    return out


def test_only_the_factory_reads_the_airflow_credentials():
    lecteurs = _lecteurs()
    intrus = {k: v for k, v in lecteurs.items() if k != _PROPRIETAIRE}
    assert not intrus, (
        f"ces fichiers lisent les identifiants Airflow hors de `{_PROPRIETAIRE}` : "
        f"{intrus}. Chaque lecteur est une précédence, et le dépôt en a entretenu "
        "QUATRE — dont une qui n'en avait aucune (`AirflowTrigger()` nu, HTTP 401) et "
        "une qui produisait `auth = (None, None)`. Passer par "
        "`build_airflow_trigger()`."
    )


def test_the_factory_does_read_them():
    """Non-vacuité : si le propriétaire cesse de lire, le test ci-dessus passe sur rien."""
    noms = set(_lectures_denv(ROOT / _PROPRIETAIRE))
    assert {"AIRFLOW_USERNAME", "AIRFLOW_PASSWORD"} <= noms, (
        f"`{_PROPRIETAIRE}` ne lit plus `AIRFLOW_USERNAME`/`AIRFLOW_PASSWORD` "
        f"(trouvé : {sorted(noms)}) — soit la fabrique a bougé, soit le prédicat est "
        "cassé. Dans les deux cas le test d'exclusivité ne garde plus rien.")


def test_the_reader_predicate_ignores_prose():
    """Un nom cité en commentaire ou en docstring n'est PAS une lecture.

    Sans cette propriété, écrire SUR le défaut — ce que font les commentaires posés
    dans `app.py` et `_render.py` le 2026-09-18 — rendrait le garde rouge, et la seule
    façon de le calmer serait de cesser de documenter.
    """
    import tempfile

    src = ('"""AIRFLOW_PASSWORD dans une docstring."""\n'
           '# AIRFLOW_USERNAME dans un commentaire\n'
           'x = "AIRFLOW_PASSWORD"          # une chaine, pas une lecture\n')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        chemin = Path(f.name)
    try:
        assert _lectures_denv(chemin) == [], (
            "le prédicat compte de la prose comme une lecture d'environnement")
    finally:
        chemin.unlink()


def test_the_reader_predicate_sees_the_three_forms():
    """Et il voit les trois écritures réelles, sinon il ne garde rien."""
    import tempfile

    src = ('import os\n'
           'a = os.getenv("AIRFLOW_PASSWORD")\n'
           'b = os.environ.get("AIRFLOW_USERNAME")\n'
           'c = os.environ["AIRFLOW_ADMIN_PASSWORD"]\n')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        chemin = Path(f.name)
    try:
        vus = set(_lectures_denv(chemin))
        assert vus == {"AIRFLOW_PASSWORD", "AIRFLOW_USERNAME", "AIRFLOW_ADMIN_PASSWORD"}, (
            f"le prédicat rate une des trois formes : {sorted(vus)}")
    finally:
        chemin.unlink()


@pytest.mark.parametrize("argument", [
    {"base_url": "http://h", "username": "", "password": "p"},
    {"base_url": "http://h", "username": "u", "password": ""},
    {"base_url": "http://h", "username": "u", "password": None},
])
def test_the_class_refuses_a_falsy_credential(argument):
    """Sur une valeur FAUSSE, pas seulement absente — `_render.py` passait `''`."""
    from src.utils.airflow_trigger import AirflowTrigger

    with pytest.raises(ValueError, match="vide ou absent"):
        AirflowTrigger(**argument)


def test_the_class_refuses_credentials_inside_the_url():
    """`redact()` ne nettoie pas l'« userinfo » d'une URL — on refuse la forme."""
    from src.utils.airflow_trigger import AirflowTrigger

    with pytest.raises(ValueError, match="identifiants dans l'URL"):
        AirflowTrigger(
            base_url="http://admin:secret@airflow:8080",  # pragma: allowlist secret
            username="u", password="p")  # pragma: allowlist secret


def test_the_class_has_no_default_credentials():
    """La propriété au niveau de la CLASSE — c'est elle qui avait été perdue.

    Le correctif de juin 2026 (`archive.md:1958`) avait été écrit dans `app.py`. La
    classe a gardé ses deux littéraux d'administrateur, et trois appelants sont nés
    depuis, dont un qui construisait nu.
    """
    import inspect

    from src.utils.airflow_trigger import AirflowTrigger

    sig = inspect.signature(AirflowTrigger.__init__)
    avec_defaut = [n for n, p in sig.parameters.items()
                   if n in ("username", "password", "base_url")
                   and p.default is not inspect.Parameter.empty]
    assert not avec_defaut, (
        f"{avec_defaut} porte(nt) une valeur par défaut. Un identifiant qui a un "
        "défaut est un identifiant qu'on oublie de passer — et le défaut était "
        "`admin`/`admin`, donc un déclenchement de DAG non authentifié.")
