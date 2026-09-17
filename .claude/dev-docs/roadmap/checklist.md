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

**R123 a été livrée le 2026-09-17** (commit `5662e33`) : le nettoyage de portée session
passe au processus contrôleur plutôt qu'au worker. **R122 a été close le 2026-09-17**,
convertie en chantier gouverné par un cliquet automatique — voir `archive.md` pour le
détail des deux.

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

## 🔖 REPRISE — état au 2026-09-17, aucune tâche actionnable (à lire EN PREMIER au `/resume`)

<!-- reprise: open= -->

**R122 et R123 sont closes le 2026-09-17, toutes deux rotées dans `archive.md`.** R123
a été ouverte le 2026-09-17 par le balayage des frères de la course corrigée dans
`test_nothing_overwritten_is_lost` — deux nettoyages de `conftest.py` en portée session
s'exécutaient une fois PAR WORKER, `xdist_group` ne les couvrait pas — puis livrée le
jour même (commit `5662e33`) : le nettoyage passe désormais par le processus
contrôleur. R122 est close le même jour, convertie en chantier gouverné par un cliquet
automatique (`make error-health`, `test_the_error_class_health_only_improves.py`) —
détail des deux dans `archive.md`. R118 est close le 2026-09-17, réfutée sur sa propre
mesure (voir `archive.md`) — les cinq vues restantes vivent maintenant dans
« Conditions d'attente », pas dans l'index. **R117 est livrée le 2026-09-17** — les
deux moitiés (déplacement du dépôt sur ext4, bascule de VS Code en Remote-WSL) sont
faites et vérifiées, par cette même séance ; détail dans `archive.md`. Elle ne va plus
dans l'ancre ci-dessus, qui ne porte que ce qui reste ouvert.

**R116 a quitté l'index le 2026-09-17**, pas ce fichier : `daily_ops_metrics` ne porte qu'une ligne (`complete = FALSE`, percentiles de rendu tous `NULL`), donc la courbe qui doit trancher l'ADR-027 n'existe pas encore. Son bloc de détail — non coché, pas livré — reste **ici**, dans une nouvelle section `## ⏸️ R116` hors des deux tables d'index : `archive.md` est strictement passif (aucun item non coché n'y est admis — `test_the_archive_holds_nothing_actionable`), et R116 n'est ni livrée ni abandonnée. Son déclencheur de réouverture est la ligne `daily_ops_metrics` de `### Conditions d'attente` ci-dessous. Elle n'a donc plus de ligne dans l'index actionnable ni dans « 🙋 En attente de toi » — elle n'attend aucun geste humain, seulement du trafic — et pour cette même raison elle **sort de l'ancre**, qui ne porte que ce que les deux tables de ce fichier listent encore.

**R121 est close le 2026-09-17, mesurée et réfutée sur ses sept sites** (non pas
livrée) : les agrégations pandas coûtent 0,2–0,4 ms, le coût mesuré est la
construction des figures plotly (27–42 % du `show()`) — détail dans `archive.md`.

**R120 est close le 2026-09-17, réfutée par sa propre mesure** (non pas livrée) : le
détail des quatre affirmations fausses et de leur correction est dans `archive.md`.

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

**Vide depuis le 2026-09-17.** R117 y a vécu du 2026-09-17 au 2026-09-17 même — le
temps d'une séance longue — puis a été livrée (les deux moitiés, déplacement sur ext4
et bascule VS Code en Remote-WSL) et rotée dans `archive.md`. Avant elle, R1, ouvrir la
bêta privée, y était rotée le 2026-09-10 : le produit est prêt et revérifié en
production, et ce qui reste n'est pas de l'ingénierie mais l'usage du produit. Une
roadmap mesure le travail à faire sur le dépôt ; elle ne suit pas les gestes commerciaux
de son propriétaire, sans quoi elle ne peut par construction jamais atteindre zéro.

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
