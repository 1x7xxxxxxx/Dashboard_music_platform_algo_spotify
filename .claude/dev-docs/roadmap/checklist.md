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

| id | Tâche | P | Où |
|---|---|---|---|

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

**R1** reste le seul geste humain, dans la section « 🙋 En attente de toi » plus bas :
inviter la bêta. Aucune ligne de code ne la débloque.

---

## 🔖 REPRISE — état au 2026-09-10, une tâche ouverte (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R1 -->

### Ce que le 2026-09-10 a changé (sept tâches livrées, une reste)

R64, R65, R66, R67, R68, R69 et R71 sont **livrées et rotées dans `archive.md`** —
correctif, garde dédié, mutations rouges avant écriture, suite complète verte à 4 804
tests. Détail dans l'archive ; ne reste ouvert de ce lot que **R70** (couches bronze /
argent / or, P4, ADR à écrire — voir la table ci-dessus).

Ce qui suit décrivait l'état au 2026-09-08.

### Ce que le 2026-09-08 a changé (rien n'ouvre de tâche)

**Deux défauts remontés par le parcours artiste, corrigés et DÉPLOYÉS le jour même**
(`2840423`, api + dashboard sains, `make sync-check` vert : prod == canonique, 972
colonnes / 95 tables, code déployé == `origin/main`).

- **Le bouton qui terminait la mise en route était mort, aux DEUX sorties** — « 🔗
  Confirmer le nom des titres » après un import de CSV, et « 🏠 Aller au dashboard → »
  après la dernière plateforme connectée. Le compte rendu qui les porte était consommé
  (`session_state.pop`) à l'affichage ; au rerun du clic le bloc n'existait plus, le
  widget n'était pas ré-instancié, le geste était jeté. `utils/pending_notice.py`
  remplace la consommation par une borne de page. Classe
  `consumed-state-hides-its-own-widget`.
- **« Aucune suggestion de campagne Meta » était NORMAL, et rien ne le disait.** Le bac
  à sable est exempté du garde d'unicité d'identité — sa raison d'être — donc il
  déclare le compte publicitaire du profil principal ; `meta_campaigns` ayant
  `campaign_id` pour seule clé de conflit, il n'obtiendra jamais une campagne. Mesuré :
  224 insights, 12 titres, **0 campagne**. Cause distincte `SANDBOX_SHARES_ACCOUNT` et
  un texte qui nomme l'exemption. Classe
  `an-exemption-on-one-surface-reads-as-a-failure-on-another`.

- **« Cumulé · par année · cette année » ne montrait AUCUNE plateforme** : un pas annuel
  sur une période d'un an ne produit qu'un seul seau, et une aire d'un point ne dessine
  rien. La contrainte `_MIN_POINTS = 2` existait déjà, appliquée aux séries et jamais à
  l'axe. Un pas qui ne tient pas **descend** au pas plus fin et le dit. Classe
  `a-form-constraint-checked-on-the-series-not-on-the-axis`.
- **La déduplication `SUM(streams)` par `(date, song)` n'a PAS lieu d'être** — mesuré,
  pas supposé : `UNIQUE(artist_id, song, date)` existe en local et en prod, 0 doublon,
  `SUM` brut = `SUM` dédoublonné = 163 088. Les 6 `DISTINCT ON (date, song)` sont
  redondants. Les 5 sommes sans `artist_id` sont les branches flotte de l'admin, hors
  d'atteinte d'un locataire (`view_session` / `tenant_scope`). Vérifier a évité un
  refactor de dix sites sur une prémisse fausse.
- **Le « gros trou dans les données de S4A » n'existait pas** : S4A a 365 / 366 / 365 /
  248 jours consécutifs depuis le 2023-01-01. Le trou était dans la FIGURE — les
  tranches de la bande étaient communes, donc un jour sans collecte YouTube coupait
  aussi Spotify : **19 semaines** effacées, dont **13** dont YouTube était seul
  responsable. Les tranches sont désormais **par plateforme** ; Spotify est tracé
  181/181 en une seule tranche. Classe `a-gap-in-one-series-erases-every-other`.
