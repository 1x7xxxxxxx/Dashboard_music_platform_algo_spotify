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
| R132 | **Isolement de flotte hors Airflow** — 6 sites mesurés que le garde AST ne peut pas voir : `metric_bounds.py:124` (aveuglement de flotte), `onboarding_health.py:65` (toute la page admin tombe), 4 scripts de `debug_dag/` | P3 | `python3 -m pytest tests/test_dag_fleet_isolation.py -q` reste vert — c'est le POINT : ces sites sont hors de son périmètre, la mesure est le balayage AST ci-dessous |
| R133 | **28 figures sous le plancher d'accessibilité de la palette** — mesuré le 2026-09-17 par figure (CIEDE2000 + Viénot/Brettel), paire dominante vert `#1DB954` ↔ un rouge, c'est-à-dire « bon/mauvais » encodé en teinte seule. `code-critic` : **BUILD-MODIFIED** — construire `semantic_colors.py` + extraire la colorimétrie de `tests/` vers `src/`, garde report-only, gate dur sur le seul diff ; **ne pas migrer les 28 sites d'un coup**. ⚠️ 28 est un PLAFOND : le plancher de 15 n'est légitime que si même type de trace, même sous-graphique sans axe secondaire, et aucune étiquette de texte persistante — `meta_funnel`, `revenue_forecast.py:82` et `ig_engagement` y tombent sans être des défauts d'attribution | P3 | le script de mesure est dans le champ `siblings` de `a-visual-constant-copied-into-a-second-renderer` (`.claude/dev-docs/error-classes.md`) ; il doit rendre moins de 28 |
| R134 | **Le détecteur de creux ne voit que 5 tables sur 84** — `DIP_TENANT_COLUMN` (`alert_monitor.py:744`) couvre YouTube, SoundCloud, Meta, ML et S4A ; un locataire qui perd ENTIÈREMENT Instagram, Apple, Hypeddit ou SACEM ne déclenche aucune alerte. Les tables éligibles sont nommées dans le champ `siblings` de `partial-collection-invisible`. ⚠️ Étendre la liste demande un seuil calibré PAR TABLE sur des données réelles — le plancher de 30 lignes/jour écrit d'instinct avait déjà rendu le détecteur aveugle à 2 locataires sur 3 | P3 | `python3 -c "import ast,pathlib;…"` sur `DIP_TENANT_COLUMN` doit rendre plus de 5 entrées, et chaque entrée neuve doit porter sa dérivation de seuil |
| R135 | **`soundcloud_tracks_daily.track_id` : `bigint` en PRODUCTION, `character varying` en local** — mesuré le 2026-09-18 colonne par colonne (1187 contre 1196). Le canonique est le VARCHAR : le collecteur écrit `str(track.get('id'))` (`soundcloud_api_collector.py:222`) et aucune migration ne déclare ce type. ⚠️ **Conséquence aujourd'hui : aucune** — les quatre lecteurs ne comparent jamais cette colonne à une chaîne, et Postgres transtype les identifiants numériques des deux côtés. Elle apparaîtra à la première jointure ou comparaison sur `track_id` : la prod rendra un `int` là où le local rend une `str`, donc **un test vert ici échouera là-bas**. La vue or `v_soundcloud_track_latest` hérite du type de chaque côté. Demande un `ALTER` sur une table vivante — décision du propriétaire, pas un effet de bord de séance | P3 | la comparaison des deux schémas ne doit plus nommer `soundcloud_tracks_daily.track_id` |
| R137 | **51 % des classes vivantes n'ont jamais eu de vrai balayage de frères** — 101 sur 197. Leur `siblings:` dit « j'ai relancé le garde, il est vert », ce qui prouve que le prédicat de CE garde ne trouve rien, jamais qu'il n'y a rien. Mesuré trois fois la nuit du 17 au 18, dont **un garde vert sur 8 sites vivants**. Une unité = une FAMILLE (règle 21) | P3 | `make error-health` → `swept_by_rerunning_the_guard` **97 → 0** et `sites_unknown` **100 → 3**, plafonds descendus dans le même commit |
| R138 | **Rien ne refuse un faux balayage AU MOMENT DE L'ÉCRIRE** — le compteur voit les 97 après coup, aucune porte ne les bloque. Et `make config-check` **n'est appelé par aucun workflow** (`grep -rn "config-check" .github/` ne rend rien) : sur ses cinq contrôles, `--prose` est câblé directement en CI mais `check_config_refs.py`, `audit_unreachable_tools.py` et `--coverage` ne tournent qu'à la main | P3 | `python3 .claude/scripts/audit_runner.py --sweep-verdict` sort 0, et ≠ 0 sur une classe mutée en relance ; `grep -n "config-check\|sweep-verdict" .github/workflows/ci.yml` rend des lignes |
| R139 | **Deux instruments qui mentent sur ce qu'ils mesurent** — (a) `swept_by_rerunning_the_guard` (97) est un sous-ensemble STRICT de `sites_unknown` (100), et les deux sont publiés comme deux problèmes dans deux paragraphes consécutifs : un lecteur additionne et lit 197 ; (b) `.test_durations`, qui équilibre les 4 shards de CI, porte **174 entrées non collectables pour 33,9 s** et ignore **475 tests collectés sans durée** — mesuré contre une collecte réelle, le prédicat « le fichier existe-t-il » en trouvant **0** | P4 | `make error-health` → les deux populations ne s'additionnent plus ; et aucun node-id de `.test_durations` ne désigne un fichier absent |
| R141 | **Un commentaire qui nomme un test disparu** — balayage du flux de JETONS (donc les commentaires EN TANT QUE commentaires) sur `tests/ tools/ src/ airflow/ .claude/scripts/` : **196 citations de noms de tests, 20 orphelines**. ⚠️ Deux corrections de prédicat déjà faites, toutes deux en sur-comptant : les noms **coupés par le retour à la ligne** d'un commentaire (27 → 20), et les notes de **RETRAIT** légitimes — `test_a_step_is_offered_only_where_it_draws.py:152` dit « A ÉTÉ RETIRÉ LE 2026-09-13 », nommer le test retiré est son travail. **20 est donc un PLAFOND, pas un défaut** : le tri site par site est la tâche, et le garde ne s'écrit qu'après | P4 | le balayage par jetons doit rendre moins de 20 orphelines, et chaque site restant porte sa raison |

