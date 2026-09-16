# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | tâches ouvertes, bugs ouverts, état de reprise | `/roadmap-done`, `roadmap-keeper` |
| `archive.md` | briques livrées, bugs clos | `roadmap-keeper` (rotation seule) |

`tests/test_roadmap_two_files.py` échoue si la somme des items des deux fichiers change :
une rotation qui rétrécit le dénominateur améliore le pourcentage sans rien livrer.

Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## 📋 Tâches ouvertes (index — détail plus bas)

Index concis des tâches **qu'on peut commencer maintenant**. À la complétion d'une tâche :
`/roadmap-done <id>` la coche dans son bloc détaillé ET la retire de ce tableau **vers
`archive.md`** (CLAUDE.md — flux roadmap).

| id | Tâche | P | Mesuré par |
|---|---|---|---|
| R120 | La vue, pas la chrome — onglets et expanders paresseux (chrome démesurée : 11-13 ms) | P2 | histogramme de rendu avant/après, même charge |
| R118 | `st.fragment` — **6/11 faites** ; le reste attend une mesure de coût | P3 | l'histogramme montre la page avant de la refactorer |
| R121 | Les agrégations Python passent en SQL (couche or) | P3 | `make gold-coverage`, cliquet |
| R116 | **ADR-027** — répliques et Redis, tranché APRÈS les courbes (026 est pris) | P4 | `ls docs/adr/ADR-027-*.md` |
| R117 | Le dépôt quitte `/mnt/c` pour ext4, et VS Code passe en Remote-WSL | P3 | suite complète chronométrée des deux côtés, en alternance |

**R109 et R110 ont été livrées et déployées le 2026-09-16** — voir `archive.md`.
Résultat mesuré : le mur du run `ci.yml` est passé d'une médiane de **427 s à 109 s**
(run 35035830958, ×3,9), en séparant les portes statiques de la suite en 4 shards
`pytest-split`. La prémisse de R110 — que le fichier le plus long dominait le temps de
mur — s'est révélée **fausse** à la mesure : `loadgroup` (349,6 s) n'a pas battu
`loadfile` (340,2 s), écart de 2,8 % dans le bruit. R110 a quand même livré quatre
courses latentes fermées, condition nécessaire pour que R109 tienne sa promesse à
quatre shards. Détail dans `archive.md`.