- **Une semaine mesurée un jour sur sept était tracée comme une semaine pleine** —
  38 % des semaines YouTube, 31 % SoundCloud. Sous la moitié des jours qu'il contient,
  un seau devient **inconnu** ; le plancher est calibré sur les distributions réelles,
  épinglées dans le test. Classe `a-partial-bucket-drawn-as-a-full-one`.
- **Le sous-titre annonçait 16 568 594 écoutes pour 163 102** — facteur 89 — parce
  qu'il sommait la série APRÈS transformation, donc des cumuls. Aucun test ne le
  voyait ; c'est d'avoir **rendu la figure et regardé l'image** qui l'a trouvé. Classe
  `a-total-that-sums-the-display-instead-of-the-data`.
- **« Je ne vois que Spotify » a enfin sa réponse** : le mode « part » n'en était pas
  une (0,26 % occupe 0,26 % de la hauteur). Quatrième mode, **« Chacune à son
  échelle »** — des petits multiples, une facette par plateforme. La règle de couverture
  qui excluait YouTube (24 j sur 195) et SoundCloud (12 sur 74) de toutes les vues a
  disparu : elle compensait le défaut des tranches communes, retiré ci-dessus.
- **Rien d'écrasé n'est perdu** (ADR-018, migration **096**) : un déclencheur générique
  journalise dans `data_revisions` toute mise à jour qui CHANGE une valeur surveillée.
  Motif : Spotify retire rétroactivement des écoutes (leur page *Artificial Streaming*),
  et nos upserts écrasaient sans trace. Côté base, parce qu'un déclencheur ne s'oublie
  pas.
- **Un pilier de contrôle manquait — les VALEURS.** Le 2026-06-01, SoundCloud a écrit
  **19 compteurs cumulés sur 19 à zéro** ; fraîcheur, pics et collecte partielle avaient
  tous raison de ne rien voir. `check_zero_resets` le signale (jamais ne le réécrit). Le
  patron du livre a été mesuré puis **écarté** : 93 alertes sur 1 254 jours contre 1
  pour le prédicat retenu. Classe `a-failed-collection-writes-zeros`.
- **Un seul calcul de total** pour l'accueil, le PDF (qui ignorait sa propre période),
  la page Apple et l'API — quatre versions qui ne s'accordaient pas. `welcome_figures`
  perd son SQL en double, celui qui additionnait un cumul et un quotidien.