**Huit tâches sont ouvertes dans cet index** — R132, R133, R134, R135, R137, R138, R139,
R141 —
et l'ancre `reprise:` les nomme toutes, dans cet ordre. La table « 🙋 En attente de toi »
plus bas porte **deux** lignes : R125, qui attend un geste humain dans l'app, et R140,
entrée le 2026-09-18, qui attend quatre décisions de PRODUIT. Inviter la bêta est l'usage
du produit, pas du travail d'ingénierie — une roadmap qui suit les gestes commerciaux de
son propriétaire ne peut par construction jamais atteindre zéro.

⚠️ **Ce paragraphe a menti trois fois, et la troisième était aujourd'hui.** Le 2026-09-12
il annonçait « quatre tâches rouvertes » alors que les quatre étaient closes et l'index
vide. Le 2026-09-18 il comptait « quatre » là où l'index en portait cinq, affirmait que
l'ancre « les nomme toutes les trois » — **trois nombres pour une seule grandeur, dans une
phrase** — et disait la table « En attente de toi » VIDE alors que R125 y était depuis le
matin. Aucun garde ne peut le voir : l'ancre et les deux tables étaient justes, c'est la
PROSE à côté qui affirmait le contraire. Classe `a-prose-claim-that-cannot-be-verified`, et
la parade reste la même — quand une phrase de ce fichier compte des tâches, elle compte ce
que l'index compte, et rien d'autre.

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

**Aucun geste HUMAIN n'est en attente** : « 🙋 En attente de toi » est vide depuis
le 2026-09-10, R1 y ayant été rotée vers `archive.md`. Les quatre tâches de l'index
ci-dessus sont du travail d'ingénierie, et elles sont ouvertes.

⚠️ Ces deux paragraphes ont affirmé « plus aucune tâche ouverte » le 2026-09-17
alors que l'index en portait deux, puis trois — la classe
`a-prose-claim-that-cannot-be-verified` que ce fichier nomme quelques lignes plus
haut, commise dans le fichier qui la documente.

---

