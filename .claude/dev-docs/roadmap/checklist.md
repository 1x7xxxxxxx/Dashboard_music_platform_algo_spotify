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
| R122 | **ROUVERTE** — la revue des `guard_scope` : 297 classes sur 393 n'ont toujours pas de « ne couvre pas », et la récidive est repassée au-dessus du seuil que R122 s'était donné | P3 | `make reopen-check` → la ligne R122 doit cesser de dire `ROUVRIR` |

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

Onze tâches en sont sorties, **R72 à R82**, chacune avec la mesure qui l'a établie.
**Trois sont livrées et déployées le soir même** — R72 (le payeur ne choisit plus le
locataire à provisionner), R73 (Meta pesait 81 % de la nuit dont 424 s de sommeil
imposé), R74 (plus aucune attente illimitée, ni base ni HTTP). Les huit autres restent
ouvertes, chacune avec sa mesure : ce sont des chantiers, pas des retouches.

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

> **Ordre de travail arrêté le 2026-09-16** : R122 passe en DERNIER, délibérément et
> sans être bornée. Elle est du volume mesurable — **363 → 332 portées en 89 minutes**,
> soit ~16 h pour la colonne `guard_scope` seule, et deux autres colonnes derrière. Mise
> en tête, elle consommerait une séance entière sans qu'aucune autre tâche avance. Les
> quatre tâches au-dessus ont un critère de fin net ; elles passent d'abord.
> R117 devait fermer la marche, parquée pour la raison qu'elle **ne pouvait pas être
> faite par la séance qui la ferait** : elle déplace le dépôt hors de `/mnt/c`, donc
> elle tue le `cwd` et la mémoire de Claude, indexée par chemin. Elle s'est parquée
> au premier réveil de la séance longue, puis a été livrée le 2026-09-17 — détail
> dans `archive.md`.

## R122 — ROUVERTE le 2026-09-17 par sa propre condition · P3

**Elle n'a jamais été livrée, et il faut le dire clairement.** Close le 2026-09-17 non
pas terminée mais **convertie** : 4 `guard_scope` écrites sur ~300, son estimation propre
étant de **~16 h pour la seule colonne `guard_scope`**. Le reste avait été confié à un
cliquet — qui interdit la régression sans jamais combler.

**Ce qui la rouvre** : elle s'était donné une condition calculable — « rouvrir si
`ever_recurred_observed` repasse au-dessus de 47 ». Mesuré le 2026-09-17 : **49**. Et il
valait déjà **48** plusieurs heures avant, sans que personne le sache.

⚠️ **Le vrai défaut n'est pas le chiffre, c'est que rien ne le lisait.** Huit conditions
de réouverture étaient écrites dans la roadmap ; **aucune n'était évaluée**. Écrire un
déclencheur et le vérifier sont deux gestes, et seul le premier avait été fait. Corrigé
par `make reopen-check` (classe `a-reopening-condition-nothing-ever-evaluates`) — c'est
lui qui a rendu ce verdict.

### L'état exact, mesuré

| compteur | à la clôture de R122 | 2026-09-17 matin | 2026-09-17 soir | bougé |
|---|---:|---:|---:|---:|
| classes au catalogue | 378 | 393 | **394** | +17 |
| `scope_without_not_covered` | 300 | 297 | **0** | **−300** |
| `scope_on_a_shared_guard_…` | — | 24 | **15** | −9 |
| `seen_red_unknown` | 331 | 331 | **331** | **0** |
| `cause_unknown` | 241 | 241 | **241** | **0** |
| `ever_recurred_observed` | ≤47 | 49 | **49** | +2 |

**La colonne `guard_scope` est LIVRÉE le 2026-09-17** : les 394 classes déclarent toutes
au moins un geste voisin que leur garde ne couvre pas, chacune écrite en ouvrant
l'implémentation du garde. C'était le chantier chiffré à ~16 h par R122 elle-même.

⚠️ **Cela ne clôt pas R122, et il faut le dire avec le chiffre** : sa condition de
réouverture porte sur `ever_recurred_observed` (49, seuil 47), une mesure de RÉCIDIVE —
donc du passé observé, que rien d'écrit aujourd'hui ne fait baisser. `make reopen-check`
continue à juste titre d'afficher `ROUVRIR`.