- **La matrice Meta du bac à sable criait une panne inexistante** (🟡 « la collecte
  s'est arrêtée, on regarde ») sur le compte où le profil principal lisait 🟢 « rien à
  faire », le même jour. `_silence_reason` comptait les campagnes du LOCATAIRE ; il lit
  maintenant celles du compte **déclaré**. Troisième surface de la même exemption.

- **Quatre modes d'affichage sur la courbe** : Cumulé (défaut, l'allure de
  l'illustration), Par période, Part de chaque plateforme, et **Chacune à son échelle**
  — ce dernier est le seul qui rende visibles YouTube (0,22 %) et SoundCloud (0,04 %)
  à côté de Spotify (99,74 %).
- **Migration 095** : la clé d'unicité Apple était sur des EXPRESSIONS, donc
  inappariable par un `ON CONFLICT (col, …)` — cinq imports échouaient. `NULLS NOT
  DISTINCT` (PostgreSQL 15+) rend la cible appariable sans perdre la déduplication.
- **Apple figure sur la courbe, au pas ANNUEL uniquement** — ses exports sont des
  totaux de période ; les étaler sur des jours inventerait une valeur. Sélecteur de pas
  (Automatique / semaine / année) sur l'accueil, et le guide demande un export par
  période.
- **La période d'un export Apple se lit dans le NOM du fichier**
  (`songs_…_2015-06-30_2026-09-04.csv`) : rien à saisir, la question n'est qu'un repli
  pour un fichier renommé. Les périodes imbriquées ne sont jamais sommées à l'aveugle
  (`non_overlapping_cover`).
- **Apple gagne une précision par ANNÉE** (migration 094) : l'export n'ayant aucune
  colonne de date, la période est **demandée** au dépôt. Périodes bornées → sommées ;
  cumuls → soustraits ; total → le dernier cumul, sinon la somme des années. Le guide
  invite désormais à déposer un export par année.
- **YouTube lisait le compteur de CHAÎNE**, mis à jour par paliers : +360 attribués à
  une seule journée contre 64 vues chez YouTube Studio. Il lit désormais les compteurs
  **par vidéo** (44 sur 28 j — le bon ordre de grandeur), écart pris par vidéo.
- **Apple ne pouvait pas avoir d'historique** : `UNIQUE(artist_id, song_name)` sans
  date faisait écraser chaque dépôt de CSV par le suivant. Migration **093** —
  `snapshot_date` entre dans la clé, et la tuile compare deux relevés.
- **Le bouton « Lancer TOUTES les collectes » a été RETIRÉ de la barre latérale** : les
  cinq collectes ont leur cron quotidien (Meta 5 h · Spotify 7 h · YouTube 8 h ·
  SoundCloud 9 h · Instagram 10 h) et une collecte repart dès qu'un identifiant est
  enregistré. Les 5 textes qui l'envoyaient « dans la barre latérale » ont été réécrits.
- **L'accueil est en deux colonnes** — courbe à gauche, chiffres à droite, filtre au
  centre en haut — avec une période « 📅 Sur mesure », un écart d'abonnés Instagram sur
  la période, et « — » plutôt que « 0 » pour une plateforme non mesurée.
- **L'accueil porte un sélecteur de période** (« Depuis le début » par défaut, Cette
  année / 12 mois / 90 / 30 jours) qui vaut pour les tuiles ET la courbe, un seul
  propriétaire du réglage. La bande s'agrège **par semaine** au-delà de 92 jours : nos
  sources n'ont pas la même cadence (Spotify 100 %, SoundCloud 56 %, YouTube 39 % de
  jours mesurés), et au pas quotidien deux périodes perdaient une plateforme entière.
- **Le bandeau de mise en route se replie quand la configuration est terminée**, et la
  figure de l'accueil redevient celle de l'illustration : des **aires empilées** aux
  couleurs du générateur d'exemples, une par plateforme. Une source trop clairsemée
  (2 jours sur 90) est nommée sous la figure au lieu d'empêcher toute la pile — la
  régression trouvée en **vérifiant** le déploiement, pas en attendant un signalement.
- **Cinq points du parcours artiste, quatre défauts et une mesure** (suite 2) : la
  colonne « Format » lisait une seule des deux copies de l'identité Spotify ; l'étape 2
  de l'assistant n'était atteignable par **aucun** chemin sur un compte configuré ; la
  courbe « tes chiffres » additionnait un cumul et un quotidien (23 560 → 1 748 par
  jour) ; l'accueil porte désormais l'**évolution par plateforme** sous les totaux. Le
  cinquième — « le bac à sable n'a pas la même app » — est **faux, mesuré** : les deux
  rendus diffèrent d'une ligne, celle du plan.

**Le mapping des campagnes n'est pas rejouable dans le bac à sable, par construction** —
c'est le seul geste du parcours qui demande le profil principal. Mesuré : le bac à sable
a les insights Meta (224 lignes, 21 campagnes, ventilations à 87–99 % du principal) mais
aucune ligne de configuration (`meta_campaigns` 0/34, `meta_adsets` 0/69, `meta_ads`
0/144, `campaign_track_mapping` 0/19). Les onglets qui lisent les insights tracent ; ceux
qui joignent la configuration restent vides.

Ce qui suit décrivait l'état au 2026-09-07.


### Ce que le 2026-09-06 et le 2026-09-07 ont changé (rien n'ouvre de tâche)