> ⚠️ **Cet ordre est PÉRIMÉ depuis le 2026-09-18** : R122 est close par sa propre
> condition (`ever_recurred_observed` 37 ≤ 47), rotée dans `archive.md`. L'ordre vivant
> est celui de l'index ci-dessus, et à l'intérieur de R137 celui de sa table des familles.
> Le raisonnement ci-dessous reste lisible parce qu'il vaut pour toute tâche de VOLUME —
> mise en tête, elle consomme la séance sans qu'aucune autre avance.
>
> **Ordre de travail arrêté le 2026-09-16** : R122 passait en DERNIER, délibérément et
> sans être bornée. Elle est du volume mesurable — **363 → 332 portées en 89 minutes**,
> soit ~16 h pour la colonne `guard_scope` seule, et deux autres colonnes derrière. Mise
> en tête, elle consommerait une séance entière sans qu'aucune autre tâche avance. Les
> quatre tâches au-dessus ont un critère de fin net ; elles passent d'abord.
> R117 devait fermer la marche, parquée pour la raison qu'elle **ne pouvait pas être
> faite par la séance qui la ferait** : elle déplace le dépôt hors de `/mnt/c`, donc
> elle tue le `cwd` et la mémoire de Claude, indexée par chemin. Elle s'est parquée
> au premier réveil de la séance longue, puis a été livrée le 2026-09-17 — détail
> dans `archive.md`.

---

## R132 — L'isolement de flotte s'arrête aux frontières du garde · P3

Ouverte le 2026-09-17, en balayant les frères de `multitenant-dag-fleet-poisoning`.
**Le balayage a trouvé 8 sites vivants sur 6 fichiers de production alors que le garde
était VERT sur 13 tests** ; les 8 sont corrigés et le garde élargi les rougit. Ce qui
reste est ce que le garde **ne peut pas** voir, et il faut le dire avec sa raison.

### Ce qui reste, et pourquoi le garde ne l'atteint pas

| site | forme | pourquoi hors de portée |
|---|---|---|
| `src/utils/metric_bounds.py:124-129` | **aveuglement de flotte** | la boucle est ici, le `try` est dans `alert_monitor.py::check_metric_bounds` — **un autre module**. Une levée sur un locataire ne fait pas tomber le DAG : elle vide les constats de la nuit pour TOUS, silencieusement. Le détecter demande une analyse **inter-procédurale**, pas un prédicat plus large |
| `src/dashboard/views/onboarding_health.py:65` | crash, variante Streamlit | `for aid, name in artists:` sous un `try … finally: db.close()` **sans `except`** — une levée fait tomber toute la page admin, pas la ligne de l'artiste. Hors du périmètre `airflow/dags/` du garde |
| `airflow/dags/trial_expiry_reminder.py:147` | **corrigé à la main** | la source de flotte est `_due_accounts(db)`, pas `get_active_artists()` : `_artist_loops` ne reconnaît pas la boucle. Le site est fermé, **le garde ne le protège pas** |
| `airflow/debug_dag/` ×4 | aveuglement | `debug_meta_token_refresh.py:58`, `debug_alert_monitor.py:45`, `debug_ml_scoring.py:58`, `debug_ml_outcome_labeling.py:48`. Scripts interactifs, hors production |

⚠️ **Trois axes indépendants, et c'est pour ça que ce n'est pas un élargissement de
plus.** Fermer ces sites demande de bouger en même temps la portée FICHIER (au-delà de
`airflow/dags/`), la détection de SOURCE de flotte (au-delà de `get_active_artists`), et
la portée du `try` (au-delà de la même fonction). Chacun élargi seul peut faire rougir
des boucles d'agrégation légitimes — le mode d'échec que ce dépôt a déjà mesuré sur un
garde élargi trop vite. C'est une refonte du modèle de « boucle de flotte », pas une
correction.

- [ ] **R132 — décider, pour chacun des 6 sites, entre le corriger à la main et étendre
      le garde ; et si le garde est étendu, le faire UN AXE À LA FOIS avec la mesure du
      bruit qu'il produit.**

  Le premier axe utile est probablement la SOURCE de flotte : `_due_accounts(db)` et
  `SELECT DISTINCT artist_id` sont des boucles par locataire aussi légitimes que
  `get_active_artists()`, et rien ne les reconnaît.

  ⚠️ **Ne pas viser un compteur.** `siblings_never_swept` a baissé de 1 en trouvant 8
  sites : c'est le balayage qui vaut, pas le nombre.

  **Mesuré par** : le balayage AST qui a produit cette liste —
  `python3 - <<'PY'` … (boucles par locataire, appels risqués hors `try`) ; il doit
  rendre 0 site hors `debug_dag/` pour que R132 se ferme.

