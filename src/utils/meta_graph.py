"""The one place that talks to the Meta Graph API.

Type: Utility
Uses: requests, meta_config
Triggers: central_apps, credentials probes, meta_partner
Depends on: META_GRAPH_BASE_URL (version), META_ACCESS_TOKEN
Persists in: nothing

`meta_config` says, in its own docstring, « Update META_API_VERSION here — no other
file needs to change ». That was false: `central_apps.check_meta` wrote
`https://graph.facebook.com/v21.0/` twice, in the two calls that decide whether the
platform app is alive. The constant moved to `v24.0` and the health check stayed three
versions behind, for months, because nothing tied the two writings together.

So the version is not the point — the DUPLICATION is. This module owns the base URL,
the token resolution and the error vocabulary; `test_meta_graph_is_the_only_door.py`
refuses a hardcoded `graph.facebook.com` anywhere else under `src/`.

Not for the collectors: they use the `facebook_business` SDK for insight pagination,
which is another job. This client covers control and configuration calls.
"""
from __future__ import annotations

import logging
import os

import requests

from src.utils.meta_config import META_GRAPH_BASE_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 20

# Ce que Meta répond, dit une fois. Chaque site d'appel réinterprétait ces codes —
# d'où des messages qui nommaient la classe d'exception sans jamais nommer la cause
# (classe `alert-names-the-class-and-drops-the-reason`, 2026-09-03).
_EXPLANATIONS = {
    3: ("L'application n'a pas la capacité de faire cet appel. Ce n'est ni le jeton "
        "ni ses permissions : c'est un accès à demander à Meta pour l'app."),
    10: ("L'application n'a pas la permission requise pour cet appel."),
    100: ("Paramètre invalide ou champ inexistant sur cet objet."),
    190: ("Le jeton est invalide ou a expiré. Il est géré par l'administrateur — "
          "il n'y a rien à corriger côté artiste."),
    200: ("Permission insuffisante sur cet objet : il n'a probablement pas été "
          "partagé avec nous."),
    294: ("Une gestion de page est requise pour cet appel."),
    803: ("Cet objet n'existe pas, ou n'est pas visible avec ce jeton."),
}


class MetaGraphError(RuntimeError):
    """Une réponse d'erreur de Graph, avec de quoi décider quoi en dire."""

    def __init__(self, code, subcode, message: str):
        self.code = code
        self.subcode = subcode
        self.message = message
        super().__init__(f"({code}) {message}")

    @property
    def explanation(self) -> str:
        """La cause, en français, ou le message brut si le code est inconnu."""
        return _EXPLANATIONS.get(self.code, self.message)

    @property
    def is_capability(self) -> bool:
        """L'app n'a pas le droit — inutile de réessayer, de retester ou d'alerter.

        Mesuré le 2026-09-05 : `POST business/client_ad_accounts` et
        `POST adaccount/agencies` répondent tous deux `(#3)` avec un jeton portant
        pourtant `business_management`, et pendant qu'une écriture Business ordinaire
        passe. Ce n'est donc pas une panne : c'est une porte fermée.
        """
        return self.code == 3


def resolve_token(token: str | None = None) -> str:
    """Le jeton, résolu UNE fois. Vide ⇒ on le dit, on ne part pas en appel."""
    resolved = (token or os.getenv("META_ACCESS_TOKEN") or "").strip()
    if not resolved:
        raise MetaGraphError(None, None, "META_ACCESS_TOKEN absent")
    return resolved


def _call(method: str, path: str, token: str | None, payload: dict) -> dict:
    url = f"{META_GRAPH_BASE_URL}/{path.lstrip('/')}"
    payload = {k: v for k, v in payload.items() if v is not None}
    payload["access_token"] = resolve_token(token)
    try:
        if method == "GET":
            r = requests.get(url, params=payload, timeout=_TIMEOUT)
        else:
            # POST : le jeton passe dans le CORPS, pas dans l'URL. C'est aussi la
            # raison de ne pas le mettre en paramètre de requête ici.
            r = requests.post(url, data=payload, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        # Le message d'une exception réseau contient l'URL préparée — donc le jeton
        # sur un GET. Seul le NOM de la classe sort.
        raise MetaGraphError(None, None,
                             f"erreur réseau ({type(exc).__name__})") from None
    try:
        body = r.json()
    except ValueError:
        # JAMAIS `r.text` ni `str(exc)`. Le jeton voyage en QUERY STRING : le corps
        # d'une erreur et le message d'une exception réseau embarquent l'URL préparée,
        # donc le jeton System User de la flotte. Gardé par
        # `test_no_probe_surfaces_a_whole_exception`. Ici on ne rend que le statut.
        raise MetaGraphError(r.status_code, None,
                             f"réponse non-JSON (HTTP {r.status_code})") from None
    if isinstance(body, dict) and "error" in body:
        err = body["error"]
        raise MetaGraphError(err.get("code"), err.get("error_subcode"),
                             err.get("message", ""))
    return body


def get(path: str, token: str | None = None, **params) -> dict:
    """Un GET Graph. Lève `MetaGraphError` — jamais un dict d'erreur déguisé."""
    return _call("GET", path, token, params)


def post(path: str, token: str | None = None, **data) -> dict:
    """Un POST Graph. Lève `MetaGraphError`."""
    return _call("POST", path, token, data)