**Ce qui reste ouvert est inchangé : R1, et rien d'autre.** Ces deux journées n'ont
inscrit aucune tâche — elles ont fermé une série de CI rouge et corrigé des défauts
trouvés en s'appuyant sur les données, pas en les auditant.

- **La CI est verte** (run `34034904194`). La série de **27 exécutions rouges** est
  close : `Run tests` n'avait plus tourné depuis le 2026-09-04, et il a rendu 5 échecs
  réels dès qu'on l'a débloqué — aucun n'était visible en local. Réparer l'étape
  bloquante n'était pas la fin de la séance, c'était ce qui rendait le reste
  observable.
- **Le rapprochement des titres était faux au-dessus du seuil d'auto-acceptation**
  (2026-09-07) : « remix » était le seul marqueur de version reconnu, donc un radio
  edit, un live ou un instrumental valait 0,90 contre son titre de base et ses écoutes
  s'ajoutaient à l'original. Corrigé et **mesuré sur les 21 rapprochements réels de
  production, figés en filet AVANT de toucher à l'algorithme** : 21/21 conservés, zéro
  régression.
- **17 % du catalogue était invisible** : `imusician_sales_detail` porte `isrc`,
  `track_title` et `track_version` que rien ne lisait, et l'export S4A « 12 mois » ne
  montre que ce qui a été écouté. Deux vraies sorties passaient pour des intrus.
- **2 533 lignes portaient la chaîne littérale `nan`** — un NaN pandas est vrai en
  booléen. Sur une clé comme l'ISRC, ça regroupe sous une même valeur tout ce qui n'a
  pas d'identifiant. Corrigé + **migration 092**.
- **Un garde textuel a été refusé par le cliquet et réécrit sur l'AST** : il a trouvé
  du premier coup un site frère (`csv_dialect.py:50`) que la recherche de chaîne
  ratait. Registre : **230 classes, propre.**

Ce qui suit décrivait l'état au 2026-09-05.


**▶️ Aucune tâche de développement ouverte.** Les quatre inscrites dans la journée
(R59-R62) ont été closes le soir même — DEVLOG « suite 14 ». Ce qui reste est **R1**,
inviter la bêta : un geste humain qu'aucune ligne de code ne débloque.

Deux d'entre elles ont été closes **sans correctif, et c'est le point** : R59 parce que
sa prémisse était fausse (ADR-016), R62 parce que la mesure a montré une porte fermée
côté Meta (ADR-017). Vérifier avant de coder a évité deux chantiers.

Ce qui suit décrivait l'état au 2026-09-04.

**▶️ Aucune tâche de développement ouverte.** R58 — la dernière — a été livrée le
2026-09-04 et rotée dans `archive.md` : les figures de l'écran de bienvenue viennent
des données du locataire dès qu'il en a sept jours. Elle disait attendre R1 ; vérifié
avant de la parquer une seconde fois, deux tiers l'attendaient (le mot de bienvenue
part AVANT toute collecte, et `kaleido` manque pour l'export PNG), un tiers non.

**Ne reste que R1**, dans « 🙋 En attente de toi » plus bas : inviter la bêta. Aucune
ligne de code ne la débloque.

**Le reste : zéro `- [ ]` dans ce fichier.** Les 19 derniers ont été **rotés dans
`archive.md` le 2026-09-03 au soir**, marqués `[CLOS — décision, non livré]` : aucun
n'était un travail qu'on pouvait commencer. Huit étaient des décisions de performance
conditionnées par ADR-007 — dont les quatre déclencheurs ont été lus contre la
production et ne sont pas tirés — et trois d'entre elles étaient **dupliquées** entre
deux blocs. Cinq étaient bloquées par l'accumulation de temps (des paires étiquetées
qu'aucune saisie ne fabrique d'avance). Les deux derniers, E1 et E2, étaient la
redite de **R1**, le geste humain porté par la table « En attente de toi » ci-dessous.

Ce qui rouvre chacun est écrit dans son bloc, dans l'archive. Ne reste donc qu'**un**
geste, et lui seul : **R1** — inviter la bêta.