## R137 — La moitié des classes vivantes n'a jamais eu de vrai balayage · P3

Ouverte le 2026-09-18. Elle **déplace la cible**, et c'est le point de la tâche.

Le facteur ×4,9 qui justifiait le rituel des gardes est tombé le 2026-09-18 : biais
d'*immortal time* en entier, **×1,1** une fois l'exposition découpée au premier garde
(CLAUDE.md règle 15 porte le tableau ; `make error-health` § « Ce que le biais valait »).
Depuis, **aucune strate ne sépare** — toutes à intervalles recouvrants sur 43 évènements.

Il ne reste donc **qu'un seul chiffre de RÉSULTAT**, déjà publié : **100 sites vivants
trouvés**, 39 classes en ont trouvé, taux **0,129** sur verdicts lisibles. 100 vrais
défauts dans du code dont personne ne s'était plaint. Ce n'est pas ce que les compteurs
optimisent : sur 13 compteurs de trou, **12 comptent des champs remplis**.

### Ce qui est ouvert, mesuré classe par classe

Les 403 entrées classées par l'état RÉEL de leur balayage, avec le code du générateur
(`_swept_by_rerunning_the_guard`, `_swept_sites` — `tools/dev/error_class_health.py:333-362`) :

| état | classes | zone |
|---|---:|---|
| verdict lisible — 0 site | 206 | dormante |
| **relance du garde — FAUX balayage** | **97** | vivante |
| verdict lisible — 0 site | 57 | vivante |
| verdict lisible — sites VIVANTS | 39 | vivante |
| verdict muet · jamais balayée | 3 · 1 | vivante |

**101 des 197 vivantes (51 %).** Leur `siblings:` dit « j'ai relancé le garde, il est
vert » — ce qui prouve que le prédicat de CE garde ne trouve rien, **jamais qu'il n'y a
rien**. Mesuré trois fois la nuit du 17 au 18, dont un garde **vert sur 8 sites vivants**
(`multitenant-dag-fleet-poisoning`, devenue R132).

### L'ordre : une unité = une FAMILLE (règle 21), par récidive décroissante

| famille | à balayer / vivantes | récidive |
|---|---:|---:|
| `le-locataire` | 8 / 24 | 21,4 % |
| `deux-surfaces-deux-nombres` | 7 / 15 | 17,2 % |
| `un-état-qui-déborde-de-sa-portée` | 8 / 13 | 12,0 % |
| `un-garde-qui-ne-garde-pas` | 20 / 47 | 11,0 % |
| `une-configuration-qui-diverge-de-la-prod` | 8 / 14 | 8,3 % |
| `une-erreur-avalée-devient-une-absence` | 7 / 12 | 8,0 % |
| `un-document-qui-affirme-un-état-périmé` | 8 / 16 | 7,7 % |
| `un-travail-qui-n-arrive-nulle-part` | 4 / 6 | 6,7 % |
| `la-frontière-avec-le-dehors` | **8 / 8** | 5,9 % |
| `un-cumul-pris-pour-un-quotidien` | 5 / 9 | 5,3 % |
| `le-message-parle-au-mauvais-lecteur` | 4 / 6 | 5,0 % |
| `un-seuil-écrit-d-instinct` · `un-nombre-affirmé` | 4 / 5 · 3 / 7 | 0,0 % |
| `un-coût-payé-sans-contrepartie` · `le-temps-et-l-horloge` | 3 / 5 · 2 / 7 | 0,0 % |
| sans rattachement | 2 / 2 | — |

⚠️ **`la-frontière-avec-le-dehors` est 8 sur 8 — la seule famille dont AUCUNE classe
vivante n'a été balayée**, et c'est celle qui demande « ce que ce code envoie dehors — un
mail, un paiement, un secret — est-il ce qu'on croit, et vers qui ? ». Sa récidive basse la
place neuvième. **Le rang se discute, et c'est écrit ici pour ça** — pas corrigé en douce.

