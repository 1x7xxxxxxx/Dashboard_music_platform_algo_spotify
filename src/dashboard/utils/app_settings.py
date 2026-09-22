"""Les réglages d'exploitation : environnement d'abord, base ensuite.

Type: Utility
Uses: os, psycopg2 (via PostgresHandler)
Depends on: app_settings (migration 134)
Persists in: PostgreSQL spotify_etl (app_settings)

La précédence, et pourquoi elle est dans ce sens
------------------------------------------------
    1. la variable d'environnement, si elle est posée et non vide
    2. la valeur en base, éditable depuis la page Admin
    3. la valeur par défaut fournie par l'appelant

L'environnement gagne pour la raison des douze facteurs : il permet d'imposer une
valeur en production sans toucher aux données, et de la retirer sans migration. La
base existe parce que l'inverse — n'avoir QUE l'environnement — laisse la
fonctionnalité éteinte : poser un lien de rendez-vous ne doit pas demander de
rebâtir un conteneur.

Ce que ce module REFUSE d'écrire
---------------------------------
Une URL qui n'est pas `https://`. Cette valeur finit dans le `href` d'un bouton
affiché aux artistes : accepter `javascript:` ou `data:` ferait de la page Admin
une surface d'injection, et accepter `http://` enverrait un locataire sur un lien
en clair. Le refus est explicite et nommé, jamais un nettoyage silencieux — un
réglage corrigé à l'insu de celui qui l'a saisi est un réglage qu'il croira posé.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

# Les clés connues. Une clé hors de cette liste est refusée : `app_settings` est
# une table de configuration, pas un sac fourre-tout où chaque vue déposerait la
# sienne sans que personne ne sache ce qui existe.
CLES = {
    "service_calendly_url": "SERVICE_CALENDLY_URL",
}


class ReglageInvalide(ValueError):
    """Une valeur refusée, avec la raison — jamais corrigée en silence."""


def valider_url(valeur: str) -> str:
    """Rend l'URL nettoyée de ses espaces, ou lève en nommant le refus."""
    v = (valeur or "").strip()
    if not v:
        return ""
    u = urlparse(v)
    if u.scheme != "https":
        raise ReglageInvalide(
            f"« {v[:60]} » : seul `https://` est accepté. Cette adresse devient "
            "le lien d'un bouton montré aux artistes — un autre schéma en ferait "
            "une surface d'injection, et `http://` les enverrait en clair.")
    if not u.netloc:
        raise ReglageInvalide(f"« {v[:60]} » n'a pas de nom de domaine.")
    return v


def get_setting(db, cle: str, defaut: str = "") -> str:
    """La valeur effective : environnement, puis base, puis défaut."""
    env = CLES.get(cle)
    if env:
        depuis_env = (os.getenv(env, "") or "").strip()
        if depuis_env:
            return depuis_env
    if db is None:
        return defaut
    try:
        rows = db.fetch_query(
            "SELECT value FROM app_settings WHERE key = %s", (cle,))
    except Exception:
        # Une lecture de réglage qui échoue ne doit pas emporter la page qui
        # l'affiche : l'absence de bouton est un dégât moindre qu'une page morte.
        return defaut
    return (rows[0][0] if rows and rows[0][0] else defaut) or defaut


def set_setting(db, cle: str, valeur: str) -> None:
    """Écrit le réglage. Lève `ReglageInvalide` plutôt que d'assainir en douce."""
    if cle not in CLES:
        raise ReglageInvalide(
            f"clé inconnue : « {cle} ». Ajoute-la à `CLES` pour qu'elle existe — "
            "une table de configuration dont personne ne connaît les entrées ne "
            "se relit pas.")
    propre = valider_url(valeur)
    db.execute_query(
        "INSERT INTO app_settings (key, value, updated_at) "
        "VALUES (%s, %s, now()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
        "updated_at = now()",
        (cle, propre))


def env_impose(cle: str) -> bool:
    """L'environnement écrase-t-il la base pour cette clé ?

    La page Admin doit le DIRE : sans ça, l'exploitant saisit une valeur, la voit
    enregistrée, et l'écran continue d'afficher l'autre — sans rien qui explique.
    """
    env = CLES.get(cle)
    return bool(env and (os.getenv(env, "") or "").strip())
