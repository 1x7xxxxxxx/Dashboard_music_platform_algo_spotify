"""Décorateur de retry avec backoff exponentiel pour les erreurs réseau/DB."""
import time
import logging
import functools
from typing import Tuple, Type

import psycopg2

logger = logging.getLogger(__name__)

# Exceptions qui méritent un retry (réseau / connexion transitoire)
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    psycopg2.OperationalError,
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
                        f"({type(exc).__name__}: {exc}). Retry dans {delay:.1f}s."
                    )
                    time.sleep(delay)
                except Exception as exc:
                    # Autre exception non identifiée : retry quand même
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    if backoff == "exponential":
                        delay = (2 ** (attempt - 1)) * base_delay
                    else:
                        delay = attempt * base_delay
                    logger.warning(
                        f"⚠️ {func.__qualname__} — tentative {attempt}/{max_attempts} échouée "
                        f"({type(exc).__name__}: {exc}). Retry dans {delay:.1f}s."
                    )
                    time.sleep(delay)

            logger.error(
                f"❌ {func.__qualname__} — toutes les tentatives ({max_attempts}) épuisées. "
                f"Dernière erreur : {last_exc}"
            )
            raise last_exc

        return wrapper
    return decorator
