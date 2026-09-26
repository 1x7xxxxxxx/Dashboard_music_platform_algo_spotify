#!/usr/bin/env python3
"""
Send a schema-drift alert email via the Brevo SMTP credentials in `.env`.

Standalone mirror of `src/utils/email_alerts.EmailAlert.send_alert` — the ops cron
script (`schema_drift_cron.sh`) calls this on drift WITHOUT importing the app package,
so a broken app import path can never silence the alert. Reads SMTP_HOST/PORT/USER/
PASSWORD (+ ALERT_EMAIL) straight from the repo `.env`. Body on stdin.

Type: Utility
Uses: smtplib, repo-root .env (SMTP_* + ALERT_EMAIL)
Triggers: schema_drift_cron.sh (on drift)
Persists in: — (sends email; prints status to stdout/stderr)

Exit: 0 sent · 1 not-configured or send failure (caller logs the message).
"""
import argparse
import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from pathlib import Path

# This script is the LAST link of the drift alert, and it states below that it must not
# depend on the app package — "a broken import path must never be able to silence the
# alert". That invariant proved itself on 2026-08-23: adding the redaction import
# unconditionally made the nightly cron die at startup, alert and all.
# So: put the repo root on the path (Python seeds sys.path with this script's directory,
# never the caller's cwd), and keep the import survivable. The fallback drops the
# message rather than reproducing the redaction rules here — a copy of them would drift,
# and a type name alone cannot leak a credential.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ⚠️ Conditionnel, comme les trois shims ci-dessous. Cette ligne était NUE jusqu'au
# 2026-09-18 : dix lignes sous la prose qui affirme qu'un import cassé ne peut jamais
# faire taire l'alerte, un `src/` cassé tuait le script ICI, avant qu'aucun repli ne
# s'exécute. L'invariant était énoncé et faux dans le même fichier. Le repli est
# `_load_env(root)`, plus bas — il fait déjà exactement ce travail.
try:
    from src.utils.env_files import load_project_env  # noqa: E402 — après le sys.path
except ImportError:  # pragma: no cover — couvert par test_the_alert_survives_a_broken_repo
    load_project_env = None  # type: ignore[assignment]

# Même omission que `create_sandbox.py`, trouvée par le même balayage (2026-09-05) et
# plus exposée : cet outil est le cron de dérive de schéma qui s'auto-notifie par
# Brevo, et il lit SIX variables SMTP. Il fonctionne aujourd'hui parce que le cron de
# prod exporte l'environnement lui-même — c'est-à-dire pour une raison qui vit
# ailleurs que dans ce fichier, et qu'une réécriture du cron peut retirer sans le
# savoir. Un outil qui a besoin de l'environnement le charge.
if load_project_env is not None:
    load_project_env()
else:
    _ENV_BOOTSTRAP = Path(__file__).resolve().parents[1]
    for _f in (".env.local", ".env"):
        _p = _ENV_BOOTSTRAP / _f
        if _p.exists():
            for _line in _p.read_text(encoding="utf-8").splitlines():
                if "=" in _line and not _line.lstrip().startswith("#"):
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"\''))

try:
    from src.utils.safe_error import safe_error  # noqa: E402 — needs the path line above
except ImportError:  # pragma: no cover — couvert par test_the_alert_survives_a_broken_repo
    def safe_error(exc: BaseException, limit: int = 300) -> str:
        return type(exc).__name__

# Les deux mêmes shims, pour la même raison, et parce que ce fichier composait son
# identité d'expéditeur LUI-MÊME. `src/utils/email_identity.py:55` dit « le seul
# endroit qui la compose » ; ici `msg["From"] = os.getenv("SMTP_FROM") or user` posait
# l'identifiant du relais SANS nom d'affichage — en production Brevo y substitue
# l'expéditeur par défaut du compte, ce qui est exactement l'incident que ce module a
# été écrit pour clore. Le sujet, lui, ne disait pas de quelle instance il venait.
# Le repli garde l'invariant du fichier : un import cassé ne doit JAMAIS faire taire
# l'alerte — il rend alors l'ancienne composition, pas une exception.
try:
    from src.utils.email_identity import from_header  # noqa: E402
except ImportError:  # pragma: no cover — couvert par test_the_alert_survives_a_broken_repo
    # ⚠️ Le repli rend une chaîne VIDE, et c'est délibéré. Il a d'abord rendu
    # `os.getenv("SMTP_USER")` — le login du relais sans nom d'affichage, c'est-à-dire
    # le défaut LITTÉRAL que `src/utils/email_identity.py` a été écrit pour supprimer.
    # Un repli qui compose est une seconde composition, quelle que soit sa motivation,
    # et `test_the_from_header_is_never_composed_locally` a rougi dessus le jour même.
    # Vide ⇒ on ne pose PAS l'en-tête et on donne l'expéditeur d'ENVELOPPE à smtplib :
    # `user` y est légitime, c'est le compte authentifié, pas une identité affichée.
    def from_header() -> str:
        return ""

try:
    from src.utils.instance_identity import instance_label  # noqa: E402
except ImportError:  # pragma: no cover
    def instance_label() -> str:
        return ""


# Same order, and for the same reason, as `src.utils.env_files.ENV_FILES`: the local
# file wins. This script deliberately does not import the app package (a broken import
# path must never be able to silence the alert), so the order is restated rather than
# shared — and restated order drifts, which is why the test names both.
_ENV_FILES = (".env.local", ".env")


def _load_env(root: Path) -> None:
    """Populate os.environ from the root env files — first seen wins, like the app.

    Read `.env` only, this loader answered from a file the dashboard and the DAGs do
    not use last: on 2026-08-22 the two disagreed about the Meta app for weeks and
    `.env.local` was the one that counted.
    """
    for name in _ENV_FILES:
        f = root / name
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Email a schema-drift alert via Brevo SMTP")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--to", default=None, help="recipient (défaut : $ALERT_EMAIL ; aucun autre repli)")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    _load_env(root)

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    # Pas de repli sur `SMTP_FROM`. Il a vécu ici jusqu'au 2026-09-18 et il divergeait
    # du chemin principal : `email_alerts.py:93` REFUSE d'émettre quand `ALERT_EMAIL`
    # manque, alors qu'ici la même instance envoyait à l'adresse d'EXPÉDITION. Une
    # alerte adressée à l'expéditeur est une alerte que personne ne lit — elle compte
    # comme livrée et n'arrive nulle part. Absent ⇒ le `if not all(...)` ci-dessous
    # rend 1 et l'appelant journalise, exactement comme le chemin principal.
    recipient = args.to or os.getenv("ALERT_EMAIL")
    body = sys.stdin.read().strip() or "(no body)"

    if not all([host, user, password, recipient]):
        print("email not configured (SMTP_USER/SMTP_PASSWORD/recipient missing) — "
              "drift is logged only", file=sys.stderr)
        return 1

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"{instance_label()}{args.subject}"
    expediteur = from_header()
    if expediteur:
        msg["From"] = expediteur
    msg["To"] = recipient

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, password)
            # `from_addr=` explicite quand l'en-tête manque : sans lui,
            # `send_message` va CHERCHER `msg["From"]` et lève sur son absence.
            if expediteur:
                server.send_message(msg)
            else:
                server.send_message(msg, from_addr=user)
    except (smtplib.SMTPException, OSError) as exc:
        print(f"email send failed: {safe_error(exc)}", file=sys.stderr)
        return 1
    print(f"drift alert emailed to {recipient}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
