"""Où tourne cette instance, et à quoi elle a le droit d'envoyer des e-mails.

Type: Utility
Uses: os (stdlib uniquement — doit s'importer depuis un DAG, un collecteur ou une vue)
Triggers: email_alerts, alert_monitor, data_quality_check, alert_root_cause
Persists in: rien

Pourquoi ce module — mesuré le 2026-08-24 sur de vrais e-mails reçus.

**1. Une URL d'Airflow codée en dur part dans un e-mail.** Trois sites écrivaient
`http://localhost:8080` littéralement, sans lire aucune variable d'environnement.

Précision mesurée, et elle corrige un diagnostic trop rapide : ces trois e-mails
partent tous vers `ALERT_EMAIL`, **l'administrateur**, et l'UI Airflow de production
est liée à `127.0.0.1:8080` seulement (vérifié le 2026-08-24 — `api.streamlytics.fr/dags`
rend 404). Pour ce destinataire-là, qui accède à la machine, `localhost:8080` est
donc l'adresse JUSTE. Ce n'était pas le défaut de `APP_BASE_URL`, où le lien partait
à un artiste.

Ce qui reste vrai et vaut le changement : l'adresse était **non configurable**. Le
jour où l'UI est exposée, ou le jour où l'un de ces textes atterrit dans un mail
destiné à un locataire, le lien suit au lieu de mentir. Une valeur qui n'a qu'un
destinataire correct par accident est une valeur qu'il faut pouvoir changer.

**2. Une instance de DÉVELOPPEMENT envoie des alertes qui ressemblent à la
production.** Le scheduler Airflow local a rejoué un run planifié, échoué sur le
credential SoundCloud partagé — que la prod venait de faire tourner 28 minutes plus
tôt, SoundCloud faisant tourner ses refresh_token — et a envoyé deux mails d'alerte
à une vraie boîte. Ils étaient indiscernables d'une panne de production au premier
coup d'œil ; seule l'adresse d'expéditeur et un lien `localhost` les distinguaient.

Une instance doit donc DIRE ce qu'elle est. `instance_label()` rend une étiquette
non vide hors production, et les surfaces d'envoi la préfixent au sujet.
"""
from __future__ import annotations

import os

# Nom de l'instance. La production le pose explicitement ; tout le reste — poste de
# dev, conteneur de CI, worktree — est « pas la production » par défaut.
_ENV_VAR = "STREAMLYTICS_ENV"
PRODUCTION = "production"


def instance_env() -> str:
    """`production`, ou l'étiquette de cette instance (`local` par défaut).

    Lu **à l'appel**, jamais figé à l'import : une constante de module porterait ce
    que l'environnement contenait au premier import, et c'est le défaut exact que
    `_BASE_URL` a coûté le 2026-08-23.
    """
    return (os.getenv(_ENV_VAR) or "local").strip().lower()


def is_production() -> bool:
    return instance_env() == PRODUCTION


def instance_label() -> str:
    """Préfixe à mettre devant le sujet d'un e-mail. Vide en production.

    Vide en production **à dessein** : ajouter « [PRODUCTION] » partout habituerait
    l'œil à un préfixe, et c'est précisément l'absence de préfixe qui doit vouloir
    dire « ceci est réel ».
    """
    return "" if is_production() else f"[{instance_env().upper()}] "


def airflow_base_url() -> str:
    """L'URL CLIQUABLE de l'interface Airflow, lue à l'appel.

    ⚠️ **`AIRFLOW_UI_URL`, surtout pas `AIRFLOW_BASE_URL`.** Les deux répondent à des
    questions différentes, et les confondre produit un lien inutilisable :
    `AIRFLOW_BASE_URL` existe déjà et vaut `http://airflow-webserver:8080` — le nom
    DNS interne à Docker, correct pour un APPEL depuis le conteneur du dashboard, et
    sans aucun sens pour un humain qui clique dans un e-mail. Réutiliser ce nom a
    d'ailleurs produit une clé YAML en double, attrapée par `check-yaml` avant le
    commit.

    Le repli `localhost:8080` est correct en production **pour son destinataire** :
    ces e-mails vont à l'administrateur et l'UI Airflow est liée à `127.0.0.1`
    seulement (vérifié le 2026-08-24). Ce qui était faux, c'est que l'adresse n'était
    pas configurable.
    """
    return os.getenv("AIRFLOW_UI_URL", "http://localhost:8080").rstrip("/")
