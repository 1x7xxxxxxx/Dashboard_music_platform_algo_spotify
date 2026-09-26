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
| R197 | Audit de la gestion de la roadmap + sonde qui MESURE les actions de dev faites sans inscription préalable (et sans code-critic quand il était dû), intégrée au suivi de nuit ; améliorations proposées au propriétaire — demandé 2026-09-26 <!-- anchor: roadmap-health-probe --> <!-- critic: requis --> | P3 | `tests/test_the_roadmap_discipline_is_measured.py` |
| R198 | Le code-critic décidé PAR TÂCHE : chaque ligne d'index porte `critic: requis` ou `critic: non — raison` ; commit de code refusé si la ligne ne décide pas, ou si « requis » sans appel code-critic la nommant <!-- anchor: critic-per-task --> <!-- critic: requis --> | P3 | `tests/test_an_action_is_on_the_roadmap_before_it_runs.py` |
| R199 | Un seul chemin de rotation qui DÉPLACE vraiment : `make roadmap-close ID=Rnnn` retire la ligne, écrit le bloc livré (avec les commits qui citent l'id) en tête de l'archive, réaligne la reprise <!-- anchor: one-rotation-path --> <!-- critic: non — outil de doc, protégé par le test de conservation --> | P3 | `tests/test_the_roadmap_rotation_names_all_three_surfaces.py` |
| R200 | Alléger `checklist.md` : la prose d'historique (~95 %) déménage mot pour mot vers l'archive ; plafond de lignes de l'actif <!-- anchor: light-active-file --> <!-- critic: non — déplacement de texte, protégé par le test de conservation --> | P4 | `tests/test_the_resume_header_is_checked.py` |
| R201 | Retirer les 2 rappels redondants (`check_roadmap_update.py`, `draft_roadmap.py`) et corriger ~15 références périmées de la gestion de roadmap <!-- anchor: roadmap-stale-refs --> <!-- critic: non — retrait réversible et corrections de texte --> | P4 | `tests/test_roadmap_two_files.py` |

**Huit lignes y sont entrées le 2026-09-25 au soir**, toutes issues de l'audit de la
surveillance des classes d'erreur — détail dans « 🧭 R167 – R176 » juste sous cet index.
Trois en sont ressorties **livrées le même soir** (R167, R168, R174 — détail dans
`archive.md`, sous « 🧭 R167 · R168 · R174 ») et quatre autres plus tard le même soir,
tranchées par `d048a5a` (R170 à R173 — détail dans `archive.md`, sous
« 🧭 R170 · R171 · R172 · R173 ») ; **une reste ici** (R169).
Avant elles, l'index avait été vidé le 2026-09-25 : R165 (la CI rouge depuis le
2026-09-22) et R166 (le contrôle de santé de la prod qui n'arrivait à personne),
entrées le 2026-09-24 au soir toutes deux nées d'un déploiement qui n'a pas pu partir,
sont livrées — détail dans `archive.md`, sous « 🧯 R165 · R166 ».

**Cet index avait été vidé le 2026-09-23 après-midi** : R164, le reste mesuré du
balayage qui a corrigé l'effacement RGPD le même jour, y est entrée et en est ressortie
livrée le même après-midi. Il était vide le matin — R162, entrée le 2026-09-22 au soir
en mutant un garde neuf, est livrée le lendemain matin, son récit est dans
`archive.md`.

Vide à midi ; **R157, R158, R159, R160 et R161** y sont entrées par le travail de
l'après-midi, toutes nées d'une mesure prise ce jour-là et aucune d'une intuition ; les
cinq en sont sorties le soir même, livrées. Leur récit est dans `archive.md`.

⚠️ **Les paragraphes qui vivaient ici ont été retirés, et c'est le geste correct.** Ils
portaient les ARGUMENTS de décisions désormais prises — pourquoi R157 méritait une
décision de produit, pourquoi les 49 dates de R160 divergeaient. Une fois la décision
prise et la brique livrée, ces arguments décrivent un état qui n'existe plus : c'est
`un-document-qui-affirme-un-état-périmé`, et un écran de reprise en est la pire victime.
Ils sont conservés **verbatim** dans `archive.md`, avec leur mesure.

**Ce qui reste n'est pas de l'ingénierie.** Les deux lignes de « 🙋 En attente de toi »
attendent chacune un geste que personne d'autre que le propriétaire ne peut faire :
interroger trois artistes sur leur prix, brancher Hypeddit sur le pixel Meta au
lancement. Le côté outil des deux est **livré**, et chacune porte sa procédure et sa
preuve dans le runbook.

**Vérifié le même soir, pour que « vide » veuille dire quelque chose :**

| | état |
|---|---|
| index actionnable | **0 ligne** |
| `TODO` / `FIXME` / `XXX` réels dans `src/ airflow/ tools/ .claude/scripts/` | **0** — les 3 occurrences sont un compteur nommé « TODO counter » et deux docstrings qui DÉCRIVENT le motif comme un défaut |
| R116 · R131, parquées | conditions de réouverture **évaluées mécaniquement** à chaque `make night-check` — aucune remplie |
| suite | 9 496 verts |

---

Les sept lignes ouvertes le matin du 2026-09-22 — R146 à R152, nées des dix livres
ingérés ce jour-là — sont sorties par deux portes différentes, et la distinction est le
résultat de la matinée :

| | sortie | ce qui l'a tranchée |
|---|---|---|
| **R146** (P2) | ✅ livrée | la limite est écrite sur **seize grappes de surfaces** ; adosser une vraie écoute est impossible (S4A ne rend que des CSV) |
| **R147** | ✅ livrée | la courbe existe, et elle rend **3 essais arrivés à terme, 0 conversion** — un effectif dont aucun taux ne sort |
| **R149** | ✅ livrée | l'activation, mesurée à **2 sur 5**, posée en tête du panneau admin ; MRR et ARPU passent sous un repli |
| **R152** | ✅ tranchée | **ADR-028** : pas d'axe de valeur tant que l'activation n'est pas réglée, avec son déclencheur de réouverture |
| **R151** | 🚫 réfutée le 2026-09-23 | Meta a retiré le classement manuel des 8 évènements — détail dans `archive.md` |
| **R150** | ✅ livrée le 2026-09-23 | 150 / 300 / 550 €, posés en local et en production |
| **R148 · R163** | 📦 backlog produit | sorties de la roadmap le 2026-09-26 vers `.claude/dev-docs/product-backlog.md` — chacune avec son déclencheur ; on les rouvre quand il arrive |

⚠️ **Et une trouvaille qui n'était dans aucun livre**, tombée en lançant la suite :
douze modules de test construisaient leur DSN à la main. Sans base ils skippaient, avec
une base ils ERREURAIENT — **20 rouges d'un coup**, aucun lié au travail en cours. Les
douze passent désormais par la porte canonique, et **91 tests** qui ne s'exécutaient pas
s'exécutent. Classe : `a-second-door-that-knows-fewer-sources-than-the-first`.

**Ces lignes venaient des dix livres ingérés le 2026-09-22**, pas d'une intuition.
Chacune croise une phrase d'un livre avec un chiffre déjà mesuré sur ce dépôt — le détail
et la citation sont dans le bloc « 📚 R146-R151 » plus bas. Une ligne dont le livre ne
faisait que confirmer ce qu'on savait déjà n'y est PAS entrée.

**Une seule tâche est ouverte dans cet index depuis le 2026-09-25 au soir** (R169) — huit
y sont entrées ce soir-là, et R167, R168, R174 en sont ressorties livrées le même soir
(détail dans `archive.md`, sous « 🧭 R167 · R168 · R174 »), puis R170 à R173 tranchées plus
tard le même soir (détail dans `archive.md`, sous « 🧭 R170 · R171 · R172 · R173 »). R175,
qui attendait un geste humain (mots de passe mail UC7), est livrée le 2026-09-25 — détail et
preuve dans `archive.md`, sous « 🧭 R175 ». **R178**, entrée le même soir — le reste
trouvé par le balayage des frères qui a fermé R177 — est livrée le 2026-09-26 : détail et
preuve dans `archive.md`, sous « 🧵 R178 ». Avant elles, R165 et R166, qui l'occupaient depuis le
2026-09-24 au soir, sont livrées le 2026-09-25 ; leur récit est dans `archive.md`. R145
y est entrée et en est sortie le 2026-09-20 : ouverte sur une mesure en fin de séance,
close le soir même parce que le cliquet de la carte or a REFUSÉ la régression — et
qu'un plafond ne se desserre pas pour faire taire un garde qui a raison.
L'ancre `reprise:` nomme l'index ET les lignes en attente d'un geste humain — plus aucune depuis le 2026-09-26 (R183 livrée ; R148 et R163, là depuis le 2026-09-23, sorties vers le backlog produit) (R151 réfutée, R150 livrée, R163 entrée et R153 livrée ce jour-là). R177, entrée le 2026-09-25, est livrée le même soir (~23:55) — détail et preuve dans `archive.md`, sous « 🔒 R177 ». R182, entrée le 2026-09-26, est livrée le même jour — détail sous « 🧰 R182 » dans `archive.md`. R179, entrée le 2026-09-26 en attendant l'accord du propriétaire pour toucher un DAG de production, est livrée le même jour — détail et preuve dans `archive.md`, sous « 🐛 R179 ». La table « 🙋 En attente de toi »
plus bas est **vide** (R183 livrée le 2026-09-26 ; R148 et R163 sorties le même jour vers le backlog produit) ; elle avait été vide du 2026-09-20 au 2026-09-22. R140, R125 et R134 en
sont sorties le 2026-09-20 — les dix-sept décisions de la première tranchées et
intégrées, la deuxième faite par le propriétaire (33 lignes en production), la troisième
mesurée EN PRODUCTION et close sur son résultat.
⚠️ Cette phrase a porté « quatre » jusqu'au 2026-09-18 au soir, pendant que le
tableau juste en dessous DÉMENTAIT ce chiffre : la correction avait été écrite dans le
journal des mensonges sans être appliquée à la phrase qui le portait. Inviter la bêta est l'usage
du produit, pas du travail d'ingénierie — une roadmap qui suit les gestes commerciaux de
son propriétaire ne peut par construction jamais atteindre zéro.

⚠️ **Ce paragraphe a menti CINQ fois, et il a lui-même annoncé « trois » trop longtemps.**
Les chiffres ci-dessous sont des citations datées, pas l'état d'aujourd'hui.

| quand | ce qu'une phrase affirmait | ce qui était vrai |
|---|---|---|
| 2026-09-12 | « quatre tâches rouvertes » | les quatre closes, index **vide** |
| 2026-09-18 matin | l'index porte « quatre » · l'ancre « les nomme toutes les **trois** » | index à **cinq** — trois nombres pour une grandeur, dans une phrase |
| 2026-09-18 matin | « En attente de toi » **VIDE** | R125 y était depuis l'aube |
| 2026-09-18 après-midi | « porte **UNE** ligne » | **deux** — R140 venait d'entrer, par la même main qui venait de recaler la phrase voisine |
| 2026-09-18 soir | R140 « **quatre** décisions » | **dix-sept** — §16.1 à §16.17 |
| 2026-09-20 | *(aucun mensonge)* | R140 sort de la table, les deux phrases de comptage recalées **dans le même commit** — c'est la première rotation de cette table où le garde n'a rien eu à dire |

Les deux premières n'étaient gardées par rien. Les trois dernières le sont maintenant, et
chaque garde a été écrit APRÈS l'occurrence qu'il aurait attrapée :
`test_a_sentence_that_counts_rows_counts_the_rows_there_are` (les lignes d'une section),
`test_a_sentence_that_counts_the_open_index_counts_its_rows` (les tâches de l'index — la
phrase désigne la section par « cet index » et ne contient jamais son titre, donc le
premier lui était aveugle par construction), et
`test_a_row_that_counts_runbook_sections_counts_the_ones_there_are` (ce qu'une ligne dit
d'un AUTRE fichier).

Classe `a-prose-claim-that-cannot-be-verified`. La parade tient en une phrase : **quand
une phrase de ce fichier compte quelque chose, elle compte ce qui existe, et rien
d'autre** — et le paragraphe qui l'énonce n'y échappe pas, comme sa propre ligne « trois
fois » vient de le montrer.

---

## 🧭 R167 – R176 — l'audit de la surveillance des classes d'erreur (entrées le 2026-09-25)

**D'où elles viennent.** Trois explorations en lecture seule le 2026-09-25 au soir :
**23 surfaces de surveillance**, dont deux seulement font arriver un rouge dans la boîte du
propriétaire (le mail de 23 h d'`alert_monitor`, `prod-health.yml`). Et rien ne faisait
ENTRER une action dans cette roadmap : ~9 identifiées ce jour-là, 0 inscrite avant ce bloc.

**R167, R168 et R174 sont livrées le même soir** (`5a17b33`, `6a40f4b`) — détail et
preuve dans `archive.md`, sous « 🧭 R167 · R168 · R174 ». **R170, R171, R172 et R173
sont tranchées plus tard le même soir** (`d048a5a`) — détail et preuve dans
`archive.md`, sous « 🧭 R170 · R171 · R172 · R173 ». **R175 et R176 sont livrées le
même soir**, chacune par le geste humain qu'elle attendait — détail et preuve dans
`archive.md`, sous « 🧭 R175 » et « 🧭 R176 ». **R177 est livrée le même soir, ~23:55** —
Spotify, YouTube et Meta tournés, toutes les anciennes valeurs refusées (l'ancienne clé
YouTube supprimée dans Google Cloud par le propriétaire) — détail et preuve dans
`archive.md`, sous « 🔒 R177 ». Son balayage des frères a trouvé un reste hors de son
périmètre, ouvert séparément en **R178** et livré le 2026-09-26 — détail et preuve dans
`archive.md`, sous « 🧵 R178 ».

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
**14 jours** à `TRUE` — **2 en production le 2026-09-20**, et le chiffre écrit ici
disait « 0 » parce qu'il avait été relevé sur la base LOCALE. `make reopen-check-prod`
le remesure ; sans `PROD_SSH` le contrôle rend désormais INDÉCIDABLE plutôt qu'un chiffre
qui ne décrit rien. Elle n'attend aucun geste humain, seulement
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

## 🔖 REPRISE — état au 2026-09-25 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R197, R198, R199, R200, R201 -->

**Journée du 2026-09-22 : sept lignes ouvertes le matin, sept ouvertes le soir — mais
ce ne sont pas les mêmes.** Quatre closes (R146, R147, R149, R152), quatre migrées vers
la table des gestes humains (R148, R150, R151, R153), et **trois entrées l'après-midi**
(R157, R158, R159), chacune née d'une mesure prise ce jour-là.

**Trois unités livrées et poussées l'après-midi**, toutes trois dans `archive.md` :

| unité | ce qu'elle a fait | le chiffre |
|---|---|---|
| **R154** `1e092ad` | cinq listes des mêmes tables repliées sur `src/utils/source_registry.py` | 8 requêtes pliées, 7 → 10 cibles surveillées |
| **R155** `10a1d61` | dix écrans d'administration en **six sections**, sélecteur paresseux | la section des comptes : **23 requêtes → 1** |
| **R156** | les trois trous de balayage du catalogue d'erreurs, fermés | **411/411 verdicts lisibles, 0 muet, 0 jamais balayée** |

**Par où reprendre (2026-09-25)** : prod en ligne (`cf7c02a`). **R165 et R166 sont
livrées** — la CI a ses 5 jobs VERTS (run `36148664155`) et un rouge de `prod-health`
arrive désormais à une adresse lue (run `36149664083`) ; leur récit est dans
`archive.md`, sous « 🧯 R165 · R166 ». L'index actionnable est de nouveau vide ; ce qui
reste dans « 🙋 En attente de toi » (R148, R163) attend un geste humain, pas du code.

**État au soir du 2026-09-23** : l'index actionnable est de nouveau
**vide** — R157 à R162 sont livrées le matin, et R164, née l'après-midi du balayage qui
a corrigé le même jour l'effacement RGPD (portée dérivée du schéma) en rédigeant la
section Google de la politique de confidentialité, est livrée le même après-midi. Tout
ce qui reste est dans « 🙋 En attente de toi » : deux gestes que seul le propriétaire
peut faire, dont R163 qui attend le lancement. R151 est réfutée : le réglage Meta
qu'elle visait n'existe plus. R153 est livrée le même jour : le client OAuth Google est
créé et publié, et l'aller-retour a réussi en production.

**Le P2 est livré.** R146 : la conversion CAPI d'Hypeddit se déclenche quand l'auditeur
QUITTE le smart link, pas quand il écoute. Le balayage a trouvé **seize grappes de
surfaces** qui affichaient ce clic sous le nom de « résultat » — dont l'optimiseur qui
RECOMMANDE d'augmenter un budget, la tuile du premier écran, l'argumentaire
d'abonnement et le PDF envoyé par mail — et **six sites déjà honnêtes**, tous écrits la
veille dans un seul fichier. La forme correcte existait et n'avait pas voyagé ; elle
vit maintenant dans `src/dashboard/utils/proxy_disclosure.py`, à un seul endroit.

**Le chiffre qui recadre tout le reste**, mesuré en production le même jour et qui
n'était demandé par aucune des sept lignes : sur **quatre artistes bêta**, **un seul**
a une plateforme qui livre des données. Trois regardent un tableau de bord vide —
Cuzebo depuis **cent jours**. Leur `etl_run_log` ne porte aucun échec, il porte
`skipped` : ils n'ont jamais saisi d'identifiant de plateforme, et `alert_monitor` dit
explicitement que `skipped` n'est pas un signalement. Correct pour l'exploitation,
aveugle pour le commerce. C'est la réponse à R147 (0 conversion sur 3 essais), le motif
de R149 (l'activation est LA métrique) et la raison d'ADR-028 (pas d'axe de valeur
quand le revenu par client est nul parce qu'il n'y a pas de client).

**R151 est réfutée le 2026-09-23** : le classement manuel des évènements agrégés a été
retiré par Meta (annoncé en mai 2023), et les cinq pixels du compte n'ont reçu aucun
évènement en 28 jours. Détail dans `archive.md`.


**R125 est LIVRÉE le 2026-09-20**, par le propriétaire. La saisie humaine
`s4a_song_algo_outcomes` porte **33 lignes en production** ; elle en portait 0 depuis la
livraison de la brique 16, et rien ne le signalait — une table vide se lit comme « pas
encore de données ». Le défaut qui a retardé la saisie est capitalisé :
`a-confirmation-thrown-away-by-the-rerun-that-follows-it` — le bouton enregistrait
réellement, et `st.rerun()` jetait le rendu qui portait le `st.success()`. **23 sites**
de la même forme dans `src/dashboard/`, tous convertis à `flash()` / `show_flash()`.

**R135 est LIVRÉE le 2026-09-20, et sa prémisse était FAUSSE.** Elle annonçait une
divergence de type isolée (`soundcloud_tracks_daily.track_id`, `bigint` en prod contre
`character varying` en local). La mesure en a trouvé **44**, et la cause n'était pas
celle-là : `CREATE TABLE IF NOT EXISTS` n'applique RIEN sur une table qui existe déjà —
**55 occurrences** dans `init_db.sql`. Une colonne ajoutée là sans migration ne change
aucune base déjà créée, et le fichier décrit alors un schéma qui n'existe nulle part.
Cliquet posé à **43** divergences (migration 127 en a retiré une), avec sa non-vacuité
ajoutée le 2026-09-20 : plafond serré ET population plancherée à 560 colonnes / 58
tables. Classe : `a-create-if-not-exists-that-declares-nothing`.

**R116 a quitté l'index le 2026-09-17**, pas ce fichier : `daily_ops_metrics` ne porte qu'une ligne (`complete = FALSE`, percentiles de rendu tous `NULL`), donc la courbe qui doit trancher l'ADR-027 n'existe pas encore. Son bloc de détail — non coché, pas livré — reste **ici**, dans une nouvelle section `## ⏸️ R116` hors des deux tables d'index : `archive.md` est strictement passif (aucun item non coché n'y est admis — `test_the_archive_holds_nothing_actionable`), et R116 n'est ni livrée ni abandonnée. Son déclencheur de réouverture est la ligne `daily_ops_metrics` de `### Conditions d'attente` ci-dessous. Elle n'a donc plus de ligne dans l'index actionnable ni dans « 🙋 En attente de toi » — elle n'attend aucun geste humain, seulement du trafic — et pour cette même raison elle **sort de l'ancre**, qui ne porte que ce que les deux tables de ce fichier listent encore.

**R109, R110, R114, R115, R118 à R121 sont livrées** ; leur récit de mesure — dont les
deux réordonnancements de R118/R120, chacun sur une mesure — a été **déplacé verbatim
dans `archive.md`** le 2026-09-18, sous « Le récit de mesure de R114–R121 ». Il n'est pas
perdu : il n'appartient simplement pas à un écran qui répond « où j'en suis ».

**La table « 🙋 En attente de toi » est VIDE depuis le 2026-09-26** — R183 (le récap de production vers la boîte lue) y est entrée et en est sortie livrée le même jour, détail dans `archive.md` sous « 📬 R183 ». R148 et R163 en sont sorties le 2026-09-26 vers `.claude/dev-docs/product-backlog.md` (décision du propriétaire). R148 était entrée
le 2026-09-22 (R151 réfutée, R150 livrée et R153 livrée le 2026-09-23), et R163, entrée le
2026-09-23 : les gestes Hypeddit à faire au lancement. R175, R176 et R177, entrées le même soir
du 2026-09-25, en sont ressorties livrées le même soir — détail dans `archive.md`, sous
« 🧭 R175 », « 🧭 R176 » et « 🔒 R177 ». R179, entrée le 2026-09-26 (un DAG de production à
corriger sur ton accord), en est ressortie livrée le même jour — détail dans `archive.md`,
sous « 🐛 R179 ». Elle avait été vide pour la première fois le 2026-09-20, quand R140,
R125 et R134 en étaient sorties ; le vide a tenu deux jours.
⚠️ Vide ne veut pas dire « rien n'attend un humain » pour toujours : inviter la bêta est
l'usage du produit, pas du travail d'ingénierie, et cette table se remplira de nouveau.
⚠️ Ce paragraphe a menti TROIS fois, et la troisième a été attrapée par un GARDE — pas
par une relecture. Le 2026-09-19, en parquant R134, j'ai recalé la phrase de tête de
l'index et pas celle-ci ; `test_a_sentence_that_counts_rows_counts_the_rows_there_are` a
nommé le fichier, la ligne, le chiffre écrit et le chiffre réel. C'est la différence
entre une leçon et un garde : les deux premières occurrences ont coûté une lecture
humaine, la troisième a coûté une seconde.
⚠️ Les deux premières fois, sans garde. Il a
d'abord affirmé « reste vide … aucune tâche n'attend un geste humain » **vingt-cinq
lignes après avoir décrit R125 qui y est**. Corrigé en « UNE ligne », il est redevenu
faux à l'entrée de R140 quelques heures plus tard — par moi, qui avais recalé la phrase
de comptage de l'index et pas celle-ci.
C'est `a-prose-claim-that-cannot-be-verified`, et l'angle mort est nommable :
`test_no_prose_sentence_places_a_task_in_a_section_that_has_no_such_row` vérifie qu'un
IDENTIFIANT est dans la bonne section — jamais **combien** de lignes une section porte.
Une phrase qui compte n'est donc gardée par rien, et ce fichier en porte plusieurs.

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


#### Mesuré le 2026-09-17 — pourquoi `PYTEST_WORKERS` restera à 2, et ce qui le débloquerait

> ⚠️ **Rectifié le 2026-09-25, par une mesure.** Le raisonnement ci-dessous confond deux
> choses : les résidents sont DÉJÀ hors de `MemAvailable`, la réserve n'a donc à couvrir
> que ce qui peut GROSSIR pendant la suite. Les deux croissances de l'époque ont cessé
> d'être permanentes (n8n le dimanche seulement, modèle knowledge-rag déchargé après
> 10 min) ; la réserve suit désormais ce qui tourne (`tools/dev/pytest_workers.py`) et
> rend **4 workers** : 179–180 s contre 269 s à 2, creux de `MemAvailable` ≥ 4 278 Mo sur
> trois suites complètes alternées. Le texte qui suit reste comme trace de l'ancien calcul.

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

> Les trois sections du 2026-09-10 (audit transverse, R83, les sept tâches livrées
> plus tôt) ont été **déplacées** dans `archive.md` le 2026-09-13 : ce fichier avait
> franchi le plafond de 50 Ko que `/resume` lit à chaque session.

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

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
-- doit rendre 30 — **4 en production le 2026-09-20**
-- ⚠️ À mesurer EN PRODUCTION : `make reopen-check-prod PROD_SSH=…`. Le « 1 » écrit ici
-- venait de la base locale, et l'outil de réouverture faisait la même erreur jusqu'au
-- 2026-09-20 (il annonçait 5).
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

⚠️ **R148 vient après l'activation** : demander à
quelqu'un ce qu'il paierait pour un produit qu'il n'a jamais vu fonctionner ne mesure
rien — et au 2026-09-22, **un seul** artiste bêta sur quatre a une plateforme qui livre.

⚠️ **R125 est entrée le 2026-09-18, mesurée en PRODUCTION, pas supposée** :
`ml_song_predictions` porte **617 lignes**, `s4a_song_algo_outcomes` (la saisie humaine)
en porte **0**, et `ml_prediction_outcomes` **0**. Le DAG hebdomadaire
`ml_outcome_labeling` est actif et n'a **aucune entrée** dans `etl_run_log` : il apparie
les prédictions assez vieilles avec les écoutes réalisées saisies à la main, et il n'a
jamais rien à apparier. **Le jeu d'entraînement vivant n'accumule rien depuis la
livraison de la brique 16**, sans qu'aucune alerte ne le dise — une table vide se lit
comme « pas encore de données », jamais comme « personne n'a fait le geste ».

**Avant elle, la table était vide depuis le 2026-09-17.** R114 y a vécu jusqu'au 2026-09-17 : le geste demandé — les identifiants du bac à sable — a été fait, les quatre passes alternées ont tourné, et le **signal de décision n'a jamais tiré** (A ne perd aucun rerun, donc B n'a rien à supprimer). La réplique n'est pas adoptée, la production est remise à son état d'avant l'expérience, et le déclencheur de réouverture est un des deux seuils de `tools/scale_check.sh`. Rotée close dans `archive.md` ; détail humain au §14 du runbook.

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

---