⚠️ **Et `scope_without_not_covered` à 0 ne dit rien de la JUSTESSE des 394
affirmations.** Aucune n'est vérifiée mécaniquement, et ce dépôt a mesuré que 4 portées
sur 6 écrites avec soin étaient inexactes. Le compteur qui reste vérifiable est
`siblings_never_swept` (386) : il parle du PRÉSENT — où le même défaut vit déjà — et se
prouve en balayant.

### Ce qui reste, avec ce que chaque chose coûte VRAIMENT

Les deux trous restants ne se comblent pas en écrivant : ils se comblent en EXÉCUTANT.
C'est la raison pour laquelle ils n'ont pas bougé d'un iota en deux sessions, et la
nommer évite de les reprogrammer à l'aveugle une troisième fois.

| trou | valeur | ce que combler UNE entrée demande | pourquoi ce n'est pas du texte |
|---|---:|---|---|
| `cause_unknown` | 241 | ouvrir le site cité, lire, et trancher `read` / `measured` / `inferred` | 58 seulement citent un fichier ; **183 n'ont aucune ancre**, donc il faut retrouver la cause avant de l'étiqueter |
| `seen_red_unknown` | 331 | remettre le défaut, voir la signature sortir ≠ 0, la retirer, la voir sortir 0 | une date `seen_red` non observée est explicitement interdite par `/capitalise` — on ne peut pas l'écrire, seulement la mesurer |

⚠️ **Le raccourci a été cherché et il est FERMÉ par construction** : marquer les 183 sans
ancre en `cause_inferred` ferait monter un compteur crânté à 0, et la mutation nº 3 de
`tests/test_the_error_class_health_only_improves.py` est exactement celle-là — vue rouge
le 2026-09-16. Le dépôt refuse de convertir « je n'ai pas cherché » en progrès.

- [ ] **R122 — reprendre la revue des `guard_scope`, par LOTS, jusqu'à repasser sous le seuil.**

  Le travail utile n'est pas « écrire 297 champs ». C'est, pour chaque classe, **ouvrir
  l'implémentation du garde** et nommer un geste voisin qu'il n'atteint pas. Mesuré le
  2026-09-16 : sur six portées écrites avec soin, **quatre étaient inexactes**, toutes
  pour la même raison — le garde nommé avait été lu, les autres fichiers cités non.

  **Ordre de travail**, et il n'est pas opportuniste : la famille `le-locataire` d'abord.
  Elle récidive à **33,3 %**, soit 3,4× la plus grosse famille, et c'est elle qui a coûté
  les deux sessions de test artiste ratées.

  ⚠️ **Ne pas viser un compteur.** Une portée écrite pour faire baisser un nombre est
  exactement ce que `/capitalise` interdit : elle affirmerait une couverture sans l'avoir
  lue, et une affirmation de couverture fausse est pire qu'un trou déclaré, parce qu'elle
  fait cesser de chercher.

  **Mesuré par** : `make reopen-check` — la ligne R122 doit cesser de dire `ROUVRIR`.

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

---