⚠️ Deux familles sont absentes parce que toutes leurs classes sont dormantes :
`un-contrôle-qui-ne-peut-jamais-passer` (4) et `l-instrument-ment-sur-ce-qu-il-mesure` (2).

### La prédiction, écrite AVANT le travail

Au taux de 0,129 et à 2,6 sites par classe qui trouve, ces 101 balayages doivent rendre
**≈ 13 classes à sites vivants et ≈ 34 défauts réels**. **Si le résultat est 0 ou 3, ce
n'est pas un échec du chantier : c'est le résultat que 0,129 ne se généralise pas** — les
39 qui ont trouvé sont peut-être exactement celles qu'on soupçonnait.

- [ ] **R137 — balayer les 101 classes vivantes dont le verdict n'est pas lisible, famille par famille, et corriger ce qui sort.**

  Par classe : `siblings:` commençant par `swept:<date>`, portant l'**entonnoir** —
  candidats bruts → écartés **avec leur raison** → `**N sites vivants**` en gras (la seule
  forme que `_swept_sites` lit) — et le prédicat **muté dans les deux sens** (règle 20).
  Nuit du 17 au 18 : **dix prédicats sur ~30 faux au premier jet**, facteur 3 à 25,
  toujours en sur-comptant.

  Tout site vivant est un **vrai défaut** : fix + garde + mutation rouge. Sauf s'il touche
  la prod, les secrets, une migration ou l'UX artiste — alors `make night-park` et la
  question dans « 🙋 En attente de toi ».

  ⚠️ **Ne pas faire tomber le compteur en boldant de la prose existante.** Un `siblings:`
  ne se réécrit qu'après avoir **relancé** le prédicat — sinon c'est faire baisser un
  compteur sans rien livrer, ce que les planchers de population interdisent.

  ⚠️ **Ne pas viser `guard_does_not_prove_itself` (306), `seen_red_unknown` (141) ni
  `cause_unknown` (140) pour eux-mêmes** : ils descendent comme effet de bord — on ne
  balaie pas une classe sans ouvrir son garde. En faire une cible propre serait retourner à
  l'optimisation d'un champ rempli, ce que la mort du ×4,9 condamne.

### Ce que le balayage a DÉJÀ trouvé — 16 sites vivants au 2026-09-18

Lot 1, `le-locataire`, 4 classes → **2 sites vivants, tous deux P1, corrigés** (`e94d836`) :
`_from_signup.py:145` écrivait une identité sans son miroir (locataire « connecté »
partout, jamais collecté) ; `_core.py:205` portait un contrôle de forme VACUOUS dont le
résultat atteignait un segment de chemin d'URL sortante. ⚠️ Corriger le second SEUL
transformait un refus franc en succès silencieux qui met le miroir à NULL — quatre
constats bloquants de `security-specialist`, détail dans le commit.

Lot 2, 4 classes → **14 sites vivants, non encore corrigés**. ⚠️ Ce total disait **13** avant que les entonnoirs soient écrits : le 14ᵉ est le site `à trancher` de `an-exemption-…`, que le rapport de balayage listait à part. Un site à trancher reste un site — le compter ailleurs aurait flatté le chiffre :

| classe | sites |
|---|---|
| `per-tenant-outcome-not-recorded` | **7** — la branche « credentials illisibles » qui `continue` sans enregistreur : `soundcloud_daily.py:146-159`, `youtube_daily.py:91-103`, `meta_ads_api_daily.py:79-90` et `:94-100` ; et une liste locale que rien ne relit : `ml_scoring_daily.py:61-86`, `ml_outcome_labeling.py:60-80`, `weekly_digest.py:308-312`. ⚠️ Le garde existant confond « il y a un `.append()` » avec « une porte extérieure alerte » — faux négatif **prouvé par mutation** sur un DAG fabriqué |
| `write-path-without-cache-invalidation` | **6** — `instagram_api_collector.py:329-339`, `soundcloud_api_collector.py:348-352`, `youtube_daily.py:171`, `spotify_api_daily.py:180` et `:470`, `_meta_upsert.py:329-333`. La purge vit côté DÉCLENCHEUR (le bouton du dashboard), jamais côté ÉCRITURE : tout autre chemin (UI Airflow, CLI, `full_history` en journée) écrit dans une table cachée sans que rien ne le sache |
| `an-account-filter-that-names-no-single-column` | **0** — les 7 candidats inspectés un par un, garde exécuté contre une base vivante (3 tests, non skippés) |
| `an-exemption-on-one-surface-reads-as-a-failure-on-another` | **1 à trancher** — `spotify_api_daily.py:344-378` exempte le bac à sable de la résolution d'ambiguïté, donc il ne peut structurellement recevoir aucune donnée Spotify ; `artist_readiness.py` ignore l'exemption et affichera « importe ton CSV, ou vérifie l'ID artiste » — un geste que ce locataire ne peut pas faire. Non observable en local (bac à sable vide) : la preuve vit en production sur le locataire 18 |

