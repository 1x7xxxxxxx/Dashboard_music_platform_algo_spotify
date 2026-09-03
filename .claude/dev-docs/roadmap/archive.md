# Roadmap — archive

Briques et bugs **livrés ou clos**. Fichier passif : rien ici n'est actionnable.
L'actif est `.claude/dev-docs/roadmap/checklist.md`.

Rotation actif → archive : `Spawn roadmap-keeper` (CLAUDE.md règle 17). Un item se
**déplace**, il ne se duplique ni ne s'efface — `tests/test_roadmap_two_files.py`
échoue si le total des deux fichiers change.

---

<!-- section actif : Open Bugs -->

### R50 · R51 · R52 — Les notes des tests artistes, livrées (clos 2026-08-23)

Trois tracks du plan de simplification UI/UX. Le fil commun n'était pas prévu et mérite
d'être gardé : **la plupart des défauts n'étaient pas du code faux, mais du code correct
que rien n'atteignait.**

- [x] **R50 — le produit savait où l'artiste devait aller, le disait, et ne l'y emmenait
  pas.** La page d'onboarding n'était dans aucune navigation (joignable seulement depuis
  l'e-mail de vérification — mail fermé, page disparue) ; les quatre étapes de l'accueil
  nommaient leur destination sans y mener ; les guides d'API lus pendant les tests étaient
  **du code mort** (180 lignes + 36 traductions) qui **contredisait** les guides vivants ;
  le guide anglais, lui, était vivant et périmé, expédié dans le PDF avec
  `http://127.0.0.1:8888/callback` — un `8888` hérité du défaut de `spotipy`, décliné en
  trois orthographes, dont la forme `localhost` que Spotify refuse désormais ; et le
  sélecteur Mac/Windows était branché sur une fonction sans appelant.
  Plus : guide replié par étapes, définitions CSV remontées, liens plateformes rendus
  visibles à l'artiste (ils vivaient sur une page **réservée admin**), PDF des identifiants
  téléchargeable (il n'existait qu'en pièce jointe), `soundcloud:users` mis en évidence, et
  « clé API pas valide » qui dit enfin **qui** doit agir — la clé est celle de l'admin,
  l'artiste n'a rien à corriger.

- [x] **R51 — le correctif contre le mur de graphiques existait depuis onze jours,
  branché nulle part.** `secondary_analyses()` a été écrit le 2026-08-12, le jour même de
  la remarque, avec elle citée dans son commentaire de module — et n'était appliqué sur
  **aucune** des cinq vues les plus denses. Douze figures repliées ; un garde compte
  désormais les graphiques du PREMIER ÉCRAN et plafonne à 5 par fichier. Les exports, qui
  étaient les entrées n°2 et n°3 du menu, sont descendus après les analytics.

- [x] **R52 — GRiNCH et Benj débloqués.** Un artiste signé sur un label n'était jamais
  collecté : le DAG le sautait dès que `user_id` était vide, **avant** de lire ses titres
  déclarés, et le collecteur levait sur le même critère — alors que la fonctionnalité
  existait en entier. Côté CSV, le séparateur `;` (celui d'Excel en configuration
  française) n'était pas testé, et l'export « Depuis le début » était détecté puis rejeté
  trois couches plus bas avec un conseil — renommer le fichier — qui ne corrige rien.

Sept classes d'erreur cataloguées, chaque garde vu rouge sur son défaut réel. Deux d'entre
eux avaient un prédicat trop lâche, démasqué par la mutation seule.

---


### Track 1 des notes artistes — les trois faux verts (clos 2026-08-23)

Premier lot du plan de simplification UI/UX. Trois messages qui annonçaient un état qu'ils
ne mesuraient pas — ce qui fait perdre confiance en l'outil bien plus vite qu'une page
laide.

- [x] **Le PDF disait « configuré » à partir du `.env` de l'admin.** Enquête partie d'une
  hypothèse **fausse** : je pensais que la matrice à l'écran confondait admin et artiste.
  Elle est correcte — elle passe par `artist_readiness` → `tenant_identity`, où un `.env`
  admin ne peut rien rendre vert. C'est la surface **imprimée**, celle que l'artiste garde,
  qui mentait : `_collect_credentials_status` recalculait `(key in have) or
  app_level_configured(key)`, soit deux faux verts indépendants — une ligne en base créée
  par un onglet enregistré vide, et l'environnement de l'administrateur. Le PDF lit
  désormais la même source que l'écran. Classe `two-surfaces-two-truths`.

- [x] **« Lancé ! » s'affichait même quand les sept déclenchements avaient échoué.** Chaque
  itération était soigneusement testée ; la conclusion, elle, vivait hors de toute condition
  de résultat. Sept ❌ puis « Lancé ! » — et c'est le dernier message que l'artiste retient.
  Conditionné, avec une branche d'échec explicite : conditionner le succès sans dire l'échec
  aurait remplacé un faux vert par un silence. Classe
  `success-message-outside-its-condition`. **Le premier prédicat du garde était vert sur le
  défaut** — le message fautif vivait déjà sous le `if` du bouton. Être sous une condition ne
  suffit pas : il faut être sous **la condition qui teste ce qu'on annonce**. Septième fois
  que le prédicat d'un garde vise le symptôme au lieu de la question, et seule la mutation
  l'a dit.

- [x] **Deux verts de la matrice ne voulaient pas dire ce qu'on croyait.** « Répond »
  affichait ✅ vert et « Des données arrivent » pour une source `stale` — morte depuis des
  mois — et « Données » affichait vert pour `quiet`, c'est-à-dire **zéro ligne**. Les deux
  états sont légitimes ; c'est le verbe au présent et la couleur qui mentaient. L'icône
  portait déjà la nuance (`⏸️`, `🟡`) et la couleur la niait. Comportement inchangé,
  honnêteté rétablie.

  Au passage : `st.error(f"❌ {label} — {e}")` rendait l'**exception brute à l'artiste** dans
  le panneau de collecte, et `src/dashboard/app.py` n'est dans la portée d'aucun garde
  anti-fuite. Rédigé par `safe_error`.

Vérifié : 1859 passed / 22 skipped, ruff propre, 110 classes 0 non gardée. Chaque garde vu
rouge sur le défaut réel avant correctif.

---


### R38 — Le nom d'expéditeur venait du code, pas de Brevo (clos 2026-08-23)

- [x] **R38 — corrigé en code, alors qu'il était parqué comme « aucune ligne de Python
  ne peut le corriger ».** La roadmap tenait pour acquis que le nom venait du compte
  Brevo. Deux mesures l'ont démenti :

  1. **`config/config.yaml` porte littéralement le nom observé** — `smtp.from_name:
     'Music Cross Platform Dashboard & Trigger Spotify'`. C'est le repli que le code lit
     **avant** son défaut `streaMLytics` : un repli intermédiaire renseigné n'atteint
     jamais le défaut. Personne n'avait ouvert ce fichier.
  2. **`email_alerts.py` n'utilisait aucun nom** : `msg['From'] = self.smtp_user`, soit
     l'identifiant de connexion au relais (`ae8df8001@smtp-brevo.com` en prod) au lieu de
     `noreply@streamlytics.fr`. Toutes les alertes de DAG, le résumé quotidien et le
     rapport d'onboarding partaient ainsi ; Brevo, qui exige un expéditeur validé, y
     substituait l'expéditeur par défaut du compte.

  On avait regardé `verification_email.py` — le chemin qui marchait.

  Fix : `src/utils/email_identity.from_header()` est la seule composition de l'en-tête,
  les 4 sites y passent, `config.yaml` corrigé, `config.example.yaml` documenté avec la
  raison. Garde AST `tests/test_every_mail_says_who_it_is_from.py`, vu rouge sur les
  4 sites d'avant le fix. Classe `sender-identity-composed-twice`.

  **Six fuites de credentials trouvées au passage.** En élargissant le prédicat du garde
  `secret-in-an-exception-message` à la 4ᵉ forme — l'exception passée en ARGUMENT de
  logger, `logger.error("… %s", e)`, que ni `str(e)` ni `f"{e}"` n'attrapaient — il a
  sorti `alert_monitor.py` (3 sites), `onboarding_report.py` (2) et
  `soundcloud_api_collector.py` (1, dans le rafraîchissement OAuth, où l'exception peut
  porter le jeton). Quatrième élargissement de ce garde, quatrième fois qu'il trouve.

---


### R46 — `data_quality_check` : tranché par l'exécution, reste en pause (clos 2026-08-23)

- [x] **R46 — lancé une fois à la main en production, et la décision est mesurée.**
  Le circuit breaker de R42 fonctionne : `⏸️ Circuit ouvert — donnée S4A périmée de 77 j
  (dernier jour porté : 2026-06-07)`. Restait la vraie question — dépauser ou non — et
  trois mesures y répondent :

  | Question | Mesure du 2026-08-23 |
  |---|---|
  | Depuis quand la source est muette ? | dernière écriture **2026-06-08**, dernier jour porté **2026-06-07** — les deux s'accordent |
  | Qui a déjà déposé un CSV S4A ? | **le seul locataire 1 (admin)**, 13 794 lignes. Ni Benken, ni GRiNCH, ni le canari |
  | La flotte est-elle aveugle à cette péremption ? | **non** — `freshness_monitor` la signale déjà : `stale: True`, `age_h: 1867`, `measured_on: 'metric'` |

  **Décision : rester en pause**, et ce n'est plus une précaution. Dépausé, il
  s'abstiendrait chaque nuit — la seule chose qu'il puisse faire sur une source muette —
  et enverrait un second e-mail quotidien à côté de l'alerte consolidée, sans un constat
  neuf. **ADR-011** l'interdit : une alerte nomme un symptôme visible par l'artiste ET
  une action possible ; celui-ci n'en nomme aucun.

  **Déclencheur de réouverture, formulé pour pouvoir se produire** : le jour où
  `freshness_monitor` cesse de marquer « Spotify S4A » comme `stale`, relancer le DAG à
  la main. Ses cinq contrôles restent la seule implémentation d'Accuracy et de
  Completeness du dépôt — ils n'ont simplement jamais eu de données fraîches à juger.
  Détail complet : `.claude/dev-docs/data-quality-check-verdict.md`.

  Appris en le lançant : `airflow dags test` **exécute réellement** la tâche de
  notification — le test manuel a envoyé un vrai e-mail de résumé.

---


### R45 — Le livre scanné du corpus rend enfin ses pages (clos 2026-08-23)

Fermé le soir même. Le pipeline avait raison de refuser d'indexer des miettes — 512
« pages » pour 10 mots — et tort de croire qu'aucun traitement n'existait : le
commentaire disait vrai d'`ocrmypdf`, qui ne lit que le PDF, et faux de l'OCR.
**tesseract**, qu'`ocrmypdf` appelle lui-même, lit un JPG sans difficulté ; le livre est
fait de 511 JPG pleine page. `ocr_epub()` écrit le chemin manquant, avec cache par
fichier (13 minutes de reconnaissance qu'une ré-ingestion ne repaie pas).

**2 865 passages là où il y en avait 0.** Plus aucun livre à zéro passage dans le
corpus ; 174 984 passages au total.

Deux choses trouvées en le fermant, toutes deux dans `knowledge-rag` :
`FAILED` est un statut **terminal**, donc l'échec transitoire d'un incident antérieur
empêchait toute nouvelle tentative — il a fallu purger l'entrée d'état à la main ; et
`--allow-ocr` est opt-in avec une aide qui ne parlait que des PDF.


*Next-Gen Chatbots RAG — Autonomous Agents with LangChain*, EPUB de 86 Mo, échoue à
**chaque** ingestion depuis son dépôt : 512 « pages » pour 512 mots. C'est un livre en
images et le pipeline n'a pas de chemin OCR pour l'EPUB (`ocrmypdf` ne traite que le PDF).

- [x] **R45** — soit extraire les images de l'EPUB et les passer à l'OCR existant, soit
      convertir l'EPUB en PDF pour réutiliser le chemin `NEEDS_OCR` déjà en place, soit
      retirer le livre en le disant. Vérif : `tools/check_index_coverage.py` ne doit plus
      lister aucun livre à 0 passage.

---


---

### R39–R44 — Le corpus relu contre le dépôt, six écarts fermés (clos 2026-08-23)

Ouverts le matin par la confrontation des dix livres ingérés au code réel, fermés
le soir. Chaque seuil est mesuré sur la vraie prod, chaque garde a été vu rouge par
mutation. Détail, citations et vérifications ci-dessous — conservés parce que c'est
le raisonnement, pas le résultat, qui sert la prochaine fois.


Dix livres ingérés ce jour. Cette section ne résume pas les livres : elle ne garde que
les endroits où **le livre et le dépôt se contredisent**, avec la citation, l'écart
mesuré et le geste qui le ferme. Ce qui coïncide déjà n'y figure pas.

### L'état du corpus lui-même, après réparation

L'ingestion est complète (**197 fichiers, 27 domaines**), mais la revue a trouvé quatre
défauts que la sortie « ✅ Couverture complète » cachait :

1. **`saas-architecture` n'existait pas dans l'index.** `list_books("saas-architecture")`
   répondait « aucun livre indexé » pendant que *Building Multi-Tenant SaaS Architectures*
   y était bien, sous `divers`, avec 3 605 passages. Cause : `ingest.py` prend le domaine
   du **nom du dossier** (`common.book_domain`), pas des règles de `organize.py` — un
   livre rangé à la main APRÈS son ingestion garde son ancien domaine. Or la description
   de `search_books` chiffre l'enjeu : avec `domain`, recall@5 = 90 % ; sans, 60 %. Le
   livre le plus pertinent pour ce dépôt était donc inatteignable par le seul filtre qui
   marche.
2. **`ingest_state.json` est clé par NOM DE FICHIER**, sans le domaine. Un même fichier
   présent dans deux dossiers est ingéré une fois, avec le domaine du dossier vu en
   premier — d'où un lot à moitié classé, ce qui ne se lit pas comme un défaut.
3. **5 963 passages dupliqués** (Alice and Bob en **trois** exemplaires, Storytelling et
   IndOS en deux) se disputaient les places du top-k.
4. **Un livre rend 0 passage** — *Next-Gen Chatbots RAG … LangChain*, EPUB de 86 Mo :
   512 « pages » pour 512 mots, c'est un livre en images, et `ocrmypdf` ne traite pas
   l'EPUB. Il est listé par `list_books()` et introuvable par `search_books()`.

Réparé le jour même : deux règles de classement ajoutées (`qualite-logicielle`,
`saas-architecture`) plus `data observability` / `data quality` sur `data-eng` ; les
doublons retirés de l'index **et** du disque ; les mal-étiquetés réétiquetés en place
(mêmes vecteurs, pas de ré-embedding) ; index FTS + IVF_FLAT reconstruits ; un livre
jamais classé depuis le 2026-07-28 (*Agents IA pour les nuls*) enfin ingéré.
`check_index_coverage.py` ne peut plus imprimer « Couverture complète » tant qu'un livre
pèse 0 passage. Le test `test_organize_covers_domains.py` **disait déjà tout ça** — il
était rouge et n'avait jamais été lancé.

### R39 — Le pilier Volume n'est surveillé que dans un sens · P2

> « The five pillars of data observability : **Freshness · Distribution · Volume ·
> Schema · Lineage**. Volume — *Has all the data arrived?* »
> — Moses, Gavish, Vorwerck, *Data Quality Fundamentals*, p.144

Confrontation, pilier par pilier, avec ce que `alert_monitor.py` fait réellement :

| Pilier | Dans le dépôt | Verdict |
|---|---|---|
| Freshness | `check_data_freshness` + `etl_run_log` + `stale` | ✅ complet |
| Volume | `check_row_anomalies` | ⚠️ **un seul sens** |
| Distribution | `check_drift_anomalies` | ⚠️ features **ML** seulement, pas la donnée collectée |
| Schema | `notify_schema_drift.py` (cron 04h) | ✅ |
| Lineage | — | ❌ absent (→ R44) |

L'écart mesuré est dans le docstring de `check_row_anomalies` lui-même : il ne détecte
que le **spike** (> 10× la moyenne 7 j) et délègue l'autre sens à la fraîcheur —
« freshness already covers the opposite (no recent data) ». C'est vrai de *zéro* ligne,
faux de *trop peu* : une collecte récente et partielle (3 titres sur 40) ne déclenche ni
l'un ni l'autre. Ce dépôt a déjà vécu exactement ce cas — SoundCloud « ✅ sur 0 titre »
au test GRiNCH, chaîne YouTube vide chez Benken — et l'a chaque fois découvert par un
humain.

- [x] **R39** — sous-volume par locataire × plateforme dans `check_row_anomalies` : ratio
      au 7 j glissant **et** plancher absolu, symétrique du spike. Vérif : tronquer la
      dernière collecte d'un locataire en base et voir l'alerte rougir (mutation), puis
      revenir au vert.

### R40 — Le filtrage par locataire dans la requête n'est pas l'isolation · P1

> « It's easy to assume that, if we're filtering these queries by tenant, then you've put
> all the measures in place to ensure that one tenant can't access the data of another
> tenant. And, in theory, it's not an unreasonable expectation. **However**… »
> — Golding, *Building Multi-Tenant SaaS Architectures*, p.204

Golding sépare deux choses que ce dépôt traite comme une seule : le **partitionnement**
(ch. 8 — où la donnée vit) et l'**isolation** (ch. 9 — ce qui empêche l'accès croisé),
et prescrit de « **Hiding Away and Centralizing Multi-Tenant Details** » derrière une
couche d'interception plutôt que de compter sur la discipline de chaque requête.

C'est le diagnostic exact de la fuite `track_popularity_history` (tous les locataires
écrits sous l'admin pendant des mois), et le dépôt a déjà la bonne réponse — mais à
moitié : `view_session()` EST cette couche d'interception, et la règle transverse #7
reconnaît que des vues sont encore sur le garde manuel. Tant qu'un second chemin existe,
la centralisation n'en est pas une.

- [x] **R40** — inventorier les vues encore sur le garde manuel `get_artist_id()`, les
      migrer sur `view_session()`, puis rendre le contournement **impossible** : un test
      AST qui refuse tout appel à `get_artist_id()` hors du gestionnaire de contexte.
      Vérif : `python3 .claude/scripts/audit_tenant_writes.py` + le test AST vu rouge sur
      une vue volontairement rétrogradée.

### R41 — Le HTTP réel n'est borné nulle part dans la suite · P2

> « Communications with **unmanaged** dependencies are part of your system's observable
> behavior. Such dependencies should be mocked out. » — et symétriquement, ne pas mocker
> les dépendances **managed** (la base).
> — Khorikov, *Unit Testing Principles, Practices, and Patterns*, p.213 et p.221

C'est la formulation exacte de la ligne que ce dépôt suit à moitié, et le livre nomme
les deux moitiés :

| Dépendance | Nature (Khorikov) | Ce que fait le dépôt |
|---|---|---|
| Postgres | *managed* — ne pas mocker | ✅ base réelle, ~160 tests l'exigent |
| SMTP | *unmanaged* — mocker | ✅ **depuis le 2026-08-23** (`_no_real_smtp`) |
| APIs plateformes (HTTP) | *unmanaged* — mocker | ❌ **rien** |

Le défaut SMTP corrigé ce jour n'était donc pas un accident isolé : c'était la première
manifestation visible d'une frontière qui n'existe pas. Elle est visible parce qu'un mail
arrive dans une boîte ; un appel HTTP réel vers l'API d'une plateforme ne laisse aucune
trace côté opérateur — il consomme du quota, peut écrire, et échoue en CI sans réseau.

- [x] **R41** — frontière `requests` / `httpx` dans `tests/conftest.py`, sur le modèle
      exact de `_no_real_smtp` : **enregistrer puis échouer au teardown**, parce que les
      collecteurs enveloppent leurs appels dans `except` et avaleraient une exception
      seule. Prévoir l'opt-in pour les tests qui exercent vraiment le client. Vérif :
      signature dédiée qui déclenche la frontière exprès, vue rouge par mutation.

### R42 — `data_quality_check` : le corpus donne la forme du déblocage · P3

> « Using circuit breakers requires three core solutions : **data lineage**, **data
> profiling across the pipeline**, **ability to automatically trigger the circuit** via
> issues unearthed through profiling. » — Moses et al., p.86

Le verdict local (`.claude/dev-docs/data-quality-check-verdict.md`) garde ce DAG en pause
parce que sa sonde Meta passerait au vert sur la source la plus périmée de la prod.
Moses explique **pourquoi** c'est structurel et pas un bug de sonde : Freshness et
Distribution sont deux piliers **distincts**, et un contrôle de distribution qui ne
s'appuie pas sur un contrôle de fraîcheur mesure la forme de données mortes.

- [x] **R42** — conditionner tout contrôle de distribution à un contrôle de fraîcheur qui
      passe (circuit breaker) avant de sortir `data_quality_check` de pause. Vérif : la
      sonde Meta doit rester **rouge ou muette** sur une source périmée, jamais verte —
      c'est précisément ce que le verdict lui reprochait.

### R43 — La politique d'alerte du dépôt est adossée à deux sources · P4 (fait, à consigner)

> « Alerting has shifted to a model in which fewer alerts are triggered, by focusing only
> on **symptoms that directly impact user experience**. »
> — Majors, Fong-Jones et al., *Observability Engineering*, p.61
> « All paging alerts should also be **actionable**. Low-priority alerts … disrupt
> productivity, and the fatigue such alerts induce … »
> — Beyer et al., *Site Reliability Engineering*, p.156

Les trois suppressions d'alerte décidées le 2026-08-23 (« rendre les nuits calmes ») ont
été prises sur mesure, sans référence. Elles sont exactement ce que les deux sources
prescrivent. Rien à changer dans le code — mais une décision non sourcée se re-litige.

- [x] **R43** — consigner dans un ADR que la règle d'alerte est « symptôme visible par
      l'artiste **et** action possible », en citant les deux passages ci-dessus.

### R44 — Le pilier Lineage est absent · P4

Aucun équivalent dans le dépôt : rien ne dit quelle table dérive de quelle collecte, donc
une anomalie ne remonte pas à sa source. Moses en fait la première des trois conditions
du circuit breaker (p.86), ce qui lie R44 à R42.

- [x] **R44** — trancher par ADR : soit le lineage est hors sujet à cette échelle (et on
      le dit, comme ADR-007 l'a fait pour la performance), soit R42 en dépend et il entre
      au plan. Ne pas le laisser implicite.


---

### R17 — Corpus ergonomie / front-end ingéré dans knowledge-rag (clos 2026-08-22)

- [x] **R17 — 10 ouvrages d'ergonomie indexés**, domaine `ux-frontend`.
  About Face · Don't Make Me Think · Information Dashboard Design (Few) ·
  Show Me the Numbers (Few) · Storytelling with Data · Data Visualisation (Kirk) ·
  Designing with the Mind in Mind · Microcopy · Strategic Writing for UX ·
  Web Form Design. **180 fichiers sur 25 domaines, couverture complète**
  (`/home/timothe/knowledge-rag/tools/check_index_coverage.py` sort 0).

  Ce que R17 bloquait est désormais sourçable : Few p.27 donne le critère du budget
  de graphiques — *« A dashboard fits on a single computer screen … within the
  viewer's eye span »*. Le critère n'est donc PAS un nombre de graphiques mais le
  coup d'œil, ce qui reclasse `trigger_algo` (15 graphiques, 5× la médiane) comme
  candidat n°1 sans avoir besoin d'inventer un seuil.

  Deux défauts trouvés en le fermant, tous deux dans `knowledge-rag` :
  neuf des dix livres étaient sur le disque depuis la veille **sans être indexés**,
  et rien ne pouvait le dire (`corpus-deposited-but-never-indexed`) ; et
  `organize.py` ignorait le domaine, classant les dix en `divers`
  (`domain-exists-but-classifier-ignores-it`) — au passage, `admin-assurances` et
  `admin-fiscalite` n'avaient eux non plus aucune règle, ce qui est une fuite de
  confidentialité et pas un défaut de rangement.

  L'ingestion est désormais **automatique** : `tools/run_book_drop.sh` en cron
  horaire + rattrapage au redémarrage, avec verrou (un gros PDF prend ~25 min, une
  passe horaire chevaucherait la précédente).


### P1 — Blocking (data missing or crash)

- [x] **SoundCloud + Instagram DAGs** — fixed 2026-03-30.
  SoundCloud: infinite pagination loop (manual offset ignored `next_href`) → cursor-based pagination + `max_pages=200` cap.
  Instagram: Meta API v18.0 deprecated Sept 2025 → centralized to `META_GRAPH_BASE_URL` (v24.0) via `src/utils/meta_config.py`; fresh personal token with ~56 days validity entered via Credentials page.
- [x] **`meta_campaigns` schema incomplete** — DB has 5 columns, `meta_ads_schema.py` expects 11.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **DAG health audit** — completed 2026-03-23. Summary:
  | DAG | Schedule | Last run | State | Note |
  |-----|----------|----------|-------|------|
  | apple_music_csv_watcher | 15min | 2026-03-23 | ✅ success | No CSVs to process |
  | data_quality_check | daily 22h | 2026-03-21 | ⚠️ partial | `check_meta_ads_freshness` fails → empty meta_campaigns |
  | instagram_daily | daily 10h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | meta_csv_watcher_config | 5min | 2025-12-08 | ✅ last was ok | Not collecting (no new CSV files in watch dir) |
  | meta_insights_watcher | 5min | 2025-12-09 | ✅ last was ok | Same — idle since Dec 2025 |
  | ml_scoring_daily | daily 6h | — | ❌ paused | `dbname` bug fixed; unpause via UI |
  | s4a_csv_watcher | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | soundcloud_daily | daily 9h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | spotify_api_daily | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | youtube_daily | manual only | 2025-11-30 | ✅ success | schedule_interval=None, manual trigger needed |

<!-- section actif : Open Bugs -->
### P2 — Data Integrity

- [x] **`meta_insights` UNIQUE(ad_id, date)** — missing `artist_id` → collision risk between artists.
  Fix: applied in `migrations/002_schema_fixes.sql`; DAG and view queries already filter by `artist_id`.
- [x] **`apple_songs_history` no `artist_id`** — data shared across all artists.
  Fix: migration in `migrations/002_schema_fixes.sql`; table added to `apple_music_csv_schema.py`; DAG and view queries updated.
- [x] **`meta_x_spotify.py` autocommit bypass** — lines 38–44 use `db.conn.cursor()` + `db.conn.commit()`.
  Fix: replace with `db.execute_query()` calls.
- [x] **`s4a_song_timeline` null artist_id** — rows created before migration may have `artist_id IS NULL`.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **`ml_scoring_daily` DAG paused** — ML scoring not running automatically.
  Fix: `dbname` → `database` typo in DAG fixed. 16 `.ubj` model files confirmed present. Unpause via Airflow UI (http://localhost:8080).
- [x] **CSV import — validation before upsert** — `upload_csv.py` watcher inserts files without feedback or `artist_id` check.
  Fix: add pre-upsert validation step: row count, expected column names, detected/prompted `artist_id`; surface result in UI before writing to DB.
- [x] **PostgreSQL schema coherence audit** — completed 2026-03-23. 5 errors fixed:
  - `hypeddit.py`, `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_csv_watcher.py`, `meta_insight_watcher.py` — all `db.conn.commit()/rollback()` calls removed (ProgrammingError with autocommit=True).
  - `hypeddit_schema.py` — 5 indexes missing IF NOT EXISTS, fixed.
  - `spotify_s4a_combined.py` — freshness query now filtered by artist_id.
  - `pdf_exporter.py` — 4 song-level queries now include 1x7 filter.
  Remaining warnings (non-blocking): youtube_channel_history/video_stats no UNIQUE, bootstrap gap (24 tables not in init_db.sql), provide_context deprecation in data_quality_check.
- [x] **Release-date filter standardized across all views** — filter by earliest release date (`MIN(date)`) is implemented on S4A/Apple/SoundCloud/Meta but missing on YouTube and inconsistent elsewhere.
  Fix: apply the same `track`/`song` release-date filter in all views; extends the YouTube-specific item (moved from P3).

<!-- section actif : Open Bugs -->
### P3 — UX / Features

- [x] **SHAP/LIME explanations + marketing levers** — `trigger_algo.py` shows raw feature JSON but no SHAP values. Extend: display SHAP feature importances for the most recent track with marketing interpretation labels ("Increase saves", "Boost week-1 streams", etc.).
- [x] **`data_quality_check` DAG** — last run Dec 2025, status unknown. Verify if failing or just not scheduled.
- [x] **User onboarding doc (PDF)** — extend to a printable PDF checklist: run Docker, launch Streamlit, connect credentials, trigger a DAG, upload a CSV, read KPIs. Deliverable: PDF exportable from the app or standalone file.
- [x] **DAG run log dashboard** — dedicated view listing last run per DAG: status, duration, rows inserted, email alert on failure. Distinct from existing failure-callback emails (Brick 11).
- [x] **Budget tracker in trigger_algo** — in `trigger_algo.py`, show estimated cost per playlist submission (Groover/Fluence rates) and remaining budget from a value stored in DB or entered by user.
- [x] **Rename "iMusician" → "Distributeur" in UI** — update nav menu labels, page titles, and UI strings in `imusician.py` / `imusician_schema.py`. Do not rename DB tables or files (would be a regression).
- [x] **View optimization audit** — review all views for N+1 queries, deprecated `use_container_width` calls, unused columns, unnecessary re-renders.
  Action: run `/review-architecture`.

<!-- section actif : Open Bugs -->
### P4 — Tech Debt

- [x] **`PostgresHandler` accept `DATABASE_URL`** — prerequisite for Railway deployment (Brick 15).
- [x] **`.github/workflows/ci.yml`** — ruff + pytest in CI (~20 lines).
- [x] **Tests for `csv_exporter.py`** — mock `db.fetch_df`, verify ZIP contains correct files.
- [x] **Export CSV: table selection** — allow checking/unchecking sources before ZIP download.
- [x] **Remove stale SQL views** — `view_soundcloud_latest`, `view_instagram_latest` replaced by DISTINCT ON in Python. DROP applied in `migrations/002_schema_fixes.sql`.
- [x] **`use_container_width` audit** — check `meta_ads_overview.py`, `instagram.py`, `youtube.py`, `hypeddit.py`, `spotify_s4a_combined.py`.

<!-- section actif : Open Bugs -->
### P2 — Data Integrity (new)

- [x] **Multi-tenancy — artist_id propagation in all collectors** (Brick 20)
  Collectors hardcode `artist_id = 1` in INSERT statements. DAGs don't iterate all active artists.
  Fix: add `artist_id` param to `SoundCloudCollector`, `InstagramCollector`, `MetaAdsWatcher`, `MetaCSVWatcher`; update DAGs to loop via `get_active_artists()`; scope DELETE queries by `artist_id`.
  Files: `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_insight_watcher.py`, `meta_csv_watcher.py`, `soundcloud_daily.py` (already OK), `instagram_daily.py`, `youtube_daily.py`, `spotify_api_daily.py`, `meta_insights_dag.py`, `meta_config_dag.py`.

<!-- section actif : Open Bugs -->
### P3 — UX / Features (new)

- [x] **Scheduled email reports** — `airflow/dags/weekly_digest.py`, every Monday 08:00 UTC. One HTML email per active artist: S4A streams delta, top song, Meta spend/CTR, Instagram delta, SoundCloud delta, ML top prediction. Requires SMTP_USER/SMTP_PASSWORD/ALERT_EMAIL env vars.
- [x] **Stripe integration** (Brick 21) — `subscription_plans` + `artist_subscriptions` tables in `stripe_schema.py` + `migrations/004_stripe_billing.sql`; `POST /webhooks/stripe` in `src/api/routers/stripe_webhook.py` (handles checkout.session.completed, subscription.updated/deleted, invoice.payment_failed); `get_artist_plan()` + `require_plan()` in `auth.py`; billing page `views/billing.py` (current plan, MRR admin view, plan comparison, upgrade links). Requires STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_CHECKOUT_URL, STRIPE_PORTAL_URL env vars.
- [x] **PDF report expansion** — `pdf_exporter.py` extended with 6 new sections: S4A top songs, YouTube, Instagram, Meta Ads, SoundCloud tracks, Apple Music. `songs_filter` parameter added to `_collect_s4a_top_songs`, `collect_report_data`, `generate_pdf`. `export_pdf.py` adds S4A song selector with "Toutes" checkbox.
- [x] **Excel export** — `csv_exporter.py` gains `export_excel()` (openpyxl, multi-sheet). `export_csv.py` adds format selector (ZIP vs Excel).
- [x] **SoundCloud track selector UX** — track list sorted by `first_seen DESC`; defaults to the latest release (`[:1]`).
- [x] **Data Wrapped multi-tenant fix** — admin query no longer filters `active=TRUE`; non-admin loads real artist name from DB instead of hardcoded value.
- [x] **Data Wrapped gains → percentages** — `artist_wrapped` 4 `*_gain` columns (INTEGER/BIGINT) renamed to `*_gain_pct` and widened to `DECIMAL(7,2)` via idempotent `migrations/033_wrapped_gains_pct.sql` (guarded RENAME + TYPE widening). `data_wrapped.py` form inputs now signed `%` `number_input`s (`_fmt_pct` helper, `_bar_gain_chart` `fmt_fn` param, "(%)" titles, "△ X %" rename_map); `wrapped_schema.py` canonical CREATE TABLE updated for fresh installs.
- [x] **Data Wrapped "top" metric → super-fans + combined chart** — the old `top_artist_name` (VARCHAR) + `top_artist_fan_pct` (DECIMAL) modelled a *similar artist*; replaced by the artist's OWN super-fans `top_fans_count INTEGER` + `top_fans_rank INTEGER` (fans who ranked the artist in their top N) via idempotent `migrations/034_wrapped_top_fans.sql` (ADD IF NOT EXISTS + DROP IF EXISTS; applied to live DB, artist_id=1/2024 row preserved + backfilled to 11/rank 5). `wrapped_schema.py` updated. `data_wrapped.py`: 4 absolute line charts merged into one `_multi_line_chart` with per-tab linear/log `st.toggle`; 4 gain % bars regrouped under "Gains annuels (%)"; new "Super-fans" line+table replaces "Top artiste similaire"; `_load_row_for_year` refactored to `fetch_df().iloc[0].to_dict()` (robust to DROP/ADD column reordering). ref: DEVLOG#2026-05-29.
- [x] **Billing page env fix** — `billing.py` replaced `st.secrets` with `os.getenv` for STRIPE_CHECKOUT_URL and STRIPE_PORTAL_URL (fixes crash when Streamlit secrets file absent).
- [x] **WeasyPrint → xhtml2pdf migration** — `pdf_exporter.py` and `requirements.txt` switched from WeasyPrint to `xhtml2pdf>=0.2.11` (eliminates system-level GTK/Pango dependency).
- [x] **SMTP config fix** — `.env` corrected: SMTP_HOST was set to an email address (now `smtp.gmail.com`); SMTP_PORT moved to its own line.

<!-- section actif : Open Bugs -->
### P4 — Tech Debt (new)

- [x] **CSV upload audit log** — `csv_upload_log` table (migration 025): filename, artist_id, platform, row_count, status, error_message, imported_at. Logged after every upsert in `upload_csv.py`; audit failure never blocks UI.

- [x] **`init_db.sql` bootstrap gap** — 26 missing tables appended (S4A, Meta Ads, Meta Insights ×10, YouTube ×6, Apple Music ×4, Hypeddit ×2). Fresh install is now self-contained.
- [x] **YouTube UNIQUE constraints** — `UNIQUE(artist_id, channel_id, collected_at::date)` and `UNIQUE(artist_id, video_id, collected_at::date)` added to `youtube_schema.py` + `migrations/003_youtube_unique.sql`.
- [x] **`provide_context` deprecation** — removed `provide_context=True` from all 4 `PythonOperator` instances in `data_quality_check.py`. Functions already accept `**context`.

<!-- section actif : Open Bugs -->
### P3 — UX / Features (new, 2026-03-27)

- [x] **Meta Ads credential onboarding guide** — step-by-step guide with screenshots for each artist to configure Meta credentials in the dashboard.
  Spec: (1) generate a long-lived User Access Token from Business Manager → System Users (not a personal token); (2) token must have `ads_read` + `ads_management` scopes; (3) account_id = numeric ID from `/me/adaccounts` (no `act_` prefix — the dashboard adds it); (4) artists do NOT create their own app — they use ETL_DASHBOARD_SPOTIFY as OAuth client; (5) link ad account to the app in Business Manager → App Settings → Business Assets.
  Deliverable: dedicated doc in `.claude/dev-docs/` + in-app help tooltip on Credentials page.

<!-- section actif : Open Bugs -->
### P2 — Data Integrity (new, 2026-03-27)

- [x] **Instagram System User token — activation** — code-side ready (DAG `meta_token_refresh` skip `expires_at=NULL`, collector ne touche plus à `os.environ`). Activation par tenant = acte opérationnel décrit dans `.claude/dev-docs/meta-ads-credential-guide.md` ; suivi par artiste, pas par roadmap.
- [x] **Instagram + Meta System User token migration** (Brick 24) — migrate from personal 60-day tokens (expired Dec 2025) to System User tokens (never expire).
  Changes: `meta_token_refresh.py` skips artists with `expires_at=NULL` instead of attempting `fb_exchange_token` (which fails on System User tokens); `instagram_daily.py` precheck error message updated; `_guide_meta()` extended with Instagram scopes (`instagram_basic`, `instagram_manage_insights`, `pages_show_list`); `meta-ads-credential-guide.md` updated with token refresh behavior table.
  Note: Spotify/YouTube/meta_token_refresh DAGs were already scheduled in previous bricks — no schedule changes needed.

<!-- section actif : Open Bugs -->
### P1 — Security (new, 2026-03-27)

- [x] **`get_artist_id()` default was `1` instead of `None`** — session non-hydratée queryait silencieusement l'artiste 1. Fix: `auth.py` default → `None`.
- [x] **`get_artist_id() or 1` dans 9 vues** — isolation tenant cassée pour les admins (None coercé sur artiste 1). Fix: guard explicite `if artist_id is None: if not is_admin(): st.stop()` dans `apple_music.py`, `instagram.py`, `soundcloud.py`, `youtube.py`, `meta_ads_overview.py`, `meta_cpr_optimizer.py`, `meta_creatives.py`, `meta_x_spotify.py`, `hypeddit.py`.
- [x] **f-string SQL avec `where_clause` interpolé — `meta_ads_overview.py`** — fragment WHERE interpolé dans 5 requêtes via f-string. Fix: suppression de la variable `where_clause`; chaque requête construite explicitement avec `_campaign_in`.
- [x] **f-string SQL avec identifiants table/colonne — `freshness_monitor.py` + `kpi_helpers.py`** — noms de table et colonne interpolés sans validation. Fix: allowlists `_ALLOWED_TABLES` / `_ALLOWED_COLS` validées avant interpolation.
- [x] **Secrets réels dans `config/config.yaml`** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

<!-- section actif : Open Bugs -->
### P1 — Security (2026-03-28 — full OWASP + RGPD hardening)

- [x] **CRITICAL-02: SQL injection in `postgres_handler.py`** — `insert_many()` / `upsert_many()` used f-string table/column interpolation. Fix: `_ALLOWED_TABLES` frozenset + `_VALID_IDENTIFIER_RE`; all queries rewritten with `psycopg2.sql` composition.
- [x] **CRITICAL-03: SQL injection via `artist_id_sql_filter()` table alias** — alias not validated. Fix: `_ALIAS_RE = re.compile(r'^[a-z_][a-z0-9_]*$')` in `auth.py`.
- [x] **CRITICAL-04: Campaign filter IDOR in `meta_ads_overview.py`** — user-supplied campaign IDs not validated against DB. Fix: allowlist check against fetched campaign list.
- [x] **CRITICAL-05: Fernet key on disk** — `credentials.py` read FERNET_KEY only from config.yaml. Fix: `os.getenv('FERNET_KEY')` first, config.yaml as local-dev fallback.
- [x] **CRITICAL-06: Token written to `os.environ` in `instagram_api_collector.py`** — exposed to all child processes. Fix: removed the assignment entirely.
- [x] **HIGH-01: No brute-force protection** — unlimited login attempts. Fix: `failed_login_attempts` + `locked_until` in DB (migration 017); 5 failures → 15-min lockout.
- [x] **HIGH-02: Email enumeration on unverified login** — error message revealed whether email existed. Fix: generic message; email looked up only on "Resend" button click.
- [x] **HIGH-04: Weak password policy** — minimum 8 chars only. Fix: 10 chars + 1 letter + 1 digit enforced in both `auth.py` and `register.py`.
- [x] **HIGH-05: Hardcoded `'admin'` default in AirflowTrigger** — unauthenticated DAG triggering possible. Fix: `RuntimeError` raised if `AIRFLOW_PASSWORD` is falsy.
- [x] **HIGH-06/07: Stored XSS via `unsafe_allow_html`** — DB values interpolated unescaped in `etl_logs.py` and `home.py`. Fix: `html.escape()` on all interpolated values.
- [x] **MEDIUM-01: Session fixation** — session state not cleared on login. Fix: `st.session_state.clear()` before `_hydrate_session()`.
- [x] **MEDIUM-02: Plan gate bypass** — `require_plan()` returned `False` instead of stopping. Fix: `st.stop()` after error.
- [x] **MEDIUM-05: TOCTOU on single-use promo codes** — concurrent registrations could exhaust code without guard. Fix: atomic `UPDATE ... WHERE uses_count < max_uses RETURNING id`.
- [x] **INFO-01: Email verification tokens never expire** — link valid indefinitely. Fix: 48h expiry check in `_verify_email()`; expired token cleared from DB.
- [x] **INFO-02: Secret key names logged at INFO level** — `credential_loader.py` logged key name in update messages. Fix: `logger.debug()` with key name removed.
- [x] **INFO-04: SSRF via open redirects in outbound requests** — 5 `requests` calls in `credentials.py` without `allow_redirects=False`. Fix: `allow_redirects=False` on all 5.
- [x] **INFO-06: No upload size cap** — Streamlit allowed arbitrarily large file uploads. Fix: `.streamlit/config.toml` with `maxUploadSize = 50`.
- [x] **RGPD Art. 5(1)(f): Marketing export not audited** — no record of admin personal data access. Fix: `admin_audit_log` write on download button click in `admin.py`.
- [x] **CRITICAL-01: Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.
- [x] **Task #11: Update all dev-docs with security session** — DEVLOG.md, retro.md, checklist.md updated to reflect the full 2026-03-28 security hardening session (Brick 25: OWASP + RGPD). All implemented items documented.

<!-- section actif : Open Bugs -->
### P2 — Data Integrity (new, 2026-03-27 — audit)

- [x] **Collecteurs silencieux — `instagram_api_collector.py` + `soundcloud_api_collector.py`** — `except Exception → self.db = None` permettait un run complet à 0 lignes avec DAG SUCCESS. Fix: suppression du try/except autour de `PostgresHandler.__init__`; échec DB = exception levée.
- [x] **`spotify_api.py` `search_artist()` retournait `None`** — au lieu de `raise` sur API error ou artiste introuvable. Fix: `ValueError` si aucun artiste trouvé, `raise` dans le bloc `except`.
- [x] **Validation email trop permissive dans `register.py`** — `'@' not in email` acceptait `a@`, `@b`, `@@`. Fix: `re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email)`.

<!-- section actif : Open Bugs -->
### P3 — Performance (new, 2026-03-27 — audit)

- [x] **`get_artist_plan()` ouvrait 2–3 connexions DB par render** — fallback `db2` ouvert séparément. Fix: 1 seule requête avec LEFT JOIN `saas_artists ↔ artist_subscriptions ↔ subscription_plans`; promo + subscription + tier résolus en 1 round-trip. (`auth.py`)
- [x] **`get_source_freshness()` — 7 requêtes séquentielles** — 1 `SELECT MAX()` par source à chaque chargement de la home. Fix: remplacé par 1 `UNION ALL` query. (`kpi_helpers.py`)
- [x] **Index composites manquants** — `migration/016_performance_indexes.sql` ajoute 4 index : `s4a_song_timeline(artist_id, date DESC)`, `soundcloud_tracks_daily(artist_id, track_id, collected_at DESC)`, `meta_insights_performance_day(artist_id, day_date DESC)`, `track_popularity_history(artist_id, date DESC)`.

<!-- section actif : Open Bugs -->
### P2 — Data Integrity (new, 2026-03-30)

- [x] **Meta Ads DAG first-run backfill** — DONE 2026-06-01. Token blocker resolved 2026-05-31 (expired personal token `code 190` → valid System User token, `type=SYSTEM_USER`/`expires_at=0`, `expires_at` NULL in DB). Rate-limit blocker resolved 2026-06-01: the `code 80004` BUC throttle was purely a concurrency/quota-exhaustion artefact (multiple runs hammering the same ad-account — confirmed live: an over-eager session fired scheduled + 2 daily manual + a full_history run, and the full_history run wall-throttled on the per-creative content fetch for ~26 min, then was killed). **Fix that worked:** stopped all Meta activity, let the account quota cool ~60 min, triggered ONE solo `full_history` run on a rested quota → completed in ~4 min with **zero throttle**: 34 campaigns, 69 adsets, 144 ads, 144 creatives, **13139 insight rows across 23 tables** (incl. all previously-empty ad/adset × country/placement/age breakdowns). `meta_insights_performance_day` now spans 2023-08-24 → 2024-09-29 (231 rows / 205 days) = the campaigns' full lifetime; it does NOT advance past 2024-09-30 because the account has had no spend since then (the daily run finds nothing newer), so the original "past 2024-09-30" criterion was an incorrect assumption. **Operational rule confirmed:** `max_active_runs=1` + a single solo run on a rested quota is the reliable way to run full_history; never fire concurrent/back-to-back Meta runs. The "Meta per-chunk insight persistence" gap (a late throttle discards the whole run) remains open below as a separate hardening item. ref: DEVLOG#2026-06-01.
- [x] **SoundCloud DAG cursor pagination — confirm** — CONFIRMED live 2026-05-31. `soundcloud_daily` scheduled run succeeded in ~2 s (precheck 1.9 s + collect 1.8 s) → no hang (the old infinite-pagination loop is gone). `soundcloud_tracks_daily` has **0 duplicate** `(track_id, collected_at::date)` rows → cursor `next_href` followed correctly. 197 rows, fresh (collected 2026-05-31 20:42).
- [x] **Instagram System User token — migration** — same as line 110 (code path complete). Per-artist migration is operational, not a code task. See guide.

<!-- section actif : Open Bugs -->
### P2/P3 — Live-ops hardening (2026-05-31, from the Meta credential session)

- [x] **DAG concurrency cap — `max_active_runs=1` fleet-wide** (P2). Root cause of the Meta throttle storm: the dashboard auto-triggers a collector DAG on every credential save (`_render.py`), and 8 DAGs had NO `max_active_runs` → rapid re-saves spawned 5 concurrent `meta_ads_api_daily` runs hammering the same ad-account → instant Meta BUC `80004`. Fix: `max_active_runs=1` added to all 8 uncapped DAGs (meta_ads_api_daily, instagram_daily, soundcloud_daily, spotify_api_daily, youtube_daily, meta_token_refresh, ml_scoring_daily, weekly_digest). **All 13 DAGs now capped.** Encoded the rule in `.claude/skills/airflow-dag.md` (template + checklist + REX). Generalization audited: the only 2 DAG-trigger sites (`app.py` "Lancer TOUTES" button, `_render.py` save) are now both safe; the button triggers 7 *distinct* DAGs (no single-account concurrency).
- [x] **Meta System User token → false 60-day expiry** (P3). `_fetch_meta_token_expiry` returned `None` for never-expiring System User tokens (debug_token `expires_at=0`), conflating "never expires" with "couldn't determine" → the save left a stale/false expiry + a misleading warning (manual `expires_at=NULL` was needed). Fix: new `META_TOKEN_NEVER_EXPIRES` sentinel (also keyed on `type=='SYSTEM_USER'`); `_handle_save` now sets `expires_at=NULL` for it; the exchange/renew path defaults `expires_in` to 0 (not 60 days) and sets NULL when the token never expires. Generalization: expiry logic is 100% `platform='meta'` (Instagram shares the Meta token) — no other platform affected.

<!-- section actif : Open Bugs -->
### P1 — Security (new, 2026-03-30)

- [x] **Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

<!-- section actif : Open Bugs -->
### Decisions / closed (2026-03-27)

- ❌ **iMusician API** — no public API exists on any iMusician plan (confirmed 2026-03-27), including AMPLIFY Pro. CSV-only. `imusician_csv_watcher` DAG is the final architecture for this source. Contact iMusician support if an enterprise/white-label API becomes available.
- ❌ **Apple Music API** — Apple Music for Artists has no public analytics API. MusicKit covers catalog/playback only. CSV export remains the only option.

---

## Brick Status

| # | Topic | Status | Priority |
|---|---|---|---|
| 1 | DB migration SaaS (artist_id + saas_artists table) | ✅ | — |
| 2 | Auth Streamlit (authenticator + artist_id in session) | ✅ | — |
| 2.5 | SQL filters by artist (artist_id in all queries) | ✅ | — |
| 3 | Admin interface (CRUD artists + CSV upload) | ✅ | — |
| 4 | API credential form (Fernet encryption) | ✅ | — |
| 5 | CSV import via Streamlit with preview + validation | ✅ | — |
| 6 | Parameterized DAGs (credentials from DB) | ✅ | — |
| 7 | iMusician — manual monthly revenue entry + viz | ✅ | — |
| 8 | Home KPI + source freshness + ROI Breakheaven | ✅ | — |
| 9 | Error handling + retry on all collectors | ✅ | P2 |
| 10 | Unit tests (pytest, 79 tests) | ✅ | P2 |
| 11 | Monitoring + alerting (DAG callbacks + freshness) | ✅ | P2 |
| 12 | PDF report export (WeasyPrint) | ✅ | P3 |
| 13 | CSV global export (ZIP per artist) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT auth) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16 | ML — ml_song_predictions table + daily scoring DAG | ✅ | P3 |
| 17 | ML — trigger_algo upgrade + model performance view | ✅ | P3 |
| 18 | Data Wrapped — annual artist performance report (PDF/HTML) | ✅ | P3 |
| 19 | Security audit — SQL injection, Fernet key exposure, auth bypass, SSRF | ✅ | P3 |
| 20 | Multi-tenancy — artist_id propagation in all collectors + DAG iteration | ✅ | P2 |
| 21 | Stripe integration — subscription plans, webhook, billing page | ✅ | P3 |
| 22 | iMusician CSV import — parser, watcher DAG, Distributeur tab, Upload CSV page | ✅ | P2 |
| 23 | Meta Ads API collector — direct pull (facebook_business SDK), daily DAG, CSV data-quality fixes | ✅ | P2 |
| 24 | Instagram + Meta System User token migration — non-expiring tokens, DAG + guide updates | ✅ | P2 |
| 25 | Security hardening — OWASP Top 10 + RGPD: SQL injection (postgres_handler), brute-force lockout, session fixation, SSRF, XSS, weak password policy, Fernet key env, promo TOCTOU, token expiry, upload cap, audit log | ✅ | P1 |
| 26 | Rate limiting — session-based sliding window (10 attempts / 5 min) on login + TOTP challenge | ✅ | P1 |
| 27 | GDPR Art. 17 erasure — cascading DELETE across 34 tables, 2-step admin confirmation, gdpr_erasure_log audit trail | ✅ | P2 |
| 28 | TOTP 2FA — pyotp + qrcode enrollment in account.py, challenge step in login flow, disable-with-password | ✅ | P1 |
| 29 | Onboarding tracker — "Getting started" progress on home page (credentials, S4A CSV, Apple Music CSV, first data collection); shows green "configuration terminée" recap when complete (no longer auto-hidden — revised 2026-05-28) | ✅ | P3 |
| 30 | Alerting dashboard — circuit breakers, freshness warnings, DAG failures, locked accounts, billing alerts | ✅ | P2 |
| 31 | S4A dashboard view audit — per-track KPIs (listeners, saves) from s4a_songs_global; dual-window (28d/12m) support; DB health view; playlist placement manual entry; s4a_audience saves/playlist_adds columns | ✅ | P3 |
| 32 | Benken onboarding incident — central-app credential model completed (admin app/platform, artist=identifier; dashboard env wiring fixed; SoundCloud wired); per-tenant DAG isolation (10 sites + `test_dag_fleet_isolation`); load_dotenv guard; CSV detection broadened; credentials UX (order, honest status, Spotify/YT guides). PRs #87-90 | ✅ | P1/P2 |
| 33 | Post-incident hardening — `test_env_contract` + boot preflights + `test_compose_parity`; per-tenant freshness + consecutive-failure escalation in alert_monitor; ADR-006 central credential model; `tools/{prod_introspect,check_central_apps}`; 6 error classes. PRs #91-93 | ✅ | P2 |
| 34 | Per-artist onboarding readiness closed loop — `artist_readiness()` (identity + data-landing per platform → status + next action); 🚦 Santé onboarding view (admin/artist); alert_monitor flag; connect-time Spotify identity validation. PRs #94-95 | ✅ | P2 |

---

### P3 — UX / Features (new, 2026-03-31)

- [x] **S4A per-track KPIs fix** — Listeners and Saves in trigger_algo `_show_tab_global()` were sourced from `s4a_audience` (artist-level → same value for all tracks). Rebound to `s4a_songs_global` per-track snapshot with automatic `time_window` selection (≤35 days → `28d`, else `12m`).
- [x] **s4a_songs_global dual-window** — migration 023 adds `time_window TEXT DEFAULT '12m'` + UNIQUE `(artist_id, song, time_window)`. Parser detects `28d` from filename tokens `28day/28d/28j`, else `12m`. `ml_inference.py` queries now filter `AND time_window = '12m'`.
- [x] **s4a_audience saves + playlist_adds** — migration 020 adds columns. Parser maps `'playlist adds'` (with space) and `'saves'` from audience CSV.
- [x] **Playlist placement manual entry** — migration 021 `s4a_song_playlists` (per-song playlist registry, unused for now). Migration 022 `s4a_song_playlist_adds(artist_id, song, period_start, period_end, count)` — stores manual count from S4A UI (not in CSV exports). `trigger_algo.py` Vue Globale shows count + update form.
- [x] **DB health view** (`src/dashboard/views/db_health.py`) — 11 datasets, freshness table + horizontal bar chart (thresholds 14j/30j), 52-week heatmap, cumulative growth chart, batch sizes chart.
- [x] **Styled dataframe NoneType crash** — `display.style.format(na_rep="—")` added as first call in Score /20 benchmark; `fillna(0)` on all numeric columns before styling.
- [x] **Upload CSV multi-file auto-detection** — `_detect_platform(filename, columns)` priority-ordered detection; `accept_multiple_files=True`; per-file preview + 4-KPI import result.
- [x] **upsert_many row count fix** — was returning `cursor.rowcount` (last batch only = 1); now returns `len(data)` post-dedup.

### P2 — Data Integrity (new, 2026-03-31)

- [x] **s4a_audience playlist_adds / saves still 0** — confirmed: `playlist_adds` is not present in `s4a_songs_global` CSV (neither 28d nor 12m format). Only source is `s4a_audience` daily timeline CSV (artist-level delta) which records 0 for this artist — genuine data. Saves ARE in songs_global CSV and import correctly. playlist_adds entry via manual form (`s4a_song_playlist_adds`) is the intended workflow.

### P2 — Data Integrity (new, 2026-05-14)

- [x] **Migrate `tracks` table to multi-tenant** — DONE 2026-05-31. `migrations/039_tracks_multi_tenant.sql` adds `saas_artists.spotify_artist_id` (bridge) + `tracks.saas_artist_id` (FK to `saas_artists.id`) + `idx_tracks_saas_artist`; idempotent unambiguous auto-bridge backfilled the single tenant (saas id=1 ← `7sbfafbLjNZGZJZjZ3xoPB`, 11 tracks). Applied to live DB. Writer `spotify_api_daily.collect_spotify_top_tracks` resolves + stamps `saas_artist_id` per Spotify id (warns if unbridged). All 4 readers now filter by `saas_artist_id` (`spotify_s4a_combined` ×3, `trigger_algo` ×2 incl. admin-unfiltered branch, `meta_x_spotify` ×1); admin (None) = no filter. `init_db.sql` updated for fresh installs. Legacy varchar `tracks.artist_id` kept (drop in a later cycle). See `.claude/dev-docs/audit-tracks-legacy.md`.

### P1 — Security hardening (closed, 2026-05-14)

- [x] **Explicit SQL allowlist guards** — `db_health.py`, `admin.py`, `airflow_kpi.py` had f-string SQL with implicit allowlist (via constant lookup). Now call `validate_table()` / `validate_columns()` explicitly before each f-string per CLAUDE.md rule #8. Promoted both validators from private (`_validate_*`) to public API in postgres_handler. Commits `d41a842`, `997dcde`.

### P2 — Data integrity (closed, 2026-05-14)

- [x] **Instagram collector silent success** — `_refresh_access_token` and `save_to_db` swallowed exceptions and reported success. Both now `logger.error` + `raise`. Commit `a0f86de`.
- [x] **`requirements.txt` duplicates** — python-dotenv, pandas, psycopg2-binary listed twice (rows 62-64 vs canonical block). Removed dupes. Commit `a0f86de`.

### P2 — Data integrity (closed, 2026-05-15)

- [x] **YouTube collector silent success** — `get_video_comments()` and `get_playlists()` did `return [partial]` inside `except` → a truncated fetch could mark a DAG SUCCESS. Both now `raise` (CLAUDE.md rule #6). YouTube collector now fully silent-success-compliant; `audit-collectors.md` status table corrected, `error-classes.md` `collector-silent-success` History appended. Commit `3b63984`.

### P3 — Infra / supply chain (closed, 2026-05-14)

- [x] **Airflow base image → Python 3.11** — was 3.10, mismatched `pyproject.toml requires-python = ">=3.11"`. Smoke-validated (15 DAGs load, sklearn/xgboost/shap import). Commit `52db15f`.
- [x] **Dependabot config** — pip weekly (groups), github-actions monthly, docker monthly. Closes the loop with `security-nightly.yml` pip-audit (detection → automated fix PR). Commit `6c323c9`.
- [x] **CI on `uv sync --frozen`** — was `pip install -r requirements*.txt` which ignored uv.lock; CI and local devs could install different transitive deps. Now CI reads uv.lock (231 packages pinned). Necessary for Dependabot to be effective. Commit `e6513b4`.
- [x] **Repo cleanup → `.archive/`** — ~22 obsolete files (unused skills, dev-docs stubs, archived agent doublons, dated retro/audit snapshots, legacy v1 collectors) moved to gitignored `.archive/`. CLAUDE.md aligned. Commits `a4fa11e`, `d60e570`, `418fad5`.
- [x] **Collectors style sweep** — 28 `print()` → `logger.*()` and 13 `datetime.now()` → `datetime.now(timezone.utc)` (filename strftime exempt). Commit `a0f86de`.
- [x] **REX promotion** — 2 drafts (`strategic-plan-architect`, `response-protocol`) validated and injected per `rules/rex-format.md`. Validator 42 tools OK. Commit `a3b13d9`.
- [x] **`check_roadmap_update.py` hook** — was no-op (`_INCLUDE='src/Application'` mismatched repo, tracker paths pointed to non-existent files). Fixed to `_INCLUDE='src'` with proper excludes, trackers = `roadmap/checklist.md` + `DEVLOG.md`. Commit `bcfe774`.
- [x] **`.env*.example` templates trackable** — `.gitignore` rule `.env.*` was swallowing the example onboarding files; added `!.env.example` + `!.env.railway.example` exceptions. Also added missing Stripe vars (Brick 21) to Railway example. Commit `66f807d`.
- [x] **pytest coverage** — added `[tool.coverage]` config in `pyproject.toml`, `--cov=src --cov-report=xml` in CI, coverage.xml uploaded as 7-day artifact. No `fail_under` (measure first). Commit `7376aae`.

### P3 — UX / Features (new, 2026-04-12)

- [x] **Live user counter + registered users widget** (Brick 32) — display on the app (home page or landing) the number of currently active sessions and total registered artists. ✅ 2026-05-14
  Sub-tasks:
  - [x] Active sessions: `active_sessions` table (heartbeat updated on each page load, TTL = 5 min). Migration 026.
  - [x] Registered users: `SELECT COUNT(*) FROM saas_artists WHERE active = TRUE`.
  - [x] SEO name: **Live Activity** chosen. Visible copy on landing: "X artistes utilisent streaMLytics".
  - [x] Read-only widget (counts only, no PII). Admin pulse on `home.py`, public trust signal on `register.py`.
  Priority: P3. Decision: added `active_sessions` heartbeat table with 60s session_state throttle (≤1 INSERT/min/session).

---

### P3 — Performance dashboard (long-term, 2026-05-14 audit)

Audit statique + live Lighthouse (page login publique) effectués 2026-05-14. Voir aussi `docs/adr/ADR-003-react-rewrite-deferred.md` pour l'option architecturale long-terme.

**Mesures Lighthouse réelles (login page, headless desktop)** :

| Métrique | Valeur | Score | Cible |
|---|---|---|---|
| Performance | 69/100 | — | ≥90 |
| FCP (First Contentful Paint) | 3.7 s | 29 | <1.8 s |
| **LCP (Largest Contentful Paint)** | **5.7 s** | 16 | <2.5 s |
| TTI (Time To Interactive) | 5.7 s | 68 | <3.8 s |
| CLS (Cumulative Layout Shift) | 0.066 | 97 | <0.1 ✅ |
| TBT (Total Blocking Time) | 80 ms | 99 | <200 ms ✅ |
| Speed Index | 3.7 s | 85 | <3.4 s |

**Network breakdown** : 25 requêtes, 818 KiB total, **bundle JS Streamlit = 532 KiB** (`index.Drusyo5m.js`), 12 fichiers JS (550 KiB cumulé), **324 KiB de JS unused** sur la page login.

**Conclusion live vs static** : le bottleneck #1 du *cold start* est le **bundle JS Streamlit** (pas Python). Les optimisations Python (cache, lazy imports) restent valides mais n'améliorent que les *renders subséquents*, pas le cold start. Cela renforce légèrement l'argument React (Next.js + code splitting → ~100-150 KiB initial bundle vs 532 KiB) mais ne change pas la décision ADR-003.

- [x] **N+1 Airflow DAG monitoring** (HIGH) — DONE 2026-05-31. New `AirflowMonitor.get_all_dags_last_state()` collapses the per-DAG `get_runs_for_dag` loop into ONE POST to the `~/dagRuns/list` batch endpoint (latest run per DAG, sorted-desc first-wins), with a per-DAG fallback if the batch endpoint is unavailable. Repointed all 3 callers: `airflow_kpi.py::_section_last_runs`, `home.py::_section_dag_status`, `credentials/_core.py::_fetch_dag_last_states`. Not live-smoke-tested (Airflow webserver was down this session) — fallback guarantees correctness. **Gain ~2-3 s/render.**
- [x] **`@st.cache_data(ttl=60)` sur 5 KPI helpers** (HIGH) — DONE 2026-05-31. 8 read-only getters in `kpi_helpers.py` wrapped: `get_source_freshness`, `get_total_streams_s4a`, `get_total_views_youtube`, `get_total_plays_soundcloud`, `get_total_plays_apple`, `get_spotify_popularity`, `get_instagram_followers`, `get_soundcloud_likes`. DB handle passed as `_db` (underscore → excluded from cache key; entries keyed on artist_id). No Airflow caller, so the Streamlit-cache decorator is safe. **Gain ~500-1000 ms.**
- [x] **View render-smoke test harness** (NEW 2026-05-31) — `tests/test_views_render_smoke.py`: `AppTest`-runs all 36 dashboard views' `show()` under an admin session against the live DB, asserting no uncaught exception (catches mis-scoped lazy-import `NameError`, broken `@st.fragment`, render-time SQL typos — the class of regression that previously shipped green, cf. WAVE 3 "failed-Edit dead code passed tests+ruff"). Module-skips when Postgres is unreachable (CI has no DB on 5433). 36 pass in ~13 s. Closes the "zero view-render coverage" gap. ([[project_no_view_render_tests]])
- ❌ **CANCELLED 2026-06-01 — Lazy imports plotly + pandas dans 19 vues** (MEDIUM). Re-analysis showed ≈0 gain: `app.py` already lazy-loads view modules per page (`elif page=="x": from views.x import show; show()`), and the module-import + `show()` call are coupled, so deferring `import plotly` into `show()` saves nothing — plotly still loads on the first chart render. Cold start is dominated by the 532 KiB JS bundle ("irréductible sans changer de framework"), which masks any Python-side ms. 26-file churn for no user-visible gain. Revisit only if a non-charting view is ever added.
- [x] **`@st.fragment` sur widgets isolés** (MEDIUM) — DONE 2026-05-31. `home.py::_section_pdf_export` (PDF "Rapport rapide" button + download) and `airflow_kpi.py::_section_insertion_test` (Today/7d/30d window selector → per-table COUNT loop) decorated with `@st.fragment`: interacting with them re-runs only that section, not the whole heavy page. Both self-contained (state via `st.session_state`), verified by the new render-smoke harness. **Gain ~300-500 ms par interaction.**
- [x] **Plotly area chart sampling** (LOW-MEDIUM) — DONE 2026-05-31. Added >500-row downsampling to the cumulative S4A area chart (`spotify_s4a_combined.py`; the `home.py:167` reference was stale — that chart moved here). Every-Nth-point on a monotonic cumulative series, with the last point always kept so the total is never understated. **Gain ~100-300 ms réseau lent.**
- [x] **Pagination admin + ETL logs** (HIGH si tables >1000 rows) — RESOLVED 2026-05-31. Re-scoped to the real concern (silent truncation, not perf): `etl_logs.py` already caps at `LIMIT 200` but hid older runs silently — added an honest "Affichage des 200 runs les plus récents sur N au total" caption (one extra `COUNT(*)`, only when truncating). `admin.py` tables (artists/users/opt-in) are bounded by tenant count — no growth risk, no pagination needed. The only daily-growing table is `etl_run_log`, now handled. Verified by render-smoke. **Gain: honesty, not ms.**
- [x] **`SELECT *` → colonnes explicites** (LOW) — RESOLVED 2026-05-31. `apple_music.py` `SELECT * FROM daily_diff` (a CTE, columns already explicit) made literal. `data_wrapped.py` ×2 (`SELECT * FROM artist_wrapped`) deliberately KEPT generic: consumed via `.to_dict()` + dynamic `df[['year', col]]` + `.get(col)`; DEVLOG#2026-05-29 made this robust to DROP/ADD column reordering (migrations 033/034) — explicit projection would re-introduce that fragility and break dynamic column access. Wontfix-by-design.
- [x] **Disable Streamlit telemetry + headless mode** — `.streamlit/config.toml` updated 2026-05-14 : `[browser] gatherUsageStats = false` (skip data.streamlit.io + fivetran calls) + `[server] headless = true` (skip auto-open browser, fixes WSL2 `gio` error + ready for Hetzner headless VPS).

**Estimated total** : ~2 jours de dev → -50 % temps de render moyen (de ~2-3s à ~1-1.5s) sur les pages internes. **Le cold start (LCP 5.7s) restera dominé par le bundle JS Streamlit (532 KiB) — irréductible sans changer de framework.**

### P4 — Refactor program (2026-05-15)

- [x] **Dashboard refactor program** — sequenced queue R1–R6 (one file/PR, trigger-gated) — DONE 2026-06-01. Tracker: `.claude/dev-docs/roadmap/refactor-program.md` (created `c30d004`, spec: `refactor-audit-dashboard.md`). R1 `credentials.py`→package ✅ (`acf8b6f`, 2026-05-15). R2 `kpi_helpers.py` ruff ✅ (already clean under authoritative config). R4 `trigger_algo.py` (grown to 2279 l / 6 tabs) → package ✅ (`d84c53a`). R5 `pdf_exporter.py` HTML primitives + snapshot net ✅ (`905202b`). R6 `revenue_forecast.py` calc→tested util ✅ (`e8fc0c6`, +8 tests). R3 = `view-session-adoption` — partial **by design** (helper ships; migration stays opt-in per view, no big-bang). 335 pytest pass. Guardrails honored: one-file commits, no FastAPI/React, no service layers (ADR-002), never split <400 l.

### P2 — Data integrity (new, 2026-05-28)

- [x] **Meta Ads `results` hardcoded to one action_type** — `meta_ads_api_collector.py` counted only `offsite_conversion.custom`. All 15 test-account campaigns are `OUTCOME_ENGAGEMENT` (0 custom conversions) → `results` written `0` daily, and the daily upsert overwrote correct CSV-imported values. Fix: `_OBJECTIVE_RESULT_ACTION` map (`OUTCOME_ENGAGEMENT→post_engagement`, `OUTCOME_TRAFFIC→link_click`, `OUTCOME_LEADS/SALES→offsite_conversion.custom`, `OUTCOME_APP_PROMOTION→app_install`; unknown/NULL/awareness → fallback `custom_conversions`). Objective propagated from `meta_campaigns` into `_extract_perf` via `objective_by_name` across all 4 `_call_insights` calls + the `insights_only` DB query. `tests/test_meta_ads_collector.py` adds `TestExtractPerfObjective` (6 tests). **Requires a `full_history` Meta DAG re-collection to backfill historical `results`.**
  Decision recorded: dashboard "Résultats" = Meta's native result per campaign objective (user-confirmed), not Spotify-only conversions.

### P3 — UX / Features (new, 2026-05-28)

- [x] **Onboarding tracker revision** (`home.py`) — replaced the "Enable 2FA" step with "Upload an Apple Music CSV" (checks `apple_songs_performance` rows); reordered so "Run your first data collection" comes after the two upload steps; removed auto-hide-when-complete — now renders a green "configuration terminée" recap with all steps checked.
- [x] **Mapping page relocation** (`app.py`) — moved `meta_mapping` out of "Publicité Meta Ads" into the "Données" section, directly under "Import CSV"; relabeled "🔗 Mapping Spotify × Meta Ads (nom de campagne)".
- [x] **`meta_x_spotify.py` cleanup** — removed the redundant inline "Gérer les associations" mapping expander (duplicate of `meta_mapping.py` AND broken: its INSERT omitted the now-NOT-NULL `artist_id`). View now only reads mappings and points to the dedicated Mapping page. Removed the "Streams Cumulés" series (trace + cumsum + yaxis8 + table column). CPR now reads the real `cpr` column (fallback to `spend/results` only where `cpr` null but `results>0`). Forced number format "13 385" (separators + `tickformat=",d"`) instead of Plotly's "13.385k".
- [x] **Upload CSV doc expander** (`upload_csv.py`) — documents the 6 recognized CSV types (S4A timeline/songs/audience, Apple Music, iMusician summary/sales) + info note to run the mapping after launching collection from the home page.

### P2 — Data integrity (new, 2026-05-29)

- [x] **Meta Ads paused/archived ad-level insights silently lost** — `meta_ads_api_collector.py` fetched all 3 levels with `effective_status: ['ACTIVE','PAUSED']`; a PAUSED campaign propagates `CAMPAIGN_PAUSED`/`ADSET_PAUSED` to its ads, excluding them from `meta_ads`, so `_build_goal_maps` lacked them and `_fetch_ad_insights` dropped the ad-level insights the API returned via `if ad_id not in goal_by_ad: continue`. Campaign spend present, per-creative breakdown missing (Créatives view). Fix: per-level allowlists `_CAMPAIGN_STATUSES`/`_ADSET_STATUSES`/`_AD_STATUSES` (incl. CAMPAIGN_PAUSED, ADSET_PAUSED, ARCHIVED, IN_PROCESS, WITH_ISSUES). `meta_creatives.py` advisory corrected to instruct a FULL full-history collection + note Meta's ~37-month retention. `audit-collectors.md` gained Rule 6 (silent loss via skip-guards fed by over-narrow scope) + 2 REX entries. **Backfill of the 4 paused campaigns not yet succeeded (account throttled at session end).**
- [x] **Meta Ads throttle robustness** — `_meta_list` retried only code 17; the placement-breakdown insights call hard-failed on code 4 and the per-creative fetch stormed code 80004 (ads-management BUC). Fix: generic `_meta_retry()` retrying `_META_THROTTLE_CODES = {4,17,32,80004}` with 60→120→240s exp backoff (4 attempts), cursor materialised inside the retry; `_meta_list` + per-creative `api_get` delegate to it. New `run(fetch_creatives=False)` skips the per-creative content fetch (dominant rate-limit driver, not shown by the view); `debug_meta_ads_api.py` gains `--skip-creatives` + routes the step-3 probe through `_meta_list`. `audit-collectors.md` Rule 7. **Known limitation:** a throttle on a late aggregate call discards all already-fetched insights of the run (no per-chunk persistence) — future-brick candidate.
- [x] **Meta Ads backfill date clamp** — including ARCHIVED campaigns pulled an aberrant start_time → backfill `since=1970-01-01` → Meta error #3018 (start beyond 37 months). Fix: `_META_INSIGHTS_RETENTION_MONTHS = 36`, `history_start` clamped to `today − 36 months` in `_fetch_all_insights`.
- [x] **Meta Ads per-chunk insight persistence** — DONE 2026-06-01. `run()` now upserts config tables (campaigns/adsets/ads/creatives) up front via `_upsert_config`, then `_fetch_all_insights` persists each monthly daily-chunk and each breakdown as it is fetched through a `persist_cb` (`_persist_insights`); the old all-or-nothing end-of-run `_upsert_all` is gone (split into `_upsert_config` + `_insight_upsert_maps` single-source column/key config + `_persist_insights`). A late throttle now keeps every already-fetched month/breakdown instead of discarding the whole run. `tests/test_meta_ads_collector.py` +6 (column trimming, late-throttle-keeps-earlier-chunk durability proof, prune behaviour); 26 meta tests pass. ref: DEVLOG#2026-06-01.
- [x] **Revenue forecast NULL-probability crash (P1)** — `ml_song_predictions.dw/rr/radio_probability` can be NULL (a model that fails to score writes None, `ml_inference.py:204-237`), making the pandas Series object-dtype so `(ml_df[col]*100).round(1)` raised `TypeError: Expected numeric dtype, got object` at `revenue_forecast.py:505`. The `ml_df.empty` guard didn't cover "non-empty but all-NULL". Fix: `pd.to_numeric(ml_df[col], errors='coerce')` + `.map(lambda v: f"{v}%" if pd.notna(v) else "—")` (lines 504-506), reusing the safe pattern from `ml_performance.py:93-99`.
- [x] **iMusician derived-table staleness — roll-up wired into all 3 import paths** — `imusician_monthly_revenue` is DERIVED from `imusician_sales_detail` via `rollup_sales_to_monthly` (`src/utils/imusician_rollup.py`), but the roll-up hook lived only in the Streamlit path. The user's full 2023-01→2026-01 export (~212€, 4326 rows) had been imported by the watcher DAG with no roll-up → monthly_revenue stuck at 13 months / 11.56€ while sales_detail held 211.87€ (dashboard ~5% of real revenue, no error). Fix: added the roll-up to `imusician_csv_watcher.py::process_csv_files` (per dag_run.conf artist_id) and `debug_imusician_csv.py::step_5_real_upsert` (per distinct artist_id), both best-effort/non-blocking. One-time backfill for artist 1 → monthly_revenue now 37 months, 2023-01→2026-01, 211.90€ (all `source='import'`). REX + Rule 8 added to `audit-collectors.md`.

### P2 — Data integrity (new, 2026-05-29 — Meta double-count + single-writer)

- [x] **Meta campaign-grain breakdowns double-counted spend (~2×)** — `meta_insights_performance_country/placement/age` showed ~2× the real spend. Root cause: a DUAL WRITER — the one-time Dec-2025 legacy Meta CSV stack wrote the same tables as the API collector with incompatible conventions (an aggregate `country='All'`/`placement='All'` total row doubling country/age, and French placement labels `Reels Instagram` vs API snake_case `instagram_reels` → distinct conflict keys, both kept). Same legacy import that earlier produced the `cg:`/`a:` prefixed-ID duplicates. Fix (DEFINITIVE): (1) cleaned spurious rows (DELETE `'All'` buckets + non-snake_case placement rows across the 6 campaign breakdown tables, all artists) → all grains reconcile to ~3088€ (= day total); (2) patched `meta_insight_csv_parser` to skip aggregate/total rows (defense); (3) ARCHIVED the entire legacy Meta CSV stack — 8 files → `archive/legacy_meta_csv/` (DAGs `meta_config_dag`/`meta_insights_dag`, watchers `meta_csv_watcher`/`meta_insight_watcher`, parsers, debug scripts) + README; removed `TestMetaCSVParser` from `tests/test_parsers.py`; repointed ALL dashboard/alerting refs (app.py sync, home.py, useful_links.py, airflow_kpi.py, credentials/_core.py, alert_root_cause.py, alert_monitor.py + debug) to the canonical `meta_ads_api_daily`; added `archive/` to `.dockerignore`. RESULT: Meta tables now have exactly ONE writer → double-count cannot recur. `audit-collectors.md` gained Rule 8 "one canonical writer per table" + dual-writer REX. ref: DEVLOG#2026-05-29.
- [x] **Meta campaign-grain breakdowns keyed by `campaign_name`** — DONE 2026-06-01. New `_prune_renamed_campaigns()` (called in `run()` after `_upsert_config`, non-insights_only only) deletes campaign-grain insight rows whose `campaign_name` is no longer returned by the API (ad/adset grains key by id, immune). Guarded: empty/failed fetch is a no-op (never a mass delete); table names validated via `validate_table()` against the allowlist (rule #8); DELETEs artist-scoped, `campaign_name <> ALL(%s)` parameterized. `_CAMPAIGN_GRAIN_TABLES` frozenset = the 10 affected tables. Test coverage in `tests/test_meta_ads_collector.py`. ref: DEVLOG#2026-06-01.

### P3 — UX / Features (new, 2026-05-29 — Road to Algorithms overhaul)

- [x] **WAVE 1 — lifecycle & benchmark tab** (`trigger_algo.py`) — 6th tab "📉 Cycle de vie & Benchmark" (cohort lifecycle/standardization band charts P25/median/P75 by song age-in-weeks, live track age overlaid). New GLOBAL read-only table `algo_lifecycle_benchmark` (`src/database/benchmark_schema.py`, `migrations/035`, `init_db.sql`) — non-tenant, NOT in `_ALLOWED_TABLES`, seeded PROVISIONAL (18 qualitative rows, `total_stream_median` NULL). Threshold-honesty rework: `ELBOW_THRESHOLDS_28D` ({DW:137,RR:130,RADIO:639}) vs `HEURISTIC_GOALS` (Radio fallback); dynamic-imputation caveat (6/13 features imputed → probabilities indicative); `show()` migrated to `view_session()`. Offline `machine_learning/export_lifecycle_benchmark.py` computes real standardization ratios from `data_anon.csv` (path to replace the seed). ref: DEVLOG#2026-05-29.
- [x] **WAVE 2 — algo knowledge layer + shared ML widgets** — `src/dashboard/utils/algo_knowledge.py` (PURE, algo-keyed: `ALGO_FEATURE_ZONES`/`ALGO_CALIBRATION_BANDS`/`ALGO_MODEL_METRICS` + helpers; only Discover Weekly populated, RR/Radio plug in later; `tests/test_algo_knowledge.py`, 8 tests). `src/dashboard/utils/ml_widgets.py` (Streamlit/Plotly render: classification scorecard shared by `trigger_algo` Modèle tab AND admin `ml_performance.py`; feature decision gauges + next-best-lever + fake-buzz guard + calibration badge in the Explainabilité tab). `ml_performance.py` gained a "Scorecard classification" tab. 247 pytest pass (239+8), ruff clean, AppTest render smoke OK. ref: DEVLOG#2026-05-29.
- [x] **WAVE 3 — Radio algorithm support + Prescriptive Coach** — `algo_knowledge.py`: `RADIO_FEATURE_ZONES` (9 features; `DaysSinceRelease` INVERTED vs DW honeymoon→flat-negative; velocity stricter 1.5 vs DW 1.2; catalog sweet-spot 10–20), `ALGO_MODEL_METRICS["RADIO"]` (AUC 0.941, TN47/FP7/FN7/TP41, n=102, real lift vs 0.529 baseline — NO calibration bands, honest), `ALGO_LABELS`, `populated_algos()`, `build_coach_actions()` (ranked prescriptive to-do list, velocity-smooth first), NEW `velocity_penalty_threshold(algo)` single-source helper. `ml_widgets.py`: `render_next_best_lever → render_coach` (ranked list + Discovery-Mode prompt for Radio). `trigger_algo.py`: stacked all-algos rendering (loop `populated_algos`) in Explainabilité + Modèle tabs; NEW `_show_velocity_budget_advice` budget cross-link (velocity-too-high → ~30% spend cut) routed through `ak.velocity_penalty_threshold` (no hardcoded 1.2/1.5). `tests/test_algo_knowledge.py` +12 (Radio zone shapes, inverted age, coach ranking/exclusions, threshold single-source contract). 258 pytest pass (1 skip), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 3 fix — failed-Edit dead code passed tests+ruff** — a mid-session Edit error left `_show_velocity_budget_advice` defined-but-never-called; pytest green + ruff clean (F-rules don't flag unused module-level functions) hid that the whole Coach+budget feature was non-functional until the call site was wired in a follow-up. REX added to `check_python_syntax.py` (after an Edit errors, verify wiring landed). ref: DEVLOG#2026-05-30.
- [x] **WAVE 3 fix — velocity cutoff single-source** — `_show_velocity_budget_advice` originally hardcoded the velocity cutoff (1.2/1.5), duplicating the zone logic in `algo_knowledge`. Fixed via `velocity_penalty_threshold()`; gate + displayed numbers both routed through it. REX added to `dashboard-view.md`. ref: DEVLOG#2026-05-30.
- [x] **WAVE 4 — Release Radar (RR) populated** — RR was the reserved-but-empty algo slot (already wired in ALGO_LABELS, `populated_algos()` order, palette, `rr_classifier` model path). `algo_knowledge.py`: `RR_FEATURE_ZONES` (6 features), `"RR"` registered in `ALGO_FEATURE_ZONES` (order DW/RR/RADIO) + `ALGO_MODEL_METRICS["RR"]` — UI lights up automatically with ZERO view-code changes (trigger_algo Algos/Modèle tabs, ml_performance scorecard grid). Zones sourced from offline SHAP zoom ARTIFACTS (`mlruns/4/.../5_SHAP_Zoom_*_RR.png`), not prose: `DaysSinceRelease` is a firing WINDOW (dip 0–7d, sweet 7–40d, then closes) not an on/off cliff; `ReleaseConsistencyNum` is feature #4 (absent from notes, rewards spaced releases); `DiscoveryMode` dead-flat. Scorecard pixel-verified vs `1_Dashboard_Performances_RR.png` (confusion {TN76,FP6,FN4,TP16}, AUC 0.961, AP 0.88, lift_top10 5.1). `PlaylistAddsLast28Days` marked `divergent + actionable:False` (negative SHAP = chronological song-age confound, NOT a causal lever — shown in gauges with warning, excluded from coach). NO RR calibration bands (no artifact exists; `test_rr_has_no_calibration_bands` documents the gap). `ml_widgets.py`: `divergent` gauge message made data-driven (was hardcoded wrong "bornée à ≤1.0") + per-spec `divergent_note` caption. `ml_performance.py`: scorecard loop routed through `ak.populated_algos()` (DRY, removed 3rd hardcoded tuple). `tests/test_algo_knowledge.py` +9 (9 RR tests + 1 cross-algo coherence guard). 267 pytest pass (258→+9), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 5 — volume (regressor) decision layer** — distinct from the classification/entry story: answers "once a song triggers, how much volume?". `algo_knowledge.py`: `ALGO_VOLUME_ZONES` (DW only, regressor-SHAP-derived — raw fuel StreamsLast7Days/NonAlgoStreams28Days drives volume, saves/playlist-adds flagged `volume_flat`: "quality buys the ticket, volume writes the cheque"), `ALGO_REGRESSOR_METRICS`, `FORECAST_FLOOR_DISCLAIMER`, `volume_scaling_threshold(algo)`, and registry-aware `_spec`/`zone_for_value`/`decode_feature_value` (one machinery serves both zone sets via `registry=`). `ml_widgets.py`: `render_floor_forecast`/`floor_forecast_text` (reframes `*_streams_forecast_7d` as a conservative FLOOR), `render_regressor_badge` (hungry/conservative), `render_volume_gauges`, `render_shap_narrative` (NL SHAP autopsy); `_render_one_gauge`/`_live_value` registry-threaded. `trigger_algo.py`: floor wording in `_display_prob_bar`, volume gauges in coach loop, regressor SHAP autopsy in Explainabilité, static organic budget-scaling section (≥6000 organic/28j, labelled "cible, pas écart live"). `revenue_forecast.py`: floor column labels "(plancher ≥)" + caption. Tier B (zones + scaling target) runs in rule+static-target mode and auto-upgrades at Phase 2 (NonAlgoStreams28Days_log/DiscoveryMode/RadioCount still imputed to 0.0). `tests/test_algo_knowledge.py` +`TestVolumeZones`/`TestVolumeScalingThreshold`/`TestRegressorNote` (broken placeholder completed). 280 pytest pass (267→+), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 6 — Radio volume regressor wired + knowledge encoded** — the Radio regressor (MLflow exp 6, run `16155f62`) existed as trained artifacts but was unwired in 5 places; all closed. **Pipeline (P2):** `ml_inference.MODEL_PATHS["radio_regressor"]` + `score_song` now computes `radio_streams_forecast_7d` (capped ≥0); `ml_scoring_daily` update_cols + `ml_song_predictions.radio_streams_forecast_7d INTEGER` (init_db.sql, create_missing_tables.sql, idempotent `migrations/036_ml_radio_streams_forecast.sql` — **needs `make migrate` on live DB**); `ml_performance._MODELS` registers exp 6 (17 PNG artifacts now visible). **Knowledge (P3):** `algo_knowledge.RADIO_VOLUME_ZONES` (StreamsLast7Days amplifier + the FIRST non-flat catalogue lever `HowManySongsDoYouHaveInRadioRightNow` = superstar effect; DiscoveryMode/Saves/PlaylistAdds/ListenersStreamRatio `volume_flat`), `ALGO_REGRESSOR_METRICS["RADIO"]` (R²=0.63 + viral-cap framing: +400k outlier under-predicted → floor not ceiling), `radio_discovery_recovery_note()` (margin-recovery: turn Discovery Mode off past cruising velocity to reclaim 30% royalties). **View (P4):** radio forecast in `_display_prob_bar`, Radio SHAP volume autopsy expander, recovery note in coach loop, 3rd "Radio forecast" column in Actual-vs-Predicted, `revenue_forecast.py` floor column. **Long-term fix:** RadioCount marked `live_unavailable` (imputed-0 → pedagogic expander, not a fake live "0 titres" gauge — the imputed-0 anti-pattern); `render_volume_gauges` pedagogic caption made algo-generic (was DW/NonAlgoStreams-hardcoded). `tests/test_ml_inference.py` (6-model + key contract + regenerated frozen baseline), `test_algo_knowledge.py` +3 RADIO tests. 283 pytest pass (280→+3), ruff clean. ref: DEVLOG#2026-05-30.
- [x] **WAVE 7 — Release Radar volume regressor SUPPRESSED (R²=0.32, product-protective)** — opposite of WAVE 6: the RR volume regressor (exp 7) scores R²=0.32 (SHAP = flat line at zero broken by 2-3 viral outliers; followers/recent-streams/saves/playlist-adds all flat — RR volume is notification-CTR noise, not algorithmic). Per the user's data-science verdict, the forecast must NOT reach users (false financial promise) — RR ships **classification-only** (AUC 0.96). **Knowledge (P3):** `ALGO_REGRESSOR_METRICS["RR"]` with `volume_reliable: False` + `r2: 0.32` + `suppressed_note` + interpretation; new single-source helpers `volume_forecast_reliable(algo)` (default True, explicit-False gate — no `if algo=="RR"` hardcoding) and `volume_suppressed_note(algo)`. **Gate the 2 user surfaces (P3):** `trigger_algo._show_ml_section` passes `None` as the RR forecast + shows the "abonnés notifiés, volume non prédictible" caption; `revenue_forecast.py` drops the `rr_streams_forecast_7d` floor column when unreliable + updated caption. **Diagnostics kept honest (P4):** the Modèle-tab RR Actual-vs-Predicted scatter + admin `ml_performance` exp 7 artifacts stay, now captioned "R²=0.32 — diagnostic, PAS une prévision". **No pipeline change:** `rr_streams_forecast_7d` still computed/persisted (diagnostics read it); only display is gated. `tests/test_algo_knowledge.py`: `regressor_note("RR")` now non-None + `test_volume_forecast_reliability_gate` + `test_volume_suppressed_note`. 285 pytest pass (283→+2), ruff clean. ref: DEVLOG#2026-05-31.
- [x] **RR (+ RADIO) calibration bands** — DONE 2026-06-05 (WAVE 8 — independent re-derivation). Instead of a notebook PNG, the bands are measured empirically from v3 out-of-fold group-CV calibrated probabilities (`machine_learning/analysis/05_calibration_bands.py`): per-bin observed positive rate → `ALGO_CALIBRATION_BANDS["RR"]` and `["RADIO"]` now populated. v3's OOF-Platt calibration is well-behaved, so most bands read "fiable : score ≈ réalité" (a big honesty upgrade over v1's over-confidence warnings). `test_rr_has_calibration_bands` / `test_radio_has_calibration_bands` updated.
- [x] **Replace provisional `algo_lifecycle_benchmark` seed with real export** — DONE 2026-06-05. Re-seeded from `data_anon.csv` via the conditioned export (`migrations/041_lifecycle_benchmark_v2.sql`, `dataset_version='v2'`): conditions on the triggering cohort so DW medians are no longer crushed to 0 and `total_stream_median` is populated. Loader prefers v2 (falls back to v1). **Needs `make migrate`.** See WAVE 8 follow-ups below.
- [x] **Phase 2 — live per-algorithm stream capture from S4A** → **CLOSED AS MANUAL (2026-06-10, ADR-004)** — see canonical entry "Phase-2 data acquisition" in Long-term ML hardening below. S4A has no source-split export; auto-capture rejected, manual entry shipped (mig 052). Extra context specific to this view: `s4a_song_timeline` is total-streams only, so per-tenant *live* lifecycle curves (vs the static v2 cohort) need the per-algo split; the volume layer's imputed-0 features (`NonAlgoStreams28Days`, `DiscoveryMode`, `RadioCount`) and the Radio superstar lever auto-upgrade from rule/static-target mode to live deltas once Phase 2 lands. (Surfaced 2026-05-29.)
- [x] **`ListenersStreamRatio28Days_adj` inverted + clamped (P2) — FIXED** — `ml_inference.build_features` now computes `streams/listeners` unclamped (was `min(listeners/streams, 1.0)`), matching the SHAP 2.2–4 sweet-spot; `divergent` flag removed from `algo_knowledge`. (2026-05-29.)
- [x] **Recover imputed DW features** — Saves (`s4a_songs_global.saves`, 28d window), PlaylistAdds (`s4a_song_playlist_adds`), ReleaseConsistency (median weeks between real release dates in `track_release_reference`, NOT the all-identical backfilled timeline first-appearance) now computed live; `_IMPUTED_FEATURES` reduced to the 3 genuinely sourceless (NonAlgoStreams28Days → Phase 2, RadioRightNow, DiscoveryMode). REX in `dashboard-view.md`. (2026-05-29.)
- [x] **`DaysSinceRelease` uses backfilled timeline MIN(date)** — FIXED 2026-05-31. `ml_inference.build_features` now resolves the per-song release date from `track_release_reference` (matched on `normalize_track_title(song)` → `match_key`), falling back to the timeline `MIN(date)` only when no reference row matches. `ReleasePhaseEarly` follows automatically (derived from `days_since`). Note: stored `ml_song_predictions.features_json` keep the stale value until the next `ml_scoring_daily` re-score (live trigger_algo render is correct immediately).

### P3 — ML re-derivation (WAVE 8, 2026-06-05 — independent rebuild from data_anon.csv → v3)

- [x] **Independent ML re-derivation + v3 pipeline** — full-takeover rebuild from `data_anon.csv` as a methodology comparison vs `train.py`/v2. Reproducible scripts `machine_learning/analysis/{01_audit,02_validate,03_train,04_forecast_variant,05_calibration_bands,06_scorecard_metrics}.py` + reports (`audit.md`, `validation.md`, `modeling.md`, `forecast.md`, **`COMPARISON_REPORT.md`**). **Findings:** (1) 30.7% of rows are repeat songs (one has 22 snapshots) → validation switched to **StratifiedGroupKFold by `NameID`**; the leakage inflation is modest (~0.02 AUC), so v2's AUCs hold up. (2) **SMOTE mildly hurts** (RR AP 0.80→0.74) → dropped. (3) Calibration was fit on the test split → v3 fits **Platt on out-of-fold** predictions. (4) **All volume regressors are weak** under honest CV (DW R²<0, RR 0.23, Radio 0.33 with log target) → DW + RR volume suppressed, Radio = floor only; regressors switched to **log1p target** (inference applies `expm1`). (5) Per-algo framing: **RR = true forecast** (AUC 0.92 from release-day metadata alone), **DW = lever model** (saves + playlist-adds), **Radio = momentum diagnostic** (collapses without concurrent streams). **Shipped:** `models/v3/` (13-feature contract KEPT per user — feature-drop deferred to Phase 2), `ml_inference.MODEL_VERSION="v3"` + expm1 + DW-volume suppression, `algo_knowledge` refreshed (group-CV scorecard metrics + `auc_ci`, honest regressor metrics, **RR+RADIO calibration bands**, per-algo interpretation copy), `ml_widgets` scorecard CI band, `_common` DW/RR/RADIO calibration badges. Tests re-baselined (`test_ml_inference` v3, `test_algo_knowledge` v3). 300 pytest pass, ruff clean. **Note:** keeping 13 features means the NonAlgoStreams28Days/RadioCount train/serve skew remains → Phase-2 live data stays a priority (UI keeps the imputation caveat). ref: DEVLOG#2026-06-05.
- [x] **Discoveries → app features (WAVE 8 part 2)** — 2026-06-05. Four features shipped from `COMPARISON_REPORT.md` §5: (A) **Pre-release RR estimator** — new metadata-only RR model `models/v3/rr_premiere_classifier.ubj` + `premiere.json` (AUC 0.923 [0.88–0.96] group-CV, `analysis/07_train_premiere.py`); `ml_inference.estimate_rr_prerelease()`; ephemeral what-if widget `ml_widgets.render_prerelease_rr_estimator()` (inputs + RR-odds curve over J0–J40) in the Algos tab. (B) **Expected-value ROI** — `_tab_budget_roi._render_expected_value()` = cost-per-trigger ÷ calibrated P(trigger) = honest risk-adjusted cost + best-bet pick. (C) **PI group-CV validation** — `analysis/08_validate_pi.py`: R²=0.923 [0.88–0.94], MAE 2.0 pts → PI is genuinely robust (not optimistic); UI help text + `metrics.json pi` block updated. (D) **DiscoveryMode coverage** — `build_features` stamps `discovery_mode_known`; `_show_imputation_caveat` distinguishes a real opt-out from a missing-data 0 and prompts entry. `MODEL_PATHS` now 8 models. 302 pytest pass, ruff clean. ref: DEVLOG#2026-06-05.

### P4 — ML follow-ups (WAVE 8, 2026-06-05)

- [x] **Quantified DW levers (local sensitivity)** — DONE 2026-06-05. `ml_inference.local_sensitivity()` sweeps one lever of the current song and recomputes the calibrated probability (upper bound = mean+3σ for resolution); `ml_widgets.render_lever_sensitivity()` plots the per-song curve + the marginal gain to target, wired into the Explainability tab for DW (the lever model). Honest *local* partial dependence — explicitly captioned "not a global rule" (XGBoost is non-linear).
- [x] **Lifecycle benchmark re-seed (conditioned)** — DONE 2026-06-05; **supersedes the provisional-seed item above**. `export_lifecycle_benchmark.py` now conditions on the TRIGGERING cohort (clears the elbow: DW>137 / RR>130 / Radio>639, min 5 songs/bin) → meaningful medians + populated `total_stream_median` (was NULL). `migrations/041_lifecycle_benchmark_v2.sql` seeds `dataset_version='v2'`; the loader prefers v2 and falls back to v1 (no regression pre-migrate). **Needs `make migrate` to go live.** Semantic shift: the curve now reads "among songs that DID trigger"; RR spans only 0–10 wk (fires near release).
- [x] **11-feature contract — RESOLVED by serving live, not dropping (2026-06-11).** The skew fix had two doors (drop the 2 features, or serve them); migration 052 already opened the *serve* door (manual S4A entry → `s4a_song_nonalgo_streams` / `s4a_artist_radio_count`, read by `ml_inference.build_features`). This session closed the loop end-to-end: `build_features` now stamps `nonalgo_known` / `radio_known` (mirroring `discovery_mode_known`); a centralized `algo_knowledge.feature_live_available(spec, feats)` un-imputes a manual-source feature once entered; `_show_imputation_caveat`, the gauges (`ml_widgets._live_value`), the lever filter and `build_coach_actions` all respect it. **A genuine entered 0 (e.g. 0 songs in Radio) now counts as real data, not imputation** → the "X/13 imputed" warning fires only when truly unfilled. Skew gone for filled tenants; keeping 13 features is correct. Verified live: `ml_scoring_daily` re-run persisted `*_known=true` on all 11 active songs. 444 tests pass. ref: DEVLOG#2026-06-11.

*(Phase-2 live per-algorithm capture and per-tenant evaluation + live-outcome retraining are tracked once in "Long-term ML hardening (roadmap)" below — not duplicated here.)*

### P3 — UX / Features (new, 2026-05-29 — Meta analytics expansion)

- [x] **Creative analytics charts** (`meta_creatives.py`) — reorganised into 6 tabs (Classement/Comparaison/Funnel/Évolution/Fatigue/Activité): #1 bubble scatter (spend×CPR, size=impressions, color=CTR), #2 ad-fatigue dual-axis (frequency↗ vs CTR↘), #3 funnel (impressions→clics→résultats, go.Funnel), #4 efficiency bars (CTR/CPM/CPC), #5 weekly density heatmap, #6 cumulative spend area; plus a per-creative multi-metric timeline (one Y-axis/metric + legend toggle, weekly down-sampling >120d, derived CPR). All from `meta_insights` (ad grain). New "🎯 Ciblage vs Performance" (#9) section in `meta_ads_overview.py` (meta_adsets targeting × CPR via `pareto_spend_cpr`). ref: DEVLOG#2026-05-29.
- [x] **Multi-grain breakdowns (ad & adset grain)** — collector `meta_ads_api_collector.py`: `_build_goal_maps` returns `goal_by_adset`; new `_fetch_breakdown(level, id_field, breakdown, goal_by_entity)` helper (reuses `_extract_perf/_extract_eng` + FK guard, +6 API calls/run); `_fetch_all_insights` +12 keys, `_upsert_all` +12 DRY entries. 12 NEW tables `meta_insights_{performance,engagement}_{ad,adset}_{country,placement,age}` (migration 032, registered in `_ALLOWED_TABLES`, documented in `meta_insight_schema.py`) — lifetime aggregates (no date col) → filtered by entity, not period. NEW view `meta_breakdowns.py` ("🌍 Breakdowns Meta", app.py nav+routing): campaign→adset→creative cascade, dimension × metric-family selectors, choropleth (new `dashboard/utils/geo.py` ISO-2→ISO-3 pycountry wrapper) + Pareto (new shared `dashboard/utils/charts.py::pareto_spend_cpr`). `dashboard-view.md` Pitfalls #7 (aggregate tables no date) + #8 (choropleth ISO-2→ISO-3). ref: DEVLOG#2026-05-29.
- [x] **Recency-ordered entity filters** — entity selectboxes now list most-recent-first via SQL `ORDER BY <recency> DESC NULLS LAST` (never Python `sorted()`): meta_breakdowns cascade (start_time/created_time), meta_creatives (campaign/timeline/fatigue/funnel), meta_x_spotify (MAX(day_date)), meta_mapping `_load_campaigns` (start_time), ml_performance (days_since_release). Deliberate non-recency: export_pdf (streams DESC), meta_mapping `_load_tracks` (no date col). `dashboard-view.md` Pitfall #9 + REX. ref: DEVLOG#2026-05-29.

### P3 — UX / Features (new, 2026-05-28 — multi-view UX pass)

- [x] **Apple Music song filter → single-select** (`apple_music.py`) — `multi=False` in `EntitySpec`, defaults to latest release.
- [x] **YouTube subscriber axis legibility** (`youtube.py`) — removed `fill='tozeroy'`, added tight computed y-range + SI `tickformat` so daily evolution is visible.
- [x] **Hypeddit single-page layout** (`hypeddit.py`) — merged the 3 `st.tabs` (Saisie/Stats/Historique) into one scrolling page (stats + history first, manual entry last). New helpers `_render_global_stats` / `_render_history` / `_render_entry_form`.
- [x] **Distributeur tab cleanup** (`imusician.py`) — removed the "Saisie" and in-view "Import CSV" tabs (redundant with the Import CSV page); kept Données + ROI; dropped dead `_upsert_revenue`.
- [x] **App-level credential status** (`credentials/_core.py` + `_render.py`) — new `app_level_configured()`: Spotify/YouTube show "Configuré (clé plateforme)" when keys exist in env/config.yaml even without an `artist_credentials` row (mirrors the collectors' DB-then-env fallback).
- [x] **Billing 3-tier rework** (`billing.py` + `stripe_schema.py`) — 3 columns (Free/Basic/Premium); removed the comparison dataframe; ungreyed the upgrade CTA (enabled button + contact message when `STRIPE_CHECKOUT_URL` unset). `PLAN_FEATURES['basic']` now includes `revenue_forecast` (ML access moved into Basic); `ALWAYS_ACCESSIBLE` now includes `process_guide`.
- [x] **Guide de démarrage page** (`process_guide.py`, NEW) — "📋 Guide de démarrage" view with downloadable PDF (WeasyPrint, HTML fallback). `app.py` nav: Données section reordered Guide → Credentials → Import CSV → Mapping → Santé (Credentials moved out of the account section).
- [x] **Welcome trial + plan-change audit** (`register.py`, `verification_email.py`, `src/utils/plan_history.py` NEW, `migrations/029`) — every new signup auto-grants a 30-day premium trial (`WELCOME_TRIAL_DAYS`) via `promo_plan` precedence; new `send_welcome_email()` recaps first actions; new append-only `subscription_plan_history` table (migration 029, idempotent backfill) with `log_plan_change()` write hooks in `register.py` (welcome_trial/promo), `admin.py` (admin_edit), `api/routers/stripe_webhook.py` (stripe_webhook). Migration 029 applied to local DB.
- [x] **Admin plan-evolution + users views** (`alerts.py`) — plan-evolution stacked-area chart (from `subscription_plan_history`) + users table (email + signup date + effective plan).

## Completed

All bricks (1–19) fully implemented. Session implementation notes were archived in `saas-db-migration/checklist.md` (deleted 2026-03-23 — no longer needed).

- [x] C5 — Benchmark VPS (sizing + topologie) ✅ 2026-06-13 (décision figée + prod live sur Hetzner CPX32)
- [x] C6 — Benchmark nom de domaine + accès public ✅ 2026-06-13 (streamlytics.fr live + Cloudflare durci)
- [x] D — Déploiement + pentest ✅ 2026-06-13 (prod live, red-team complet, classes `api-router-schema-drift` + `csv-formula-injection` cataloguées)
- [x] R3 — 2 collectors `return None` ✅ 2026-06-14 (youtube:45 chaîne-introuvable → `raise ValueError` + test de non-régression ; instagram:294 = skip par-item légitime confirmé)

---

## ML decision layer (2026-05-31, WAVE 8)

- [x] **Scaler-free retrain + PI model** — `machine_learning/train.py`, models in `models/v2_noscaler/`; `pi_forecast_7d` column (migration 037). ✅ 2026-05-31
- [x] **B2 "Portes par PI"** — per-song positioning on the PI→trigger curves (`threshold_tables.json`). ✅ 2026-05-31
- [x] **Verdict banner 🔴🟠🟢** — consolidated kill/optimize/scale on argmax of the 3 probs. ✅ 2026-05-31
- [x] **Budget pacing calculator** — spread budget over the eval window to avoid the velocity spike. ✅ 2026-05-31
- [x] **Snowball radar** — catalogue scan (radio_probability ≥0.5) bypassing the imputed-0 radio-count feature. ✅ 2026-05-31
- [x] **Resurrection data foundation** — `s4a_song_saves_daily` table + daily writer (migration 038). ✅ 2026-05-31
- [x] **Resurrection alert (activation)** — `detect_saves_resurrection` wired into the `alert_monitor` consolidated email as a green "opportunities" section. Dormant until ~2 weeks of saves history accrue. ✅ 2026-05-31
- [x] **Probability calibration (Platt)** — sigmoid calibrator per classifier (`calibration.json`), applied in `score_song`; verdict bands now real probabilities. ✅ 2026-05-31
- [x] **Drift detection foundation** — training `feature_stats` exported; `ml_inference.check_drift` flags out-of-distribution inputs, logged per song in the scoring DAG. ✅ 2026-05-31
- [x] **Empirical threshold reconciliation** — `derive_thresholds.py` computes success-rate knees from data; recalibrated 5 DW zones in algo_knowledge (velocity no longer penalises 1.2-2.0; saves 50→165; organic→3900; adds→175; followers bonus→2650). ✅ 2026-05-31
- [x] **Phase strategy + Discovery Mode protocol + variable hierarchy** — `_show_phase_strategy`, `_show_discovery_mode_protocol`, `_show_feature_importance` (gain-ranked) in trigger_algo. ✅ 2026-05-31
- [x] **ML KPI gaps** — LIME local explanation (`_show_lime_explanation` + lime_background.json + `lime` dep), Meta-lever scoring on real Meta perf (`_show_meta_lever_scoring`), calibrated budget-to-trigger (`_TRIGGER_STREAM_TARGETS`), PI-driven breakeven (`_show_pi_breakeven`). 6/7 requested graphs already existed. ✅ 2026-05-31
- [x] **PI line + 28d gate** — Popularity Index added to the main algos chart; `_GATE_28D` + `_show_28d_gate` (28d streams/listeners vs validated per-algo thresholds, DW 9200/4100). ✅ 2026-05-31
- [x] **Drift surface + alerting** — `_show_drift_status` (OOD features per track, Explainabilité tab) + `check_drift_anomalies` task in alert_monitor (systemic drift >50% of predictions → email). `check_drift` now excludes the imputed features (permanently OOD by design). ✅ 2026-05-31

## P3 — Product usage tracking (spec'd 2026-06-09, Option A — homegrown)

Goal: know what end-users (artists) actually do in the app (pages visited, features
used, drop-offs, dead features). **Decision: build a lightweight server-side event log
in Postgres rather than PostHog** — Streamlit's rerun/DOM model makes PostHog's JS
autocapture/session-replay unusable (see Deferred § below); a homegrown table reuses the
DB + auth + admin-view stack already in place, with zero third-party egress / RGPD cost.

- [x] **`usage_events` table + tracking hook + admin view** — SHIPPED 2026-06-09
  (`migrations/045_usage_events.sql`, `src/dashboard/utils/usage_tracker.py` fail-silent
  `track()`/`track_page_view()`, `views/usage_analytics.py` admin view). Spec below kept for
  reference.
- [x] (spec) **`usage_events` table + tracking hook + admin view** — original spec:
  - **Schema** (`migrations/045_usage_events.sql` + `init_db.sql` + add to `_ALLOWED_TABLES`):
    `usage_events(id BIGSERIAL PK, artist_id INT, role TEXT, session_id TEXT, event TEXT NOT NULL,
    page TEXT, ts TIMESTAMPTZ DEFAULT now(), meta JSONB)`. Indexes on `(ts)`, `(artist_id, ts)`,
    `(event)`. Use UTC-aware `ts` (rules/python.md). Retention: prune > N months via a tiny
    step in an existing daily DAG (or a `DELETE` in `data_quality_check`).
  - **Writer** (`src/dashboard/utils/usage_tracker.py`, NEW): `track(event, page=None, meta=None)`
    → single INSERT via `PostgresHandler.execute_query` (autocommit). **Fail-silent** (try/except,
    never raise — telemetry must NOT break or slow a page; this is the deliberate inverse of the
    collector "must raise" rule). `distinct_id = artist_id` from `get_artist_id()`; `session_id`
    from a `st.session_state['_session_id']` set once (uuid4).
  - **Page-view hook**: in `app.py::main()`, right after `page = show_navigation_menu(role)`
    (line ~313, the single routing choke-point), call `track('page_view', page=page)` **only when
    the page changed** vs `st.session_state['_last_tracked_page']` — Streamlit reruns on every
    widget interaction, so logging every rerun would massively inflate counts.
  - **Key action events** (explicit `track()` calls): `pdf_generate`, `csv_export`,
    `dag_trigger`, `login`, plus `error` (wrap nothing new — just call where errors are already
    caught). Keep the taxonomy small and stable.
  - **Admin view** (`views/usage_analytics.py`, admin-only — add to `_NAV_SECTIONS` admin section
    + `_ADMIN_ONLY` + routing): top pages (bar), events/day (line), active artists, least-used
    pages ("dead features"), simple funnel (login→page→action). Reuse `kpi_helpers`/`charts.py`
    patterns; gate behind `is_admin()`.
  - **RGPD**: first-party, no egress. The app already has a cookie notice
    (`_show_cookie_notice`) + a `?page=privacy` policy — extend the policy text to mention
    in-app usage analytics. No new consent vendor needed for first-party functional analytics,
    but confirm wording.
  - **Verification**: migrate; click around → rows land; rerun a page (widget interaction) →
    NO duplicate page_view; admin view renders; render-smoke + a small unit test on
    `usage_tracker.track` (fail-silent on bad DB). Effort ≈ ½–1 j.

## Pré-déploiement program (2026-06-09)

Ordered A→B→C→D. **Deployment (Docker containerization + Hetzner) is the LAST phase** and is
parked in `.claude/dev-docs/deployment.md` (out of current scope per user). Pricing is now
**2 tiers** free(0€)/premium(10€) — basic retired (migrations 047/048).

- [x] **A — Validations & gate** : 375 tests verts ; tiers free/premium validés + alignés
  (code+DB+billing/upgrade) ; vue admin **📊 Supervision** (business + fraîcheur données) ;
  leak Export-PDF des sections premium corrigé (`PREMIUM_SECTIONS`).
- [x] **B1 — Mapping cross-plateforme + suggestions** (LIVRÉ 2026-06-09 ; **consolidé 2026-06-11**) :
  `migrations/049_track_platform_link.sql`, moteur pur `src/utils/track_mapping_suggest.py`
  (+15 tests), vue `views/track_mapping.py` — 3 onglets : suggestions par plateforme
  (S4A/Spotify/Apple/SC/YT, accept/reject + bulk), **Meta campagnes** (title-sim + date-proximity,
  écrit `campaign_track_mapping` en `_`-form), vue unifiée. Validé sur données réelles.
  **2026-06-11** : fusion `track_mapping` + mapping Meta en **une seule vue `meta_mapping` à 2 onglets**
  (« 🎵 Titres & couverture » + « 📣 Campagnes Meta »), grille couverture ✅ verte, bug confiance
  « toujours 0 % » corrigé (ProgressColumn ×100 à l'affichage, DB reste [0,1]), campagnes 0 € pré-cochées
  Rejeter (tombstone `campaign_mapping_rejected`, mig 054). Vue splitée en package `meta_mapping/`
  (`_common`/`_tracks`/`_campaigns`/`__init__`, move-only). Garde-fou i18n orphelins (`test_i18n_orphans.py`).
- [x] **B1bis — SACEM + revenu consolidé** (2026-06-11) : parser `sacem_parser.py` (xlsx relevé de compte),
  table `sacem_statement` (mig 055), import xlsx + how-to ; royalties brutes (`repartition`) dans le ROI +
  trace SACEM distincte sur le graphe prévision revenus. **VIEW `v_artist_monthly_revenue`** (mig 056) consolide
  iMusician+DistroKid+SACEM (fin du copier-coller UNION sur ~6 sites ; VIEW read-only hors `_ALLOWED_TABLES`).
  Dépense « Hypeddit » fantôme (budget Meta mal interprété) retirée de tous les points ROI → `total_spend = meta_spend`.
- [x] **B2 — DistroKid** (phases 1+2 livrées 2026-06-10) :
  **Phase 1 — saisie manuelle** : table `distrokid_monthly_revenue` (migration 050,
  `distrokid_schema.py`) ; vue Distributeur partagée (`imusician.py`) — sélecteur
  iMusician/DistroKid/Tous (chart empilé), formulaire de saisie mensuelle EUR
  (défaut = mois précédent), suppression distributor-aware ; ROI Breakheaven somme
  les 2 sources (`kpi_helpers` UNION ALL ×4) ; +5 tests (`test_distrokid_revenue.py`).
  **Phase 2 — import « bank details »** : parser `src/transformers/distrokid_parser.py`
  (TSV **ou** CSV sniffé, fallback latin-1, schéma 15 col post-juillet-2025 + legacy
  `Song/Album`, dédup pré-upsert) ; table `distrokid_sales_detail` USD NUMERIC(14,10)
  (migration 051, `distrokid_csv_schema.py`) ; rollup USD→EUR `distrokid_rollup.py`
  (taux `DISTROKID_USD_EUR_RATE` défaut 0.92, modifiable par import, préserve les
  saisies manuelles) ; intégration Upload CSV (uploader accepte `.tsv`, lecture headers
  robuste encodage+délimiteur, champ taux, hook rollup) ; DAG `distrokid_csv_watcher`
  (15 min, max_active_runs=1, watch `data/raw/distrokid/`) + `debug_distrokid_csv.py` ;
  guide in-app (`csv_guides.py`). Fixture réelle `tests/fixtures/distrokid_bank_sample.csv`
  (BetterKid) ; +17 tests parser. **Validé end-to-end live** : 22 lignes → 4 mois EUR,
  idempotent, DAG chargé sans import error. Format : `dev-docs/distrokid-export-format.md`.
  ⚠️ Reste à confirmer sur TON premier export réel (le sample BetterKid fait foi pour le
  schéma, pas pour l'extension/zip exacts).
- [x] **B3 — Refactor ciblé** (2026-06-09) : vues mapping (`track_mapping`, `meta_mapping`) migrées vers `view_session()` (rule #7). Reste : adoption `view_session()` sur les vues legacy au fil des touches (audit #2).
- [x] **C1 — Alerting erreurs app** (2026-06-09) : `src/dashboard/utils/error_alert.py` (`notify_app_error`, fail-silent, rate-limité, re-raise des signaux st.stop/st.rerun) ; dispatch des vues extrait en `_render_page()` + guard try/except dans `app.py` ; +4 tests.
- [x] **C2 — Backup DB** (2026-06-09) : `tools/db_backup.sh` (pg_dump→gzip + rétention) + `tools/db_restore_test.sh` (drill restauration) + `make backup` / `make backup-test`. Drill validé (78 tables restaurées). Cron VPS = Phase D.
- [x] **C3 — Hardening sécurité (code)** (2026-06-10) : (1) rate-limit FastAPI —
  `src/api/security.py` (NEW), fenêtre glissante en mémoire par IP (120 req/60s global,
  10/300s sur `POST /auth/token`), 429 + Retry-After, `/health` exempt, IP via 1er hop
  X-Forwarded-For derrière proxy ; (2) security headers middleware (nosniff, X-Frame-Options
  DENY, Referrer-Policy, HSTS, Permissions-Policy, CSP `default-src 'none'` sauf /docs+/redoc,
  Cache-Control no-store) — headers outermost donc présents aussi sur les 429 ; (3) timeout
  d'inactivité session Streamlit — `auth.py::_session_idle_expired` dans `require_login()`
  (défaut 60 min, `SESSION_IDLE_TIMEOUT_MINUTES`), session clear + notice à la reconnexion.
  Env vars documentées dans `.env.example`. +14 tests (`test_api_security.py`, TestClient
  sans DB). Limiteur in-memory single-process assumé (ADR-002 : pas de Redis/slowapi) —
  re-évaluer si l'API passe multi-worker en phase D.
- [x] **C4 — i18n EN/FR** (infra 2026-06-09 ; **couverture complète 2026-06-10**) :
  `src/dashboard/utils/i18n.py` (`t()` helper, FR source + fallback), **toggle sidebar**
  (`language_selector`), **navigation entièrement traduite**, +5 tests (garde-fou nav).
  **Couverture totale** : catalogues EN par vue sous `i18n_catalog/` (~47 modules, ~2150 clés,
  auto-mergés par `_load_catalogs()`) — **toutes les vues** (login/inscription, compte, billing,
  admin/ops, packages `trigger_algo/` + `credentials/`, `ml_widgets`, guides CSV). Vérifié :
  410 tests verts, render-smoke live sur les 37 vues, ruff clean, 0 clé sans EN. Commits
  `a672725` + `cde230c`. FR conservé par design : prose `csv_guides.py` (partagé PDF) +
  constantes de labels au niveau module (résolution langue au runtime).
- [x] **C5 — Benchmark VPS (sizing + topologie)** ✅ (2026-06-13 — décision figée + prod live) — **DÉCISION FIGÉE le 2026-06-11** → `.claude/dev-docs/benchmark-deployment-synthesis.md`. Topologie **split** + **VPS choisi** :
  - **Box A — Hetzner CAX31 (ARM Ampere, 8 vCPU / 16 Go / 160 Go NVMe, ~12,50 €/mo)** : streaMLytics (Postgres + Airflow + Streamlit + FastAPI + Caddy) **maintenant**, n8n + ffmpeg d'assemblage **plus tard sur la même box** (16 Go absorbe les deux : streaMLytics 10-50 tenants seul ET le pic combiné ~8-10 Go). Resize vertical Hetzner (~2 min reboot, même disque) vers **CAX41 32 Go (~24,50 €/mo)** seulement au-delà de ~50 tenants ou vidéo lourde/concurrente. **Cible retenue : 10-50 artistes à 3-6 mois.**
    ✅ **PRÉREQUIS ARM64 VALIDÉ (2026-06-11)** : `docker buildx --platform linux/arm64` du `Dockerfile` dashboard → **chaque dépendance résout un wheel aarch64** (numpy/pandas/xgboost/scikit-learn/scikit-image/shap/lime/weasyprint/numba/llvmlite/streamlit/airflow), **zéro `No matching distribution`**, `lime` compilé depuis les sources OK. Le fallback x86 CPX31 **n'est pas nécessaire**. (Fin du build local lente sous émulation QEMU = artefact, pas un problème ; natif ARM = rapide.) Détail : DEVLOG#2026-06-11.
  - **Box B — VPS Windows dédié ISOLÉ** : MT5 live 24/7 (2 vCPU / 4 Go / 50-60 Go, ~10-20 €/mo, ou **VPS broker gratuit**). Downsize de l'actuel surdimensionné (H1 ≠ HFT). Jamais mutualisé (OS + stabilité live + isolation creds broker).
  - **Vidéo (POUR PLUS TARD)** : GPU **serverless pay-per-call** (fal.ai/Replicate, modèles open LTX-Video/Wan) + ffmpeg local + nœud cleanup. **Aucun GPU acheté/loué.** 0 € tant que non déployé.
  - **Scraping** : **proxy résidentiel** (~50-75 €/mo) pour isoler l'IP — pas un 2ᵉ VPS.
  - **Budget always-on streaMLytics = ~13 €/mo tout compris** (CAX31 ~12,50 + domaine ~0,60 + email/backup gratuits). **Restant ouvert** : mesure réelle Mo/session Streamlit sous charge (seuil de resize 16→32 Go). Questions initiales (archivées) :
  1. **Échelle streaMLytics** : nb d'artistes cible à 3 / 6 / 12 mois ? (10 / 100 / 1000 ?) — pilote la RAM (Streamlit garde chaque session en mémoire).
  2. **MT5 / vidéo / scraping / n8n sur le MÊME VPS, ou séparés** (juste mutualisés pour le coût) ?
     ⚠️ **MT5 = Windows-only** → ne tourne PAS sur un VPS Linux/Docker → soit VPS Windows séparé, soit machine dédiée → **casse le « un seul VPS »**.
  3. **Génération vidéo** : rendu GPU ou CPU ? quelle fréquence/volume ? (change radicalement le sizing).
  4. **Budget €/mois** visé pour l'infra ?
  **Reco** : sizer **streaMLytics seul d'abord** (le seul prêt+mergé : postgres + airflow web/scheduler + dashboard Streamlit + API FastAPI + reverse proxy), MT5/vidéo/scraping en couche au-dessus une fois la mutualisation décidée.
  **→ GRILLE EXHAUSTIVE : `.claude/dev-docs/benchmark-deployment.md`** — profil ressources par composant (RAM/CPU/disk/réseau, idle/pic), hypothèses d'échelle, méthodo de load-test (⚠️ Streamlit = WebSockets, pas HTTP), topologie, stockage/I/O, coût, backup/DR/monitoring, critères hébergeur, seuils de scaling, **+ les 2 prompts cross-projets à poser aux IA MT5 / n8n** (§ M) pour récupérer leurs profils ressources et trancher la topologie.
  **Livrable** (→ `dev-docs/deployment.md`) : topologie (1 VPS Linux vs split Linux/Windows), sizing vCPU/RAM/disk par composant, reco hébergeur, estimation €/mois.
- [x] **C6 — Benchmark nom de domaine + accès public (NEW 2026-06-10)** ✅ (2026-06-13 — streamlytics.fr live + Cloudflare) — **DÉCISION FIGÉE le 2026-06-11** → `benchmark-deployment-synthesis.md` § 9. Vérif RDAP live 2026-06-11 :
  - **Domaine retenu : `streamlytics.fr`** (libre ✅ ; cible FR assumée ; le moins cher ~7 €/an). `streamlytics.com` = **pris** (enregistré 2017 GoDaddy, **parké/site mort**) → écarté ; `streamlytics.app` = libre (alternative HTTPS-forcé si besoin). Option : prendre `.fr` + `.app` (~20 €/an) et rediriger l'un vers l'autre.
  - **Registrar : OVH** (français, le moins cher pour `.fr`, **boîte email gratuite incluse** pour `contact@`). Cloudflare ne vend PAS le `.fr` (mais sa DNS gratuite reste utilisable plus tard pour CDN/anti-DDoS).
  - **TLS : Caddy** sur la Box A (Let's Encrypt auto). Sous-domaines `app.streamlytics.fr` (Streamlit) + `api.streamlytics.fr` (FastAPI / webhook Stripe).
  - **Email** : **2 flux distincts** — (1) **ENVOI** (vérif compte, alertes, digest, Stripe) reste sur le **SMTP Gmail actuel**, rien à changer ; (2) **RÉCEPTION** `contact@streamlytics.fr` = **boîte gratuite OVH** ou **Cloudflare Email Routing** (forward gratuit → Gmail). **Email de domaine = crédibilité, PAS un prérequis Stripe** (Stripe accepte un email quelconque). Bascule expéditeur → `noreply@streamlytics.fr` + SPF/DKIM/DMARC = sujet de **scale**, pas de lancement.
  - **Backup** : `pg_dump` gzippé → **Cloudflare R2 (10 Go gratuits)** ou Hetzner Storage Box (`tools/db_backup.sh` existe).
  - **Restant ouvert** : réservation effective `streamlytics.fr` chez OVH + plan DNS (A `app`/`api` → IP Box A). Questions initiales (archivées) :
  Un domaine est un **PRÉREQUIS**, pas cosmétique : HTTPS exigé par **Stripe** (checkout + webhook) + cookies d'auth + crédibilité SaaS. Sans lui = `http://IP:8501` (inviable).
  1. **Nom de marque** : `streamlytics.{com,io,app,fr}` ? → vérifier dispos + prix (je peux checker).
  2. **Registrar** : Cloudflare (DNS + proxy/CDN gratuit, recommandé) / OVH / Namecheap ?
  3. **Sous-domaines** : `app.X` (dashboard Streamlit) + `api.X` (FastAPI / webhook Stripe) ?
  4. **TLS** : **Caddy** recommandé (Let's Encrypt auto, zéro config) en reverse proxy.
  5. **Email pro** (`contact@X`) pour Stripe + support artistes ?
  6. **Délivrabilité email** (SPF/DKIM/DMARC) pour que les emails de vérification ne finissent pas en spam.
  **Modèle d'accès (déjà construit)** : 1 URL publique → register/login → isolation par `artist_id` → chaque artiste voit ses données, connecte ses credentials, upload ses CSV ; DAGs paramétrés par artiste. Il manque juste : domaine + TLS + reverse proxy + port 443 ouvert.
  **→ Détail complet : `.claude/dev-docs/benchmark-deployment.md` § G** (domaine/registrar/sous-domaines/TLS/email/CDN).
  **Livrable** (→ `dev-docs/deployment.md`) : reco domaine + plan DNS + reverse proxy (Caddy) + schéma d'accès multi-tenant.
- [x] **D — Déploiement + pentest** ✅ (2026-06-13 — prod live + red-team complet, classes cataloguées) (DERNIER, séquencé 2026-06-12) : runbook copier-coller dans
  `deployment.md`. Légende : 🤖 code (moi, PR) · 🧑 ops (toi) · 🤝 sur le VPS. On coche au fil de l'eau.
  - **Phase 0 — Prep code (🤖)** :
    - [x] **0.1** services `dashboard` (Streamlit:8501) + `api` (FastAPI:8502) ajoutés à
      `docker-compose.example.yml` (DATABASE_URL, loopback bind, mount `machine_learning`/`data`).
      Le dashboard tournait sur l'hôte → désormais conteneurisable. ref: DEVLOG#2026-06-12 (suite 6).
    - [x] **0.2** `deploy/Caddyfile` — `app.`→8501 (WebSocket), `api.`→8502, TLS Let's Encrypt auto,
      HSTS + headers sécurité, apex/www → `app.`.
    - [x] **0.3** backup + restore drill validés live (`tools/db_backup.sh` → 516K ; `db_restore_test.sh`
      → 92 tables / 13794 rows / DB jetable droppée).
  - [x] **Phase 1 — Provisioning infra (🧑)** — DONE 2026-06-12. OVH `streamlytics.fr` (compte Particulier)
    + email Zimbra inclus · Hetzner **CPX32** (x86 AMD, 4 vCPU/8 Go, ~16,79 €/mo — **ARM CAX en rupture UE**,
    fallback x86 documenté pris) Ubuntu 24.04 Nuremberg, IP **167.233.92.1** · DNS A `app`/`api`/racine.
    ⚠️ racine a un **doublon** `A 213.186.33.5` (parking OVH) à supprimer. **Gate 1** ✅ (`app`/`api` résolvent).
  - [x] **Phase 2 — Hardening D0 (🤝)** — DONE 2026-06-12. MAJ système, Docker 29.5 + Compose v5.1,
    `ufw` (22/80/443 only, reste deny), `fail2ban`. `.env` prod : mdp Postgres + admin Airflow (`sladmin`)
    rotés, `API_SECRET_KEY` généré, FERNET_KEY **réutilisée** (déchiffrement creds), URLs `https://`,
    perms 600. Postgres/Airflow/Streamlit/API en loopback (compose + ufw). **Gate 2** ✅.
  - [x] **Phase 3 — Déploiement D1 (🤝)** — DONE 2026-06-12. Clone via `GITHUB_TOKEN` (purgé du remote) ;
    **migration données** (dump local → restore : 13 794 lignes S4A, 92 tables, 0 erreur) ; `docker compose
    up -d --build` (5 conteneurs) ; **Caddy v2.11** + cert **Let's Encrypt** auto. **Smoke ✅** : `https://
    app.streamlytics.fr` HTTP 200 + login + données visibles ; `https://api.../health` ok ; HTTP→HTTPS 308.
    ⚠️ **2ᵉ bug fresh-install `init_db.sql`** trouvé (FK `hypeddit_daily_stats`→`hypeddit_campaigns(campaign_name)`
    sans UNIQUE matching) → contourné en provisionnant depuis le dump (mount `init_db.sql` retiré du compose
    serveur). À corriger dans le repo (même classe que le bug youtube ; lié au blocker Postgres-en-CI).
    **Gate 3** ✅ → 🎉 **app live**.
  - [x] **Phase 4 — Activation Stripe (🤝)** — DONE 2026-06-12 (**mode TEST**). Produit Premium 10€/mo +
    Payment Link + webhook (4 events) créés **via l'API Stripe** (clé test). `STRIPE_SECRET_KEY` +
    `WEBHOOK_SECRET` + `CHECKOUT_URL` posés dans le `.env` prod. **Webhook vérifié end-to-end** (événement
    `checkout.session.completed` signé → 200 → `artist_subscriptions` provisionné + `tier=premium`, puis
    nettoyé). **2 bugs corrigés** : billing ne passait pas `client_reference_id` (PR #32) ; le handler 500ait
    car `stripe.Event` (StripeObject) n'a pas `.get()` → parse en dict après vérif signature (PR #33).
    **Restant** : `STRIPE_PORTAL_URL` (portail client, optionnel) ; passage **mode LIVE** = activation complète
    du compte Stripe (KYC + SIRET 939874392 + IBAN) puis recréer produit/link/webhook en live + clés `sk_live`.
    **Gate 4** ✅ (provisioning prouvé en test).
  - [x] **Phase 5 — Pentest D2 (🤝)** — **COMPLET 2026-06-13** (pentest live mené par sondes externes ; Gate 5 entièrement levé, A→G ✅).
    ✅ **A. Recon** : seuls 22/80/443 ouverts ; 5433/5432/8080/8501/8502 **filtrés** depuis l'extérieur.
    ✅ **B. Transport** : HTTP→HTTPS 308 · HSTS (1 an + includeSubDomains) · X-Frame DENY · nosniff ·
    Referrer-Policy · **TLS 1.0 refusé / TLS 1.3 OK**. ✅ **C. Surface** : `/docs`+`/redoc` 404 ; `/.env`,
    `/config.yaml`, `/.git/config` → **faux positif** (catch-all SPA Streamlit en `text/html`, aucun secret).
    **FINDING corrigé** : `/openapi.json` était servi (carte API complète) → gé sur `API_ENABLE_DOCS`, **404**
    désormais (PR #54). ✅ **D. Auth** : tous les endpoints API → 401 sans token, token forgé → 401, webhook
    Stripe sans signature → 400 (fail-closed). **Note auth API** : `/auth/token` était inerte en prod (503) →
    rendu **fonctionnel** (auth DB `saas_users`, lockout partagé, 2FA refusé — PR #56) ; l'API est donc désormais
    une vraie surface authentifiée (le tenant-scoping `require_artist_scope` PR #49 la protège).
    ✅ **E. Lockout brute-force PROUVÉ en direct (2026-06-13)** via l'API : `POST /auth/token` ×6 mauvais mdp →
    401 ×5 puis **429 (verrouillé)** au 6ᵉ (le 5ᵉ pose le verrou) → compteur reset. Verrou **partagé** dashboard↔API.
    ✅ **F. Scan client-side secrets (2026-06-13, suite 15)** — fait **par HTTP** (le MCP Chrome crashe toujours
    « Target closed » en WSL ; son fix exige un vrai redémarrage de Claude Code, non réalisable in-session).
    Résultats : (1) HTML bootstrap = seul inline `window.prerenderReady = false` (standard Streamlit), aucun secret ;
    (2) les 3 chunks JS principaux (index/src/lib) = bundle framework Streamlit générique, **0 hit** sur les motifs
    `sk_live/sk_test/AKIA/fernet/postgres://…/-----BEGIN/*secret*` (le code Python n'atteint jamais le client) ;
    (3) **source maps NON exposés** : `*.js.map` renvoie 200 mais c'est le **catch-all SPA** (HTML `text/html`
    5381 o, identique pour un `.map` inexistant) → **faux positif, même classe que `/.env`/`/config.yaml`**.
    ✅ **G. Messages console live (2026-06-13, suite 15) — MCP Chrome RÉPARÉ.** Cause racine trouvée : pas les
    args sandbox/pipe mais la **résolution de version Chrome** — par défaut (`channel: stable`, pas
    d'`executablePath`) le MCP tente un Chrome récent qui meurt en WSL (« Target closed »). Fix définitif :
    `--executablePath=…/puppeteer/chrome/linux-131.0.6778.204/…/chrome` (Chrome 131 du cache, prouvé OK) dans
    `.mcp.json` (gitignored). Scan console de la page login : 2 messages, **tous bénins** (`[issue]` form field
    sans id/name ×2 ; `[verbose] [DOM]` password field hors `<form>`) — **aucun secret, aucune erreur sensible**.
    Pas de CSP/Permissions-Policy (limite Streamlit, P4). **Gate 5 entièrement levé.**
    ✅ **H. Batterie offensive active (2026-06-13, suite 17) — MITM/TLS + injection.** Lancée en direct
    (openssl + testssl.sh) contre la prod : **(ports)** seuls 22/80/443 ouverts (5432/5433/8080/8501/8502/3000
    filtrés) ; **(downgrade MITM)** TLS 1.0/1.1 **refusés**, TLS_FALLBACK_SCSV « no fallback possible »,
    seuls TLS 1.2/1.3 + ciphers **AEAD/forward-secrecy** (ECDHE-ECDSA-AES-GCM) ; RC4/3DES/NULL/CBC-SHA1 tous
    **rejetés** ; **(CVE TLS)** Heartbleed/CCS/Ticketbleed/ROBOT/POODLE/CRIME/SWEET32/FREAK/DROWN/LOGJAM/BEAST/
    LUCKY13/Winshock = **not vulnerable** ; reneg sécurisée OK ; cert LE ECDSA valide (SAN match). **Seul flag :
    BREACH** « potentially » (compression gzip HTTP) — exploitabilité faible (Streamlit websocket, pas de secret
    reflété en réponse) + désactiver gzip dégraderait le LCP déjà lent → **accepté P4** comme le no-CSP.
    **(SQLi)** 3 payloads (`' OR '1'='1`, `'--`, `UNION SELECT`) sur `/auth/token` → **401 propre, 0 erreur SQL**
    (requêtes paramétrées tiennent) ; **(surface)** `/.env /.git/config /openapi.json /docs /redoc /actuator` =
    404 ; endpoints protégés = 401, JWT forgé rejeté, webhook sans signature = 400 fail-closed.
    **Non testé (refusé volontairement)** : DoS volumétrique sur la prod (risque service + ToS Hetzner) →
    recommandation = **Cloudflare gratuit** (WAF + anti-DDoS + cache, comble aussi l'absence de WAF). RCE : surface
    nulle (0 `eval/exec/pickle/subprocess/shell` dans `src/`), non fuzzé. Phishing = hors-scope app (social).
  - ~~Phase 6 — Box B MT5~~ — **RETIRÉ 2026-06-13 : hors scope de streaMLytics** (projet trading MT5 séparé, traité ailleurs).

### Pré-déploiement — optimisations & ship-blockers (2026-06-11)

Trois audits multi-agents (sécu/perf, intégrité données, couverture tests) avant l'ouverture
publique. Verdict intégrité = **GO, convergent** (oublis localisés, pas systémique). PR #21
(perf + sécu) + PR #22 (bugs intégrité + tests) **mergées**.

- [x] **Perf DB** : migrations **057** (5 index composites `(artist_id, date)`) + **058** (3 index :
  `etl_run_log(artist_id,status)` page home, `etl_run_log(started_at)`, `instagram_daily_stats`) ;
  fusion du double-scan de `v_artist_monthly_revenue` dans `get_monthly_roi_series`.
- [x] **Perf/RAM dashboard** : cache `get_artist_plan` (+invalidation sur mutation de plan),
  `get_roi_data`/`get_monthly_roi_series`/`_load_scored_tracks` ; libération des blobs export ;
  mémoïsation des modèles ML ; throttle du ping DB ; `meta_token_refresh` 1 connexion réutilisée.
- [x] **Durcissement sécurité (code)** : `docker-compose.example.yml` tracké (secrets en `${VAR}`,
  binding loopback Postgres/Airflow) ; JWT secret éphémère (plus de fallback public) ; `/docs`+`/redoc`
  off par défaut ; CORS env ; webhook Stripe fail-closed. Checklist ops **D0** dans `deployment.md`.
- [x] **Bugs intégrité** : 2 requêtes S4A sans le filtre `1x7xxxxxxx` (Coût/stream ~2× faux) +
  2 requêtes `meta_x_spotify` non scopées par `artist_id` (fuite cross-tenant sur collision de nom) → corrigés.
- [x] **Tests des chemins argent/tenant** (DB-free → tournent en CI) : `test_plan_gating.py`
  (free verrouillé hors premium), `test_tenant_isolation.py` (`artist_id_sql_filter`), `test_revenue_math.py`.
- [x] **Postgres en CI** (P3 infra/test) — **FAIT 2026-06-13.** `ci.yml` a un service `postgres:17`
  **provisionné** (étape « Provision Postgres » : `init_db.sql` + `migrations/*.sql`, fail-loud si `saas_artists`
  absent → pas de skip silencieux) + `DATABASE_URL` sur l'étape tests. Le render-smoke **39 vues** + les tests
  ML DB tournent désormais en CI. Le « bloquant » `\c`/seed s'est avéré **non bloquant** : avec un service dont
  `POSTGRES_DB=spotify_etl` existe déjà, le `\gexec CREATE DATABASE` no-op et `\c` reconnecte ; le seed est en
  `ON CONFLICT DO NOTHING`. Validé localement (Postgres éphémère) : provisioning **0 erreur**, **39/39 vertes**,
  suite complète **555 passed**. `_db_ready()` rendu conscient de `DATABASE_URL` (skippait sinon sur le check
  socket 5433 codé en dur). **2 bugs fresh-install corrigés au passage** : `campaign_track_mapping` absente du
  bootstrap → ajoutée à `init_db.sql` (débloque migrations 011/049 + vue meta_cpr_optimizer) ; `alerts` crashait
  `px.area` sur DataFrame vide → guard empty-state. ref: DEVLOG#2026-06-13.
- [x] **Cohérence env-first des 11 `*_schema.py`** (P3 tech debt) — DONE 2026-06-13 (suite 15). Les 11 schémas
  (`apple_music_csv/app_costs/distrokid_csv/distrokid/hypeddit/imusician_csv/imusician/instagram/stripe/wrapped/
  youtube`) faisaient `config['database']` en **subscript direct sans fallback `DATABASE_URL`** → `KeyError` si
  lancés en prod (pas de config.yaml). Fix : nouvelle factory **`PostgresHandler.from_env_or_config()`**
  (`postgres_handler.py`) = `DATABASE_URL` d'abord, sinon `config.yaml`, sinon `RuntimeError` clair (plus de
  `KeyError`) — sans dépendance Streamlit (contrairement à `get_db_connection()`, couplée au dashboard). Les 11
  `__main__` appellent désormais la factory ; imports `config_loader` morts retirés (ruff vert). Vérifié : path
  DATABASE_URL (parse OK), path config-absent → RuntimeError, 11 modules `py_compile`, suite **519 passed /
  39 skipped**. ref: DEVLOG#2026-06-13 (suite 15).
- [x] **DistroKid — persister le taux FX** (P2 data integrity) — DONE 2026-06-12. `migrations/059_distrokid_fx_rate.sql`
  ajoute `fx_rate NUMERIC(8,5)` (NULL pour les saisies manuelles EUR, renseigné pour les imports) sur
  `distrokid_monthly_revenue` ; `distrokid_rollup.py` l'écrit (INSERT + ON CONFLICT UPDATE, 3 placeholders de taux).
  `revenue_eur` redevient réversible (`revenue_eur / fx_rate`). Le taux reste aussi dans `notes` (affichage humain).
  Schéma canonique (`distrokid_schema.py` + `init_db.sql`) aligné pour les fresh installs. Vérifié live (synthetic
  $10 @ 0.85 → 8,50 € → reverse 10,00 $) + 3 tests DB-free (`test_distrokid_revenue.py`). Migration appliquée live.
  ref: DEVLOG#2026-06-12.
- [x] **API `/ml/predictions` cassé** (P4) — FIXED 2026-06-13. Le endpoint lisait des colonnes inexistantes
  (`score`/`tier`/`predicted_at`) → 500 systématique. Contrat API redessiné : renvoie les vraies probabilités
  `dw/rr/radio_probability` + `prediction_date` (dernière ligne par titre via `DISTINCT ON (song)`), scopé
  tenant par `require_artist_scope` + filtre nom `1x7xxxxxxx`. Plus de KNOWN-BROKEN. ref: DEVLOG#2026-06-13.

### P3 — UX / Features (closed, 2026-06-12 — pre-deploy validation)

- [x] **Admin "Voir comme" toggle + artist plan vision** — `app.py::show_view_as_selector` (radio
  Admin/Premium/Free, admin-only); `get_artist_plan()` reads the session `_view_as` override; effective
  role='artist' when impersonating free/premium (hides `_ADMIN_ONLY`). Previews ACCESS only — data stays
  admin-wide (`get_artist_id()` untouched). Artist sidebar shows a plan badge + 🔒=Premium marker.
  **Root cause of "no free vision": the sole tenant is premium and the owner is admin → no free account
  ever existed** (not a gating bug). ref: DEVLOG#2026-06-12 (suite 5).
- [x] **Billing premium features live** — 3 bullets in ✓ (no "coming soon"): daily auto-download of
  S4A+Apple CSV, CPR budget&streams optimization, video creative generation 60+/campaign + targeting.
  EN+FR catalogs synced. `SERVICE_CONTACT_EMAIL` → `1x7xxxxxxx@gmail.com`. ref: DEVLOG#2026-06-12 (suite 5).
- [x] **E2E outcome chain proven** — synthetic self-cleaning script: saisie upsert (7d+28d) → real
  `label_predictions()` = 1 label (`y_dw/y_rr/y_radio` vs thresholds 137/130/639, horizon 30d) → trigger
  read OK → idempotent (2nd run=0) → 0 residual. Plumbing was already correct; the chain had simply never
  been exercised (`s4a_song_algo_outcomes` was empty). ref: DEVLOG#2026-06-12 (suite 5).

### P1 — Fuite locataire et pannes muettes (clos, 2026-08-20)

Rotation depuis `checklist.md` le 2026-08-21 (règle 17). Les neuf entrées ci-dessous
portaient déjà leur `✅` dans l'index actif ; elles y sont retirées, pas effacées.
Le code correspondant a été commité le 2026-08-21 (`83d3c63`) — il ne vivait que dans
l'arbre de travail jusque-là.

- [x] **R21 — Nettoyer les lignes contaminées en PROD** (P1) — sauvegarde prise, **5304 lignes**
  supprimées : GRiNCH 67 vidéos + 603 stats + 1 chaîne ; Cuzebo 4556 stats + 68 historiques —
  toutes rattachées à la chaîne de l'admin. `track_popularity_history` gardait 1051 lignes sous
  `artist_id=1` mais **légitimes** (seul l'admin a des tracks Spotify) : mécanisme armé, dégâts
  nuls. Vérifié après coup : collecte réelle relancée, admin = ses 67 vidéos, locataires 11 et 13
  = rien.
- [x] **R22 — Appliquer la migration `064` en prod** (P1) — additive : index composites +
  colonne `is_canary`. Appliquée 2026-08-20.
- [x] **R23 — Retirer les `DEFAULT 1` sur `artist_id`** (P2) — `migrations/068`. `DEFAULT` retiré
  (55 colonnes) **et** `NOT NULL` posé (81) : l'oubli du locataire devient fatal au lieu de
  silencieux. 805 tests verts contre une base la portant. Deux enseignements retenus :
  `tracks.saas_artist_id` reste volontairement nullable, et `artist_id` **n'est pas toujours le
  locataire** (VARCHAR Spotify sur `artists`, `artist_history`, `tracks`) → classe
  `column-name-is-not-its-meaning`, on raisonne sur le type. ⚠️ l'application en prod reste
  séquencée derrière le déploiement du code (cf. R25/R26, toujours ouverts).
- [x] **R27 — Alerting muet dans le scheduler** (P1) — `SMTP_*` et `ALERT_EMAIL` n'étaient
  déclarés que pour le service `dashboard` : **672 échecs de watchers CSV en 7 jours, aucun
  mail**. Câblés dans `airflow-common-env` (prod + exemple), scheduler redémarré, vérifié. Garde :
  `test_env_contract` élargi aux lectures **transitives** (`src/utils`), qui était son angle mort.
- [x] **R28 — Watchers CSV en échec permanent** (P1) — `PermissionError` sur
  `/opt/airflow/data/raw` (volume `root:root`, airflow en uid 50000). 672 runs échoués depuis le
  13/08. Droits corrigés, run manuel **et** run planifié verts.
- [x] **R29 — `make schema-check` aveugle aux contraintes** (P2) — comparaison étendue aux
  PK/UNIQUE/FK et index uniques, **par définition** et non par nom. Premier passage : 3 dérives
  prod inconnues → `migrations/066` (deux `UNIQUE (campaign_name, platform, placement)` aveugles
  au locataire : deux artistes homonymes ne pouvaient pas coexister) et `067` (3 FK Meta
  manquantes, 0 orphelin vérifié). Les deux appliquées en prod.
- [x] **R30 — Deux locataires, même identifiant plateforme** (P2) — `find_identity_conflict()`
  refuse le doublon à l'enregistrement sur les 4 plateformes, plus un test qui garantit qu'aucune
  plateforme ne peut être ajoutée sans règle d'unicité.
- [x] **R31 — « Lancé ! » sans résultat** (P3, = item B2 de R14) — `collection_progress.py` garde
  le `run_id`, lit l'état à chaque rerun et traduit l'échec en geste. Un échec non reconnu ne
  reçoit **pas** d'explication inventée.
- [x] **R32 — Parcours d'inscription non testé** (P2) — `tests/test_signup_funnel_db.py` : paire
  user/tenant atomique, non vérifié + jeton, mot de passe haché, slug unique, locataire frais
  cohérent (aucune ligne, readiness « à connecter »).

### P3 — Configuration recentrée sur ce dépôt (clos, 2026-08-21)

Rotation depuis `checklist.md` (règle 17). La classe commune aux deux : un fichier de
configuration copié d'un autre dépôt décrit ce dépôt-là, et rien ne le signale — un
pointeur qui rate ne se plaint pas.

- [x] **R34 — Trancher le sort de `.claude/dev-docs/architecture/`** (P3) — **retiré**,
  pas peuplé, vers `.claude/.retired/dev-docs/architecture/` avec son argumentaire.
  Quatre mesures, pas une préférence : **584 marqueurs `[TODO]` sur 1301 lignes**
  (`database_schema.md` en portait 539 à lui seul) ; **aucun consommateur vivant** — la
  seule référence était `agents/code-architecture-reviewer.md`, un agent que CLAUDE.md
  signale lui-même comme jamais invoqué ; **le mécanisme censé le remplir n'existe pas
  ici** (les fichiers renvoient à `/dev-docs-init` et à un agent `dev-docs-architect`,
  ni l'un ni l'autre présents, et `generate-dev-docs.py` vise `src/Application` par
  défaut, n'est câblé à aucune cible du Makefile ni à aucun hook) ; enfin **une copie
  markdown du schéma tenue à la main est un générateur de dérive** — les sources
  autoritaires sont `migrations/*.sql`, `src/database/*_schema.py` et `make schema-check`,
  qui compare à la base vivante par définition (cf. classe `api-router-schema-drift`).
  `code-architecture-reviewer` est repointé sur `.claude/dev-docs/architecture.md`, la
  surface peuplée, avec la vérité-terrain de chaque diagramme nommée explicitement.

- [x] **R36 — Fuite de domaine restante dans la config** (P3) — sweep terminé. Corrigés :
  `commands/audit-collectors.md` (la **règle transverse #6** impose `/audit-collectors`
  après tout collector, et la commande auditait `fanuc_reader.py` en OPC UA — le plus
  grave du lot, une règle à déclencheur réel pointant une procédure fausse) ;
  `skills/verification/SKILL.md` (quatre phases inexécutables, dont un `cd` vers un autre
  dépôt) ; `commands/dev-docs.md` (gabarits en QuestDB / révisions Alembic / Redis Streams) ;
  `commands/check-env.md` ; `skills/continuous-learning/SKILL.md` (vocabulaire de domaines) ;
  `rules/rex-format.md` (titre) ; `hooks/guard_destructive.py` (trois avertissements qui ne
  pouvaient pas se déclencher — Alembic est rejeté par l'ADR-002 — remplacés par les trois
  vrais dangers d'ici, dont `make migrate` qui porte désormais un garde mécanique pour la
  classe `migration-ahead-of-its-code`). **Deux défauts conséquents trouvés au passage**,
  catalogués et gardés par `tests/test_probes_scoped_to_repo.py` (vérifié 4 rouges avant /
  6 verts après) : `probe-scoped-to-the-machine-not-the-repo` et
  `state-path-namespaced-by-another-project`. Ce qui reste nommer l'autre projet est de la
  **prose REX** — la provenance d'une leçon mesurée ailleurs, qui est sa raison d'être.

### P1 — Déploiement en production du correctif de fuite locataire (clos, 2026-08-21)

- [x] **R26 — Déployer le code corrigé en prod** (P1) — fait. `96554a2 → 49e94a4`, deux
  mois d'écart. Sauvegarde prise avant (`spotify_etl_20260821_103908.sql.gz`, 600 K),
  `tools/deploy.sh` a pull + rebuild + gate de santé : api et dashboard `200`. Airflow
  monte `./src` et `./airflow/dags` depuis l'hôte, donc les collecteurs suivaient déjà ;
  scheduler et webserver redémarrés pour qu'aucun processus ne tourne sur l'ancien code.
- [x] **R25 — Appliquer `065` et `068` avec le déploiement** (P1) — fait, dans le bon
  ordre cette fois, et **vérifié en structure et en fonction**. Structure : `youtube_videos`
  et `youtube_channels` portent `PRIMARY KEY (id)` au lieu de l'identifiant plateforme, les
  index uniques `(artist_id, video_id)` et `(artist_id, channel_id)` sont là ; **0 colonne
  `artist_id` ne porte plus de `DEFAULT`** (elles étaient 55) et 76 sur 81 sont `NOT NULL`
  — les 5 restantes sont exactement celles qu'on voulait garder (deux `VARCHAR` qui sont
  l'identifiant Spotify et non le locataire, une vue, et deux tables où l'absence de lien
  est un état légitime). Fonction : DAG `youtube_daily` déclenché sur le locataire 1 →
  `success`, **67 vidéos et 67 lignes de stats réécrites à l'instant** — l'upsert résout
  bien son `ON CONFLICT` contre le nouveau schéma, ce qui est précisément ce qui avait
  cassé le 2026-08-20. `tenant_contamination_check` : aucune contamination croisée. Les
  deux locataires détenteurs d'une chaîne YouTube détiennent chacun la leur.
  `artist_preflight --artist 12` tourne de bout en bout et s'arrête, à raison, sur les
  identités manquantes de Benken (Spotify, Instagram) et sur le token Meta de R13.

### P3 — Outillage rendu exécutable là où il compte (clos, 2026-08-21)

- [x] **R37 — `make` absent du serveur de production** (P3) — ouvert et clos le même
  jour. `make migrate` sortait en **127** sur la prod pendant que `make deploy`
  marchait, parce que `deploy` met sa logique dans `tools/deploy.sh` et fait
  `ssh … bash`. La logique de migration est passée dans **`tools/migrate.sh`** sur le
  même modèle, le Makefile y délègue, et **`make migrate-prod PROD_SSH=…`** ajoute le
  wrapper ssh qui manquait — avec un rappel de l'ordre (le code d'abord, cf.
  `migration-ahead-of-its-code`). Le script garde les deux propriétés apprises du run
  réel : il continue après une erreur (c'est ce qui permet à 044 de réparer 024) et il
  **nomme** les fichiers en erreur au lieu de se taire. Garde
  `tests/test_migrate_reports_errors.py` repointé sur le script, plus une assertion
  dédiée : « les migrations doivent être lançables sans `make` ». Toute procédure
  écrite « lance `make X` sur la prod » est de nouveau vraie.

### P3 — Rendu réel vérifié, sans attendre R18 (clos, 2026-08-21)

- [x] **R19 — Vérifier en rendu réel les 4 vues restructurées + le sélecteur d'OS** (P3) —
  fait, et la dépendance à R18 levée au passage : un **Postgres jetable** sur 5434
  (`init_db.sql` + `tools/migrate.sh`) fait tourner toute la suite sans `make up`.
  **858 tests verts / 14 sautés** contre 716/128 — dont les **57 tests de rendu** des vues,
  tous verts, et les 10 sondes de production lancées en live (les 4 dernières attendent des
  identifiants qui vivent dans les secrets CI, par conception).
  La moitié « passage visuel Mac/Windows » ne repose plus sur une capture d'écran :
  `tests/test_guides_render_per_os.py` rend la page Credentials via `AppTest` **une fois par
  OS** et lit ce qui sort — aucun `{{TOKEN}}` sur la page, le rendu Windows sort
  `Ctrl+C/F/U` sans une seule graphie ⌘, le rendu macOS l'inverse, et les deux diffèrent
  (sans quoi tout le reste serait vrai deux fois sur la même page). Une capture prouve une
  fois ; ceci prouve à chaque exécution.

### P3 — Une seule résolution du DSN (clos, 2026-08-21)

- [x] **R33 — Fabrique de connexion unique** (P3) — la fiche annonçait « 5 modules » et
  « duplication, pas défaut de correction ». Les deux étaient faux, et le garde l'a montré :
  ils étaient **sept**, et la duplication cachait une vraie divergence.

  Les quatre connus construisaient leur DSN à la main, avec **deux valeurs par défaut
  différentes pour l'hôte** — `credential_loader` disait `localhost` (×4 copies dans le
  même fichier), `circuit_breaker` et `dag_run_logger` disaient `postgres`, et
  `stripe_webhook` ne lisait que `DATABASE_URL` puis `config.yaml`. Ce n'est pas
  arbitraire : la production est **réellement scindée** — Airflow reçoit
  `DATABASE_HOST=postgres` et **aucun** `DATABASE_URL`, l'api et le dashboard reçoivent
  `DATABASE_URL` et **aucun** `DATABASE_HOST`. Chaque fabrique marchait donc là où elle
  tournait, et aucune ne marchait ailleurs. `credential_loader` n'est importé que par les
  DAGs et les collecteurs : c'est la seule raison pour laquelle son `localhost` n'a jamais
  mordu — le premier import depuis une vue du dashboard l'aurait trouvé.

  Les trois autres, **trouvés par le garde et non par la fiche**, remplissaient le
  constructeur de `PostgresHandler` avec les mêmes cinq variables, un étage plus haut :
  `instagram_api_collector`, `meta_ads_api_collector`, `soundcloud_api_collector` — tous
  trois par défaut sur `localhost`, dans Airflow, c'est-à-dire au mauvais endroit.

  Livré : `src/utils/pg_connect.py` résout `DATABASE_URL` → variables `DATABASE_*` →
  `config.yaml`, dans cet ordre, une fois. `PostgresHandler.from_env_or_config()` — qui
  ignorait les variables et servait déjà 11 bootstraps de schéma — partage désormais cette
  résolution au lieu d'en tenir une seconde. Deux portes, une résolution.

  Deux comportements délibérés ont été préservés et sont testés nommément : le webhook
  Stripe rend toujours `None` au lieu de lever (il doit répondre à Stripe, pas remonter
  dans la pile ASGI), et la fabrique, elle, lève toujours — un assistant de connexion qui
  avale sa propre panne transforme une base indisponible en « aucune ligne », ce que
  `.claude/rules/python.md` interdit. `tests/test_pg_connect.py` : 21 tests, dont un grep
  d'une ligne qui aurait attrapé la divergence d'origine.

### P3 — Le canari synthétique, et le couplage qu'il a révélé (clos, 2026-08-21)

- [x] **R15 — Canary onboarding synthétique** (P3) — la fiche demandait la chaîne
  « tenant test → connect → trigger → vérif » et disait attendre une décision « tenant
  seedé ». La décision était déjà prise par les fixtures que le dépôt a fait pousser
  depuis : le locataire est **éphémère** — créé, parcouru, supprimé — donc la marche
  tourne en CI sur un Postgres jetable et ne laisse rien qui pourrirait. Un locataire
  seedé en permanence serait une deuxième chose à maintenir vraie.

  Chaque maillon était déjà testé séparément (inscription, tests de connexion, collecte
  scopée, readiness). Ce qui manquait, c'est qu'ils **composent** :
  `tests/test_canary_onboarding_walk.py` marche les quatre étapes sur un seul locataire,
  dans l'ordre, et en un seul test — divisé en quatre, chacun passerait contre un
  locataire que l'étape précédente n'a jamais touché, ce qui est précisément le défaut
  visé. Il affirme au passage la distinction que les deux sessions bêta n'avaient pas :
  **déclarer une identité ne suffit pas à allumer le voyant**, il faut des lignes derrière.

  **Trouvé en écrivant la marche** : `artist_readiness` dérive tous ses voyants de
  `freshness_monitor.MONITOR_TARGETS`, et pour YouTube c'est `youtube_channel_history`
  **seule** — ni le catalogue, ni les stats par vidéo. Écrire des vidéos sans ligne
  d'historique laisse le voyant gris avec les données présentes. Le DAG écrit bien les
  quatre tables aujourd'hui, donc ce n'est pas un défaut : c'est une dépendance que
  personne n'avait déclarée. Une optimisation du DAG qui cesserait d'écrire l'historique
  ferait passer **tous** les locataires au gris d'un coup, collecte normale. Une
  assertion le dit désormais au moment du changement, pas à la bêta suivante.

  Le canari **réel** en production (R20) reste nécessaire et différent : il utilise de
  vrais identifiants contre de vraies API. Celui-ci prouve la plomberie ; l'autre prouve
  le monde.

### P4 — Performance : quatre items deviennent des conditions (clos par décision, 2026-08-21)

Clos par **ADR-007 — « Performance work is trigger-gated, not backlogged »**. Aucun des
quatre n'était une tâche : chacun portait déjà, écrite à côté de lui, la raison de ne pas
le faire. Un item mesuré comme inutile coûte une lecture à chaque `/resume` et invite
périodiquement à « le faire quand même », ce qui dépenserait du risque contre un bénéfice
mesuré à zéro. Le déclencheur qui les rouvre est nommé dans l'ADR, et il est observable.

- [x] **R8 — Caching `@st.cache_data(ttl=300)` sur 4 vues** (P4) — les requêtes tournent
  en **moins d'1 ms** ; le vrai levier sur le temps de chargement est le cache Cloudflare,
  déjà en place. Mettre en cache une requête sub-milliseconde échange de la fraîcheur de
  données contre rien. *Déclencheur : trafic concurrent avec un p95 réellement ressenti.*
- [x] **R10 — Splitter les god-functions (171 fonctions > 40 l.)** (P4) — la fiche disait
  elle-même « **au fil de l'eau, jamais en sweep dédié** ». Un balayage de 171 fonctions
  est un gros diff sans test comportemental pour rattraper ce qu'il casse, dans un dépôt
  dont les vues ne sont couvertes que par un render-smoke. *Déclencheur : au moment où la
  fonction est ouverte pour une autre raison.* Détail par fonction conservé dans
  `refactor-audit-dashboard.md`.
- [x] **R11 — Lazy imports (plotly/sklearn/shap)** (P4) — aucune latence par vue n'a jamais
  été rapportée ni mesurée. *Déclencheur : un cold-start par vue au-dessus d'~1 s.*
- [x] **R12 — Index composite `s4a_song_timeline(artist_id, song, date)`** (P4) —
  `EXPLAIN ANALYZE` = **0,4 ms** sur 13 794 lignes via l'index `(artist_id, date)`
  existant. Ajouter un index que le planificateur n'utilise pas coûte à l'écriture pour
  rien. *Déclencheur : ~10× le volume (≈140 k lignes), ou un EXPLAIN au-dessus de ~50 ms.*

### P3 — Conformité baseline : 76,2 → 84,4 (clos, 2026-08-21)

- [x] **R35 — Combler les 3 axes faibles** (P3) — fait, et un quatrième avec.

  **Axe F contexte 4 → 6/10** : CLAUDE.md est passé de 427 à 392 lignes, sous le seuil
  de 400. Les tableaux d'agents, de skills et de commandes sont partis dans
  `dev-docs/tooling-reference.md` : le dépôt a mesuré qu'un agent cité dans un tableau
  n'est **jamais** invoqué (0 sur 23), donc ils coûtaient du contexte à chaque session
  pour rien. Les règles impératives sont toutes restées.

  **Axe E atteignabilité 6,7 → 8,8/10** : `code-architecture-reviewer` et
  `web-research-specialist` n'étaient nommés que dans un tableau. Les règles 18 et 19
  leur donnent un déclencheur **vérifiable à la commande** — `git diff --name-status`
  compté sur `^(A|D|R)` pour l'un, `grep -rl "<code d'erreur>" .claude/dev-docs/` vide
  pour l'autre. La note dit explicitement que si un déclencheur ne se produit jamais, la
  bonne réponse est de retirer l'agent, pas de lui inventer une règle.

  **Axe D agents 12 → 15/15** : aucun des 8 agents ne portait de section de bornes. Ce
  n'est pas cosmétique — un agent sans non-buts explicites est un agent qui déborde, et
  c'est précisément ce que `build-error-resolver` promet de ne pas faire dans sa
  description sans que rien ne le tienne. Chacun porte désormais ses limites, écrites
  sur ce qu'il ne doit pas faire ici.

  **Ce qui reste, et pourquoi ce n'est pas de la configuration :**

  - **Axe A 18/20 — défaut de l'auditeur.** `parse_frontmatter` d'`audit_fleet.py`
    fabrique une clé `_rex_extra` pour toute ligne indentée du frontmatter (l.115), puis
    l'axe A la compte comme « hors spec » (l.204) alors que la même ligne exclut
    explicitement `rex`. Toute skill portant un bloc REX **rempli** — ce que
    `rules/rex-format.md` impose — perd un point. Le correctif appartient au baseline.
  - **Axe C 10/15 — environnemental.** 15 fichiers de hooks (>14 ⇒ 0 point sur ce
    sous-critère) et la latence non mesurée (+2 « neutre »). ⚠️ **Ne pas lancer
    `--measure-latency` pour « améliorer » le score : ça le baisse à 8.** L'événement
    Stop coûte ~10 s, et ce n'est pas les hooks : mesuré ici, `git status --porcelain`
    coûte **2 690 ms** sur `/mnt/c` (9p) contre 4 ms en natif, et `draft_rex` coûte
    2 879 ms **sans un seul appel git** — c'est la marche de répertoires et les lectures
    de fichiers qui paient. Une tentative de cache git partagé a été écrite puis
    **retirée le jour même** : le comptage déterministe montre que la chaîne Stop fait
    **4 appels git, tous différents** — il n'y a aucun doublon à mettre en cache. Le
    seul vrai levier serait de déplacer le dépôt sur le système de fichiers natif de
    WSL, ce qui est une décision d'environnement, pas de configuration.
  - **Axe G 6,6/10** : fichiers modifiés localement par rapport au payload — normal et
    voulu (c'est tout le travail de recentrage sur ce dépôt), à ne surtout pas
    « corriger » par un re-push.

### P3 — Meta : le risque résiduel était devenu inatteignable (clos, 2026-08-21)

- [x] **R24 — Clé de conflit scopée pour `meta_campaigns/adsets/ads`** (P3) — clos sans
  changement de schéma, sur preuve. La fiche disait : reporté sciemment, parce que les
  PK plateforme de ces tables sont référencées par **15 clés étrangères** ; la
  réattribution de ligne était déjà retirée côté code, et il restait le cas « deux
  locataires, même compte pub », qui n'aurait qu'une ligne au lieu de deux.

  Ce cas ne peut plus être créé. **R30** a posé `find_identity_conflict()` au moment de
  l'enregistrement, et sa table d'identités couvre Meta : `'meta': 'account_id'`. Deux
  locataires ne peuvent plus déclarer le même compte publicitaire — le produit refuse à
  la porte, avec le champ et la valeur nommés. Un test garantit par ailleurs qu'aucune
  plateforme ne peut être ajoutée au registre sans règle d'unicité, donc la couverture
  ne peut pas se perdre en silence.

  Vérifié en production le 2026-08-21 : **0** compte publicitaire partagé entre
  locataires (`GROUP BY extra_config->>'account_id' HAVING count(DISTINCT artist_id) > 1`),
  sur 34 campagnes. Il n'y a donc ni état à réparer, ni migration à écrire contre 15
  clés étrangères pour un état que le produit n'autorise plus.

  Ce qui reste, et qui n'est pas ce que R24 décrivait : une écriture directe en base,
  hors produit, pourrait encore créer le doublon. C'est vrai de toute contrainte posée
  au niveau applicatif, et la réponse serait la migration que R24 chiffrait — à rouvrir
  si un jour un tel doublon apparaît vraiment.

### P3 — Cinq items qui attendent une entrée, pas une décision (clos par ADR-008, 2026-08-21)

Clos par **ADR-008 — « Work that waits on an input we do not have »**. Ils ne sont ni
différés par préférence (c'est ADR-007) ni bloqués par un arbitrage : l'ingénierie est
comprise et la donnée sur laquelle elle opère n'existe pas encore. Chaque condition de
réouverture est une requête qu'on peut lancer.

- [x] **R5 — Retraining automatique champion/challenger** (P3) — mesuré en production le
  2026-08-21 : `SELECT count(*) FROM ml_prediction_outcomes` → **0**. Le DAG
  `ml_outcome_labeling` qui *produit* ces paires tourne déjà (migration 060) ; elles
  s'accumuleront seules. Le piège est écrit dans l'ADR : construire la comparaison
  maintenant livrerait un pipeline **intestable** qui a l'air fini, ce qui est pire que
  rien puisque plus personne ne voit le manque. *Rouvre quand : assez de paires étiquetées
  pour tenir un jeu de test — quelques centaines, pas une poignée.*
- [x] **R4 — More training data + évaluation per-tenant** (P3) — un seul locataire porte
  de la donnée ; une évaluation « par locataire » sur un locataire n'évalue rien.
  *Rouvre quand : un deuxième locataire accumule son propre historique étiqueté.*
- [x] **R6 — RR volume regressor** (P3) — supprimé sur un R²=0,23 honnête en group-CV,
  et la fiche disait déjà « blocker = volume, pas features ». *Rouvre avec R4.*
- [x] **R7 — Resurrection tuning** (P3) — les seuils de `detect_saves_resurrection`
  (min_age 180 j, 2× baseline, min_spark 50) sont heuristiques et n'ont jamais été
  calibrés contre une vraie série. *Rouvre quand : `s4a_song_saves_daily` porte assez de
  lignes datées pour voir une résurrection réelle.* C'est la condition la plus silencieuse
  des cinq.
- [x] **R14 — Onboarding UX / Meta multi-comptes (C1)** (P3) — dernier reste de R14 après
  la livraison de D1 (chaîne YouTube) et le constat que les guides étaient complets.
  Mesuré : **2 locataires, 1 compte publicitaire chacun**, et `meta_campaigns` **n'a pas
  de colonne `account_id`** — le schéma est mono-compte par construction, donc la donnée
  ne sait même pas de quel compte vient une campagne. C'est une brique (colonne + boucle
  côté collecteur + décision d'affichage : fusionner ou séparer), et la concevoir contre
  zéro demande revient à deviner la question produit — le devinage partant en schéma.
  *Rouvre quand : un locataire déclare un second compte. Le formulaire n'accepte
  aujourd'hui qu'un `account_id`, donc le déclencheur est une demande explicite, pas une
  condition silencieuse.*

### P4 — Le filtre inutile avait déjà été retiré (clos, 2026-08-21)

- [x] **R16 — Filtre inutile à enlever (front)** (P4) — périmé, et c'est la mesure qui le
  dit plutôt qu'un avis. La fiche décrivait une redondance « date/release **vs période
  28j/12m** ». **Ce contrôle 28j/12m n'existe plus dans le produit** : le commit
  `a975445` (« unified smart period filter + 4 view retrofits ») l'a remplacé par les
  quatre presets de `smart_period_filter` — `📅 En cours` / `🚀 Depuis dernière release`
  / `♾️ Tout l'historique` / `🎯 Plage personnalisée`, plus une granularité
  Semaine/Mois/Année sur « En cours ».

  Les seules occurrences de « 28j » et « 12 mois » qui subsistent sont ailleurs et
  légitimes : les guides CSV disent à l'artiste quel filtre régler **dans l'interface de
  Spotify for Artists** (pas la nôtre), et `algo_knowledge.py` porte une unité métier
  (« streams/28j »).

  Vérifié aussi par énumération plutôt qu'à l'œil : les sept vues à filtre de période
  ont été rendues via `AppTest` et leurs contrôles listés. Aucune n'en porte deux qui se
  recouvrent — au plus un sélecteur d'entité et le filtre de période, ce qui est le
  dessin voulu. La relecture du code du 2026-08-21 avait déjà conclu qu'aucun filtre
  redondant n'était démontrable ; savoir *pourquoi* manquait, et c'est que le nettoyage
  avait déjà eu lieu.

### P3 — Une connexion par rendu, sur les 18 vues (clos, 2026-08-21)

- [x] **R9 — `view_session()` / connexions par vue** (P3) — la fiche disait « 16 vues
  legacy, valide mais non conforme, tech-debt, **pas un leak** ». La mesure disait autre
  chose : `admin.py` **5** connexions par rendu, `hypeddit.py` **5**, `airflow_kpi.py`
  **4**, `export_csv.py` et `export_pdf.py` **2**. La règle #9 ne dit pas « préférer une
  connexion » : elle dit qu'une vue en ouvre exactement une et jamais une seconde en
  repli. Les 18 vues sont désormais à **1**, et le plafond de
  `tests/test_view_connection_budget.py` est **vide** — un nom qui y réapparaît est une
  régression, plus une base.

  Ce que le détail rendait coûteux : Streamlit exécute le corps de **chaque onglet** à
  chaque rerun, donc les cinq connexions d'`admin` partaient à tous les coups, pas
  seulement celle de l'onglet regardé. Et les 10 `db.close()` pour 5 ouvertures étaient
  les chemins d'erreur refermant une seconde fois.

  **Le préalable, tenu avant le refactor.** `test_views_render_smoke` rend `show()` sans
  appuyer sur rien : il serait resté vert sur un bouton cassé. Refactorer un effacement
  RGPD avec seulement ça derrière n'était pas livrable, donc la couverture est venue
  d'abord — `tests/test_admin_hypeddit_buttons.py` clique les boutons d'`admin` et
  affirme au passage la garde en deux temps de l'effacement (motif obligatoire, puis
  confirmation séparée) : cliquer sans motif **n'efface rien** et le dit.

  Pour `hypeddit`, la route du clic était fermée : `AppTest` ne peut pas rejouer une page
  portant un `st.segmented_control` mono-sélection — `streamlit/testing/v1/element_tree.py`
  itère la valeur scalaire du widget comme une séquence d'options. C'est le harnais, pas
  la vue, et le test le dit en nommant le fichier plutôt qu'en avalant l'erreur. La
  couverture est donc venue par l'autre bout : `tests/test_hypeddit_write_path.py`
  appelle directement `add_campaign_stats`, ce qui est un meilleur test qu'un clic — il
  affirme que les lignes atterrissent **sous le locataire qui a soumis**, qu'un second
  envoi le même jour **corrige au lieu de dupliquer**, et qu'une session sans locataire
  n'écrit rien du tout.

  Deux vues gardent une sémantique que `view_session()` ne sait pas exprimer, et c'est
  documenté plutôt que forcé : `admin`, `airflow_kpi` et `perf_monitor` ne résolvent
  aucun locataire (surfaces transverses), `referral` **refuse** les admins là où
  `view_session()` leur donnerait `artist_id = 1`. Le manquement à la règle #9 était le
  **nombre**, et il est corrigé sans passer par l'helper.

  900 tests verts.

### P3 — Growth : la landing attend quatre entrées, pas un développeur (clos par ADR-008, 2026-08-21)

- [x] **R2 — E2 landing marketing + pixel Meta + CAPI server-side** (P3) — rejoint ADR-008.
  Quatre entrées manquent, et aucune n'est une question d'ingénierie : **le positionnement
  et la copie** (la voix du produit, que personne d'autre que son auteur ne peut inventer —
  et la landing siège à la racine du domaine), **un Meta Pixel ID** qui n'existe pas, **un
  token Meta valide** (R13 est rouge), et **une campagne** à attribuer.

  Construire la CAPI maintenant serait exactement le piège écrit pour R5 un domaine plus
  loin : sans pixel ID, sans token et sans campagne, aucun événement ne peut être vérifié
  comme arrivé. Ce qui partirait en production est une intégration de conversions qui n'a
  jamais rien converti — et qui a l'air finie.

  Le détail à ne pas perdre : **l'attribution est la seule partie qui a une échéance.**
  `_fbp`/`_fbc` et les UTM ne se récupèrent pas rétroactivement, donc la capture au
  `register` doit être en place **au moment** où la campagne est décidée, pas après. C'est
  pourquoi le déclencheur est « la première campagne est planifiée » et non « la landing
  est en ligne ». Le reste de la spécification (sous-domaines, dédup `event_id`, e-mail
  haché SHA-256, Consent Mode v2) est conservé tel quel dans le bloc détaillé.

### P4 — `.env` ligne 67, et ce que sa correction a révélé (clos, 2026-08-21)

- [x] **R18 — `.env` ligne 67 malformée** (P4) — la ligne était
  `nom entreprise=BAUDRY Timothé` : une étiquette écrite sans `#`. Docker la lisait comme
  une clé, et une clé ne peut pas contenir d'espace. Commentée. `docker compose config`
  passe, `make up` démarre, et **`check_env.py` affiche 10/10 pour la première fois**.

  **Ce que la correction a débloqué compte plus que la correction.** Lancer la suite
  contre la vraie base locale — au lieu du Postgres jetable — a fait tomber **8 tests**,
  et chacun disait quelque chose de vrai :

  1. **Un garde a protesté à raison.** `test_the_permission_deny_list_does_not_shrink` a
     rougi parce que les trois protections `.env` avaient été retirées pour l'opération.
     Elles sont remises : le travail était fini, l'accès n'avait plus de raison d'être.
  2. **La base locale avait dérivé du canonique** (classe `local-db-drifts-from-canonical`) :
     `soundcloud_tracks_daily.track_id` en `bigint` là où `init_db.sql` dit `VARCHAR(50)`.
     `make schema-check` compare la **prod** au canonique — rien ne compare le local.
     Converti, 349 lignes conservées. Diff complet : 0 colonne manquante ou en trop, 26
     écarts de type dont **24 cosmétiques** (`text` et `varchar` sans longueur sont le même
     type en Postgres).
  3. **Un vrai défaut de DAG** (classe `dag-conf-honoured-by-one-task-only`) :
     `collect_spotify_top_tracks` ne lisait **jamais** `dag_run.conf`, alors que
     `collect_spotify_artists`, dans le même DAG, le fait. Un déclenchement « collecte
     pour l'artiste 12 » depuis le dashboard scopait la première tâche et faisait tourner
     la seconde sur **tout le catalogue** — le quota Spotify de toute la flotte dépensé à
     chaque clic per-tenant. Rien ne fuyait (chaque ligne porte son locataire), mais le
     contrat de CLAUDE.md était à moitié honoré. Corrigé, et le test qui l'attrape lance
     désormais le DAG **comme le dashboard le lance** : scopé.
  4. **Le test de fuite lui-même était faux** : `assert artist_ids == {tenant}` n'était
     vrai que sur une flotte à un membre. Il aurait crié au loup le jour où la CI aurait
     eu des données.

### R20 — Locataire canari · ✅ LIVRÉ le 2026-08-21 (local ET production)

**Prod** : `artist_id=14`, slug `canary-prod`, Spotify `4tZwfgrHOc3mvqYlEYSvVi` +
YouTube `UC_x5XG1OV2P6uZZ5FSM9Ttw`. `artist_preflight --platforms youtube` **vert de
bout en bout**, étape de contamination comprise. Collecte prouvée sur la vraie prod :
**10 titres** (`track_popularity_history`) et **200 vidéos** (`youtube_videos`) sous le
locataire 14, les deux DAG en `success`, déclenchés avec `conf={"artist_id": 14}`.

**Local** : `artist_id=471`, slug `canary-isolation`, même vérification.

**Ce qu'il a coûté et rapporté.** Trois défauts réels trouvés dans l'heure suivant sa
création, tous structurellement invisibles à une base mono-locataire :
`identity-mirrored-but-written-once` (P1), `api-partial-date-into-date-column` (P2),
`env-resolved-against-cwd` (P2). Plus, en installant le registre de migrations,
`unguarded-drop-replayed-alone` (P1) et, en tentant la procédure de prod,
`script-unreachable-from-its-dependencies` (P2). Cinq classes, cinq gardes.

**Le blocage qui a failli le tuer** : `tools/` n'était monté dans aucun conteneur alors
que psycopg2 n'existe QUE dans les conteneurs — la procédure du runbook ne s'exécutait
nulle part. Montage `- ./tools:/opt/airflow/tools:ro` ajouté aux trois services airflow,
dans `docker-compose.example.yml` **et à la main sur le serveur** (le compose de prod est
gitignoré, donc il n'arrive pas par `git pull` — sauvegarde `docker-compose.yml.pre-tools-mount`).

⚠️ **Effet permanent assumé** : le canari est collecté chaque nuit par les DAG de flotte.
C'est ce qui le rend détecteur, et ça consomme un peu de quota d'API.

---

## R13 — token Meta System User (clos 2026-08-22 : il n'a jamais fallu le régénérer)

| R13 | **Régénérer le token Meta** — oui, c'est nécessaire : mesuré | P2 | **Le collage fautif est maintenant impossible à rater** : `check_meta()` valide la FORME avant tout appel réseau et refuse un token qui ne commence pas par `EAA`, en nommant la cause (« 1 caractère en trop »). Vérifié contre le vrai token : il le détecte. Colle le nouveau, relance `python3 tools/artist_preflight.py` — s'il est mal collé tu le sais en une seconde au lieu du lendemain matin. **la question « faut-il régénérer s'il est fonctionnel ? » est tranchée : il ne l'est pas.** Testé le 2026-08-21 contre l'API Graph depuis la production. Le token stocké commence par **`EEAA…`** au lieu de `EAA` — **un `E` parasite**, une faute de collage — d'où le `Malformed access token` sur tous les appels. Mais **retire ce caractère et Meta reconnaît un vrai token** et dit pourquoi il ne marche plus : *« The session has been invalidated because the user changed their password or Facebook has changed the session »*. Ce n'est donc pas une expiration, et aucune correction de `.env` ne le ressuscitera. ⚠️ **L'application échoue aussi** (`META_APP_ID`+`META_APP_SECRET` → *Cannot get application info*) : vérifier les deux dans la même visite, sinon on régénère un token dans une app cassée. Procédure et vérification : `runbook-actions-utilisateur.md` §1. **Le silence, lui, est corrigé** : `check_central_apps` tourne chaque nuit, et la fraîcheur ne lit plus la date d'écriture (classe `freshness-measured-on-write-time`) — Meta Ads sort à **16 577 h** de retard. |

**Ce que la mesure a dit, contre ce que trois séances avaient conclu.** Interrogé le
2026-08-22 avec les credentials d'application corrects, `debug_token` répond que le
token stocké dans `.env` est **valide** : `type=SYSTEM_USER`, `expires_at=0` (n'expire
jamais), 43 scopes, `app_id=2200684950508458`. Le token de **production** l'est aussi,
et celui de `artist_credentials` pour l'artiste 1 également. Aucune régénération n'était
nécessaire — la roadmap réclamait un geste Business Manager pour un token qui marchait.

**Ce qui était réellement cassé** : `.env.local`, qui **gagne** sur `.env` par
construction (`ENV_FILES = (".env.local", ".env")`, premier chargé gagné), portait
encore l'ID de **compte publicitaire** dans `META_APP_ID` et un token avec un `E`
parasite. La correction du 2026-08-21 était allée dans le fichier qui perd. Classe
`config-corrected-in-the-file-that-loses`. Les trois clés dupliquées ont été retirées
de `.env.local` — un seul fichier les possède désormais.

**Et la sonde ne pouvait pas le voir** : `tools/check_central_apps.py`, la commande que
le runbook fait lancer, n'appelait jamais `load_project_env()`. Depuis un shell nu elle
affichait `⚠️ env not set` sur les quatre plateformes et sortait **0**. Câblée, elle
nomme la cause en une seconde (`1 extra character ('E') before the 'EAA' prefix`), puis
sort 0 une fois le doublon retiré. Frère manqué de `env-resolved-against-cwd` : sa
signature cherche la *mauvaise forme*, or ici c'était l'*absence* d'appel.

**Pourquoi Meta ne renvoie toujours aucune donnée, et pourquoi ce n'est pas une panne** :
le compte publicitaire porte **34 campagnes, 0 ACTIVE** (19 archivées, 15 en pause),
`amount_spent=0`, zéro insight sur 90 jours — vérifié en direct sur l'API et en base de
production. Les insights Meta n'existent que pendant qu'une publicité tourne. Cette
absence est désormais rendue ⏸️ « silence attendu » partout au lieu d'une fausse alerte
ou d'un faux vert (classe `suppressed-alert-renders-as-health`).

**Reste, et ça ne dépend pas de toi** : le compte publicitaire de Benken
(`act_65390907`, artiste 12) n'est **toujours pas partagé** — l'API répond
`(#200) Ad account owner has NOT granted ads_management or ads_read permission`.
C'est un geste de Benken dans son Business Manager, pas une correction de code.

---

## 🌙 R23–R31 — les neuf de la nuit du 21→22, closes le 2026-08-22

Ouvertes entre 22 h et 2 h par le pentest et ses suites, livrées dans la séance du
lendemain. Chacune porte un garde vu **rouge sur le défaut** et vert après ; les cinq
classes qu'elles ont produites sont dans `.claude/dev-docs/error-classes.md`.

- [x] **R23** — le parcours d'inscription n'est plus un oracle anonyme. Réponse
      identique que l'adresse existe ou non, e-mail « ce compte existe déjà » au vrai
      propriétaire, codes validés APRÈS création, budget par IP, message d'erreur
      générique avec référence d'incident. Garde :
      `tests/test_registration_is_not_an_oracle.py` (5 tests, 4 régressions rejouées).
      Classe : `anonymous-surface-answers-a-private-question`.
- [x] **R24** — une révocation révoque. Relecture de `active`/`role`/`artist_id` à
      chaque requête (30 s côté dashboard), `saas_users.token_version` en migration
      **072** porté par le JWT, bumpé par la désactivation et le changement de mot de
      passe. Garde : `tests/test_revocation_actually_revokes.py` (8 tests).
      Classe : `revocation-written-but-never-read`.
- [x] **R25** — règle #7 rétablie sur **9 vues**, pas 4 : le balayage a trouvé
      `artist_id_sql_filter()`, par où ~30 vues atteignent la base. `tenant_scope()`
      porte la désambiguïsation une fois. Garde :
      `tests/test_stray_session_reads_nothing.py` (24 tests, espion de requêtes ;
      11 vues vues rouges). Classe : `sentinel-means-privileged-and-missing`.
- [x] **R26** — le second facteur n'est plus brute-forçable : le compteur de compte
      n'est plus remis à 0 par le mot de passe quand un code est dû, un code faux
      compte vers le verrouillage, et le budget est par IP. Garde :
      `tests/test_second_factor_is_not_brute_forceable.py` (5 tests).
      Classe : `second-factor-budget-refunded-by-the-first`.
- [x] **R27** — `tenant_contamination_check` dérive sa portée du schéma (préfixe par
      plateforme) au lieu de 8 noms tapés à la main, entrée **spotify** comprise. A
      immédiatement trouvé `youtube_channel_history`. Garde :
      `tests/test_contamination_scope_is_derived.py` (5 tests).
      Classe : `guard-scope-is-a-hand-written-list`.
- [x] **R28** — dette de schéma des classes d'erreur soldée : **100 %** portent
      `root_cause` et `long_term_fix`. Le contrôle CI passe d'*advisory* à **bloquant**
      (`--fields --strict`), comme son propre commentaire le demandait depuis mai.
- [x] **R29** — `make chart-budget` compte ce que Few compte : ce qui est dans le coup
      d'œil (Few, *IDD* p.27/p.39/p.81, corpus `ux-frontend` ingéré en R17). AST au lieu
      de regex, colonnes `glance`/`worst`/`click`/`tab`/`mods`. `data_wrapped` passe de
      9 à **1** — il était signalé à tort. Toujours sans seuil : la source donne l'unité
      de mesure, pas un nombre.
- [x] **R30** — les 9 constats BAS traités : clé de fenêtre du limiteur (`auth.py:64`),
      test de véracité dans `artists.py`, `_totp_pending` laissé au logout, secret de
      désinscription en dur retiré (les liens se désactivent au lieu d'être forgeables),
      docstring `_get_fernet` alignée sur son code, titres échappés dans l'e-mail
      hebdo, clé Fernet du CI **générée par run**, `src/utils/http_logger.py`
      **supprimé** (zéro importateur). Le constat « affiche l'`artist_id` de l'autre
      locataire » était inexact — la valeur est retournée, jamais rendue ; la frontière
      est désormais testée
      (`tests/test_identity_conflict_names_no_other_tenant.py`).
- [x] **R31** — clos par **décision**, pas par code : `docs/adr/ADR-009`. Les deux
      registres s'accordent par test plutôt que de dériver, et le garde d'accord a reçu
      son plancher de non-vacuité (il ne comparait que les libellés communs, donc un
      renommage le faisait passer sur rien).

### Le détail tel qu'il était ouvert

## 📌 R23–R31 — ce que la nuit du 21→22 a laissé ouvert

Toutes découvertes entre 22h et 2h. Aucune n'était connue en début de séance. Chacune
porte le fichier et la ligne — pas « quelque part dans l'auth ».

### R23 — Le parcours d'inscription est un oracle anonyme (P1)

Quatre fuites sur la même page, aucune authentifiée, `src/dashboard/views/register.py` :

| ligne | ce qui fuit |
|---|---|
| `:332-334` | « L'email 'x' est déjà enregistré. » ⇒ **énumération de comptes** par n'importe qui |
| `:344-351` | promo / referral validés **avant** création du compte, avec retour anticipé ⇒ chaque soumission sonde gratuitement un espace de 24 bits (`secrets.token_hex(3)`), et un promo valide donne `promo_plan='premium'` |
| `:385` | un e-mail de vérification part vers une adresse **choisie par l'attaquant**, depuis ton domaine, sans CAPTCHA ni limite par IP |
| `:408-409` | `except Exception as e: st.error(…)` rend le message psycopg2 brut (noms de contraintes et de colonnes) à un visiteur anonyme |

Ce qui a changé cette nuit : le limiteur de débit de l'API fonctionne enfin (R21), donc
la moitié « verrouiller tous les comptes » de la chaîne est fermée. L'énumération et le
sondage de codes, eux, passent par le **dashboard**, pas par l'API — ils sont intacts.

**Fix** : réponse identique que l'email existe ou non ; valider promo/referral APRÈS la
création ou avec un budget par IP ; message d'erreur générique.

### R24 — Une révocation ne révoque rien (P1)

`src/dashboard/views/admin.py:75-79` (désactivation), `src/dashboard/views/account.py:104-107`
(changement de mot de passe), `src/api/auth.py:38-46` (JWT 24 h, sans `jti`, sans
denylist). `require_login()` (`src/dashboard/auth.py:370-379`) relit `st.session_state`
seul ; `active`, `role` et `artist_id` ne sont lus en base qu'**au login**.

Un locataire désactivé garde le dashboard tant qu'il clique (inactivité : 60 min) et
l'API jusqu'à 24 h. Changer le mot de passe après une compromission n'expulse pas
l'attaquant.

**Fix** : relire `active` en base à chaque `require_login()` (une requête déjà faite
ailleurs), et une denylist de `jti` ou un `token_version` par utilisateur pour l'API.

### R25 — La règle #7 a été perdue sur 4 vues (P2)

`views/home.py:226`, `views/spotify_s4a_combined.py:24,29-31`, `views/export_pdf.py:121`,
`views/imusician.py:76-81` : `artist_id is None` y prend la branche **admin** sans
vérifier `is_admin()`. Les puits suivent (`kpi_helpers.py:259,278,300,366,384`,
`pdf_exporter/_collectors.py:46,89,110,132,206`).

**Honnêtement : pas exploitable aujourd'hui.** L'état `role='artist'` +
`artist_id IS NULL` naît d'un `DELETE FROM saas_artists` nu (`admin.py:87-89`,
`ON DELETE SET NULL` en `migrations/007:9`) — et cette fonction est du code mort, le
seul chemin câblé étant la cascade RGPD qui supprime `saas_users` d'abord. Ce qui est
réel : le schéma peut représenter l'état, une fonction existante suffirait à le
produire, et 4 vues n'ont rien contre.

### R26 — Le second facteur est brute-forçable (P2)

`src/dashboard/auth.py:281-298`. Un code faux n'appelle que `_rate_record_failure()`,
local à la session ; `failed_login_attempts` n'est pas touché — il vient d'être remis à
0 par le mot de passe correct (`:209-212`). Ouvrir une session Streamlit neuve et
resoumettre le mot de passe (connu) reforge un `_totp_pending`. `valid_window=1` ⇒ trois
codes vivants par fenêtre de 30 s, soit 10⁶/3 sans plafond serveur.

Demande le mot de passe d'abord — d'où P2 et non P1.

### R27 — Le détecteur de contamination a des trous connus (P2)

`tools/tenant_contamination_check.py:59-67` liste 8 tables. Cinq portent
`id_column=None` (`youtube_video_stats`, `instagram_media`, `soundcloud_tracks_daily`,
`meta_campaigns`, `meta_ads`), donc seul le cas ORPHELIN s'y applique : une ligne
étrangère chez un locataire qui A déclaré la plateforme est invisible. Et il n'y a
**aucune entrée Spotify** — seulement la jointure `track_popularity_history`↔`tracks`.

C'est l'étape 5 de `artist_preflight`, celle qui dit « les données ne sont pas celles
d'un autre ». Elle en dit moins que son nom.

### R28 — 25 classes d'erreur sans `root_cause` ni `long_term_fix` (P3)

`python3 .claude/scripts/audit_runner.py --fields` les nomme. Dette héritée, antérieure
au schéma ; le cliquet tient (aucune classe neuve incomplète depuis). Les solder rend le
catalogue utilisable pour la question qui compte : « ce défaut, on l'a déjà eu ? ».

### R29 — Budget de graphiques, maintenant sourcé (P3)

`make chart-budget` : 22 vues, 83 graphiques, médiane 3, `trigger_algo` à **15**.
Le corpus tranche enfin (R17) — Few, *Information Dashboard Design* p.27 : *« A dashboard
fits on a single computer screen … entirely within the viewer's eye span »*, et p.97 : la
zone haut-gauche porte les mesures décisives, pas la navigation. Le critère n'est donc
pas un nombre mais le coup d'œil. Motif déjà appliqué : `secondary_analyses()`
(instagram 4→2, soundcloud 2→1, spotify 4→3).

### R30 — Constats BAS du pentest, groupés (P3)

Aucun exploitable seul ; tous réels :
- `auth.py:64` lit `rate_window_start`, la vraie clé est `_rate_window_start` (`:65`) — la fenêtre se réinitialise à chaque échec. Échoue *fermé*, mais le limiteur ne fait pas ce qu'il se lit faire.
- `api/routers/artists.py:24` — `if not artist_id: return {"role": "admin"}` : le test de véracité que `require_artist_scope` existe pour supprimer (`api/deps.py:56-70` le dit).
- `credentials/_core.py:338-340` — le refus d'unicité affiche l'`artist_id` **de l'autre locataire**.
- `auth.py:506-509` — le logout laisse `_totp_pending` (qui contient `totp_secret`) dans la session.
- `verification_email.py:180` — secret de désinscription qui retombe sur un littéral en dur.
- `credentials/_core.py:61-80` — la docstring promet « jamais `config.yaml` », le code le lit.
- `airflow/dags/weekly_digest.py:206,245` — noms de titres non échappés dans l'e-mail.
- `.github/workflows/ci.yml:177` — une clé Fernet valide est commitée (CI seulement aujourd'hui).
- `src/utils/http_logger.py:74,79` — **code mort** qui masque l'URL puis réajoute l'exception non masquée : le défaut à l'intérieur du composant écrit pour l'empêcher. À supprimer, pas à réparer.

### R31 — `kpi_helpers.SOURCES_CONFIG` (P4, différé volontairement)

Cinquième registre plateforme→table. L'accord sur les libellés partagés est **gardé**
(`test_platform_sources_agree`), mais il n'est pas dérivé : il porte des sources que
readiness ignore (iMusician, Apple) et alimente une requête UNION ALL avec ses propres
allowlists. Le faire dériver changerait le comportement d'un code qui marche, pour un
gain nul. Inscrit pour que le choix soit visible, pas pour être fait.


## 🛡️ R21 — Pentest complet (clos côté code le 2026-08-22)

Deux passages : un sur le diff de la séance, un sur toute l'application (auth, API,
isolation SQL, injections, secrets, Stripe, upload). **Six constats CRITIQUE/HAUT,
tous corrigés, gardés, déployés et vérifiés en production.**

| sév | constat | vérifié en prod |
|---|---|---|
| CRITIQUE | `ig_user_id` interpolé dans un chemin Graph API : `me/accounts` faisait appeler `/me/accounts` **avec le System User token de la plateforme**, réponse (Page tokens) renvoyée au locataire | exploit rejeté |
| HAUT | Export PDF : `HTML(string=…)` sans `url_fetcher` ⇒ SSRF aveugle depuis le conteneur + lecture d'un fichier serveur dans le PDF téléchargé. Charge plantée via un **nom de fichier CSV** ou un nom de campagne. Un admin générant le rapport d'un locataire la déclenchait dans SA session | `http://` et `file://` bloqués |
| HAUT | `META_ACCESS_TOKEN` + `META_APP_SECRET` écrits **chaque nuit** dans les logs Airflow et l'e-mail d'échec, par tous les collecteurs | rédigés |
| HAUT | Limiteur de débit contournable : `X-Forwarded-For[0]` est choisi par l'appelant ⇒ verrouillage de tous les comptes indéfiniment possible par un anonyme | 50 requêtes forgées → 1 compartiment |
| HAUT | Unicité d'identité Instagram **inatteignable** (appelée avec la clé d'onglet) | corrigé |
| MOYEN | Nom d'artiste injecté brut dans l'e-mail HTML ; allowlist SQL se testant contre sa propre sortie | corrigé |

**Zones auditées et propres** (à ne pas ré-auditer sans raison) : isolation locataire
dans les 71 lectures de tables scopées ; **zéro** injection SQL de valeur sur 118 sites
de SQL dynamique ; IDOR — `st.query_params` ne touche jamais `artist_id`, et aucune
route FastAPI n'est pilotable par paramètre ; Stripe — le webhook échoue **fermé** sans
secret, et aucun chemin applicatif n'écrit `tier` hors webhook signé ; injection de
commande et traversée de chemin — un seul `subprocess`, sans entrée utilisateur ;
`defang_formulas` couvre **tous** les chemins d'export ; XSS Streamlit — les 11 sites
`unsafe_allow_html` sont échappés ou numériques ; Fernet — aucune clé commitée.

**Ce qui reste et n'est PAS du code** — dans `## 🙋 En attente de toi` :
un test d'intrusion réseau externe (Cloudflare, Caddy, ports, TLS), un fuzzing des
endpoints, et `pip-audit -r requirements.txt` (non lancé : l'outil n'est pas installé ;
`python-jose` est en 3.5.0 et `decode_token` épingle `HS256`, donc la confusion
d'algorithme ne s'applique pas ; `passlib==1.7.4` n'est plus maintenu depuis 2020).

Constats MOYEN/BAS documentés et différés **nommément** dans
`.claude/dev-docs/error-classes.md` et le rapport d'audit — pas par omission.

---

## 🛡️ R22 — Volet non-code du pentest, clos le 2026-08-22

- [x] **`pip-audit`** — une vulnérabilité, `ecdsa 0.19.2` / PYSEC-2026-1325 : attaque
      temporelle Minerva sur la **signature** P-256, sans correctif prévu en amont
      (python-ecdsa considère les canaux auxiliaires hors périmètre). Non applicable :
      `ecdsa` n'arrive que transitivement par `python-jose` et nos JWT sont HS256 à
      l'encodage comme au décodage. `make audit-deps` rejoue le contrôle et l'ignore
      **nommément** ; toute autre vulnérabilité fait échouer la cible.
- [x] **Test d'intrusion réseau externe** — scan TCP de l'origine `167.233.92.1` sur 33
      ports usuels : **seul 22 répond**. Ni Postgres (5433), ni Airflow (8080), ni
      Streamlit (8501) ; 80 et 443 ne sont pas joignables en direct non plus. Les noms
      d'hôte résolvent sur Cloudflare et n'ont donc pas été scannés — infrastructure
      d'un tiers. TLS des trois noms : zéro protocole obsolète, ni Heartbleed ni CCS
      injection ni ROBOT, certificats valides sur 5/5 magasins. **Un écart trouvé** :
      le dashboard n'avait ni CSP ni `Permissions-Policy` là où l'API en a — parce que
      celles de l'API viennent du middleware FastAPI et pas de Caddy, ce qu'aucune
      lecture du dépôt ne montrait. `deploy/Caddyfile` corrigé (CSP volontairement
      étroite : rien sur `script-src`/`style-src`, qui blanchirait Streamlit).
- [x] **Fuzzing des endpoints** — contre une instance **locale** du même code, parce que
      `/openapi.json` est désactivé en prod et que fuzzer une base de production y écrit.
      **Un vrai défaut** : `GET /streams/timeline?song=a%00b` renvoyait 500, un octet NUL
      atteignant psycopg2 via une `ValueError` non rattrapée. Corrigé à la frontière
      (400), gardé par `tests/test_api_survives_hostile_input.py`, classe
      `input-nobody-would-type-reaches-the-driver`. Re-fuzzé : 4 graines, 1730 cas,
      zéro 5xx.

Leçon : le volet avait été classé « en attente d'un humain » sur un raisonnement faux —
« hors du VPS » ne veut pas dire « hors de portée », et la machine de développement en
est une. Le premier essai a d'ailleurs produit neuf faux « Server error » avant qu'on
remarque qu'ils étaient tous des 503 dus à un mauvais mot de passe local : un fuzz doit
commencer par prouver que sa baseline répond 200.

---

## 🔌 Chaîne credentials → collecte : prouvable en continu (2026-08-22, hors numérotation)

Demandé après deux échecs de session bêta sur le même thème — les identifiants d'un
artiste ne produisaient rien sur le VPS (Benken 06/2026, GRiNCH 08/2026). Point de
départ contre-intuitif, mesuré : **les détecteurs existaient, tournaient et voyaient
juste.** Le problème était au-dessus et en dessous d'eux.

- [x] **P1 — un ré-enregistrement d'onglet détruisait un secret.** Les onglets
      `soundcloud` et `meta` n'ont aucun champ secret, donc sauvegardaient toujours un
      blob vide, et l'`ON CONFLICT` écrasait. En prod ces lignes portent le
      `refresh_token` OAuth (228 o) et le **token System User dont dépend la collecte
      Meta et Instagram de toute la flotte** (804 o). Un clic les supprimait, sans
      message. Prouvé corrigé en prod sur le vrai token : 804 o avant, 804 après.
- [x] **La livraison de l'alerte n'était pas prouvée, et elle avait lâché** trois
      nuits (16-18/08) — `send_alert()` renvoie `False` sans SMTP, la valeur était
      jetée, « Consolidated alert sent » journalisé quand même. `deliver_or_raise`
      fait échouer la tâche ; `monitoring_run` (mig. 073) en garde la trace ; un
      balayage AST interdit tout envoi dont le résultat est jeté (il a trouvé deux
      autres sites). Vérifié en prod : `Marking task as FAILED`.
- [x] **Le diagnostic vivant est devenu automatique.** `artist_readiness` lit la base
      et devinait ; `CONNECTION_TESTS` appelle l'API et sait. Les deux ne se parlaient
      pas. Désormais la sonde tourne **là où la base est déjà rouge** — 2 appels par
      nuit, pas 35 — et sa réponse remplace la devinette. Mesuré en prod :
      Benken/Meta rend l'erreur Facebook littérale `(#200) … has NOT granted
      ads_management`, GRiNCH/SoundCloud rend « aucun titre public ».
- [x] **Le titre de l'alerte nomme enfin les locataires** :
      `🔴 NE COLLECTE PAS : Benken (Meta Ads), GRiNCH (SoundCloud)`. Il pouvait être
      **vide** : les quatre signaux par locataire ne contribuaient à aucun sujet.
- [x] **`silent_zero_findings` supprimé** — écrit pour cette classe exacte, appelé par
      son seul test. Son prédicat est déjà celui de `readiness_red_flags`, qui tourne.
- [x] **Le garde d'isolation de flotte voyait une compréhension de liste comme rien.**
      `check_data_freshness:215` n'avait aucun try possible ; un locataire en erreur
      faisait échouer la tâche et le mail partait amputé. Le garde matche désormais
      l'itérateur, pas le nom de variable.
- [x] **Titres hébergés sur d'autres comptes** (cas GRiNCH, `track_count=0` sur son
      profil) : `GET /tracks/{id}` rend les stats quel que soit l'hôte (vérifié).
      `track_platform_link.platform_ref_id` existait déjà ; mig. **074** rend une
      revendication exclusive, le collecteur les ajoute, le test de connexion cesse
      d'être rouge, et l'onglet SoundCloud a le champ pour les coller.
- [x] **Le cron hôte lit le ledger de livraison** — par Brevo, donc il survit à la
      panne SMTP qu'il surveille. Vu crier en prod avec un seuil abaissé.

**Écarté volontairement** : « le compose ne câble pas `SOUNDCLOUD_*` » — vérifié faux,
`docker-compose.yml` est gitignoré, l'exemple suivi les câble et la prod aussi. Et un
endpoint API exposant la santé de collecte : nouvelle surface authentifiée publique
pour un bénéfice que le ledger donne déjà.

Quatre classes capitalisées : `resave-erases-a-secret-the-form-cannot-show`,
`delivery-failure-logged-as-success`, `static-hint-contradicts-the-live-probe`,
`detector-written-and-never-called`. 87 classes, 1371 tests verts.

---

## 🔍 Six correctifs d'audit + matrice de setup (2026-08-22 nuit, hors numérotation)

- [x] **Déclenchement de collecte refusé, invisible** — `trigger_dag` renvoie
      `{'success': False}` sans lever ; l'artiste lisait « enregistré » et rien ne
      partait. Balayage AST étendu à `trigger_dag`.
- [x] **Deux horloges dans le moniteur de fraîcheur** — âge de **−1 h** mesuré ;
      l'âge est désormais calculé par Postgres.
- [x] **Audit nocturne** — portée dérivée du registre (Instagram n'était jamais
      audité) et présence jugée sur l'identité, pas sur la vacuité du dictionnaire.
- [x] **Upsert Meta** — `collected_at` rafraîchi ; 17 545 UPDATE avec un horodatage
      de mai.
- [x] **Deux portes sur une base** — `get_db_connection` route vers
      `from_env_or_config()` ; cliquet sur les 14 lecteurs directs restants.
- [x] **Clé Fernet malformée ≠ absente** ; bandeau KPI remplacé par la matrice.
- [x] **Matrice de setup** — Configuré / Répond / Données sur les 5 plateformes, un
      seul renderer (`utils/status_matrix.py`), quatre surfaces, **zéro appel API au
      rendu**, verdicts mémorisés par la nuit (mig. 075).

Écarté après vérification : « Meta figé depuis 85 jours » — faux, le code avait raison.

Cinq classes capitalisées. 92 au total, 1399 tests verts.


### R47 · R48 · R49 · R53 — L'index actionnable, vidé (clos 2026-08-24)

Quatre entrées, une séance. Le fil commun n'était pas prévu : **trois des quatre
décrivaient une couche présente que rien n'exécutait**, et dans les trois cas la
brancher telle quelle aurait cassé la production — parce que ce que la couche
supposait du reste du code n'était plus vrai depuis longtemps, et que rien ne
pouvait le signaler tant que personne ne l'appelait.

- [x] **R53 — Meta multi-comptes, livré (2/3 et 3/3).** Décision produit :
  **comptes séparés** (ADR-013). `account_ids` canonique sous une seule ligne de
  credentials ; boucle collecteur sur N comptes ; migration 077 met
  `ad_account_id` dans la clé d'unicité des dix tables à la maille campagne, avec
  `NULLS NOT DISTINCT` — sans quoi la contrainte aurait cessé de dédupliquer
  l'historique et AJOUTÉ un doublon chaque nuit. Sélecteur de compte sur les cinq
  vues Meta et sur le formulaire d'export PDF, rendu seulement à partir de deux
  comptes. Le test de connexion sonde désormais **tous** les comptes ; une panne
  sur l'un n'empêche plus les autres de collecter, et la tâche reste rouge.

- [x] **R47 — validateurs Meta Ads : branchés, après correction.** La ROADMAP les
  disait « exactement la forme des payloads ». Ils ne l'étaient pas, et les
  brancher tels quels aurait **arrêté la collecte** : quatre divergences, trouvées
  une par une en les branchant — aucun ne déclarait `artist_id` (le seul champ dont
  ce dépôt ait réellement souffert), `status` était obligatoire alors que le
  collecteur écrit `.get('status')`, `targeting` était typé `dict` alors qu'on
  écrit une chaîne JSON, et `MetaInsight` exigeait dix métriques non nulles que
  Meta ne rend pas sur un objectif d'engagement. Le test passait *parce que* rien
  n'exécutait les modèles : il les confrontait à des payloads inventés par le test.

- [x] **R48 — `error_handler.py` retiré, pas câblé.** Ses trois fonctions
  interpolent l'exception brute — l'invariant du dépôt est *ne jamais interpoler
  une exception brute, nulle part* — et `safe_call` / `log_errors(reraise=False)`
  sont un helper béni pour avaler une exception et rendre `None`, exactement ce que
  la règle transverse #6 interdit. Module, tests, ligne d'architecture et référence
  dans `response-protocol/SKILL.md` retirés ensemble.

- [x] **R49 — le lock régénéré, et l'audit repointé.** 127 avis sur 18 paquets →
  **12 sur 2**, dont `pyjwt` (notre authentification), `starlette`,
  `python-multipart`. La cause de fond était ailleurs : l'audit nocturne lisait
  `requirements.txt`, un fichier de **planchers** que rien n'installe tel quel,
  pendant que la CI installait `uv.lock`. Il lit désormais le lock **résolu**
  (`uv export --frozen`). Restent `apache-airflow` (pin délibéré sur la version de
  l'image → R49b, resté ouvert) et `ecdsa` (sans correctif amont).

Détail d'origine des quatre entrées, conservé tel quel :

### R47 — Les validateurs Meta Ads existent et ne sont jamais appelés · P2

`src/models/meta_ads_validators.py` définit `MetaCampaign`, `MetaAdset`, `MetaAd` et
`MetaInsight` — exactement la forme des payloads que `_meta_upsert.py` écrit. **Aucun
code de production ne les importe** ; seul `tests/test_validators.py` le fait. Et
`_meta_upsert.py` ne valide que le **nom de table** (`validate_table`, l'allowlist SQL de
la règle #8), jamais le contenu.

Ce que ça vaut : `CLAUDE.md` présente `models/` comme une couche de l'architecture
(« Pydantic validators »), et Meta Ads est la plateforme qui a coûté le plus d'incidents
de données à ce dépôt. `audit_tenant_writes.py` signale d'ailleurs les payloads de
`_meta_upsert.py` comme « not statically resolvable » — c'est précisément la question
qu'un validateur trancherait.

- [x] **R47** — trancher, puis faire : soit brancher les quatre modèles dans
      `_meta_upsert.py` (et le dire dans l'architecture), soit les retirer et cesser
      d'annoncer une couche de validation qui n'existe pas. Ne pas laisser l'ambiguïté :
      une couche écrite et débranchée donne la confiance sans la propriété.
      Vérif : un payload Meta malformé doit être refusé (mutation), et
      `audit_tenant_writes.py` ne doit plus dire « not statically resolvable » sur ces
      trois sites.

### R48 — Deux modules ne vivent que par leur propre test · P4

| Module | Importé par |
|---|---|
| `src/utils/error_handler.py` (`log_errors`, `log_and_raise`, `safe_call`) | `tests/test_error_handler.py` **uniquement** |
| `src/models/meta_ads_validators.py` | `tests/test_validators.py` **uniquement** (→ R47) |

Le motif est trompeur par construction : le test passe, la couverture a l'air bonne,
l'architecture décrit le module comme porteur, et **rien ne l'exécute**. Le test protège
du code mort et empêche de le retirer sans discussion.

- [x] **R48** — trancher chacun : câbler (et le prouver par un appelant réel) ou retirer
      (module ET test ET la ligne d'architecture). `error_handler.py` est de surcroît
      cité comme exemple canonique de « Utility » dans
      `.claude/skills/response-protocol/SKILL.md` — une référence à retirer aussi si le
      module part.

---

### R49 — Le lockfile épingle des versions vulnérables que la prod n'exécute pas · P3
`pip-audit` sur le venv local : **18 paquets vulnérables, 127 avis**. Le réflexe serait
d'alerter — la mesure dit l'inverse. Ce que la **production** exécute :
| Paquet | venv local (`uv.lock`) | prod api/dashboard |
|---|---|---|
| `pyjwt` | 2.12.1 ⚠️ | **2.13.0** ✅ |
| `cryptography` | 48.0.0 ⚠️ | **50.0.0** ✅ |
| `starlette` | 1.0.0 ⚠️ | **1.6.0** ✅ |
| `python-multipart` | 0.0.28 ⚠️ | **0.0.32** ✅ |
| `pillow` | 10.4.0 ⚠️ | **12.3.0** ✅ |
La cause : `requirements.txt` déclare des **planchers** (`cryptography>=42.0.0`), donc
l'image Docker installe la dernière version satisfaisante, pendant que `uv.lock` fige des
versions exactes et anciennes. **La CI, qui fait `uv sync --frozen`, teste donc du code
que la production n'exécute pas** — c'est la famille `streamlit-pin-drift`, dans le sens
qu'on n'attendait pas.
Le conteneur **Airflow** est l'exception inverse : il tourne `apache-airflow 2.8.1`,
`sqlparse 0.4.4`, `aiohttp 3.9.1`, `pyjwt 2.8.0` — en retard, lui, pour de bon. Gravité
mesurée et non supposée : il n'écoute que sur `127.0.0.1:8080`, UFW n'ouvre 80/443 qu'aux
plages Cloudflare, et rien ne le publie. C'est de la défense en profondeur, pas une
surface exposée.
- [x] **R49** — décider et faire : soit `uv.lock` est régénéré pour suivre les planchers
      (`uv lock --upgrade`) et la CI teste enfin ce que la prod exécute, soit les deux
      manifestes sont alignés dans l'autre sens. Ne pas laisser deux vérités.
      Vérif : `pip-audit` sur le venv issu du lock, et comparaison avec
      `docker exec streamlytics_api pip list` — les versions critiques doivent coïncider.
### R53 — Meta multi-comptes, suite · P2

**Fait (1/3, déployé)** : `migrations/076` ajoute `ad_account_id` aux 10 tables à la maille
campagne et aux 3 de provenance (13 colonnes, appliquée en prod), et le `DELETE` de
`_prune_renamed_campaigns` porte désormais le même discriminant que ce qu'il vient
d'écrire. Sans ça, la boucle sur deux comptes aurait fait **effacer par le second tout ce
que le premier venait d'écrire** — corrigé avant que le cas existe, sinon il n'aurait été
visible qu'en constatant des données manquantes.

- [x] **R53 (2/3)** — boucle collecteur sur N comptes. `self.ad_account` est un attribut
      unique (`meta_ads_api_collector.py:101`) ; `_current_ad_account_id` doit être
      alimenté à chaque tour, sinon le scope du prune est écrit mais vide. Mécanique, mais
      à faire avant l'étape suivante.
- [x] **R53 (3/3)** — remplacer les contraintes d'unicité des 10 tables (aujourd'hui sur
      `campaign_name` seul : deux comptes ayant une campagne du même nom écrivent la même
      ligne), puis le stockage (`UNIQUE(artist_id, platform)` et un `account_id` scalaire ;
      `identity_is_well_formed` rejette une liste, et `find_identity_conflict` **interdit
      déjà que deux artistes partagent le compte d'une agence**), puis l'interface.
      **Dans cet ordre.**

### R47 — Les validateurs Meta Ads existent et ne sont jamais appelés · P2

`src/models/meta_ads_validators.py` définit `MetaCampaign`, `MetaAdset`, `MetaAd` et
`MetaInsight` — exactement la forme des payloads que `_meta_upsert.py` écrit. **Aucun
code de production ne les importe** ; seul `tests/test_validators.py` le fait. Et
`_meta_upsert.py` ne valide que le **nom de table** (`validate_table`, l'allowlist SQL de
la règle #8), jamais le contenu.

Ce que ça vaut : `CLAUDE.md` présente `models/` comme une couche de l'architecture
(« Pydantic validators »), et Meta Ads est la plateforme qui a coûté le plus d'incidents
de données à ce dépôt. `audit_tenant_writes.py` signale d'ailleurs les payloads de
`_meta_upsert.py` comme « not statically resolvable » — c'est précisément la question
qu'un validateur trancherait.

- [x] **R47** — trancher, puis faire : soit brancher les quatre modèles dans
      `_meta_upsert.py` (et le dire dans l'architecture), soit les retirer et cesser
      d'annoncer une couche de validation qui n'existe pas. Ne pas laisser l'ambiguïté :
      une couche écrite et débranchée donne la confiance sans la propriété.
      Vérif : un payload Meta malformé doit être refusé (mutation), et
      `audit_tenant_writes.py` ne doit plus dire « not statically resolvable » sur ces
      trois sites.

### R48 — Deux modules ne vivent que par leur propre test · P4

| Module | Importé par |
|---|---|
| `src/utils/error_handler.py` (`log_errors`, `log_and_raise`, `safe_call`) | `tests/test_error_handler.py` **uniquement** |
| `src/models/meta_ads_validators.py` | `tests/test_validators.py` **uniquement** (→ R47) |

Le motif est trompeur par construction : le test passe, la couverture a l'air bonne,
l'architecture décrit le module comme porteur, et **rien ne l'exécute**. Le test protège
du code mort et empêche de le retirer sans discussion.

- [x] **R48** — trancher chacun : câbler (et le prouver par un appelant réel) ou retirer
      (module ET test ET la ligne d'architecture). `error_handler.py` est de surcroît
      cité comme exemple canonique de « Utility » dans
      `.claude/skills/response-protocol/SKILL.md` — une référence à retirer aussi si le
      module part.

---

### R49 — Le lockfile épingle des versions vulnérables que la prod n'exécute pas · P3
`pip-audit` sur le venv local : **18 paquets vulnérables, 127 avis**. Le réflexe serait
d'alerter — la mesure dit l'inverse. Ce que la **production** exécute :
| Paquet | venv local (`uv.lock`) | prod api/dashboard |
|---|---|---|
| `pyjwt` | 2.12.1 ⚠️ | **2.13.0** ✅ |
| `cryptography` | 48.0.0 ⚠️ | **50.0.0** ✅ |
| `starlette` | 1.0.0 ⚠️ | **1.6.0** ✅ |
| `python-multipart` | 0.0.28 ⚠️ | **0.0.32** ✅ |
| `pillow` | 10.4.0 ⚠️ | **12.3.0** ✅ |
La cause : `requirements.txt` déclare des **planchers** (`cryptography>=42.0.0`), donc
l'image Docker installe la dernière version satisfaisante, pendant que `uv.lock` fige des
versions exactes et anciennes. **La CI, qui fait `uv sync --frozen`, teste donc du code
que la production n'exécute pas** — c'est la famille `streamlit-pin-drift`, dans le sens
qu'on n'attendait pas.
Le conteneur **Airflow** est l'exception inverse : il tourne `apache-airflow 2.8.1`,
`sqlparse 0.4.4`, `aiohttp 3.9.1`, `pyjwt 2.8.0` — en retard, lui, pour de bon. Gravité
mesurée et non supposée : il n'écoute que sur `127.0.0.1:8080`, UFW n'ouvre 80/443 qu'aux
plages Cloudflare, et rien ne le publie. C'est de la défense en profondeur, pas une
surface exposée.
- [x] **R49** — décider et faire : soit `uv.lock` est régénéré pour suivre les planchers
      (`uv lock --upgrade`) et la CI teste enfin ce que la prod exécute, soit les deux
      manifestes sont alignés dans l'autre sens. Ne pas laisser deux vérités.
      Vérif : `pip-audit` sur le venv issu du lock, et comparaison avec
      `docker exec streamlytics_api pip list` — les versions critiques doivent coïncider.
### R53 — Meta multi-comptes · P2 — **brique de schéma, pas d'UI**

Besoin **confirmé** (agence de Tom). R14 avait été clos avec « rouvre quand un locataire
déclare un second compte » : le déclencheur s'est produit.

Trois blocages, par coût croissant. Le troisième est le vrai :

1. **Stockage** — `UNIQUE(artist_id, platform)`, un seul `account_id` scalaire ;
   `identity_is_well_formed` rejette une liste, et `find_identity_conflict` **interdit déjà
   que deux artistes partagent le compte d'une agence**.
2. **Collecteur** — `self.ad_account` est un attribut unique. Mécanique.
3. **Schéma — perte de données silencieuse.** Les 10 tables d'insights à la maille campagne
   sont uniques sur **`campaign_name`**, sans discriminant de compte : deux comptes ayant une
   campagne du même nom **écrasent la même ligne**. Pire,
   `_prune_renamed_campaigns` (`_meta_upsert.py:87`) exécute
   `DELETE … WHERE artist_id = %s AND campaign_name <> ALL(%s)` — en boucle sur deux comptes,
   **le second efface tout ce que le premier vient d'écrire**.

- [x] **R53** — migration ajoutant `ad_account_id`, réécriture des contraintes d'unicité,
      mise à jour de `_insight_upsert_maps()`, re-clé du prune, puis boucle collecteur, puis
      UI. **Dans cet ordre** : livrer l'UI d'abord produirait des données silencieusement
      fausses. **Décision d'affichage à prendre** : comptes fusionnés (un total) ou séparés
      (un onglet par compte) — ça décide de la forme du schéma.


---

## Livré le 2026-08-26 — la séance des alertes

Quatre briques descendues de l'actif. R49b avait été livrée le 2026-08-24 sans être tournée ; R50, R51 et R52 étaient **en grande partie déjà faites** et leurs notes décrivaient un état antérieur au 2026-08-23 — vérifié point par point avant de cocher, jamais sur la foi du texte. Ce qui restait réellement est livré ce jour et gardé par mutation. La part de R51 marquée « métrique à préciser » n'est PAS cochée ici : elle attend une décision et remonte en « En attente de toi » (ADR-008).

### R49b — L'image Airflow de production est en retard · P3

Séparé de R49, livré le 2026-08-24 : le lock Python a été régénéré et l'audit
nocturne lit désormais le lock résolu. L'image Airflow, elle, ne vient pas du
lock — elle vient du `Dockerfile`, et c'est la seule dépendance réellement en
retard en production. `apache-airflow 3.2.2` porte 11 avis, tous corrigés en
3.3.1. Le pin est délibéré (il doit suivre la version de l'image), donc le
remonter est un changement d'infrastructure, pas de dépendance.

- [x] **R49b** — mettre à jour l'image Airflow (2.8.1 → ≥ 2.11.1). Non urgent au sens
      réseau, mais c'est la seule version réellement en retard en production.



### R50 — Le parcours de setup · P2

Quatre défauts structurels mesurés, tous invisibles à la lecture du code :

1. **Les guides d'API lus pendant les tests sont du code mort.**
   `_registry._render_platform_guide` et les quatre `_guide_*` des modules plateforme
   **n'ont aucun appelant** — ~450 lignes maintenues et traduites, qui **contredisent** les
   guides réellement affichés (`content/credential_guides.py`). Sur Spotify : le vivant dit
   « tu n'as rien à créer », le mort dit « crée une app, copie le Client ID et le Secret ».
2. **Le guide ANGLAIS est un miroir périmé du corpus mort**, et il est **expédié dans le
   PDF d'onboarding** quand `lang == "en"` : `Redirect URI = http://127.0.0.1:8888/callback`
   … `Tick Web API`. C'est la source exacte des notes « uri non bonne », « rajout de s sur
   uri », « web api pas cochée ». Le dépôt porte **trois orthographes** du même URI jetable
   (`127.0.0.1:8888`, `localhost:8888`, `http://localhost`), toutes en `http://`, aucune en
   `https://` — héritées du défaut de `spotipy`, que le tableau de bord Spotify **refuse
   désormais** sous la forme `localhost`.
3. **Le sélecteur Mac/Windows ne s'affiche jamais.** `os_hints.os_selector()` n'est appelé
   que par `render_credential_guides()`, **sans appelant**. Le chemin vivant devine l'OS par
   User-Agent, **Windows par défaut**, sans moyen de corriger. C'est la note GRiNCH.
4. **Le guide de démarrage a deux surfaces, dont une injoignable.** L'entrée de navigation
   pointe `process_guide.py` (quatre listes à puces plates, ni onglets ni dépliants) ;
   l'assistant qui porte la sélection cochable est `onboarding.py`, **absent de toute
   navigation**, joignable seulement par `?page=onboarding` depuis l'e-mail. Mail fermé,
   onglet fermé : il n'existe plus.

Et deux petits, à fort effet : les quatre étapes de l'accueil **nomment leur destination
sans y mener** (`home.py:168`, la clé de page est liée à `_` puis jetée), et le PDF
d'onboarding n'est **livré qu'en pièce jointe d'e-mail** — aucun bouton dans l'application.

- [x] **R50** — supprimer le corpus mort et ses traductions ; une seule chaîne d'URI définie
      une fois, en `https://` là où la plateforme l'exige ; afficher le sélecteur d'OS ;
      entrée de navigation permanente vers l'assistant + atterrissage automatique dessus à
      la première connexion tant que rien n'est configuré ; étapes d'accueil cliquables ;
      bouton de téléchargement du PDF ; lien `artists.apple.com` visible par un artiste
      (aujourd'hui seulement sur `useful_links`, **réservée admin**) ; définitions CSV
      remontées hors du dépliant replié ; captures YouTube ; étape « créer le projet Google
      Cloud » ; surbrillance de `soundcloud:users`. Unifier les **trois ordres de
      plateformes** (onglets / sélecteur d'onboarding / guides) et cesser de proposer
      Instagram et Apple Music dans l'onboarding alors qu'ils n'ont pas d'onglet.
      Vérif : parcours e2e dans un navigateur — première connexion, étapes cliquables,
      guide joignable depuis la navigation, sélecteur d'OS visible.



### R51 — La page qui donne la valeur · P2

`src/dashboard/utils/ui.py:83` — `secondary_analyses()` a été écrit **explicitement pour la
remarque de GRiNCH du 2026-08-12** (le commentaire du fichier la cite mot pour mot) et
applique « une décision par écran ». Il est utilisé sur 4 sites et sur **aucune** des cinq
vues les plus denses : `trigger_algo` (15 graphiques + jusqu'à 17 jauges ≈ **35 figures**),
`data_wrapped` (9), `meta_creatives` (8), `meta_ads_overview` (8), `revenue_forecast` (6).
C'est donc **appliquer un motif existant**, pas en inventer un.

L'accueil, lui, est un tableau d'état : **0 graphique**, 4 tuiles, 9 cartes de statut DAG.
Il dit si la machine tourne, pas ce que l'artiste doit faire. Few : un tableau de bord tient
dans un coup d'œil et sert de **rampe de lancement**. Knaflic : désencombrer ne suffit pas,
il faut ensuite **montrer où regarder**.

- [x] **R51** — appliquer `secondary_analyses()` aux cinq vues denses ; concevoir une page
      récap de 3 à 5 visuels répondant chacun à « dois-je faire quelque chose ? » ; déplacer
      Export PDF et Export CSV, aujourd'hui entrées **n°2 et n°3** de la navigation, avant
      le guide et les credentials — alors que `app.py:180` annonce « Order = user journey ».
      Ajouter la section PDF « 30 premiers jours vs actuel » sur le taux de trigger
      (**métrique à préciser**).



### R52 — Débloquer les deux artistes en test · P2

**GRiNCH / SoundCloud.** La fonctionnalité « Mes titres hébergés sur d'autres comptes »
**existe et fonctionne de bout en bout** (widget, `track_platform_link`, `migrations/074`,
consommation par le collecteur). Quatre défauts autour : le message d'erreur dit « ci-dessous »
alors que le widget est rendu **au-dessus** ; pas d'exemple d'URL ; `_claimed_count` a besoin
de `fields['_artist_id']`, injecté seulement dans l'interface — donc `artist_preflight` et la
sonde nocturne obtiennent **0** et rendent un rouge **à tort** ; et un **trou réel** : un
artiste **sans compte SoundCloud du tout** n'est jamais collecté, `soundcloud_daily.py:134`
le saute avant de lire ses déclarations.

**Benj / CSV.** Causes probables, par fréquence : séparateur `;` (**non supporté** — seuls
`,` et la tabulation sont testés), ligne de préambule au-dessus des en-têtes, `.xlsx`
non-SACEM, en-tête localisé. Et une **contradiction réelle** : un export `songs-all` est
*détecté* par son nom de fichier (règle 6) puis **rejeté** par `_detect_window`
(`s4a_csv_parser.py:99`).

- [x] **R52** — corriger les quatre défauts SoundCloud ; passer le fichier de Benj dans
      `_detect_platform` **quand il arrive** et corriger la règle qui l'a manqué, pas
      deviner ; nommer la raison du refus (le séparateur n'est jamais mentionné).


### R55 — La section PDF « 30 premiers jours vs actuel » · P3

Créée puis close le 2026-08-26, dans la même journée. Elle attendait une **définition**,
et les trois candidates que j'avais proposées étaient toutes fausses : part de
catalogue, portes par titre, délai médian — trois agrégats de PORTEFEUILLE. L'auteur du
produit a tranché en une phrase : **le taux de trigger est le % de chance d'intégrer
l'algorithme en question, et il porte sur UN SEUL titre.**

`ml_song_predictions` portait déjà exactement ça, avec `days_since_release` et
`model_version`. La section compare donc la médiane des 30 premiers jours à la mesure
courante, par porte, et refuse trois façons de mentir : soustraire deux versions de
modèle (la v3 est une reconstruction group-CV avec calibration OOF — l'écart mêlerait
le titre et le modèle), dessiner une absence en 0 %, et donner une valeur de fenêtre
sans son effectif.

- [x] **R55** — métrique définie, `src/utils/trigger_rate_history.py`, section branchée
      dans le PDF sur les rapports mono-titre uniquement, 12 tests, 4 mutations vues
      rouges.

### R54 — Le GIF animé à côté des e-mails · P4

Close le 2026-08-28, **vérifiée par son destinataire** : l'avatar est en place et il
bouge.

Trois diagnostics successifs, dont deux faux, et c'est le fil de la brique :

1. « quelque chose que l'application envoie » — faux. Vérifié le 2026-08-24 : aucun
   `<img>`, aucun `MIMEImage`, aucune URL distante dans les trois expéditeurs.
2. « le relais Brevo » — insuffisant. C'est la **photo de profil du compte Google
   expéditeur**, ce que seul le destinataire pouvait dire, et il l'a dit.
3. « il faut que ça bouge dans la ligne du mail » — **impossible, et c'est mesuré** :
   Gmail fige la frame 1 dans la liste dense et n'anime que les vues de profil
   dépliées. La règle de conception s'inverse donc : la frame 1 doit être un avatar
   complet, parce que la frame 1 EST la ligne du mail.

BIMI écarté sur un fait, pas sur son prix : `SVG Tiny PS` **interdit l'animation** — un
logo BIMI ne peut structurellement pas bouger. Il aurait fallu en plus passer
`_dmarc.streamlytics.fr` de `p=none` à `p=quarantine` et un certificat VMC payant, pour
un résultat immobile.

- [x] **R54** — `tools/dev/make_avatar_gif.py` → `assets/brand/avatar_streamlytics.gif`
      (256×256, 24 frames, 35 KB) dérivé de `logo_mark.svg` ; frame 0 = le logo exact,
      tout dans les 70 % centraux parce que Gmail recadre en cercle. Posé sur le compte
      Google expéditeur, confirmé en réception.

---

# 🔖 Historique des reprises — déplacé depuis `checklist.md` le 2026-08-28

Mesuré ce jour-là : `checklist.md` faisait 88 Ko (~22 600 tokens) et **72 % en était de
l'historique** — sept blocs REPRISE/Historique remontant au 2026-08-21, dont **deux
portaient tous les deux la mention « à lire EN PREMIER au `/resume` »**, ce qui ne peut
pas être vrai des deux. S'y ajoutaient deux sections dupliquées mot pour mot (le rapport
du graphe et les notes UI du 2026-08-23).

Or ce fichier est celui que `/resume` lit AVANT tout le reste, à chaque séance. Un
historique y coûte à chaque ouverture et n'y sert jamais : c'est de l'archive qui se fait
passer pour de l'état courant. Déplacé ici, pas supprimé — `tests/test_roadmap_two_files.py`
échoue si la somme des deux fichiers rétrécit.

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

## 🎨 Simplification UI/UX — notes des tests artistes (2026-08-23)

~30 notes de terrain issues des tests Benken (19/06) et GRiNCH (12/08). Plan complet et
approuvé : `~/.claude/plans/unified-mapping-teapot.md`. Cette section porte ce qui reste ;
ce qui est livré est descendu dans `archive.md` sous « R49b–Track 1 ».

### Ce que la mesure a corrigé dans les notes

Trois demandes étaient **déjà satisfaites ou périmées**, et il valait mieux le savoir avant
de coder : le nom d'expéditeur des mails (corrigé et déployé le jour même), les livres
d'ergonomie (11 ouvrages déjà ingérés, R17 close — ils sourcent le plan), le filtre de
période (retiré par l'auteur des notes). Et « case verte ou rouge par plateforme » **existe
déjà** (`status_matrix.py`, 3 colonnes, 4 surfaces) — c'était sa sémantique qu'il fallait
corriger, pas son absence.

## 🔖 REPRISE — état au 2026-08-24, séance close (à lire EN PREMIER au `/resume`)

**▶️ L'index de code est vide à une entrée près — R49b, qui est un changement
d'image Docker. Les quatre questions qui bloquaient sont tranchées.**

**2688 tests verts**, 22 skippés, ruff propre, `make config-check` clean
(**129 classes d'erreur**, 0 non gardée), 77 migrations appliquées.
✅ **Déployé et vérifié en production** : migration 077 appliquée, `prod == canonique`
(946 colonnes / 94 tables), DAG Meta déclenché → succès, 100 % des lignes stampées.

### Ce que la journée a livré, en une phrase chacun

| | |
|---|---|
| R53 | **Meta multi-comptes, séparés** (ADR-013) : N comptes sous une credential, clés d'unicité corrigées (mig. 077), sélecteur sur les 5 vues Meta **et** avant l'export PDF |
| R47 | Les validateurs Meta étaient **faux sur quatre points** ; les brancher tels quels aurait arrêté la collecte. Corrigés, puis branchés |
| R48 | `error_handler.py` **retiré**, pas câblé — il rouvrait la classe de fuite d'exception sur trois sites |
| R49 | Lock régénéré (**127 avis → 12**) et audit nocturne repointé du fichier de planchers vers le lock résolu |
| Questions | Les 4 tranchées ; 2 ont produit du code, 2 se règlent hors du dépôt |

### Le fil commun, à relire avant de reprendre

**Trois des quatre entrées décrivaient une couche présente que rien n'exécutait —
et dans les trois cas, la brancher telle quelle aurait cassé la production.** Non
pas parce que la couche était mal écrite, mais parce que ce qu'elle supposait du
reste du code n'était plus vrai depuis longtemps, et que rien ne pouvait le
signaler tant que personne ne l'appelait. Un test vert sur une forme inventée par
le test ne dit rien de la forme réelle.

C'est la suite directe du fil du 2026-08-23 (« du code correct que rien
n'atteignait »), avec une nuance neuve : **le code débranché n'est pas neutre, il
pourrit.** Plus il attend, plus le brancher devient dangereux.

### Trois défauts trouvés en chemin, aucun cherché

- **Un panier sans observation dessiné comme un 0 %.** Le graphique des portes
  algorithmiques du PDF affichait « 0 % de chance » là où la donnée dit « aucun
  titre observé » (Release Radar, panier « 50+ », n=0). Et 66,7 % sur **3** titres
  s'affichait aussi net que 99,4 % sur 172.
- **Le compteur public comptait nos propres robots.** « N artistes utilisent
  streaMLytics », sur la page d'inscription, incluait les canaris de surveillance.
  Et le nom d'artiste du propriétaire servait d'exemple à chaque inscription.
- **Le mail de rapport de crash partait par Brevo avec la traceback en clair**,
  donc potentiellement un `access_token=` d'URL préparée. Le garde anti-fuite ne
  pouvait pas le voir : sa portée suit le **graphe d'imports**, et cette exception
  arrive en **argument**. Septième fois que la portée d'un garde est le défaut, et
  la première où l'élargir au graphe d'imports n'aurait rien donné.

### Ce que la vérification AVANT déploiement a rattrapé

Les validateurs fraîchement branchés refusaient **70 lignes déjà en base** : une borne
`max_length=255` **inventée** (les colonnes sont des `text`, et la prod contient une
campagne de 313 caractères) et un `targeting` typé `str` alors que la colonne est
`jsonb`. Comme les modèles **lèvent**, la collecte Meta se serait arrêtée dès la nuit
suivante. **Quand on branche une validation qui lève, on lui montre la production
avant de déployer** — les tests unitaires du modèle lui présentent des payloads écrits
à la main, donc courts et propres.

Dans la foulée, trois défauts dans `circuit_breaker.py` (aucun appelant, deux panneaux
qui affirment une bonne santé sur une table que personne n'écrit, un contrat qui
prescrit `str(e)` pour une valeur persistée puis affichée), et un garde anti-fuite qui
**punissait l'application de son propre remède**.

### La sonde de production était morte, et son rouge passait pour du bruit

« Prod — Daily health check » échouait chaque matin depuis le 2026-08-23 : la
frontière HTTP `autouse` de `conftest.py` bloquait, au niveau socket, la seule suite
dont l'objet EST de sortir sur le réseau — celle qui regarde l'app **à travers
Cloudflare**. Sortie nommée posée (`@pytest.mark.real_http`), portée gardée, et
vérifiée en la lançant : **10 passed**, production saine.

**Une frontière `autouse` sans exception nommée n'est pas une frontière, c'est un
interrupteur.**

### Ce qu'il faut savoir avant de toucher au code demain

- **`make sync` installe enfin les outils de dev.** Il faisait `uv sync --frozen`
  sans `--extra dev`, là où la CI met `--extra dev` : la cible annoncée « one-shot
  dev setup » produisait un environnement sans pytest, ruff ni pre-commit — et
  enchaînait sur `hooks-install`, qui a besoin de pre-commit.
- **Le lock a bougé** (ruff 0.15.5 → 0.15.17, weasyprint 68 → 69, starlette 1.0 →
  1.6, pyjwt, uvicorn…). `uv sync --frozen --extra dev` avant de lancer quoi que
  ce soit.
- **Lancer la suite avec la base** : `docker start postgres_spotify_airflow` puis
  `uv run pytest tests/ -q -n auto --dist loadfile`.
- **Le sélecteur de compte Meta ne s'affiche qu'à partir de deux comptes.** Toute
  la flotte étant mono-compte, l'écran est identique à hier — c'est voulu, et ça
  veut dire que la fonctionnalité **ne sera visible qu'avec un vrai locataire
  d'agence**. Le chemin est couvert par des tests, pas par un clic.

### Ce qui reste

**R49b** (image Airflow, un `Dockerfile`), **R1** (inviter des proches) et **R54**
(un réglage Brevo, cosmétique). Plus le **déploiement de cette séance**, qui n'est
pas fait.

---

## 🔖 Historique — état au 2026-08-23, séance close

**▶️ Quatre entrées ouvertes, dont trois qui attendent une réponse de toi et une seule
qui est du code : R53 (2/3 et 3/3).**

1955 tests verts *au 2026-08-23* (chiffre d'époque — l'état courant est en tête de fichier), ruff propre, **117 classes d'erreur, 0 non gardée**, prod ==
`origin/main`, 76 migrations appliquées, 4 services sains. Tout ce qui suit est **déployé
et vérifié en production**.

### Ce que la journée a livré, en une phrase chacun

| | |
|---|---|
| Matin | Le rouge CI était déjà résolu mais pas prouvé (éviction `sys.modules`) ; un garde anti-fuite élargi à `tools/` **tuait le cron de dérive de 04h** — non commité, donc la prod ne l'a jamais porté |
| Midi | **La suite de tests envoyait de vrais mails à de vraies personnes**, puis appelait les APIs réelles. Deux frontières posées dans `conftest.py` |
| Après-midi | Le corpus relu contre le dépôt (R39→R46) ; `saas-architecture` était absent de l'index alors que son livre y était |
| Soir | Audit sécurité 18 points : **17 tenus**. Le trou — `showErrorDetails` non réglé, donc la **traceback partait au navigateur**, prouvé dans les deux sens via Chrome |
| Nuit | Les ~30 notes des tests artistes : **4 tracks sur 5 livrés** |

### Le fil commun des notes artistes, à relire avant de reprendre

La plupart ne décrivaient **pas du code faux, mais du code correct que rien n'atteignait**
— six occurrences le même jour. Un test de rendu ne dit jamais si une page est
**atteignable**, et un DAG qui saute un locataire le journalise proprement. C'est pourquoi
rien ne le signalait.

### Deux défauts qui touchaient de l'argent ou des données

- **Un lien de paiement non attribuable**, sur les deux surfaces : le client payait, le
  webhook faisait `if artist_id and customer_id:` et **ne provisionnait rien**.
- **Un nettoyage plus large que son écriture** : `_prune_renamed_campaigns` supprimait par
  LOCATAIRE ce qu'il venait d'écrire par COMPTE. Corrigé **avant** que le multi-comptes
  existe — sinon il n'aurait été visible qu'en constatant des données manquantes.

### Ce que la vérification AVANT déploiement a rattrapé

Les validateurs fraîchement branchés refusaient **70 lignes déjà en base** : une borne
`max_length=255` **inventée** (les colonnes sont des `text`, et la prod contient une
campagne de 313 caractères) et un `targeting` typé `str` alors que la colonne est
`jsonb`. Comme les modèles **lèvent**, la collecte Meta se serait arrêtée dès la nuit
suivante. **Quand on branche une validation qui lève, on lui montre la production
avant de déployer** — les tests unitaires du modèle lui présentent des payloads écrits
à la main, donc courts et propres.

Dans la foulée, trois défauts dans `circuit_breaker.py` (aucun appelant, deux panneaux
qui affirment une bonne santé sur une table que personne n'écrit, un contrat qui
prescrit `str(e)` pour une valeur persistée puis affichée), et un garde anti-fuite qui
**punissait l'application de son propre remède**.

### La sonde de production était morte, et son rouge passait pour du bruit

« Prod — Daily health check » échouait chaque matin depuis le 2026-08-23 : la
frontière HTTP `autouse` de `conftest.py` bloquait, au niveau socket, la seule suite
dont l'objet EST de sortir sur le réseau — celle qui regarde l'app **à travers
Cloudflare**. Sortie nommée posée (`@pytest.mark.real_http`), portée gardée, et
vérifiée en la lançant : **10 passed**, production saine.

**Une frontière `autouse` sans exception nommée n'est pas une frontière, c'est un
interrupteur.**

### Ce qu'il faut savoir avant de toucher au code demain

- **Lancer la suite avec la base** : `docker start postgres_spotify_airflow` puis
  `uv run pytest tests/ -q -n auto --dist loadfile`. Sans base, ~160 tests skippent en
  silence. Et l'invocation avec `-n auto --dist loadfile` est celle de la CI — un bug
  ordre-dépendant ne se voit qu'ainsi.
- **Aucun DAG n'est importable hors conteneur** (l'Airflow installé refuse
  `schedule_interval`) : un test qui passe par l'import **skippe en silence**. Les seuils
  vivent dans `src/utils/` (`volume_monitor.py`, `quality_gate.py`, `email_identity.py`).
- **Huit fois cette journée, le prédicat d'un garde visait le symptôme au lieu de la
  question** — dont deux gardes **verts sur leur propre défaut**, démasqués par la seule
  mutation. Ne jamais livrer un garde sans l'avoir vu rouge.
- **`graphify update` ajoute et ne retire pas** : le graphe référence 15 fichiers qui
  n'existent plus. Il oriente, il ne prouve pas.

### Le seul geste qu'aucune machine ne fera

**R1 — inviter des proches.** Tout le reste du filet est en place et prouvé.

---

## 🔖 Historique — état au 2026-08-23 (soir) (à lire EN PREMIER au `/resume`)

**▶️ L'index actionnable est vide. Il reste UNE entrée sur toute la roadmap : R1,
inviter des proches.**

**Séance du 2026-08-23 — la chaîne credentials → collecte est prouvable par locataire.**
Suite verte à la clôture de CETTE séance-là (1403 au départ ; le compte courant est dans
le bloc REPRISE en tête de fichier — un seul chiffre fait foi, et c'est le plus récent),
ruff propre, audit déterministe clean, `make config-check` clean, **98 classes d'erreur,
0 non gardée**. Détail complet dans le DEVLOG ; ce qui compte pour reprendre :

- **Un P1 de sécurité fermé** — la clé API YouTube partait en clair dans les logs Airflow
  chaque nuit. 16 modules, 64 sites. La portée du garde était le défaut, pour la 3ᵉ fois :
  elle est désormais la **fermeture transitive du graphe d'imports**, et l'invariant est
  *ne jamais interpoler une exception brute, nulle part*.
- **Une panne vivante corrigée** — Benken/YouTube échouait chaque nuit avec un DAG vert.
  La branche « chaîne sans vidéo » existait et était **inatteignable** : elle décidait sur
  une chaîne tronquée à 300 caractères alors que le mot cherché est à l'index 455.
- **`etl_run_log` enregistre les 5 plateformes** (il n'en avait jamais eu que Meta). Trois
  surfaces du dashboard s'allument avec — `etl_logs`, `alerts`, le KPI `has_runs`.
- **Le silence a trois maillons, chacun gardé** : `stale` alerte, `error` survit à
  l'e-mail, et deux tâches nocturnes s'ajoutent (`check_collection_outcomes`,
  `check_tenant_contamination` — cette dernière donne enfin un ordonnanceur à la seule
  classe dont ce dépôt a réellement souffert).
- **Les nuits calmes le redeviennent** — la cause n'était pas le canari mais le fait que
  la fraîcheur par locataire signalait **chaque source** là où readiness prend la
  meilleure. Trois suppressions, toutes mesurées, et un doute garde l'alerte.
- **`tools/check_env_parity.py`** — la parité env dépôt↔VPS n'existait nulle part.
  Vérifié contre la vraie prod : 27 variables sur 3 conteneurs, toutes présentes. Porte
  bloquante dans `deploy.sh`.
- **`data_quality_check` reste EN PAUSE, à dessein.** Il n'a **jamais** tourné, et sa
  sonde Meta passerait au vert sur la source la plus périmée de la prod. Verdict :
  `.claude/dev-docs/data-quality-check-verdict.md`.

### Ce que la reprise du soir a trouvé (2026-08-23, après déploiement)

Cinq sujets remontés depuis la boîte mail, tous tranchés :

- **P1 corrigé en prod — un lien de désinscription vers `localhost`.** `APP_BASE_URL`
  était réglé sur le dashboard et **absent du scheduler**, où `onboarding_report`
  construit le pied de page de désinscription. Chaque rapport d'onboarding portait donc
  `http://localhost:8501`. Câblé dans le compose (exemple **et** prod, gitignoré donc à
  la main), et `_BASE_URL` est passé d'une constante figée à l'import à une lecture **à
  l'appel** — figée, elle portait ce que l'environnement contenait au premier import.
  `check_env_parity.py` couvre désormais `APP_BASE_URL`, `ALERT_EMAIL` et le bloc SMTP :
  ma propre parité ne les listait pas, et une parité ne vaut que la largeur de sa liste.
- **Les mails de vérification en `localhost` venaient d'un run LOCAL**, pas de la prod
  (`APP_BASE_URL=https://streamlytics.fr` y est correct). Le nombre de mails s'explique
  par autant de tentatives d'inscription.
- **Le nom d'expéditeur « Music Cross Platform Dashboard & Trigger Spotify »** ne vient
  pas du code : celui-ci met `streaMLytics` par défaut et `SMTP_FROM_NAME` est absent des
  deux conteneurs. C'est le **nom d'expéditeur du compte Brevo**, qui écrase. → geste
  dans Brevo, § « En attente de toi ».
- **CI rouge : deux causes, une de moi.** `tools/check_index_coverage.py` cité dans ces
  fichiers **existe dans `knowledge-rag`, pas ici** — le garde des outils opérateur a eu
  raison de le signaler (`config-path-dangling`). Chemin qualifié en absolu. La seconde
  (`test_a_raising_probe_becomes_a_red_not_a_traceback`) est **antérieure** et dépend de
  l'ordre/état de la suite : reproduction en cours.
- **n8n `market-scores` désactivé.** Il tournait **16 fois par jour** (`15 7-22 * * *`),
  consommait de l'inférence Ollama et échouait au dernier nœud, alors que le projet est
  abandonné. Désactivé et n8n redémarré — geste **réversible**, rien n'est supprimé.
- **Cinq sites de fuite de plus dans `tools/`**, dont `artist_preflight.py` qui rend
  l'exception d'une sonde **au terminal de l'opérateur**. Portée du garde élargie à
  `tools/` — **troisième fois** que la portée est le défaut et non la logique.

### Ce que la reprise après coupure a trouvé (2026-08-23, soir)

La séance précédente s'est arrêtée **entre le fix et le commit** : 15 fichiers étaient
dans l'arbre de travail, non versionnés. Deux constats en sont sortis.

**Le rouge CI était déjà résolu, pas encore prouvé.** `test_a_raising_probe_becomes_a_red_not_a_traceback`
échouait parce qu'un *autre* fichier de test faisait `del sys.modules[…]` au lieu de
restaurer — l'éviction rend un second objet module, et un monkeypatch ultérieur patche
l'un pendant que le code lit l'autre. Fix et garde étaient écrits ; il manquait la
preuve. **1663 passed, 23 skipped** contre la vraie base, et le garde vu rouge sur le
défaut réel (ligne 192) puis vert après.

**Un défaut introduit par le fix précédent, lui, était vivant.** Élargir le garde
anti-fuite à `tools/` a ajouté `from src.utils.safe_error import safe_error` à six
scripts ; deux n'avaient pas le repo root sur `sys.path` et **mouraient au démarrage** —
`tools/dev/check_manifest_consistency.py` (porte CI, dont `audit_runner` lisait le crash
comme une dérive `streamlit-pin-drift` inexistante) et `tools/notify_schema_drift.py`,
**le cron de dérive de 04h en prod** : l'import censé le durcir le faisait taire, ce que
son propre commentaire annonçait deux lignes plus bas. Non commité, donc la prod n'a
jamais porté le défaut. Classe `tool-imports-the-app-without-a-path`, gardée par AST.

**Quatrième fois en trois jours que la portée d'un garde est le défaut** — ici,
l'élargissement a cassé les fichiers nouvellement couverts, dont le contrat d'exécution
diffère de ceux contre lesquels le garde avait été écrit. Et une leçon neuve : *un hit
d'audit sur une classe dont le symptôme ne correspond pas au dépôt se vérifie à la main
avant d'être cru* — une signature qui shelle hérite du code de sortie d'un crash et le
présente comme son propre verdict.

---

### Le corpus
Les 10 livres demandés sont arrivés et rangés (`divers` ne contient plus que des mails).
Trois doublons exacts, créés par un re-dépôt, ont été retirés. Deux domaines créés :
`qualite-logicielle` (tests + sécurité applicative) et `saas-architecture`. **L'ingestion
était encore en cours à la clôture** — vérifier avec
`python3 /home/timothe/knowledge-rag/tools/check_index_coverage.py` : la sortie
doit être vide. Sinon : `uv run python ingest.py`.

### Les deux leçons à relire avant d'écrire un garde
1. **La portée d'un garde est plus souvent le défaut que sa logique** — trois fois dans
   cette seule séance.
2. **Un prédicat doit épouser la question, pas le symptôme.** « Ce fichier contient-il ce
   mot » a donné 40 % de précision ; « cette lecture peut-elle doubler un total » en a
   donné 100 %.

---

## 🔖 Historique — état au 2026-08-23 (matin)

**▶️ L'index actionnable est vide. Il reste UNE entrée sur toute la roadmap : R1,
inviter des proches** — et c'est la seule qu'aucune machine ne peut faire à ta place.

**Séance du 2026-08-23 — le journal écrivait dans une copie que personne ne lit, et un
item « bloqué » ne l'était pas.**
Suite prouvée d'abord : **1399 passed, 17 skipped** contre la vraie base, ce que la
ligne ci-dessous annonçait — **1403 après le garde ajouté ce jour**. Puis, en soldant un brouillon DEVLOG resté non rempli
depuis deux jours : `/devlog-promote` et `draft_devlog.py` pointaient tous deux sur
`.claude/dev-docs/DEVLOG.md`, **gelé au 2026-06-11**, alors que le journal vivant —
celui que `/resume` lit — est `DEVLOG.md` à la racine. Conséquence mesurée : **deux
séances entières sans aucune page nulle part**, le 2026-08-21 (après-midi → nuit,
45 commits) et la nuit du 21→22. Les deux entrées manquantes sont écrites à partir des
commits, les deux écrivains sont repointés, la copie morte porte un bandeau ARCHIVE, et
la classe `pipeline-writes-to-the-copy-nobody-reads` est gardée par
`tests/test_devlog_is_written_where_it_is_read.py` — 4 assertions, chacune vue rouge par
mutation. Les six **lecteurs** étaient déjà corrects : c'est pourquoi la divergence
produisait du silence et non une contradiction.

Et pour la seconde fois en deux jours, **un item parqué comme bloqué ne l'était pas** :
« la config Caddy ne peut pas être validée ici, image indisponible » — elle l'est.
`make caddy-validate` rend **Valid configuration**, garde fail-fast sur Docker (règle #10),
vu rouge par mutation sur une directive cassée. La leçon du 2026-08-22 (« prouver qu'une
tâche est bloquée avant de la parquer ») s'applique aussi aux notes de bas de page.

---

## 🔖 Historique — état au 2026-08-22, séance close

Tout était déployé et vérifié : `prod == canonique`, **75 migrations**, code déployé ==
`origin/main`, `deploy/Caddyfile` == ce que Caddy sert, 1399 tests verts (état d'alors) contre une
vraie base, ruff propre, `audit_runner --deterministic` clean, `make config-check` clean,
93 classes d'erreur toutes gardées et complètes.

### Avant de conclure quoi que ce soit, demain

```
docker start postgres_spotify_airflow && python3 -m pytest tests/ -q
```
~160 tests exigent une base et **skippent en silence** sans elle. Toute la séance a
tourné avec.

### Les deux pannes de collecte encore vivantes en prod

Elles sont **réelles**, elles appartiennent à leurs propriétaires, et le produit les
nomme désormais correctement chaque nuit **en tête du sujet** de l'alerte :

- **Benken / Meta** — `(#200) Ad account owner has NOT granted ads_management` sur
  `act_65390907`. Geste de Benken, pas correctif de code.
- **GRiNCH / SoundCloud** — profil sans **aucun titre public** ; ses sorties paraissent
  sous d'autres comptes. La réponse est construite : l'onglet SoundCloud a le champ
  « Mes titres hébergés ailleurs ». Il reste à lui faire coller ses URLs.

### Ce que les trois séances du 2026-08-22 ont livré

**Matin — R23→R31 + R22.** Deux fuites d'authentification (oracle d'inscription,
révocation qui ne révoquait rien), la règle #7 rétablie sur 9 vues et non 4, le pentest
clos y compris son volet réseau — qui n'attendait personne, cette machine étant hors du
VPS. Un vrai 500 trouvé par fuzzing (octet NUL → psycopg2).

**Soir — la chaîne credentials → collecte rendue prouvable.** Fait contre-intuitif : les
détecteurs existaient, tournaient et voyaient juste. Ce qui manquait était **la preuve
que leur constat sortait de la boîte** — trois nuits d'alertes évaporées avec une tâche
verte — et **le diagnostic vivant**. Plus un P1 : ré-enregistrer l'onglet Meta détruisait
le token System User de toute la flotte.

**Nuit — six correctifs d'audit et la matrice de setup.** Un déclenchement de collecte
refusé était invisible ; le moniteur de fraîcheur comparait deux horloges (âge de −1 h
mesuré) ; l'audit nocturne n'auditait pas Instagram ; l'upsert Meta gelait son
horodatage ; deux portes mutuellement exclusives sur une base ; une clé Fernet malformée
annoncée « absente ». Et la matrice **Configuré / Répond / Données** sur les 5
plateformes, quatre surfaces, un seul renderer, **zéro appel API au rendu**.

### Les deux leçons transverses de la journée, à relire avant d'écrire un garde

1. **Un garde lit la structure, pas le texte.** Quatre gardes écrits ce jour ont échoué
   sur *leur propre commentaire* (`if not creds`, `get_db_connection()`, `probe=`,
   `send_alert`). Le piège n'est pas la gêne : c'est qu'on reformule la documentation
   pour faire taire le test. Inspecter du code ⇒ AST.
2. **Vérifier qu'une tâche est bloquée avant de la parquer.** « Hors du VPS » ne voulait
   pas dire « hors de portée » : les ⅔ de R22 se sont faits en vingt minutes après avoir
   été classés « en attente de toi ».

Et une règle qui a payé trois fois : **la fraîcheur EST la preuve, la sonde n'est que
l'explication.** Elle a dissous la question du budget d'API à chaque fois qu'elle s'est
posée — 2 appels par nuit au lieu de 35, et zéro au rendu d'une page.

### Deux points d'attention pour demain

- ~~`deploy/Caddyfile` n'a jamais été validé par un binaire Caddy depuis ce dépôt (image
  indisponible ici)~~ — **levé le 2026-08-23** : l'image l'était. `make caddy-validate`
  la valide en local (certs bidon montés pour que `tls <fichier> <fichier>` résolve) →
  **Valid configuration**. Vu rouge par mutation sur une directive cassée. Reste un
  avertissement `caddy fmt` : **ne pas reformater** — `sync-check` compare ce fichier
  octet par octet avec ce que sert la prod.
- Le hook RTK réécrit `git` en `rtk git` **à l'intérieur** d'une commande `ssh` : utiliser
  `/usr/bin/git` quand on pilote la prod.

## 🔖 Historique — état au 2026-08-21

> Bloc conservé pour le contexte. Les chiffres datés (taille du schéma, nombre de tests)
> en ont été retirés le 2026-08-22 : ce fichier est le premier que `/resume` lit, et deux
> états chiffrés s'y lisent comme deux prétentions au présent — c'est ce que
> `test_the_roadmap_never_states_two_different_test_counts` empêche. L'état d'hier est
> dans `archive.md` et le DEVLOG, datés.

**streaMLytics est EN PRODUCTION et lançable.** (détail : `[[project_production_deploy]]`, DEVLOG suites 7→14)

- 🌐 **Live** : https://streamlytics.fr (HTTPS Let's Encrypt · Hetzner **CPX32** Nuremberg `167.233.92.1` · `ssh root@167.233.92.1` via clé WSL `~/.ssh/id_ed25519` · code à `/opt/streamlytics`). Durci (ufw 22/80/443, fail2ban, SSH key-only), backup cron `pg_dump` 3h, postgres `restart: unless-stopped`.
- 💳 **Stripe** : **mode LIVE PROUVÉ end-to-end (2026-06-13)** — KYC validé, 4 env vars live sur le serveur, vrai paiement carte → webhook → `tier=premium` + annulation OK. Portail client actif. (détail : `[[project_stripe_state]]`)
- 👤 **Funnel d'inscription** : **COMPLET et validé en prod** (Brevo → inbox, login par **email** OU username, vérif instantanée, welcome + **2 PDF guide FR/EN** en PJ). Pré-requis **E1 validés**.
- ⚙️ **DAGs** : tous **activés** (étaient en pause par défaut !) → collecte quotidienne par artiste (Meta 5h/Spotify 7h/YT 8h/SC 9h/IG 10h/ML 11h UTC ; CSV watchers 15 min). Si Airflow recréé → ré-`unpause`.
- 🔌 **API REST** : **fonctionnelle en prod** (auth DB `saas_users`, lockout partagé, 2FA refusé, tenant-scoped). `POST /auth/token` → JWT.
- ⚙️ Déploiement = sur le serveur `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard` (ou `api`). Compte test QA supprimé.

**▶️ Séance du 2026-08-22 (nuit) — pourquoi « les credentials ne marchaient pas » : rien n'était en panne.**

Deux sessions artiste avaient échoué là-dessus. En cherchant ce qui restait après tous
les correctifs par symptôme, la réponse est plus simple et pire : **les deux
plateformes que l'onboarding recommande en premier échouaient sous les yeux de
l'artiste**, sans qu'aucune infrastructure ne soit en panne.

| # | ce qui se passait | mesuré |
|---|---|---|
| 1 | **La matrice Spotify lisait la table CSV.** Test de connexion vert nommant l'artiste, DAG qui collecte, écran 🔴 « Connecté — aucune donnée » jusqu'à un import CSV. | Spotify était jugée sur **quatre tables** selon l'écran. Vérifié en prod après correctif : le canari a **0 ligne CSV, 10 lignes API**, et readiness dit `ok`. |
| 2 | **Enregistrer un identifiant Instagram déclenchait `meta_ads_api_daily`**, jamais `instagram_daily` — aucune première collecte. L'entrée `'instagram'` de la carte était inatteignable par construction. | Le fichier se lisait comme si la fonctionnalité existait. |
| 3 | **L'onglet Meta mentait à chaque sauvegarde** : « ⚠️ Le renouvellement automatique ne fonctionnera pas », pour tout artiste, parce qu'il lisait trois champs que le formulaire ne déclare pas. Bouton de rafraîchissement idem. | Retiré, pas réparé : sous ADR-006 le token est central et n'expire pas. |
| 4 | **Instagram était exemptée de tout** : pas d'unicité d'identité (deux locataires pouvaient revendiquer le même compte en silence), pas de test de connexion, absente du canari et de l'alerte. | La même carte existait en **six exemplaires**, dont deux amputés. |
| 5 | **Un garde vert tenait le trou en place** : un test affirmait l'égalité entre les deux copies fausses, et les tests d'unicité se paramétraient sur la copie amputée — une entrée manquante y **retire des cas** au lieu d'en faire tomber un. | Vérifié par contraste : Instagram retiré, les paramétrés restent verts (8), seul le cliquet littéral tombe. |
| 6 | **Une sonde en panne s'affichait « Connecté — aucune donnée »** — `freshness_monitor` posait un champ `error` pour ça, personne ne le lisait. | Statut `BROKEN` ⚠️ qui ne demande **rien** à l'artiste. |
| 7 | **L'inscrit qui abandonne n'existait pour personne.** `readiness_red_flags` ne remontait que `NO_DATA` ; un locataire sans identité n'en produit aucune. | Première exécution en prod : **11 locataires bloqués** détectés. |
| 8 | **Le moniteur nocturne ne pouvait pas voir la cause littérale de Benken** : les sondes renvoient `True` sur env absent, et seul un humain tapant `--require` le voyait. | `central-app-missing` passe reported/manual → **guarded/deterministic**. |
| 9 | **Le portail go/no-go n'avait aucun test ni horaire.** Le runbook s'ouvre sur « on n'invite personne tant que `make artist-preflight` n'est pas vert ». | 9 tests + `check_canary_preflight` chaque nuit, scopé aux plateformes que le canari déclare. Exécuté en prod : **0 problème**. |

**Deux régressions à moi, trouvées en production et non en relecture.** Faire dériver
les cibles du watchdog m'a fait rendre la table `artists`, où `artist_id` est
l'identifiant Spotify VARCHAR — `operator does not exist: character varying = integer`,
soit la classe `column-name-is-not-its-meaning` que ce dépôt documente déjà. Et exiger
des lignes dans **toutes** les tables d'une plateforme rapportait le canari muet alors
qu'il collecte : `watchdog-becomes-the-noise` failli recréé. Les deux corrigées et
gardées. Ce qui a tenu : le contrat conservateur — la sonde a dit « could not run »
plutôt que « tout va bien ».

**Ce que ça dit des trois bêta-testeurs** : Benken et GRiNCH n'ont **jamais déclaré de
Spotify**, Cuzebo n'a rien du tout. Ils ont abandonné devant les écrans ci-dessus. Le
correctif ne les récupère pas tout seul — il empêche le prochain de vivre la même chose.

**Déployé et vérifié en production** (`prod == canonique`, 920 col / 92 tables,
71 migrations, code déployé == `origin/main`). 1220 tests verts contre une vraie base.

Classes : `same-platform-judged-on-different-tables`, `map-key-unreachable-by-construction`,
`guard-derived-from-the-thing-it-guards`, `broken-probe-rendered-as-user-fault`,
`row-existence-read-as-connection`, `gate-with-no-test-of-its-own`.

⚠️ **Un angle mort assumé** : les tests gardés par la base skippent en silence sans
Postgres sur 5433. J'ai développé les quatre vagues dedans, et la base a trouvé un vrai
défaut au premier lancement. Lancer la suite avec base avant de conclure.

**▶️ Séance du 2026-08-22 (suite) — R13 est clos, et il n'a jamais fallu régénérer.**

Trois séances avaient conclu qu'un token Meta était mort et qu'il fallait Business
Manager. Interrogé avec les credentials d'application corrects, il répond **valide** :
`SYSTEM_USER`, `expires_at=0`, 43 scopes — en local, en production, et dans
`artist_credentials`. La roadmap réclamait un geste humain pour un token qui marchait.

| # | livré | mesuré |
|---|---|---|
| 1 | **La correction du 2026-08-21 était allée dans le fichier qui perd** | `.env` était corrigé ; `.env.local`, qui **gagne** par construction, portait encore l'ID de compte publicitaire dans `META_APP_ID` et le token avec le `E` parasite. Tout Meta était cassé en local *sur une configuration réputée corrigée*. Les trois clés dupliquées retirées de `.env.local` — un seul fichier les possède. Classe `config-corrected-in-the-file-that-loses`. |
| 2 | **La sonde ne pouvait pas voir ce défaut** | `tools/check_central_apps.py` n'appelait jamais `load_project_env()` : depuis un shell nu, `⚠️ env not set` sur les quatre plateformes et **exit 0**. Frère manqué d'`env-resolved-against-cwd` — sa signature cherche la *mauvaise forme*, ici c'était l'*absence*. Câblée : **exit 1** nommant `1 extra character ('E')`, puis **exit 0** après nettoyage. Garde dérivé des outils que la doc fait lancer, donc un outil neuf est couvert le jour où il est documenté. |
| 3 | **L'ordre des fichiers d'env était recopié ailleurs** | `tools/notify_schema_drift.py` n'importe volontairement pas le paquet applicatif (un import cassé ne doit pas pouvoir museler l'alerte de dérive) — il relisait donc `.env` seul. Aligné sur `ENV_FILES` et **épinglé** dessus par test : un ordre recopié dérive. |
| 4 | **Pourquoi Meta ne renvoie rien, et pourquoi ce n'est pas une panne** | Vérifié sur l'API **et** en base de prod : **34 campagnes, 0 ACTIVE** (19 archivées, 15 en pause), `amount_spent=0`, 0 insight sur 90 j. Les insights n'existent que pendant qu'une publicité tourne. C'est exactement la condition que la séance précédente a rendue ⏸️ au lieu d'une fausse alerte — la suppression se déclenchera donc en prod (34 > 0 connues, 0 active), et un locataire dont aucune campagne n'est connue reste alerté. |

**Ce qui reste sur Meta ne dépend ni de moi ni de toi** : le compte publicitaire de
Benken (`act_65390907`) n'est toujours pas partagé — `(#200) Ad account owner has NOT
granted ads_management or ads_read permission`. Geste de Benken, pas correction de code.

⚠️ **Non déployé.** Le code de ces deux séances est sur `origin/main` mais pas en prod.
Déploiement : `cd /opt/streamlytics && git pull --ff-only origin main && docker compose up -d --build dashboard`.

**▶️ Séance du 2026-08-22 (reprise après crash machine) — la suppression d'alerte
écrite la veille était devenue un feu vert.**

Le travail interrompu par le redémarrage était complet côté décision et **muet côté
lecteur** : `check_freshness` répond à une question avec un seul booléen, et poser
`stale=False` pour une source légitimement silencieuse la fait rendre comme saine
partout. Un rouge qui part chaque nuit finit par être lu comme du bruit ; un vert
n'est jamais questionné — la deuxième panne est la pire des deux.

| # | livré | mesuré |
|---|---|---|
| 1 | **Le silence attendu de Meta Ads ne déclenche plus d'alerte** | Aucune campagne ACTIVE (19 archivées + 15 en pause, `amount_spent=0`, zéro insight en 90 j) ⇒ aucune ligne d'insight ne PEUT exister. Sans ça, `16 577 h stale` partait chaque nuit pour un pipeline correct. La sonde est volontairement conservatrice : sonde en échec, zéro campagne connue ou règle inconnue ⇒ **on garde l'alerte**. Supprimer sur une supposition retire le seul signal qu'une vraie panne produirait. |
| 2 | **Quatre surfaces lisaient `not stale` comme « tout va bien »** | Le tableau des sources (🟢 OK à côté d'une ligne du 2024-09-30) ; `platform_status`, donc la matrice d'onboarding, `readiness_red_flags` **et** `artist_preflight` ; le pied « ✅ Sources OK » de l'e-mail nocturne ; et `debug_alert_monitor` (`✅ OK (16577h)`) — la quatrième trouvée en **balayant la classe**, pas en regardant le bug, et la pire des quatre : c'est ce qu'on lance quand on soupçonne déjà quelque chose. La raison mesurée voyage désormais avec le drapeau et chaque surface a un troisième état ⏸️ qui l'imprime. |
| 3 | **Six gardes, chacun vu ROUGE par mutation** | Retirer la branche `QUIET`, la branche de la vue, la légende de la raison, le filtre du pied d'e-mail, la clé du saut XCom, la branche du script de debug — chacune fait tomber le test correspondant, puis vert après restauration. La vue est testée par **exécution réelle** (le tableau rendu est inspecté), pas par sous-chaîne. |
| 4 | **L'index du catalogue d'erreurs avait cessé de lister** | Trouvé en ajoutant une classe, pas en le cherchant : **63 entrées, 51 lignes d'index**, et les douze manquantes étaient les douze plus récentes — quatre écrites le jour même. Une omission qui ne contredit rien : l'index ne prétend jamais être complet, donc son incomplétude est silencieuse dans la seule direction qui compte (on réécrit la classe sous un autre nom). Lignes **régénérées depuis les entrées**, garde dans les deux sens, et `/capitalise` nomme désormais l'index dans ce qu'il écrit. |

Classes : `suppressed-alert-renders-as-health` (P2), `catalogue-index-omits-its-own-entries` (P3).
Constat annexe non traité (hors périmètre, à décider) : `freshness_monitor.run_freshness_alerts`
n'a **aucun appelant** dans tout le dépôt — l'alerte de fraîcheur réellement envoyée est
celle d'`alert_monitor`. Code mort ou câblage oublié : les deux se corrigent différemment,
et aucune des deux corrections n'appartenait à cette séance.

**▶️ Séance du 2026-08-21 (nuit) — R20 livré en prod, et trois lacunes de plus.**

| # | livré | mesuré |
|---|---|---|
| 4 | **Le canari a un lecteur** (`check_canary_health` dans `alert_monitor`) | Un canari que personne ne lit est de la décoration. Il rapporte, par plateforme déclarée, si des lignes atterrissent encore sous lui (seuil 36 h). L'**absence** de canari est elle-même un constat. Exécuté en prod : `Canary 14 (Canary prod): 0 problem(s)`. |
| 5 | **`central_apps_broken` n'envoyait aucun e-mail** | Il alimentait le corps ET le sujet, mais **pas `has_issues`** — donc une app partagée tombée, seule, ne produisait rien. Masqué par coïncidence (Meta cassé *et* périmé). Le garde balaie la classe : tout `xcom_pull` de `send_consolidated_alert` doit figurer dans la décision d'envoi. |
| 6 | **`make sync-check` voit les migrations non appliquées** | Impossible à demander avant le registre. Ferme `migration-ahead-of-its-code` par le côté qui manquait : du code déployé avant sa migration. Vérifie aussi que `tools/` reste monté — le compose de prod étant gitignoré, ce montage **ne voyage pas** avec `git pull`. Vu rouge sur une migration factice, vert après. |
| 7 | **Un token Meta mal collé se voit tout de suite** | `check_meta()` valide la forme avant le réseau. Vérifié contre le vrai token de prod : il nomme le caractère en trop. |
| 8 | **Le canari n'inondera pas la boîte mail** | Vérifié quelques heures après l'avoir créé : les deux contrôles d'onboarding l'auraient signalé chaque nuit (« 3 credentials manquants », « connecté sans données ») pour un état **normal**. `exclude_canaries=True` là seulement — le défaut reste `False`, sinon les collecteurs cesseraient de collecter POUR lui. Troisième fois que ce dépôt paie la taxe du loup. |

**▶️ Les trois optimisations proposées ont été livrées le 2026-08-21 (soir).**

| # | livré | mesuré |
|---|---|---|
| 1 | **Registre de migrations** (`schema_migrations` + `tools/migrate.sh`, migration 071) | 70 fichiers rejoués à chaque exécution → **0**. Un fichier édité après coup passe de invisible à détecté au `checksum`. ⚠️ Son installation a **cassé** `s4a_song_playlist_adds` (clé primaire + 2 colonnes) en rendant 024 rejouable seule ; réparé, gardé, et consigné comme classe `unguarded-drop-replayed-alone`. |
| 2 | **`make schema-check-local`** | La dérive que ni la CI ni une base jetable ne peuvent voir. Empreinte extraite dans `tools/dev/schema_fingerprint.sql` — elle était **dupliquée** dans le Makefile. Résultat après réparation : **local == canonique, 920 col / 92 tables**. |
| 3 | **Suite contre ≥2 locataires** | Mesuré : une base canonique fraîche contient **exactement 1** locataire, et c'est contre ça que la CI a toujours tourné. La CI sème désormais `ci-canary` ; le garde tombe en dessous de deux. |

**▶️ Séance du 2026-08-21 (soir) — le canari a trouvé trois défauts en une heure.**

Créé en local, il a fait exactement ce pour quoi il existe : révéler ce qu'un dépôt
mono-locataire ne peut pas voir. Dans l'ordre où ils sont tombés :

| classe | gravité | ce qui se passait |
|---|---|---|
| `env-resolved-against-cwd` | P2 | `make artist-preflight` annonçait « credential NOT configured » pour des credentials présents, simplement pas chargés dans ce shell. Et `app.py`, lancé de la façon documentée (`cd src/dashboard`), ne chargeait **rien** — `load_dotenv` renvoyait `False` sans un mot. |
| `identity-mirrored-but-written-once` | P1 | l'identité Spotify vit dans **deux** tables ; le formulaire écrivait les deux, `create_canary.py` une seule. Le canari affichait « Connecté — Daft Punk ✅ » partout et collectait zéro ligne. Le locataire dont le seul rôle est d'attraper un faux vert **était** le faux vert. |
| `api-partial-date-into-date-column` | P2 | Spotify renvoie `release_date` à précision variable (`2013`, `2013-05`, `2013-05-21`) ; la colonne est `DATE`. Un seul album à date approximative faisait perdre à l'artiste **tous** ses top tracks du run. Latent depuis des années : le catalogue de l'admin n'a que des dates complètes. |

Les trois ont un correctif, une signature vue rouge sur le défaut puis verte, et un test
vérifié par mutation. Deux gardes ont dû être réécrits : le premier testait une
**sous-chaîne** que la ligne d'`import` satisfaisait à elle seule — vert alors que l'appel
avait disparu. Réécrit sur l'AST, il tombe.

Un piège d'outillage consigné au passage : vérifier une signature **à la main** dans ce
shell est trompeur — `grep` y est une fonction (le wrapper RTK) qui renvoie 0 dès que la
sortie est redirigée. Passer par `audit_runner.py` ou `command grep`.

**▶️ Où on en est (MAJ 2026-08-21, nuit) — la file d'ingénierie est vide.**

Prod à jour (`prod == canonique`, code déployé == `origin/main`, registre de migrations
**71/71**), 940 tests verts hors base (159 gated DB), `ruff` propre, audit
déterministe propre, canari de production surveillé. L'index `## 📋 Tâches ouvertes` est
à **0**, et les trois items de `## 🙋 En attente de toi` demandent chacun un geste que
seul un humain peut poser — détail juste en dessous.

**Ce qui t'attend — deux choses, et aucune n'est du code.**

L'index actif est à **0**. Les deux items ci-dessous ne se débloquent que par un geste
que tu es seul à pouvoir faire — un fichier, une invitation. Chacun a été **réduit** au
plus petit geste possible.

> **R13 est clos le 2026-08-22, et il ne demandait plus rien.** Le token Meta stocké
> était déjà **valide** — `debug_token` le confirme `SYSTEM_USER`, `expires_at=0`,
> 43 scopes, sur la bonne application. Ce qui restait cassé était `.env.local`, qui
> **gagne** sur `.env` et portait encore l'ID de compte publicitaire et le token mal
> collé. Détail et classe : `config-corrected-in-the-file-that-loses`.

1. ~~**R17 — déposer les PDF/EPUB d'ergonomie**~~ — **fait le 2026-08-21, l'ingestion
   tourne.** Dix ouvrages déposés, 1 indexé, 9 en cours. La lecture « le corpus renvoie
   du bruit, il n'a rien » était juste sur le symptôme et fausse sur la cause : neuf
   livres étaient déjà sur le disque, jamais ingérés, et rien ne distinguait « domaine
   vide » de « ingestion pas lancée ». Un contrôle de couverture donne désormais la
   différence. La décision que R17 bloquait reste **mesurée**
   (`make chart-budget` : 22 vues, 83 graphiques, médiane 3, `trigger_algo` à 15) ; le
   corpus servira à trancher le **seuil** une fois les 10 livres indexés.
2. **R1 — ouvrir la bêta privée** sur `streamlytics.fr`. Son prérequis dur est tombé :
   le canari de production existe et `artist_preflight` y est vert de bout en bout,
   contamination comprise. Le filet qui manquait aux deux sessions bêta précédentes est
   en place. R2 (landing + pixel + CAPI) démarre avec la première campagne, pas avant —
   ADR-008.

**Historique des grandes étapes (toutes ✅) :**
1. **✅ Cloudflare — ACTIF, PROXIFIE & DURCI (complet)** (détail `[[project_security_cloudflare]]`). Fait : zone active, NS Cloudflare, **SSL Full(strict)**, zone settings (min TLS 1.2 / Always HTTPS / Brotli / TLS 1.3), **rate-limit `/auth/token`** (10/10s), **firewall origine verrouillé** (ufw → IP CF only, vérifié), **Bot Fight Mode** ON, **cert Origin CF 15 ans** posé sur Caddy (plus de risque renouvellement, vérifié 2 edges). **RESTE (non bloquant)** : 🔑 **révoquer le token** `streamlytics-hardening` ; (optionnel) ré-activer DNSSEC via CF. ⚠️ vérifs prod **toujours via `curl --resolve host:443:<edge-CF-IP>`** (cache DNS local peut pointer l'IP origine firewallée → faux « down »).
2. **✅ Red-team — COMPLET** (réseau + app + dashboard). Couvert & clean : MITM/TLS (CVE suite), brute-force, SQLi, deps (0 CVE), **isolation tenant/IDOR (prouvé live)**, priv-esc, JWT, CORS, secrets, XSS (escaping tient), **replay webhook Stripe** (signature + handlers idempotents + tolérance 5 min), upload path-traversal (filename = détection seulement), app-DoS (cap 50 Mo + bornes `le=1000` + Cloudflare). **Trouvé+fixé+déployé** : `/kpis` & `/youtube/videos` schema-drift 500 (suite 18/19b) ; **CSV/Excel formula injection sur export (CWE-1236, suite 20)** → `defang_formulas()` sur les 3 chemins d'export + test. Mineur restant : XSRF/cookies Streamlit = défaut framework (P4). Compte test `redteam_qa` **supprimé (clôturé suite 20)**. Classes cataloguées : `api-router-schema-drift`, `csv-formula-injection` (`error-classes.md`).
3. **✅ E1 OUVERT** — 1er beta externe **Benken** (artist_id=12) onboardé 2026-06-15. A révélé une cascade per-tenant (tous les tests credentials KO, tous les CSV sauf Apple KO) → **diagnostiquée + corrigée + déployée** (voir session ci-dessous). 2e tenant **Cuzebo** (id=11) créé aussi.
4. **Actions restantes de l'époque, désormais reprises ci-dessus** : ~~**R13 régénérer le token Meta**~~ (clos 2026-08-22 : le token était valide ; c'est `.env.local` qui masquait la correction) ; **prep pré-session Benken** (partage compte pub Meta 65390907 + bon channel YouTube + Spotify artist ID) ; **R14 onboarding UX restant** (plan Track 1) ; refaire une session live avec Benken (tout doit marcher du 1er coup pour SoundCloud ✅/Apple ✅/YouTube/Spotify).

*Session 2026-08-21 (conformité baseline + capitalisation) : **la config baseline n'est PAS entièrement déployée — 76,2/100** (`audit_fleet.py`), et une partie de ce qui l'est était écrite **pour un autre projet**. Trouvé et corrigé : `rules/python.md` — une règle **contraignante, chargée à chaque session** — imposait un factory Redis, un « ingestion hot path » nommant 5 modules inexistants, et surtout des placeholders SQL `?` (SQLite/QuestDB) là où tout le dépôt utilise `%s` psycopg2 ; `/review-architecture` lisait deux gabarits **non remplis** et cherchait QuestDB + des révisions Alembic (que l'ADR-002 rejette) ; `code-critic` — pourtant nommé dans une règle impérative, donc réellement invoqué — se présentait comme critique du projet « MSDR Predictive Maintenance » ; `security-reviewer` auditait OPC UA et `INFLUX_TOKEN` dans un SaaS musical, doublon de `security-specialist` qui, lui, est correct → retiré, ses 5 appelants repointés. **Capitalisation** : dette de schéma des classes d'erreur 29 → **25**, les 4 classes soldées étant celles du sujet du jour (`central-app-missing`, `multitenant-mono-test-blindspot`, `prod-compose-drift`, `env-not-wired-to-service`) ; aucune classe neuve incomplète (cliquet). 812 tests verts.*

*Session 2026-08-20 quater (actions long terme de l'audit) : **6 items de l'audit livrés**. (1) `make schema-check` ne comparait que les colonnes — étendu aux **contraintes et index uniques, par définition** ; premier passage : 3 dérives prod inconnues → migrations `066` (deux `UNIQUE (campaign_name, platform, placement)` **aveugles au locataire**, deux artistes homonymes ne pouvaient pas coexister) et `067` (3 FK Meta manquantes, 0 orphelin vérifié) — **appliquées en prod**, drift restant = la seule divergence YouTube attendue. (2) Migration `068` : `DEFAULT` retiré et `NOT NULL` posé sur les colonnes de locataire — l'oubli devient fatal ; 805 tests verts contre une base la portant ; **attend le déploiement**. Deux enseignements : `tracks.saas_artist_id` reste volontairement nullable, et `artist_id` **n'est pas toujours le locataire** (VARCHAR Spotify sur 3 tables) → classe `column-name-is-not-its-meaning`, on raisonne sur le type. (3) Unicité d'identité refusée à l'enregistrement sur les 4 plateformes. (4) Le déclenchement de collecte **rend son résultat** et traduit l'échec en geste. (5) Parcours d'inscription testé. (6) Gate DB factorisé (`tests/db_gate.py`). **805 tests**, ruff clean, audit clean.*

*Session 2026-08-20 ter (exécution en production + audit de refactor) : **diagnostic prod confirmé sur données réelles** — `YOUTUBE_CHANNEL_ID` du scheduler = la chaîne de l'admin, GRiNCH détenait ses 67 vidéos, Cuzebo 4556 lignes de stats, et l'admin n'avait plus **aucune** ligne `youtube_videos` (volée par l'upsert). SoundCloud de GRiNCH : ID valide, **0 titre public** côté API — son symptôme exact, désormais diagnostiqué par le produit. **Fait en prod** : sauvegarde, migration 064, identités admin déclarées comme locataire puis retirées de `.env` **et** de `docker-compose.yml` (les défauts en dur y résistaient), 5304 lignes contaminées supprimées, collecte réelle revérifiée. **Deux pannes prod découvertes au passage, sans rapport avec les tests artiste** : les 4 watchers CSV échouaient **toutes les 15 min depuis le 13/08** (`PermissionError` sur le volume `data/`), et **aucune alerte n'était envoyée** car `SMTP_*` n'était câblé qu'au service `dashboard` — 672 échecs muets. Les deux corrigés et vérifiés. **Erreur commise et corrigée** : la migration 065 appliquée avant son code a cassé la collecte YouTube (revert immédiat) → classe `migration-ahead-of-its-code`. **Audit de refactor** : `.claude/dev-docs/refactor-audit-2026-08.md` (le RAG ne couvre ni le refactor ni le multi-tenant ; un passage de Reis & Housley p.387 s'applique). 776 tests verts.*

*Session 2026-08-20 bis (cause racine des deux échecs de test artiste) : **une seule règle implicite expliquait les deux symptômes** — « identité illisible ⇒ prends celle de l'admin », « locataire inconnu ⇒ écris sous `artist_id=1` ». Six mécanismes trouvés et corrigés : (1) **`track_popularity_history` écrivait l'historique de TOUS les locataires sous l'admin** depuis la migration multi-tenant (payload sans clé `artist_id` + `DEFAULT 1`), tous les jours, sans erreur ; (2) l'identité SoundCloud/YouTube/Meta retombait sur les variables d'env, qui portent celle de l'admin (`docker-compose` la codait même en dur par défaut) ; (3) un champ vidé (`""`) valait absence, donc identité admin — le geste le plus probable en session ; (4) le bouton « Lancer TOUTES les collectes », que l'e-mail d'inscription recommande, n'envoyait aucun `artist_id` : collecte de flotte + CSV du répertoire partagé écrits sous l'admin ; (5) les upserts réattribuaient la propriété d'une ligne (`youtube_videos UNIQUE(video_id)` + `artist_id` en `update_columns`) — reproduit en vrai ; (6) `load_platform_credentials`/`get_active_artists` renvoyaient vide sur **panne DB** comme sur « pas connecté ». Rien n'alertait parce qu'`artist_readiness` lit la DB seule : le voyant affichait ⚪ « À connecter » pendant que le tuyau coulait. **Livré** : garde E2E deux-locataires (`tests/test_e2e_two_tenants.py`, prouvée **7 rouges avant / 9 verts après** sur un vrai Postgres), migration `064`, `tools/tenant_contamination_check.py` (a détecté de vraies lignes contaminées), `make artist-preflight` en 5 étapes, `check_central_apps --require`, runbook `runbook-artist-test-session.md`, 4 classes d'erreur P1. 758 tests verts avec DB.*

*Session 2026-08-20 (retour test bêta Grinch du 12/08) : **4 chantiers, 46 tests ajoutés, 678 verts, ruff clean, `audit_runner --deterministic` clean**. (1) **Tests de connexion honnêtes** — les 4 plateformes validaient l'app partagée de l'admin, jamais l'identifiant du locataire : ✅ vert puis 0 ligne collectée. SoundCloud passait au vert sur 0 titre (le symptôme exact de Grinch), Meta ne regardait jamais `account_id`, YouTube ni Spotify l'identifiant artiste. Classe `connection-test-proves-app-not-tenant`. (2) **macOS** — `Ctrl+U`/`F12` codés en dur sur 7 sites : tokens `{{VIEW_SOURCE}}`… résolus par OS (détection User-Agent + bascule), les deux graphies dans le PDF. Classe `guide-single-os-shortcut`. (3) **Ergonomie d'installation** — l'étape 2 devient une sélection à cocher : ce que chaque plateforme débloque, ce qu'elle coûte en minutes, recommandation **Spotify + Instagram**, sélection reportée sur la page Credentials. Découvert au passage : **Instagram était inconnectable** (`ig_user_id` lu par le DAG et la readiness, absent du formulaire) → champ ajouté, classe `identity-read-but-never-collectable`. (4) **Moins de graphiques** — règle « un graphique primaire par décision », le reste replié dans `secondary_analyses()` : instagram 4→2 à l'ouverture, soundcloud 2→1, spotify 4→3, budget verrouillé par `tests/test_chart_budget.py`. Chaque classe a une signature vue rouge avant / verte après.*

*Session 2026-06-19→20 (Benken onboarding + durcissement) : **8 PR mergées+déployées** (prod `96554a2`, 587 tests verts). (1) **Modèle central-app complété** : admin = 1 app/plateforme, artiste = 1 identifiant ; câblage env dashboard manquant corrigé (cause #1 de l'échec Benken) ; SoundCloud env ajouté. (2) **Isolation per-tenant** sur 10 sites DAG (un tenant cassé ne casse plus toute la flotte) + garde-fou `test_dag_fleet_isolation`. (3) **load_dotenv** gardé (soundcloud+instagram). (4) **Détection CSV** élargie. (5) **UX credentials** : ordre facile→difficile, statuts honnêtes (App prête vs Connecté), guides Spotify/YT réécrits. (6) **Durcissement** : `test_env_contract` (code-lit ⊆ service-déclare), préflights boot dashboard/api, `test_compose_parity`, alerting per-tenant (freshness + escalation consécutive), ADR-006, `tools/{prod_introspect,check_central_apps}`, 6 classes d'erreur. (7) **Boucle fermée readiness per-artiste** : `artist_readiness()` + vue 🚦 Santé onboarding + flag alert_monitor — Benken meta=🔴 (compte non partagé) remonté auto. (8) **Validation au connect** Spotify (résout l'artiste dans le form). ⚠️ Le plan de cette session (« Tracks 1/2/3 ») **n'a jamais été commité** et n'existe nulle part : `git log --all -- .claude/plans/` est vide et le chemin n'est pas gitignoré. C'était un fichier local, perdu. R14 a donc pointé pendant deux mois un périmètre introuvable — trouvé le 2026-08-21 en élargissant `check_config_refs.py` à la roadmap. Le périmètre a été **reconstruit depuis le code** (voir R14) ; les libellés A6/A7/E/F/G du plan d'origine ne sont pas récupérables.*

*Session 2026-06-13 (suites 12→14) : Stripe live prouvé ; 4 bugs corrigés (nav login-bounce #46, date période #47, fuite fraîcheur Spotify #48, « Aucun DAG trouvé »/AirflowMonitor env-first #53) ; audit isolation tenant (#49 : `require_artist_scope` + P3) ; `/ml/predictions` réparé & P4 fermée (#50) ; cadence freshness #51 ; **Postgres-en-CI #52 (P3 fermée, render-smoke 39 vues en CI)** ; pentest A-D (#54 `/openapi.json` fermé) ; DAGs activés ; **API REST fonctionnelle en prod #56** ; analyse d'impact config/prod = classe « config.yaml absent » entièrement contenue sur le chemin runtime.*

---

## 🔖 Séances rotées depuis le fichier actif (2026-09-03)

Blocs datés du 2026-08-26 au 2026-08-30, déplacés hors de `checklist.md` : ce sont des
comptes rendus de séances closes, pas de l'état ouvert. Le fichier actif était remonté à
42 Ko, dont ~80 % d'historique — la dérive exacte que
`test_the_resume_header_is_checked.py::test_the_active_file_stays_readable_in_one_sitting`
surveille. Déplacement, jamais suppression.

### Séance du 2026-08-30 (test artiste) — le défaut qu'aucune mesure ne voyait

L'artiste en test : *« des fois je clique sur un bouton et il ne se passe rien »*.
Cause : **`server.websocketPingInterval` valait `None`** — aucun keepalive — et le
dashboard est servi à travers **Cloudflare**, qui ferme les websockets inactifs. Lire
une page deux minutes suffisait à perdre la connexion, en silence.

C'est sa précision « **rien ne bouge du tout**, pas même un spinner » qui a tranché :
un clic sans réaction n'a jamais atteint le serveur. J'avais commencé à balayer les
`st.button` — ça n'aurait rien donné, les 3 sites suspects sont sur des pages d'admin.

`websocketPingInterval = 20`, et la valeur mise sous test parce que sa voisine
(`showErrorDetails`) avait déjà repris son défaut en silence.

---

### Séance du 2026-08-30 (soir) — la passe d'optimisation n'en était pas une

Les 42 vues mesurées **dans le conteneur de prod**, SQL séparé de Python. Résultat :
**SQL = 2 ms la requête** (755 ms / 372 requêtes), **p50 de rendu = 61 ms**, 33 vues
sur 42 sous 150 ms. Il n'y avait rien à optimiser au sens large — trois des quatre
trouvailles étaient des **bugs de correction** déguisés en lenteur.

| Trouvaille | État |
|---|---|
| La vue `admin` **plantait en prod** : `timestamptz` relu à cheval sur un changement d'heure (`+01`/`+02`). 4 autres sites latents, dont un `aware - naïf` qui aurait cassé la page Credentials au premier token Meta | corrigé, `utils/tz.py` + garde AST |
| **12 DAGs sur 16 affichés « sans run »** sur l'accueil : une fenêtre globale de 200 runs pour répondre à une question par DAG, alors que 4 watchers font 98 % des 392 runs/jour | corrigé, `_runs_per_dag` parallèle — 16/16, et `airflow_kpi` de 1541 à 499 ms |
| `hypeddit` ouvrait 2 connexions : un helper fermait la connexion partagée, `_ensure_connection` reconnectait en silence. Le garde comptait le **texte source**, pas le rendu | corrigé, comptage au rendu, plafonds vides sur 42 vues |
| `webserver.workers = 4` sur une UI à un lecteur | passé à 2 puis **remis à 4** : la vérification post-déploiement a montré que 116 Mio coûtaient **317 ms sur chaque rendu de l'accueil** (le dashboard interroge les 16 DAGs *à travers* ce webserver) |

**Deux choses que la mesure a interdites**, et c'est le plus utile :
`core.parallelism` reste à 32 (pic réel **19** sur 108 215 tâches — j'allais proposer
8), et le balayage `view_session` aurait été **une fuite locataire** : 17 des 25 vues
utilisent `tenant_scope()`, qui rend `None` pour l'admin là où `view_session()` rend
`artist_id = 1`.

**Le correctif Airflow avait un prix, trouvé en re-mesurant après déploiement** :
`home` 378 → 670 ms et `credentials` 288 → 515 ms, les deux appelant le moniteur à
chaque rerun. Cache 60 s → **home 144 ms, credentials 81 ms** — plus rapide qu'avant
la séance, et toujours 16/16 DAGs.

**Et le refactor final a produit sa propre leçon.** `admin.show()` découpée (401 → 64
lignes) : le premier jet retirait le `with tab_gdpr:` et rendait le contenu **hors** de
l'onglet. **Trois gardes existants sont passés dessus**, dont l'empreinte de rendu que
j'avais écrite pour prouver l'équivalence — `at.main` aplatit l'arbre. Une vérification
qui rend la même réponse pour le code juste et le code cassé n'est pas une
vérification.

4 classes de plus au catalogue, chacune avec sa signature **vue rouge sur le vrai
code d'avant**.

---

### Séance du 2026-08-30 — la mesure prise au mauvais endroit

Point de départ : relancer les vérifications périmées, puis chercher des optimisations.
Rien n'était ouvert côté machine ; ce qui suit a été **trouvé**, pas planifié.

**Les quatre déclencheurs d'ADR-007 ont été lus contre la production : aucun n'est
tiré.** 1 seul locataire a jamais déposé du S4A, 13 794 lignes (le seuil est 140 k),
6–77 ms d'import par vue en conteneur. La porte tient — et c'est maintenant mesuré,
ce que l'ADR nommait lui-même comme son risque.

**Ne pas mesurer la performance depuis WSL.** Le déclencheur « imports paresseux »
paraissait tiré depuis `/mnt/c` (900–1250 ms par vue). En conteneur : 6–77 ms.
`trigger_algo` : 9801 ms en WSL, 625 ms en prod. Facteur 5 à 160.

| Trouvaille | État |
|---|---|
| `process_guide` reconstruisait **deux PDF WeasyPrint par rerun** — 721 ms des 1034 ms de la vue, sur la première page d'un artiste neuf | **déployé et mesuré en prod : 1034 ms → 8 ms**, `utils/guide_assets.py` + garde AST |
| **Aucun des 16 DAGs** ne déclarait `dagrun_timeout`. `alert_monitor` (p50 3,4 s) porte un run de **13,1 h en état success** — le canal d'alerte, muet, indiscernable d'une nuit calme | corrigé, `src/utils/dag_timeouts.py` + garde |
| L'image API portait 454 MB de CUDA + xgboost + plotly qu'elle n'importe jamais : **0,98 → 0,26 GB** ; dashboard 0,99 → 0,67 GB | corrigé, `requirements-api.txt` + garde |
| `uv.lock` résolvait **apache-airflow 3.2.2** quand la prod tourne en **2.11.2** : chaque test de forme DAG validait un Airflow que l'ordonnanceur ne charge pas, et rendait vert | corrigé, cœur épinglé dans `pyproject.toml` + garde à 3 assertions |

4 classes au catalogue, chacune avec une signature **vue rouge sur le vrai code
d'avant** et verte après. Suite complète : **3483 passed, 25 skipped, 0 failed** —
84 tests de plus qu'avant, l'épinglage d'Airflow ayant rendu à la suite les tests de
DAGs et de collecteurs qui sautaient en silence. ⚠️ **Rien de tout ça n'est déployé** : `deploy.sh` ne vise
que api+dashboard, et les DAGs passent par un `git pull` côté scheduler (bind-mount).

---

### Séance du 2026-08-28 — quatre mails en deux nuits, deux causes

✅ **DÉPLOYÉ ET VÉRIFIÉ EN PRODUCTION** (commit `4b940fe`, migration 078 appliquée).
Point de départ : quatre alertes apportées telles quelles. Le tri d'abord — le lien
`localhost:8080` ne prouve rien (l'UI Airflow de prod est liée à 127.0.0.1), c'est
**l'absence de préfixe `[LOCAL]`** qui tranche : les quatre venaient de la production.
Deux mails par nuit, deux causes distinctes.

| | |
|---|---|
| **Le plantage** | `PostgresHandler()` sans argument dans `_mirrored_identities`, arrivé avec `350ed8d`. Seul site du dépôt. Plus grave que le mail : `xcom_pull` rendant None, la section « credentials manquants » a **disparu des deux alertes consolidées** sans que rien ne le dise, et le dé-bruitage par le miroir n'a jamais tourné. Garde AST lisant la **vraie** signature par `inspect` — un `grep` aurait trébuché sur les commentaires du correctif lui-même |
| **La redite** | Le récapitulatif repartait chaque nuit à l'identique. Mesuré sur les XCom de prod des 25 et 26 : **identiques à deux champs près**, `age_h` (1945.0 → 1969.0) et `when`. Le registre montre **cinq** nuits de suite avec le même sujet, pas deux. `src/utils/alert_repetition.py` empreinte les constats en ignorant la MESURE et en gardant l'IDENTITÉ ; migration 078 |

**Ce que la suppression ne peut pas faire**, et c'est le point : un constat nouveau,
disparu ou de raison changée part la nuit même ; au-delà de `ALERT_REPEAT_SILENCE_DAYS`
(7) le même constat repart, parce qu'un silence permanent est indiscernable d'un moniteur
mort. La nuit supprimée s'écrit `delivery_expected = FALSE`, comme une nuit calme, pour
que `infra_health_cron.sh` ne la lise pas comme une panne du canal d'alerte.

**Le fil : la liste des champs volatils est une liste NOIRE, pas blanche.** Un champ de
constat ajouté demain entre par défaut dans l'empreinte — au pire un mail de trop. Une
liste blanche aurait fait qu'un champ oublié rende deux constats différents
indiscernables, donc supprime un mail dû. Entre trop de courrier et un constat perdu, le
biais est choisi une fois et il va toujours du même côté.

**Et la fixture est le vrai XCom des deux nuits**, pas une forme inventée par le test :
une règle écrite de mémoire aurait laissé passer `age_h` et n'aurait rien supprimé. Un
test garde la RÉALITÉ mesurée, jamais la constante qu'on vient d'écrire.

---

### Archive — séance du 2026-08-26

✅ **DÉPLOYÉ ET VÉRIFIÉ EN PRODUCTION** le 2026-08-26 (commit `350ed8d`).
`prod == origin/main`, aucune reconstruction d'image nécessaire — le scheduler
bind-monte `src/` et `airflow/dags/`. Trois preuves prises **dans le conteneur de
prod** : `diagnosis_text` importable, le rendu produit `<b>`/`<br>`, et
`instance_env() == production` (donc la porte anti-mail hors-prod ne peut pas rendre
la production muette). Puis la preuve sur les **données réelles**, appels API compris :
les diagnostics de Benken (Meta) et GRiNCH (SoundCloud) portent enfin leur moitié
actionnable, dont l'instruction Business Manager qui débloque `act_65390907`.

### Ce que la séance a livré

Sept défauts, sept classes d'erreur, chacune avec un garde **vu rouge par mutation**.
Point de départ : une alerte nocturne de production, puis deux mails d'une instance
LOCALE — provoqués par cette séance même, en redémarrant le Postgres local pour la suite.

| | |
|---|---|
| Diagnostic amputé | `platform_probes` gardait `splitlines()[0]` : les **2 lignes rouges sur 2** perdaient le geste qui répare, dont l'instruction Business Manager qui débloque `act_65390907` |
| Action impossible | « relancer le DAG » sur des sources alimentées par CSV — **2 stale sur 2** |
| Doublons | « Inscrits sans rien connecter » et « Credentials manquants » posent le MÊME prédicat : 11 lignes sur 12 dites deux fois |
| Faux positif | l'admin réclamé chaque nuit pour une identité Spotify **présente sur son miroir** — et c'était la seule ligne que le dé-bruitage laissait |
| Mails de dev | hors production, le silence est désormais le défaut, sur les **deux** chemins d'envoi |
| Montage manquant | `./tools` absent du compose du dépôt ⇒ deux faux rouges en ligne de sujet |
| Import muet | un CSV en `;` n'importait rien et le refus ne nommait rien ; **9 `except:` nus** balayés dans `src/` |

### Deuxième passe — les gardes rouges de la CI (2026-08-26, soir)

`audit_runner --deterministic` signalait **6 classes en HIT**, toutes bloquantes en CI.
Deux causes, aucune dans le code applicatif :

- **Un diff non commité supprimait 4 tests** de `test_claude_config_floor.py`, dont
  **trois sont le `guard:` ou la `signature:`** de classes cataloguées. Le catalogue
  affichait toujours `guarded`. Restaurés (l'amélioration de commentaire du diff est
  conservée), et le catalogue est désormais **parsé par la suite** : un nœud pytest
  nommé qui ne résout plus fait échouer le build. Ce garde a trouvé **13 références
  mortes de plus** — 11 vers la forme À PLAT des skills, migrée le 2026-07-28.
- **La suite tournait avec le mauvais interpréteur.** `/usr/bin/python3` n'a ni
  `apache-airflow`, ni `googleapiclient`, ni `spotipy` : 28 rouges qui disaient
  « environnement », pas « code ». `tests/dep_gate.py` (jumeau de `db_gate`) les
  transforme en skips **criés**, avec l'appariement qui rend ça sûr : `CI` présent ⇒
  aucune porte ne peut sauter. En posant les portes, `test_e2e_two_tenants` s'est
  révélé porter **deux `pytestmark`**, le second écrasant le premier sans bruit.

**Suite : 2 échecs → 0.** De 32 rouges ce matin à zéro, sans toucher au code applicatif.

### Le fil, et il vise les gardes eux-mêmes

**Quatre fois dans la journée, un garde que je venais d'écrire est passé sur sa propre
documentation** — la dernière étant le garde des références mortes, qui trébuchait sur
l'exemple `tests/x.py::TestFoo` écrit dans sa PROPRE fiche — le commentaire français qui expliquait le correctif contenait le nom
recherché. Chaque fois, la réponse a été l'AST. Et deux gardes étaient **vacants** :
l'un ne matchait rien (`status_matrix` n'a pas de f-string), l'autre couvrait deux fois
la même branche. Corollaire : après avoir écrit un garde, le muter n'est pas une
formalité — c'est la seule chose qui prouve qu'il garde quelque chose.

Second fil : **R50/R51/R52 étaient en grande partie déjà faites.** Leurs notes
décrivaient un état d'avant le 2026-08-23. Vérifier chaque point dans le code avant de
cocher a évité de refaire trois briques — et a montré que la roadmap se périme comme
n'importe quel commentaire.


---

### Archive de la séance précédente

#### REPRISE` ci-dessous.

> **L'index de code est VIDE au 2026-08-26.** R49b, R50, R51 et R52 sont descendues
> dans `archive.md`. R50/R51/R52 étaient en grande partie déjà faites : leurs notes
> décrivaient un état antérieur au 2026-08-23, et chaque point a été vérifié dans le
> code avant d'être coché — jamais sur la foi du texte de la roadmap.
>
> Ce qui restait réellement et a été livré ce jour : le séparateur CSV mesuré et le
> refus qui nomme sa raison (R52), le bouton de téléchargement du guide (R50),
> `secondary_analyses()` sur la cinquième vue dense (R51).
>
> Ne restent que des **gestes humains**, ci-dessous. Aucun ne se code.

| id | tâche | prio | statut / déclencheur |
|----|-------|------|----------------------|
| — | *(aucune tâche machine ouverte)* | — | — |


---


---
