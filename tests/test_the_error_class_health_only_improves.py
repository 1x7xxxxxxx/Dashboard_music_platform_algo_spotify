"""L'instantané de santé du catalogue ne peut que s'améliorer — sauf le taux.

Type: Test
Uses: tools/dev/error_class_health, json
Depends on: .claude/dev-docs/error-class-health.{json,md}
Persists in: nothing

Mutation record — 2026-09-16 : huit mutations jouées, **huit vues ROUGES**.
  1. plafond `cause_inferred` relevé de 1       → rouge (plafond au-dessus de la mesure)
  2. classe synthétique sans les trois champs   → rouge (`seen_red_unknown` grandit)
  3. `cause_evidence: inferred` sur une classe  → rouge (2 tests : trou + plafond lâche)
  4. plancher d'exposition porté à 999 999      → rouge (fenêtre rétrécie)
  5. SUPPRESSION d'une classe du catalogue      → rouge (plancher de population)
  6. parseur rendant 0 classe                   → rouge (5 tests — jamais vert-sur-vide)
  7. ids divergents entre les deux lecteurs     → rouge (4 tests)
  8. document édité à la main sans régénérer    → rouge (fraîcheur, nomme le remède)
  9. deux fins de ligne au lieu d'une           → rouge AU COMMIT SUIVANT (voir ci-dessous)

  ⚠️ Deux de ces mutations ont d'abord été écrites FAUSSES et rendaient le garde vert :
  la n° 3 insérait le champ dans le bloc `## Per-class schema` — un gabarit, pas une
  classe — et une première tentative renommait une variable des deux côtés, donc ne
  désactivait rien. **Une mutation qu'on n'inspecte pas ment dans le même sens que le
  garde**, et les deux fois j'ai failli conclure « il ne mord pas ».

  ⚠️ Et le premier commit a été REFUSÉ par pre-commit, pour deux raisons que seul le
  commit pouvait révéler : `end-of-file-fixer` retirait la ligne vide finale du document,
  donc le disque cessait d'égaler `build()` **dès le commit** ; et `detect-secrets` voyait
  les SHA de commit stockés dans le JSON comme 89 secrets à haute entropie. Le SHA est
  sorti du document — le marquer en faux positif ferait enfler `.secrets.baseline` à
  chaque régénération, et un fichier qui change tous les jours n'a rien à faire dans une
  liste d'exceptions. **Un générateur doit produire exactement ce que les crochets
  laissent passer**, sinon son cliquet est rouge sans que rien n'ait bougé.

Ce qui est cranté, et ce qui ne l'est surtout PAS
--------------------------------------------------
**Le taux de récidive n'est pas cranté**, et c'est la décision centrale de ce fichier.
Mesuré le 2026-09-16, normalisé par le temps d'exposition, il **monte** : la cohorte de
septembre porte 0,35 évènement par classe-mois contre 0,11 pour celle de mai. Un cliquet
« le taux ne peut que baisser » serait donc rouge le jour où on l'écrit — et ce dépôt a
la classe `a-gate-that-can-never-be-green` pour ça.

Ce qui se crante, c'est la **MÉTHODE** : la part de classes dont la connaissance est
invérifiable. Elle ne baisse que par du travail. Et des **planchers de population**
empêchent de la faire baisser en supprimant des classes — un taux s'améliore aussi bien
en corrigeant qu'en effaçant, et seul le plancher distingue les deux.

Le résultat qui a justifié tout ça
------------------------------------
Première mesure séparant les strates, 2026-09-16 : une classe **sans garde automatique
récidive 5,2× plus** (1,005 évènement par classe-mois contre 0,193), et **les intervalles
à 95 % ne se recouvrent pas** (0,433–1,980 contre 0,142–0,257). Deux estimations
précédentes — « 15 % contre 23 % », puis « pas robuste » — étaient fausses pour la même
raison : elles comptaient des CLASSES, pas des évènements par temps d'exposition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_DATA = _ROOT / ".claude" / "dev-docs" / "error-class-health.json"
_DOC = _ROOT / ".claude" / "dev-docs" / "error-class-health.md"

# ── Gelé à la MESURE du 2026-09-16, jamais à une estimation ──────────────────
# Ces plafonds ne peuvent que BAISSER. Les faire baisser demande soit de renseigner un
# champ sur une classe, soit de retirer une classe devenue fausse — les deux sont des
# progrès. Les planchers plus bas interdisent la seconde de devenir un raccourci.
_CEILINGS = {
    # Resserrés le 2026-09-16 dans le commit de la passe mécanique, comme
    # `test_the_ceiling_is_not_slack` l'exige : un plafond laissé au-dessus de la mesure
    # est du budget pour régresser en silence.
    # 331 → 309 le 2026-09-18 (axe 2 de la nuit) : VINGT ET UN gardes P1 mutés et vus
    # rouges, un par un. ⚠️ DEUX mutations ont d'abord échoué en disant quelque
    # chose sur MOI et non sur le garde : un `chmod -x` sur le DISQUE laissait
    # `exec-bit-lost-outside-the-index` vert, à raison — il lit l'INDEX, ce que
    # `git archive` embarque ; et casser `_build` produisait 11 ERREURS d'import
    # au lieu d'un échec du garde, c'est-à-dire un autre mode de panne, donc pas
    # une preuve. Un garde ne compte comme vu rouge que s'il ÉCHOUE sur le défaut.
    # Historique : 363 → 352 (les `n-a`) → 332 (phase B, traces de mutation) → 330
    # le 2026-09-17 (un défaut remis et vu lever) → 321 ce jour-ci.
    "seen_red_unknown": 129,  # 140 → 138 le 2026-09-25 ; → 137 le 2026-09-26 (R169) ; → 134 ; → 133 ; → 132 ; → 131 ; → 130 ; → 129
    # ── Ajouté le 2026-09-18 avec l'état `self-proving` ─────────────────────────
    # Voir une signature rouge UNE fois, à la main, prouve qu'elle mordait CE SOIR-LÀ.
    # Un garde qui porte un test fabriquant la forme interdite se prouve à CHAQUE
    # exécution. À l'introduction : **9 gardes sur 192** le faisaient (5 %), donc 391
    # classes sur 400 n'ont pas cette preuve. Le plafond ne peut que baisser, et il
    # baisse en ÉCRIVANT le test de non-vacuité dans le garde — pas en rédigeant.
    "guard_does_not_prove_itself": 270,  # 306 → 303 le 2026-09-25 (R169) ; → 300 le 2026-09-26 (migration P1 gardée, central-app + wrapper RTK auto-prouvants) ; → 297 (shared-db, replica, prose-claim) ; → 294 (collector, env, connexion par vue) ; → 292 (digest du guide, porte de dépendances) ; → 288 (4 preuves existantes enfin citées) ; → 285 ; → 284 ; → 281 ; → 278 ; → 276 ; → 274 ; → 270
    "seen_red_never": 0,
    # 363 → 241 : les causes qui nomment un chemin vérifiable.
    # 241 → 183 le 2026-09-17 : les **58** classes dont le `root_cause` cite un fichier
    # ont été vérifiées UNE PAR UNE, en ouvrant le site et en cherchant soit le mécanisme
    # décrit, soit son correctif. 56 en `read`, 2 en `measured` (une mesure d'infra et un
    # `wc -c`).
    #
    # ⚠️ **Deux des 58 adresses étaient PÉRIMÉES**, et c'est le résultat le plus utile de
    # la passe : `bom-survives-the-encoding-fallback` nommait
    # `views/upload_csv.py::_read_headers`, qui vit maintenant dans
    # `utils/csv_serialization.py` ; `download-payload-rebuilt-per-rerun` nommait
    # `views/process_guide.py`, SUPPRIMÉ. Dans les deux cas la cause est juste et son
    # adresse ne l'est plus — c'est `a-signature-anchored-on-a-location` appliquée au
    # champ `root_cause`, que sa signature ne couvre pas (elle ne cherche qu'un numéro de
    # ligne). Le `cause_evidence` de ces deux classes le dit à l'endroit où on le lira.
    #
    # ⚠️ Les **183** qui restent n'ont AUCUNE ancre vers du code : les étiqueter demande
    # de retrouver la cause d'abord, pas de la relire. C'est pourquoi ce compteur ne se
    # comble pas en écrivant, et pourquoi `cause_inferred` reste crânté à 0 — marquer en
    # masse « plausible, non vérifié » ferait baisser CE compteur en faisant monter
    # l'autre, et la mutation n° 3 de ce fichier refuse ce troc.
    # −1 le 2026-09-17 : `multitenant-dag-fleet-poisoning` passe en `measured` — les
    # trois prédicats fautifs de son garde ont été EXÉCUTÉS un par un, pas relus.
    # 181 → 148 le 2026-09-18, et la méthode compte autant que le chiffre. Les 181
    # n'avaient AUCUNE ancre vers du code — les étiqueter demandait de retrouver la
    # cause, pas de la relire. Ce qui a débloqué : ancrer sur un SYMBOLE au lieu d'un
    # chemin. Entonnoir mesuré : 181 → **112** citant un symbole → **73** dont le
    # symbole existe dans l'arbre → **48** dont le symbole est DISTINCTIF et défini en
    # production → **34** dont le fichier ancré contient AU MOINS DEUX jetons de la
    # cause (un seul peut être une coïncidence) → **33** après lecture, la 34ᵉ écartée
    # parce que son ancre tombait dans du rendu PDF sans rapport.
    #
    # ⚠️ Les 33 ont été LUES, une par une. La confirmation mécanique choisit QUOI lire ;
    # elle ne remplace pas la lecture, et `read` veut dire « j'ai lu ».
    "cause_unknown": 117,  # 140 → 117 le 2026-09-26 (R169, causes lues dans le code) ; 182 → 181 le 2026-09-17 : `object-dtype-numeric-op` mesurée — `SUM(bigint)`
    # rend `numeric` en PostgreSQL, donc dtype `object` SANS aucun NULL.
    "cause_inferred": 0,
    "scope_unknown": 0,               # 363 → 0 : la famille est dérivable pour toutes
    # −21 le 2026-09-17 : la famille `le-locataire` est à ZÉRO (42/42). Choisie la
    # première non pour son volume — `un-garde-qui-ne-garde-pas` est plus grosse —
    # mais pour sa RÉCIDIVE : 33,3 %, soit 3,4× la plus grosse famille, et c'est elle
    # qui a coûté les deux sessions de test artiste ratées.
    # −12 de plus le même jour : `la-frontière-avec-le-dehors` est à ZÉRO aussi
    # (18/18), récidive 23,5 %. Les DEUX familles les plus récidivistes du
    # catalogue sont désormais intégralement couvertes.
    # −15 de plus : `une-erreur-avalée-devient-une-absence` aussi (21/21),
    # récidive 19 %. Les TROIS familles les plus récidivistes sont à zéro ;
    # 48 portées écrites dans la séance, chacune en ouvrant son garde.
    # −13 : `un-cumul-pris-pour-un-quotidien` aussi (19/19), récidive 21,1 %.
    # ⚠️ Cette quatrième famille a été choisie sur un taux RECALCULÉ, pas sur
    # celui de la prose : les taux par famille vivaient dans une analyse
    # ponctuelle et s'étaient périmés (`la-frontière` annoncée à 23,5 %, mesurée
    # à 22,2 %). La colonne est désormais rendue par `make error-families`.
    # −18 : `un-état-qui-déborde-de-sa-portée` aussi (24/24), récidive 16,7 %.
    # −11 : `un-travail-qui-n-arrive-nulle-part` aussi (15/15), récidive 13,3 %.
    # −12 : `un-seuil-écrit-d-instinct` (8/8) et `un-coût-payé-sans-contrepartie`
    # (8/8), 12,5 % chacune. HUIT familles à zéro, 102 portées dans la séance.
    # −24 : `deux-surfaces-deux-nombres` à ZÉRO (29/29), récidive 10,3 %.
    # −21 : `une-configuration-qui-diverge-de-la-prod` à ZÉRO (24/24), 8,3 %.
    # −19 : `le-message-parle-au-mauvais-lecteur` à ZÉRO (20/20), 5,0 %.
    # −18 : `le-temps-et-l-horloge` à ZÉRO (20/20). DOUZE familles à zéro,
    # 184 portées. −18 : `un-nombre-affirmé-qui-n-a-pas-été-mesuré` à ZÉRO (20/20).
    # −32 : `un-document-qui-affirme-un-état-périmé` à ZÉRO (41/41).
    # QUATORZE familles à zéro, 234 portées dans la séance.
    # −63 : `un-garde-qui-ne-garde-pas` (47/47 restantes) et les 3 orphelines.
    #
    # ⚠️ **ZÉRO le 2026-09-17 — les 394 classes déclarent toutes un geste voisin NON
    # couvert.** Ce que ce zéro veut dire, et surtout ce qu'il ne veut pas dire : chaque
    # classe NOMME désormais au moins une chose que son garde laisse passer. Il ne dit
    # rien de la JUSTESSE de ce qui est nommé — aucune de ces 394 affirmations n'est
    # vérifiée mécaniquement, et le catalogue a déjà mesuré que 4 portées sur 6 écrites
    # avec soin étaient inexactes (voir `/capitalise`, « Je lis le CODE du garde »).
    # Le compteur qui reste honnête après celui-ci est `siblings_never_swept` : lui
    # parle du PRÉSENT et se vérifie.
    #
    # ⚠️ **Le plancher de population est ce qui empêche ce zéro d'être gratuit.** Un
    # `scope_without_not_covered` à 0 s'obtient aussi bien en écrivant 394 portées qu'en
    # supprimant 394 classes ; `_FLOORS` refuse la seconde voie.
    "scope_without_not_covered": 0,
    # ⚠️ Compteur NEUF le 2026-09-17, posé sur une question du propriétaire : « est-ce
    # qu'on a intégré la réflexion de savoir si l'erreur découverte peut être situéé
    # ailleurs dans le code ? ». La réponse mesurée était NON — 69 classes sur 395
    # portaient une trace de balayage, 326 aucune, et ni `/capitalise` ni le schéma ne
    # posaient la question.
    #
    # ⚠️ Ne PAS le confondre avec `scope_without_not_covered` : `ne couvre pas` parle
    # du FUTUR (ce que le garde laissera passer), `siblings` parle du PRÉSENT (où le
    # même défaut vit déjà). Le balayage de `a-replica-that-builds-its-own-image` a
    # trouvé DEUX sites vivants sur lesquels le garde était vert.
    # −8 le 2026-09-17 : les balayages RÉELLEMENT faits ce jour-là.
    # −1 de plus le même jour : `server-side-render-fetches-tenant-chosen-urls`, et ce
    # balayage-là a trouvé **DEUX sites vivants** — `grep -rn "HTML(string=" src/` rend
    # TROIS rendus WeasyPrint, un seul passait `url_fetcher`. Aucun ne touchait à de la
    # donnée de locataire, donc il n'y avait pas de défaut vivant : la clôture était la
    # propriété d'un SITE et non du GESTE, et rien ne pouvait le voir. C'est ce que ce
    # compteur existe pour produire — pas un nombre, des sites.
    # −1 de plus le 2026-09-17 : `multitenant-dag-fleet-poisoning`, et ce balayage a
    # trouvé **8 sites vivants sur 6 fichiers de production** alors que son garde était
    # VERT sur 13 tests. Deux compteurs bougent ensemble et c'est le signe recherché :
    # le balayage produit des sites, pas un nombre.
    # 384 → 352 le 2026-09-17 : **32 balayages EXÉCUTÉS**, pas déclarés. Chaque
    # `siblings:` porte la commande, son verdict du jour, et la mention que c'est le
    # PRÉDICAT qui a été balayé — parce que ce dépôt a mesuré le même jour qu'un
    # garde parcourant l'arbre peut rester vert sur 8 sites vivants.
    #
    # ⚠️ Le tri des 7 signatures `heuristic` — celles dont un exit ≠ 0 est le mode
    # NORMAL — a produit un défaut réel : `a-fallback-that-answers-the-whole-question`.
    # C'est la justification de ce compteur en une ligne : il ne sert pas à descendre,
    # il sert à faire regarder.
    # 352 → 255 : les 97 classes dont le garde est un pytest QUI PARCOURT L'ARBRE,
    # exécuté ce jour-là (90 node-ids, 3201 tests, 0 rouge).
    #
    # ⚠️ **Une classe a été EXCLUE de l'estampillage** — `environment-failure-worn-as-
    # a-code-failure`, dont le garde ne tourne QU'EN CI (« only meaningful inside CI »)
    # et a donc SKIPPÉ ici : il n'a rien balayé, l'estampiller serait un faux calme.
    # Trois autres sont estampillées en NOMMANT ce qui a skippé chez elles — un DAG
    # exempté, 27 scripts hors périmètre, un jeu de paramètres vide (légitime : la
    # liste d'orphelins est vide parce que les classes ont été écrites).
    # −1 le 2026-09-17 : `column-name-is-not-its-meaning`, et le site trouvé est
    # l'outil que `.claude/rules/python.md` NOMME comme garde de cette règle —
    # il matchait sur le NOM de la colonne là où la règle exige le TYPE.
    # TROISIÈME garde de la séance vert sur ce qu'il prétend garder.
    # 254 → 240 le 2026-09-17 : la famille `le-locataire`, classe par classe, avec une
    # recherche CONÇUE pour chacune — ces gardes-là visent UN site, donc les exécuter
    # n'est pas un balayage. Ce que les recherches ont établi, et qui ne se lit nulle
    # part ailleurs : les 8 décideurs de « connecté » passent tous par
    # `declared_identities` ; les 3 consommateurs de statut dérivent tous de
    # `SOURCES_FOR_PLATFORM` ; les seules écritures de credentials hors des 3 chemins
    # humains sont des rafraîchissements de JETON, qui ne touchent aucune identité.
    # 240 → 234 le 2026-09-17 : la famille `un-document-qui-affirme-un-état-périmé`.
    # DEUX sites vivants trouvés, tous deux invisibles à leur garde :
    #  · `make sync` lançait `uv sync` sans vérifier `uv` — seule cible du Makefile
    #    sans prérequis NI garde en ligne à l'ajouter depuis le tri de mai ;
    #  · `make caddy-drift`, nommé dans un `guard_scope` de ce catalogue, N'EXISTE
    #    PAS (la cible est `caddy-validate`) — et il était dans mon écriture du jour.
    #
    # ⚠️ Et le balayage a corrigé un CHIFFRE : la signature brute de `make-fail-late`
    # rend 34 lignes, soit **8,5× la réalité** — 16 cibles, 12 sans prérequis,
    # 4 sans aucun garde. Lire le nombre brut aurait ouvert un chantier fantôme.
    # 234 → 224 le 2026-09-17 : la famille `deux-surfaces-deux-nombres`. Aucun site
    # vivant cette fois, et c'est un résultat : les 2 soustractions d'horloges
    # restantes sont tz-aware des deux côtés, le PDF et l'écran importent les MÊMES
    # fonctions de série.
    #
    # ⚠️ Ce que les balayages ont surtout produit, ce sont des POPULATIONS non
    # triées, que seuls ces champs portent désormais : **58** agrégats pandas dans
    # les vues (invisibles à tout garde qui lit du SQL), **20** invariants or pour
    # 19 objets `gold_*` déclarés — donc pas une couverture un-pour-un — et **21**
    # contrôles dans le mail du soir dont UNE SEULE paire est confrontée à
    # elle-même. Les 19 autres ne le sont par personne.
    #
    # ⚠️ Et une leçon de MOTIF : la recherche « soustraction d'horloges » n'a PAS vu
    # le mélange naïf/aware d'`airflow_monitor.py:124`, trouvé le même jour par une
    # autre recherche — le défaut y était une COMPARAISON. Deux motifs pour une
    # cause, et un seul aurait conclu « aucun site ».
    # 224 → 218 le 2026-09-17 : `un-nombre-affirmé-qui-n-a-pas-été-mesuré`.
    # Le balayage qui compte : `insert_many` rend TOUJOURS `len(data)` — le compte
    # ENVOYÉ — et trois appelants gardent cette valeur. Le seul qui montre un chiffre
    # à un ARTISTE mesure le delta (`_rows_in_table` avant/après) ; les deux autres
    # ne l'écrivent que dans un journal. 0 site vivant, établi en suivant la valeur,
    # pas en lisant le garde.
    #
    # ⚠️ **48 zéros fabriqués** (`COALESCE(…, 0)` / `fillna(0)`) dans les vues et les
    # utilitaires. Plusieurs sont délibérés ET COMMENTÉS comme tels ; les autres n'ont
    # été ni lus ni triés. C'est la liste où le prochain site de cette classe vit, et
    # elle n'existait nulle part avant ce balayage.
    # 218 → 215 le 2026-09-17 : `le-message-parle-au-mauvais-lecteur`, et le balayage
    # a trouvé **DEUX messages vivants face à l'artiste** sous un garde VERT —
    # « (lancez `ml_scoring_daily`) » dans une vue premium ET dans le PDF que
    # l'artiste REÇOIT. Aucun artiste ne peut lancer un DAG.
    #
    # ⚠️ QUATRIÈME garde de la séance vert sur ce qu'il prétend garder, et c'est
    # encore le trou de `pkill`/`pgrep` : `_PLUMBING` nommait les MOTS de la
    # plomberie (`DAG`, `Airflow`, `Postgres`) et pas ses NOMS. Sans le mot « DAG »
    # dans la phrase, il ne voyait rien. Élargi en DÉRIVANT la liste de
    # `airflow/dags/`, pour qu'elle ne se périme pas.
    # 215 → 209 le 2026-09-17 : `un-état-qui-déborde-de-sa-portée`. Aucun site vivant,
    # et trois faux positifs ÉCARTÉS EN LISANT plutôt qu'en comptant :
    #  · 3 écritures sur une clé de widget vivent dans un `on_click=` — une écriture
    #    en callback a lieu AVANT le rendu suivant, donc elle est légitime ;
    #  · 24 `INSERT` sans `ON CONFLICT` sur 35, mais seulement **2** ont la forme
    #    « récupère ou crée », et l'un prend un `pg_advisory_xact_lock` — le remède ;
    #  · l'autre est une course LATENTE, pas vivante : rien ne lance deux collectes
    #    Instagram simultanées pour un même locataire.
    #
    # ⚠️ Et j'allais nommer un garde INEXISTANT dans une portée
    # (`test_the_suite_does_not_borrow_a_real_connection.py`). Vérifié avant d'écrire —
    # c'est exactement ce que `named-guard-deleted-while-the-class-reads-guarded`
    # demande, et la vraie fixture vit DANS `test_postgres_handler.py:42-51`, donc sa
    # portée est ce fichier et lui seul.
    # 209 → 204 le 2026-09-17 : `le-temps-et-l-horloge`. Le TRI des signatures
    # `heuristic` est tout le travail ici, et il change les chiffres d'un ordre de
    # grandeur : 53 candidats `tz-aware-naive-mix` → **1** site réellement risqué,
    # et ce site est LE REMÈDE (`airflow_kpi.py:554` normalise en naïf-UTC avec le
    # commentaire qui nomme l'erreur qu'il évite). 10 candidats `naive-datetime-now`
    # → 3 de prose, 5 cosmétiques autorisés, 1 faux site, **1 VRAI défaut**.
    #
    # ⚠️ Incohérence LATENTE nommée au passage : `airflow_kpi` normalise
    # `start_date`/`end_date` en naïf-UTC quand `airflow_monitor` les produit
    # tz-aware. Deux consommateurs, deux conventions sur la MÊME donnée ;
    # `airflow_kpi` est sûr parce qu'il coerce, pas parce que la convention est
    # partagée.
    # 204 → 199 le 2026-09-17 : `un-cumul-pris-pour-un-quotidien`, 4ᵉ famille la plus
    # récidiviste. Balayé sur le REGISTRE des natures : `metric_bounds.KINDS` en
    # déclare **3** quand le produit en porte **5** — Instagram et Meta n'ont aucune
    # nature, et la boucle itère `for k in KINDS`, donc **2 plateformes sur 5 ne sont
    # jamais contrôlées en bornes**.
    #
    # ⚠️ Ce n'est PAS un trou silencieux, et c'est ce qui change le verdict :
    # `gold_invariants.py:24` l'écrit, Instagram est couvert par le détecteur de
    # collecte à zéro (rejoint le 2026-09-12), et Meta en est exclu avec SA MESURE —
    # sur une table de quantités du jour, le prédicat sonnerait **93 fois sur
    # 1 254 jours**. Une exclusion chiffrée est une décision ; c'est l'exclusion
    # non chiffrée qui est un défaut.
    # 199 → 194 le 2026-09-17 : `une-erreur-avalée-devient-une-absence`, 3ᵉ famille la
    # plus récidiviste. Balayé à l'AST sur la CAUSE, en entonnoir :
    #   123 `except` rendant une valeur vide → **46 MUETS** → **14** enjambant une
    #   lecture de données → **4** rendant `0` pour un TOTAL DE LOCATAIRE.
    # Les 4 rendent désormais `None` et journalisent.
    #
    # ⚠️ La conséquence était BORNÉE EN AVAL, et le dire change la sévérité : les
    # surfaces font `_fmt_big(x) if x else "—"`, donc aucun faux chiffre n'atteignait
    # l'artiste. Ce qui changeait : un échec de base indiscernable d'un catalogue
    # vide, sans trace, figé 600 s par `@st.cache_data`.
    #
    # ⚠️ **32 `except` muets restent non triés.** C'est la population où le prochain
    # site de cette classe vit, et elle n'existait nulle part avant ce balayage.
    # 194 → 191 le 2026-09-17 : `un-garde-qui-ne-garde-pas`, balayée sur la CAUSE
    # PARTAGÉE par les cinq instances de la soirée — un garde qui ÉNUMÈRE une
    # population au lieu de la DÉRIVER. Sur les **80** listes de noms écrites à la
    # main dans les gardes, **4** énumèrent des vues réelles : 6/45, 11/45, 11/45,
    # 22/45.
    #
    # ⚠️ **Le balayage a corrigé DEUX de mes propres affirmations du même jour** :
    # j'avais écrit « sur les 36 vues » dans ce catalogue pour un garde qui en
    # regarde **11**, et pour un balayage AST qui en parcourt **41**. Aucun des deux
    # chiffres n'avait été mesuré. Un sous-ensemble n'est pas un défaut ; celui qui
    # se laisse LIRE comme exhaustif en est un, et je l'ai lu ainsi deux fois.
    # 191 → 186 le 2026-09-17 : suite de `un-garde-qui-ne-garde-pas`.
    # Le balayage le plus net : tout appel `subprocess.*` dans `src/` et `airflow/` →
    # **ZÉRO**. Le code conteneurisé ne shelle plus jamais, et le site historique est
    # documenté AVEC sa mesure — l'image n'a ni `rclone` ni `git`, `command -v` ne
    # rend rien pour les deux (2026-09-04), d'où le passage à un reçu lu en base.
    # Un faux positif écarté en lisant : `useful_links.py:211` NOMME `pg_dump` dans
    # une chaîne affichée à un admin — une commande à taper sur l'HÔTE, pas un appel.
    # 186 → 184 le 2026-09-17 : les deux classes de CLIQUET, balayées PAR MUTATION —
    # parce que mes deux prédicats mécaniques se sont contredits et que je peux dire
    # pourquoi. Chercher un test nommé « slack/mou » rend **32** fichiers sans
    # anti-mou : il matche le mot dans la PROSE. Chercher la propriété
    # `mesure >= CEILING` à l'AST en rend **5** : il rate les plafonds lus depuis un
    # dictionnaire par une variable de boucle. Le seul chiffre défendable est
    # **25 constantes de plafond réelles sur 20 fichiers**.
    #
    # ⚠️ Six relevées de +50 : **QUATRE sont restées VERTES**, dont trois à ZÉRO —
    # et zéro est exactement là où le mou est invisible, parce qu'un 0 relevé à 50
    # ressemble à un 0 dans un diff. Le cas le plus net :
    # `test_the_ceilings_are_not_slack` est au PLURIEL et ne vérifiait qu'UN des deux
    # plafonds de son propre fichier. Trois corrigés, chacun re-muté rouge.
    # 184 → 179 le 2026-09-17. **Ma TROISIÈME recherche fausse de la soirée**, et elle
    # mérite d'être écrite : cherchant les pages admin gardées, j'ai d'abord conclu
    # « 10 sur 10 sans contrôle ». Faux — `app.py:598` porte UN contrôle centralisé
    # AVANT tout routage. Mon prédicat cherchait une garde À PROXIMITÉ de chaque
    # `page == '<clé>'`, et une garde centralisée est invisible à une recherche de
    # voisinage. Même leçon que sur les cliquets : le prédicat mécanique se trompe
    # dans les deux sens, et seule la LECTURE tranche.
    # 179 → 174 le 2026-09-17. **QUATRIÈME prédicat mécanique faux de la soirée**, et
    # celui-ci donne la règle qui manquait : mon balayage a signalé **7 sondes sur 7**
    # comme ne distinguant pas « illisible » d'« absent ». **7/7 n'est pas un
    # résultat, c'est un symptôme.** Les sondes rendent `(bool, message)` : la
    # distinction vit dans le MESSAGE (`inconclusive_page`, `token_missing`,
    # `app_not_configured`), pas dans le code que je cherchais.
    #
    # Les quatre prédicats faux de la soirée, et leur mode d'échec :
    #   · « slack » cherché par NOM        → 32 au lieu de ~4 (matche la prose)
    #   · `mesure >= CEILING` à l'AST      → 5 (rate les plafonds en dictionnaire)
    #   · garde admin par PROXIMITÉ        → 10/10 « sans contrôle », il est CENTRALISÉ
    #   · sonde par MOTS DU CODE           → 7/7, la distinction est en i18n
    # Deux sur-rapportent, deux sous-rapportent. Un résultat uniforme (0/N ou N/N)
    # doit faire LIRE avant de conclure.
    # 174 → 169 le 2026-09-17 : `la-frontière-avec-le-dehors`, 2ᵉ famille la plus
    # récidiviste. Les deux balayages qui comptent, tous deux exhaustifs :
    #   · **3 lectures d'en-tête** de requête dans tout le dépôt — `stripe-signature`
    #     (vérifié, et l'endpoint FERME EN DÉFAUT en 503 sans secret), `User-Agent`
    #     (cosmétique) et `Retry-After` (lu sur les réponses AMONT). L'IP cliente
    #     passe par UN parseur, qui lit depuis la DROITE de `X-Forwarded-For`.
    #   · **toutes les étiquettes Prometheus** sont bornées par construction, et
    #     aucune n'est un identifiant de locataire — ce qu'ADR-026 interdit.
    #
    # ⚠️ Un angle mort NOMMÉ plutôt que trouvé : `TRUSTED_PROXY_HOPS` vaut 2 et se
    # lit dans l'environnement. Un déploiement à UN proxy qui oublierait de le poser
    # retomberait sur le pair socket — le côté SÛR — mais dégraderait la granularité
    # du limiteur sans le dire.
    # 169 → 164 le 2026-09-17 : `une-configuration-qui-diverge-de-la-prod`.
    # Méthode appliquée deux fois : poser les DEUX MOITIÉS de la question
    # séparément. Pour les adresses d'écoute, l'outil dit exit 0 ET le motif
    # inverse (`0.0.0.0:`) ne rend rien — les 8 publications de port du dépôt sont
    # toutes sur `127.0.0.1`.
    #
    # ⚠️ Le garde du superutilisateur porte SIX propriétés, dont cinq lisent des
    # FICHIERS et une seule interroge la BASE (« le rôle vivant tient ses bornes »).
    # Cette dernière SKIPPE sans Postgres joignable : en CI sans base, le garde ne
    # vérifie que des fichiers, ce qui ne dit rien de la prod.
    # 164 → 159 le 2026-09-17 : `un-travail-qui-n-arrive-nulle-part`, et **DEUX sites
    # vivants trouvés dans MON travail de la même séance**. `telemetry_retention.py`
    # a été écrit pour fermer « déclaré en commentaire, appliqué par personne » ;
    # `purge_telemetry` était câblée, mais `purge_summary` et `undeclared_tables`
    # n'avaient AUCUN appelant. On ne ferme pas cette classe en écrivant un module
    # que personne n'appelle — c'est la même, un cran plus loin.
    #
    # ⚠️ **Le garde écrit pour ça a dû être corrigé TROIS fois, chaque fois par une
    # mutation qui passait au vert** : (1) `git grep` lit l'INDEX et ne voyait pas
    # une modification non indexée ; (2) `git grep --no-index` voyait le disque mais
    # aussi la PROSE — mon propre commentaire nommait la fonction, donc le garde se
    # croyait satisfait ; (3) seule la lecture à l'AST compte un appel. Les trois
    # versions ont été MESURÉES fausses, aucune devinée.
    # 159 → 154 le 2026-09-17 : `un-document-qui-affirme-un-état-périmé`.
    # Deux balayages menés sur les DEUX moitiés de leur chaîne, et les deux à zéro :
    #   · **21** `check_*` définis, **23** callables câblés, `[22 tâches] >> t_alert`
    #     — aucun détecteur sans opérateur, et aucun opérateur hors de la chaîne ;
    #   · les **7** services du compose portent tous `restart:` sauf `airflow-init`,
    #     où ce serait FAUX (conteneur à usage unique).
    #
    # ⚠️ **SEPTIÈME lecture textuelle fausse de la séance.** Mon premier motif sur
    # les politiques de redémarrage rendait « 10 services, 5 sans restart » : il
    # comptait les VOLUMES et les RÉSEAUX comme des services, et ne voyait pas la
    # valeur héritée par ancre YAML. Un analyseur YAML tranche en une ligne ce qu'un
    # motif ne peut pas voir.
    # 154 → 149 le 2026-09-17, et le balayage a trouvé un SITE VIVANT dans un crochet :
    # **DEUX** crochets de ce dépôt inspectent une commande Bash, **UN SEUL** lisait
    # la structure. `pre_commit_scan.py:140` testait `"git commit" not in command`,
    # donc un `grep` sur la documentation lançait un scan complet des fichiers
    # indexés et pouvait BLOQUER dessus. La classe était écrite, le garde était là —
    # et il regardait un seul des deux sites.
    #
    # ⚠️ **Ma première version du garde élargi est passée VERTE sur la mutation** :
    # elle appelait le prédicat DIRECTEMENT, donc elle prouvait qu'il est juste, pas
    # qu'il est BRANCHÉ. `guard-asserts-presence-not-reachability`, écrite dans le
    # garde qui venait fermer une autre classe. Fermé par un test AST exigeant que
    # `main()` appelle le prédicat.
    # 149 → 144 le 2026-09-17 : `le-locataire`, famille la plus récidiviste (33,3 %).
    # Balayage à l'AST de TOUS les DAG multi-tâches : quelles tâches lisent
    # `dag_run.conf` ? Trois candidats, **aucun n'est un site** — `alert_monitor`
    # n'est jamais déclenché avec un locataire (vérifié : aucun chemin du dashboard),
    # et les deux precheck n'ÉCRIVENT RIEN (ni upsert, ni execute_query, ni
    # record_tenant_*, vérifié à l'AST).
    #
    # ⚠️ `multitenant-mono-test-blindspot` est estampillée en DISANT ce qu'elle ne
    # ferme pas : les trois harnais multi-locataires existent, mais **rien ne mesure
    # combien des ~7 250 tests tournent sur un seul locataire**. La classe reste
    # ouverte par sa portée, pas par son garde.
    # 144 → 139 le 2026-09-17. Le balayage le plus instructif du lot :
    # **30** `upsert_many` à `update_columns` littéral, **21** rafraîchissent un
    # horodatage, **9** non. Un compte mécanique aurait rendu « 9 sites » ; ouvrir
    # UN SEUL suffisait — la date qui compte est dans la CLÉ DE CONFLIT, donc c'est
    # une dimension, et `saisie_s4a.py:176-180` documente que le « correctif »
    # évident **ferait planter** : lister `collected_at` dans `update_columns` fait
    # référencer un `EXCLUDED.collected_at` absent au second enregistrement du jour.
    #
    # ⚠️ **Huitième fois de la séance qu'un compte mécanique aurait induit en
    # erreur**, et la première où le remède supposé est lui-même le défaut.
    # 139 → 138 le 2026-09-17 : `song-name-convention-mismatch`, et DEUX sites vivants
    # visibles par l'artiste. S4A remplace `< > : " / \ | ? *` par `_` dans le nom de
    # ses FICHIERS, donc le même titre arrive épelé de deux façons. Deux requêtes
    # comparaient un nom de fichier à une table écrite par l'API : la courbe de
    # popularité était MUETTE pour tout titre ponctué — **5 titres** sur la base de
    # développement, mesuré.
    #
    # ⚠️ Le routeur qui remplit le sélecteur normalisait DÉJÀ pour SA jointure. La
    # convention existait, l'outil existait, et ils se perdaient UN APPEL plus loin.
    #
    # ⚠️ Mon garde est passé VERT sur sa première mutation (il cherchait le NOM dans
    # le texte, et retirer l'import le laissait satisfait), puis le cliquet
    # anti-garde-textuel a refusé DEUX autres comparaisons de chaîne que j'y avais
    # mises. Trois corrections pour un seul garde, toutes mesurées.
    #
    # ⚠️ **386 → 106 dans la nuit du 2026-09-17 au 18**, par ~30 balayages. Le
    # détail de chaque descente vit dans les messages de commit et dans le champ
    # `siblings:` de chaque classe — PAS ici. Il y était, sous forme de douze
    # fragments concaténés par une insertion automatique sur une seule ligne de
    # 600 caractères, et une ligne qu'on ne relit pas ne documente rien.
    #
    # Ce que la descente a rapporté est désormais CHIFFRÉ, ce qui n'était pas le
    # cas quand elle a commencé : voir `sites_unknown` juste dessous.
    # 1 → 0 le 2026-09-22. La dernière classe jamais balayée était
    # `a-diagram-is-verified-by-looking-at-it`, dont le balayage avait été REFUSÉ par
    # argument : « aucun prédicat ne sépare un schéma juste d'un schéma faux ». L'argument
    # est juste et répondait à la mauvaise question — un balayage de frères cherche les
    # autres surfaces où la MÊME confusion est commise, pas le détecteur. Reformulé en
    # « où affirme-t-on un visuel en ne vérifiant que du texte ? » : 2 sites vivants,
    # corrigés. **Le catalogue n'a plus aucune classe non balayée.**
    "siblings_never_swept": 0,
    # ── LE RENDEMENT, sous cliquet lui aussi (2026-09-18) ────────────────────
    #
    # `siblings_never_swept` mesure l'EFFORT ; ce compteur-ci mesure ce qu'on SAIT
    # du résultat. Un balayage FAIT dont la trouvaille s'est perdue en prose ne
    # compte ni comme zéro ni comme trouvaille — il compte comme un trou, et c'est
    # ce trou qui empêchait de répondre à « est-ce que balayer paie ? ».
    #
    # Mesuré le 2026-09-18 en donnant un verdict lisible au champ : sur 291
    # balayages, **49 seulement** en portaient un (34 à zéro, 15 avec des sites,
    # 30 sites au total). Taux de trouvaille sur ces 49 : **30,6 %** — le chiffre
    # qui justifie de continuer, et qui n'existait pas avant ce jour.
    #
    # ⚠️ Ce bloc a dû être RÉÉCRIT : l'insertion automatique avait concaténé sur
    # cette ligne les commentaires de chaque abaissement précédent de
    # `siblings_never_swept`. Le fichier restait valide et le cliquet fonctionnait —
    # c'est la LISIBILITÉ qui était perdue, et une ligne de 600 caractères ne se
    # relit pas.
    #
    # 242 → 101 le 2026-09-18 (axe 1 de la nuit). 41 champs disaient « aucun autre
    # site » sans le gras ; 94 autres étaient silencieux, et le SILENCE est le verdict :
    # une trouvaille est bruyante. Prédicat validé sur un jeu de CONTRÔLE de 91 verdicts
    # déjà connus — **0 faux négatif, 0 faux positif** — après que trois prédicats plus
    # naïfs eurent sur-classé (« aucun autre site » attrapait 131 champs dont 97 étaient
    # des relances de garde ; un discriminant de population en ratait « ZÉRO » et
    # « 5 plateformes »).
    #
    # ⚠️ Le rendement a CHUTÉ en remplissant le dénominateur : 32 % → 17,6 % → **11 %**
    # (21 balayages productifs sur 191, 52 sites vivants au total). Le premier chiffre
    # ne portait que sur les balayages de la nuit, ceux qui trouvaient. Un taux mesuré
    # sur la population qui l'a inspiré n'est pas un taux.
    # 2 → 0 le 2026-09-22 : les DEUX balayages muets tranchés, et la même cause
    # expliquait les deux — leur prédicat cherchait une FORME là où la classe parle
    # d'une PROPRIÉTÉ. `a-fallback-…-succeeded` : sept mots à droite d'un `||` → « le
    # repli AGIT-il ? », 1 site vivant que l'ancien motif avait vu PUIS écarté comme
    # faux positif de `commit` dans `pre-commit`. `a-guard-satisfied-by-the-collapse` :
    # `assert not …` → « vraie sur un écran vide ? », 2 sites prouvés par un témoin.
    # L'exemption codée en dur d'`audit_runner.py` a été VIDÉE dans le même commit :
    # la laisser aurait autorisé en silence un futur balayage muet sur ces deux noms.
    "sites_unknown": 0,
    #
    # ── « BALAYÉ » N'EST PAS « LE GARDE ÉTAIT VERT » (2026-09-18) ────────────
    #
    # Mesuré en relisant les champs : **97 des 292 `siblings: swept:` (33 %)**
    # disent, mot pour mot, « son garde PARCOURT l'arbre et a été exécuté ce
    # jour-là, vert ». C'est une RELANCE du prédicat existant, pas une recherche
    # de frères — et ce dépôt a payé trois fois la différence dans la nuit du 17
    # au 18 : `multitenant-dag-fleet-poisoning` avait un garde vert sur **8 sites
    # vivants** ; `test_every_collection_dag_records_its_tenants` n'avait lu aucun
    # `except` en douze jours ; `test_views_render_smoke` restait vert sur le
    # défaut qu'il déclarait couvrir.
    #
    # Compté À PART plutôt qu'en redéfinissant `siblings_swept` : la redéfinition
    # ferait bondir `siblings_never_swept` de 106 à ~203, et le cliquet lirait une
    # RÉGRESSION là où il y a une correction de mesure. Le vrai nombre de classes
    # dont personne n'a cherché les frères est donc la SOMME des deux.
    "swept_by_rerunning_the_guard": 0,
    "scope_on_a_shared_guard_without_naming_its_tests": 15,  # phase C ; 23 → 15 le 2026-09-17
                                      # ⚠️ 9 → 11 le 2026-09-17, et les DEUX de hausse sont
                                      # STRUCTURELS, pas de la négligence : `ci-runs-twice-for-one-commit`
                                      # et `ci-has-no-concurrency-group` partagent
                                      # `.claude/scripts/check_ci_waste.py`, un SCRIPT. Le prédicat
                                      # `_names_a_test` cherche `::test_x` ou un `` `test_x` `` — il est
                                      # de forme pytest et ne peut pas être satisfait par un garde qui
                                      # est un script. Les deux classes SONT pourtant distinguées :
                                      # `analyse()` étiquette chaque constat par son identifiant de
                                      # classe. C'est le prédicat qui ne sait pas le lire, pas la portée
                                      # qui ment. Écrit ici plutôt que contourné en déformant les portées.
                                      #
                                      # ⚠️ ÉTAT AU 2026-09-17, et il faut le lire avant de croire ce
                                      # compteur : **6 des 15 sont structurelles**, soit 40 %. Ce sont
                                      # les classes dont le garde N'EST PAS un fichier pytest —
                                      # `ci-runs-twice-for-one-commit` et `ci-has-no-concurrency-group`
                                      # (un script), `streamlit-pin-drift` et
                                      # `a-major-upgrade-that-moves-a-default` (une étape de workflow),
                                      # `a-procedural-rule-in-the-database` (`audit_runner`),
                                      # `an-action-pin-derived-from-a-version-number` (un outil).
                                      #
                                      # Un compteur dont 40 % ne mesure plus ce qu'il prétend cesse de
                                      # discriminer. Le corriger demande d'accepter un nom d'étape, de
                                      # constat ou de fonction à côté de `::test_x` — chantier nommé.
                                      # Le crânter tel quel est honnête ; s'y fier ne l'est pas.
                                      #
                                      # ⚠️ TROISIÈME cas de la même forme le 2026-09-17 :
                                      # `streamlit-pin-drift` a pour garde une ÉTAPE de
                                      # `.github/workflows/ci.yml`. Nommer l'étape (« manifest
                                      # consistency ») ne satisfait pas davantage un prédicat qui cherche
                                      # `::test_x`. Trois classes sur douze sont donc comptées comme des
                                      # trous pour une raison qui n'est pas la leur — le prédicat suppose
                                      # qu'un garde est un fichier pytest, et trois gardes de ce dépôt
                                      # n'en sont pas. Le corriger demanderait d'accepter aussi un nom
                                      # d'étape ou de constat ; c'est un chantier nommé, pas un oubli.
                                      # ⚠️ 8 → 14 puis 9 le 2026-09-17 : écrire 79 portées a MÉCANIQUEMENT fait
                                      # monter ce compteur, chaque portée neuve sur un garde partagé
                                      # devant nommer ses tests. Le cliquet m'a repris quatre fois
                                      # dans la séance. `est la PREMIERE classe dont les trois preuves sont
                                      # observées le même jour — date vue rouge, cause mesurée,
                                      # portée écrite en lisant le garde. Les trois compteurs
                                      # baissent ensemble, ce qui est le signe recherché.
                                      #
                                      # ⚠️ **15 le 2026-09-17, et les 15 sont STRUCTURELLES** — la
                                      # proportion est passée de 40 % à 100 %, donc ce compteur ne
                                      # mesure plus AUCUNE négligence. Les 24 classes qui restaient
                                      # évitables ont été nommées le même jour ; ce qui subsiste n'a
                                      # aucun nœud pytest à nommer :
                                      #   · `.claude/dev-docs/error-classes.md` (2) — un document
                                      #   · `.claude/scripts/audit_runner.py` (2) — un script
                                      #   · `.claude/scripts/check_ci_waste.py` (2) — un script
                                      #   · `.claude/skills/dashboard-view/SKILL.md` (3) — une skill
                                      #   · `.github/workflows/ci.yml` (4) — des étapes de workflow
                                      #   · `tools/dev/check_action_drift.py` (2) — un outil
                                      # Le crânter à 15 est donc un plancher, pas un objectif : il ne
                                      # peut plus descendre sans ÉLARGIR `_names_a_test` pour accepter
                                      # un nom d'étape, de constat ou de fonction à côté de `::test_x`.
                                      # Tant que ce chantier n'est pas fait, une hausse reste le seul
                                      # signal utile de ce compteur — elle signifie qu'une portée neuve
                                      # sur un garde pytest partagé a oublié de nommer ses tests.
    # Liste de RELECTURE, pas une faute à corriger dans une direction imposée : un
    # désaccord peut venir du garde comme de l'expression de la famille.
    # `scope_family_disagreements` RETIRÉ le 2026-09-16 : 10 désaccords sur 18 portées,
    # presque tous du côté de la dérivation (une regex de mots-clés sur un symptôme).
    # 55 % de faux positifs — un compteur bruyant fait ignorer les vrais. Remplacé par
    # une vérification sans faux positif : la famille déclarée EXISTE-t-elle ?
    "scope_family_invalid": 0,
    "guards_ref_missing": 0,
}
_FLOORS = {
    # Relevés le 2026-09-16 : deux classes écrites AVEC la nouvelle méthode. Un plancher
    # monte quand la population grandit — c'est son sens.
    # +1 au lot 5 : `a-guard-names-a-class-nobody-wrote`, **la première classe du
    # catalogue dont `seen_red` porte une DATE OBSERVÉE** et non un rétro-portage.
    # +1 encore : `a-runbook-that-names-a-command-nobody-can-run`, écrite parce que le
    # garde précédent l'a EXIGÉE — sa docstring annonçait l'identifiant avant qu'il
    # existe. Première fois que la chaîne se referme sans qu'on y pense.
    # +1 encore : `a-shared-database-read-while-another-test-writes-it`, écrite sur
    # DEUX rouges de suite complète le même soir, chacun vert en isolation.
    # +1 : `a-fallback-that-runs-when-the-first-branch-succeeded`, écrite sur MON
    # erreur du soir — un `|| git commit` dont la première branche a réussi, avec le
    # message d'un vieux commit. Livrée `guarded` et non `reported` parce qu'une classe
    # sans garde fait monter DEUX plafonds (`prose_only`, `seen_red_unknown`) : les
    # relever pour sa propre erreur serait la leçon inverse. Elle a une surface réelle,
    # les fichiers versionnés, et son garde y a trouvé un faux positif dès la première
    # exécution.
    # +1 : `a-memo-field-written-and-never-consulted`, trouvee en cherchant AUTRE chose —
    # R121 annoncait `platform_chart` comme meilleur candidat ; le profil dit 1,4 ms
    # pour lui et 12,5 ms pour `config_loader.load()`.
    # +1 : `a-renderer-that-recomputes-what-its-caller-already-has`, DEUX instances
    # dans deux fichiers sans rapport le meme jour — `onboarding_health` (324 → 181
    # requetes) et `db_health` (22 → 11 `fetch_df`).
    # +5 le 2026-09-17 : les cinq classes qu'un garde nommait sans qu'elles existent,
    # ecrites depuis la docstring de leur garde. Les CINQ arrivent avec un `seen_red`
    # DATE — chacune vue rouge par mutation, dont deux avec la valeur fautive d'origine
    # (`_COLUMN_WIDTH_PX = 720`, `noise_tokens` retire de l'appel de production).
    # `seen_red_unknown` ne bouge donc pas : +5 classes, +5 dates observees.
    # +1 : `a-parser-that-knows-one-of-two-syntaxes`.
    # ⚠️ `automatic_guard` fait un BOND de 358 a 367, et ce n'est pas du travail : c'est
    # la correction du parseur. Il ne lisait qu'une des deux syntaxes de `guard:`, donc
    # neuf classes gardees etaient comptees comme non gardees depuis toujours. Le
    # plancher monte parce que la MESURE a change, pas le depot.
    "classes": 379,
    "with_signature": 367,
    "automatic_guard": 368,
}
# Le plancher qui n'a pas d'équivalent dans `gold-coverage`, et le plus important ici :
# un taux s'améliore aussi en RÉTRÉCISSANT la fenêtre d'observation.
_EXPOSURE_FLOOR = 7628


def _payload() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


# LA FRAÎCHEUR DE L'INSTANTANÉ EST VÉRIFIÉE EN CI, PLUS DANS LA SUITE — 2026-09-18.
#
# `test_the_snapshot_still_describes_the_catalogue` vivait ici et coûtait **6,97 s** :
# il appelait `_fresh()`, donc `build()`, donc **330 `git show`** à chaque exécution
# locale. Les six autres tests de ce fichier lisent le JSON sur disque ; le plus cher
# coûte 0,19 s.
#
# `make error-health-check` fait exactement cela et n'était lancé par aucun workflow.
# La propriété vit désormais dans `.github/workflows/ci.yml`.
#
# ⚠️ Ce test avait une seconde conséquence, invisible tant qu'on le lisait comme un
# simple contrôle : c'est LUI qui forçait le cycle « commiter le catalogue → régénérer
# → recommiter ». `build()` lit `git log -- error-classes.md`, donc commiter change
# l'instantané, et l'égalité octet à octet exigeait alors un second commit. **50 des
# 104 commits du 2026-09-18 étaient ce second commit.**
#
# Ce qui reste ici : les cliquets, qui n'ont pas besoin de git.


def test_no_hole_counter_ever_grows() -> None:
    holes = _payload()["aggregate"]["holes"]
    grown = {k: (holes.get(k, 0), c) for k, c in _CEILINGS.items() if holes.get(k, 0) > c}
    assert not grown, (
        "compteur(s) de trou en hausse (mesure, plafond) : " + repr(grown)
        + "\n\nUn trou est une classe dont la connaissance est INVÉRIFIABLE : signature "
          "jamais vue rouge, cause non établie, portée du garde non nommée. C'est cela "
          "qui est cranté — pas le taux de récidive, qui monte et dont un cliquet serait "
          "rouge à l'écriture.")


def test_the_ceiling_is_not_slack() -> None:
    """Un plafond au-dessus de la mesure est du budget pour régresser en silence.

    C'est la discipline qui fait fonctionner `gold-coverage` : le plafond ÉGALE la
    mesure, et resserrer fait partie du commit qui améliore.
    """
    holes = _payload()["aggregate"]["holes"]
    slack = {k: (holes.get(k, 0), c) for k, c in _CEILINGS.items() if holes.get(k, 0) < c}
    assert not slack, (
        "plafond(s) plus haut que la mesure (mesure, plafond) : " + repr(slack)
        + "\n\nLe baisser DANS LE MÊME COMMIT que l'amélioration, sinon le budget "
          "reste ouvert et la prochaine régression passe sans rougir.")


def test_the_population_did_not_shrink() -> None:
    agg = _payload()["aggregate"]
    pop = agg["population"]
    shrunk = {k: (pop.get(k, 0), f) for k, f in _FLOORS.items() if pop.get(k, 0) < f}
    assert not shrunk, (
        "population en baisse (mesure, plancher) : " + repr(shrunk)
        + "\n\nUn compteur de trous s'améliore aussi en SUPPRIMANT des classes. Le "
          "plancher est ce qui distingue « on a corrigé » de « on a effacé ». Si une "
          "classe devait vraiment disparaître, baisser le plancher DANS LE MÊME COMMIT, "
          "avec la raison.")
    exposed = agg["recurrence"].get("class_days_exposed", 0)
    assert exposed >= _EXPOSURE_FLOOR, (
        f"fenêtre d'observation rétrécie : {exposed} classe-jours contre un plancher de "
        f"{_EXPOSURE_FLOOR}. Un taux d'évènements par classe-mois s'améliore en "
        "raccourcissant la fenêtre aussi sûrement qu'en corrigeant des défauts.")


def test_a_falling_rate_is_not_a_ratchet() -> None:
    """Le NON-test délibéré. Il documente ce qu'on refuse de cranter, et pourquoi.

    Il vérifie seulement que le taux est PUBLIÉ avec son intervalle. Cranter sa baisse
    serait rouge à l'écriture : normalisé par l'exposition, il monte.
    """
    rec = _payload()["aggregate"]["recurrence"]
    obs = rec.get("observed") or {}
    assert obs.get("per_class_month") is not None, (
        "le taux observé n'est plus publié — sans lui, les strates ne se lisent pas")
    assert obs.get("ci95"), (
        "le taux est publié SANS intervalle. Les sous-groupes portent 8 à 47 "
        "évènements : un écart de facteur 5 peut n'être que du bruit, et seul "
        "l'intervalle le dit.")
    for key in ("by_guard", "by_seen_red", "by_scope"):
        assert key in rec, f"la strate `{key}` a disparu — c'est elle qui répond à la question posée"


def test_the_two_readers_of_the_catalogue_agree() -> None:
    """Deux cliquets sur une même population ne doivent pas dériver."""
    sys.path.insert(0, str(_ROOT / ".claude" / "scripts"))
    import audit_runner

    text = (_ROOT / ".claude" / "dev-docs" / "error-classes.md").read_text(encoding="utf-8")
    theirs = {c["id"] for c in audit_runner.parse_all_headers(text)}
    mine = set(_payload()["classes"])
    assert mine == theirs, (
        f"les deux lecteurs du catalogue ne voient pas les mêmes classes : "
        f"{sorted(mine ^ theirs)[:8]}. Deux parseurs d'un même fichier qui divergent, "
        "c'est une grandeur avec deux définitions.")

    from tests.test_a_class_binds_or_it_is_only_prose import _classes, _is_automatic
    prose_other = sum(1 for _, g in _classes() if not _is_automatic(g))
    assert _payload()["aggregate"]["population"]["prose_only"] == prose_other, (
        "le compte de classes « prose seule » diffère entre ce cliquet et "
        "`test_a_class_binds_or_it_is_only_prose.py`.")


def test_the_scan_is_not_vacuous() -> None:
    """Sans ça, un parseur cassé rendrait tous les tests ci-dessus verts à vide."""
    p = _payload()
    assert len(p["classes"]) >= 300, (
        f"{len(p['classes'])} classes lues — la lecture est cassée, et « zéro trou » "
        "sur zéro classe est vrai sans rien dire.")
    agg = p["aggregate"]
    assert agg["recurrence"].get("window_start"), "aucune fenêtre d'observation"
    assert agg["generated_from"]["catalogue_revisions"] >= 100, (
        "moins de 100 révisions rejouées : le rejeu git ne trouve plus l'historique du "
        "catalogue, donc la récidive OBSERVÉE serait nulle par construction.")
    assert agg["population"]["ever_recurred_observed"] >= 1, (
        "aucune récidive observée sur tout l'historique : le détecteur ne détecte plus.")


def test_the_sweep_verdict_is_the_first_bold_count_not_the_nearest_zero() -> None:
    """La prose qui RÉTRACTE un zéro ne doit pas faire rapporter zéro.

    Mesuré le 2026-09-18. `_swept_sites` cherchait `**0 site vivant**` dans TOUT le
    champ, et avant le compte. Une classe qui publiait six sites vivants puis racontait
    qu'un prédicat fautif avait « rendu **0 site vivant** » se voyait attribuer **0** :
    l'instrument lisait la rétractation au lieu du résultat.

    C'est `guard-satisfied-by-its-own-comment` appliqué à un COMPTEUR — écrire sur le
    défaut change la mesure — et c'est la deuxième fois de la journée que cette forme
    mord, la première étant deux gardes rougis par un commentaire expliquant leur
    propre correctif.
    """
    from tools.dev.error_class_health import _swept_sites

    cas = [
        ("swept: **6 sites vivants**, et un prédicat rendait **0 site vivant**", 6),
        ("swept: **0 site vivant**, vérifié", 0),
        ("swept: **1 site vivant**", 1),
        ("swept: **0 site vivant**, puis **3 sites vivants** plus loin", 0),
        ("swept: aucune forme en gras", None),
        ("pas un balayage", None),
    ]
    faux = [(c, _swept_sites(c), a) for c, a in cas if _swept_sites(c) != a]
    assert not faux, (
        "le verdict de balayage n'est plus la PREMIÈRE forme en gras : "
        f"{[(c[:50], got, att) for c, got, att in faux]}")
