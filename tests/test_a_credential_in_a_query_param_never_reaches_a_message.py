"""Un identifiant passé en paramètre de requête ne ressort jamais dans un message.

Type: Test
Uses: ast
Depends on: src/, airflow/, tools/
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
`_probe_instagram` (`src/dashboard/views/credentials/_platform_meta.py:162`) passe le
jeton de l'application Meta partagée en **paramètre de requête** :

    requests.get(f'{META_GRAPH_BASE_URL}/{ig_user_id}',
                 params={'access_token': token, ...})

`requests` place ce paramètre dans l'URL préparée, et le message d'une `ConnectionError`
contient cette URL. Sa fonction appelante `_test_instagram:212` interpolait l'exception
BRUTE (`.format(err=e)`) et renvoyait le tout à `_render.py`, qui l'affiche par
`st.error` — **à l'artiste**.

Prouvé par exécution le 2026-09-18, sur un hôte volontairement invalide :

    le jeton apparaît dans str(e) ?   True
    avec type(e).__name__ ?           ConnectionError

C'est le jeton Meta de l'application partagée, **celui qui n'expire pas**, montré à un
non-admin sur une simple panne DNS. Sa fonction-sœur `_test_meta` porte ce correctif et
son motif depuis le début ; `_test_instagram` ne l'avait jamais reçu.

Le piège du prédicat, et c'est la moitié qui compte
----------------------------------------------------
Mon premier balayage a rendu **0 site vivant** — et il ratait celui-là. Il exigeait que
l'appel `requests` et le `except` vivent dans la MÊME fonction. Or ici la fonction qui
fuit ne contient aucun appel réseau : elle appelle `_probe_instagram`. Le prédicat
cherchait une FORME (« les deux dans la même fonction ») là où la propriété est
« l'exception a traversé un appel porteur d'identifiant ». Règle 20, dans le balayage
écrit pour l'attraper.

Ce garde suit donc **un niveau d'appel**, et le dit dans son nom.

Ce qu'il ne couvre PAS — à lire avant de s'y fier
---------------------------------------------------
* **deux niveaux d'appel ou plus** : `a()` appelle `b()` qui appelle `c()` porteuse ;
* un identifiant passé dans un **en-tête** plutôt qu'en paramètre — c'est la forme SÛRE
  (`AirflowTrigger` le fait), mais un jour un en-tête pourrait fuir autrement ;
* une exception **stockée puis ré-interpolée** ailleurs (`msg = str(e)` plus haut) ;
* le contenu réel du message : aucun prédicat ne sait si une `ValueError` maison porte
  un secret. On raisonne sur le CHEMIN, pas sur le texte.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ARBRES = ("src/**/*.py", "airflow/**/*.py", "tools/**/*.py")
_SECRETS = ("access_token", "api_key", "client_secret", "password", "secret", "token")


def _secret_en_params(appel: ast.Call) -> str | None:
    for k in appel.keywords:
        if k.arg != "params":
            continue
        if isinstance(k.value, ast.Dict):
            for cle in k.value.keys:
                if isinstance(cle, ast.Constant) and \
                        any(s in str(cle.value).lower() for s in _SECRETS):
                    return str(cle.value)
        else:
            # `params=une_variable` : on ne peut pas savoir, donc on suppose le pire.
            return "params=<variable>"
    return None


def _porteuses(arbre: ast.AST) -> dict:
    """{nom de fonction: le paramètre secret} pour les appels réseau DIRECTS."""
    out = {}
    for fn in ast.walk(arbre):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and "requests" in ast.unparse(n.func):
                s = _secret_en_params(n)
                if s:
                    out[fn.name] = s
    return out


def _fuites(chemin: Path) -> list:
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    locales = _porteuses(arbre)
    out = []
    for fn in ast.walk(arbre):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        secret, via = locales.get(fn.name), None
        if not secret:                       # ── LE niveau d'appel que je ratais ──
            for n in ast.walk(fn):
                if isinstance(n, ast.Call):
                    nom = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                    if nom in locales and nom != fn.name:
                        secret, via = locales[nom], nom
                        break
        if not secret:
            continue
        for h in ast.walk(fn):
            if not isinstance(h, ast.ExceptHandler) or not h.name:
                continue
            c = ast.unparse(h).replace(" ", "")
            brut = (f"format(err={h.name})" in c or f"format({h.name})" in c
                    or f"str({h.name})" in c or f"{{{h.name}}}" in c)
            protege = (f"type({h.name}).__name__" in c
                       or f"safe_error({h.name}" in c or f"redact({h.name}" in c)
            if brut and not protege:
                out.append((str(chemin.relative_to(ROOT)), fn.name, h.lineno,
                            secret, via or "direct"))
    return out


def _tous() -> list:
    out = []
    for motif in _ARBRES:
        for p in sorted(ROOT.glob(motif)):
            out += _fuites(p)
    return out


def test_no_exception_from_a_credential_bearing_call_is_interpolated_raw():
    fuites = _tous()
    assert not fuites, (
        "ces gestionnaires interpolent une exception BRUTE alors qu'elle a traversé un "
        f"appel portant un identifiant en paramètre de requête : {fuites}. Le message "
        "d'une `ConnectionError` contient l'URL préparée, chaîne de requête comprise — "
        "mesuré le 2026-09-18, le jeton y apparaît. Utiliser `type(e).__name__` ou "
        "`safe_error(e)`."
    )


def test_the_predicate_follows_one_call_level():
    """La preuve que ce fichier se donne : c'est CE niveau que mon balayage ratait.

    Un prédicat qui exige l'appel réseau et le `except` dans la même fonction rend 0 sur
    le défaut réel. On fabrique la forme exacte et on exige qu'elle soit vue.
    """
    import tempfile

    src = (
        "import requests\n"
        "def _probe(uid, token):\n"
        "    return requests.get(f'https://x/{uid}', params={'access_token': token})\n"
        "def _test(uid, token):\n"
        "    try:\n"
        "        return _probe(uid, token)\n"
        "    except Exception as e:\n"
        "        return False, 'reseau : {err}'.format(err=e)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ROOT, delete=False) as f:
        f.write(src)
        chemin = Path(f.name)
    try:
        vus = _fuites(chemin)
        assert vus and vus[0][1] == "_test" and vus[0][4] == "_probe", (
            f"le prédicat ne suit pas l'appel : {vus}. C'est exactement le faux négatif "
            "qui a fait rendre « 0 site vivant » à mon premier balayage, sur un défaut "
            "qui atteignait un artiste.")
    finally:
        chemin.unlink()


def test_the_predicate_accepts_the_corrected_form():
    """Et il ne mord PAS sur le correctif, sinon l'arbre serait rouge en permanence."""
    import tempfile

    src = (
        "import requests\n"
        "def _probe(uid, token):\n"
        "    return requests.get(f'https://x/{uid}', params={'access_token': token})\n"
        "def _test(uid, token):\n"
        "    try:\n"
        "        return _probe(uid, token)\n"
        "    except Exception as e:\n"
        "        return False, 'reseau ({err})'.format(err=type(e).__name__)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ROOT, delete=False) as f:
        f.write(src)
        chemin = Path(f.name)
    try:
        assert _fuites(chemin) == [], (
            "le prédicat mord sur `type(e).__name__` — le correctif même")
    finally:
        chemin.unlink()


def test_the_carrier_detector_is_not_vacuous():
    """S'il ne trouve aucune fonction porteuse, tout le fichier passe sur rien."""
    total = 0
    for motif in _ARBRES:
        for p in sorted(ROOT.glob(motif)):
            try:
                total += len(_porteuses(ast.parse(p.read_text(encoding="utf-8"))))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
    assert total >= 5, (
        f"seulement {total} fonction(s) passent un identifiant en paramètre de requête "
        "— le détecteur de porteuses est probablement cassé, et les tests ci-dessus ne "
        "gardent plus rien.")
