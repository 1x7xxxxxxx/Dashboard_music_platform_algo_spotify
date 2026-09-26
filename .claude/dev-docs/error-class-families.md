# Familles de classes d'erreur

<!-- GÉNÉRÉ par `tools/dev/error_class_families.py` — toute édition à la main est perdue à la prochaine exécution. `make error-families` -->

**419 classes**, regroupées en **18 familles** par une règle explicite, écrite sous chaque titre. Aucune entrée de `.claude/dev-docs/error-classes.md` n'est modifiée : le catalogue est append-only, cette taxonomie vit à côté.

Une famille porte une **question**, pas un mot-clef. La question est ce qui a de la valeur : elle se pose devant du code, avant que le défaut existe. Une classe rejoint la **première** famille qui la retient — l'ordre va du plus spécifique au plus général, sinon « deux surfaces, deux nombres » avalerait la moitié du catalogue.

⚠️ **La colonne `récidive` est ce qui décide de l'ordre de travail**, pas la colonne `classes`. Mesuré : la plus GROSSE famille récidive 3,5× moins que la plus douloureuse. Elle est calculée ici, à chaque régénération, précisément parce que les taux qui servaient à prioriser vivaient en prose et se sont périmés — un chiffre figé fait prioriser sur le passé.

Le rattachement est mécanique et donc parfois discutable. La règle est publiée pour qu'on puisse le contester sans lire le script : si une classe est mal rangée, c'est le motif qu'on corrige, jamais l'entrée.

