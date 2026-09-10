"""Décorateur de retry avec backoff exponentiel pour les erreurs réseau/DB."""
import time
import logging
import functools
from typing import Tuple, Type

import psycopg2
from src.utils.safe_error import safe_error

logger = logging.getLogger(__name__)

# Exceptions qui méritent un retry (réseau / connexion transitoire)
#
# `TimeoutError` (alias de `socket.timeout` depuis Python 3.10) est ici pour une
# raison mesurée le 2026-09-03 : le collecteur YouTube n'utilise pas `requests` mais
# `googleapiclient`, donc `httplib2`, qui lève `socket.timeout` — ni
# `requests.exceptions.Timeout`, ni `ConnectionError`. Ses cinq méthodes portaient
# `@retry` depuis toujours **sans qu'aucune tentative ne soit jamais rejouée** : un
# blip réseau faisait échouer la tâche du premier coup, là où chaque autre
# collecteur en rejoue trois.
#
# Volontairement `TimeoutError` et pas `OSError` : ce dernier couvre aussi
# `FileNotFoundError` et `PermissionError`, qu'il ne faut surtout pas rejouer —
# elles ne deviennent pas vraies en attendant.
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    psycopg2.OperationalError,
    TimeoutError,
)

# Importation optionnelle de requests (pas toujours installé dans le contexte Airflow)
try:
    import requests
    RETRIABLE_EXCEPTIONS = RETRIABLE_EXCEPTIONS + (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    )
except ImportError:
    pass


def retry(max_attempts: int = 3, backoff: str = "exponential", base_delay: float = 2.0):
    """
    Décorateur de retry avec backoff.

    Args:
        max_attempts: Nombre maximum de tentatives (défaut 3).
        backoff: Stratégie de délai — 'exponential' (2^n * base_delay) ou 'linear' (n * base_delay).
        base_delay: Délai de base en secondes (défaut 2.0).

    Les exceptions ValueError, KeyError, TypeError (erreurs de données) ne déclenchent PAS de retry.
    """
    NON_RETRIABLE = (ValueError, KeyError, TypeError, AttributeError)

    def _http_verdict(exc):
        """(rejouable ?, délai imposé par le serveur) — ou (None, None) si pas du HTTP.

        UN 401 NE REDEVIENDRA JAMAIS VRAI. Un credential révoqué, un compte publicitaire
        retiré, une ressource supprimée : la branche `except Exception` finale rejouait
        tout, donc trois tentatives et six secondes d'attente par appel, pour échouer
        quand même. `NON_RETRIABLE` ne couvre que les erreurs de données Python et ne
        pouvait pas l'attraper.

        ET LE SERVEUR SAIT MIEUX QUE NOUS. Sur 429, notre recul est fixe (2 s, 4 s)
        pendant que Spotify et Meta annoncent des fenêtres de plusieurs minutes à
        plusieurs heures dans `Retry-After` — que SoundCloud lit déjà, et n'utilise pas.
        Les trois tentatives sont alors garanties de rater.
        """
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
        if status is None:
            status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if not isinstance(status, int):
            return None, None
        after = None
        try:
            raw = (resp.headers or {}).get("Retry-After") if resp is not None else None
            if raw is not None:
                after = float(str(raw).strip())
        except (TypeError, ValueError, AttributeError):
            after = None
        if status == 429 or status >= 500:
            return True, after
        if 400 <= status < 500:
            return False, None
        return None, None

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except NON_RETRIABLE:
                    # Erreur de données : pas de retry
                    raise
                except RETRIABLE_EXCEPTIONS as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    if backoff == "exponential":
                        delay = (2 ** (attempt - 1)) * base_delay
                    else:
                        delay = attempt * base_delay
                    logger.warning(
                        f"⚠️ {func.__qualname__} — tentative {attempt}/{max_attempts} échouée "
                        f"({type(exc).__name__}: {safe_error(exc)}). Retry dans {delay:.1f}s."
                    )
                    time.sleep(delay)
                except Exception as exc:
                    last_exc = exc
                    retriable, server_delay = _http_verdict(exc)
                    if retriable is False:
                        logger.warning(
                            "⚠️ %s — refus définitif du serveur (%s) : aucune reprise, "
                            "réessayer ne changera rien.",
                            func.__qualname__, type(exc).__name__)
                        raise
                    if attempt == max_attempts:
                        break
                    if backoff == "exponential":
                        delay = (2 ** (attempt - 1)) * base_delay
                    else:
                        delay = attempt * base_delay
                    if server_delay is not None:
                        # Le serveur a DIT combien attendre : on l'écoute, sans jamais
                        # descendre en dessous de notre propre recul.
                        delay = max(delay, server_delay)
                    logger.warning(
                        f"⚠️ {func.__qualname__} — tentative {attempt}/{max_attempts} échouée "
                        f"({type(exc).__name__}: {safe_error(exc)}). Retry dans {delay:.1f}s."
                    )
                    time.sleep(delay)

            # safe_error, NOT f"{last_exc}" — measured in production 2026-08-23: this line
            # printed a googleapiclient HttpError whose repr embeds the request URI, so the
            # YouTube API key landed in the Airflow task log in clear, every night. The
            # per-attempt lines above were already redacted; only the exhausted one was not.
            logger.error(
                f"❌ {func.__qualname__} — toutes les tentatives ({max_attempts}) épuisées. "
                f"Dernière erreur : {safe_error(last_exc, limit=1000)}"
            )
            raise last_exc

        return wrapper
    return decorator
