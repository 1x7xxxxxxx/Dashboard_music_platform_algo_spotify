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
| R104 | La série de niveaux YouTube porte une RUPTURE DE MÉTHODE (+18 438 en une nuit le 2026-06-11, compteur de chaîne → somme par vidéo) que rien ne nomme | P2 | une requête sur `v_platform_levels` ne rend plus de croissance quotidienne supérieure à 100× le maximum observé de la plateforme, ou la rupture est annotée |
| R103 | `artist_first_look` importe `views.<nom>` au lieu de suivre la table de routage d'`app.py` — il rapporte 2 pages en ERREUR que le produit sert correctement | P3 | `make artist-firstlook-prod PROD_SSH=… ARTIST=1` ne rapporte plus `process_guide` ni `upload_csv` en ❌ |

**Deux tâches ouvertes**, R103 et R104, mesurées le 2026-09-12. R92 à R95, les quatre tâches de l'audit metrics layer du 2026-09-11, ont été
closes et rotées dans `archive.md`, comme R89, R90 et R91 avant elles (critère du
double axe écrit et six figures triées, légende devenue le filtre de sources, PDF doté
de la figure d'évolution multi-plateformes). Détail complet dans l'archive.

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

Deux chantiers restent, et aucun n'est une tâche : la réconciliation des fuseaux de
PUBLICATION (Spotify et Apple datent dans le leur ; 7,9 % des lignes YouTube changent de
jour selon celui qu'on retient) demande une décision écrite avant d'être engagée, et la
reprise des définitions encore recopiées se fait **au fil de l'eau** sous la règle de
livraison d'ADR-019 — son avancement se lit dans le cliquet du bronze, pas ici.

**R1** reste le seul geste humain, dans la section « 🙋 En attente de toi » plus bas :
inviter la bêta. Aucune ligne de code ne la débloque.

---

## 🔖 REPRISE — état au 2026-09-12 (soir), DEUX tâches ouvertes : R103, R104 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R103,R104 -->

### Le 2026-09-11 a chiffré la montée en charge, et démenti trois de mes chiffres

Question posée : combien d'utilisateurs simultanés, quel palier suivant, et que penser
du conseil « regarde star schema / Data Vault mais ne les mets pas en place ». Tout ce
qui suit est **mesuré dans le conteneur de production**, pas estimé.

| Mesure | Valeur |
|---|---|
| Rendu de page complète, caches chauds (12 rendus, 0 échec) | **p50 287 ms**, p95 345 ms |
| dont SQL (12 requêtes) | **103 ms — 39,5 %** |
| dont connexions (4 poignées de main × 13 ms) | **40 ms — 15,4 %** |
| dont plotly | **0,9 ms** |
| Part de tout le SQL venant de `platform_timeseries.py` | **88 %** |
| Base : taille / lignes / plus grosse table / locataires | 62 Mo / 111 008 / 34 078 / 8 |
| `EXPLAIN (ANALYZE, BUFFERS)` de l'agrégat le plus lourd | `shared hit=626`, **`read=0`** |

**Le mur est le GIL de Streamlit, pas la donnée.** Un seul processus, un seul upstream
Caddy, aucun pool. Plafond dérivé de p50 : **~12 utilisateurs actifs** à un clic toutes
les 5 s, ~24 à 10 s, ~49 à 20 s. `read=0` dit qu'il n'y a aucune entrée-sortie disque à
optimiser : la base tient entière dans `shared_buffers`.

**Le mentor a raison, et ADR-012 + ADR-018 disent pourquoi** : les deux choses que vend
le Data Vault — traçabilité des sources, historisation de ce qui change — sont déjà
achetées ici, moins cher. Le seul motif de Kimball dont ce dépôt aura besoin est la
**table de faits agrégée**, et son déclencheur est écrit plus bas.

**Trois chiffres démentis par la mesure** (le détail vit dans le DEVLOG) : « ~25-50
utilisateurs » venait d'un rendu de *vue* (61 ms) et non de *page* ; « plotly, 36
figures, le pire cas » vaut pour `trigger_algo` et pas pour l'accueil (0,9 ms) ; et
replier les trois appels à `v_platform_totals` en un seul rapporte **1,0 ms**, pas 20 —
le prédicat `platform = %s` élague déjà les autres branches. Mesurer a évité ce refactor.

### Le graphique de l'accueil — six symptômes, UNE cause (2026-09-11)

Signalés par l'artiste : cumulé incohérent pour YouTube et SoundCloud, mesures
« uniquement journalières » sur cette année / 12 mois / 90 j / 30 j, aucune donnée en
« Par période », idem par année et par semaine. Mesuré en production, artiste 1 :

| | Somme des points tracés | Total annoncé | Écart |
|---|---|---|---|
| Spotify | 165 065 | 165 065 | ×1,0 |
| YouTube | **136** | 118 334 | **×870** |
| SoundCloud | **77** | 23 563 | **×306** |

**Le mode « Cumulé » fait un `cumsum` de la série quotidienne.** Pour Spotify c'est
juste — le CSV S4A porte l'historique. Pour les deux autres, cette série est un ÉCART
de compteur : elle ne contient rien d'avant notre première collecte ni les trous. On
ne peut pas ré-intégrer une dérivée sans sa constante, et le compteur la donne.

La conséquence explique tout le reste : YouTube est mesuré **115 jours**, SoundCloud
**95**, contre **1 344** pour Spotify. Le plancher de seau (50 %, posé à raison) vide
alors les agrégats — au pas **annuel, YouTube garde 0 seau**.

Classe `cumulative-counter-drawn-as-its-own-history`. Le balayage a trouvé deux frères
dans le PDF (R89), déjà corrigés côté app et jamais reportés.

**Ce que ce défaut dit de l'architecture, et c'est le plus utile.** La couche or existe
et elle est juste : `v_platform_totals` (migration 097) donne 118 334, et la tuile le
lit. Le graphique la CONTOURNE — il prend une série de la couche argent, les écarts
quotidiens, et la ré-additionne pour fabriquer son propre total. Deux définitions du
même nombre sur un écran, ce qu'ADR-019 interdit.

**ADR-019 a couvert les totaux SCALAIRES, pas les séries.** La migration 097 avait
repointé les cinq surfaces qui calculaient *un nombre*. Une courbe cumulée fait la même
affirmation — son dernier point EST un total — et n'a jamais été comptée parmi elles.
Une couche or qui définit un total sans définir la série qui y aboutit laisse la
contradiction visible. R88 est donc énoncée comme une extension de la frontière, pas
comme la correction d'un mode : le premier énoncé empêche la classe de revenir, le
second ne corrige qu'une instance.

### L'audit metrics layer du 2026-09-11

Critère : Reis & Housley, *Fundamentals of Data Engineering* p. 482 — une **metrics
layer** est l'endroit, et le seul, où la logique métier est maintenue et calculée.
ADR-019 en est la version locale.

Inventaire mesuré — agrégats (`SUM`/`AVG`) posés sur une table de fait depuis une
surface d'affichage, hors couche or :

| plateforme | agrégats hors couche or |
|---|---|
| Spotify S4A | 33 |
| Meta Ads | 22 |
| Instagram | 3 |
| Apple | 2 |
| Hypeddit | 1 |
| Revenu | 1 |
| **YouTube** | **0** |
| **SoundCloud** | **0** |

**Ce ne sont pas 62 défauts.** Mesuré en production le même jour, ces surfaces
s'accordent : S4A rend 165 065 par quatre chemins, Instagram 1 525 par deux, la vue
revenu égale exactement ses trois sources. Ce sont 62 **risques** — rien ne garantit
qu'elles s'accordent demain, et le dépôt connaît le prix : trois totaux YouTube
incompatibles avant la migration 097, puis trois contradictions le 2026-09-11 (×5 630,
×887, ×151).

La couche or couvre aujourd'hui **3 métriques** : les écoutes (`v_platform_totals`,
migration 097), le revenu (`v_artist_monthly_revenue`), la dépense Meta
(`v_meta_spend_totals`, migration 101, déployée le 2026-09-11).

Le cliquet `tests/test_the_metrics_layer_only_grows.py` gèle ces huit plafonds : ils ne
remontent jamais, ils doivent rester SERRÉS (un plafond au-dessus du réel autorise
autant de régressions silencieuses), et les deux plateformes à zéro sont nommées
explicitement. Classe d'erreur `a-metric-computed-outside-the-metrics-layer`.

### La soirée du 2026-09-12 — la carte, et les deux défauts qu'elle a trouvés

R94 est close : les plafonds du cliquet des agrégats sont à **zéro sur les huit
plateformes**, et son préalable — « la couche or gagne-t-elle un grain temporel, ou
`platform_totals()` reste-t-il la porte unique ? » — est tranché par **ADR-022** : les
deux, en couches. Le grain descend en SQL (lisible par l'API, Airflow, `psql`), la porte
ne porte que la forme. Détail dans `archive.md`.

Ce qui a rendu la clôture possible n'est pas un correctif de plus, c'est **une carte** :
`.claude/dev-docs/gold-coverage.md`, générée par `make gold-coverage`, sans base et sans
horodatage. À sa PREMIÈRE exécution elle a trouvé deux défauts vivants que 5 200 tests
verts ne voyaient pas :

- **la page Créatives tombait** pour tout locataire multi-comptes (`column
  "ad_account_id" does not exist` × 3, `is ambiguous` × 2) — la migration 106 avait fait
  descendre une jointure dans une vue sans y emporter une colonne que trois `WHERE`
  filtraient. Prouvé contre la base, corrigé par les migrations 108/109, gardé par
  `tests/test_an_account_filter_names_one_column.py` (23 sites surveillés) ;
- **la tuile « Dépenses » de la page Meta Ads affichait le double** : 6 165,65 € pour
  3 087,82 € réels. `meta_insights_performance` porte deux générations de lignes —
  231 quotidiennes et 21 cumuls à vie d'un collecteur antérieur — et la page les sommait
  **en pandas**, donc aucun garde SQL du dépôt ne pouvait le voir. La leçon était écrite
  depuis des semaines dans un commentaire de `pdf_exporter/_collectors.py:329`. Un
  commentaire ne garde rien : le garde s'appelle
  `tests/test_a_total_is_computed_where_a_guard_can_see_it.py`.

### Ce que la seconde passe a fermé, et comment

Énumérer des trous n'est pas les fermer. Trois des six l'ont été le soir même, et
**aucun par une phrase** :

| compteur | avant | après | ce qui a fermé le trou |
|---|---|---|---|
| cliquets sans non-vacuité | 5 | **0** | un plancher sous la population de chacun |
| cliquets sans trace de mutation | 10 | **0** | dix mutations faites, dix messages lus |
| agrégats hors cliquet | 21 | **0** | 9 repointés, 12 DÉCLARÉS avec leur raison |
| classes d'erreur sans famille | 68 | **3** | cinq familles qui manquaient |

Trois mutations ont ÉCHOUÉ, et c'est la moitié la plus utile :

* retirer `{frag}` d'une requête bornée laisse
  `test_a_chart_is_bounded_by_the_period_it_announces` **vert** — il voit la fenêtre
  LIÉE, jamais la fenêtre APPLIQUÉE. Classe
  `a-guard-that-sees-the-binding-not-the-application`, livrée en `kind: manual`
  SANS signature : le défaut existe, donc aucune commande ne sort ≠ 0 dessus ;
* un second axe ajouté dans `utils/` laissait `test_the_visual_rules_only_tighten`
  vert — sa portée s'arrêtait à `views/`, et `utils/charts.py` portait un axe
  secondaire VIVANT, rendu par deux vues. Portée élargie, axe déclaré avec sa raison ;
* et un `git checkout` réflexe a détruit le travail non commité de
  `tools/dev/gold_coverage.py`. Troisième fois que ce dépôt l'enregistre.

### Ce que la mesure de « ce qui n'est gardé par rien » a rendu (2026-09-12, soir)

Le livrable disait ce qui existe, jamais ce qui n'est gardé par rien. Le tableau
**plateforme × famille** le dit maintenant, et il est passé de **19 cases vides à
zéro** le soir même — R102 close. Les cases n'ont pas été « remplies » : trois gardes
ont été écrits pour les questions que personne ne posait, et **deux défauts vivants
sont sortis en les écrivant**.

Une plateforme neuve ajoutera cinq cases d'un coup et fera rougir le cliquet.
Brancher une source sans la garder devient impossible en silence — c'est le seul
mécanisme qui l'empêche sans relecture humaine.

Deux trouvailles en le construisant :

* **Instagram** — `followers_count` est un NIVEAU (1 525 → 1 606) qu'aucun garde ne
  traitait comme un compteur. L'ajouter tel quel aurait produit un détecteur MUET :
  `MIN_ENTITIES = 3` est calibré sur des catalogues et Instagram a 1,0 entité par
  locataire et par jour. Le plancher est devenu un attribut de la cible.
* **Un facteur 3 049**, trouvé par un garde existant qui a rougi tout seul quand une
  collecte fraîche a fait qualifier l'artiste 471. Une collecte à 1 vidéo sur 200
  devenait la ligne de base des niveaux, et le pas demandé dégradait vers le jour où
  la dérivation par les niveaux est désactivée. Migration 112, seuil lu dans la
  distribution réelle. **La première version du correctif a été attrapée par un
  invariant écrit une heure plus tôt** — écart de 5 vues, nommé.

### La troisième passe a fermé les trois dernières

| compteur | départ | fin | ce qui l'a fermé |
|---|---|---|---|
| figures sans source établie | 15 | **7** | deux corrections du LECTEUR, pas du code |
| tuiles sans source établie | 18 | **11** | idem |
| couples bronze | 132 | **110** | `csv_exporter.py` déclaré : un export de lignes brutes n'est pas une dette |
| dbt | question ouverte | **tranchée** | ADR-023 |

Les deux corrections du lecteur valent d'être nommées, parce qu'elles disaient le
contraire de la vérité : `_QUERY.format(acct=…)` est un **littéral avec des trous**,
pas une requête dynamique — vingt-huit surfaces étaient déclarées `sql-dynamique`
alors que leur table se lit. Et le plafond de sauts est passé de 2 à 3 sur une
MESURE (2 → 27 indéterminées, 3 → 23, 4 → 23 : le quatrième cran n'apporte rien).
Un livrable qui déclare « je ne sais pas » là où il sait est aussi trompeur qu'un
livrable qui invente.

**Et le repointage a introduit un défaut, corrigé le même soir** : `_QUERY_CREATIVES`
reçoit désormais un fragment de compte `ma.`-aliasé alors qu'il lit une VUE, donc
`missing FROM-clause entry for table "ma"`. La troisième forme du même défaut, dans
le correctif des deux premières. Le garde la couvre maintenant, et il a fallu
suivre `TEMPLATE.format(acct=X)` pour la voir — le gabarit et l'alias vivent dans
deux fichiers qui ne savent rien l'un de l'autre.

**La roadmap n'a plus de tâche ouverte sur ce sujet.** Ce qui reste vit dans les
compteurs de `.claude/dev-docs/gold-coverage.md`, tous sous cliquet : sept figures,
onze tuiles et cinq figures PDF dont la source n'est pas attribuable — et le
document dit, pour chacune, POURQUOI.

### Vérification finale mesurée en production le 2026-09-12

| KPI | couche or | porte Python | courbe |
|---|---|---|---|
| Spotify — écoutes | 165 065 | 165 065 | — |
| YouTube — vues | 118 334 | 118 334 | 118 334 |
| SoundCloud — écoutes | 23 563 | 23 563 | 23 563 |
| Apple — plays | 3 718 | 3 718 | — |
| Apple — shazams | 1 772 | 1 772 | — |
| Revenu — total | 260,96 € | 260,96 € | — |
| Meta — dépense | 3 087,82 € | 3 087,82 € | — |
| Instagram — abonnés | 1 525 | 1 525 | — |

**Aucune divergence.** Trois plateformes à zéro agrégat hors couche or : YouTube,
SoundCloud, Apple.

**Deux écarts mesurés à NE PAS corriger, consignés pour qu'on ne les reprenne pas :**

- les breakdowns Meta ne couvrent que **76 %** de la dépense (2 348 € sur 3 088) — c'est
  Meta qui n'attribue pas tout à une dimension, la page le mesure et le dit désormais ;
- la vue revenu compte la **répartition SACEM brute** (43,06 €) et non le versement
  (`payout` 36,49 €, après TVA −14,67 et charges −6,90) — choix de définition, cohérent
  avec le brut distributeur. À trancher avec l'utilisateur, pas à « corriger » ;
- iMusician : 217,90 (rollup mensuel) contre 217,8895 (détail) — un centime d'arrondi.

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

### Ce que le 2026-09-10 a changé (l'audit transverse, huit tâches livrées)

**R75 à R82 sont livrées et rotées dans `archive.md`.** Elles portaient l'audit
transverse commandé ce jour-là : résilience API, vitesse Streamlit et ingestion,
robustesse des données, couche or/argent/bronze, cybersécurité, refactor, filtres,
méthode de tracé. Chacune avec son correctif, son garde dédié, et ses mutations vues
ROUGES avant écriture.

Trois d'entre elles ont rectifié leur propre énoncé, et c'est le résultat le plus
utile de la séance — une roadmap se périme comme un commentaire :

- les « 144 échecs Spotify » de R76 sont des `skipped` : quatre locataires n'ont pas
  déclaré d'identifiant. Le troisième état délibéré du journal, pas une panne ;
- les « 6 requêtes en double de l'accueil » de R79 avaient déjà été retirées par
  R64–R69. Le vrai compte du jour était 14 exécutions pour 13 questions, un seul
  doublon ;
- le « repère de progression manquant » de R81 aurait été une **régression** : ces API
  rendent des compteurs cumulés par entité, et relire chaque entité chaque nuit est la
  mesure elle-même.

Et R77 a été trouvée fausse-verte : son cliquet lisait 0 pendant que trois figures
portaient encore un axe secondaire, sous une forme Plotly que le prédicat ne voyait
pas. Septième instance de « la portée d'un garde est le défaut », la première sur un
cliquet écrit le jour même.

### R83 — la septième cause, trouvée en LISANT le PDF

Le dossier d'architecture annonçait « quatre horloges » comme la seule des sept causes
de l'audit restée entière. Elle n'était **dans aucune roadmap** : elle vivait dans une
ligne d'historique d'une classe d'erreur, là où personne ne la relit. Ouverte et close
le même jour — voir `archive.md`.

Deux choses en sortent, plus utiles que le correctif :

- **le chiffre que j'avais écrit était faux.** « 200 lignes sur 2 535 (7,9 %) changent
  de jour selon le fuseau » mélangeait deux ères sur une base locale. En production, sur
  l'ère actuelle : **0 sur 5 807** pour YouTube, **29** toutes plateformes confondues ;
- **le risque était à l'envers.** Le danger n'est pas de laisser ces dates tranquilles,
  c'est de les « corriger » : une harmonisation des fuseaux déplacerait 267 jours
  calendaires déjà justes d'une journée entière. Ce qui manquait n'était pas un
  correctif mais la DÉCLARATION — `src/utils/clocks.py`, ADR-021.

Le PDF, lui, annonçait « cause ouverte » sur trois suggestions dont **deux étaient déjà
livrées**. Un document généré se périme comme un commentaire.

**Un seul geste humain en sort** (il ne rouvre pas de tâche, il attend une main) :
basculer la production sur le rôle applicatif non-superutilisateur créé par R80 —
`APP_DB_PASSWORD='…' make db-app-role`, puis `DATABASE_USER=streamlytics_app` dans
l'environnement de prod et redémarrer. `make db-role-check` dit à tout moment sous
quel rôle l'application tourne.

### Ce que le 2026-09-10 a changé plus tôt (sept tâches livrées)

R64, R65, R66, R67, R68, R69 et R71 sont **livrées et rotées dans `archive.md`** —
correctif, garde dédié, mutations rouges avant écriture, suite complète verte à 4 804
tests. Détail dans l'archive ; ne reste ouvert de ce lot que **R70** (couches bronze /
argent / or, P4, ADR à écrire — voir la table ci-dessus).

Ce qui suit décrivait l'état au 2026-09-08.

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


## R103 — un diagnostic qui rapporte des pannes que le produit n'a pas

- [ ] `tools/artist_first_look.py` résout chaque page par la table de routage
      d'`app.py`, et non par `from src.dashboard.views.<nom> import show`.

**Mesuré le 2026-09-12**, en vérifiant un déploiement avec
`make artist-firstlook-prod PROD_SSH=root@… ARTIST=1` : le rapport annonce **2 pages
sur 6 en ERREUR** — `process_guide` (`ModuleNotFoundError`) et `upload_csv`
(`ImportError: cannot import name 'show'`). **Les deux pages fonctionnent.** `app.py`
les route ailleurs depuis la fusion du 2026-09-04 : `upload_csv` → `views.credentials`,
et `process_guide` a sa propre branche. C'est l'outil qui importe le module portant le
nom de la page, alors que le nom d'une page et le module qui la sert ont cessé d'être
la même chose.

**Pourquoi ça compte plus qu'un faux positif.** Cet outil existe pour répondre à « que
voit un artiste », et c'est le dernier contrôle avant de déclarer un déploiement sain.
Un diagnostic qui crie sur deux pages saines apprend à lire ses ❌ en diagonale — et le
jour où l'une est vraie, elle passe avec les deux autres. Le dépôt a déjà payé cette
forme : un garde `/kpis` dont les 28 assertions « pas de 500 » étaient toutes
satisfaites par des 401.

**La classe est nommée** : `a-diagnostic-that-reads-a-name-not-a-route`. Le correctif
durable n'est pas de mettre à jour deux lignes de la liste — elle se périmera encore au
prochain regroupement de vues — mais de faire lire à l'outil la SOURCE de vérité du
routage. Un garde doit alors rougir si une page listée n'est atteignable par aucune
branche d'`app.py`.


## R104 — une rupture de méthode dessinée comme une croissance

- [ ] Une croissance de niveau invraisemblable au regard de la distribution propre à
      la plateforme est traitée comme une DISCONTINUITÉ, pas comme une quantité.

**Mesuré en production le 2026-09-12, artiste 1**, après le signalement « filtre par
période, j'ai un pic à 18000 pour youtube alors que c'est faux » :

| | valeur |
|---|---|
| Niveau YouTube au 2026-06-10 | 99 778 |
| Niveau YouTube au 2026-06-11 | 118 216 |
| Croissance en une nuit | **+18 438** |
| Plus gros écart QUOTIDIEN de toute la série (116 points) | **7** |
| Médiane des écarts quotidiens | **1** |

Le pic est **réel dans les données et faux comme information**. Le 11 juin, la collecte
a changé de DÉFINITION : du compteur de CHAÎNE — qui plafonnait à 99 xxx et compte des
vidéos qui ne sont pas les siennes, prouvé ~10× faux le 2026-09-08 — à la somme des
compteurs PAR VIDÉO. Une rupture de méthode ne devient pas une quantité parce qu'on la
soustrait à la veille.

**Ce qui a été fait le 2026-09-12 :** le mode « Par période », seul à transformer cette
marche en un bâton de 18 438 attribué à un jour, a été retiré de l'accueil. C'est un
correctif d'AFFICHAGE — il cesse de déguiser la rupture, il ne la corrige pas. En
cumulé la marche reste visible, ce qui est honnête : une marche se lit comme une
discontinuité.

**Ce qui reste, et pourquoi ce n'est pas une retouche :** décider ce que vaut
l'historique d'avant le changement de méthode est une question de DÉFINITION. Trois
options, aucune gratuite — recaler l'ancien historique sur la nouvelle base (invente des
vues qu'on n'a pas mesurées), couper la série au 11 juin (perd sept mois), ou marquer la
discontinuité et refuser toute croissance qui la traverse (honnête, mais laisse un trou
dans les totaux par période qui l'enjambent).

La migration 112 connaît déjà la forme MIROIR — un relevé partiel n'est pas un niveau —
et son seuil est lu dans la distribution réelle. C'est le précédent à suivre : le
critère doit être mesuré sur la plateforme elle-même, jamais posé d'instinct.

⚠️ **À vérifier sur les autres locataires avant de trancher** : la même bascule a pu se
produire ailleurs, à d'autres dates. Un correctif calibré sur l'artiste 1 seul serait
un correctif pour une instance, pas pour la classe.
