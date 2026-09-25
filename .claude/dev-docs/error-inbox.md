# Registre des erreurs applicatives

<!-- GÉNÉRÉ par `tools/error_inbox.py` — toute édition à la main est perdue à la prochaine exécution. -->

Une ligne par **défaut**, pas par occurrence : l'empreinte (`src/utils/error_fingerprint.py`) est la classe d'exception plus le premier cadre de pile qui nous appartient, **sans numéro de ligne**. Le même bug vu vingt fois, avant et après un déploiement, reste une seule ligne avec un compteur.

⚠️ **Instantané de la base LOCALE, régénéré à la main** (`make error-inbox`). Les défauts de PRODUCTION n'ont pas besoin de ce fichier : ils arrivent chaque soir dans le mail de 23 h (`check_app_errors`, DAG `alert_monitor`). Décision R171 du 2026-09-25 — le fichier était resté 7 jours sans régénération, avec pour seul défaut ouvert un artefact de test.

Régénéré le 2026-09-25 20:00 UTC · **0 ouverte(s)** sur 1 au total.

Fermer une entrée : `make error-resolve FP=<12 premiers caractères> NOTE="ce qui a été corrigé"`. Une **nouvelle** occurrence la rouvre automatiquement — c'est le signal le plus utile du registre.

## ✅ Rien d'ouvert

Aucune erreur applicative non triée.

## Fermées

| Empreinte | Exception | Fermée il y a | Note |
|---|---|---|---|
| `513cba567b5a` | `ValueError` | 0 h | artefact de test local (ValueError boom, env local), pas un defaut applicatif - R171 |