### Ce que le 2026-09-04 (soir) a changé sous cette ligne

Deux lots de parcours artiste, traités et déployés le même jour — DEVLOG « suite 10 »
et « suite 11 ». Vingt remarques, une seule famille : **l'app parlait d'elle-même**.
Les gestes qui la fermaient sont, dans l'ordre de ce qu'ils ont coûté à un artiste :

- un **verdict de connexion calculé et jamais montré** (le `st.rerun()` effaçait le
  message juste avant qu'il s'affiche) ;
- **Apple Music cochable et ne menant nulle part** — aucun onglet, aucun repli, aucun
  message, et éternellement « Suivante » ;
- un **sélecteur d'OS** en tête de chaque onglet alors qu'aucun guide ne dépend plus
  du clavier ;
- une **alerte DAG** qui envoyait remplir `SPOTIFY_ARTIST_IDS`, variable qui doit
  rester vide sous peine de réarmer la fuite de locataire du 2026-08-20 ;
- un **bac à sable qui masquait un conflit d'identité entre deux vrais locataires**
  (classe `exempt-row-hides-others-conflict`, P2).

### Ce que le 2026-09-04 avait déjà changé

Rien n'a été rouvert ; trois choses ont été **retirées ou rendues prouvables**.

- **ADR-014** tranche la stack data moderne (dbt, ClickHouse, DuckDB, dlt, Dagster,
  Parquet/R2, Supabase, ECharts) : tout différé, chaque refus avec un déclencheur
  **calculable**. Le chiffre qui tranche : 43 Mo de base, agrégat à 18,5 ms.
- **Le seul trou de robustesse réel a été comblé** — les 21 sauvegardes vivaient sur le
  disque de la base, et le drill de restauration n'avait aucun appelant depuis juin.
  **Refermé pour de bon le 2026-09-04** : R57 attendait un bucket, donc une carte
  bancaire ; elle est partie sur un dépôt privé chiffré (ADR-015), 22 archives
  distantes, et la restauration a été prouvée **sans le serveur** — archive tirée de
  GitHub, déchiffrée localement, 93 tables. Le geste humain a disparu avec la tâche.
- **Airflow a maigri** : parsing 30 → 300 s, métadonnées 246 → 91 Mo, et les 4
  `*_csv_watcher` **supprimés** — 98,4 % des lignes de métadonnées pour sonder des
  répertoires vides. La page d'import garde désormais le fichier 14 jours, ce qui
  était la seule moitié utile d'un watcher.

