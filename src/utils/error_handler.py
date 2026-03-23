"""Gestion centralisée des erreurs et logging structuré."""
import logging
import traceback
import functools

logger = logging.getLogger(__name__)


def log_errors(reraise: bool = True):
    """
    Décorateur pour logger les erreurs avec contexte complet.

    Args:
        reraise: Si True (défaut), reraise l'exception après logging.
                 Si False, swallow l'erreur et retourne None.

    Usage:
        @log_errors()
        def ma_fonction(): ...

        @log_errors(reraise=False)
        def fonction_optionnelle(): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    f"❌ Erreur dans {func.__qualname__}: {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()}"
                )
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


def log_and_raise(message: str, exc: Exception) -> None:
    """Log une erreur avec message contextualisé puis reraise."""
    logger.error(f"❌ {message}: {type(exc).__name__}: {exc}")
    raise exc


def safe_call(func, *args, default=None, **kwargs):
    """
    Appelle func(*args, **kwargs) en swallowing toute exception.
    Retourne `default` en cas d'erreur. Utile pour les appels dashboard non-critiques.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.warning(f"⚠️ safe_call({func.__qualname__}) ignoré: {type(exc).__name__}: {exc}")
        return default
