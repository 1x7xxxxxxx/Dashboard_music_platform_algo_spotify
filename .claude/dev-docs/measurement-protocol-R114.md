# Protocole de mesure de R114 — écrit AVANT la première courbe

Écrit le 2026-09-16, sur condition bloquante n°2 de `code-critic`. Un protocole rédigé
après la mesure choisit, sans le vouloir, celui qui donne le résultat qu'on espérait.

## 1. Le signal de décision est « reruns perdus », pas le p50

`code-critic` a trouvé une erreur dans la justification de R114, et elle est réelle :

> Le déclencheur écrit pour R87 était « `loadtest_dashboard.py -n 12` rend un p50
> > 200 ms ». Or `loadtest_dashboard.py` **se sature lui-même** (352 ms à un fil,
> 2 144 ms à six, sous `AppTest`) — c'est précisément pourquoi il a été remplacé par
> `tools/loadtest_concurrency.py`, qui parle le vrai websocket via un navigateur. Le
> nouvel outil rend **329 ms à N=1**, c'est-à-dire sans aucune concurrence : déjà
> au-dessus d'un seuil de 200 ms défini pour l'autre instrument.

**Le déclencheur a donc été lu sur un chiffre non comparable à celui qui l'a défini.**
Deux instruments, deux échelles, un seuil transporté de l'un à l'autre.

Le signal qui ne souffre pas de ce problème est la colonne **reruns perdus** — un
COMPTE, pas une durée, sans unité à transporter et sans ligne de base à soustraire :

| onglets | 1 | 2 | 4 | 8 | 12 | 16 | 24 |
|---|---|---|---|---|---|---|---|
| reruns perdus (1 instance) | 0 | 0 | 0 | **9** | **33** | — | **98** |

Un rerun perdu est un clic d'utilisateur qui n'a jamais rendu de page. Zéro est zéro
quel que soit l'instrument, sur n'importe quelle machine, à n'importe quelle heure.

**Décision** : R114 se juge sur les reruns perdus à 8 et 12 onglets. Le p50 est
rapporté, jamais décisif.

## 2. Les mesures ALTERNENT, et rien ne se conclut sous le seuil de bruit

Le dépôt a mesuré que comparer deux configurations **d'affilée** sur une machine
partagée ne prouve rien : la contention auto-infligée a déjà gonflé une mesure d'un
facteur **12,8**, et la suite varie de **±40 %**. Le VPS de production partage son CPU
entre Airflow, Postgres, Caddy et les conteneurs applicatifs.

Protocole :

1. **A** = une instance (état d'aujourd'hui) — une passe complète de la rampe.
2. **B** = deux instances derrière Caddy — une passe complète.
3. **A** — deuxième passe.
4. **B** — deuxième passe.

Les quatre passes aux mêmes paliers (`1,2,4,8,12,16,24`), mêmes `--reps 6`, à moins de
deux heures d'intervalle, **en heures creuses** (aucun DAG nocturne en cours : ils
tournent à 23 h UTC).

## 3. Le seuil de bruit, fixé AVANT

- **Reruns perdus** : la différence compte si B rend **zéro** rerun perdu là où A en
  perd ≥ 9 (le palier 8 onglets), **sur les DEUX passes**. Une passe seule ne conclut
  rien.
- **p50** : rapporté à titre indicatif. Un écart inférieur à **40 %** entre A et B est
  déclaré **dans le bruit** et ne peut soutenir aucune conclusion, ni dans un sens ni
  dans l'autre.
- Si les deux passes d'une même topologie diffèrent entre elles de plus de 40 %, la
  série est **jetée** et refaite. Une variance interne supérieure à l'effet cherché
  rend la comparaison vide.

## 4. Les trois issues, et elles sont toutes utiles

| Résultat | Ce qu'on écrit dans ADR-026 |
|---|---|
| B perd 0 rerun là où A en perd 9+, deux fois | le levier est prouvé ; on sait ce que coûte un utilisateur de plus |
| B perd autant que A | **le goulot n'est pas le GIL** — on aurait acheté Redis et des workers pour rien. C'est la découverte visée |
| écart sous le seuil | on ne conclut pas ; on garde une instance et on écrit pourquoi la mesure n'a pas tranché |

**La troisième issue est un résultat**, pas un échec. L'écrire est ce qui distingue une
expérience d'une justification.

## 5. Ce qui invalide la mesure, et qu'il faut vérifier avant de lancer

- un DAG en cours (`docker logs airflow_scheduler --tail 20`) ;
- un déploiement dans l'heure (les caches sont froids, le premier rendu coûte 12,5 s) ;
- `_heavy_local_processes()` refuse déjà de mesurer depuis une machine chargée — le
  garde existe côté client, pas côté serveur.
