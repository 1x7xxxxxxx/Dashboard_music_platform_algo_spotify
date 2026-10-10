# Études E1–E6 — outillage de test et lecteurs CSV (2026-10-10)

Chaque étude répond à UNE question avec un critère d'intégration fixé AVANT la lecture
(plan `cryptic-mapping-crystal`). Verdict : **intégrer**, **plus tard**, ou **rien à prendre**.
Une intégration retenue devient une ligne Rnnn ; tant qu'elle n'en a pas, elle n'existe pas.

| # | Sujet | Question | Verdict | Pourquoi / déclencheur |
|---|---|---|---|---|
| E1 | mutmut (cosmic-ray en alternative) | Remplace-t-il `mutate_guards.py` pour le code PRODUIT ? | **Intégrer, borné** : `src/transformers/` seulement, en tâche de nuit | `mutate_guards.py` mute des GARDES, pas le code produit ; mutmut fait l'inverse et ne le remplace pas. Borné aux parseurs (purs, rapides). Critère de maintien : ≥1 survivant qui soit un vrai trou de test sur le premier mois, sinon retrait. |
| E2 | Pandera / Great Expectations | Un schéma déclaratif à la place des rejets faits main de R502 ? | **Plus tard** | Le besoin de R502 est un COMPTE de cellules illisibles par colonne avec un message lisible par un artiste ; Pandera rend des `SchemaErrors` techniques et ajoute une dépendance lourde pour 5 lecteurs. Rouvrir si les parseurs dépassent ~10 ou si une validation inter-colonnes apparaît. |
| E3 | `babel.numbers.parse_decimal` | Remplace-t-il `csv_dialect.read_number` (R503) ? | **Plus tard** | Le mode `strict=True` ne refuse pas « 1.234 » en `fr` : l'ambiguïté que R503 tranche par FICHIER reste entière valeur par valeur. Babel ne sait pas décider la locale d'un fichier ; c'est notre problème, pas le sien. |
| E4 | Quarantaine des tests instables (KIP-1090, pytest-rerunfailures) | Faut-il une quarantaine ? | **Mesurer seulement** | Critère : > 2 rouges instables par semaine sur 2 semaines. Mesuré sur 14 j : 1 seul rouge CI sur 8 lus était un défaut produit, aucun n'était instable — les autres étaient Dependabot (5) et des documents périmés (3, retirés par R506). Une relance automatique masquerait précisément ce que `defect-log` compte. |
| E5 | Dependabot `uv` / Renovate | Lequel garde `uv.lock` cohérent ? | **Intégrer avec garde** — mais voir R507 | L'écosystème `uv` de Dependabot met à jour `pyproject.toml` + `uv.lock`, mais **pas** `requirements*.txt` (20 épinglages `==` écrits à la main, lus par les Dockerfiles). Basculer seul ferait rougir le contrôle de cohérence du manifeste. Décision du propriétaire : R507, options (a)/(b)/(c). |
| E6 | SQLite pour tests, OpenHands, SWE-agent, self-healing-ci-agent | Qu'adopter pour la boucle autonome ? | **Lu, rien à prendre** | Aucune pratique précise ne supprime une étape manuelle d'ici : la boucle `night-start → test-changed → push → CI → roadmap-close` couvre déjà ce que ces agents automatisent, et SQLite ne remplace pas les tests contre le vrai Postgres (le schéma canonique a déjà divergé d'une base locale, R219/R228). |

## Références lues (corpus `knowledge-rag`)

- Reis & Housley, *Fundamentals of Data Engineering*, p.363 — file des rejets (dead-letter
  queue) : ce qui ne s'ingère pas est mis de côté sans bloquer le reste. Fonde R502.
- Densmore, *Data Pipelines Pocket Reference*, p.195 — un échec silencieux rend un jeu de
  données partiel. Fonde le refus du « 0 silencieux ».
- Khorikov, *Unit Testing*, p.152 — les tests sur la sortie sont les plus maintenables.
  Fonde le choix des propriétés Hypothesis (R499, R504, R505) sur des fonctions pures.