**R1 a commencé le 2026-08-30** : premier parcours d'onboarding fait en entier, ~20
remarques de terrain, toutes traitées et déployées (PR #115, migration 079). Aucune ne
portait sur la lenteur — la classe dominante était du texte adressé au mauvais lecteur.
R1 reste ouverte parce que le test n'est pas fini : l'artiste reprend là où il s'était
arrêté.

### Audit du 2026-09-03 — trois jours de tourne sans intervention

La prod tourne depuis 64 jours (`postgres` 2 mois, `dashboard`/`api` 3 jours). **Rien
n'a cassé pendant l'absence** et, pour la première fois, ce n'est pas une déduction :
les surfaces de preuve construites en août ont toutes répondu.

| Ce qui a été lu | Verdict |
|---|---|
| 16 DAGs, 4 jours de runs | **0 tâche Airflow en échec** ; les 4 DAGs sans run récent sont hebdomadaires (`0 * * 1`), pas muets |
| `etl_run_log`, par locataire × plateforme | 1 seule défaillance : `meta_ads_api_daily` / Benken (12), 5 nuits d'affilée, `act_65390907` — **le blocage connu de partage de compte, pas une régression** |
| `check_tenant_contamination` | **0 constat** — aucune ligne sous un locataire qui ne peut pas la porter |
| `check_canary_health` (locataire 14) | 0 problème, et il redit lui-même qu'il ne couvre ni Meta ni Instagram (ADR-010) |
| `check_row_dips` | 0 collecte partielle |
| Sources périmées | 2 : **S4A (88 j) et Apple Music (79 j)** — les deux alimentées par CSV, que personne ne dépose. Attendu, pas un incident (R46) |
| Meta Ads « silencieux » | qualifié `expected_silence` : 34 campagnes connues, aucune active — la vue distingue enfin « pas de données » de « pas de campagne » |
| `app.` / `api.` / apex `streamlytics.fr` | 200, ~0,2 s ; `/health` → `{"status":"ok"}` |
| Sauvegardes | quotidiennes à 03:00, 4 dernières présentes et **croissantes** (1,52 → 1,79 Mo) |
| Disque / RAM | 42 % de 150 Go ; 4,5 Go dispo sur 7,7 |

**Le point le plus utile de l'audit** : le mail nocturne n'est pas parti, et c'est
**décidé**. Le log dit `✉️ not re-sent (constats inchangés depuis le dernier envoi
(2j), renvoi dans 4j ou dès qu'un constat change)`. Un silence obtenu par dédup nommée,
pas un silence par accident — exactement ce que le commit `5d22bd2` visait.

**Ce qui attend une décision, pas un correctif** : `STREAMLYTICS_ALLOW_ARTIST_EMAIL`
n'est posée dans aucun conteneur de prod. Le garde d'audience de PR #121 est donc actif,
et **aucun e-mail ne partira jamais vers un locataire** tant qu'elle n'est pas posée.
C'est l'état voulu aujourd'hui ; c'est aussi la variable à poser le jour où R1 passe à
l'invitation réelle. `verification_email` n'est pas concernée — l'inscription vaut
consentement, et elle part depuis `streamlytics_dashboard`, qui porte bien
`STREAMLYTICS_ENV=production` et ses trois variables SMTP.

> `streamlytics_api` n'a pas `STREAMLYTICS_ENV`. Sans effet aujourd'hui : `src/api/`
> n'importe ni `email_alerts` ni `instance_identity`, donc aucun chemin d'envoi n'y
> passe. À reposer si l'API se met un jour à écrire à quelqu'un.

> La ligne `<!-- reprise: open=… -->` ci-dessus n'est pas décorative : c'est la même
> affirmation que le paragraphe, sous une forme que `tests/test_the_resume_header_is_checked.py`
> peut comparer aux deux tableaux d'index. Une prose ne se vérifie pas ; une prose
> **ancrée** se vérifie.

> ⚠️ Ce bloc nommait encore R13, R17 et R55 le 2026-08-28 alors que les trois étaient
> closes. Le corps du fichier le disait déjà ; c'est l'en-tête qui n'avait pas suivi.
> Une roadmap se périme comme un commentaire, et son en-tête plus vite que son corps :
> c'est la seule partie que `/resume` recopie sans la relire. Les comptes rendus des
> séances du 26 au 30 août ont été **rotés dans `archive.md` le 2026-09-03** — le
> fichier actif était à 42 Ko dont ~80 % d'historique.

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

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
| R1 | E1 — beta privée avec des proches sur `streamlytics.fr` | P3 | **un seul geste : inviter.** Tout le reste est fait au 2026-08-22, déployé et vérifié (`prod == canonique`, 75 migrations, Caddy inclus — l'empreinte de schéma courante est en tête de fichier, un seul chiffre fait foi). Le filet a trois épaisseurs désormais : **(a)** le canari prouve Spotify/YouTube/SoundCloud chaque nuit ; **(b)** Meta et Instagram — qu'aucun canari ne peut couvrir (ADR-010) — sont sondés **chaque nuit sur le compte réel de chaque locataire**, et le message de l'alerte est celui de l'API, plus une devinette ; **(c)** l'artiste voit lui-même sa **matrice Configuré / Répond / Données** sur la page Credentials, l'onboarding et l'accueil, avec un bouton « Vérifier maintenant ». Après chaque inscription, garder le réflexe `make artist-preflight ARTIST=<son id>` — c'est le contrôle avant-données que la sonde nocturne ne peut pas faire. Runbook §5. |

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