## ⏸️ R116 — ADR-027, en attente de ses courbes (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux
index. Sortie de l'index actionnable le 2026-09-17 parce que `daily_ops_metrics` ne
porte qu'**une seule ligne** (2026-09-16), `complete = FALSE`, et **tous ses
percentiles de rendu sont `NULL`** — seul `peak_sessions = 8` est renseigné. La
courbe que R116 exige, `streamlytics_rerun_duration_seconds` côté serveur, n'existe
donc pas encore ; le bloc le disait déjà lui-même : « un ADR écrit avant la mesure
serait une rationalisation ». Déclencheur de réouverture, calculable, dans
`### Conditions d'attente` ci-dessous, ligne « Écrire **ADR-027** (répliques et
Redis) » : `SELECT count(*) FROM daily_ops_metrics WHERE complete` doit rendre
**14 jours** à `TRUE` (aujourd'hui : 0). Elle n'attend aucun geste humain, seulement
du trafic — elle ne va donc pas dans « 🙋 En attente de toi » — et pour la même
raison elle sort de l'ancre de reprise en tête de fichier, qui ne porte que ce que
les deux tables d'index de ce fichier listent encore.

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

## 🔖 REPRISE — état au 2026-09-17 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R122 -->

**R116 a quitté l'index le 2026-09-17**, pas ce fichier : `daily_ops_metrics` ne porte qu'une ligne (`complete = FALSE`, percentiles de rendu tous `NULL`), donc la courbe qui doit trancher l'ADR-027 n'existe pas encore. Son bloc de détail — non coché, pas livré — reste **ici**, dans une nouvelle section `## ⏸️ R116` hors des deux tables d'index : `archive.md` est strictement passif (aucun item non coché n'y est admis — `test_the_archive_holds_nothing_actionable`), et R116 n'est ni livrée ni abandonnée. Son déclencheur de réouverture est la ligne `daily_ops_metrics` de `### Conditions d'attente` ci-dessous. Elle n'a donc plus de ligne dans l'index actionnable ni dans « 🙋 En attente de toi » — elle n'attend aucun geste humain, seulement du trafic — et pour cette même raison elle **sort de l'ancre**, qui ne porte que ce que les deux tables de ce fichier listent encore.

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

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


#### Mesuré le 2026-09-17 — pourquoi `PYTEST_WORKERS` restera à 2, et ce qui le débloquerait

`PYTEST_DIST` vaut `-n $(PYTEST_WORKERS)`, avec
`workers = (MemAvailable_Mo − 5120) / 700`, borné à `[2, nproc]`. La constante de
réserve avait été écrite le matin même après **deux morts par OOM en une heure**,
sans être confrontée au pic réel. Elle l'a été :

| ce qui a été mesuré | valeur |
|---|---|
| suite complète à `-n 2`, creux de `MemAvailable` | **991 Mo consommés** (3 918 → 2 927) |
| donc par worker | **~495 Mo** — la formule en budgète 700, soit ×1,4 de marge |
| résidents au repos | RAG **1 548** · Airflow+PG **1 686** · serveur VS Code **1 089** · `claude` **449** = **4 772 Mo** |
| RAM totale de la WSL | 9 945 Mo (plafond `.wslconfig`, hôte 15,7 Gio) |

**La réserve de 5 120 Mo n'est donc pas arbitraire : elle vaut à peu près ce que les
résidents pèsent (4 772 Mo mesurés).** Et elle explique l'OOM : à 8 workers,
8 × 495 = 3 960 Mo de suite + 4 772 de résidents = 8 732 Mo sur 9 945. La baisser
rendrait l'OOM, elle ne rendrait pas des workers.

**Le levier est donc les RÉSIDENTS, et il manque 68 Mo.** Le troisième worker demande
`MemAvailable ≥ 7 220`. En libérant le RAG (1 548) et Airflow (1 686) :
3 918 + 3 234 = **7 152 Mo** — à **68 Mo** du seuil. Arrêter en plus un serveur MCP
inutilisé (`chrome-devtools` 89 Mo, `graphify` 90 Mo) ferait basculer.

**Ce qu'on ne fait pas** : courir après ce troisième worker. Le gain attendu est
178 s → ~145 s, soit ~33 s sur une suite qu'on lance quelques fois par jour, contre
l'obligation d'éteindre Airflow — dont on a justement besoin pour que ~160 tests ne
skippent pas. Motif d'ADR-007.

⚠️ Deux mesures de cette séance sont **invalides et ne doivent pas être recitées** :
la somme des `VmHWM` des processus pytest (**194 Mo**, le motif `pgrep` ratait les
workers `execnet`) et les trois bancs mémoire du serveur RAG, dont le dernier rendait
*moins* de mémoire avec préchargement que sans. Seul le creux de `MemAvailable` est
fiable ici.

| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Chercher un 3ᵉ worker pytest en baissant la réserve mémoire | `MemAvailable` au repos dépasse durablement **7 220 Mo** SANS éteindre Airflow — c'est-à-dire si le RAG paresseux tient sa promesse (`ps -eo rss` sur `knowledge-rag` après un redémarrage de session) |
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |
| Écrire **ADR-027** (répliques et Redis) | `daily_ops_metrics` porte **14 jours `complete = TRUE`** : `SELECT count(*) FROM daily_ops_metrics WHERE complete` — **aujourd'hui 0**. La table a UNE ligne (2026-09-16), `complete = FALSE`, et **tous ses percentiles de rendu sont `NULL`** ; seul `peak_sessions = 8` est renseigné. La courbe qui doit trancher — `streamlytics_rerun_duration_seconds` côté serveur, et `streamlytics_reruns_in_flight` pour la saturation — n'existe donc pas encore. Le bloc de R116 le disait lui-même : *« un ADR écrit avant la mesure serait une rationalisation »*. Ce n'est pas du travail en retard, c'est du temps et du trafic |
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

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

📥 **Erreurs applicatives non triées : 1** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=1 -->

## ⏸️ R131 — Calibrer les trois seuils de charge (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux index.

**Pourquoi elle sort de l'index actionnable** : elle demande de dériver trois seuils sur
une distribution, et la distribution n'existe pas. Mesuré le 2026-09-17 :
`daily_ops_metrics` porte **1 ligne en production** (2026-09-17) et 2 en local. Il en
faut 30. Aucun geste ne la débloque — seulement du trafic et du temps —, donc elle ne va
pas non plus dans « 🙋 En attente de toi ».

Écrire les seuils maintenant serait exactement le défaut que la règle interdit : le dépôt
porte déjà **cinq** seuils sans dérivation (disque 85 %, RAM 500 Mo, sauvegarde 25 h,
watchdog 26 h / 48 h), plus le 20 de `scale_check.sh`, posé face à un pic observé de 12
sans que le facteur 1,7 soit justifié.

**Déclencheur de réouverture, calculable** :

```sql
SELECT count(*) FROM daily_ops_metrics WHERE day > now() - interval '30 days';
-- doit rendre 30 (aujourd'hui : 1)
```

- [ ] **R131 — les trois seuils de charge, dérivés d'une distribution et non d'un instinct.**

| règle différée | ce qu'elle surveillerait | la grandeur qui existe déjà |
|---|---|---|
| `SessionsHigh` | la charge utilisateur | `streamlytics_sessions_1m`, `daily_ops_metrics.peak_sessions` |
| `ErrorRateHigh` | une pointe d'erreurs | `streamlytics_app_errors_total`, `errors_by_page` |
| `LogErrorBurst` | une pointe de journaux ERROR | `streamlytics_log_records_total{level="ERROR"}` |

⚠️ Les quatre alertes livrées le 2026-09-17 ne portent **aucun** seuil — `absent()`,
`up == 0`, `read_ok == 0`. Elles couvrent le silence des instruments, pas la charge. Les
deux questions sont distinctes et la seconde attend ses données.

---

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

**La table est de nouveau vide depuis le 2026-09-17.** R114 y a vécu jusqu'au 2026-09-17 : le geste demandé — les identifiants du bac à sable — a été fait, les quatre passes alternées ont tourné, et le **signal de décision n'a jamais tiré** (A ne perd aucun rerun, donc B n'a rien à supprimer). La réplique n'est pas adoptée, la production est remise à son état d'avant l'expérience, et le déclencheur de réouverture est un des deux seuils de `tools/scale_check.sh`. Rotée close dans `archive.md` ; détail humain au §14 du runbook.

Avant elle, R124 y a vécu du 2026-09-17 au
2026-09-17 même : le geste demandé a été fait (session authentifiée en production), et
il a **réfuté** la tâche elle-même — l'instrument enregistre, 28 séries mesurées — plutôt
que de la livrer ; rotée close dans `archive.md`. Avant elle, R117 y a vécu la même
journée, livrée (les deux moitiés, déplacement sur ext4 et bascule VS Code en
Remote-WSL) et rotée dans `archive.md`. Avant elle, R1, ouvrir la bêta privée, y était
rotée le 2026-09-10 : le produit est prêt et revérifié en production, et ce qui reste
n'est pas de l'ingénierie mais l'usage du produit. Une roadmap mesure le travail à faire
sur le dépôt ; elle ne suit pas les gestes commerciaux de son propriétaire, sans quoi
elle ne peut par construction jamais atteindre zéro.

## 🔁 Consignes permanentes — ce ne sont PAS des tâches

Rien ici ne se coche, ne se livre ni ne s'archive : ce sont des gestes à faire le jour
où un évènement les déclenche. Ils vivent dans le fichier actif pour être relus, pas
pour être finis.

⚠️ Titre corrigé le 2026-09-17. Il s'appelait « Brick Status » et annonçait « ce qui
reste ouvert est ci-dessous » — deux affirmations fausses : aucune brique n'y figurait
depuis des mois, et rien de ce qui suit n'est ouvert au sens de la roadmap. Un lecteur
qui cherchait l'état des briques lisait une liste de secrets à faire tourner.

### Rotation des secrets — sur incident seulement (aucune action de code)

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---