**R108 a été livrée le 2026-09-14** — la dernière tâche qui
y figurait, et avec elle l'index n'a plus eu de ligne jusqu'au 2026-09-15. Elle tranchait entre exempter ou
compter les jointures de dimension dans le cliquet du bronze ; le critère retenu
(« cette table porte-t-elle une quantité ADDITIVE ? ») a fait descendre le cliquet
de 104 à 81 via un registre de 8 tables de dimension et la migration 121. Détail dans
`archive.md`. **R103 et R107 ont été
livrées le 2026-09-14** — le diagnostic lit une route et non un nom, et les trois
décisions produit de R107 sont toutes tranchées. Détail dans `archive.md`. **R106 a été livrée le 2026-09-13** — la
tuile Shazam est sur l'accueil (1 770 au catalogue, 637 pour la dernière sortie), et
avec elle la mention que l'historique journalier de YouTube et SoundCloud est
définitivement hors de portée. R105 a été ABANDONNÉE le
2026-09-13 par ADR-025 : le produit est Spotify + Meta + ML, et YouTube pèse
0,2 % du signal. Le code écrit pour elle a été retiré, pas désactivé. R104 a été close le soir même — la rupture de
méthode YouTube est détectée sur un seuil mesuré et retirée des deux surfaces
qui la comptaient (figure et totaux). Détail dans `archive.md`. R92 à R95, les quatre tâches de l'audit metrics layer du 2026-09-11, ont été
closes et rotées dans `archive.md`, comme R89, R90 et R91 avant elles (critère du
double axe écrit et six figures triées, légende devenue le filtre de sources, PDF doté
de la figure d'évolution multi-plateformes). Détail complet dans l'archive.

**Aucune tâche ouverte ne reste dans cet index, ni dans aucune autre section.** La
table « 🙋 En attente de toi » plus bas est vide elle aussi depuis le 2026-09-10 :
R1, sa dernière ligne, est rotée dans `archive.md`. Inviter la bêta est l'usage du
produit, pas du travail d'ingénierie — une roadmap qui suit les gestes commerciaux de
son propriétaire ne peut par construction jamais atteindre zéro.

⚠️ Ce paragraphe annonçait encore « quatre tâches rouvertes » le 2026-09-12, alors que
les quatre étaient closes et l'index vide. Aucun garde ne pouvait le voir : l'ancre et
le tableau étaient justes, c'est la PROSE à côté qui affirmait le contraire. C'est la
classe `a-prose-claim-that-cannot-be-verified`, et la parade reste la même — quand une
phrase de ce fichier compte des tâches, elle doit compter ce que l'index compte.

R59, R60, R61 et R62 ont été closes le 2026-09-05 (voir `archive.md`) : deux par un
correctif, une par un ADR qui montre que sa prémisse était fausse, une par un ADR qui
mesure une porte fermée. **R63** a suivi le soir même, le quota Meta revenu ayant permis
de trancher : `business_discovery` lit un compte Instagram tiers sans aucun partage
Business Manager (les insights, non) — 📸 Instagram a donc son onglet, et son collecteur
retombe sur cette route.

**Le 2026-09-10 a rouvert huit tâches** (R64–R71), venues d'un audit de la figure de
l'accueil qui a mesuré un défaut invisible aux 4 740 tests — la figure dessinait ×2,7 ce
qui avait été mesuré — puis d'un balayage du dépôt qui a rendu **~130 sites frères** sur
cinq classes. **Sept ont été livrées le jour même** — R64, R65, R66, R67, R68, R69, R71,
voir `archive.md` — correctif, garde, mutations rouges et suite complète verte à 4 804
tests. **R70 a suivi le soir même** : ADR-019 écrit, migration 097
(`v_platform_totals`), et les **cinq** surfaces qui calculaient le total d'une
plateforme repointées sur la définition unique — le total YouTube de l'artiste 1 valait
120 627 sur deux d'entre elles et 118 219 sur les trois autres au même instant. Le lot
de huit est clos.

**Un audit transverse a été mené le 2026-09-10 au soir** — sécurité, résilience,
performance, filtres, méthode de tracé, refactor. Il a d'abord trouvé **un défaut
CRITIQUE que j'avais moi-même livré le matin** : `/kpis` rendait 500 en production pour
tous les appelants, faute d'un alias de colonne, et le garde écrit pour cette classe
exacte était devenu **aveugle depuis trois semaines** — ses 28 assertions « pas de 500 »
étaient toutes satisfaites par des 401, parce qu'un contrôle d'authentification ajouté
entre-temps arrêtait les requêtes avant les routeurs. Corrigé, déployé, et le garde
rougit désormais sur ce défaut précis.

Onze tâches en sont sorties, **R72 à R82**, chacune avec la mesure qui l'a établie.
**Trois sont livrées et déployées le soir même** — R72 (le payeur ne choisit plus le
locataire à provisionner), R73 (Meta pesait 81 % de la nuit dont 424 s de sommeil
imposé), R74 (plus aucune attente illimitée, ni base ni HTTP). Les huit autres restent
ouvertes, chacune avec sa mesure : ce sont des chantiers, pas des retouches.

**Le soir du 2026-09-10 a construit les propositions du dossier d'architecture**, sans
ouvrir de tâche : le cliquet de la frontière du bronze (124 couples, il ne peut que
descendre), le compteur de ce que la conversion cumul → quotidien jette (la figure
traçait 21 écoutes YouTube et en écartait 167, en silence), une seule horloge pour
décider d'une date, 38 lectures muettes du rapport client désormais tracées, et les
zéros de prédiction retirés. **ADR-020** clôt la question des deux vocabulaires de
période : ils ne sont pas une duplication, ils répondent à deux questions — l'une
calendaire, l'autre ancrée sur une sortie.

**Un seul chantier reste, et ce n'est pas une tâche** : la reprise des définitions
encore recopiées, qui se fait **au fil de l'eau** sous la règle de livraison d'ADR-019
— son avancement se lit dans le cliquet du bronze, pas ici.

**La réconciliation des fuseaux de PUBLICATION a été retirée d'ici le 2026-09-15, et
il faut lire pourquoi avant de la rouvrir.** Ce paragraphe la justifiait par « 7,9 %
des lignes YouTube changent de jour selon le fuseau qu'on retient ». **Ce chiffre a
été retiré comme faux le 2026-09-10 même** — il mélangeait deux ères sur une base
locale — et la rétractation est écrite dans `error-classes.md`, dans `archive.md` et
dans ADR-021 ; ce fichier-ci est le seul à l'avoir gardé cinq jours de plus. Recompté
en production : **0 ligne sur 5 807** pour `collected_at` post-migration-019, les
collectes nocturnes atterrissant à 10 h UTC, à plus de quatre heures de toute
frontière de jour. ADR-021 tranche la question — chaque date déclare l'horloge qui l'a
produite — et **désigne nommément cette tâche comme la forme dangereuse** : une
harmonisation appliquée sans distinction déplacerait 267 jours calendaires déjà justes
d'une journée entière. L'écart résiduel aux bords des journées de reporting de Spotify
et d'Apple n'est pas corrigeable ; il est nommé par `UNRECONCILABLE_NOTE`, et
l'effacer serait la faute.

**Plus aucune tâche n'est ouverte**, ni dans l'index ci-dessus ni dans
« 🙋 En attente de toi » plus bas : R1, le dernier geste humain, y a été rotée vers
`archive.md` le 2026-09-10.

---

## 🏗 R113–R116 — Monter l'architecture scalable, pour mesurer si elle est nécessaire

Le contexte, en une phrase : la concurrence a enfin été MESURÉE le 2026-09-16 contre la
production, et elle dément le plafond que ce dépôt citait depuis trois mois.

| onglets | p50 | reruns perdus | p50 / p50(1) |
|---|---|---|---|
| 1 | 329 ms | 0 | ×1,00 |
| 4 | 754 ms | 0 | ×2,29 |
| 8 | 1 088 ms | **9** | ×3,31 |
| 24 | 3 488 ms | **98** | ×10,60 |

Débit plafonné à ~7 rendus/s contre 11,1 « soutenables » dérivés. La dérivation était
optimiste de 1,2× à 1,6× **et aveugle à l'échec** : elle ne connaît que la latence,
jamais les 98 reruns perdus. **Le point unique est un processus Python — Redis n'est pas
le levier, la seconde instance l'est.** C'est l'inverse de l'ordre qu'on suppose.

⚠️ **Le p50 de ce tableau ne se compare PAS au déclencheur qui a rouvert R87**, et je
l'avais fait. Trouvé par `code-critic` le 2026-09-16 : le déclencheur disait
« `loadtest_dashboard.py -n 12` rend un p50 > 200 ms », or cet outil **se sature
lui-même** (352 ms à un fil, 2 144 ms à six, sous `AppTest`) — c'est la raison pour
laquelle il a été remplacé. Le nouvel outil rend **329 ms à N=1**, donc déjà au-dessus
d'un seuil défini pour l'autre instrument. Deux échelles, un seuil transporté de l'une à
l'autre.

**Le signal de décision est donc la colonne « reruns perdus »** — un COMPTE, sans unité
à transporter et sans ligne de base à soustraire. Un rerun perdu est un clic qui n'a
jamais rendu de page ; zéro est zéro quel que soit l'instrument. Protocole complet,
écrit AVANT la première courbe : `.claude/dev-docs/measurement-protocol-R114.md`.

Ces quatre tâches construisent la forme scalable **même si le seuil n'est pas atteint**
(R87 est close sur un pic de 12 sessions/minute contre un seuil de 20). C'est une
décision assumée : découvrir par la mesure que ce n'était pas nécessaire vaut mieux que
le supposer.

- [ ] **R120 — la VUE, pas la chrome.** (titre corrigé le 2026-09-16 : il disait l'inverse)

  ⚠️ **Ma première hypothèse était fausse et le dépôt le savait déjà.** `docs/adr/ADR-007`
  porte un profil cProfile pris **dans le conteneur de production** (2026-08-30,
  `trigger_algo`, 662 ms) : `plotly.__setitem__` 0,327 s cumulé, `__getitem__` 0,199 s,
  `copy.deepcopy` 0,141 s sur 82 462 appels, SQL 0,067 s. **pandas n'apparaît ni en temps
  propre ni dans les 20 premiers.** C'est **plotly** et la construction des figures.

  ⚠️⚠️ **ET LA SECONDE PHRASE DE CE BLOC ÉTAIT FAUSSE AUSSI.** Elle disait : « le coût
  n'est pas dans la vue — rendu par vue p50 = 61 ms, page complète = 468-538 ms, soit
  ~8× ». Ces 468-538 ms sont mesurés sous `AppTest`, dont le plancher vaut 352 ms (détail
  plus bas). **Mesuré côté SERVEUR le 2026-09-16, c'est l'inverse**, sur les 8 pages
  visitées, sans une exception :

  | page | chrome | vue | vue / chrome |
  |---|---|---|---|
  | `meta_mapping` | 12,3 ms | **776,8 ms** | **63×** |
  | `soundcloud` | 75,5 ms | 515,0 ms | 6,8× |
  | `data_wrapped` | 13,4 ms | 357,7 ms | 26,6× |
  | `home` | 11,2 ms | 315,9 ms | 28,2× |
  | `meta_cpr_optimizer` | 11,3 ms | 98,7 ms | 8,7× |
  | `instagram` | 12,3 ms | 96,3 ms | 7,8× |
  | `apple_music` | 12,3 ms | 87,3 ms | 7,1× |
  | `saisie_s4a` | 10,9 ms | 49,8 ms | 4,6× |

  **La chrome est PLATE** — 11 à 13 ms sur sept pages sur huit. Le 75 ms de `soundcloud`
  est son premier rendu, imports compris. C'est la vue qui varie, de 50 ms à 777 ms.

  **D'où venait le « facteur 8 » ? D'une soustraction jamais faite.** `468-538 ms` est
  mesuré **sous `AppTest`**, et `tools/loadtest_dashboard.py:30-33` documente vingt
  lignes plus haut le plancher de ce harnais, pris dans le MÊME conteneur le MÊME jour :
  **352 ms pour `st.write('hello')`** — deux lignes, pas d'app, pas de base, pas de
  plotly. Le coût réel de l'application au-dessus du harnais valait donc ~116-186 ms.
  C'est ce reste-là qu'il fallait comparer aux 61 ms d'une vue, pas le total.

  Les chiffres se recollent : `instagram` vaut 12 ms de chrome + 96 ms de vue = **108 ms**
  côté serveur, au milieu de la bande 116-186. Ce qu'on attribuait à « la barre latérale »
  était presque entièrement `AppTest`.

  ⚠️ **Et ma première explication de l'erreur était fausse aussi** : j'ai attribué l'écart
  à une mesure « côté client », alors que le fichier dit qu'elle est prise dans le
  conteneur de production. J'expliquais un chiffre faux par une cause plausible sans lire
  la source — le geste même qui avait produit le chiffre faux.

  ⚠️ Portée : **12 rendus, 8 pages, une session**. Le multiplicateur exact n'est pas
  établi. Ce qui l'est : le plus PETIT rapport observé est 4,6×, et la chrome ne bouge
  pas d'une page à l'autre. Aucune accumulation de données ne fera passer un plancher de
  11 ms devant une vue à 777 ms.

  **Conséquence sur ce bloc** : les quatre premiers postes ci-dessous (`st.tabs`,
  `st.expander`, `platform_chart`) sont **dans la vue** et restent valables — ce sont eux
  que la mesure incrimine. Les deux qui visaient la chrome (la barre latérale à ~39 `t()`
  par rerun, `track_page_view` hors du pool) **pèsent ensemble moins de 13 ms** : ils
  descendent en P4, et `track_page_view` ne reste que parce qu'une connexion hors du pool
  est un défaut de forme, pas de vitesse.

  Les postes, tous vérifiés :
  * **`st.tabs` exécute tous les corps** — `views/trigger_algo/router.py:202-225` ouvre
    7 onglets et les appelle tous ; 15 vues ont un `st.tabs` ;
  * **`st.expander(expanded=False)` exécute son corps aussi** — `utils/ui.py:83-98` ;
    `tools/dev/chart_budget.py` compte les figures construites et jamais vues :
    meta_creatives 4, data_wrapped 4, trigger_algo 4, meta_ads_overview 3 ;
  * **la barre latérale** — ~39 `t()` + ~39 `page_is_locked` + 6 `st.sidebar.radio` à
    CHAQUE rerun pour un menu qui ne change pas ;
  * **`track_page_view`** (`utils/usage_tracker.py:27-38`) ouvre un `PostgresHandler`
    **hors du pool** ;
  * **`utils/platform_chart.py:225-285`** refait un `GROUP BY date_trunc` en boucles
    Python, sur la figure de l'accueil.

- [ ] **R118 — `st.fragment` sur les vues à filtres. AVANCÉE 6/11, et sa population est
      à redériver.**

  **Fait le 2026-09-16, et déployé** : `db_health` (2 sections), `airflow_kpi` (le seul
  fragment préexistant, RÉPARÉ — il capturait une connexion fermée), `data_wrapped`
  (l'onglet Évolution, 357,7 ms mesurés), `meta_creatives` (4 sections),
  `revenue_forecast` (3 onglets à curseurs), `spotify_s4a_combined` (1 section).

  ⚠️⚠️ **LA POPULATION DE CETTE BRIQUE A ÉTÉ CHOISIE PAR NOMBRE DE WIDGETS, PAS PAR
  COÛT.** Les mesures serveur du 2026-09-16 le montrent, et elles changent ce qui reste
  à faire :

  | page | vue mesurée | filtres | R118 peut-elle aider ? |
  |---|---|---|---|
  | `meta_mapping` | **776,8 ms** | 3 (dans `_campaigns`) | partiellement |
  | `soundcloud` | **515,0 ms** | **0** | **non** |
  | `data_wrapped` | 357,7 ms | 5 | oui — **fait** |
  | `home` | **315,9 ms** | **0** | **non** |
  | `meta_cpr_optimizer` | 98,7 ms | 0 | non |
  | `instagram` | 96,3 ms | 0 | non |
  | `apple_music` | 87,3 ms | 0 | non |
  | `saisie_s4a` | 49,8 ms | 0 | non |

  **Les trois pages les plus chères n'ont presque aucun filtre.** Un fragment ne borne
  que le travail refait *quand un filtre bouge* ; sur une page sans filtre il ne borne
  rien. Leur coût est le CORPS de la vue — c'est-à-dire R120 (onglets et expanders
  paresseux) et R121 (agrégations Python → SQL), pas celle-ci.

  **Ce qui reste ici, et ce que ça vaut** : `imusician`, `meta_ads_overview`, `hypeddit`,
  `youtube`, `admin`. Aucune n'est apparue dans la session mesurée, donc **leur coût est
  inconnu** — les fragmenter serait payer un refactor sur une page dont on ignore si elle
  coûte quelque chose. Le geste correct est d'attendre qu'elles apparaissent dans
  l'histogramme : `sum by (page) (streamlytics_rerun_duration_seconds_count)`. C'est
  exactement le motif d'ADR-007, appliqué à nous-mêmes.

  ⚠️ **La limite d'éligibilité, trouvée en le faisant** : un fragment DESSINE, il ne
  RETOURNE pas. `_song_detail()` de `spotify_s4a_combined` porte un `st.selectbox` et
  rend une figure que son appelant pose — rejoué seul, il rendrait à un appelant qui ne
  se rejoue pas, et la page afficherait un titre choisi avec les données d'un autre.

  ⚠️ **Et un défaut vivant trouvé en écrivant le garde** : `airflow_kpi` portait le seul
  `@st.fragment` du dépôt, et il recevait la connexion de `show()`, fermée avant qu'il ne
  se rejoue. Ça ne plantait pas — `_ensure_connection()` ré-empruntait au pool, sans
  jamais rendre. Une fuite d'une connexion par session admin sur un pool à 10.
  `tests/test_a_fragment_never_captures_a_connection.py` le tient maintenant dans les
  deux sens.

- [ ] **R121 — les agrégations Python passent en SQL.**

  Une agrégation en Python tient le GIL ; la même en SQL le relâche pendant l'attente.
  La couche or (ADR-019, 19 migrations `gold`) **est déjà le mécanisme**.

  Sites localisés : `views/alerts.py:251` (`groupby().tail(1)` dans une boucle sur tous
  les mois), `views/meta_creatives.py:539-561` (`groupby` + `nlargest` + `cumsum`),
  `views/meta_x_spotify.py:168-201` (3 `merge` + `concat` pour un axe de dates),
  `views/db_health.py:129-145` (`concat` en boucle + `pivot_table`),
  `views/hypeddit.py:181`, `views/soundcloud.py:183`, `views/meta_ads_overview.py:696`.

  **Garde existant à réutiliser** : `make gold-coverage` et son cliquet.

- [ ] **R116 — ADR-027, écrit APRÈS les courbes.**

  ⚠️ **Le numéro a changé** : ce bloc annonçait ADR-026, qui est pris depuis le
  2026-09-16 par la décision d'observabilité. Cette décision-ci est **ADR-027**.

  La décision sur les répliques et sur Redis, avec les DEUX courbes mesurées, les
  alternatives refusées et le déclencheur de relecture. Un ADR écrit avant la mesure
  serait une rationalisation — c'est pourquoi il est une tâche à part et qu'il vient en
  dernier.

  **Il a maintenant de quoi être écrit honnêtement, ce qui n'était pas le cas avant :**
  la réplique est arrêtée côté Caddy ET côté scrutation Prometheus, et les trois gestes
  de remise en service sont écrits en UN seul endroit (le bloc au-dessus de
  `reverse_proxy` dans `deploy/Caddyfile`). La courbe qui tranchera est
  `streamlytics_rerun_duration_seconds`, mesurée côté SERVEUR — insensible à la
  saturation du client, qui est ce qui rendait la mesure de R114 ambiguë.

**Ce qui reste écarté, avec sa raison** : Redis (R113 supprime son besoin pour les
caches, l'étape 1 l'a fait pour les limiteurs — s'il reste un besoin après R114, il sera
NOMMÉ, pas supposé) ; Celery/RQ (Airflow tient l'asynchrone, 13 DAGs) ; Loki et les
traces (après Prometheus, et seulement si un incident les réclame) ; Terraform (0 fichier
IaC, vrai manque — déclencheur : une SECONDE machine, ou une reconstruction subie) ;
S3/MinIO (les deux répliques partagent le même bind-mount sur le même hôte — déclencheur :
une seconde MACHINE) ; MLflow (déclencheur : la première décision de réentraîner) ;
dbt, Kafka, OpenSearch, pgvector, K8s, sharding (déclencheurs calculables d'ADR-014 et
ADR-023, relus le 2026-09-11, aucun tiré).

---

## 🧰 R117 — Le dépôt quitte `/mnt/c`, et VS Code passe en Remote-WSL

- [ ] **R117 — déplacer le dépôt sur ext4 et basculer l'éditeur en Remote-WSL.**

  **Ce qui a été mesuré le 2026-09-16**, à périmètre égal (6572 tests collectés des deux
  côtés, arbre git propre des deux côtés) et en ALTERNANCE :

  | | `/mnt/c` | ext4 (`~`) | rapport |
  |---|---|---|---|
  | collecte pytest (2 tours) | 27,1 s · 27,2 s | **4,8 s · 4,9 s** | **×5,6** |
  | suite complète `-n auto` | 372 s | **109 s** | ×3,4 |
  | écriture de 2 000 petits fichiers | 4,12 s | **0,06 s** | ×69 |

  ⚠️ **Deux mesures ont été JETÉES avant celle-ci**, et c'est la partie utile :
  la première comparait 6 571 tests à 6 572 (la copie ext4 n'avait pas `.git`, donc
  51 tests rouges — et un test qui échoue fait moins de travail) ; la seconde a révélé
  un vrai défaut au lieu d'un artefact (voir plus bas). Un rapport annoncé sur deux
  périmètres différents n'est pas un rapport.

  **La cause est structurelle, pas un réglage.** `/mnt/*` est monté par `drvfs`, qui
  parle **9P** — un protocole réseau. Chaque `open()` et chaque `stat()` devient un
  message sérialisé à travers la frontière VM/hôte. La littérature converge sur ~×7 en
  écriture de flux et **~×60 sur les métadonnées** ; pytest parcourant 375 fichiers de
  test et un `.venv` de 2,2 Go est du travail entièrement métadonnées.

  **Ce qui s'y ajoute sans mesure nécessaire** : Docker est natif WSL ici
  (`docker context` → `unix:///var/run/docker.sock`), donc les bind-mounts `src/` et
  `airflow/dags/` des conteneurs traversent 9P aujourd'hui ; l'éditeur aussi ;
  `git status`, `ruff` et pre-commit sont du pur métadonnées.

  **La contrepartie annoncée n'existe pas dans ce poste de travail.** L'état mesuré :
  `~/.vscode-server` existe (Remote-WSL a déjà servi), mais `VSCODE_IPC_HOOK_CLI` est
  ABSENT du shell et `which code` rend `/mnt/d/1_Logiciels/VS Code/bin/code` — le
  binaire Windows. VS Code tourne donc côté Windows et ouvre le dossier par `/mnt/c`,
  ce qui est exactement la combinaison lente. En Remote-WSL le serveur s'exécute DANS
  WSL : éditeur, terminal et Claude lisent ext4 en natif, et il n'y a plus aucun accès
  Windows → ext4. Bascule : `code .` depuis un shell WSL. Contrôle :
  `echo $VSCODE_IPC_HOOK_CLI` doit rendre une valeur.

  **Les trois pièges, rencontrés en fabriquant la copie de mesure** :
  1. **la mémoire de Claude est indexée par CHEMIN**
     (`~/.claude/projects/-mnt-c-Users-timot-Desktop-…`) — sans renommage du dossier,
     l'historique et les mémoires du projet sont perdus ;
  2. **les fichiers gitignorés ne suivent pas un `git clone`** — `.mcp.json`,
     `.env.local`, `config/config.yaml`, `data/`, `.venv` ; il a fallu trois
     allers-retours pour compléter la copie de mesure, dont quatre fichiers `assets/`
     à nom accentué ;
  3. **les conteneurs doivent être recréés une fois** ; `deploy.sh` et `migrate.sh`
     détectent le conteneur par NOM, donc eux suivent sans changement.

  **Pourquoi APRÈS R113–R116** : ces tâches touchent Caddy, les répliques et la
  production. Déplacer le dépôt au milieu mélangerait deux causes si quelque chose
  casse. R117 est réversible et sans urgence.

### Écarté dans la même séance, avec sa mesure

**Optimiser les rendus `AppTest`** — les dix fichiers les plus lourds font **62 %** du
temps (`test_views_render_smoke.py` 193,5 s à lui seul, 20,7 %), et le profil dit où va
le temps : `import streamlit.testing` **4,84 s** une fois par PROCESSUS, premier rendu
**12,54 s** (il importe toute l'application), rendus suivants **~2 s**. Ce n'est donc pas
« AppTest est lent », c'est un amorçage de ~17 s par worker.

Le remède canonique existe — **Humble Object** (Khorikov, *Unit Testing Principles*,
ch. 7 p. 155-180 ; SE@Google p. 308-311 sur les *fakes*) : rendre la vue une coquille
mince sur une fonction pure, tester la fonction vite, garder quelques rendus en fumée.

**Et il est refusé ici, sur la mesure inverse.** Les défauts que ces rendus ont attrapés
n'existent qu'AU RENDU, et 4 737 tests unitaires verts ne les voyaient pas : une vue vide
trouvée par l'artiste en une heure, deux causes racines de navigation passées à travers
3 755 tests verts, six défauts « du code correct que rien n'atteint ». `render_harness.py`
le dit déjà : *« ce dépôt attaque le temps d'ATTENTE, jamais la couverture de la porte »*.
Échanger 190 s contre cette classe de défauts serait un mauvais troc. **Le levier pour le
travail quotidien existe déjà et n'enlève aucune couverture** :
`python3 .claude/scripts/select_tests.py` (règle transverse #16).

---

## 🔖 REPRISE — état au 2026-09-16, cinq tâches ouvertes (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R120,R118,R121,R116,R117 -->

**Cinq tâches sont ouvertes** : R118, R120, R121, R116, R117.

R115 (l'instrument serveur) et R119 (réparer l'instrument client) sont livrées le
2026-09-16 ; leur détail est dans `archive.md`. R114 est livrée et déployée (`e859ae3`),
et **son résultat était AMBIGU** — c'est ce constat qui a ouvert R118 à R121. La
première mesure de l'instrument serveur a tranché : c'est la VUE qui domine, pas la
chrome, ce qui a réordonné R118 devant R120.

**L'ordre était contraint** : R115 (l'instrument) puis R119 (le réparer) AVANT toute
optimisation. **Les deux sont faites**, et la première mesure du nouvel instrument a
immédiatement inversé la suite (voir R120). Puis **R120, R118**, R121 (les causes), puis R116 (l'ADR), puis R117 (l'outillage).

⚠️ **L'ordre R118/R120 a changé DEUX FOIS le 2026-09-16, chaque fois sur une mesure**, et
les deux mouvements comptent. R118 est d'abord passée devant R120 : la mesure serveur
avait montré que la VUE domine la chrome (4,6× à 63×), ce qui invalidait la prémisse de
R120. Puis R120 est repassée devant : les trois pages les plus chères — `meta_mapping`
777 ms, `soundcloud` 515 ms, `home` 316 ms — **n'ont presque aucun filtre**, et un
fragment ne borne que le travail refait quand un filtre bouge. R118 garde donc ce qui
était mesurément cher (fait), et le reste attend d'apparaître dans l'histogramme.

⚠️ **Mode de travail : une étape à la fois, validée avant la suivante.**

⚠️ **Mode de travail convenu le 2026-09-16 : une étape à la fois, validée par le
propriétaire avant la suivante.** Ce n'est pas une précaution de style — R114 modifie le
reverse proxy de la production et R115 y ajoute deux conteneurs. Ne pas enchaîner deux
étapes sans retour. L'étape 0 (robustesse) et l'étape 1 (les
seaux d'authentification en base) sont livrées et commitées ; leur détail est plus bas.

R109 (découper la CI en 4 shards) et R110 (répartir le long pôle par `--dist loadgroup`)
sont livrées et déployées ; leur détail est dans `archive.md`.

**La table « 🙋 En attente de toi » reste vide** depuis le 2026-09-10, R1 y ayant été
rotée vers `archive.md`. Aucune tâche n'attend un geste humain.

**Livrées le 2026-09-15, déjà dans `archive.md`** : **R111** (le ménage de la CI —
apt mort, trois exécutions du même `--check`, l'étape `--fields` qui écrivait dans un
fichier suivi, l'artefact de couverture que personne ne télécharge, `-v` qui faisait
87 % du log) et **R112** (la sonde de production n'avait **rien exécuté pendant neuf
jours** — `pytest-xdist` manquant à une liste tenue à la main ; la production allait
bien, c'est l'instrument qui était cassé).

**Les rétrospectives datées du 2026-09-11 au 2026-09-13** — la coupure de courant, la montée en charge chiffrée, le graphique de l'accueil, l'audit metrics layer, la carte de la couche or et la vérification en production — **ont été rotées dans `archive.md` le 2026-09-16**, ce fichier ayant dépassé son plafond de 50 Ko. Elles y sont intégrales ; `tests/test_the_resume_header_is_checked.py` impose ce plafond parce que `/resume` lit ce fichier AVANT tout, à chaque session.

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.

| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |

### La méthode, pour R85 à R87

- **R85 (cache)** est sorti **BUILD-MODIFIED** d'une revue `code-critic`, avec un point
  bloquant : les cinq fonctions visées sont écrites pour *ne jamais lever et rendre
  vide*. Les cacher transformerait une panne passagère de base en « aucune donnée »
  faux pendant 600 s **pour tous les spectateurs**. Les quatre autres conditions :
  `views/onboarding.py:162` manque à la liste des appelants ; `apple_lifetime_plays`
  n'est pas dans l'ensemble enveloppé alors que c'est ce dont `apple_music.py` a besoin ;
  les imports de constantes ne doivent pas passer par le module caché ; et
  `upload_csv.py` doit purger — **fait le 2026-09-11**, c'était un défaut vivant.
  Le précédent à copier est `kpi_helpers` : `ttl=600`, `_db` hors clé, `artist_id`
  DEDANS, purge sur l'événement et pas sur l'horloge.
- **R86 (pool) est ÉCRIT, TESTÉ, MESURÉ — et personne ne l'appelle.** Le gain est
  réel : 20 cycles ouverture/fermeture font **0 poignée de main** au lieu de 20, soit
  ~40 ms sur un rendu de 287 en production, et `statement_timeout` survit au pool
  (mutations vues rouges sur les trois propriétés). Ce qui bloque est ailleurs et
  **n'est pas expliqué** : l'activer fait passer l'accueil de **13 à 23 requêtes SQL**,
  mesuré sur une base neuve, à l'identique contre `main`. Les dix en trop ne sont pas
  un surcoût mais une **section supplémentaire rendue** (matrice de mise en route,
  fraîcheur par source, sonde Meta). Suspect principal, non prouvé :
  `_ensure_connection()` appelle `conn.poll()`, qui sur une connexion RÉUTILISÉE peut
  lever `OperationalError` et déclencher un emprunt de plus. Reproduction : brancher
  `enable_pool(1, 8)` dans `get_db_connection()`, puis
  `pytest tests/test_a_page_asks_the_same_question_once.py` sur une base neuve.
  Tant que l'effet n'est pas expliqué, le chemin chaud de 43 vues + l'API + Airflow
  ne le reçoit pas.
- **R87 (répliques)** ne change aucune ligne d'application : 3 services, 3 upstreams, et
  **`lb_policy cookie` est obligatoire** (Streamlit tient un état serveur par websocket).
  Le compose de prod est gitignoré : modifier sur la boîte ET porter dans
  `docker-compose.example.yml`. Conséquence à accepter : le cache devient par réplique.
- **Mesurer, pas déduire** : `tools/loadtest_dashboard.py`, à lancer **sur le serveur**
  (il refuse `/mnt/…`, où DrvFS gonfle les temps de 5× à 160×). Il ne trace **pas** de
  courbe de concurrence et `--self-check` montre pourquoi : `AppTest` sature de lui-même
  sous threads, un `st.write('hello')` passant de 352 ms à 2 144 ms.

> Les trois sections du 2026-09-10 (audit transverse, R83, les sept tâches livrées
> plus tôt) ont été **déplacées** dans `archive.md` le 2026-09-13 : ce fichier avait
> franchi le plafond de 50 Ko que `/resume` lit à chaque session.

## 🙋 En attente de toi (aucune ne se débloque sans une action humaine)

Elles restent comptées comme ouvertes — rien n'est supprimé — mais elles ne sont pas dans
l'index ci-dessus parce qu'aucune ne peut commencer sans toi. Chacune dit exactement quel
geste elle attend.

📋 **Procédures pas à pas, avec leur vérification :
`.claude/dev-docs/runbook-actions-utilisateur.md`** — classées par ce qu'elles
débloquent, chacune avec la commande qui prouve que c'est fait. `tests/test_roadmap_index_is_honest.py`
échoue si une ligne d'ici n'a pas sa section là-bas.

| id | tâche | prio | le geste qu'elle attend |
|----|-------|------|--------------------------|

**Vide depuis le 2026-09-10.** La dernière — R1, ouvrir la bêta privée — est rotée dans
`archive.md` : le produit est prêt et revérifié en production ce jour-là, et ce qui reste
n'est pas de l'ingénierie mais l'usage du produit. Une roadmap mesure le travail à faire
sur le dépôt ; elle ne suit pas les gestes commerciaux de son propriétaire, sans quoi
elle ne peut par construction jamais atteindre zéro.

## 🔍 Ce que le graphe de code a sorti (2026-08-23)

Graphe régénéré après 71 jours de péremption (**5468 nœuds / 10691 arêtes / 689
communautés**, contre « 1500+ / 94 » annoncés). Trois constats l'ont justifié ; le
premier concerne l'outil lui-même.

**Le graphe référence 15 fichiers qui n'existent plus** (135 nœuds, 2 %) — `graphify
update` ajoute et ne retire pas. Parmi eux d'anciens modules devenus des paquets
(`views/trigger_algo.py`, `utils/pdf_exporter.py`) et un dossier `archive/` supprimé.
Comme `CLAUDE.md` désigne `GRAPH_REPORT.md` comme la première lecture « avant de
grepper », la mise en garde y est désormais écrite : le graphe **oriente**, il ne prouve
pas. Mon propre inventaire d'orphelins en a été contaminé avant vérification.

**`.claude/dev-docs/architecture.md` annonçait une dépendance inexistante** —
`error_handler.py | Utility | email_alerts`. `error_handler.py` n'est importé par rien
en production. Corrigé sur place.

## 🎨 Notes des tests artistes — ce qui reste (2026-08-23)

~30 notes de terrain (Benken 19/06, GRiNCH 12/08). Plan approuvé :
`~/.claude/plans/unified-mapping-teapot.md`. **Quatre tracks sur cinq sont livrés,
déployés et archivés** sous « R50 · R51 · R52 » et « R53 (1/3) ». Ne restent ici que la
suite de R53 et les questions auxquelles je ne peux pas répondre seul.

### Le fil commun, à relire avant de reprendre

La plupart des notes ne décrivaient **pas du code faux, mais du code correct que rien
n'atteignait** — six occurrences en une séance : la page d'onboarding hors navigation, les
étapes de l'accueil dont la clé de page était jetée, le sélecteur Mac/Windows branché sur
une fonction sans appelant, `secondary_analyses()` écrit le jour de la remarque et
appliqué sur aucune vue dense, les titres SoundCloud déclarés que le DAG n'atteignait
jamais, le PDF des identifiants livré seulement par e-mail.

**Un test de rendu ne dit jamais si une page est atteignable**, et un DAG qui saute un
locataire le journalise proprement. C'est pourquoi rien ne le signalait.

### Les questions, tranchées (2026-08-24)

Les quatre questions qui bloquaient du travail réel ont leur réponse. Deux ont
produit du code ; deux se règlent hors du dépôt, et le dire est la réponse.

**1. Meta multi-comptes : SÉPARÉS.** Chaque compte a son budget, son CPR, ses
campagnes ; un total les mélange sans le dire. C'est ce qui a décidé la forme des
clés d'unicité — voir **ADR-013**, qui traite dans la foulée la question née de
celle-ci : *faut-il faire pareil pour Spotify ?* **Non**, et la raison n'est pas le
volume de travail : ce qui est pluriel chez Meta, c'est l'identité du **payeur**
sous une credential unique ; chez Spotify, ce serait l'identité **artistique**, et
additionner les streams de deux alias ne décrit personne. Un deuxième projet est
déjà un deuxième locataire ; ce qui manquerait le jour où le besoin se présente,
c'est qu'une même connexion en possède plusieurs et bascule entre eux — brique de
comptes, aucune table métier touchée.

**2. Le sélecteur avant l'export PDF : livré**, avec la portée qui a un sens — le
**compte publicitaire**, dès qu'il y en a deux. Le PDF part à un tiers : un CPR qui
mélange deux annonceurs n'est le CPR d'aucun des deux, et le lecteur n'a aucun
moyen de s'en apercevoir. Côté profil d'artiste, il n'y a rien à choisir : le
rapport porte sur le locataire connecté (le sélecteur d'artiste reste admin).

**3. Le « taux de trigger » : trois taux, un par algorithme** — la part OBSERVÉE
des titres de la cohorte d'entraînement, dans ce panier de Popularity Index, qui
ont déclenché Discover Weekly / Release Radar / Radio (`threshold_tables.json`).
Aucun ne « fait foi » sur les autres. **Et le graphique mentait** : un panier dont
`prob` vaut `null` et `n` vaut 0 — aucun titre observé — était dessiné comme une
barre à **0 %**, que le lecteur lit « aucune chance de déclencher ». Cas réel :
Release Radar, panier « 50+ ». De même, 66,7 % mesuré sur **3** titres s'affichait
aussi net que 99,4 % sur 172. Corrigé : effectif écrit sous chaque barre, paniers
peu peuplés atténués, paniers jamais observés non dessinés.
Garde : `tests/test_an_empty_bracket_is_not_a_zero.py`.

**4. La « valeur de démo » : deux candidats trouvés et corrigés, la note d'origine
reste non confirmée.** Aucun KPI codé en dur n'existe dans le dépôt — vérifié.
Mais deux valeurs fausses étaient bien affichées : le compteur public « **N**
artistes utilisent streaMLytics », sur la page d'inscription, comptait **les
canaris que nous créons nous-mêmes** pour surveiller la collecte ; et le nom
d'artiste du **propriétaire de la plateforme** servait d'exemple dans le champ
« Nom d'artiste » de chaque inscription. Les deux sont corrigés parce qu'ils sont
faux, pas parce qu'on est sûr que c'était ça. Si la note visait autre chose, une
capture suffira. Garde : `tests/test_public_counters_count_humans.py`.

**5. Le GIF animé dans les messageries : il ne vient pas de l'application.**
Vérifié : **aucune** balise `<img>`, aucun `MIMEImage`, aucune URL d'image dans le
moindre corps de mail — les trois expéditeurs (`email_alerts`,
`verification_email`, `onboarding_report`) n'envoient que du texte et du HTML sans
ressource distante, pied de désinscription compris. C'est donc le relais (Brevo)
ou l'avatar du compte expéditeur affiché par la messagerie du destinataire —
exactement le même cas que le nom d'expéditeur « Music Cross Platform Dashboard »
tranché le 2026-08-23, qui venait du compte Brevo et écrasait celui du code. Geste
dans Brevo, § « En attente de toi ».


### Ce qui attend un fichier, pas une décision

- **Le CSV de Benj.** Les deux causes probables sont fermées — séparateur `;` (celui
  d'Excel FR) désormais supporté de bout en bout, et l'export « Depuis le début » refusé à
  la détection avec la vraie raison. **Sa cause à lui n'est pas confirmée** : quand le
  fichier arrive, le passer dans `_detect_platform` et corriger la règle qui l'a manqué.

### Une vérification que je n'ai pas pu faire

Le parcours **post-connexion** n'a pas été joué dans un navigateur, faute de compte de test
local : l'atterrissage première connexion sur l'assistant, les étapes cliquables et le
sélecteur d'OS sont couverts par des gardes AST, pas par un clic réel. À faire à la
prochaine session artiste.

---

## Open Bugs

- [x] **`/youtube/videos` API cassé (HTTP 500) — schema drift, MÊME CLASSE que `/kpis`** — sélectionnait `views/likes/comments/title` sur `youtube_video_stats` (vraies colonnes `view_count/like_count/comment_count`, pas de `title`). **FIXÉ** : requête sur `youtube_videos` (catalogue par-vidéo : title + view_count/like_count/comment_count). Mergé PR #62, déployé, `/youtube/videos` = **200** confirmé live. *(8 routers audités, youtube était le dernier cassé.)*
- [x] **Gap de test systémique = cause racine `/kpis` + `/youtube`** — les 2 bugs avaient échappé aux tests (routers testés **DB mockée**). **FIXÉ** : `tests/test_api_db_smoke.py` — smoke-test **DB-gated** (comme `test_views_render_smoke`) qui exécute chaque endpoint data contre le vrai schéma (token admin+tenant forgé) et assert no-500 → attrape toute la classe en CI. Aurait fait échouer /kpis ET /youtube.

**P3/P4 — correctness borderline :**
- [x] **2 collectors `return None`** ✅ (2026-06-14) — `youtube_collector.py:45` (chaîne introuvable) **escaladé en `raise ValueError`** (vrai échec → plus de 0-rows-DAG-SUCCESS) + test de non-régression `test_get_channel_stats_raises_on_channel_not_found`. `instagram_api_collector.py:294` (insights code-100, 1 média) **confirmé skip par-item légitime** (l'appelant filtre `None` L322) + commenté explicitement. `_meta_config_fetch.py:168 return []` = 0-créative valide, hors-scope.

**Mesuré & ÉCARTÉ (FP / non pertinent — ne pas re-auditer) :**
- Index `s4a_song_timeline(artist_id, song, date)` → **prématuré** : EXPLAIN ANALYZE = **0.4ms** sur 13794 lignes via l'index `(artist_id,date)` existant. Revisiter à ~10× volume.
- `API_SECRET_KEY` → **SET (64 chars) en prod** : JWT stables au restart, non-issue.
- Sweep schema-drift : 132 candidats bruts → **tous FP sauf le router youtube** (alias `col AS x`, vars f-string `{filt}/{frag}`, fonctions SQL, littéraux, commentaires FR, ON CONFLICT/EXCLUDED).
- Deps `uv.lock` **0 CVE** ; imports morts **0** (ruff F401) ; data-integrity (filtre 1x7 / scoping tenant / clés upsert) **clean** ; secrets git history **0**.

## Brick Status

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.

### Standing ops — incident-driven (no code action)

These are not roadmap bricks; they are operational standing instructions kept here for visibility.

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---

## Long-term ML hardening (roadmap)

- [x] **Phase-2 data acquisition — CLOSED AS MANUAL (2026-06-10, ADR-004).** The 2 ex-imputed features are now sourced from manual entry: `NonAlgoStreams28Days` → `s4a_song_nonalgo_streams`, `HowManySongsDoYouHaveInRadioRightNow` → `s4a_artist_radio_count` (migration 052), captured in the Saisie S4A form, read by `ml_inference.build_features` (default 0 when no entry). **Automatic capture rejected:** the artist confirmed S4A shows the source split on-screen only (no CSV export → parser+watcher impossible), and scraping the authed S4A UI is ToS-violating + per-tenant-credential-heavy + fragile (see ADR-004). **Reopen only if** Spotify exposes the split via a CSV export or official API → then a cheap DistroKid-style parser+watcher. 416 tests pass.
- [x] **Discovery Mode manual input** — DONE 2026-05-31. `migrations/040_s4a_song_discovery_mode.sql` (table mirrors `s4a_song_playlist_adds`: per-song dated opt-in, latest `recorded_at` wins) + `init_db.sql` + `_ALLOWED_TABLES`. `ml_inference.build_features` sources `IsThisSongOptedIntoSpotifyDiscoveryMode` from the latest manual entry (default 0.0). `trigger_algo` gains a "🔭 Discovery Mode" metric + manual opt-in form (after Ajouts playlist). Kept in `_IMPUTED_FEATURES` (drift-excluded) — bounded binary flag, z-score drift is meaningless. End-to-end verified (feature flips 0→1 on opt-in); render-smoke + 321 pytest green. Marginal SHAP weight (rank 13) but un-imputes one of the 3 sourceless features with zero external API.

---

## Pré-déploiement program (2026-06-09)

> Blocs livrés déplacés vers `archive.md`. Ce qui reste ouvert est ci-dessous.


## Deferred — revisit ONLY if migrating to React (ADR-003 reversal)

Items that are currently irrelevant / worked-around **because of Streamlit** and would become
natural (or need redoing) under a React/Next.js front-end. Parked here per user request
(2026-06-09) so a future migration picks them up. ADR-003 currently keeps Streamlit.

> **PARKED — not open backlog.** Listed as plain bullets (no `[ ]`) **on purpose** so `/resume`
> does not recount them as actionable items. They re-activate only on an ADR-003 reversal
> (migration to React/Next.js). Do not treat them as a to-do until then.

- **PostHog full client-side analytics** — autocapture, **session replay**, heatmaps,
  client funnels/retention. Blocked today: Streamlit strips `<script>` and sandboxes
  `components.html` iframes, and re-runs the whole script (no stable DOM / client event model).
  Under React the standard JS snippet drops in → reconsider PostHog (cloud-w/-consent or
  self-host) and likely retire the homegrown event log's *capture* layer (the `usage_events`
  table can remain as a server-side sink). Needs RGPD consent banner for a 3rd-party processor.
- **Interactive / exact-parity report charts (PDF & in-app)** — the PDF export rebuilds
  every chart in **matplotlib→PNG** (`pdf_charts.py`) because `kaleido` (Plotly→image) is absent
  and Streamlit can't headless-render its Plotly figures. Under React, reports could share the
  *same* chart components (client-side render / a proper reporting service), giving interactive
  + pixel-parity charts and removing the matplotlib duplication. ref: export-pdf overhaul
  2026-06-09.
- **Cold-start bundle / perf** — already audited (line ~295): the #1 cold-start bottleneck
  is the **Streamlit JS bundle** (~532 KiB), not Python. React+Next (code-splitting → ~100–150
  KiB initial) is the structural fix. Python-side caching/lazy-import work stays valid for
  subsequent renders only.
- **Rich client interactions** — anything that fought the rerun model (live event hooks,
  drag/drop, fine-grained widget state, real-time updates without full reruns) becomes
  first-class under React; revisit UX patterns that were simplified to fit Streamlit.