⚠️ **Ce que ces deux lots disent du taux de 0,129** : 8 classes balayées, **16 sites**
(rendement global 100 → 116, taux 0,129 → **0,142**).
C'est bien au-dessus de la prédiction, et l'explication la plus probable n'est pas que le
dépôt soit plus cassé qu'on croyait — c'est que les classes JAMAIS balayées sont
précisément celles dont personne n'avait regardé les frères. À redire après 30 classes,
pas après 8.

  **Mesuré par** : `make error-health` — `swept_by_rerunning_the_guard` **0**,
  `sites_unknown` **3**, plafonds de `tests/test_the_error_class_health_only_improves.py`
  descendus **dans le même commit** (sinon `test_the_ceiling_is_not_slack` rougit).

## R138 — Rien ne refuse un faux balayage au moment de l'écrire · P3

Ouverte le 2026-09-18 en mesurant R137. Les 97 relances comptées comme des balayages ne
sont pas une négligence individuelle : **aucune porte ne les refuse**. Le compteur les voit
à la régénération suivante, après que la prose est écrite et commitée — et un compteur
qu'on lit une fois par jour ne change pas un geste. Le dépôt l'a déjà mesuré sur un autre
axe : il a fallu `--admission`, **bloquant**, pas une note.

### Et une porte présente que rien n'ouvre

`grep -rn "config-check" .github/` **ne rend rien**. Sur les cinq contrôles de
`make config-check`, un seul tourne en CI :

| contrôle | en CI ? |
|---|---|
| `check_config_refs.py` — chemins pendants dans `.claude/` | ❌ |
| `audit_unreachable_tools.py` — un outil que rien n'invoque | ❌ |
| `audit_runner.py --prose` | ✅ `ci.yml:205` |
| `audit_runner.py --coverage` | ❌ |
| `error_class_health.py --check` | ❌ (`make error-health-check` l'est) |

⚠️ **J'ai d'abord écrit que `--prose` était hors CI. C'était faux**, vérifié en lisant
`ci.yml` au lieu d'une sortie de balayage. Le trou réel est plus petit et mieux nommé.

- [ ] **R138 — `audit_runner.py --sweep-verdict`, et `config-check` câblé en CI.**

  `--sweep-verdict` : un `siblings:` en `swept:` doit porter `**N site(s) vivant(s)**` ou
  `**0 site vivant**`, et **ne peut pas** être une relance de garde. Sortie 2 comme
  `--lint` et `--admission`, plafond d'exemption **égal à la mesure du jour**.

  ⚠️ Le plafond descend au fil de R137. Posé à 97 et oublié, c'est le « plafond mou » que
  `test_the_ceiling_is_not_slack` refuse.

  ⚠️ **Lancer `config-check` avant de le câbler** : vert ici ne dit pas vert sur un runner,
  qui n'a pas le même arbre. Une porte câblée rouge apprend que le rouge est du bruit.

  **Mesuré par** : `audit_runner.py --sweep-verdict` sort 0 sur l'arbre sain et **≠ 0** sur
  une classe mutée en relance ; `grep -n "config-check\|sweep-verdict" .github/workflows/ci.yml`
  rend des lignes.

## R139 — Deux instruments qui mentent sur ce qu'ils mesurent · P4

Ouverte le 2026-09-18. Les deux trouvés en lisant les instruments, pas leur affichage.

**(a) Le document de santé compte deux fois.** `swept_by_rerunning_the_guard` (97) est un
sous-ensemble **strict** de `sites_unknown` (100) : intersection **97**, **3** muets hors
relance, **0** relance chiffrée. Les deux sont publiés dans deux paragraphes ⚠️ consécutifs
**sans que rien ne dise qu'ils se recouvrent** — un lecteur additionne et lit 197.
`anchor-a-number-to-its-population`, commise dans le document dont c'est le sujet.

**(b) `.test_durations` décrit un arbre qui n'existe plus, dans les deux sens.** Ce fichier
équilibre les **4 shards de CI**. Comparé à une collecte réelle le 2026-09-18 :

| | |
|---|---:|
| entrées dans `.test_durations` | 7 564 |
| node-ids réellement collectés | 8 039 |
| **entrées FANTÔMES — non collectables** | **174** · **33,9 s** |
| **tests collectés SANS durée** | **475** |

Les deux plus grosses sont les tests de fraîcheur retirés le jour même
(`test_the_document_still_describes_the_repository` **19,54 s**,
`test_the_snapshot_still_describes_the_catalogue` **8,21 s**) — **82 % de la masse
fantôme**. `make test-durations` relancé le même jour ne les a pas retirées : le fichier
**ajoute sans retirer**, comme `graphify update`. 33,9 s sont attribuées à du travail que
rien ne produit, et 475 tests entrent sans poids. Invisible : la CI reste verte.

⚠️ **Le prédicat évident est FAUX.** Vérifier que le FICHIER d'un node-id existe rend
**0 fantôme** — les 174 vivent dans des fichiers présents, seul le test a disparu. Règle 20
en une ligne : une FORME (« le fichier est là ») au lieu d'une PROPRIÉTÉ (« ce node-id est
collectable »). Seul un diff contre une **collecte réelle** répond.

