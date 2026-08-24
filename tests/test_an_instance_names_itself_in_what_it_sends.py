"""Une instance qui n'est pas la production le dit dans ce qu'elle envoie.

Classe `a-dev-instance-sends-production-shaped-mail`.

Le 2026-08-24, le scheduler Airflow **local** a rejoué un run planifié, a échoué sur
le credential SoundCloud partagé — que la production venait de faire tourner 28
minutes plus tôt, SoundCloud faisant tourner ses `refresh_token` — et a envoyé deux
alertes à une vraie boîte mail. Au premier coup d'œil, elles étaient indiscernables
d'une panne de production ; seuls l'expéditeur et un lien `localhost` les
distinguaient. La production, elle, allait parfaitement bien.

C'est la suite directe de l'incident du 2026-08-23, où la SUITE DE TESTS envoyait de
vrais mails de vérification. La frontière posée alors borne les tests. **Un Airflow
qui tourne en local a exactement le même rayon de souffle, et rien ne le bornait.**

Deux invariants, et le second est celui qui a déjà coûté :

1. Chaque chemin d'envoi préfixe son sujet par `instance_label()` — vide en
   production, `[LOCAL] ` ailleurs.
2. **TOUS** les chemins, pas ceux qu'on a regardés. Ce dépôt a payé une fois d'avoir
   corrigé le chemin qui marchait en laissant l'autre (R38, le nom d'expéditeur) :
   le garde énumère donc les sites par AST et échoue sur celui qu'on a oublié.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_SENDERS = ("src/utils/email_alerts.py", "src/utils/verification_email.py")


def _subject_assignments(path: pathlib.Path) -> list:
    """Les affectations `msg['Subject'] = …`, avec leur ligne et leur valeur."""
    out = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "Subject"):
                out.append((node.lineno, node.value))
    return out


def _mentions_label(value) -> bool:
    """`instance_label()` apparaît-il dans l'expression du sujet ?"""
    for node in ast.walk(value):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "instance_label"):
            return True
    return False


@pytest.mark.parametrize("rel", _SENDERS, ids=_SENDERS)
def test_every_send_path_names_its_instance(rel: str):
    path = ROOT / rel
    subjects = _subject_assignments(path)
    assert subjects, f"aucun `msg['Subject']` trouvé dans {rel} — garde périmé ?"
    unlabelled = [ln for ln, val in subjects if not _mentions_label(val)]
    assert not unlabelled, (
        f"{rel} compose un sujet sans `instance_label()` aux lignes {unlabelled}. "
        "Une alerte envoyée depuis un poste de dev doit se distinguer d'une panne "
        "de production — et il y a QUATRE chemins d'envoi dans ce dépôt."
    )


def test_the_label_is_empty_in_production_and_visible_elsewhere(monkeypatch):
    from src.utils.instance_identity import instance_label, is_production

    monkeypatch.setenv("STREAMLYTICS_ENV", "production")
    assert is_production() and instance_label() == "", (
        "en production le préfixe doit être VIDE : c'est son absence qui veut dire "
        "« ceci est réel », un « [PRODUCTION] » partout finirait ignoré"
    )

    monkeypatch.delenv("STREAMLYTICS_ENV", raising=False)
    assert instance_label() == "[LOCAL] ", "hors production, l'instance doit se nommer"

    monkeypatch.setenv("STREAMLYTICS_ENV", "staging")
    assert instance_label() == "[STAGING] "


def test_the_env_is_read_at_call_time(monkeypatch):
    """Figée à l'import, la valeur serait celle du premier import — défaut R38/APP_BASE_URL."""
    from src.utils.instance_identity import instance_env

    monkeypatch.setenv("STREAMLYTICS_ENV", "production")
    assert instance_env() == "production"
    monkeypatch.setenv("STREAMLYTICS_ENV", "local")
    assert instance_env() == "local", "la valeur est mise en cache — elle ne doit pas l'être"


def test_no_mail_body_hardcodes_a_localhost_airflow_url():
    """`localhost` dans un mail est un lien mort pour le destinataire."""
    offenders = []
    for sub in ("src", "airflow"):
        for path in sorted((ROOT / sub).rglob("*.py")):
            if "__pycache__" in str(path) or path.name == "instance_identity.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "localhost:8080" not in text:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if "localhost:8080" not in line:
                    continue
                # Un repli lu depuis l'environnement est légitime ; un littéral
                # posé dans du HTML ne l'est pas.
                if "getenv" in line or "get(" in line or "base_url:" in line:
                    continue
                if "<a href" in line or "href=" in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not offenders, (
        f"URL Airflow `localhost` écrite en dur dans un corps d'e-mail : {offenders}. "
        "Utiliser `instance_identity.airflow_base_url()`, lu à l'appel."
    )
