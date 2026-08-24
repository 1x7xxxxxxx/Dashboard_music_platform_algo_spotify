"""Une exception REÇUE en paramètre est une exception dont on ignore l'origine.

Classe `leak-via-an-exception-received-as-an-argument`, trouvée le 2026-08-24.

Le garde anti-fuite existant (`test_credentials_security.py::test_no_probe_surfaces_a_whole_exception`)
demande : « une exception née d'un appel HTTP peut-elle atteindre ce module ? », et
répond en suivant le **graphe d'imports**. C'est la bonne question pour une
exception CAPTURÉE sur place. Elle est aveugle à celle qu'on reçoit en ARGUMENT :

    def _maybe_email(page: str, exc: BaseException) -> None:
        html = f"<p>{exc}</p><pre>{traceback.format_exception(...)}</pre>"

`error_alert.py` n'importe aucun client HTTP et n'en est importé par aucun — il est
donc hors de la portée du garde — et il envoyait la traceback complète **par
Brevo**, un tiers, dans une boîte mail. Le message d'une exception `requests`
embarque l'URL préparée : `access_token=…`, `key=…`.

Septième fois que la portée d'un garde est le défaut, et la première où l'élargir
au graphe d'imports n'aurait rien donné — l'appel passe par un argument, qui ne
laisse aucune trace dans ce graphe. Le prédicat ci-dessous épouse la question :
*est-ce que cette fonction met dans une chaîne une exception qu'elle n'a pas
attrapée ?*
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_DIRS = ("src", "airflow", "tools")

# Noms conventionnels d'un paramètre portant une exception. L'annotation est
# vérifiée en plus, pour les paramètres nommés autrement.
_EXC_PARAM_NAMES = {"exc", "error", "err", "e", "exception"}

# Les seuls emballages qui rendent l'interpolation sûre.
_SAFE_WRAPPERS = {"redact", "safe_error", "public_error_ref", "type"}


def _exception_params(fn) -> set:
    params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    out = {p for p in params if p in _EXC_PARAM_NAMES}
    for a in fn.args.args + fn.args.kwonlyargs:
        if a.annotation is not None and "xception" in ast.dump(a.annotation):
            out.add(a.arg)
    return out


def _traceback_locals(fn) -> set:
    """Variables locales issues d'un `traceback.format_*` — le pire des deux."""
    out = set()
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        # Une variable déjà emballée n'est plus risquée. Sans ce test, `tb =
        # redact(''.join(traceback.format_exception(...)))` reste signalé : le dump
        # de l'appel EXTÉRIEUR contient toujours le mot `traceback`, et le garde
        # déclarerait en faute le code qui applique justement le correctif.
        if (isinstance(call.func, ast.Name) and call.func.id in _SAFE_WRAPPERS):
            continue
        # `''.join(traceback.format_exception(...))` : on descend d'un cran.
        flat = ast.dump(call)
        if "traceback" in flat and "format_" in flat:
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
    return out


def _offending_lines(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        risky = _exception_params(fn) | _traceback_locals(fn)
        if not risky:
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.FormattedValue):
                continue
            value = node.value
            if isinstance(value, ast.Name) and value.id in risky:
                bad.append((fn.name, node.lineno))
            elif (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                  and value.func.id not in _SAFE_WRAPPERS):
                for arg in value.args:
                    if isinstance(arg, ast.Name) and arg.id in risky:
                        bad.append((fn.name, node.lineno))
    return bad


def _python_files() -> list:
    out = []
    for sub in _DIRS:
        for path in sorted((ROOT / sub).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            out.append(path.relative_to(ROOT).as_posix())
    return out


_FILES = _python_files()


def test_the_scope_is_not_empty():
    """Un garde dont la portée s'est vidée passe au vert sans rien regarder."""
    assert len(_FILES) > 100, f"portée suspecte : {len(_FILES)} fichiers"


@pytest.mark.parametrize("rel", _FILES, ids=_FILES)
def test_a_received_exception_is_never_interpolated_raw(rel: str):
    lines = _offending_lines(ROOT / rel)
    assert not lines, (
        f"{rel} met dans une chaîne une exception (ou une traceback) qu'il n'a pas "
        f"attrapée : {lines}. L'appelant peut l'avoir prise sur un appel HTTP dont "
        "le message porte le credential. Emballer dans `redact(...)` "
        "(`src/utils/safe_error.py`)."
    )
