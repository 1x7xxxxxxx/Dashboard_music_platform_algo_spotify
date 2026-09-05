"""L'état du partage d'un compte publicitaire Meta, lu chez Meta.

Type: Utility
Uses: src.utils.meta_graph (la seule porte vers Graph), META_BUSINESS_ID
Depends on: un jeton System User portant `business_management`
Persists in: rien — lecture seule, mise en cache par l'appelant

Pourquoi ce module existe
-------------------------
Le 2026-09-05, un artiste a suivi la consigne « colle notre numéro dans
Attribuer un partenaire » sur un compte que **notre propre Business possède
déjà**. Meta retire du sélecteur le business propriétaire : le numéro était
donc introuvable, la consigne infaisable, et une installation qui marchait
paraissait cassée.

L'app affirmait « il faut partager » sans jamais regarder si le partage était
acquis. Les trois arêtes ci-dessous répondent à la question, et elles étaient
lisibles depuis le début.

`ADR-017` a fermé la moitié « envoyer la demande » (capacité d'app refusée par
Meta). Ceci est la moitié « constater », qui n'était pas fermée.
"""
from __future__ import annotations

import os
from typing import Literal

from src.utils.meta_graph import MetaGraphError, get

ShareState = Literal["owned", "accepted", "pending", "absent", "unknown"]

# `unknown` n'est PAS `absent`. Un plafond de quota ou une panne réseau ne
# prouvent aucune absence de partage, et affirmer « il faut partager » sur une
# lecture ratée reproduit exactement la classe `probe-reads-unreadable-as-absent`.
_EDGES: tuple[tuple[str, ShareState], ...] = (
    ("owned_ad_accounts", "owned"),
    ("client_ad_accounts", "accepted"),
    ("pending_client_ad_accounts", "pending"),
)


def _digits(account_id: str) -> str:
    """`act_567…`, `567…`, une URL entière : on ne garde que le numéro."""
    return "".join(c for c in (account_id or "") if c.isdigit())


def business_id() -> str:
    return os.getenv("META_BUSINESS_ID", "").strip()


def share_state(account_id: str, token: str | None = None) -> ShareState:
    """Où en est ce compte vis-à-vis de NOTRE business. Ne lève jamais.

    - `owned`    : nous le possédons — il n'y a rien à partager, jamais.
    - `accepted` : le partage est en place.
    - `pending`  : la demande attend l'acceptation de l'artiste.
    - `absent`   : lu chez Meta, et le compte n'est sur aucune des trois arêtes.
    - `unknown`  : la lecture a échoué — on n'affirme rien.
    """
    wanted = _digits(account_id)
    bid = business_id()
    if not wanted or not bid:
        return "unknown"

    for edge, state in _EDGES:
        try:
            payload = get(f"{bid}/{edge}", token=token, fields="account_id", limit=200)
        except MetaGraphError:
            return "unknown"
        except Exception:  # noqa: BLE001 — une lecture ratée n'est pas une absence
            return "unknown"
        for row in payload.get("data", []):
            if _digits(str(row.get("account_id") or row.get("id") or "")) == wanted:
                return state
    return "absent"