| famille | classes | récidive | la question |
|---|---|---|---|
| [le-locataire](#le-locataire) | 21 | **8/21** · 38.1 % | Cette lecture, cette écriture, cette jointure nomment-elles leur locataire — toutes, et pas seulement la première ? |
| [un-cumul-pris-pour-un-quotidien](#un-cumul-pris-pour-un-quotidien) | 12 | **1/12** · 8.3 % | Cette colonne est-elle une quantité du jour ou un compteur qui ne redescend pas ? Et si c'est un compteur, la fenêtre est-elle `niveau(fin) − niveau(début)` ? |
| [un-travail-qui-n-arrive-nulle-part](#un-travail-qui-n-arrive-nulle-part) | 24 | **5/24** · 20.8 % | Ce résultat atteint-il quelqu'un ? Ce code est-il appelé par quelque chose qu'un humain peut déclencher ? |
| [un-nombre-affirmé-qui-n-a-pas-été-mesuré](#un-nombre-affirmé-qui-n-a-pas-été-mesuré) | 32 | **3/32** · 9.4 % | Ce chiffre a-t-il été mesuré, ou construit ? Le lecteur peut-il distinguer « zéro » de « on ne sait pas » ? |
| [le-message-parle-au-mauvais-lecteur](#le-message-parle-au-mauvais-lecteur) | 20 | **0/20** · 0.0 % | Cette phrase s'adresse-t-elle à qui la lira — et nomme-t-elle un geste que ce lecteur-là peut faire ? |
| [un-état-qui-déborde-de-sa-portée](#un-état-qui-déborde-de-sa-portée) | 26 | **1/26** · 3.8 % | Cet état vit-il exactement le temps de ce qui l'a créé — ni plus, ni pour quelqu'un d'autre ? |
| [deux-surfaces-deux-nombres](#deux-surfaces-deux-nombres) | 25 | **5/25** · 20.0 % | Ce nombre a-t-il une seule définition, ou chaque surface refait-elle le calcul ? |
| [une-erreur-avalée-devient-une-absence](#une-erreur-avalée-devient-une-absence) | 23 | **2/23** · 8.7 % | Ce `except` distingue-t-il « rien à lire » de « on n'a pas pu lire » — et l'utilisateur voit-il la différence ? |
| [un-garde-qui-ne-garde-pas](#un-garde-qui-ne-garde-pas) | 62 | **9/62** · 14.5 % | Ce garde a-t-il déjà été VU rouge sur le défaut qu'il vise — et sa portée contient-elle ce défaut ? |
| [un-document-qui-affirme-un-état-périmé](#un-document-qui-affirme-un-état-périmé) | 35 | **6/35** · 17.1 % | Ce qui est écrit là est-il régénéré, ou recopié une fois puis oublié ? |
| [un-contrôle-qui-ne-peut-jamais-passer](#un-contrôle-qui-ne-peut-jamais-passer) | 13 | **0/13** · 0.0 % | Où ce contrôle s'exécute-t-il — la machine où il tourne a-t-elle ce qu'il lui faut pour réussir un jour ? |
| [un-coût-payé-sans-contrepartie](#un-coût-payé-sans-contrepartie) | 16 | **1/16** · 6.2 % | Ce travail est-il payé par quelqu'un — temps de CI, premier écran, attention du lecteur — et lui rend-il quelque chose ? |
| [un-seuil-écrit-d-instinct](#un-seuil-écrit-d-instinct) | 11 | **0/11** · 0.0 % | Ce seuil vient-il de la distribution réelle, ou d'une intuition ? Le test épingle-t-il la réalité ou la constante ? |
| [une-écriture-qui-écrase](#une-écriture-qui-écrase) | 7 | **1/7** · 14.3 % | Cette écriture peut-elle détruire ce qu'un autre vient d'écrire — et le saurait-on ? |
| [le-temps-et-l-horloge](#le-temps-et-l-horloge) | 19 | **0/19** · 0.0 % | Cette date est-elle celle de l'événement ou celle de la collecte ? Et dans quel fuseau ? |
| [la-frontière-avec-le-dehors](#la-frontière-avec-le-dehors) | 26 | **3/26** · 11.5 % | Ce que ce code envoie dehors — un mail, une requête, un paiement, un secret — est-il ce qu'on croit, et vers qui ? |
| [une-configuration-qui-diverge-de-la-prod](#une-configuration-qui-diverge-de-la-prod) | 43 | **4/43** · 9.3 % | Ce que le dépôt déclare est-il ce que la production exécute ? |
| [l-instrument-ment-sur-ce-qu-il-mesure](#l-instrument-ment-sur-ce-qu-il-mesure) | 4 | **0/4** · 0.0 % | Ce que cet instrument AFFICHE est-il ce qu'il a mesuré ? |
| _sans famille_ | 0 | — | — |

## le-locataire

**Cette lecture, cette écriture, cette jointure nomment-elles leur locataire — toutes, et pas seulement la première ?**

Règle de rattachement : `tenant|artist[_-]id|saas_artist|multitenant|fleet|canary|sandbox|deux locataires|par locataire|du locataire|son locataire|le locataire|d'un locataire|leur locataire|chaque locataire|un locataire|locataires? multi|aux locataires` sur l'identifiant et le symptôme. 21 classe(s).

| classe | symptôme |
|---|---|
| [`a-shared-database-read-while-another-test-writes-it`](error-classes.md#a-shared-database-read-while-another-test-writes-it) | un test est **rouge dans la suite complète et vert quand on le relance seul**. Le rapport ne montre rien d'anormal, la valeur attendue est simplement  |
| [`view-session-adoption`](error-classes.md#view-session-adoption) | a view uses raw `get_db_connection()` + the manual `get_artist_id()` guard instead of the `view_session()` context manager. The manual form is correct |
| [`multitenant-dag-fleet-poisoning`](error-classes.md#multitenant-dag-fleet-poisoning) | a collector/processing DAG iterates `get_active_artists()` and a per-tenant `raise` (or a precheck that raises on ANY incomplete artist) is NOT caught |
| [`multitenant-mono-test-blindspot`](error-classes.md#multitenant-mono-test-blindspot) | every smoke/integration test runs with `artist_id=1` only → a bug that appears only for tenant #2 (per-tenant SQL scoping, NULL handling, missing iden |
| [`connection-test-proves-app-not-tenant`](error-classes.md#connection-test-proves-app-not-tenant) | a "Test the connection" button validates the **platform's shared admin app** (Spotify client_credentials, YouTube API key, Meta `/me`, SoundCloud OAut |
| [`tenant-identity-falls-back-to-admin`](error-classes.md#tenant-identity-falls-back-to-admin) | a per-tenant IDENTITY (`user_id`, `channel_id`, `account_id`, `ig_user_id`, `spotify_artist_id`) resolves to an environment variable, a hardcoded defa |
| [`dag-trigger-without-tenant-scope`](error-classes.md#dag-trigger-without-tenant-scope) | a dashboard action triggers a DAG without `conf={'artist_id': …}`. The API collectors then run fleet-wide, and the CSV watchers — which defaulted to ` |
| [`column-name-is-not-its-meaning`](error-classes.md#column-name-is-not-its-meaning) | a sweep, a migration or a guard treats every column sharing a NAME as sharing a MEANING. In this schema `artist_id` is the tenant (INTEGER) on ~55 tab |
| [`identity-claimed-by-two-tenants`](error-classes.md#identity-claimed-by-two-tenants) | two artists declare the same platform identity (SoundCloud user_id, YouTube channel, Meta ad account, Spotify artist). Nothing refuses it. Both accoun |
| [`identity-mirrored-but-written-once`](error-classes.md#identity-mirrored-but-written-once) | a tenant shows as connected on every screen, passes its connection test, and collects nothing. The DAG succeeds in under a second. |
| [`canary-tenant-unwatched`](error-classes.md#canary-tenant-unwatched) | every global freshness light is green while every real artist collects nothing. |
| [`an-exemption-on-one-surface-reads-as-a-failure-on-another`](error-classes.md#an-exemption-on-one-surface-reads-as-a-failure-on-another) | une fonctionnalité reste vide pour un locataire, et le message d'explication — pourtant mesuré et exact — se termine par « rien à faire de ton côté ». |
| [`a-truncated-read-recorded-as-a-complete-one`](error-classes.md#a-truncated-read-recorded-as-a-complete-one) | la collecte d'un locataire s'enregistre `success`, et une partie de ses données n'a pas été lue. L'artiste voit un historique amputé sans que rien ne  |
| [`artist-id-or-1`](error-classes.md#artist-id-or-1) | `get_artist_id() or 1` coerces an unhydrated session onto artist 1 → cross-tenant data leak (CLAUDE.md rule #7). |
| [`an-account-filter-that-names-no-single-column`](error-classes.md#an-account-filter-that-names-no-single-column) | une page tombe — pas un chiffre faux, une exception — et **seulement chez les locataires multi-comptes**. `column "ad_account_id" does not exist` ou ` |
| [`a-late-platform-has-no-tenant-guard`](error-classes.md#a-late-platform-has-no-tenant-guard) | une plateforme arrivée tard dans le produit n'est couverte par AUCUN garde de tenance. Aucun symptôme visible — jusqu'au jour où une lecture sans `art |
| [`exempt-row-hides-others-conflict`](error-classes.md#exempt-row-hides-others-conflict) | une recherche d'unicité trouve une ligne EXEMPTÉE, s'arrête donc là, puis retire l'exemptée du résultat — et répond « aucun conflit » alors que deux l |
| [`write-without-explicit-artist-id`](error-classes.md#write-without-explicit-artist-id) | an upsert payload omits the `artist_id` key on a tenant-scoped table. `upsert_many` derives the INSERT column list from the payload keys (`postgres_ha |
| [`upsert-transfers-row-ownership`](error-classes.md#upsert-transfers-row-ownership) | an upsert whose `conflict_columns` is a global PLATFORM id carries `artist_id` in its `update_columns`. Two tenants touching the same object do not ge |
| [`dag-conf-honoured-by-one-task-only`](error-classes.md#dag-conf-honoured-by-one-task-only) | a per-tenant trigger from the dashboard (`conf={'artist_id': …}`) scopes the first task of a DAG and runs the next one over the whole fleet. Nothing f |
| [`suite-runs-against-one-tenant`](error-classes.md#suite-runs-against-one-tenant) | the whole suite is green, CI is green, and multi-tenant defects ship anyway. They surface later, in front of a real artist, as "connected but no data" |

## un-cumul-pris-pour-un-quotidien

**Cette colonne est-elle une quantité du jour ou un compteur qui ne redescend pas ? Et si c'est un compteur, la fenêtre est-elle `niveau(fin) − niveau(début)` ?**

Règle de rattachement : `cumulative|counter|compteur|delta|lifetime|two-generations|snapshot` sur l'identifiant et le symptôme. 12 classe(s).

| classe | symptôme |
|---|---|
| [`cumulative-counter-drawn-as-its-own-history`](error-classes.md#cumulative-counter-drawn-as-its-own-history) | la courbe « Cumulé » et la tuile de la même plateforme, sur le MÊME écran, donnent deux totaux. Mesuré en production le 2026-09-11 pour l'artiste 1 :  |
| [`two-generations-of-rows-in-one-fact-table`](error-classes.md#two-generations-of-rows-in-one-fact-table) | un total affiché vaut **le double** du même total lu ailleurs, sans qu'aucune requête soit fausse. Mesuré le 2026-09-12 : la tuile « Dépenses » de la  |
| [`a-quantity-mistaken-for-a-counter`](error-classes.md#a-quantity-mistaken-for-a-counter) | l'erreur SYMÉTRIQUE de celle qui a coûté un facteur 151 — traiter une quantité du jour comme un compteur cumulé. Le report en avant inventerait des vi |
| [`a-first-bucket-declared-unknown-when-it-was-observed`](error-classes.md#a-first-bucket-declared-unknown-when-it-was-observed) | la figure totalise MOINS que ce que le compteur a gagné, sans qu'aucun message ne le dise. Mesuré sur un locataire réel le 2026-09-12 : **182 432 dess |
| [`a-counter-drawn-from-zero-before-anyone-was-looking`](error-classes.md#a-counter-drawn-from-zero-before-anyone-was-looking) | une bande de plateforme est **plate à zéro pendant des années**, puis saute d'un coup au niveau du compteur. Mesuré le 2026-09-12 sur « depuis le débu |
| [`a-rule-that-was-right-for-quantities-applied-to-counters`](error-classes.md#a-rule-that-was-right-for-quantities-applied-to-counters) | la famille. Une règle écrite pour une quantité du jour — « la somme du seau », « zéro avant la première mesure », « le total de la période » — est app |
| [`two-shapes-summed-as-one`](error-classes.md#two-shapes-summed-as-one) | un total est faux d'un facteur qui ressemble à un vrai chiffre. Aucune exception, aucune ligne perdue : deux grandeurs de NATURES différentes ont été  |
| [`a-cumulative-counter-charted-as-a-daily-figure`](error-classes.md#a-cumulative-counter-charted-as-a-daily-figure) | une courbe « par jour » affiche des valeurs absurdes et plates, ou un pic vertical isolé. Aucune erreur : le graphique a l'air d'un graphique. Signalé |
| [`an-aggregate-counter-is-not-the-sum-of-its-parts`](error-classes.md#an-aggregate-counter-is-not-the-sum-of-its-parts) | un chiffre affiché est faux d'un facteur cinq à dix, sans erreur ni trou. Signalé le 2026-09-08 : « les données de YouTube sont fausses, voici celles  |
| [`a-bucket-sums-deltas-instead-of-deriving-the-counter`](error-classes.md#a-bucket-sums-deltas-instead-of-deriving-the-counter) | un agrégat de période sur une plateforme à COMPTEUR vaut une fraction de la réalité, et la bande devient invisible. Mesuré en production le 2026-09-11 |
| [`a-partial-collection-becomes-a-baseline-level`](error-classes.md#a-partial-collection-becomes-a-baseline-level) | une figure sous-déclare d'un facteur **3 049**. Mesuré le 2026-09-12 sur l'artiste 471 : « par semaine » totalisait 11 053 écoutes là où le compteur Y |
| [`a-stack-that-mixes-two-baselines`](error-classes.md#a-stack-that-mixes-two-baselines) | une série disparaît d'un graphique empilé alors qu'elle y est bien tracée. Elle n'est ni absente ni à zéro — elle est ÉCRASÉE, parce qu'une série vois |

## un-travail-qui-n-arrive-nulle-part

**Ce résultat atteint-il quelqu'un ? Ce code est-il appelé par quelque chose qu'un humain peut déclencher ?**

Règle de rattachement : `never-sent|not-alerted|never-read|nothing-happens|nothing-routes|nobody-call|never-hit|not-when-it-is-needed|nobody-writes|no-mechanism|rebuilt-per-rerun|thrown-away|unwired|debranch|not-reached|orphan|registered-twice-kills-the-import|referenced-but-never-declared|dangling|nothing-ever|never-evaluat|jamais évalué` sur l'identifiant et le symptôme. 24 classe(s).

| classe | symptôme |
|---|---|
| [`a-declared-agent-whose-trigger-cannot-fire`](error-classes.md#a-declared-agent-whose-trigger-cannot-fire) | un agent est déclaré dans `.claude/agents/` et nommé par une règle de `CLAUDE.md`, donc il se lit comme une couverture — et personne ne le lance jamai |
| [`a-promise-with-no-mechanism-behind-it`](error-classes.md#a-promise-with-no-mechanism-behind-it) | l'interface promet, au futur et à la voix passive, une action qu'aucun code n'exécute — « ils **seront appliqués** avant votre prochain cycle de factu |
| [`finding-rendered-but-not-alerted`](error-classes.md#finding-rendered-but-not-alerted) | a monitoring check runs, finds a real problem, writes it to xcom — and no alert is ever sent. The dashboard of checks looks complete; the inbox stays  |
| [`map-key-unreachable-by-construction`](error-classes.md#map-key-unreachable-by-construction) | a config dict carries an entry no caller can ever select. The behaviour it declares never runs, and the file reads as though the feature exists. Measu |
| [`detector-written-and-never-called`](error-classes.md#detector-written-and-never-called) | a function exists whose docstring names an error class, it has unit tests, and nothing in production calls it. The catalogue and the module both read  |
| [`stopped-collecting-is-not-a-status-anyone-reads`](error-classes.md#stopped-collecting-is-not-a-status-anyone-reads) | a tenant whose collection worked and then stopped produces no signal anywhere. The credential is valid, rows exist from before, the DAG reports SUCCES |
| [`the-feature-is-wired-to-the-function-nobody-calls`](error-classes.md#the-feature-is-wired-to-the-function-nobody-calls) | une fonctionnalité est écrite, traduite, complète — et ne s'affiche nulle part. Aucun test ne tombe : la fonction qui la rend existe et fonctionne, el |
| [`the-feature-exists-and-the-path-never-reaches-it`](error-classes.md#the-feature-exists-and-the-path-never-reaches-it) | un utilisateur ne peut pas faire une chose que le produit sait faire. La fonctionnalité est écrite, testée, documentée — et le chemin qui y mène s'arr |
| [`mermaid-block-does-not-render`](error-classes.md#mermaid-block-does-not-render) | un diagramme s'affiche en boîte d'erreur, ou pas du tout, chez le lecteur — et rien ne rougit, parce que rien dans le dépôt ne rend du markdown. |
| [`page-that-nothing-routes-to`](error-classes.md#page-that-nothing-routes-to) | une vue rend parfaitement, son test de rendu est vert, elle figure dans une liste intitulée « ce qu'un artiste peut atteindre » — et aucun artiste ne  |
| [`a-surface-reads-a-table-nobody-writes`](error-classes.md#a-surface-reads-a-table-nobody-writes) | un panneau de tableau de bord reste vide sans rien dire. La table qu'il lit existe, le SQL est valide, et personne ne l'écrit. |
| [`an-identifier-that-is-referenced-but-never-declared`](error-classes.md#an-identifier-that-is-referenced-but-never-declared) | **une interface entière rend « No data », et rien n'est en erreur.** Aucun journal ne se plaint, la source de données répond, les requêtes sont justes |
| [`pipeline-writes-to-the-copy-nobody-reads`](error-classes.md#pipeline-writes-to-the-copy-nobody-reads) | an automated capture → validate → publish loop runs, reports success, and produces nothing anyone sees. Each stage is individually correct; the output |
| [`unregistered-write-table`](error-classes.md#unregistered-write-table) | a table passed as a literal to `upsert_many`/`insert_many` is absent from `_ALLOWED_TABLES` (postgres_handler) → the SQL-injection allowlist raises a  |
| [`revocation-written-but-never-read`](error-classes.md#revocation-written-but-never-read) | an administrative gesture that is supposed to cut access writes a column nothing reads on the live path. The UI confirms, the row changes, and the hol |
| [`detector-with-no-scheduler`](error-classes.md#detector-with-no-scheduler) | a detector is written, tested, documented — and nothing ever runs it. It reports on the day a human happens to type its command, which is never the da |
| [`the-page-that-tells-you-what-to-do-is-unreachable`](error-classes.md#the-page-that-tells-you-what-to-do-is-unreachable) | l'utilisateur ne sait pas quoi faire, et la page qui le lui dirait existe — mais aucun chemin de l'application n'y mène. Rien ne casse, rien ne lève : |
| [`layer-written-but-never-wired`](error-classes.md#layer-written-but-never-wired) | une couche que l'architecture décrit comme porteuse — validation, gestion d'erreur — existe, a des tests verts, et **aucun code de production ne l'app |
| [`verdict-exists-but-not-when-it-is-needed`](error-classes.md#verdict-exists-but-not-when-it-is-needed) | le contrôle qui répondrait à la question de l'utilisateur existe, tourne, et donne la bonne réponse — mais à un moment où plus personne ne la lit. L'u |
| [`journey-completes-and-nothing-happens`](error-classes.md#journey-completes-and-nothing-happens) | l'utilisateur finit tout ce qu'on lui a demandé et l'écran ne bouge pas. La dernière étape reste ⬜, et l'action qui la coche est ailleurs — derrière u |
| [`finding-computed-but-never-sent`](error-classes.md#finding-computed-but-never-sent) | une tâche de surveillance tourne, calcule un constat juste, et reste verte. Personne n'est prévenu. Le contrôle a l'apparence exacte d'un contrôle qui |
| [`a-step-that-nothing-routes-to`](error-classes.md#a-step-that-nothing-routes-to) | une étape d'un parcours existe, se rend correctement, et aucun chemin n'y mène. Signalé le 2026-09-08 : « quand je clique sur mise en route (assistant |
| [`a-retention-declared-in-a-comment-and-applied-by-nobody`](error-classes.md#a-retention-declared-in-a-comment-and-applied-by-nobody) | une politique de conservation est écrite quelque part — commentaire SQL, ADR, migration — et **rien ne l'exécute**. Rien n'échoue jamais ; la table gr |
| [`a-reopening-condition-nothing-ever-evaluates`](error-classes.md#a-reopening-condition-nothing-ever-evaluates) | une tâche close se donne une **condition de réouverture calculable**, écrite noir sur blanc — et rien ne l'évalue jamais. La condition se remplit, la  |

## un-nombre-affirmé-qui-n-a-pas-été-mesuré

**Ce chiffre a-t-il été mesuré, ou construit ? Le lecteur peut-il distinguer « zéro » de « on ne sait pas » ?**

Règle de rattachement : `plausible-wrong-measurement|wrong-measurement|unmeasured|claimed-not-measured|outranks-the-measurement|nan-written|rendered-as-health|sums-the-display|discarded-in-silence|erases-every-other|past-the-end-of-its-evidence|renders-nothing|named-like-a-final-one|imput|estimat|wins-a-desc-ranking|taken-before-the-writer-ran|carried-across-instruments|chosen-by-a-proxy|ignores-the-floor` sur l'identifiant et le symptôme. 32 classe(s).

| classe | symptôme |
|---|---|
| [`collector-shipped-dag-not-rerun`](error-classes.md#collector-shipped-dag-not-rerun) | a new collector method + table ship (migration applied, code volume-mounted) but the owning DAG hasn't re-run since, so the table stays empty and the  |
| [`intermediate-state-named-like-a-final-one`](error-classes.md#intermediate-state-named-like-a-final-one) | l'utilisateur croit l'opération faite et s'en va. Rien n'est écrit, rien n'est en panne, et le rapport qu'il a sous les yeux dit « ✅ ». |
| [`a-filtered-test-run-proves-nothing`](error-classes.md#a-filtered-test-run-proves-nothing) | annoncer « N tests verts » après une exécution filtrée par `-k`. Le 2026-09-11 : **931 verts** annoncés, puis la sélection officielle en a trouvé **4  |
| [`an-empty-group-wins-a-desc-ranking`](error-classes.md#an-empty-group-wins-a-desc-ranking) | une surface qui affiche « le meilleur X » montre `—` alors qu'un vrai chiffre existe en base. Aucune erreur, aucune trace : la requête a bien rendu un |
| [`a-count-taken-before-the-writer-ran`](error-classes.md#a-count-taken-before-the-writer-ran) | une mesure rend zéro, on en conclut qu'il n'y a rien à faire, et le travail correspondant n'est pas fait. Rien n'échoue — le chiffre était juste **à l |
| [`a-population-chosen-by-a-proxy-for-the-cost`](error-classes.md#a-population-chosen-by-a-proxy-for-the-cost) | une brique d'optimisation énumère précisément **les mauvaises cibles**. La liste est juste selon son propre critère, le travail est réel, et le gain e |
| [`two-instruments-that-do-not-observe-the-same-path`](error-classes.md#two-instruments-that-do-not-observe-the-same-path) | deux instruments censés mesurer la même chose rendent des résultats incompatibles, et l'un des deux rend **zéro**. Le zéro se lit comme « rien ne s'es |
| [`a-sweep-predicate-that-matches-a-form-not-a-property`](error-classes.md#a-sweep-predicate-that-matches-a-form-not-a-property) | un balayage annonce un nombre de sites, et ce nombre est faux d'un facteur 3 à 25 — toujours dans le sens du SUR-COMPTAGE. Rien ne le signale : le pré |
| [`nan-written-as-a-value`](error-classes.md#nan-written-as-a-value) | une colonne censée être vide contient la chaîne `'nan'`. Les requêtes `IS NULL` ne la voient pas, les regroupements la comptent comme une valeur, et u |
| [`a-gap-rendered-as-a-zero-by-the-stack`](error-classes.md#a-gap-rendered-as-a-zero-by-the-stack) | la bande d'une plateforme est correctement COUPÉE sur un jour non mesuré, et le total empilé la compte quand même pour zéro — la pile redescend, et ça |
| [`a-population-that-counts-its-own-headers`](error-classes.md#a-population-that-counts-its-own-headers) | un compteur sur un document porte un dénominateur trop grand, et tous les pourcentages qui en découlent sont faux **dans le sens rassurant** — une par |
| [`a-parser-that-knows-one-of-two-syntaxes`](error-classes.md#a-parser-that-knows-one-of-two-syntaxes) | un compteur dérivé est faux, et sa valeur fausse est une réponse **parfaitement plausible**. Rien ne signale l'erreur : le champ vaut sa valeur par dé |
| [`suppressed-alert-renders-as-health`](error-classes.md#suppressed-alert-renders-as-health) | an alert correctly suppressed for a source that has nothing to send is then rendered as 🟢 / ✅ by every surface that reads the same flag. "Quiet becaus |
| [`static-hint-contradicts-the-live-probe`](error-classes.md#static-hint-contradicts-the-live-probe) | two layers answer the same question about a tenant. One reads the database and guesses at the cause from a fixed string; the other calls the platform  |
| [`unmeasured-rendered-as-measured`](error-classes.md#unmeasured-rendered-as-measured) | a status display shows a green indicator for something nobody has checked. The viewer cannot tell "verified and fine" from "never asked", and acts on  |
| [`empty-table-rendered-as-health`](error-classes.md#empty-table-rendered-as-health) | un panneau affiche « ✅ tout va bien » à partir d'une requête qui ne rend rien — alors que « rien » a deux causes opposées : il n'y a effectivement auc |
| [`prediction-outranks-the-measurement`](error-classes.md#prediction-outranks-the-measurement) | un artiste voit un ❌ et un 🟢 sur le même écran, pour la même plateforme, et conclut que l'application se contredit. Il n'a pas tort ; ce qui est faux, |
| [`view-renders-nothing-and-says-nothing`](error-classes.md#view-renders-nothing-and-says-nothing) | une page s'affiche, ne lève pas, et ne montre rien. L'utilisateur ne sait pas s'il doit attendre, configurer, ou signaler — et aucune alerte ne se déc |
| [`a-guess-that-leaves-no-trace`](error-classes.md#a-guess-that-leaves-no-trace) | un fichier est refusé, ou pire, importé avec des chiffres faux — et rien nulle part ne dit comment il a été LU. Le diagnostic après coup est impossibl |
| [`a-count-that-is-claimed-not-measured`](error-classes.md#a-count-that-is-claimed-not-measured) | l'écran annonce « ✅ N ligne(s) importée(s) » et le journal enregistre N. Personne ne sait si la base en a reçu N. Le chiffre a exactement l'apparence  |
| [`a-gap-in-one-series-erases-every-other`](error-classes.md#a-gap-in-one-series-erases-every-other) | un artiste voit un trou dans une plateforme qui n'en a AUCUN. Signalé le 2026-09-08 : « il y a un gros trou dans les données de S4A ». Mesuré le même  |
| [`a-total-that-sums-the-display-instead-of-the-data`](error-classes.md#a-total-that-sums-the-display-instead-of-the-data) | un total affiché est faux d'un ou deux ordres de grandeur, sans erreur ni trou. Vu au rendu le 2026-09-08 : **16 568 594 écoutes** en sous-titre de la |
| [`a-partial-bucket-drawn-as-a-full-one`](error-classes.md#a-partial-bucket-drawn-as-a-full-one) | une agrégation sous-estime silencieusement, d'un facteur qui dépend de la collecte. Mesuré le 2026-09-08 : **38 %** des semaines YouTube et **31 %** d |
| [`a-symmetric-guard-for-an-asymmetric-truth`](error-classes.md#a-symmetric-guard-for-an-asymmetric-truth) | en mode « Cumulé » — l'affichage par défaut de l'accueil — la bande d'une plateforme dont la collecte s'arrête MONTE puis **retombe à zéro** et y rest |
| [`a-verdict-computed-from-a-value-nobody-read`](error-classes.md#a-verdict-computed-from-a-value-nobody-read) | un document PAYANT affirme « ✅ Rentable » à un artiste alors que la base était injoignable. Le chiffre affiché est `0,00 €` des deux côtés, le net vau |
| [`a-fabricated-zero-mailed-as-a-measurement`](error-classes.md#a-fabricated-zero-mailed-as-a-measurement) | un artiste premium sans dépôt S4A reçoit par e-mail « Streams (last 7 days) : 0 · +0 vs prev week », « Spend : 0.00 € » et « CTR : 0.00 % ». Trois aff |
| [`a-discarded-measurement-is-discarded-in-silence`](error-classes.md#a-discarded-measurement-is-discarded-in-silence) | une figure montre une fraction du volume réel d'une plateforme, sans le dire, ce qui se lit comme une plateforme morte. Mesuré le 2026-09-10 : l'accue |
| [`a-verdict-computed-past-the-end-of-its-evidence`](error-classes.md#a-verdict-computed-past-the-end-of-its-evidence) | une page affiche un verdict en vert — « breakeven atteint le … » — sur un croisement de courbes garanti par construction. Mesuré le 2026-09-10 pour l' |
| [`an-unmeasured-platform-is-rendered-as-zero`](error-classes.md#an-unmeasured-platform-is-rendered-as-zero) | un artiste qui vient de s'inscrire lit **« 0 écoute »** sur les quatre plateformes. Ça ne se lit pas comme « la collecte n'a pas encore tourné », ça s |
| [`a-verdict-whose-validator-lives-outside-the-repo`](error-classes.md#a-verdict-whose-validator-lives-outside-the-repo) | une règle est écrite dans un commentaire avec son chiffre, et personne ne peut la rejouer. La palette portait « refusé : ΔE 4.5 (deutan) » depuis le 2 |
| [`a-measurement-that-cannot-say-why-it-failed`](error-classes.md#a-measurement-that-cannot-say-why-it-failed) | un instrument rend une colonne d'échecs — « perdus », « timeouts », « erreurs » — et **on ne peut pas savoir ce qu'elle décrit**. Le chiffre a l'air d |
| [`a-percentile-computed-on-survivors`](error-classes.md#a-percentile-computed-on-survivors) | un quantile publié **sous-estime** ce qu'il décrit, et toujours dans le sens rassurant. Plus le système se dégrade, plus le chiffre paraît bon — parce |

## le-message-parle-au-mauvais-lecteur

**Cette phrase s'adresse-t-elle à qui la lira — et nomme-t-elle un geste que ce lecteur-là peut faire ?**

Règle de rattachement : `assumes-a-shell|assumes-visibility|by-direction-not-by-name|wrong-advice|blames-the-most-common|names-an-action|flattened-for-the-narrowest|without-naming-the-reason|leaves-no-trace|announces-a-field|instruction-|-instruction|speaks-its-own-plumbing|addressed-to|reader|becomes-the-word-|undefined` sur l'identifiant et le symptôme. 20 classe(s).

| classe | symptôme |
|---|---|
| [`guide-addresses-the-wrong-reader`](error-classes.md#guide-addresses-the-wrong-reader) | un guide montre à l'utilisateur du travail qu'il ne peut pas faire, ou étiquette « admin » une action qui n'appartient qu'à lui. Dans les deux cas il  |
| [`printed-command-assumes-a-shell-the-reader-does-not-have`](error-classes.md#printed-command-assumes-a-shell-the-reader-does-not-have) | une page donne au lecteur une commande à coller, il la colle, elle échoue — et rien dans le message ne dit laquelle des deux hypothèses tacites a lâch |
| [`two-silences-one-message`](error-classes.md#two-silences-one-message) | l'écran dit « Pas encore assez d'historique pour tracer une évolution » à un locataire qui en a **quatre ans**. Vu au navigateur le 2026-09-12 sur « 9 |
| [`a-blocking-hook-that-writes-its-reason-to-stdout`](error-classes.md#a-blocking-hook-that-writes-its-reason-to-stdout) | un hook PreToolUse bloque une commande et l'appelant ne voit AUCUN motif : l'outil rapporte « No stderr output ». La porte est fermée, la raison est i |
| [`alert-names-the-class-and-drops-the-reason`](error-classes.md#alert-names-the-class-and-drops-the-reason) | une panne de collecte est correctement détectée, correctement isolée, correctement alertée — et le message reçu ne dit pas quoi faire, parce que la ph |
| [`setup-step-asks-for-a-developer-gesture`](error-classes.md#setup-step-asks-for-a-developer-gesture) | une étape de mise en route est écrite, testée, et **personne ne la franchit**. Aucune erreur, aucun signal : le locataire abandonne en silence, et on  |
| [`guide-single-os-shortcut`](error-classes.md#guide-single-os-shortcut) | setup-guide prose spells a keyboard shortcut for one OS family (`Ctrl+U`, `Ctrl+F`, `F12`). A macOS artist following the guide literally is blocked at |
| [`watchdog-becomes-the-noise`](error-classes.md#watchdog-becomes-the-noise) | a daily alert email that always contains the same findings, calls for no action, and is therefore skimmed and then ignored — taking the real findings  |
| [`decision-made-on-a-string-truncated-for-display`](error-classes.md#decision-made-on-a-string-truncated-for-display) | a branch written to handle a known, valid edge case never executes. The code reads correctly, the condition names the right thing, and reviewers confi |
| [`detect-then-reject-with-the-wrong-advice`](error-classes.md#detect-then-reject-with-the-wrong-advice) | un fichier est accepté par la détection puis refusé plus bas, avec un conseil qui ne corrige rien. L'utilisateur applique le conseil, réessaie, échoue |
| [`message-flattened-for-the-narrowest-renderer`](error-classes.md#message-flattened-for-the-narrowest-renderer) | un diagnostic en deux moitiés — le symptôme, puis le geste qui le répare — arrive sur ses surfaces automatiques amputé de la seconde. L'alerte nomme l |
| [`alert-names-an-action-its-source-cannot-take`](error-classes.md#alert-names-an-action-its-source-cannot-take) | une alerte vraie nomme une action qui ne peut pas changer l'état qu'elle signale. Le lecteur l'exécute, rien ne bouge, et le même message repart la nu |
| [`instruction-assumes-visibility-the-reader-does-not-have`](error-classes.md#instruction-assumes-visibility-the-reader-does-not-have) | une consigne nomme un objet que son lecteur ne peut pas voir depuis sa place. Il ouvre l'écran indiqué, n'y trouve rien, et s'arrête. Rien n'échoue :  |
| [`instruction-given-without-reading-the-state-it-asks-to-change`](error-classes.md#instruction-given-without-reading-the-state-it-asks-to-change) | l'app prescrit un geste que l'utilisateur ne peut pas accomplir parce qu'il est **déjà fait**, ou sans objet dans sa situation. Il suit la consigne à  |
| [`instruction-points-by-direction-not-by-name`](error-classes.md#instruction-points-by-direction-not-by-name) | une consigne dit « colle-la au-dessus » et le champ est à gauche — ou l'inverse. Deux lecteurs de bonne foi se contredisent sur la même phrase, et cha |
| [`header-announces-a-field-the-form-does-not-have`](error-classes.md#header-announces-a-field-the-form-does-not-have) | un en-tête de formulaire décrit des champs qui n'y sont pas. Le lecteur cherche ce qu'on lui annonce, ne le trouve pas, et doute du reste de la page. |
| [`refusal-leaves-no-trace`](error-classes.md#refusal-leaves-no-trace) | l'utilisateur voit un refus à l'écran, nous ne le voyons jamais. Le journal n'enregistre que ce qui a réussi, donc un défaut qui bloque tout un parcou |
| [`empty-list-blames-the-most-common-cause`](error-classes.md#empty-list-blames-the-most-common-cause) | une liste vide affiche un message écrit d'avance qui demande à l'utilisateur des gestes qu'il vient de faire. Il ne peut ni corriger ce qu'on lui repr |
| [`a-removed-title-becomes-the-word-undefined`](error-classes.md#a-removed-title-becomes-the-word-undefined) | la figure affiche le mot **« undefined »** en gras là où son titre a été retiré. Vu au navigateur le 2026-09-12, immédiatement après avoir supprimé le |
| [`an-alert-judged-on-time-for-a-manual-source`](error-classes.md#an-alert-judged-on-time-for-a-manual-source) | une alerte de fraîcheur est rouge presque en permanence pour un pipeline correct. Mesuré le 2026-09-14 : le CSV Spotify for Artists a déclenché **85 n |

## un-état-qui-déborde-de-sa-portée

**Cet état vit-il exactement le temps de ce qui l'a créé — ni plus, ni pour quelqu'un d'autre ?**

Règle de rattachement : `outlives-the-visit|outlives-its-pull-request|written-after-instantiation|per-worker|namespaced-by-another|connection|closes-a-connection|only-inside-a-session|loses-the-race|first-row|session|cache|named-after-an-environment|environment-variable|state-file|leak` sur l'identifiant et le symptôme. 26 classe(s).

| classe | symptôme |
|---|---|
| [`a-scoring-call-that-omits-its-context`](error-classes.md#a-scoring-call-that-omits-its-context) | un rapprochement correct cesse d'être proposé tout seul, et rien ne le signale. Pas d'exception, pas de compte qui change : le score passe simplement  |
| [`db-connection-per-show`](error-classes.md#db-connection-per-show) | a Streamlit view opens >1 DB connection per `show()` instead of one opened-then-closed-in-finally (CLAUDE.md rule #9). |
| [`helper-closes-a-connection-it-did-not-open`](error-classes.md#helper-closes-a-connection-it-did-not-open) | une vue ouvre deux connexions par rendu au lieu d'une, sans qu'aucun deuxième `get_db_connection()` n'existe dans son fichier. Rien ne casse : la page |
| [`connection-escapes-unclosed`](error-classes.md#connection-escapes-unclosed) | sans charge, rien. Au palier suivant, des connexions s'accumulent contre `max_connections` (100 par défaut, partagé avec Airflow et une API qui peut e |
| [`write-path-without-cache-invalidation`](error-classes.md#write-path-without-cache-invalidation) | le locataire enregistre, l'écran confirme (« ✅ Importé »), et le chiffre affiché reste l'ancien pendant jusqu'à 600 s, sans que rien n'explique pourqu |
| [`correct-because-there-is-only-one-of-it`](error-classes.md#correct-because-there-is-only-one-of-it) | du code exact aujourd'hui devient faux le jour où une seconde instance existe — **sans qu'une seule ligne change**. Rien n'échoue au moment du changem |
| [`a-telemetry-table-that-nothing-ever-purges`](error-classes.md#a-telemetry-table-that-nothing-ever-purges) | une table écrite à chaque événement grossit sans borne. Rien n'échoue jamais — jusqu'au jour où une requête de tableau de bord ralentit, ou où le disq |
| [`a-test-writes-a-probe-into-the-real-tree`](error-classes.md#a-test-writes-a-probe-into-the-real-tree) | un test rouge au hasard, en ordre aléatoire ou sous xdist, sur un fichier qu'il n'a jamais écrit : `FileNotFoundError` sur `src/dashboard/_probe_platf |
| [`session-wide-stub-of-an-installed-package`](error-classes.md#session-wide-stub-of-an-installed-package) | des tests passent ou échouent selon l'ORDRE d'exécution. Isolés ils sont verts ; groupés, quatre d'entre eux tombent sur « n'est pas un paquet ». Et,  |
| [`consumed-state-hides-its-own-widget`](error-classes.md#consumed-state-hides-its-own-widget) | un bouton s'affiche, on clique, et il ne se passe rien. Aucune erreur, aucune trace : le bloc qui portait le bouton disparaît simplement de l'écran. S |
| [`a-fragment-that-outlives-the-connection-it-captured`](error-classes.md#a-fragment-that-outlives-the-connection-it-captured) | **rien ne plante**, et c'est ce qui coûte. Une page admin se met à consommer une connexion de plus par session, sans message qui relie la fuite au ges |
| [`widget-key-written-after-instantiation`](error-classes.md#widget-key-written-after-instantiation) | a helper called from a VIEW writes `st.session_state[<key>]` for a key that is a sidebar widget's, and Streamlit raises `StreamlitAPIException: st.ses |
| [`anonymous-surface-answers-a-private-question`](error-classes.md#anonymous-surface-answers-a-private-question) | a page reachable without authentication behaves differently depending on private state, so a visitor reads that state one request at a time. The page  |
| [`boundary-wider-than-its-docstring`](error-classes.md#boundary-wider-than-its-docstring) | une frontière de test annonce une portée étroite dans son docstring et l'applique à tout le processus. Symptôme observable : des tests deviennent ROUG |
| [`state-file-accumulates-its-own-history`](error-classes.md#state-file-accumulates-its-own-history) | le fichier lu en PREMIER à chaque séance grossit sans fin parce qu'on empile les états successifs au lieu de les faire tourner. Le coût est payé à cha |
| [`capability-resolved-only-inside-a-session`](error-classes.md#capability-resolved-only-inside-a-session) | une fonctionnalité facturée ne peut pas être livrée par un travail de fond, parce que la seule façon de savoir qui y a droit exige une session de navi |
| [`check-then-insert-loses-the-race`](error-classes.md#check-then-insert-loses-the-race) | une page qui « récupère ou crée » plante sur une contrainte d'unicité — pas toujours, pas pour tout le monde, et jamais quand on la regarde. Le messag |
| [`per-worker-reference-point-for-shared-state`](error-classes.md#per-worker-reference-point-for-shared-state) | un garde qui lit un état partagé est vert seul et rouge en exécution parallèle, sur des données que rien n'a changé. Le rouge se déplace d'un fichier  |
| [`view-state-outlives-the-visit`](error-classes.md#view-state-outlives-the-visit) | on rouvre un écran et il s'ouvre là où on l'avait laissé, alors qu'on y revient pour le reprendre depuis le début. Rien n'est en panne, et la page sem |
| [`bulk-write-reads-only-the-first-row`](error-classes.md#bulk-write-reads-only-the-first-row) | aucun. La requête est valide, la transaction réussit, le compte renvoyé est juste — et une colonne n'a jamais été écrite. Le défaut ne se voit qu'en r |
| [`a-cache-key-that-can-never-be-hit-twice`](error-classes.md#a-cache-key-that-can-never-be-hit-twice) | un cache est posé, le code a l'air correct, et la requête part quand même à chaque rendu. Aucun signal : un cache sans succès se comporte exactement c |
| [`a-unit-test-that-borrows-a-real-connection-from-the-pool`](error-classes.md#a-unit-test-that-borrows-a-real-connection-from-the-pool) | un fichier de tests UNITAIRES, qui patche `psycopg2.connect` et se croit entièrement simulé, parle en réalité à la base de production locale. Il passe |
| [`a-cold-measurement-that-clears-caches-by-name`](error-classes.md#a-cold-measurement-that-clears-caches-by-name) | un cliquet qui affirme mesurer « à froid » rend un nombre DIFFÉRENT selon ce qui a tourné avant lui dans le même processus. Il passe en ordre de fichi |
| [`a-metric-registered-twice-kills-the-import`](error-classes.md#a-metric-registered-twice-kills-the-import) | l'application **ne démarre plus du tout** — `Duplicated timeseries in CollectorRegistry` à l'import, avant qu'une ligne ne s'affiche. Rien de progress |
| [`a-make-variable-named-after-an-environment-variable`](error-classes.md#a-make-variable-named-after-an-environment-variable) | une cible `make` prend une option qu'on ne lui a pas donnée. La commande affichée montre l'argument, mais personne ne le lit — on a tapé la ligne, on  |
| [`a-metric-label-whose-cardinality-is-unbounded`](error-classes.md#a-metric-label-whose-cardinality-is-unbounded) | un label de métrique prend ses valeurs dans un ensemble que l'application ne contrôle pas — une URL, un identifiant de ressource, un nom de fichier. L |

## deux-surfaces-deux-nombres

**Ce nombre a-t-il une seule définition, ou chaque surface refait-elle le calcul ?**

Règle de rattachement : `metric-computed-outside|outside-the-metrics|two-|divergen|recopi|restated|duplicat|escapes-every-sql-guard|drift|desync|hand-synced|span-read-from|étendue|sélecteur de période` sur l'identifiant et le symptôme. 25 classe(s).

| classe | symptôme |
|---|---|
| [`a-second-door-that-knows-fewer-sources-than-the-first`](error-classes.md#a-second-door-that-knows-fewer-sources-than-the-first) | un module recopie la résolution d'une ressource partagée en n'en connaissant qu'une partie des sources. Le défaut est INVISIBLE tant que la source man |
| [`image-sized-for-a-layout-it-no-longer-has`](error-classes.md#image-sized-for-a-layout-it-no-longer-has) | une image déborde de son cadre, ou devient floue. Rien ne casse ; c'est simplement laid, et personne ne le signale avant qu'un utilisateur le dise. |
| [`song-name-convention-mismatch`](error-classes.md#song-name-convention-mismatch) | an exact-match join on a song/track title between a FILENAME-derived table (`s4a_song_timeline`, `ml_song_predictions`, manual-entry tables — they car |
| [`state-path-namespaced-by-another-project`](error-classes.md#state-path-namespaced-by-another-project) | a writer and its readers disagree on where shared state lives, because one of them hardcodes a project name in the path. Nothing errors — the reader s |
| [`local-db-drifts-from-canonical`](error-classes.md#local-db-drifts-from-canonical) | tests pass in CI and against a throwaway database, and fail on the developer's own machine — with type errors, not logic errors. |
| [`audit-scope-restated-not-derived`](error-classes.md#audit-scope-restated-not-derived) | a check iterates a hand-typed list of the things it audits while a registry of those things already exists. The list is a subset, and the difference i |
| [`two-doors-onto-one-database`](error-classes.md#two-doors-onto-one-database) | two halves of one application resolve the same database by two different precedences, and neither works in the other's configuration. Moving a variabl |
| [`mandatory-filter-with-no-guard`](error-classes.md#mandatory-filter-with-no-guard) | a rule stated in bold in `CLAUDE.md` is enforced by memory alone. It holds for months, then one query forgets it and the number shown to a user is sil |
| [`two-surfaces-two-truths`](error-classes.md#two-surfaces-two-truths) | deux surfaces du produit répondent différemment à la MÊME question, et l'utilisateur croit celle qui a tort. Ici : le PDF exporté annonçait « Spotify  |
| [`two-widgets-for-one-gesture`](error-classes.md#two-widgets-for-one-gesture) | l'utilisateur fait une chose à un endroit, la retrouve absente à l'autre, et rien n'est en panne. Le produit a deux surfaces pour un seul geste, chacu |
| [`a-visual-constant-copied-into-a-second-renderer`](error-classes.md#a-visual-constant-copied-into-a-second-renderer) | la même plateforme porte **deux couleurs** dans le même produit — Spotify en vert à l'écran, en bleu dans le PDF du même artiste, le même jour. |
| [`identity-read-but-never-collectable`](error-classes.md#identity-read-but-never-collectable) | a consumer (DAG tenant filter, readiness matrix, collector) reads an identity key from `artist_credentials.extra_config` that **no credential form fie |
| [`same-platform-judged-on-different-tables`](error-classes.md#same-platform-judged-on-different-tables) | several surfaces each decide whether a platform is "collecting" by reading a different table, so the same tenant is 🟢 on one screen and 🔴 on another — |
| [`row-existence-read-as-connection`](error-classes.md#row-existence-read-as-connection) | a surface decides "connected" from the presence of a credentials row rather than from the identity value, so a tab opened and saved blank reads as ✅ — |
| [`counter-includes-our-own-robots`](error-classes.md#counter-includes-our-own-robots) | un compteur affiché à des visiteurs — « N artistes utilisent le produit » — inclut les comptes de service que nous créons nous-mêmes. Le nombre est fa |
| [`two-checks-one-question-reported-twice`](error-classes.md#two-checks-one-question-reported-twice) | deux contrôles portant des noms différents évaluent le MÊME prédicat, et le rapport imprime chaque fait deux fois, sous deux formulations du même gest |
| [`mirror-visible-to-one-reader-only`](error-classes.md#mirror-visible-to-one-reader-only) | une identité stockée à DEUX endroits (une ligne de credentials et une colonne miroir sur `saas_artists`) n'est vue que par l'un des lecteurs. Le lecte |
| [`one-set-answers-two-questions`](error-classes.md#one-set-answers-two-questions) | un correctif juste en produit un autre dans l'heure, à l'endroit exact qu'il venait de toucher. |
| [`one-identity-two-readers`](error-classes.md#one-identity-two-readers) | deux colonnes de la MÊME ligne se contredisent — « Saisi ✅ » à côté de « Format ? — forme non vérifiable pour cette plateforme ». Signalé le 2026-09-0 |
| [`the-live-chart-drifted-from-its-illustration`](error-classes.md#the-live-chart-drifted-from-its-illustration) | l'artiste voit une figure d'exemple, puis « la sienne », et ce n'est pas la même chose — autre forme, autres couleurs. La seconde se lit comme une rég |
| [`a-metric-computed-outside-the-metrics-layer`](error-classes.md#a-metric-computed-outside-the-metrics-layer) | deux surfaces du même produit répondent deux nombres à la même question, sans qu'aucune soit « en panne ». Instances mesurées : trois définitions inco |
| [`an-overload-makes-the-old-call-ambiguous`](error-classes.md#an-overload-makes-the-old-call-ambiguous) | une tuile passe à **0** après une migration qui n'a rien retiré. Mesuré le 2026-09-12 : « Total Streams (Cumul) » affichait **0** sur la page Apple Mu |
| [`two-definitions-that-must-coincide-are-never-compared`](error-classes.md#two-definitions-that-must-coincide-are-never-compared) | deux chemins qui répondent à la même question rendent deux nombres différents, chacun cohérent avec lui-même, pendant des semaines. Mesuré en PRODUCTI |
| [`one-fact-two-answers-by-display-mode`](error-classes.md#one-fact-two-answers-by-display-mode) | la même phrase de l'interface affiche deux valeurs différentes selon un réglage d'affichage que l'utilisateur vient de changer. Aucune des deux n'est  |
| [`a-span-read-from-a-table-that-carries-a-mandatory-filter`](error-classes.md#a-span-read-from-a-table-that-carries-a-mandatory-filter) | un sélecteur de période propose une fenêtre plus large que ce que la figure d'à côté peut tracer. L'utilisateur choisit dans un intervalle qui existe, |

## une-erreur-avalée-devient-une-absence

**Ce `except` distingue-t-il « rien à lire » de « on n'a pas pu lire » — et l'utilisateur voit-il la différence ?**

Règle de rattachement : `silent|swallow|avalée|absence|silencieu|renders?-as-a-measurement|empty-bracket|no-op|returns-none|degrade|logged-as-success|inbox-nobody-reads|outside-its-condition|read-that-failed|failed-read|except.*number|read-through-a-filtering|fallback` sur l'identifiant et le symptôme. 23 classe(s).

| classe | symptôme |
|---|---|
| [`an-absence-that-becomes-a-nan-because-nan-is-truthy`](error-classes.md#an-absence-that-becomes-a-nan-because-nan-is-truthy) | une valeur absente traverse DEUX filets successifs et ressort en `NaN`. Selon le site, elle s'affiche « nan € » sans que rien ne lève, ou elle fait pl |
| [`collector-silent-success`](error-classes.md#collector-silent-success) | a collector `except` block logs then returns empty (`None`/`[]`/`{}`) → DAG upserts 0 rows, exits SUCCESS, no alert, dashboard silently stale. |
| [`rex-delimiter-unanchored`](error-classes.md#rex-delimiter-unanchored) | a validator reports a tool as carrying no `rex:` block when the block is present and correct — it could not parse, and said "absent". The reader is se |
| [`per-tenant-outcome-not-recorded`](error-classes.md#per-tenant-outcome-not-recorded) | a multi-tenant job reports SUCCESS while one tenant collected nothing. The per-tenant `try/except/continue` that keeps one bad tenant from aborting th |
| [`absence-rendered-as-a-measurement`](error-classes.md#absence-rendered-as-a-measurement) | un graphique ou un tableau affiche `0` là où la donnée dit « aucune observation ». Le lecteur y lit une mesure — « 0 % de chance » — c'est-à-dire l'in |
| [`import-refused-without-naming-the-reason`](error-classes.md#import-refused-without-naming-the-reason) | un fichier déposé par un artiste n'importe rien, et le refus ne nomme rien. « Mon CSV ne marche pas » est alors tout le diagnostic disponible — pour l |
| [`a-read-that-failed-is-rendered-as-a-number`](error-classes.md#a-read-that-failed-is-rendered-as-a-number) | une tuile affiche un chiffre alors que la requête a LEVÉ. Quatre occurrences en deux jours, aucune n'a produit d'erreur visible : « Total Streams : ** |
| [`a-verification-read-through-a-filtering-wrapper`](error-classes.md#a-verification-read-through-a-filtering-wrapper) | une commande de vérification rend une réponse **plausible et fausse**, et la décision qui s'ensuit est prise sur cette réponse. Mesuré le 2026-09-13 : |
| [`a-timeout-reported-as-a-missing-thing`](error-classes.md#a-timeout-reported-as-a-missing-thing) | un outil annonce qu'une chose N'EXISTE PAS alors qu'il a seulement cessé de l'attendre. Mesuré le 2026-09-15 : `.claude/scripts/select_tests.py --dry` |
| [`a-parenthesis-is-not-a-tuple`](error-classes.md#a-parenthesis-is-not-a-tuple) | une requête paramétrée ne s'exécute JAMAIS. Elle lève avant d'atteindre la base, un `except` plus haut l'attrape, et l'appelant reçoit une liste vide  |
| [`a-red-verdict-delivered-to-an-inbox-nobody-reads`](error-classes.md#a-red-verdict-delivered-to-an-inbox-nobody-reads) | un contrôle tourne, rougit à temps sur une vraie panne, et personne ne le sait. Son verdict ne part que par un canal que le destinataire ne lit pas —  |
| [`ast-guard-blind-to-bom`](error-classes.md#ast-guard-blind-to-bom) | a source file starts with a UTF-8 BOM (`\xef\xbb\xbf`). `ast.parse` on text read with plain `encoding="utf-8"` raises `SyntaxError: invalid non-printa |
| [`i18n-untranslated-key`](error-classes.md#i18n-untranslated-key) | a `t("ns.key", "FR …")` / `_t("ns.key", "FR …")` call has no EN entry in `i18n_catalog/` → EN mode silently renders the French default (untranslated s |
| [`delivery-failure-logged-as-success`](error-classes.md#delivery-failure-logged-as-success) | the code path that sends a notification returns a "did not send" value, the very next line logs that it was sent, and the task ends green. The finding |
| [`broken-probe-rendered-as-user-fault`](error-classes.md#broken-probe-rendered-as-user-fault) | a check that FAILED (missing table, bad identifier, dead connection) renders identically to "connected, no data", so the user is told to fix something |
| [`success-message-outside-its-condition`](error-classes.md#success-message-outside-its-condition) | l'utilisateur voit défiler des erreurs, puis un message de succès. Il retient le dernier. Ici : sept déclenchements de collecte en échec affichaient s |
| [`the-watcher-is-not-watched`](error-classes.md#the-watcher-is-not-watched) | un contrôle planifié cesse de tourner et tout reste vert, parce que rien ne surveille le surveillant. L'absence d'échec est lue comme une absence de p |
| [`probe-reads-unreadable-as-absent`](error-classes.md#probe-reads-unreadable-as-absent) | un outil de diagnostic accuse le produit d'un défaut qu'il n'a pas — et il vise précisément la page où un vrai défaut coûterait le plus cher. |
| [`filename-dependency-survives-below-detection`](error-classes.md#filename-dependency-survives-below-detection) | un fichier est reconnu à l'écran puis n'importe rien, sous un message qui accuse son CONTENU (« Aucune ligne valide détectée après parsing ») ou qui d |
| [`a-failed-collection-writes-zeros`](error-classes.md#a-failed-collection-writes-zeros) | des lignes arrivent, à l'heure, en nombre normal — et leurs valeurs sont fausses. Mesuré le 2026-09-08 : le 2026-06-01, `soundcloud_tracks_daily` a re |
| [`a-default-branch-that-skips-instead-of-refusing`](error-classes.md#a-default-branch-that-skips-instead-of-refusing) | un script de déploiement met un service EN SERVICE sans l'avoir vérifié une seule fois, et sort en 0. Rien n'échoue, rien n'avertit : le service deman |
| [`a-gauge-that-reports-zero-when-it-cannot-read`](error-classes.md#a-gauge-that-reports-zero-when-it-cannot-read) | une jauge alimentée depuis une ressource externe tombe à 0 quand cette ressource est injoignable. Le tableau affiche alors un chiffre rassurant — « au |
| [`a-fallback-that-answers-the-whole-question`](error-classes.md#a-fallback-that-answers-the-whole-question) | une tuile annonce « N sur les dernières 24 h » et donne le total de TOUT l'historique. Aucune erreur, aucun trou : le chiffre est simplement celui d'u |

## un-garde-qui-ne-garde-pas

**Ce garde a-t-il déjà été VU rouge sur le défaut qu'il vise — et sa portée contient-elle ce défaut ?**

Règle de rattachement : `guard|gate|porte|cliquet|ratchet|signature|probe|predicate|vacuous|mutation|substitution|s'exécute|accent grave|test-|suite|assert|blind|skips-instead-of-refusing|only-one-of-it|rollback-wider-than-the-failure|fallback-that-runs` sur l'identifiant et le symptôme. 62 classe(s).

| classe | symptôme |
|---|---|
| [`a-fallback-that-runs-when-the-first-branch-succeeded`](error-classes.md#a-fallback-that-runs-when-the-first-branch-succeeded) | un `A \|\| B` livre le résultat de A alors qu'on attendait B — ou l'inverse. Rien n'échoue, rien ne s'affiche : la commande sort 0 et le mauvais effet e |
| [`probe-scoped-to-the-machine-not-the-repo`](error-classes.md#probe-scoped-to-the-machine-not-the-repo) | a health probe enumerates every container or process on the HOST instead of the ones this repo declares. It reports on neighbouring projects — and can |
| [`guard-derived-from-the-thing-it-guards`](error-classes.md#guard-derived-from-the-thing-it-guards) | a test is GREEN while the thing it guards is wrong, because it derives its own scope or its own expectation from that thing. Two shapes, both measured |
| [`gate-with-no-test-of-its-own`](error-classes.md#gate-with-no-test-of-its-own) | a tool whose entire job is to answer go/no-go has no test and no schedule. Its greenness is trusted by a runbook, its logic is verified by nobody, and |
| [`guard-scope-is-a-hand-written-list`](error-classes.md#guard-scope-is-a-hand-written-list) | a check is correct on everything it looks at, and what it looks at is a list somebody typed. It never reports the things it does not cover, so its sil |
| [`leak-via-an-exception-received-as-an-argument`](error-classes.md#leak-via-an-exception-received-as-an-argument) | un credential part dans un journal, un mail ou une base, depuis un module que le garde anti-fuite ne surveille pas — et il a raison de ne pas le surve |
| [`format-marker-in-a-plain-string`](error-classes.md#format-marker-in-a-plain-string) | un marqueur `{...}` destiné à une f-string se retrouve dans une chaîne ordinaire et part **tel quel** dans le SQL. Postgres reçoit huit caractères lit |
| [`boundary-with-no-named-exit-kills-what-must-pass`](error-classes.md#boundary-with-no-named-exit-kills-what-must-pass) | une frontière posée pour borner le rayon de souffle de la suite éteint aussi **ce qui doit sortir**. Le composant tué est un moniteur : son rouge quot |
| [`environment-failure-worn-as-a-code-failure`](error-classes.md#environment-failure-worn-as-a-code-failure) | la suite rend des dizaines de rouges qui disent « mauvais interpréteur », pas « code cassé ». On apprend à ne plus lire le récapitulatif, et un vrai é |
| [`retry-blind-to-the-exception-its-client-raises`](error-classes.md#retry-blind-to-the-exception-its-client-raises) | un décorateur `@retry` est en place, visible, jamais retiré — et **aucune tentative n'a jamais été rejouée**. Un blip réseau fait échouer la tâche du  |
| [`guard-matches-its-own-comment`](error-classes.md#guard-matches-its-own-comment) | un test de garde est VERT sur le défaut qu'il existe pour attraper, ou ROUGE sur le commentaire qui explique le correctif. Les deux erreurs viennent d |
| [`guard-anchored-on-shape-not-question`](error-classes.md#guard-anchored-on-shape-not-question) | un garde vire au rouge sur un changement qui n'altère AUCUN comportement — un renommage de variable, une branche inversée, une factorisation. Le réfle |
| [`guard-reads-the-box-not-its-subject`](error-classes.md#guard-reads-the-box-not-its-subject) | un garde est vert sur le poste où il a été écrit et rouge — ou vide — partout ailleurs. Il n'a jamais mesuré son sujet : son verdict vient de la confi |
| [`guard-asserts-presence-not-reachability`](error-classes.md#guard-asserts-presence-not-reachability) | un garde structurel passe au vert sur le défaut qu'il devait attraper. Il demande « cet appel est-il là ? » et l'appel EST là — sous une branche morte |
| [`guard-predicate-depends-on-the-host-env`](error-classes.md#guard-predicate-depends-on-the-host-env) | un garde est vert sur le poste où on l'écrit et rouge partout ailleurs, sur un code identique. Il n'interroge pas le code : il interroge l'environneme |
| [`guard-branch-only-reached-when-it-fails`](error-classes.md#guard-branch-only-reached-when-it-fails) | un garde est vert sur une base propre et rouge dans la grande exécution, et le rouge ne parle pas du sujet gardé — un `TypeError`, un `KeyError`, une  |
| [`module-level-read-turns-a-deletion-into-a-collection-error`](error-classes.md#module-level-read-turns-a-deletion-into-a-collection-error) | on supprime un fichier et le rapport de tests annonce « N errors » au lieu de « N failed ». Les propriétés que ces tests défendaient disparaissent de  |
| [`a-confirmation-thrown-away-by-the-rerun-that-follows-it`](error-classes.md#a-confirmation-thrown-away-by-the-rerun-that-follows-it) | une action RÉUSSIT et l'écran ne le dit pas. La page se recharge sans un mot, ce qui se lit exactement comme un échec — l'utilisateur recommence, ou c |
| [`a-signature-anchored-on-a-location`](error-classes.md#a-signature-anchored-on-a-location) | une signature de classe d'erreur rougit sur un arbre sain, deux fois en deux jours, parce que le correctif a déplacé ou renommé ce qu'elle nommait. On |
| [`a-guard-that-sees-the-binding-not-the-application`](error-classes.md#a-guard-that-sees-the-binding-not-the-application) | un garde reste vert sur le défaut exact qu'il décrit, parce qu'il vérifie qu'une valeur est CALCULÉE et non qu'elle est UTILISÉE. |
| [`a-kill-pattern-that-matches-its-own-shell`](error-classes.md#a-kill-pattern-that-matches-its-own-shell) | une commande composée s'arrête au milieu, sans message, et rend le code **144**. Ce qui suit n'a jamais tourné — relancer la suite, écrire le script,  |
| [`a-verdict-from-a-tree-that-moved-under-it`](error-classes.md#a-verdict-from-a-tree-that-moved-under-it) | la suite complète rend des échecs qui **n'existent pas** — verts dès qu'on les rejoue. Mesuré le 2026-09-12 : quatre signalés sur deux exécutions, **t |
| [`a-bash-hook-that-blocks-the-prose-about-the-gesture`](error-classes.md#a-bash-hook-that-blocks-the-prose-about-the-gesture) | **écrire sur un défaut devient impossible.** Trois commandes bloquées d'affilée le 2026-09-12, toutes en train d'écrire la classe d'erreur du geste co |
| [`a-measurement-taken-under-self-inflicted-load`](error-classes.md#a-measurement-taken-under-self-inflicted-load) | un chiffre de performance est mesuré pendant que d'autres processus LANCÉS PAR MOI occupent la machine, puis lu comme une propriété du système. **Troi |
| [`a-file-whose-tests-share-a-namespace`](error-classes.md#a-file-whose-tests-share-a-namespace) | sous une distribution test-par-test (`--dist loadgroup`, ou des shards), deux tests d'un MÊME fichier tournent en parallèle et se disputent un nom qu' |
| [`a-gate-that-repairs-what-it-judges`](error-classes.md#a-gate-that-repairs-what-it-judges) | une porte BLOQUANTE de la CI passe au vert sur un arbre qui porte exactement le défaut qu'elle cherche. Elle n'a jamais pu échouer, et rien dans son t |
| [`a-ratchet-that-only-watches-the-direction-it-was-burned-in`](error-classes.md#a-ratchet-that-only-watches-the-direction-it-was-burned-in) | un garde passe VERT sur un défaut qui appartient pourtant très exactement à son sujet. En le relisant on ne trouve rien à redire : il fait ce qu'il di |
| [`a-docstring-exclusion-that-compares-dedented-text`](error-classes.md#a-docstring-exclusion-that-compares-dedented-text) | un garde qui lit l'AST — donc écrit précisément pour ne PAS être textuel — reste malgré tout vert sur sa propre mutation. Il a l'air rigoureux et il n |
| [`a-backtick-in-a-shell-string-is-executed`](error-classes.md#a-backtick-in-a-shell-string-is-executed) | une commande destinée à être AFFICHÉE s'exécute. Le message qui décrit un geste devient le geste. Rien n'avertit : la sortie ressemble à celle de la c |
| [`guard-satisfied-by-its-own-comment`](error-classes.md#guard-satisfied-by-its-own-comment) | le défaut est remis en place **en entier** et la suite reste VERTE. Rien ne signale quoi que ce soit — c'est un garde qui ne garde plus, dans l'état e |
| [`a-proof-that-tests-a-copy-of-its-detector`](error-classes.md#a-proof-that-tests-a-copy-of-its-detector) | un garde porte une preuve de non-vacuité VERTE, et le garde est pourtant aveugle : casser son prédicat laisse la preuve verte. Rien ne le signale ; on |
| [`a-command-wrapper-that-returns-a-plausible-wrong-measurement`](error-classes.md#a-command-wrapper-that-returns-a-plausible-wrong-measurement) | une commande de vérification rend un résultat **crédible et faux**. Rien n'échoue, aucun message, et le chiffre est du bon ordre de grandeur — donc on |
| [`df-na-rep`](error-classes.md#df-na-rep) | `df.style.format({...})` without `na_rep=` → `TypeError` when a formatted column is NULL (LEFT JOIN / empty window). |
| [`test-leaves-a-hole-in-sys-modules`](error-classes.md#test-leaves-a-hole-in-sys-modules) | tests are green file by file and red in a full run, on assertions unrelated to whatever changed. The failing test's own monkeypatch appears not to tak |
| [`guard-seeded-by-prose-not-by-code`](error-classes.md#guard-seeded-by-prose-not-by-code) | un garde marque en faute un module qui vient d'appliquer son propre correctif. Le module ne fait rien de risqué : il a seulement **importé le remède** |
| [`handler-built-without-its-arguments`](error-classes.md#handler-built-without-its-arguments) | une tâche planifiée lève `TypeError: X.__init__() missing N required positional arguments` à sa première exécution réelle, des heures après le commit. |
| [`a-ratchet-frozen-on-a-partial-predicate`](error-classes.md#a-ratchet-frozen-on-a-partial-predicate) | un cliquet gelé à zéro passe au vert, et la chose qu'il interdit est toujours là. Mesuré le 2026-09-10 : `_MAX_SECONDARY_AXES = 0` était vert alors qu |
| [`an-aggregate-computed-in-pandas-escapes-every-sql-guard`](error-classes.md#an-aggregate-computed-in-pandas-escapes-every-sql-guard) | un cliquet certifie « zéro agrégat hors de la couche or » pendant qu'une tuile affiche un total faux. Les deux affirmations sont vraies : le total n'e |
| [`a-marker-shared-by-several-sites-guards-none`](error-classes.md#a-marker-shared-by-several-sites-guards-none) | un test de non-régression qui cherche la PRÉSENCE d'un marqueur dans un fichier reste vert quand un seul des sites qui l'utilisent perd son correctif. |
| [`a-guard-satisfied-by-the-collapse-it-should-catch`](error-classes.md#a-guard-satisfied-by-the-collapse-it-should-catch) | un garde qui affirme une ABSENCE (« cette ligne ne doit pas s'afficher », « ce champ ne doit pas apparaître ») reste vert sur le défaut, parce que le  |
| [`a-hook-shaped-function-pytest-never-calls`](error-classes.md#a-hook-shaped-function-pytest-never-calls) | une fonction porte la signature exacte d'un hook pytest, son corps fait le travail d'un hook, et elle n'est JAMAIS appelée. Rien ne le signale : il n' |
| [`a-ci-checkout-too-shallow-for-the-guard-that-reads-git`](error-classes.md#a-ci-checkout-too-shallow-for-the-guard-that-reads-git) | un garde passe en local et échoue en CI, **toujours**, sans que rien dans son code ne diffère. On relance, on suspecte un aléa, on finit par lire le r |
| [`an-optimisation-that-degrades-what-worked`](error-classes.md#an-optimisation-that-degrades-what-worked) | un algorithme « amélioré » se trompe sur des cas qu'il réussissait. Il se trompe **en silence** : aucune exception, aucun compte qui change, juste des |
| [`api-router-schema-drift`](error-classes.md#api-router-schema-drift) | a FastAPI data router (Brick-14) SELECTs a column renamed/dropped by a later migration → the endpoint 500s for every tenant (no client stack-trace lea |
| [`partial-collection-invisible`](error-classes.md#partial-collection-invisible) | la collecte d'un locataire s'effondre sans que rien ne le dise. Des données arrivent — donc la fraîcheur est verte — mais bien moins que d'habitude :  |
| [`automation-gap-between-two-ecosystems`](error-classes.md#automation-gap-between-two-ecosystems) | une règle de sécurité existe, elle est écrite, elle est commentée — et elle ne couvre qu'un des écosystèmes auxquels elle s'applique. La proposition d |
| [`selector-blind-to-the-import-prefix`](error-classes.md#selector-blind-to-the-import-prefix) | un sélecteur de tests rend un ensemble qui a l'air restreint — 19 sur 169, 11 % — et qui est en réalité CONSTANT : le même, octet pour octet, pour un  |
| [`code-ships-without-a-trace`](error-classes.md#code-ships-without-a-trace) | une séance modifie du code de production et se termine sans entrée de journal ni mise à jour de roadmap. Le code part ; le raisonnement qui l'a produi |
| [`assertion-wider-than-the-question-it-asks`](error-classes.md#assertion-wider-than-the-question-it-asks) | un test accuse une régression de destruction de données qui n'a jamais eu lieu, et bloque une PR sans rapport. |
| [`headline-asserts-a-cause-the-probe-did-not-measure`](error-classes.md#headline-asserts-a-cause-the-probe-did-not-measure) | un écran affiche, l'un sous l'autre, un verdict et le détail qui le contredit — et des indicateurs verts qui contredisent les deux. Le titre est un re |
| [`probe-does-not-ask-the-collectors-question`](error-classes.md#probe-does-not-ask-the-collectors-question) | une sonde de configuration annonce à l'utilisateur que sa source est vide, pendant que le collecteur en ramène le contenu tous les jours. Les deux int |
| [`menu-filter-mistaken-for-an-access-gate`](error-classes.md#menu-filter-mistaken-for-an-access-gate) | une page réservée n'apparaît pas dans le menu et s'affiche quand même — il suffit d'en connaître l'adresse. La liste qui devait la protéger existe, el |
| [`a-form-constraint-checked-on-the-series-not-on-the-axis`](error-classes.md#a-form-constraint-checked-on-the-series-not-on-the-axis) | une combinaison de réglages rend une figure entièrement VIDE, sans message, alors que les données sont là. Signalé au rendu le 2026-09-08 : « je vois  |
| [`a-non-vacuity-check-anchored-on-the-data-instead-of-the-parser`](error-classes.md#a-non-vacuity-check-anchored-on-the-data-instead-of-the-parser) | le jour où le travail est réellement terminé, **trois gardes tombent ensemble** — et ils tombent sur la seule chose qu'ils n'avaient pas prévue : le s |
| [`a-ratchet-at-zero-over-a-scope-that-excludes-the-defect`](error-classes.md#a-ratchet-at-zero-over-a-scope-that-excludes-the-defect) | un cliquet affiche zéro et la propriété qu'il annonce est fausse. Le prédicat est juste, la portée ne l'est pas — et rien dans le message ne distingue |
| [`a-ratchet-with-no-floor-under-its-population`](error-classes.md#a-ratchet-with-no-floor-under-its-population) | un cliquet à zéro reste vert alors que la propriété qu'il annonce n'est plus vérifiée — parce qu'il ne mesure plus rien. Mesuré le 2026-09-12 : **5 de |
| [`a-test-whose-input-derives-from-its-subject`](error-classes.md#a-test-whose-input-derives-from-its-subject) | un garde reste VERT quand on mute la constante qu'il prétend garder. Il n'échoue sur aucune valeur, si extrême soit-elle, parce que l'entrée qu'il con |
| [`an-exemption-declared-per-site-never-stops-growing`](error-classes.md#an-exemption-declared-per-site-never-stops-growing) | une liste d'exemptions grossit à chaque changement sans rapport avec elle. Mesuré le 2026-09-14 : `saas_artists` est passée de **0 à 4 déclarations en |
| [`a-gate-that-counts-instead-of-comparing-sets`](error-classes.md#a-gate-that-counts-instead-of-comparing-sets) | une porte compare deux NOMBRES là où la question porte sur deux ENSEMBLES. Elle est verte, les deux totaux sont justes, et l'élément qui manque d'un c |
| [`a-rollback-wider-than-the-failure`](error-classes.md#a-rollback-wider-than-the-failure) | un retour arrière déclenché par la panne d'UNE instance reconstruit tout ce qui tourne. Le remède coupe ce qui marchait encore, et la coupure est plus |
| [`a-verdict-swallowed-by-the-pipe-that-abbreviated-it`](error-classes.md#a-verdict-swallowed-by-the-pipe-that-abbreviated-it) | une vérification est lancée, son verdict est ROUGE, il s'affiche à l'écran — et la livraison qui suit sur le même `&&` part quand même. Rien n'échoue, |
| [`a-view-body-behind-a-non-default-filter`](error-classes.md#a-view-body-behind-a-non-default-filter) | une vue rend sans erreur dans la suite, et lève chez l'utilisateur dès qu'il élargit un filtre. Le bloc fautif vit derrière une condition de TAILLE de |

## un-document-qui-affirme-un-état-périmé

**Ce qui est écrit là est-il régénéré, ou recopié une fois puis oublié ?**

Règle de rattachement : `stale|périmé|obsolete|doc|readme|roadmap|comment|caption|note|prose|generated|index|diagram|map|guide|runbook|lags-its-source|hand-written-list|telemetry-table-that-nothing-ever-purges|proc[ée]dure|playbook|runbook|instruction` sur l'identifiant et le symptôme. 35 classe(s).

| classe | symptôme |
|---|---|
| [`a-price-page-that-restates-a-gate-instead-of-reading-it`](error-classes.md#a-price-page-that-restates-a-gate-instead-of-reading-it) | la page qui VEND une fonctionnalité et le verrou qui l'OUVRE se contredisent. Rien ne lève : les deux textes sont valides, ils sont simplement écrits  |
| [`a-runbook-that-names-a-command-nobody-can-run`](error-classes.md#a-runbook-that-names-a-command-nobody-can-run) | une procédure dit de lancer une commande ; la commande n'existe pas, ou plus. Rien ne le signale, parce qu'une procédure est de la prose. Le coût n'es |
| [`operator-guidance-phantom-or-wrong-auth`](error-classes.md#operator-guidance-phantom-or-wrong-auth) | operator-facing text (failure-alert root-cause map, Credentials help UI, setup guides) instructs running a script that does not exist, or describes an |
| [`config-status-file-unrendered`](error-classes.md#config-status-file-unrendered) | a file the tooling treats as the status source is an un-expanded bootstrap template — literal `$(date +%Y-%m-%d)`, `TODO: fill in` — so every reader o |
| [`views-map-drifts-from-the-views`](error-classes.md#views-map-drifts-from-the-views) | la carte d'architecture décrit un sous-ensemble du produit et rien ne le dit. Le lecteur la consulte AU LIEU de lister le répertoire — c'est sa foncti |
| [`dev-doc-nothing-points-at`](error-classes.md#dev-doc-nothing-points-at) | un document utile existe et reste introuvable, parce qu'aucun index ne le nomme. Symétriquement, des gabarits vides survivent des mois sans que person |
| [`cache-not-invalidated-by-the-event-that-stales-it`](error-classes.md#cache-not-invalidated-by-the-event-that-stales-it) | l'utilisateur déclenche une action, l'interface lui confirme qu'elle est lancée, puis affiche l'état d'AVANT son clic — jusqu'à l'expiration du TTL. L |
| [`shipped-artifact-lags-its-source`](error-classes.md#shipped-artifact-lags-its-source) | tous les gardes sont verts, la source est juste, et l'utilisateur reçoit quand même les instructions d'il y a trois mois. |
| [`page-that-restates-what-the-app-already-shows`](error-classes.md#page-that-restates-what-the-app-already-shows) | une page « guide » explique en prose ce que l'application montre déjà en agissant. Elle vieillit plus vite que ce qu'elle décrit, et deux surfaces fin |
| [`a-glyph-with-no-font-vanishes-without-a-trace`](error-classes.md#a-glyph-with-no-font-vanishes-without-a-trace) | un document généré perd des caractères — sans erreur, sans avertissement, sans carré de substitution. Reproduit le 2026-09-10 : rendu le golden HTML d |
| [`a-diagram-is-verified-by-looking-at-it`](error-classes.md#a-diagram-is-verified-by-looking-at-it) | un schéma généré est syntaxiquement valide, son SVG contient tout le texte attendu, et il est faux à l'œil. Mesuré le 2026-09-10 sur sept schémas neuf |
| [`a-generated-document-asserts-a-stale-state`](error-classes.md#a-generated-document-asserts-a-stale-state) | un document généré décrit un dépôt qui n'existe plus. Il ne porte aucune marque de péremption — il se lit exactement comme une mesure fraîche, et c'es |
| [`a-merged-branch-outlives-its-pull-request`](error-classes.md#a-merged-branch-outlives-its-pull-request) | le dépôt affiche des dizaines de branches « actives » alors qu'une seule ligne de travail existe. Le propriétaire se demande s'il va **perdre des avan |
| [`a-status-screen-that-reads-half-its-source`](error-classes.md#a-status-screen-that-reads-half-its-source) | un écran d'état annonce un TOTAL faux, sans erreur et sans trou visible. Il dit « 0 » là où la source en porte une, parce qu'il ne lit qu'une partie d |
| [`a-prose-claim-that-cannot-be-verified`](error-classes.md#a-prose-claim-that-cannot-be-verified) | un document dont les TABLEAUX sont justes affirme le contraire dans la prose posée à côté, et rien ne le voit. Mesuré le 2026-09-15 sur `.claude/dev-d |
| [`config-path-dangling`](error-classes.md#config-path-dangling) | a rule, skill or command names a `.claude/` file that is not there. Nothing errors — the instruction is simply unfollowable, and the reader cannot tel |
| [`a-guard-names-a-class-nobody-wrote`](error-classes.md#a-guard-names-a-class-nobody-wrote) | un défaut est parfaitement décrit — symptôme, cause, mesure, date, coût — **dans la docstring d'un test, et nulle part ailleurs**. Le catalogue ne le  |
| [`a-percent-sign-in-a-parameterised-query`](error-classes.md#a-percent-sign-in-a-parameterised-query) | une requête paramétrée échoue en bloc sur `IndexError: tuple index out of range`, alors que le nombre d'emplacements `%s` et le nombre de valeurs pass |
| [`a-class-that-claims-its-neighbours-guard`](error-classes.md#a-class-that-claims-its-neighbours-guard) | une classe d'erreur annonce une protection plus large que celle qu'elle a. Le champ `guard:` nomme un fichier qui contient bel et bien les tests décri |
| [`catalogue-index-omits-its-own-entries`](error-classes.md#catalogue-index-omits-its-own-entries) | the Index table at the top of a catalogue stops listing the entries below it. Every reader who scans the index concludes a class does not exist — and  |
| [`named-guard-deleted-while-the-class-reads-guarded`](error-classes.md#named-guard-deleted-while-the-class-reads-guarded) | une classe d'erreur affiche `status: guarded` et nomme un test qui n'existe plus. La classe est rouverte, le catalogue dit le contraire, et rien n'éch |
| [`procedure-outlives-its-task`](error-classes.md#procedure-outlives-its-task) | un document de procédure présente comme À FAIRE, priorité comprise, une tâche close depuis des jours ou des semaines. Le lecteur ouvre une séance en c |
| [`resume-header-claims-what-the-index-denies`](error-classes.md#resume-header-claims-what-the-index-denies) | l'en-tête d'un fichier d'état énumère des tâches comme restant à faire alors que le corps du même fichier les dit closes. Le lecteur ouvre sa séance a |
| [`exec-bit-lost-outside-the-index`](error-classes.md#exec-bit-lost-outside-the-index) | un script du dépôt refuse de s'exécuter depuis un clone frais — et son propre mode d'emploi dit de le lancer ainsi. |
| [`one-guide-three-sources`](error-classes.md#one-guide-three-sources) | un lecteur anglophone reçoit une procédure abandonnée côté français ; le PDF d'une langue décrit plus d'étapes que l'autre. Personne ne le voit : ces  |
| [`extracted-rule-with-one-caller-rewired`](error-classes.md#extracted-rule-with-one-caller-rewired) | une règle est factorisée pour être partagée, la factorisation est annoncée dans les commentaires — et les deux copies coexistent, parce qu'un seul app |
| [`layout-keyed-by-a-hand-written-list`](error-classes.md#layout-keyed-by-a-hand-written-list) | une mise en page range correctement ce que son auteur avait en tête, et range tout le reste dans un groupe par défaut — qui porte un titre. L'élément  |
| [`detection-keyed-on-the-filename`](error-classes.md#detection-keyed-on-the-filename) | un fichier valide est refusé, ou pire, un fichier invalide est accepté — selon comment il s'appelle. Renommer corrige ou casse, ce qui apprend à l'uti |
| [`a-caption-written-beside-the-behaviour-instead-of-derived-from-it`](error-classes.md#a-caption-written-beside-the-behaviour-instead-of-derived-from-it) | la légende sous une figure affirme trois choses fausses en même temps, sans qu'aucune ne soit un bug de calcul. Vu au rendu le 2026-09-10 en « Chacune |
| [`a-note-outlives-the-figure-it-explains`](error-classes.md#a-note-outlives-the-figure-it-explains) | la figure est juste et le lecteur croit qu'elle est vide, parce que la légende sous elle décrit l'ancienne figure. Signalé le 2026-09-11 **après** le  |
| [`a-document-that-cannot-be-current-in-its-own-commit`](error-classes.md#a-document-that-cannot-be-current-in-its-own-commit) | un document généré est **périmé à l'instant même où on le commite**. Son contrôle de fraîcheur est rouge juste après un `make` qui vient de le produir |
| [`a-make-target-that-claims-a-barrier-it-does-not-hold`](error-classes.md#a-make-target-that-claims-a-barrier-it-does-not-hold) | une cible `make` annonce dans son aide qu'elle est la barrière — « (CI) » — alors qu'aucun workflow ne la lance. Le document EST gardé, mais par un au |
| [`a-generated-document-with-no-freshness-guard`](error-classes.md#a-generated-document-with-no-freshness-guard) | un document **généré** n'a ni contrôle de fraîcheur ni test jumeau, là où tous ses pairs en ont. Il se périme en silence et continue d'être lu comme u |
| [`a-scrape-target-that-is-up-measuring-nothing`](error-classes.md#a-scrape-target-that-is-up-measuring-nothing) | une cible de scrutation répond `up`, sa page `/metrics` se sert correctement, et elle ne mesure **rien** de ce qu'elle est censée mesurer. La couvertu |
| [`a-procedure-that-omits-a-surface-it-must-touch`](error-classes.md#a-procedure-that-omits-a-surface-it-must-touch) | une procédure écrite est correcte, détaillée, et **omet une des surfaces que le geste doit toucher**. Celui qui la suit fait le travail et laisse une  |

## un-contrôle-qui-ne-peut-jamais-passer

**Où ce contrôle s'exécute-t-il — la machine où il tourne a-t-elle ce qu'il lui faut pour réussir un jour ?**

Règle de rattachement : `never-pass|env-independent|host-env|container|reachab|unreachable|not-wired|orphan|dead-code|no-caller|unrun|install|shares-the-fate|unstated-import-path|below-detection` sur l'identifiant et le symptôme. 13 classe(s).

| classe | symptôme |
|---|---|
| [`make-fail-late`](error-classes.md#make-fail-late) | a Makefile target invokes a runtime dependency (Docker / venv / Postgres / `uv` / `streamlit`) and crashes mid-execution instead of failing fast with  |
| [`tool-imports-the-app-without-a-path`](error-classes.md#tool-imports-the-app-without-a-path) | a standalone script under `tools/` dies at startup with `ModuleNotFoundError: No module named 'src'`, however it is invoked — including from the repo  |
| [`ci-gate-with-no-local-counterpart`](error-classes.md#ci-gate-with-no-local-counterpart) | `main` est rouge et personne ne le sait avant le mail de GitHub. Le commit est passé sur le poste — `pre-commit` était installé et vert — parce que le |
| [`a-blocking-gate-red-on-its-own-syntax`](error-classes.md#a-blocking-gate-red-on-its-own-syntax) | une porte bloquante est rouge, et ce qu'elle nomme n'existe pas. Le message dit « ces touches sont réelles » ; on cherche un défaut du produit, il n'y |
| [`no-db-signature-opens-a-connection`](error-classes.md#no-db-signature-opens-a-connection) | un garde tombe pour une raison qui n'est pas la sienne. Le rapport nomme sa classe d'erreur, et la trace dessous dit `psycopg2.OperationalError` — on  |
| [`check-calls-a-binary-its-image-lacks`](error-classes.md#check-calls-a-binary-its-image-lacks) | a check running INSIDE a container shells out to a host binary (`rclone`, `git`, `docker`, `psql`) that is not in that image. It never crashes — it ta |
| [`script-unreachable-from-its-dependencies`](error-classes.md#script-unreachable-from-its-dependencies) | a runbook step that reads perfectly cannot be executed anywhere. `can't open file '/app/tools/<script>.py'` from a container, `ModuleNotFoundError: ps |
| [`content-rendered-outside-its-container`](error-classes.md#content-rendered-outside-its-container) | le contenu d'un onglet (ou de tout conteneur Streamlit) se rend **à côté** au lieu de dedans. Aucune exception, tous les éléments présents, tous les t |
| [`route-depends-on-an-unstated-import-path`](error-classes.md#route-depends-on-an-unstated-import-path) | l'application démarre proprement puis meurt au **premier clic**, sur un `ModuleNotFoundError` qui nomme un paquet présent sur le disque. |
| [`backup-shares-the-fate-of-what-it-protects`](error-classes.md#backup-shares-the-fate-of-what-it-protects) | les sauvegardes tournent chaque nuit, réussissent, et ne survivraient pas à l'incident contre lequel elles existent. |
| [`red-gate-hides-every-step-behind-it`](error-classes.md#red-gate-hides-every-step-behind-it) | la CI est rouge et le reste des jours. Chaque exécution rapporte le même échec, à la même étape, et **rien de ce qui vient après n'a tourné** — donc r |
| [`a-gate-that-can-never-be-green`](error-classes.md#a-gate-that-can-never-be-green) | une porte de comparaison rapporte une divergence **à chaque exécution**, quoi qu'on fasse. On la lit deux fois, on la contourne la troisième, et le jo |
| [`a-load-guard-that-counts-names-instead-of-measuring-load`](error-classes.md#a-load-guard-that-counts-names-instead-of-measuring-load) | un garde de qualité de mesure refuse systématiquement, sur une machine objectivement inactive. On finit par lui passer `--force`, ce qui le retire pou |

## un-coût-payé-sans-contrepartie

**Ce travail est-il payé par quelqu'un — temps de CI, premier écran, attention du lecteur — et lui rend-il quelque chose ?**

Règle de rattachement : `runs-twice|concurrency-group|overload|competing-for-one-decision|costs-more-than|waste|duplicate-run|too-many|drags-a-.*-behind|paid-by|first-render|recomputes-what-its-caller|memo-field-written` sur l'identifiant et le symptôme. 16 classe(s).

| classe | symptôme |
|---|---|
| [`ci-runs-twice-for-one-commit`](error-classes.md#ci-runs-twice-for-one-commit) |  |
| [`ci-has-no-concurrency-group`](error-classes.md#ci-has-no-concurrency-group) |  |
| [`too-many-charts-competing-for-one-decision`](error-classes.md#too-many-charts-competing-for-one-decision) | une vue s'ouvre sur un mur de graphiques. Aucun n'est faux, aucun n'est de trop pris isolément, et l'utilisateur ne sait pas où regarder. |
| [`image-ships-what-it-never-imports`](error-classes.md#image-ships-what-it-never-imports) | une image Docker embarque des centaines de mégaoctets qu'aucun de ses processus n'importera jamais. Rien ne casse : le build est plus long, le déploie |
| [`orchestrator-costs-more-than-what-it-orchestrates`](error-classes.md#orchestrator-costs-more-than-what-it-orchestrates) | l'outil qui coordonne le travail consomme plus que le travail lui-même, et personne ne le remarque parce que tout est vert. |
| [`a-shared-module-drags-a-view-behind-it`](error-classes.md#a-shared-module-drags-a-view-behind-it) | le premier rendu d'une page quadruple, et rien dans le code ne le montre. Mesuré le 2026-09-12 : `setup_completion` — lu dans le chemin de la barre la |
| [`a-prudence-rule-with-no-expiry-becomes-a-freeze`](error-classes.md#a-prudence-rule-with-no-expiry-becomes-a-freeze) | une dépendance reste gelée des ANNÉES sur une version que personne n'a choisie, et rien ne le signale. Le symptôme visible est ailleurs et ne ressembl |
| [`a-cache-whose-sharing-depends-on-an-unasserted-scheduler-flag`](error-classes.md#a-cache-whose-sharing-depends-on-an-unasserted-scheduler-flag) | un montage d'optimisation est en place, tous les tests sont verts, et le gain qu'il devait rendre est **nul**. Rien ne rougit, parce que le montage n' |
| [`a-gate-that-pays-a-check-twice`](error-classes.md#a-gate-that-pays-a-check-twice) | le job critique de la CI est lent sans qu'aucun contrôle ne soit lent en soi. Chaque ligne a une raison d'être, et c'est exactement pourquoi personne  |
| [`a-memo-field-written-and-never-consulted`](error-classes.md#a-memo-field-written-and-never-consulted) | un attribut de mémoïsation existe, il est rempli à chaque appel, et le travail est refait quand même. Aucun signal : **un cache sans succès se comport |
| [`a-renderer-that-recomputes-what-its-caller-already-has`](error-classes.md#a-renderer-that-recomputes-what-its-caller-already-has) | une page fait exactement deux fois le même travail, et rien ne le montre. Les deux appels sont à quelques lignes l'un de l'autre et se lisent comme de |
| [`first-paint-chart-overload`](error-classes.md#first-paint-chart-overload) | a view opens on several charts that all bear on the same decision. Nothing is wrong with any single chart; together they leave the artist unable to sa |
| [`download-payload-rebuilt-per-rerun`](error-classes.md#download-payload-rebuilt-per-rerun) | une page Streamlit reconstruit à chaque rerun le fichier qu'elle propose au téléchargement. Déplier un accordéon suffit à repayer le rendu complet d'u |
| [`an-alert-that-never-changes-stops-being-read`](error-classes.md#an-alert-that-never-changes-stops-being-read) | une alerte quotidienne signale correctement un problème réel, à l'identique, pendant des mois. Le lecteur cesse de l'ouvrir, et le soir où une VRAIE p |
| [`a-subplan-re-executed-by-a-misestimated-row-count`](error-classes.md#a-subplan-re-executed-by-a-misestimated-row-count) | une vue SQL passe de quelques dizaines de millisecondes à plusieurs minutes sans qu'aucune donnée n'ait changé, et la page qui la lit rend `canceling  |
| [`a-log-counter-whose-cardinality-follows-the-codebase`](error-classes.md#a-log-counter-whose-cardinality-follows-the-codebase) | un compteur de lignes de journal étiqueté par nom de logger complet crée une série par MODULE et par niveau. Le nombre de séries suit alors la taille  |

## un-seuil-écrit-d-instinct

**Ce seuil vient-il de la distribution réelle, ou d'une intuition ? Le test épingle-t-il la réalité ou la constante ?**

Règle de rattachement : `threshold|seuil|min[_-]|floor|ceiling|limit|budget|quota|window|magic-number|hardcoded` sur l'identifiant et le symptôme. 11 classe(s).

| classe | symptôme |
|---|---|
| [`trigger-threshold-split`](error-classes.md#trigger-threshold-split) | a rule, the agent it spawns, and the hook that signals it state different thresholds. The agent's `description` wins, because it is the only one the r |
| [`an-exemption-that-outlives-what-it-exempted`](error-classes.md#an-exemption-that-outlives-what-it-exempted) | une exemption reste dans une liste après la disparition de ce qu'elle exemptait. Elle ne casse rien le jour où ça arrive — elle devient du **budget**  |
| [`a-threshold-true-at-one-grain-and-false-at-another`](error-classes.md#a-threshold-true-at-one-grain-and-false-at-another) | un garde rougit alors que rien n'est cassé, uniquement parce que la figure a changé de PAS. Le sien exigeait « au moins 30 pas non mesurés couverts »  |
| [`a-threshold-carried-across-instruments`](error-classes.md#a-threshold-carried-across-instruments) | un déclencheur chiffré se déclenche — ou ne se déclenche pas — et la décision qui en découle repose sur une comparaison qui n'a jamais eu de sens. Rie |
| [`object-dtype-numeric-op`](error-classes.md#object-dtype-numeric-op) | a numeric DB column that contains a NULL loads as pandas `object` dtype; subsequent arithmetic + `Series.round(n)` then raises `TypeError: Expected nu |
| [`second-factor-budget-refunded-by-the-first`](error-classes.md#second-factor-budget-refunded-by-the-first) | a multi-factor flow rate-limits each step, and the earlier step's success resets the later step's budget. The attacker holds the earlier factor by ass |
| [`validation-bound-invented-not-read-from-the-schema`](error-classes.md#validation-bound-invented-not-read-from-the-schema) | un validateur qui **lève** refuse une donnée parfaitement légitime, parce qu'une de ses bornes a été tapée à la main au lieu d'être lue dans le schéma |
| [`page-window-answers-a-per-entity-question`](error-classes.md#page-window-answers-a-per-entity-question) | une vue de supervision affiche une fraction des entités et présente l'absence comme une donnée — « aucun run » au lieu de « je n'ai pas regardé ». Tou |
| [`a-window-widened-to-its-bucket-instead-of-the-bucket-clipped`](error-classes.md#a-window-widened-to-its-bucket-instead-of-the-bucket-clipped) | une figure ou un total bornés par une période affichent PLUS que ce que la période contient. Mesuré le 2026-09-10 sur l'accueil : « 12 mois · Par anné |
| [`one-scale-for-two-contracts`](error-classes.md#one-scale-for-two-contracts) | une tuile de fraîcheur passe au **rouge** pour un comportement parfaitement normal. Signalé le 2026-09-12 : « c'est en rouge alors qu'on a que 3 jours |
| [`a-ratio-between-two-instruments-that-ignores-the-floor-of-one`](error-classes.md#a-ratio-between-two-instruments-that-ignores-the-floor-of-one) | un RAPPORT entre deux grandeurs oriente des semaines de travail, et il est faux **dans le mauvais sens**. Les deux nombres sont justes, aucun calcul n |

## une-écriture-qui-écrase

**Cette écriture peut-elle détruire ce qu'un autre vient d'écrire — et le saurait-on ?**

Règle de rattachement : `overwrit|écrase|clobber|upsert|conflict|restore|delete|drop|purge|lost|data-loss|resurrect|rotation` sur l'identifiant et le symptôme. 7 classe(s).

| classe | symptôme |
|---|---|
| [`snapshot-fixture-hook-reflow`](error-classes.md#snapshot-fixture-hook-reflow) | a byte-exact golden/snapshot fixture under `tests/fixtures/` is silently reflowed by the `trailing-whitespace` / `end-of-file-fixer` pre-commit hooks  |
| [`unguarded-drop-replayed-alone`](error-classes.md#unguarded-drop-replayed-alone) | a table silently loses its primary key. Nothing errors visibly at the application level; duplicate rows become possible and `ON CONFLICT` upserts star |
| [`a-surgical-restore-erases-work-nothing-will-give-back`](error-classes.md#a-surgical-restore-erases-work-nothing-will-give-back) | du travail non commité disparaît sans trace ni message. Aucune erreur, aucun avertissement : la commande réussit, et ce qu'elle a écrasé n'est ni dans |
| [`a-limiter-consumed-in-two-steps`](error-classes.md#a-limiter-consumed-in-two-steps) | un limiteur ATOMIQUE ne borne que les tentatives séquentielles. N requêtes simultanées obtiennent toutes l'autorisation, le budget affiché est respect |
| [`prune-scoped-wider-than-what-it-refreshed`](error-classes.md#prune-scoped-wider-than-what-it-refreshed) | des données de production disparaissent, sans erreur, sans trace. Le nettoyage qui suit une collecte supprime plus large que ce que cette collecte vie |
| [`a-document-slice-bounded-by-the-wrong-heading-level`](error-classes.md#a-document-slice-bounded-by-the-wrong-heading-level) | un découpage de document Markdown emporte **plus que ce qu'il visait**, et rien dans le résultat ne le dit. Le 2026-09-13 : la rotation de trois secti |
| [`a-repair-that-reverts-what-a-successor-widened`](error-classes.md#a-repair-that-reverts-what-a-successor-widened) | un correctif de rejouabilité fait DISPARAÎTRE une colonne, une contrainte ou un index qu'une migration ultérieure avait ajoutés. Le fichier corrigé pa |

## le-temps-et-l-horloge

**Cette date est-elle celle de l'événement ou celle de la collecte ? Et dans quel fuseau ?**

Règle de rattachement : `date|time|clock|tz|utc|timezone|fresh|schedule|cron|window-applied|day|month|period` sur l'identifiant et le symptôme. 19 classe(s).

| classe | symptôme |
|---|---|
| [`naive-datetime-now`](error-classes.md#naive-datetime-now) | bare `datetime.now()` persisted to DB / returned from API → host-TZ-naïve, mis-orders vs aware `+00:00` siblings (`.claude/rules/python.md`). |
| [`mixed-date-timestamp`](error-classes.md#mixed-date-timestamp) | a collection mixes psycopg2 `datetime.date` (raw DATE column) and `pd.Timestamp` (a `pd.to_datetime`'d Series); `sorted()` / `pd.merge` on `date` / an |
| [`ingest-time-as-release-date`](error-classes.md#ingest-time-as-release-date) | an `entity_period_filter`/`EntitySpec` orders "latest release" by `MIN(date_column)` where `date_column` is the ingest timestamp (`collected_at`) → de |
| [`a-date-that-does-not-say-which-clock-produced-it`](error-classes.md#a-date-that-does-not-say-which-clock-produced-it) | aucun, tant qu'on ne compare pas deux périodes — et alors l'écart est de quelques heures, change avec la saison, et personne ne peut dire s'il est rée |
| [`a-figure-under-a-period-selector-that-ignores-it`](error-classes.md#a-figure-under-a-period-selector-that-ignores-it) | l'artiste choisit « 30 jours » et la figure lui montre autre chose, sans que rien ne le dise. Aucune erreur, aucun trou : des barres pleines, sur une  |
| [`a-window-applied-to-the-wrong-date`](error-classes.md#a-window-applied-to-the-wrong-date) | le filtre de période EST appliqué, et la figure répond quand même à une autre question. Aucun garde ne peut le voir : tous demandent *que* la fenêtre  |
| [`tz-aware-naive-mix`](error-classes.md#tz-aware-naive-mix) | a column of ISO timestamp strings where some carry a tz offset (`+00:00`) and some are naive → `pd.to_datetime(series)` or a Plotly datetime coercion  |
| [`freshness-measured-on-write-time`](error-classes.md#freshness-measured-on-write-time) | a source is reported FRESH while its data is months or years old. The collector still runs and still writes, so the write timestamp advances nightly — |
| [`age-computed-against-another-clock`](error-classes.md#age-computed-against-another-clock) | a staleness check compares a stored timestamp against a clock that is not the one that wrote it. The verdict is wrong by the offset between the two, i |
| [`upsert-freezes-its-own-timestamp`](error-classes.md#upsert-freezes-its-own-timestamp) | an upsert refreshes a row's data and leaves its `collected_at` at the value of the first insert. The rows are current; every reader of `MAX(collected_ |
| [`dag-without-dagrun-timeout`](error-classes.md#dag-without-dagrun-timeout) | un DAG qui se bloque ne se termine jamais, garde son créneau, et peut être enregistré **success**. Aucune alerte : Airflow n'a rien à signaler tant qu |
| [`timestamptz-parsed-across-a-dst-change`](error-classes.md#timestamptz-parsed-across-a-dst-change) | une page plante avec `ValueError: Tz-aware datetime.datetime cannot be converted to datetime64 unless utc=True, at position N`. Elle marchait la veill |
| [`snapshot-keyed-by-a-per-row-timestamp`](error-classes.md#snapshot-keyed-by-a-per-row-timestamp) | un agrégat sur « le dernier relevé » ne somme qu'**une** ligne du lot, et le delta qui en découle part à l'utilisateur comme un effondrement. |
| [`bom-survives-the-encoding-fallback`](error-classes.md#bom-survives-the-encoding-fallback) | un export parfaitement valide est refusé, et le message d'erreur affiche la BONNE colonne. « Type non reconnu — colonnes vues : date, streams » alors  |
| [`two-clocks-subtracted-from-each-other`](error-classes.md#two-clocks-subtracted-from-each-other) | un âge, une durée ou une borne de période est faux d'une à deux heures, et le décalage change avec la saison. Mesuré le 2026-09-10 : une source collec |
| [`a-batch-that-commits-one-row-at-a-time`](error-classes.md#a-batch-that-commits-one-row-at-a-time) | une écriture de lot est lente, et — le vrai défaut — un échec en cours de route laisse la première moitié en base. Mesuré le 2026-09-10 : sur 1 001 li |
| [`a-method-change-counted-as-growth`](error-classes.md#a-method-change-counted-as-growth) | une figure ou un total affiche un pic énorme et parfaitement faux, à une date où rien n'est arrivé. Le chiffre est DÉRIVÉ correctement d'une série cor |
| [`a-join-on-a-display-name-loses-what-the-name-normalises`](error-classes.md#a-join-on-a-display-name-loses-what-the-name-normalises) | une figure ou un total ne montre qu'une partie du catalogue, sans erreur ni ligne manquante visible. Mesuré le 2026-09-14 : joindre `track_release_ref |
| [`a-zero-that-predates-the-thing-it-measures`](error-classes.md#a-zero-that-predates-the-thing-it-measures) | une courbe dessine des mois de plat à zéro avant que l'objet mesuré n'existe. Mesuré le 2026-09-14 : « Ô Chiotte l'arbitre Tucome Back », sorti le 30/ |

## la-frontière-avec-le-dehors

**Ce que ce code envoie dehors — un mail, une requête, un paiement, un secret — est-il ce qu'on croit, et vers qui ?**

Règle de rattachement : `secret|token|credential|auth|jwt|mail|smtp|http|webhook|stripe|payment|url|cors|redact|external|api-|fstring-identifier|string-substitution|untrusted|privileged|access-gate|is-not-an-identity|rendered-to-the-visitor|bare-except|containment` sur l'identifiant et le symptôme. 26 classe(s).

| classe | symptôme |
|---|---|
| [`csv-formula-injection`](error-classes.md#csv-formula-injection) | user-controlled values (song/campaign names, usernames) exported via `to_csv`/`to_excel` without defang → a cell like `=cmd\|'/c calc'!A1` executes whe |
| [`central-app-missing`](error-classes.md#central-app-missing) | a shared central-app credential (SPOTIFY_CLIENT_ID/SECRET, YOUTUBE_API_KEY, SOUNDCLOUD_CLIENT_ID/SECRET, META_ACCESS_TOKEN) is absent or expired in pr |
| [`tenant-identity-reaches-a-url-unvalidated`](error-classes.md#tenant-identity-reaches-a-url-unvalidated) | a free-text field a tenant controls is interpolated into a REST path, and the raw response is echoed back to them. `requests` does not percent-encode  |
| [`secret-in-an-exception-message`](error-classes.md#secret-in-an-exception-message) | a credential is passed as a QUERY PARAMETER, so a `requests` exception message embeds the full prepared URL. Surfacing the exception — to a user, or i |
| [`server-side-render-fetches-tenant-chosen-urls`](error-classes.md#server-side-render-fetches-tenant-chosen-urls) | a renderer that runs on the SERVER builds a document from tenant data and then resolves the resources it references. Any markup surviving into that do |
| [`unattributable-payment-link`](error-classes.md#unattributable-payment-link) | un client paie et n'est jamais provisionné. Le paiement réussit côté Stripe, le webhook renvoie 200, et le compte reste sur son ancien plan. Rien n'éc |
| [`sender-identity-composed-twice`](error-classes.md#sender-identity-composed-twice) | les e-mails du produit arrivent sous un nom d'expéditeur qui n'est pas le sien — ici « Music Cross Platform Dashboard & Trigger Spotify » au lieu de « |
| [`a-dev-instance-sends-production-shaped-mail`](error-classes.md#a-dev-instance-sends-production-shaped-mail) | une alerte arrive dans une vraie boîte mail, annonce une panne, et **la production va très bien**. Elle vient d'une instance de développement. Rien da |
| [`containment-ignores-what-it-leaves-out`](error-classes.md#containment-ignores-what-it-leaves-out) | un titre court s'associe tout seul à un libellé long qui le contient — un mix DJ, un set, un morceau d'un autre artiste. Le score est le même que pour |
| [`a-probe-that-runs-the-whole-dag-in-production`](error-classes.md#a-probe-that-runs-the-whole-dag-in-production) | une « vérification d'une seule tâche » (`airflow tasks test <dag> <task>`) lancée en production exécute en réalité TOUT le DAG, mails compris ; juste  |
| [`a-secret-committed-to-a-public-history`](error-classes.md#a-secret-committed-to-a-public-history) | `gitleaks` rouge 5 nuits sur 5, lu par personne ; un `git clone` suffit à lire des identifiants de production — sans compte, sans trace |
| [`sql-fstring-identifier`](error-classes.md#sql-fstring-identifier) | a table/column name interpolated into SQL via f-string without `frozenset` allowlist validation (CLAUDE.md rule #8) → SQL injection. |
| [`bare-except`](error-classes.md#bare-except) | un `except:` nu avale aussi `KeyboardInterrupt` et `SystemExit` — donc une interruption volontaire et l'arrêt du processus — et il ne dit jamais QUELL |
| [`api-partial-date-into-date-column`](error-classes.md#api-partial-date-into-date-column) | a collector fails with `invalid input syntax for type date: "2013"` and the artist loses EVERY row of that run, not just the offending one. Latent for |
| [`app-id-confused-with-ad-account-id`](error-classes.md#app-id-confused-with-ad-account-id) | `Error validating application. Cannot get application info due to a system error.` on every Meta call, which reads as "the token expired" — so the inv |
| [`trusted-value-read-from-an-untrusted-header`](error-classes.md#trusted-value-read-from-an-untrusted-header) | a security control keys on a value taken from a request header the caller controls, so the caller varies the key and the control never fires. It looks |
| [`sentinel-means-privileged-and-missing`](error-classes.md#sentinel-means-privileged-and-missing) | one sentinel value carries two unrelated meanings — "this caller may see everything" and "this caller has no scope" — so the branch written for the fi |
| [`resave-erases-a-secret-the-form-cannot-show`](error-classes.md#resave-erases-a-secret-the-form-cannot-show) | pressing "save" on a form destroys a stored secret the form has no field for. The UI reports success, nothing logs a warning, and the loss only surfac |
| [`test-sends-real-mail-to-real-people`](error-classes.md#test-sends-real-mail-to-real-people) | real email arrives in a real inbox after a test run, from the project's own SMTP account, carrying a `http://localhost:8501` link that no recipient ca |
| [`test-calls-a-real-api`](error-classes.md#test-calls-a-real-api) | la suite consomme du quota d'API réel et échoue en CI dès qu'il n'y a pas de réseau, sans qu'aucun test ne le dise. Contrairement à son jumeau `test-s |
| [`traceback-rendered-to-the-visitor`](error-classes.md#traceback-rendered-to-the-visitor) | une exception non rattrapée affiche sa **traceback complète dans le navigateur** du visiteur — chemins de fichiers, lignes de code, et le message de l |
| [`boundary-narrower-than-the-surface`](error-classes.md#boundary-narrower-than-the-surface) | une frontière d'exception EXISTE, elle est documentée, elle fonctionne — et le défaut passe quand même, parce qu'elle n'entoure qu'une partie du code. |
| [`nonprod-instance-puts-mail-on-the-wire`](error-classes.md#nonprod-instance-puts-mail-on-the-wire) | une instance hors production expédie de vrais e-mails à de vraies boîtes. Ils ressemblent à une panne, il faut les ouvrir, les lire et les écarter — e |
| [`alert-repeats-an-unactionable-verdict`](error-classes.md#alert-repeats-an-unactionable-verdict) | la même alerte arrive chaque nuit avec le même contenu, sur un problème dont le geste correctif est une action humaine dans une interface tierce. Le l |
| [`a-handle-is-not-an-identity`](error-classes.md#a-handle-is-not-an-identity) | un artiste colle l'adresse de son profil, l'app résout un identifiant, l'enregistre, et collecte les chiffres de quelqu'un d'autre. Rien n'échoue : la |
| [`a-query-assembled-by-string-substitution`](error-classes.md#a-query-assembled-by-string-substitution) | une requête SQL fabriquée en appliquant `.replace()` à une autre requête. Elle se compile, s'exécute, et rend **zéro ligne**. Comme la lecture est env |

## une-configuration-qui-diverge-de-la-prod

**Ce que le dépôt déclare est-il ce que la production exécute ?**

Règle de rattachement : `prod|deploy|schema-drift|migration|image|docker|compose|pin|lock|requirements|manifest|ddl|init_db|version|montée de majeure|valeur par défaut|majeure|reload-that-does-not-reload|bind-address-that-hides-the-service` sur l'identifiant et le symptôme. 43 classe(s).

| classe | symptôme |
|---|---|
| [`streamlit-pin-drift`](error-classes.md#streamlit-pin-drift) | a package pinned `==X` in one manifest while another manifest / the lockfile / the installed env pins `==Y` → prod≠dev, "works locally breaks in Docke |
| [`prod-canonical-schema-drift`](error-classes.md#prod-canonical-schema-drift) | the live prod DB has a table/column the version-controlled schema (`init_db.sql` + `migrations/*.sql`) lacks, or vice-versa. Code reading/writing the  |
| [`collector-import-dotenv-crash`](error-classes.md#collector-import-dotenv-crash) | a module-level `load_dotenv()` in a collector (not wrapped in try/except) raises `PermissionError` at import when the mounted `/opt/airflow/.env` is r |
| [`env-not-wired-to-service`](error-classes.md#env-not-wired-to-service) | a service's CODE reads a central-app env var (`os.getenv('SOUNDCLOUD_CLIENT_ID')` …) that the service's `docker-compose` block does NOT declare → empt |
| [`prod-compose-drift`](error-classes.md#prod-compose-drift) | the live prod `docker-compose.yml` is UNTRACKED (gitignored) and hand-derived, so it silently diverges from the canonical `docker-compose.example.yml` |
| [`migrate-heals-only-if-run-to-completion`](error-classes.md#migrate-heals-only-if-run-to-completion) | `make migrate` prints success while `psql` errors scroll past. The full run is self-consistent, so nothing looks wrong — but a run interrupted at the  |
| [`env-resolved-against-cwd`](error-classes.md#env-resolved-against-cwd) | a tool reports "credential NOT configured" for a credential that is configured, or a process silently runs with no configuration at all. The red names |
| [`repo-copy-of-a-config-is-not-what-runs`](error-classes.md#repo-copy-of-a-config-is-not-what-runs) | a config file lives in the repo, looks authoritative, and is not the one the service loads. Editing it changes nothing, reading it describes a deploym |
| [`script-replaced-while-it-runs`](error-classes.md#script-replaced-while-it-runs) | a deploy script is updated, pushed, and the very deploy that pulls the update does not run it. The run reports success, so the change looks deployed — |
| [`compose-omits-a-package-the-dags-import`](error-classes.md#compose-omits-a-package-the-dags-import) | un contrôle répond honnêtement « je n'ai pas pu tourner » (`ModuleNotFoundError`), et cette honnêteté remonte en ligne de sujet comme une alarme métie |
| [`the-only-copy-is-consumed-on-read`](error-classes.md#the-only-copy-is-consumed-on-read) | un import réussit, produit des chiffres douteux une semaine plus tard, et **il n'existe plus aucune copie de ce qui a été envoyé** pour trancher. |
| [`a-rule-copied-is-a-rule-that-will-diverge`](error-classes.md#a-rule-copied-is-a-rule-that-will-diverge) | le même locataire lit trois nombres différents pour la même métrique, au même instant, sur trois surfaces du même produit. Mesuré le 2026-09-10 : le t |
| [`a-zero-that-was-never-measured-passes-for-a-measurement`](error-classes.md#a-zero-that-was-never-measured-passes-for-a-measurement) | une colonne de mesure est remplie sur toutes les lignes, donc elle a l'air mesurée, et toute moyenne calculée dessus est fausse — pas approximative, f |
| [`a-create-if-not-exists-that-declares-nothing`](error-classes.md#a-create-if-not-exists-that-declares-nothing) | le fichier qui prétend décrire le schéma décrit autre chose, et rien ne le dit. Une colonne porte en base un type différent de celui que `init_db.sql` |
| [`a-procedural-rule-in-the-database`](error-classes.md#a-procedural-rule-in-the-database) | une règle métier vit en PL/pgSQL. Elle n'est ni testable par pytest, ni lisible dans une revue de diff Python, ni déplaçable — et le jour où elle est  |
| [`an-action-pin-derived-from-a-version-number`](error-classes.md#an-action-pin-derived-from-a-version-number) | les CINQ jobs d'un workflow échouent en **neuf secondes**, à « Prepare all required actions », avant la moindre mise en route : `Unable to resolve act |
| [`a-reload-that-does-not-reload-what-you-changed`](error-classes.md#a-reload-that-does-not-reload-what-you-changed) | on pose un fichier de configuration, on recharge le service, la commande sort en 0, le fichier est bien là — et **le réglage n'est pas appliqué**. Rie |
| [`a-replica-that-builds-its-own-image`](error-classes.md#a-replica-that-builds-its-own-image) | une seconde instance d'un service, définie par `extends`, sert un artefact DIFFÉRENT de celui qu'elle réplique — code applicatif d'un autre commit, au |
| [`a-local-measurement-presented-as-a-production-fact`](error-classes.md#a-local-measurement-presented-as-a-production-fact) | un chiffre relevé sur l'environnement de développement est énoncé comme une propriété de la PRODUCTION. Il n'y a ni erreur ni exception : la requête r |
| [`a-test-that-only-ever-ran-on-its-authors-machine`](error-classes.md#a-test-that-only-ever-ran-on-its-authors-machine) | un test vert sur le poste et rouge en CI — ou l'inverse — sur un code identique. Il n'a jamais tourné que dans UNE des deux formes d'environnement : s |
| [`a-major-upgrade-that-moves-a-default`](error-classes.md#a-major-upgrade-that-moves-a-default) | une montée de MAJEURE laisse le build vert et rend une de ses garanties fausse. Rien n'échoue, rien n'avertit : le seul endroit où le changement exist |
| [`audit-reads-the-constraints-not-the-installed-set`](error-classes.md#audit-reads-the-constraints-not-the-installed-set) | l'audit de vulnérabilités rend un rapport propre pendant que le parc réellement installé porte des dizaines d'avis. Il lit un fichier de **contraintes |
| [`config-not-env`](error-classes.md#config-not-env) | a bootstrap/runtime path subscripts `config['…']` directly (config.yaml-only) instead of reading env first → `KeyError` in prod where there is no `con |
| [`migration-ahead-of-its-code`](error-classes.md#migration-ahead-of-its-code) | a migration that changes a **key** (primary key, unique constraint, conflict target) is applied to production while the code that uses the new key is  |
| [`dead-argument-from-a-major-version-ago`](error-classes.md#dead-argument-from-a-major-version-ago) | un paramètre d'une version majeure précédente traîne dans le code. Il ne fait **rien** sur la version qui tourne, donc rien ne le signale — et il rend |
| [`on-conflict-target-without-index`](error-classes.md#on-conflict-target-without-index) | l'import ne se dégrade pas, il LÈVE — `ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification`. Prouvé en production |
| [`config-corrected-in-the-file-that-loses`](error-classes.md#config-corrected-in-the-file-that-loses) | a credential is investigated, found wrong, and corrected — and nothing changes. Every later look at the corrected file confirms the fix, so the invest |
| [`input-nobody-would-type-reaches-the-driver`](error-classes.md#input-nobody-would-type-reaches-the-driver) | a caller-supplied string reaches the database driver in a shape the driver refuses, and the refusal is an unhandled exception rather than a rejected r |
| [`dead-content-that-still-ships`](error-classes.md#dead-content-that-still-ships) | un utilisateur suit une consigne que le produit ne demande plus, et échoue. La consigne vient d'un contenu maintenu, traduit, et que plus rien n'affic |
| [`tests-run-a-different-core-than-prod`](error-classes.md#tests-run-a-different-core-than-prod) | la suite valide le code contre une version majeure d'un socle que la production n'exécute pas, et rend vert. Rien ne signale l'écart : les deux moitié |
| [`websocket-dies-behind-the-proxy`](error-classes.md#websocket-dies-behind-the-proxy) | « je clique sur un bouton et il ne se passe rien, je dois recliquer ». Pas UN bouton — **tous**, par intermittence, et avec **aucune réaction** : ni s |
| [`verified-locally-observed-in-prod`](error-classes.md#verified-locally-observed-in-prod) | un utilisateur signale plusieurs fois la même absence ; chaque vérification confirme que la chose est là ; les corrections successives portent sur le  |
| [`ui-state-not-addressable`](error-classes.md#ui-state-not-addressable) | chaque demande de « rediriger vers X » produit un bug de mise en page — la barre bouge sous l'utilisateur, un message s'affiche dans un panneau fermé, |
| [`test-pinned-to-a-row-of-the-authors-database`](error-classes.md#test-pinned-to-a-row-of-the-authors-database) | un test est vert chez son auteur et rouge partout ailleurs, sur une erreur de base de données qui ne parle pas du sujet gardé — une clé étrangère, une |
| [`message-written-before-a-rerun`](error-classes.md#message-written-before-a-rerun) | une action réussit, son message est écrit, et l'écran est vide. Le code est correct, la fonction appelée a fait son travail, et aucun test de rendu ne |
| [`a-key-that-forbids-history`](error-classes.md#a-key-that-forbids-history) | on conclut qu'une source « ne fournit pas d'historique », et on l'écrit dans le produit. Signalé le 2026-09-08 : « pour Apple je ne comprends pas, je  |
| [`overlapping-readings-summed-as-one`](error-classes.md#overlapping-readings-summed-as-one) | un total gonfle sans raison visible, d'autant plus que l'utilisateur a fourni PLUS de données. Aucune erreur : chaque relevé est juste, c'est leur add |
| [`conflict-target-an-index-cannot-match`](error-classes.md#conflict-target-an-index-cannot-match) | tout upsert sur la table échoue, en bloc, avec un message qui parle d'une contrainte ABSENTE alors qu'elle est là. Signalé le 2026-09-08 sur cinq fich |
| [`the-application-connects-as-a-superuser`](error-classes.md#the-application-connects-as-a-superuser) | aucun. Tout fonctionne — c'est le propre de cette classe : elle ne se manifeste que le jour où autre chose échoue. |
| [`ddl-resurrects-a-migrated-fix`](error-classes.md#ddl-resurrects-a-migrated-fix) | la production est correcte, et toute base NEUVE renaît avec le défaut — CI, poste de développeur, reconstruction après sinistre — jusqu'à ce que quelq |
| [`a-dependency-that-does-not-come-back`](error-classes.md#a-dependency-that-does-not-come-back) | après un redémarrage de l'hôte (WSL, Docker Desktop, la machine), les services qui DÉPENDENT d'un autre remontent et celui dont ils dépendent reste à  |
| [`a-deduction-subtracted-from-the-wrong-base`](error-classes.md#a-deduction-subtracted-from-the-wrong-base) | une surface affiche un montant NET manifestement faux, sans erreur ni trace. Mesuré le 2026-09-14 : la page Royalties SACEM annonçait « ✅ Net estimé * |
| [`a-bind-address-that-hides-the-service`](error-classes.md#a-bind-address-that-hides-the-service) | un service démarre, son conteneur est `healthy`, aucun journal ne se plaint — et **rien ne peut l'atteindre**. Le symptôme arrive à l'autre bout de la |

## l-instrument-ment-sur-ce-qu-il-mesure

**Ce que cet instrument AFFICHE est-il ce qu'il a mesuré ?**

Règle de rattachement : `metric|gauge|jauge|scrape|exporter|prometheus|grafana|observab|instrument|telemetr|measuring-nothing|histogram|cardinalit` sur l'identifiant et le symptôme. 4 classe(s).

| classe | symptôme |
|---|---|
| [`a-proxy-rendered-under-the-name-of-the-thing-it-proxies`](error-classes.md#a-proxy-rendered-under-the-name-of-the-thing-it-proxies) | une figure, une tuile ou un tableau affiche un indicateur INTERMÉDIAIRE sous le nom du résultat final qu'on aimerait mesurer. Rien ne lève : le chiffr |
| [`a-fail-fast-gate-cannot-diagnose`](error-classes.md#a-fail-fast-gate-cannot-diagnose) | l'outil que le runbook fait lancer pour comprendre pourquoi une plateforme ne collecte pas s'arrête AVANT de la tester, et rend un verdict qui ne parl |
| [`one-version-marker-out-of-many`](error-classes.md#one-version-marker-out-of-many) | les écoutes d'un radio edit, d'un live ou d'un instrumental s'ajoutent à celles du titre original, sous la mauvaise date de sortie. Aucune erreur, auc |
| [`a-diagnostic-that-reads-a-name-not-a-route`](error-classes.md#a-diagnostic-that-reads-a-name-not-a-route) | un outil de diagnostic rapporte des pannes que le produit n'a pas. Mesuré le 2026-09-12 par `make artist-firstlook-prod ARTIST=1` : **2 pages sur 6 en |

## Sans famille

Ces classes ne tombent dans aucun motif. **Ce compte est un cliquet : il ne peut que baisser.** Une taxonomie qui laisse un tiers du catalogue dehors décrit une opinion, pas le catalogue — et chaque classe qu'on range est une question qu'on a su formuler.

_Aucune._

## Les chiffres gelés

<!-- error-class-families: total=419 families=18 orphans=0 -->

<!-- error-class-families: sha256=5431bfe46a6da4463aa72c5fa6e8e4b24f4f2fc033b6d947982161193ccd2189 -->