⚠️ Et j'ai commis l'autre moitié en vérifiant : mon premier contrôle a cherché le nom du
test par sous-chaîne dans le source, l'a trouvé **dans le commentaire qui explique son
retrait**, et j'en ai conclu qu'il existait. `guard-satisfied-by-its-own-comment`, deux
minutes après l'avoir écrite au catalogue.

- [ ] **R139 — publier `sites_unknown_hors_relance`, et purger `.test_durations` de ce qui ne s'exécute plus.**

  ⚠️ Le garde de (b) coûte une collecte (~8 s). Il va donc là où `.test_durations` sert —
  **en CI, à côté du calcul des shards** — pas dans la suite à chaque exécution. Décider ça
  AVANT de l'écrire : un garde cher au mauvais endroit se fait retirer, et sa propriété part
  avec lui. Son `guard_scope` doit nommer ce qu'il ne couvre pas : les **475 sans durée**.

  **Mesuré par** : `make error-health` → les deux populations ne s'additionnent plus ; et le
  diff de `.test_durations` contre `pytest --collect-only -q` rend **0 non collectable**.
  Deux gardes neufs, chacun muté rouge.

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

## 🔖 REPRISE — état au 2026-09-18 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R132, R133, R134, R135, R137, R138, R139, R141, R125, R140 -->

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

**La table « 🙋 En attente de toi » porte UNE ligne** : R125, entrée le 2026-09-18.
⚠️ Ce paragraphe a affirmé le contraire — « reste vide … aucune tâche n'attend un geste
humain » — **vingt-cinq lignes après avoir décrit R125 qui y est**. La même section se
contredisait donc elle-même, et c'est `a-prose-claim-that-cannot-be-verified` commise
dans le fichier qui la nomme.

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
| R125 | Saisir les écoutes 28 j réalisées (DW / RR / Radio) pour au moins un morceau, dans **Saisie S4A** | P3 | ouvrir Saisie S4A, entrer les trois chiffres à 28 jours pour un morceau prédit il y a plus de 28 jours — voir §15 du runbook |
| R140 | Trancher **quatre décisions de produit** trouvées par le balayage R137 — un appariement de titres trop large dans le PDF, un jeton SoundCloud partagé entre dev et prod, un bouton « ce locataire » qui déclenche la flotte, un script de migration sans allowlist | P2 | lire les quatre mesures et dire pour chacune ce que le produit DOIT faire — voir §16 du runbook |

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
