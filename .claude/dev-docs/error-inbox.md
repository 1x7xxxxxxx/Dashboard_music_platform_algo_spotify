# Registre des erreurs applicatives

<!-- GÉNÉRÉ par `tools/error_inbox.py` — toute édition à la main est perdue à la prochaine exécution. -->

Une ligne par **défaut**, pas par occurrence : l'empreinte (`src/utils/error_fingerprint.py`) est la classe d'exception plus le premier cadre de pile qui nous appartient, **sans numéro de ligne**. Le même bug vu vingt fois, avant et après un déploiement, reste une seule ligne avec un compteur.

Régénéré le 2026-09-17 12:47 UTC · **1 ouverte(s)** sur 1 au total.

Fermer une entrée : `make error-resolve FP=<12 premiers caractères> NOTE="ce qui a été corrigé"`. Une **nouvelle** occurrence la rouvre automatiquement — c'est le signal le plus utile du registre.

## Ouvertes

| Empreinte | Exception | Où | Page | Env | # | Vue il y a | Classe |
|---|---|---|---|---|---|---|---|
| `513cba567b5a` | `ValueError` | `unknown` | home | local | 1 | 22 h | — |

### Le détail

#### `513cba567b5a` — ValueError dans `unknown`

- **Message** : boom
- **Page** : home · **environnement** : local
- **1 occurrence(s)**, première il y a 22 h, dernière il y a 22 h
- **Classe** : non rattachée — si elle se reproduit, `/capitalise` en écrit une
