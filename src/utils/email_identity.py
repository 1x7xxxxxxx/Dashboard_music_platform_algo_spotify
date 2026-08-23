"""Who our mail says it is from — one place, because two places drifted.

Type: Utility
Uses: os (stdlib only — must be importable from DAGs, views and collectors)
Triggers: every outbound email
Persists in: nothing

R38, mesuré le 2026-08-23. Deux chemins d'envoi coexistaient et ne composaient pas le
même en-tête `From` :

* `verification_email.py` : `f"{from_name} <{from_email}>"` — correct.
* `email_alerts.py` : **`self.smtp_user`** — l'identifiant de connexion au relais, sans
  nom d'affichage et sur le mauvais domaine.

En production `SMTP_USER` vaut `ae8df8001@smtp-brevo.com` et `SMTP_FROM` vaut
`noreply@streamlytics.fr`. Toutes les alertes de DAG, le résumé quotidien et le rapport
d'onboarding partaient donc en annonçant le compte de relais. Brevo, qui exige un
expéditeur validé, y substitue l'expéditeur par défaut du compte — **c'est de là que
venait « Music Cross Platform Dashboard & Trigger Spotify »**, et non d'un réglage
qu'aucune ligne de Python ne pourrait corriger, comme la roadmap le supposait.

La supposition tenait parce que personne n'avait lu les DEUX chemins : celui qu'on
regardait était le bon.
"""
from __future__ import annotations

import os

DEFAULT_FROM_NAME = "streaMLytics"


def sender_identity() -> tuple[str, str]:
    """`(nom affiché, adresse)`. L'environnement gagne, `config.yaml` complète.

    L'adresse d'expédition n'est PAS l'identifiant SMTP : chez un relais (Brevo,
    Mailgun…) le login est un compte technique, et le `From` doit porter l'adresse du
    domaine authentifié pour que SPF/DKIM s'alignent. On ne retombe sur le login que
    faute de mieux — c'est un pis-aller, pas le cas nominal.
    """
    env = os.environ
    cfg: dict = {}
    try:                                    # absent des conteneurs Airflow, et c'est normal
        from src.utils.config_loader import config_loader
        cfg = config_loader.load().get("smtp", {}) or {}
    except Exception:                       # noqa: BLE001 — l'absence de config n'est pas une panne
        cfg = {}

    name = env.get("SMTP_FROM_NAME") or cfg.get("from_name") or DEFAULT_FROM_NAME
    email = (env.get("SMTP_FROM") or cfg.get("from_email")
             or env.get("SMTP_USER") or cfg.get("user") or "")
    return name, email


def from_header() -> str:
    """La valeur à poser dans `msg['From']`, et le seul endroit qui la compose."""
    name, email = sender_identity()
    return f"{name} <{email}>" if email else name
