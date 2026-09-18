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
| R135 | **`soundcloud_tracks_daily.track_id` : `bigint` en PRODUCTION, `character varying` en local** — mesuré le 2026-09-18 colonne par colonne (1187 contre 1196). Le canonique est le VARCHAR : le collecteur écrit `str(track.get('id'))` (`soundcloud_api_collector.py:222`) et aucune migration ne déclare ce type. ⚠️ **Conséquence aujourd'hui : aucune** — les quatre lecteurs ne comparent jamais cette colonne à une chaîne, et Postgres transtype les identifiants numériques des deux côtés. Elle apparaîtra à la première jointure ou comparaison sur `track_id` : la prod rendra un `int` là où le local rend une `str`, donc **un test vert ici échouera là-bas**. La vue or `v_soundcloud_track_latest` hérite du type de chaque côté. Demande un `ALTER` sur une table vivante — décision du propriétaire, pas un effet de bord de séance | P3 | la comparaison des deux schémas ne doit plus nommer `soundcloud_tracks_daily.track_id` |

**Une tâche est ouverte dans cet index** — R135 —
et l'ancre `reprise:` les nomme toutes, dans cet ordre. La table « 🙋 En attente de toi »
plus bas porte **trois** lignes : R125, qui attend un geste humain dans l'app, R140,
entrée le 2026-09-18, qui attend **dix-sept** décisions de PRODUIT (§16.1 à §16.17 du
runbook), et R134, parquée le 2026-09-19 faute de données locales à calibrer.
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

## 🔖 REPRISE — état au 2026-09-18 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R135, R125, R140, R134 -->

**R125 est entrée le 2026-09-18, et elle n'attend qu'un geste de trois minutes.** Mesuré
en production : `ml_song_predictions` porte 617 lignes, `s4a_song_algo_outcomes` (la
saisie humaine) en porte 0, `ml_prediction_outcomes` 0, et le DAG hebdomadaire
`ml_outcome_labeling` n'a aucune entrée dans `etl_run_log`. **Le jeu d'entraînement du
scoring n'accumule rien depuis la livraison de la brique 16**, et rien ne le signale :
une table vide se lit comme « pas encore de données ». Procédure au §15 du runbook des
gestes humains.

**R135 est entrée le 2026-09-18, mesurée contre la production.** La comparaison des deux
schémas (1187 colonnes contre 1196) nomme une divergence de TYPE :
`soundcloud_tracks_daily.track_id` est `bigint` en prod et `character varying` en local.
Rien ne casse aujourd'hui — Postgres transtype les identifiants numériques — et c'est
exactement pourquoi elle a survécu. Elle apparaîtra à la première comparaison sur cette
colonne : **un test vert ici échouera là-bas**.

**R116 a quitté l'index le 2026-09-17**, pas ce fichier : `daily_ops_metrics` ne porte qu'une ligne (`complete = FALSE`, percentiles de rendu tous `NULL`), donc la courbe qui doit trancher l'ADR-027 n'existe pas encore. Son bloc de détail — non coché, pas livré — reste **ici**, dans une nouvelle section `## ⏸️ R116` hors des deux tables d'index : `archive.md` est strictement passif (aucun item non coché n'y est admis — `test_the_archive_holds_nothing_actionable`), et R116 n'est ni livrée ni abandonnée. Son déclencheur de réouverture est la ligne `daily_ops_metrics` de `### Conditions d'attente` ci-dessous. Elle n'a donc plus de ligne dans l'index actionnable ni dans « 🙋 En attente de toi » — elle n'attend aucun geste humain, seulement du trafic — et pour cette même raison elle **sort de l'ancre**, qui ne porte que ce que les deux tables de ce fichier listent encore.

**R109, R110, R114, R115, R118 à R121 sont livrées** ; leur récit de mesure — dont les
deux réordonnancements de R118/R120, chacun sur une mesure — a été **déplacé verbatim
dans `archive.md`** le 2026-09-18, sous « Le récit de mesure de R114–R121 ». Il n'est pas
perdu : il n'appartient simplement pas à un écran qui répond « où j'en suis ».

**La table « 🙋 En attente de toi » porte TROIS lignes** : R125 et R140, entrées le
2026-09-18, et R134, parquée le 2026-09-19 faute de données locales à calibrer.
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
| R125 | Saisir les écoutes 28 j réalisées (DW / RR / Radio) pour au moins un morceau, dans **Saisie S4A** | P3 | ouvrir Saisie S4A, entrer les trois chiffres à 28 jours pour un morceau prédit il y a plus de 28 jours — voir §15 du runbook |
| R140 | Trancher **dix-sept décisions de produit** trouvées par le balayage R137 — dont un appariement de titres trop large dans le PDF, un jeton SoundCloud partagé entre dev et prod, `/health` qui dit « ok » sans rien vérifier pendant que trois systèmes en font un verdict, le digest hebdomadaire qui somme deux générations (6 165 € au lieu de 3 088), et vingt dates affichées en UTC sans qualificatif | P2 | lire les dix-sept mesures et dire pour chacune ce que le produit DOIT faire — voir §16.1 à §16.17 du runbook |
| R134 | **Étendre le détecteur de creux au-delà de ses 5 tables** — il ne voit ni Instagram, ni Apple, ni Hypeddit, ni SACEM. L'outillage est LIVRÉ (`make dip-calibrate` + le garde qui refuse un seuil non dérivé) ; il bute sur la donnée : **0 table sur 8 calibrable localement**, la mieux fournie n'ayant que 12 % de jours couverts | P3 | lancer `make dip-calibrate` **contre la base de PRODUCTION** et me renvoyer sa sortie — voir §17 du runbook |

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
