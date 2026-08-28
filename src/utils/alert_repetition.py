"""Quand la même alerte, dite une deuxième fois, n'apprend plus rien.

Type: Utility
Uses: hashlib, json, os, datetime (stdlib uniquement — doit s'importer depuis un DAG)
Triggers: alert_monitor.send_consolidated_alert
Persists in: rien (l'empreinte est écrite par l'appelant dans `monitoring_run`)

Pourquoi ce module — mesuré le 2026-08-28 sur les deux vraies nuits de production.

`alert_monitor` envoyait son récapitulatif chaque nuit, que les constats aient bougé ou
non. Les XCom des runs du 25 et du 26 août, relus tels quels, sont **identiques à deux
champs près** : `age_h` (1945.0 → 1969.0, la même source qui vieillit) et `when`
(l'horodatage du dernier échec Meta). Les constats eux-mêmes — Benken / Meta bloqué sur
le partage de `act_65390907`, GRiNCH / SoundCloud sans titre public, deux sources CSV
stale — étaient les mêmes, mot pour mot, y compris le geste à faire.

Deux mails, un seul contenu, et aucun des deux ne pouvait être traité le soir même : les
deux gestes sont des actions humaines dans des interfaces tierces. C'est de la fatigue
d'alerte au sens strict — le coût est payé à la réception, pas à l'inspection.

## La règle, et ce qu'elle refuse de faire

Deux nuits sont « la même » quand les mêmes choses sont cassées chez les mêmes
locataires sur les mêmes plateformes. Une **mesure** qui bouge (l'âge d'une source, la
date du dernier échec) ne rouvre pas le sujet ; un **constat** qui apparaît, disparaît ou
change de raison le rouvre immédiatement.

Ce module ne sait pas taire une alerte, seulement en taire la RÉPÉTITION :

- un constat nouveau, disparu ou modifié ⇒ l'empreinte change ⇒ envoi immédiat ;
- au-delà de `ALERT_REPEAT_SILENCE_DAYS` (7 par défaut) sans envoi réel, le même
  constat repart quand même. C'est un battement de cœur, et il est délibéré : un
  silence permanent est indiscernable d'un moniteur mort, et « le silence d'une
  alerte EST l'incident » (migration 073, ADR-011).

## Le biais est choisi, et il va vers l'envoi

`_VOLATILE_KEYS` est une **liste noire**, pas une liste blanche. La conséquence est
voulue : un champ de constat ajouté demain entre par défaut dans l'empreinte, donc au
pire il fait partir un mail de trop. L'inverse — une liste blanche de champs d'identité —
ferait qu'un champ oublié rendrait deux constats DIFFÉRENTS indiscernables, et
supprimerait un mail dû. Entre trop de courrier et un constat perdu, le module penche
toujours du même côté.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

# Les champs qui MESURENT plutôt qu'ils n'identifient. Relevés sur les constats réels
# des deux nuits ; chacun bouge tout seul, sans que rien n'ait changé pour personne.
_VOLATILE_KEYS = frozenset({
    "age_h",          # freshness — 1945.0 → 1969.0 d'une nuit à l'autre
    "age_days",       # resurrection sparks
    "when",           # collection_outcomes — horodatage du dernier échec
    "last_dt",        # freshness — date de la dernière ligne vue
    "first_failure",  # dag_failures
    "last_failure",   # dag_failures
    "recent",         # row_anomalies — la magnitude du pic, pas son identité
    "baseline",       # row_anomalies
    "recent_gain",    # resurrection sparks — la magnitude du regain
    "measured_at",
    "checked_at",
    "run_at",
})

# `consecutive_days` est un cas à part : le nombre monte chaque nuit (volatile), mais le
# passage à ≥3 jours est une ESCALADE que le corps du mail affiche en rouge. On garde le
# fait, pas le compteur — la nuit où un DAG escalade, le mail repart.
_ESCALATION_KEY = "consecutive_days"

_WINDOW_VAR = "ALERT_REPEAT_SILENCE_DAYS"
_DEFAULT_WINDOW_DAYS = 7


def repeat_window_days() -> int:
    """Nombre de jours au bout duquel un constat inchangé repart quand même.

    Lu à l'appel, jamais figé à l'import — même raison que `instance_env()`. Une valeur
    illisible ou ≤ 0 retombe sur le défaut : rendre la fenêtre infinie par une faute de
    frappe dans une variable d'environnement, c'est exactement la panne silencieuse que
    ce module doit être incapable de produire.
    """
    try:
        days = int(str(os.getenv(_WINDOW_VAR, "")).strip() or _DEFAULT_WINDOW_DAYS)
    except ValueError:
        return _DEFAULT_WINDOW_DAYS
    return days if days > 0 else _DEFAULT_WINDOW_DAYS


def _strip(value):
    """Retire récursivement les champs de mesure, en gardant tout le reste."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in _VOLATILE_KEYS:
                continue
            if k == _ESCALATION_KEY:
                out["_escalated"] = bool(v)
                continue
            out[k] = _strip(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_strip(v) for v in value]
    return value


def findings_digest(findings: dict) -> str:
    """Empreinte stable de l'ensemble des constats d'une nuit.

    `sort_keys` et `default=str` sont tous les deux load-bearing : sans le premier
    l'empreinte dépendrait de l'ordre d'insertion des dictionnaires, sans le second un
    `datetime` ou un `Decimal` remonté d'une requête ferait lever `TypeError` au beau
    milieu de l'envoi — et une empreinte qui plante est un mail qui ne part pas.
    """
    return hashlib.sha256(
        json.dumps(_strip(findings), sort_keys=True, ensure_ascii=False,
                   default=str).encode("utf-8")
    ).hexdigest()


def suppression_reason(digest: str, last_digest, last_delivered_at, now=None) -> str | None:
    """Pourquoi ne pas renvoyer ce mail, ou None s'il doit partir.

    Tout ce qui est inconnu fait partir le mail : pas d'envoi précédent, empreinte
    précédente absente, date illisible. Le module ne peut se taire que sur une preuve
    positive qu'un mail identique est déjà parti, et récemment.
    """
    if not last_digest or last_delivered_at is None:
        return None
    if last_digest != digest:
        return None
    if isinstance(last_delivered_at, str):
        try:
            last_delivered_at = datetime.fromisoformat(last_delivered_at)
        except ValueError:
            return None
    now = now or datetime.now(timezone.utc)
    # Les deux côtés doivent être comparables : `monitoring_run.run_at` est TIMESTAMPTZ,
    # mais un appelant qui passe un datetime naïf ne doit pas faire lever TypeError au
    # milieu de l'envoi. Un naïf est lu en UTC, faute de mieux, et jamais rejeté.
    if last_delivered_at.tzinfo is None:
        last_delivered_at = last_delivered_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window = repeat_window_days()
    age = now - last_delivered_at
    if age >= timedelta(days=window):
        return None
    remaining = timedelta(days=window) - age
    return (f"constats inchangés depuis le dernier envoi ({age.days}j), "
            f"renvoi dans {max(1, remaining.days)}j ou dès qu'un constat change "
            f"({_WINDOW_VAR}={window})")
