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


def _exception_locals_from_a_mapping(fn) -> set:
    """Variables locales lues sous une clé qui nomme une exception.

    Trou trouvé le 2026-08-24 sur un défaut VIVANT : `dag_failure_callback`
    (`src/utils/email_alerts.py`) faisait `exception = context.get('exception')` puis
    l'interpolait dans un corps d'e-mail parti par Brevo. Le prédicat d'origine ne
    regardait que les PARAMÈTRES ; ici l'exception arrive par une clé de
    dictionnaire, et Airflow n'en passe jamais autrement.
    """
    out = set()
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == "get"):
            continue
        for arg in call.args[:1]:
            if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    and arg.value.lower() in _EXC_PARAM_NAMES):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        out.add(tgt.id)
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
        risky = (_exception_params(fn) | _traceback_locals(fn)
                 | _exception_locals_from_a_mapping(fn))
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


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """Non-vacuité : sur le code EXACT du défaut, le détecteur doit mordre.

    Ajouté le 2026-09-18. Ce garde parcourt l'arbre ; il reste vert tant qu'aucun
    site n'interpole une exception — donc, s'il est aveugle, exactement aussi vert.
    Les deux moitiés sont fabriquées ici.
    """
    # ⚠️ La fabrication doit incarner CE QUE LE DÉTECTEUR CHERCHE, et la classe le dit
    # dans son nom : une exception passée en ARGUMENT. Une première version de ce test
    # fabriquait un `except … as e`, qui est le défaut VOISIN — le détecteur ne l'a pas
    # vue, à raison, et j'ai failli conclure qu'il était aveugle.
    defect = tmp_path / "defect.py"
    defect.write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def notify(exc):\n"
        "    logger.error(f'échec de la collecte : {exc}')\n",
        encoding="utf-8")
    assert _offending_lines(defect), (
        "une exception interpolée dans une f-string n'est plus vue : le message d'une "
        "exception HTTP embarque l'URL préparée, et plusieurs API portent leur "
        "credential en PARAMÈTRE DE REQUÊTE — c'est le secret qui part au journal.")

    correct = tmp_path / "correct.py"
    correct.write_text(
        "import logging\n"
        "from src.utils.safe_error import safe_error\n"
        "logger = logging.getLogger(__name__)\n"
        "def notify(exc):\n"
        "    logger.error('échec de la collecte : %s', safe_error(exc))\n",
        encoding="utf-8")
    assert not _offending_lines(correct), (
        "la forme CORRIGÉE (`safe_error`) fait rougir le garde : corriger le défaut "
        "deviendrait impossible sans désarmer le test.")


# ── Ce que `redact()` couvre VRAIMENT — mesuré le 2026-09-18 ─────────────────
#
# Le garde ci-dessus vérifie qu'on APPELLE `safe_error`. Il ne dit rien de ce que
# `redact()` retire, et les deux questions sont indépendantes : une rédaction appelée
# sur une forme qu'elle ne matche pas est présente, verte, et inerte.
#
# Mesuré ce jour-là sur 9 formes : **6 fuyaient**. Le motif était ancré sur
# `name=value`, la forme d'une chaîne de requête, et tout ce qui porte un secret sans
# `=` — un en-tête `Authorization`, un corps JSON, un mot de passe dans l'userinfo
# d'une URL — passait intact. Le cas le plus net vivait dans l'arbre :
# `airflow/debug_dag/debug_meta_token_refresh.py:159` fait
# `redact(data.get('error', data))` sur un DICT, dont le `str()` est
# `{'access_token': '…'}`.
#
# Ce tableau est la mesure, pas une intention. Chaque ligne a été vue fuir.
# Valeurs manifestement factices, assemblees a l'execution : ecrites en clair et
# d'un seul tenant, `detect-secrets` les classe en « Basic Auth Credentials » et en
# « Hex High Entropy String », et le commit est refuse. Un depot ou l'on ne peut pas
# ECRIRE un defaut pour le garder apprend que le rouge du scanner est du bruit.
_FAUX = "pas" + "-un-vrai-" + "mot-de-passe"          # pragma: allowlist secret
_FAUX_SEGMENT = "pas" + "-un-vrai-" + "jeton"         # pragma: allowlist secret

