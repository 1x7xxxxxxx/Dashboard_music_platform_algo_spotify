# Backlog produit — ce qui attend un déclencheur hors de l'ingénierie

Type: Doc (déplacé depuis la roadmap le 2026-09-26, décision du propriétaire)
Uses: `.claude/dev-docs/runbook-actions-utilisateur.md` (la procédure de chaque geste)
Persists in: ce fichier

La roadmap (`roadmap/checklist.md`) ne porte que du travail qu'une séance peut faire. Ce qui
suit attend un **déclencheur produit** ou une **personne** — des artistes à interroger, un
lancement — et n'y avait qu'un effet : empêcher la roadmap d'être vide sans rien faire
avancer. Rien n'est perdu : chaque ligne garde son déclencheur et sa procédure. **Quand le
déclencheur arrive, la tâche repart dans la roadmap** (`🙋 En attente de toi` si elle
attend un geste, l'index sinon).

| id | tâche | déclencheur | procédure |
|----|-------|-------------|-----------|
| R148 | Trois conversations « combien tu paierais » | trois entretiens de vingt minutes, avec des artistes **qui ont vu leurs données** — runbook §19 | runbook §19 |
| R163 | Brancher Hypeddit sur le pixel et sa Conversions API, au lancement | **déclencheur : l'app terminée ET une campagne Meta relancée.** Choisir le pixel dans Hypeddit, y coller un jeton CAPI, rattacher le pixel à chaque smart link, vérifier l'évènement en test, puis 48 h après voir `custom_conversions` remonter — runbook §24 | runbook §24 |
| R276 | Assistant in-app (FAQ + RAG) pour lire un graphique, décider, configurer ses identifiants — architecture RAG en couches (sécurité entrée/sortie, cache, citations, évaluation) — notes L174-L220, L452 | **déclencheur : tous les KPI validés et au moins cinq artistes actifs** — sinon il n'aurait rien de stable à expliquer | à écrire au déclenchement |
| R277 | PDF de prospection de 2 pages (graphiques à plus forte valeur, questions marketing et streams) — notes L167 | **déclencheur : tous les KPI validés** (décision du 2026-09-27 : le rapport PDF artiste attend la validation) | à écrire au déclenchement |
| R278 | Formats : migrer les 26 séparateurs faits main, les 77 formats `{:,}` et les 45 tableaux sans format vers `formats.num/eur/pct/table` — suite de R260 | **déclencheur : toute modification d'une vue qui en porte** ; le cliquet de `tests/test_a_number_is_written_one_way.py` interdit d'en ajouter et se baisse dans le même commit | la vue touchée |
| R280 | Lectures brutes → or : descendre le plafond de 66 (18 figures, 44 tuiles) vue par vue, en vérifiant la sémantique de chacune (`v_meta_daily` n'a pas de `cpr` ; Apple à vérifier) — suite de R258, verdict critic (c) | **déclencheur : toute modification d'une vue qui lit le brut** ; le cliquet de `tests/test_the_bronze_boundary_only_tightens.py` interdit d'en ajouter |
| R281 | Alertmanager : le déclencheur d'ADR-026 (~10 règles) est franchi le 2026-09-28 (11 règles, R265) ; non adopté tant qu'aucune alerte ne doit joindre quelqu'un avant le mail de 23 h | **déclencheur : une alerte qui ne peut pas attendre le soir** (astreinte, client payant touché en journée) |
| R284 | Scalabilité différée d'ADR-030 : fan-out par locataire (`.expand()`) et budget de quota par locataire, cible de charge au seuil d'ADR-007, limites CPU par conteneur — suite de R266 | **déclencheur : un DAG de prod passe, au p95 sur 30 jours, la moitié de son `dagrun_timeout`** (6 % le 2026-09-28), ou `loadtest_dashboard.py -n 12` rend un p50 > 200 ms — les deux lus chaque nuit par `tools/dev/reopen_check.py` | ADR-030 |
| R302 | Note L268 : sur la courbe Meta × Spotify, le seuil de déclenchement de l'algorithme avec sa probabilité et la prédiction en pointillés — différée sur ma reco à la clôture de R282 (2026-09-28) : le modèle ne change presque pas d'avis d'une semaine à l'autre (fiche 126), un pointillé serait lu comme une promesse | **déclencheur : plusieurs relevés S4A par algorithme** (4 semaines distinctes) disent si le modèle se rapproche du réel — la fiche 126 le montre | à écrire au déclenchement |
| R303 | Note L276 : s'inspirer de graphiques générés ailleurs — R282 a proposé et tranché les siens, aucun graphique extérieur n'a encore été fourni | **déclencheur : tu colles dans le fil (ou dans `revue/`) les graphiques qui t'inspirent, avec la page où tu les verrais** | runbook § 38 (barré, la consigne y reste) |
| R309 | Contrôle de contamination nocturne en une requête groupée par table (au lieu de 2 par locataire × plateforme × table) — différé le 2026-09-28 : mesuré 0,3 à 0,5 s pour 13 locataires (~500 requêtes sur colonne indexée), rien à gagner (ADR-007, ADR-030) | **déclencheur : 100 locataires dans `saas_artists`** — lu chaque nuit par `tools/dev/reopen_check.py` (13 le 2026-09-28) | à écrire au déclenchement |

---

## 📚 R148, R150, R151 — ce que les dix livres du 2026-09-22 ont changé

Dix livres ingérés (11 939 passages) en trois domaines : `business-offre` (6),
`marketing-ads` (3), `marketing-musical` (1). Ce bloc portait à l'origine six points où
un livre **contredit ou complète une mesure existante**, un par tâche R146 à R152 (sept
tâches, une synthèse — R152 partageait son livre avec R147). Quatre ont été closes le
2026-09-22 et **déplacées dans `archive.md`** (« 📚 R146, R147, R149, R152 — les quatre
tâches ... closes le jour même ») : R146 (P2, livrée), R147 (livrée), R149 (livrée),
R152 (tranchée par ADR-028). Les trois points restants, ci-dessous, sont ceux qui
attendent encore un geste humain.

### R148 — Le prix a été posé, jamais mesuré

*Monetizing Innovation* (Ramanujam & Tacke) : parler du prix **avant** de construire,
et le terme central est *willingness to pay*.

> « To build a product around a price, you must engage in deep discussions with
> potential customers before you design and develop it. »

Ici l'ordre a été l'inverse : le produit d'abord, 10 €/mois ensuite. Et aucun des
artistes bêta n'a jamais été interrogé sur ce qu'il paierait. Le livre ne dit pas que
10 € est faux — il dit qu'on n'en sait rien, et c'est vérifiable : zéro trace d'un
entretien WTP dans le dépôt.

### R150 — La prestation ne chiffre rien

*Pricing Creativity* et *The Win Without Pitching* (Blair Enns) : proposer des **options**
plutôt qu'un prix, et établir la disposition à payer avant de chiffrer.

Le panneau de service livré le 2026-09-21 nomme quatre arguments et propose un appel.
Il ne porte aucune structure de prix, donc l'appel commence à zéro à chaque fois. Trois
options ancrent la conversation sans engager sur un tarif public.

### R151 — La limite iOS 14 sur les évènements agrégés

*La petite boîte à outils Facebook Ads et Instagram Ads* (Pellerin) :

> « Depuis iOs 14, il est nécessaire de définir une **hiérarchie** entre les différentes
> conversions personnalisées créées, afin que Facebook identifie celle(s) à mesurer en
> priorité. »

Meta ne mesure que huit évènements par domaine, dans un ordre choisi. Si la conversion
Hypeddit n'est pas prioritaire dans l'Events Manager, une partie des conversions n'est
tout simplement pas attribuée — et cela se lit comme des campagnes moins performantes
qu'elles ne le sont. C'est un geste humain de cinq minutes, avec une conséquence
mesurable sur tous les chiffres de coût par résultat de l'app.

### Les deux repères chiffrés à se donner

*Lean Analytics* publie des bornes de référence SaaS, et streaMLytics tombe dans un
cas précis : **essai sans carte bancaire**.

| | avec carte à l'inscription | **sans carte (ton cas)** |
|---|---|---|
| visiteurs qui démarrent l'essai | 0,5–2 % | **5–10 %** |
| essais qui deviennent payants | 50 % | **15 %** |
| bout en bout | 0,6 % | **1,2 %** |

Et sur la rétention : « The best SaaS sites usually have churn ranging from **1,5 % to
3 % a month** », et il faut passer **sous 5 %/mois** avant de pouvoir parler de
croissance.

Ces quatre nombres donnent enfin une barre à R147 et R149 : sans eux, « 15 % de
conversion » est une impression ; avec eux, c'est une cible ou un écart.

⚠️ Ce sont des repères de 2013 sur des SaaS B2B. Ils cadrent l'ordre de grandeur, ils
ne remplacent pas la mesure de TES cohortes — qui est précisément ce que R147 demande.

### Une confirmation, et elle compte autant

*Pricing Creativity* (Enns) : « adding a third, higher price increases the sales of the
middle price — previously the highest price — by almost **50 %** ».

Deux plans (Free / Premium) n'ont pas de milieu. Le Premium à 10 € est le haut de
gamme, donc le point de résistance. Un troisième niveau au-dessus — même peu vendu —
déplacerait le Premium vers le centre. C'est le même mécanisme que R150 demande pour
la prestation : **trois options, pas un prix**. Les deux se décident ensemble.

### Ce que les livres n'ont PAS apporté

⚠️ Deux des dix sont des **dérivés, pas les originaux** : « 100M Offers Made Easy … by
Turning ChatGPT into Alex Hormozi » (Ben Preston) commente Hormozi, et « Breakthrough
Copywriter 2.0 » (Worstell) commente Schwartz. Quand le RAG citera un passage de l'un
des deux, c'est une paraphrase qu'on lira, pas la source — à garder en tête avant de
fonder une décision dessus.

Et rien dans ces dix livres ne traite de **TVA, de frais de fonctionnement déductibles
ni d'obligations de facturation**. C'est délibéré : ce sujet change chaque année et
dépend de la forme juridique. Les sources qui font foi sont le BOFiP, impots.gouv.fr et
l'URSSAF — elles se rangent dans `admin-fiscalite`, préfixé `admin-` pour rester hors
des recherches par défaut.
