# Registre des erreurs applicatives

<!-- GÉNÉRÉ par `tools/error_inbox.py` — toute édition à la main est perdue à la prochaine exécution. -->

Une ligne par **défaut**, pas par occurrence : l'empreinte (`src/utils/error_fingerprint.py`) est la classe d'exception plus le premier cadre de pile qui nous appartient, **sans numéro de ligne**. Le même bug vu vingt fois, avant et après un déploiement, reste une seule ligne avec un compteur.

Régénéré le 2026-09-04 10:18 UTC · **0 ouverte(s)** sur 0 au total.

Fermer une entrée : `make error-resolve FP=<12 premiers caractères> NOTE="ce qui a été corrigé"`. Une **nouvelle** occurrence la rouvre automatiquement — c'est le signal le plus utile du registre.

## ✅ Rien d'ouvert

Aucune erreur applicative non triée.