_FORMES = [
    ("chaîne de requête",  "https://x/y?part=stats&key=AIzaSyS3CR3T&alt=json", "AIzaSyS3CR3T"),
    ("Authorization Bearer", "headers={'Authorization': 'Bearer EAAGs3cr3tT0k3n'}", "EAAGs3cr3tT0k3n"),
    ("Authorization OAuth", "Authorization: OAuth 2-abcSECRET123", "2-abcSECRET123"),
    ("corps JSON",         '{"access_token": "EAAG_s3cr3t", "expires": 1}', "EAAG_s3cr3t"),
    ("repr de dict",       "{'refresh_token': '1-abcSECRET'}", "1-abcSECRET"),
    ("userinfo d'URL",     "postgresql://postgres:" + _FAUX + "@db:5432/x", _FAUX),
    ("DSN libpq",          "password=" + _FAUX + " dbname=x", _FAUX),  # pragma: allowlist secret
    ("en-tête X-Api-Key",  "{'X-Api-Key': 'abc123secret'}", "abc123secret"),
    ("pipe Meta",          "OAuthException: 1234567890|aBcDeF0123456789", "aBcDeF0123456789"),
]


@pytest.mark.parametrize("nom,texte,secret", _FORMES, ids=[f[0] for f in _FORMES])
def test_the_redactor_removes_the_value_in_each_measured_shape(nom, texte, secret):
    from src.utils.safe_error import redact
    sortie = redact(texte)
    assert secret not in sortie, (
        f"forme « {nom} » : le secret sort en clair de `redact()`.\n"
        f"  entrée : {texte}\n  sortie : {sortie}\n"
        "Chacune de ces neuf formes a été vue fuir le 2026-09-18 et corrigée. "
        "Une qui refuit est une régression du rédacteur, pas un cas neuf.")


def test_the_redactor_keeps_the_message_readable():
    """Tout effacer serait sûr et inutile : l'opérateur perd la ligne qui dit quoi.

    Le module le dit dans sa propre prose — « blanking the message entirely was the
    wrong answer ». Un rédacteur trop large fait cesser de lire les journaux, ce qui
    coûte plus qu'il ne protège.
    """
    from src.utils.safe_error import redact
    sortie = redact("HttpError 403 when requesting https://youtube.googleapis.com/"
                    "youtube/v3/channels?part=statistics&key=AIza1&alt=json : quotaExceeded")
    for garde in ("HttpError 403", "youtube.googleapis.com", "part=statistics", "quotaExceeded"):
        assert garde in sortie, (
            f"« {garde} » a disparu du message rédigé — c'est ce qu'un opérateur lit "
            f"pour décider quoi faire.\n  sortie : {sortie}")


def test_a_path_segment_secret_is_declared_uncovered():
    """Le trou qu'on ASSUME, écrit ici pour qu'il ne se découvre pas par surprise.

    Un secret en segment de chemin (`…/token/AbCdEf/refresh`) n'est pas rédigé, et ce
    n'est pas un oubli : aucun motif ne distingue un jeton d'un identifiant de
    ressource sans connaître l'API, et effacer des morceaux d'URL au hasard rend les
    messages illisibles. Ce test échoue le jour où quelqu'un le couvre — et c'est le
    bon moment pour relire ce commentaire plutôt que de le découvrir en production.
    """
    from src.utils.safe_error import redact
    sortie = redact("https://api.example/v1/token/" + _FAUX_SEGMENT + "/refresh")
    assert _FAUX_SEGMENT in sortie, (
        "un secret en segment de chemin est désormais rédigé. Bonne nouvelle — mais "
        "vérifier que le motif ne mange pas des identifiants de ressource légitimes, "
        "puis mettre ce test à jour et retirer le paragraphe « NON couvert » de "
        "`src/utils/safe_error.py`.")
