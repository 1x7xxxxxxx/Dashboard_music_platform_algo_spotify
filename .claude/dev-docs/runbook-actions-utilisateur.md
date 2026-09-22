# Runbook — les 4 actions qui n'appartiennent qu'à toi

Écrit le 2026-08-21. Ce sont les seuls items encore ouverts de la ROADMAP : aucun ne
peut être fait depuis une session Claude Code, chacun demande un accès, un fichier ou
une décision qui est à toi. Ils sont classés par ce qu'ils débloquent.

Après chacun, la vérification est donnée — ne pas la sauter : c'est elle qui distingue
« fait » de « cru fait », et cette distinction a coûté deux sessions de test artiste.

---

## 1. ~~R13 — Régénérer le token Meta System User~~ · ✅ CLOS le 2026-08-22 — **il n'a jamais fallu régénérer**

### La réponse à « faut-il vraiment le régénérer ? » : oui, et voici pourquoi

Mesuré le 2026-08-21 directement contre l'API Graph, depuis le conteneur de production.
Deux questions ont été séparées, parce qu'un premier diagnostic les avait confondues.

| test | ce que Meta répond |
|---|---|
| le token **tel qu'il est stocké** | `Malformed access token` (code 190) |
| le même **sans son 1er caractère** | *« The session has been invalidated because the user changed their password or Facebook has changed the session for security reasons »* |
| l'**application** (`META_APP_ID` + `META_APP_SECRET`) | `Error validating application. Cannot get application info` |

La deuxième ligne est celle qui tranche. Le token stocké commence par **`EEAA…`** alors
qu'un token Meta commence par `EAA` : il porte **un `E` parasite en tête**, une faute de
copier-coller. Retire ce caractère et Meta cesse de dire « malformé » — il **reconnaît**
un vrai token et t'explique qu'il ne marche plus parce que **la session a été
invalidée** (changement de mot de passe, ou action de sécurité Facebook).

Donc : ce n'est pas une expiration, et **aucune correction de `.env` ne le ressuscitera**.
Il faut en émettre un nouveau. Mais note le `E` en trop : c'est ainsi que le précédent a
été collé, et c'est ainsi que le prochain le sera si rien ne change.

⚠️ **Ne pas s'arrêter au token.** La troisième ligne dit que l'application elle-même ne
s'authentifie pas. Régénérer un token dans une app cassée fait perdre le voyage :
vérifie `META_APP_ID` et `META_APP_SECRET` **pendant la même visite**.

### Étapes

1. **business.facebook.com** → *Paramètres d'entreprise* → *Utilisateurs* → **Utilisateurs
   système** → sélectionne l'utilisateur système de streaMLytics.
2. **Générer un nouveau token**. Cocher au minimum : `ads_read`, `read_insights`,
   `business_management`, `instagram_basic`, `pages_read_engagement`.
3. **Copier le token en entier.** Il commence par `EAA`. S'il commence par autre chose,
   la copie a débordé d'un caractère — recommence.

   > **Tu ne peux plus te tromper sans le savoir.** Depuis le 2026-08-21,
   > `check_meta()` valide la **forme** avant tout appel réseau et refuse un token qui
   > ne commence pas par `EAA`, en nommant la cause exacte (« 1 caractère en trop »).
   > Vérifié contre le token actuellement stocké : il le détecte. Après avoir collé le
   > nouveau, lance `python3 tools/artist_preflight.py` — un mauvais collage se voit en
   > une seconde, au lieu d'attendre l'e-mail du lendemain matin.
4. Au même endroit, *Paramètres d'entreprise* → **Applications** : relève l'**ID** et le
   **secret** de l'app, et compare-les à `META_APP_ID` / `META_APP_SECRET`.
5. Sur le serveur :
   ```bash
   ssh root@167.233.92.1
   cd /opt/streamlytics
   nano .env          # META_ACCESS_TOKEN=EAA…   (aucun espace, aucun guillemet)
   docker compose up -d --force-recreate airflow-scheduler airflow-webserver dashboard api
   ```

### Vérification (ne pas sauter)

```bash
ssh root@167.233.92.1 'docker exec airflow_scheduler python3 -c "
import os,json,urllib.request,urllib.parse
t=os.environ[\"META_ACCESS_TOKEN\"]
print(\"prefixe\", t[:3], \"(doit etre EAA)\")
u=\"https://graph.facebook.com/v21.0/me/adaccounts?\"+urllib.parse.urlencode({\"access_token\":t})
print(json.load(urllib.request.urlopen(u))[\"data\"][:3])
"'
```

Puis, le lendemain matin, l'e-mail d'`alert_monitor` ne doit plus porter
`🚨 APP PARTAGÉE HS : Meta`, et **Meta Ads doit sortir de la liste des sources
périmées** — c'est le seul signe qui prouve que la collecte a repris (voir la note sur
la fraîcheur plus bas).

> **Pourquoi la fraîcheur et pas l'authentification ?** `check_meta()` passe
> délibérément au vert sur « REST inconclusive » : c'est le comportement normal d'un
> token System User, qu'on ne peut pas valider par `/me`. Pour Meta, c'est donc la
> **fraîcheur des données** qui alerte. Elle a été corrigée le 2026-08-21 : elle lisait
> la date d'écriture, que le DAG faisait avancer chaque nuit en réécrivant des lignes de
> 2024. Elle lit maintenant `day_date`, et rapporte **16 577 h** de retard.

---

## 2. ~~R20 — Créer le canari~~ · ✅ FAIT le 2026-08-21, **local ET production**

**Prod** : `artist_id=14`, slug `canary-prod`. `artist_preflight --platforms youtube`
**vert de bout en bout**, contamination comprise. Collecte prouvée sur la vraie prod :
**10 titres** et **200 vidéos** sous le locataire 14, les deux DAG en `success`.

Le blocage réel a été levé au passage : `tools/` n'était monté dans aucun conteneur
alors que psycopg2 n'existe QUE dans les conteneurs. Montage
`- ./tools:/opt/airflow/tools:ro` ajouté aux trois services airflow, **et à la main sur
le serveur** — le compose de prod est gitignoré, il n'arrive donc pas par `git pull`
(sauvegarde : `/opt/streamlytics/docker-compose.yml.pre-tools-mount`).

Pour le relancer plus tard :
```bash
ssh root@167.233.92.1
docker exec airflow_scheduler python3 /opt/airflow/tools/artist_preflight.py --platforms youtube
```

⚠️ Le canari est collecté chaque nuit par les DAG de flotte. C'est ce qui le rend
détecteur, et ça consomme un peu de quota d'API.

---

## 3. ~~R18 — `.env` ligne 67~~ · ✅ FAIT le 2026-08-21

La ligne était `nom entreprise=BAUDRY Timothé` — une étiquette écrite sans `#`, que
Docker lisait comme une clé. Commentée. `check_env.py` affiche désormais **10/10** et
`make up` démarre.

Ce que sa correction a révélé vaut plus que la correction : lancer la suite contre la
**vraie** base locale, au lieu d'un Postgres jetable, a fait tomber 8 tests — dont un
défaut de DAG réel (`collect_spotify_top_tracks` ignorait `dag_run.conf`, donc un clic
per-tenant dépensait le quota Spotify de toute la flotte). Détail dans `archive.md`.

**Leçon à garder — et désormais gardée mécaniquement.** Mesuré le 2026-08-21 : une base
canonique fraîche contient **exactement un** locataire, et c'est contre ça que la CI a
toujours tourné. Avec un seul, « collecter pour ce locataire » et « collecter pour toute
la flotte » renvoient les mêmes lignes — tout défaut d'isolation se lit comme correct.
La CI sème maintenant un second locataire, et
`tests/test_suite_runs_against_two_tenants.py` échoue en dessous de deux.

---

## 4. ~~R17 — Ingérer un corpus ergonomie / front-end~~ · ✅ FAIT le 2026-08-21 — 11 ouvrages indexés

Vérifié le 2026-08-21 : le dossier ne contient qu'un `README.md`, **zéro PDF ou EPUB**.

### Étapes

1. Déposer les PDF/EPUB dans `/mnt/c/Users/timot/knowledge/books/ux-frontend/`.
2. ```bash
   cd /home/timothe/knowledge-rag && uv run python ingest.py
   ```

### Vérification

`mcp__knowledge-rag__list_books` doit faire apparaître le domaine `ux-frontend` avec un
nombre de passages non nul.

**Ce que ça débloque** : les arbitrages d'ergonomie — dont le budget de graphiques par
vue, aujourd'hui fixé à l'intuition — deviennent sourçables.

---

## 6. ~~R38 — Le nom d'expéditeur des e-mails~~ · ✅ CORRIGÉ EN CODE le 2026-08-23

> **Rien à faire dans Brevo. Ce n'en venait pas.** La procédure ci-dessous partait d'un
> diagnostic faux — « aucune ligne de Python ne peut le corriger ». Deux mesures l'ont
> démenti :
>
> 1. **`config/config.yaml` portait littéralement le nom observé**
>    (`smtp.from_name: 'Music Cross Platform Dashboard & Trigger Spotify'`). C'est le
>    repli que le code lit **avant** son défaut `streaMLytics` — un repli intermédiaire
>    renseigné n'atteint jamais le défaut.
> 2. **`email_alerts.py` n'utilisait aucun nom** : il posait `msg['From'] = smtp_user`,
>    l'identifiant de connexion au relais, et Brevo y substituait son expéditeur par
>    défaut.
>
> Corrigé : `email_identity.from_header()` est la seule composition de l'en-tête, les
> quatre sites d'envoi y passent, et un garde AST interdit d'en composer un ailleurs.
> En production, `SMTP_FROM=noreply@streamlytics.fr` et l'absence de `SMTP_FROM_NAME`
> donnent désormais `streaMLytics <noreply@streamlytics.fr>` sans aucun réglage.

<details><summary>Ancienne procédure Brevo, conservée pour mémoire — elle n'était pas la bonne piste</summary>


**Le geste** : dans Brevo → *Expéditeurs, domaines & IPs* → l'expéditeur
`noreply@streamlytics.fr`, remplacer le **nom affiché** par `streaMLytics`.

**Pourquoi c'est là et pas dans le code.** Le code met déjà `streaMLytics` par défaut
(`src/utils/verification_email.py`, `from_name`), et `SMTP_FROM_NAME` est **absent des
deux conteneurs** de production — vérifié le 2026-08-23. Le nom que reçoit le
destinataire est donc celui **du compte Brevo**, qui écrase le nôtre. Aucune ligne de
Python ne peut le corriger.

**La vérification** : s'inscrire avec une adresse jetable et regarder l'expéditeur du
mail de confirmation. Il doit dire `streaMLytics <noreply@streamlytics.fr>`.

**Variante si tu préfères le forcer depuis chez nous** : poser `SMTP_FROM_NAME=streaMLytics`
dans `/opt/streamlytics/.env` puis
`docker compose up -d --force-recreate dashboard airflow-scheduler`. Selon la
configuration Brevo, le nom du compte peut malgré tout gagner — d'où le geste ci-dessus
en premier.

---

## 8. ~~R54 — Le GIF animé à côté des e-mails~~ · ✅ FAIT le 2026-08-28 — avatar posé et **vérifié en réception**

**Le constat, mesuré le 2026-08-24 : il ne vient pas de l'application.** Le dépôt a été
inspecté sur les trois expéditeurs — `src/utils/email_alerts.py`,
`src/utils/verification_email.py`, `airflow/dags/onboarding_report.py` :

- **zéro** balise `<img>` dans le moindre corps de mail ;
- **zéro** `MIMEImage`, aucune pièce jointe image (les seules pièces jointes sont les
  guides PDF d'onboarding) ;
- **zéro** URL d'image (`.png`/`.jpg`/`.gif`/`.svg`) dans tout `src/`, `airflow/` et
  `tools/` ;
- le pied de page de désinscription (`_unsubscribe_footer`) est du texte et un lien.

**La réponse, donnée par le destinataire le 2026-08-28** : c'est **la photo de profil du
compte Google expéditeur**. Ni Brevo, ni une signature — la seule des deux hypothèses
que personne dans le dépôt ne pouvait trancher, parce qu'elle se lit dans une boîte de
réception et nulle part ailleurs.

**Et la demande telle qu'énoncée était impossible.** « Quelque chose qui bouge, dans la
ligne du mail » : la ligne de la boîte de réception est précisément la surface que Gmail
n'anime pas. Il y fige la frame 1 et ne joue l'animation que dans les vues de profil
dépliées (survol, fiche contact). La règle de conception s'inverse donc —

> la frame 1 doit être un avatar complet, **parce que la frame 1 EST la ligne du mail**.

Le mouvement est un bonus pour les surfaces qui l'affichent, jamais la fonction.

**BIMI est écarté sur un fait, pas sur son prix** : `SVG Tiny PS` **interdit
l'animation**, donc un logo BIMI ne peut structurellement pas bouger. Il demanderait en
plus de passer `_dmarc.streamlytics.fr` de `p=none` (état vérifié le 2026-08-28) à
`p=quarantine`, et un certificat VMC payant — pour un résultat immobile.

**Le geste, s'il faut le refaire** :

```bash
python3 tools/dev/make_avatar_gif.py     # → assets/brand/avatar_streamlytics.gif
```

256×256, 24 frames, 35 KB, dérivé de `src/dashboard/assets/logo_mark.svg`. Puis, sur le
compte Google expéditeur : badge de profil → icône appareil photo → **Modifier** →
**Importer une photo** → déposer le GIF, quelques minutes de propagation.

Deux contraintes que le script tient déjà, et qui sont la raison de son existence :
la **frame 0 reproduit exactement** les hauteurs de barres du SVG (une boucle qui
s'en écarterait ferait afficher à la ligne du mail une image que la marque n'a jamais
validée), et tout tient dans les **70 % centraux** parce que Gmail recadre en cercle —
une marque qui se lit en carré perd ses bords dès qu'elle sert d'avatar.

**La vérification** : la ligne de la boîte montre la marque fixe ; survoler l'avatar
déplie la fiche et les barres bougent. Fait le 2026-08-28.

---

## 7. ~~R46 — Décider du sort de `data_quality_check`~~ · ✅ TRANCHÉ le 2026-08-23

> **Fait, et la décision est mesurée : il RESTE EN PAUSE.** Lancé une fois à la main en
> production, le circuit breaker s'ouvre (S4A périmée de 77 j). Trois mesures ont tranché :
> personne n'a déposé de CSV S4A depuis le 2026-06-08, seul l'admin en a jamais déposé, et
> `freshness_monitor` signale déjà la péremption. Dépausé, le DAG s'abstiendrait chaque nuit
> en envoyant un second e-mail sans constat — ce qu'ADR-011 interdit.
> **Rien à faire de ton côté.** Le déclencheur qui rouvrirait la question : le jour où un
> artiste dépose un CSV S4A. Détail : `.claude/dev-docs/data-quality-check-verdict.md`.

<details><summary>Procédure conservée, pour le jour où le déclencheur se produit</summary>


Le DAG est **en pause depuis toujours** (`is_paused = t`, `last_start` vide : il n'a
jamais tourné une seule fois). R42 a rendu son code sûr — mais rallumer un DAG est une
décision de production, pas une conséquence d'un correctif.

### Ce qui a changé le 2026-08-23 (R42)

- `check_meta_ads_freshness` **retirée**, pas réparée : elle mesurait la fraîcheur sur la
  date d'ÉCRITURE et serait passée au vert sur la source la plus morte de la prod
  (`collected_at` : il y a 8 h ; `day_date` : 2024-09-30). `freshness_monitor` fait le
  même travail correctement et est déjà branché sur l'e-mail nocturne.
- `check_spotify_data_consistency` passe derrière un **circuit breaker de fraîcheur** :
  aucun verdict sur la forme des données tant que la source n'est pas prouvée fraîche.
- Elle a reçu le **5ᵉ filtre S4A** qui lui manquait (un artiste dont les seules lignes
  sont la ligne « Total » du CSV passait pour alimenté).
- Elle ne **lève plus** : une tâche qui part en `FAILED` sur un constat métier devient sa
  propre alerte quotidienne via `check_dag_failures`.

### Étapes

1. Le lancer **une fois à la main**, sans le dépauser, et lire ce qu'il dit :
   ```bash
   ssh root@167.233.92.1 'docker exec airflow_scheduler \
     airflow dags test data_quality_check 2026-08-23'
   ```
2. Lire la sortie de `check_spotify_consistency`. Trois cas :
   - **abstention** (« circuit ouvert ») → la source S4A est périmée ; c'est un constat
     sur la collecte, pas sur ce DAG. Ne pas dépauser, traiter la collecte.
   - **0 constat** → le dépauser est sans risque.
   - **des constats** → les lire un par un avant de dépauser. ADR-011 s'applique :
     chacun doit nommer un symptôme visible par l'artiste ET une action possible, sinon
     il se journalise et ne se maile pas.
3. Dépauser seulement après le cas 2 ou 3 tranché :
   ```bash
   ssh root@167.233.92.1 'docker exec airflow_scheduler \
     airflow dags unpause data_quality_check'
   ```

### Vérification

```bash
ssh root@167.233.92.1 'docker exec airflow_scheduler \
  airflow dags list-runs -d data_quality_check --state failed'
```
Doit rester **vide** après la première nuit. Une seule nuit en `failed` et
`check_dag_failures` en fera une alerte quotidienne — exactement le bruit qu'ADR-011
interdit.

⚠️ `airflow dags test` **exécute réellement** `send_summary_notification` : le lancer
envoie un vrai e-mail de résumé. Mesuré le 2026-08-23.

</details>

---

</details>

---

## 5. ~~R1 — Ouvrir la bêta privée~~ · ✅ CÔTÉ PRODUIT le 2026-09-10 — **il n'y a plus rien à construire**

> Rotée dans `archive.md` ce jour-là. Le filet a été revérifié EN PRODUCTION,
> ligne par ligne, plutôt que repris de la fiche du 2026-08-22 : canari Spotify /
> YouTube / SoundCloud verts les deux dernières nuits, Meta et Instagram sondés par
> locataire, inscription à `200`, SMTP Brevo armé, et le lien de vérification testé
> jusqu'au bout (`APP_BASE_URL` pointe `streamlytics.fr` quand l'app est servie sur
> `app.` — les DEUX domaines servent l'application, le lien aboutit ; c'était la
> forme exacte du défaut qui a coûté deux séances de test artiste).
>
> Aucun mécanisme d'invitation n'existe et il n'en faut pas : l'artiste s'inscrit
> lui-même. **Les étapes ci-dessous restent vivantes et utiles** — ce n'est pas la
> procédure qui est close, c'est le travail de dépôt qu'elle attendait.

> 📋 **La procédure pas à pas est `.claude/dev-docs/runbook-artist-test-session.md`** —
> écrite après deux sessions de test artiste ratées pour la même heure perdue. Elle
> était orpheline jusqu'au 2026-08-28 : aucun fichier hors de `dev-docs/` ne la nommait,
> donc la seule tâche encore ouverte n'avait, en pratique, pas de runbook trouvable.

Les prérequis sont prouvés en production : funnel d'inscription complet, e-mails Brevo
livrés, paiement Stripe validé de bout en bout, isolation locataire testée.

### Ce que le filet couvre RÉELLEMENT — mesuré et étendu le 2026-08-22

Le canari de prod (`artist_id=14`) prouve **trois plateformes sur cinq**, et l'outil le
dit lui-même dans sa dernière ligne :

```
✅ Pre-flight green FOR soundcloud, spotify, youtube ONLY
```

| plateforme | identité du canari | état |
|---|---|---|
| Spotify | `4tZwfgrHOc3mvqYlEYSvVi` (Daft Punk) | 🟢 identité, connexion, données, contamination propre |
| YouTube | `UC_x5XG1OV2P6uZZ5FSM9Ttw` (Google Developers) | 🟢 idem |
| SoundCloud | `112904040` (NASA) — **ajouté le 2026-08-22**, 1498 lignes | 🟢 idem |
| Meta Ads | — | ⚫ **incanarisable**, voir ci-dessous |
| Instagram | — | ⚫ **incanarisable** |

**Pourquoi Meta et Instagram ne peuvent pas l'être** : lire un compte publicitaire exige
qu'il soit *partagé avec l'app* dans Business Manager ; lire un compte Instagram Business
exige une Page liée avec permissions accordées. Il n'existe aucun équivalent public,
contrairement à un profil SoundCloud ou une chaîne YouTube. Et prendre ceux de l'admin —
ils sont dans `.env` — ferait passer le canari au vert **à cause** de la fuite qu'il
existe pour détecter : `create_canary.py` refuse cette identité en dur, et **ADR-010**
explique pourquoi il ne faut pas contourner ce refus.

**Comment ils sont couverts à la place** : par artiste invité, après sa connexion.

```bash
make artist-preflight ARTIST=<son id>
```

Ce n'est pas un doublon de confort pour ces deux plateformes — c'est **la seule preuve**.
Le sauter, c'est sauter le contrôle. Et c'est un signal plus fort qu'un canari : il
éprouve le compte réel qui a cassé chez Benken (Meta) et GRiNCH (Instagram), pas un
substitut.

### Étapes

0. ~~Déployer la séance du 2026-08-22.~~ ✅ **FAIT** — `prod == canonique`, 921/921
   colonnes, 72 migrations, code == `origin/main`, `deploy/Caddyfile` == ce que Caddy
   sert.
1. ~~Compléter le filet du canari.~~ ✅ **FAIT dans la limite du possible** — SoundCloud
   ajouté, Meta/Instagram traités par ADR-010. Rejouer à tout moment :
   ```bash
   docker run --rm --network container:streamlytics_api \
     -v /opt/streamlytics/tools:/app/tools -w /app --env-file .env \
     streamlytics-dashboard python3 tools/artist_preflight.py \
     --artist 14 --platforms spotify,youtube,soundcloud
   ```
   (`tools/` n'est monté dans aucun conteneur par défaut — d'où le `-v` ; et
   `python:3.12-slim` ne suffit pas, il manque streamlit/requests/pandas.)
2. **Inviter les proches sur `https://streamlytics.fr`.** C'est le seul geste restant.
3. Après chaque inscription, **sans exception** :
   ```bash
   make artist-preflight ARTIST=<son id>
   make tenant-check
   ```
   Pour Meta et Instagram, c'est le seul contrôle qui existe (ADR-010).

**R2** (landing + pixel + CAPI) démarre avec la **première campagne**, pas avant — voir
`docs/adr/ADR-008`. Retiens seulement ceci : l'attribution est la seule partie qui a une
échéance, parce que `_fbp`/`_fbc` et les UTM ne se récupèrent pas rétroactivement.

## 9. ~~R55 — Choisir la métrique « 30 premiers jours vs actuel »~~ · ✅ TRANCHÉ le 2026-08-26

Écrit le 2026-08-26, en fermant R51. La brique demandait une section du PDF comparant
les 30 premiers jours d'un titre à son état actuel « sur le taux de trigger », et
laissait la métrique **à préciser**. Ce n'est pas un oubli qu'on peut combler en lisant
le code : « taux de trigger » désigne trois grandeurs différentes, déjà toutes
calculables, et elles ne racontent pas la même histoire.

### Les trois candidates

| | Ce qu'elle dit | Ce qu'elle cache |
|---|---|---|
| **A. Part des titres ayant franchi ≥1 porte** | « 4 titres sur 10 sont entrés dans un algorithme » — la plus lisible pour un artiste | Un titre entré dans Discover Weekly compte comme un titre entré dans Radio ; l'intensité disparaît |
| **B. Nombre moyen de portes par titre** | L'intensité de la poussée algorithmique | Une moyenne sur peu de titres bouge énormément — c'est le défaut « 66,7 % sur 3 titres » déjà corrigé dans ce PDF le 2026-08-24 |
| **C. Délai médian avant la première porte** | La vitesse de réaction de l'algorithme, la plus actionnable pour décider **quand** pousser | Muette sur les titres qui n'ont jamais déclenché ; une médiane sur des données censurées ment |

### Le geste

Réponds par **A**, **B** ou **C** (ou décris la tienne). C'est tout — la construction
suit, y compris le garde qui empêchera d'afficher un panier vide comme un 0 %, comme
pour les portes algorithmiques.

### Vérification

```bash
python3 -m pytest tests/test_the_pdf_says_what_the_screen_says.py -q
```

Et l'existence de la section dans le PDF rendu : `python3 -m src.dashboard.utils.pdf_exporter --artist <id>`
puis ouvrir le fichier — le rendu, pas la config.

## 10. ~~R57 — Créer le bucket de sauvegarde hors-site~~ · ✅ FAIT le 2026-09-04, **sans bucket**

<!-- Le titre ne dit pas « Cloudflare R2 » à dessein : l'index de roadmap
     repère un id par `^#{2,3} .*\b(R\d+)\b`, dont le `.*` est gourmand — sur
     « … Cloudflare R2 … » il retenait **R2** et concluait que R57 n'avait pas
     de procédure. Un identifiant de roadmap et un nom de produit partagent
     ici le même espace de noms. -->

**Le geste attendu n'a jamais eu lieu, et c'est ce qui a fait changer de cible.** Tous
les stockages objet à palier gratuit — R2, B2, Scaleway, Wasabi, Storj — exigent une
carte bancaire pour activer le service, y compris quand le palier reste à 0 €. Aucune
API n'amorce cette étape. La tâche est donc partie sur la seule cible configurable
**sans aucun geste humain** : un dépôt GitHub privé, l'archive chiffrée avant de partir.
Décision et alternatives : **ADR-015**.

### Ce qui tourne depuis le 2026-09-04

| Élément | Valeur |
|---|---|
| Cible | `git@github-backup:1x7xxxxxxx/streamlytics-db-backups.git` (privé) |
| Chiffrement | `gpg --symmetric --cipher-algo AES256`, phrase de 44 caractères |
| Accès | clé de déploiement **en écriture, limitée à ce seul dépôt** — pas de PAT sur la machine |
| Rétention distante | 30 jours ; commit orphelin + `push --force`, le dépôt ne s'accumule pas |
| Archives distantes | **22**, ~1,9 Mo chacune |
| Reçu | `data/offsite_receipt.json`, écrit seulement après relecture du distant |
| Drill hebdomadaire | restaure désormais l'archive **chiffrée** (lundi 06:00) |

### Les commandes qui le prouvent

```bash
# 1. la copie part et le distant porte bien ce qu'on a poussé
ssh root@167.233.92.1 'cd /opt/streamlytics && bash tools/db_backup.sh 2>&1 | tail -2'
# ✅ Hors-site OK — N archive(s) distante(s) chiffrée(s), rétention 30 j.

# 2. le contrôle nocturne le voit — il ne le pouvait PAS avant (voir plus bas)
ssh root@167.233.92.1 'docker exec airflow_scheduler airflow tasks test \
  alert_monitor check_offsite_backup 2026-09-04 2>&1 | grep Offsite'
# INFO - Offsite backup: 22 archive(s) on git@github-backup:…, proven 0 h ago

# 3. la seule preuve qui compte : restaurer SANS le serveur
gh api -H "Accept: application/vnd.github.raw" \
  "repos/1x7xxxxxxx/streamlytics-db-backups/contents/<archive>.sql.gz.gpg?ref=backups" > /tmp/a.gpg
gpg --batch --decrypt --passphrase-file ~/streamlytics-backup-passphrase.txt /tmp/a.gpg | gunzip | head
# fait le 2026-09-04 : 9,88 Mo de SQL, 93 tables
```

### Le geste qui reste — 10 secondes, un jour où tu y penses

**Mettre la phrase de passe dans ton gestionnaire de mots de passe.** Elle vit
aujourd'hui à deux endroits : `/opt/streamlytics/.backup_passphrase` sur le serveur, et
`~/streamlytics-backup-passphrase.txt` sur ce poste. Une clé qui ne survit pas aux deux
machines rend les 22 archives illisibles — une sauvegarde qu'on ne sait plus déchiffrer
n'est pas une sauvegarde.

### Deux défauts trouvés en câblant la vérification

1. **`check_offsite_backup` appelait `rclone` depuis le conteneur Airflow, qui n'a ni
   `rclone` ni `git`.** Il aurait répondu `unreadable` toutes les nuits, **y compris une
   fois R2 correctement configuré**. Un contrôle qui appelle un binaire absent de son
   image ne devient jamais vert. Seul site des 12 DAGs.
2. **La procédure ci-dessus posait la variable là où elle ne sert pas.** « `echo
   R2_REMOTE=… >> .env` puis recréer le scheduler » l'aurait posée pour le **conteneur**,
   jamais pour le **cron** qui pousse — `0 3 * * *` n'hérite d'aucun environnement.
   `db_backup.sh` lit désormais ses propres clés dans `.env`.

### Si tu poses une carte un jour

Rien à réécrire : créer le bucket, `rclone config`, puis
`echo 'R2_REMOTE=r2:streamlytics-backups/db' >> /opt/streamlytics/.env`. `R2_REMOTE` est
prioritaire dans le script ; le chemin git s'éteint de lui-même.

---

## 11. ~~R105 — Faire vérifier l'application Google pour lire les stats YouTube~~ · ⛔ ABANDONNÉE le 2026-09-13

> **Ne fais pas cette démarche.** ADR-025 a tranché le jour même où cette section a été
> écrite : le produit est Spotify + Meta + ML, et YouTube pèse **0,2 %** des écoutes
> observées (304 contre 165 065). Le code qui aurait utilisé ce consentement a été
> retiré, pas désactivé.
>
> La section est conservée telle quelle parce qu'elle porte ce qu'il faudrait préparer
> le jour où un artiste dont YouTube dépasse 20 % de ses écoutes le justifierait. Elle
> décrit une procédure VALIDE ; elle ne décrit plus une procédure À FAIRE.

<details>
<summary>La procédure, si la question se rouvre un jour</summary>


**Pourquoi c'est toi et pas moi** : Google demande un dossier au nom du propriétaire du
projet Cloud — politique de confidentialité, domaine vérifié, vidéo de démonstration.
Aucune ligne de Python ne le dépose.

**Pourquoi ça bloque vraiment** : sans vérification, l'écran de consentement reste en
mode *Testing*, et **les refresh tokens y expirent au bout de 7 jours**. Une collecte
nocturne meurt donc chaque semaine, et l'artiste doit re-consentir. Construire l'étape
d'onboarding avant d'avoir déposé le dossier livrerait un parcours qui casse tous les
sept jours.

⚠️ **Reconfirme d'abord le niveau des scopes dans la console.** Google n'en publie pas
de tableau lisible ; l'indicateur « Sensitive » s'affiche au moment où tu ajoutes le
scope à l'écran de consentement. Si l'un des deux ressort **Restricted**, arrête-toi et
dis-le : ça ferait entrer une évaluation de sécurité tierce PAYANTE, et l'arbitrage
change complètement.

### Ce qu'il faut préparer

| pièce | où | note |
|---|---|---|
| Politique de confidentialité en ligne | déjà servie par l'app | l'URL doit être celle de l'écran de consentement |
| Domaine vérifié | Google Search Console | même domaine que l'URL ci-dessus |
| Vidéo de démonstration | non répertoriée sur YouTube | doit montrer le flux de consentement **et** l'usage réel du scope dans l'app |
| Scopes demandés | `yt-analytics.readonly`, `youtube.readonly` | ne rien demander de plus : chaque scope en trop allonge l'examen |

### Les étapes

1. Console Google Cloud → APIs & Services → **OAuth consent screen**.
2. Type d'utilisateur : **External**. (Internal est réservé à un domaine Workspace ;
   nos artistes ont des comptes Gmail personnels, ils recevraient `access_denied`.)
3. Ajouter les deux scopes, **et noter le niveau affiché en face de chacun**.
4. Renseigner la politique de confidentialité et le domaine.
5. Passer le statut en **Production** → « Submit for verification ».
6. Joindre la vidéo.

### La commande qui prouve que c'est fait

```bash
# Un artiste qui n'est PAS toi consent sans voir « application non vérifiée »,
# et son refresh token survit au-delà de 7 jours :
make artist-preflight-prod PROD_SSH=root@167.233.92.1 ARTIST=<id>
```

Tant que ce n'est pas déposé, R105 reste développable **sur ton propre compte** : en tant
que propriétaire du projet GCP tu ne vois pas l'écran d'avertissement et ton jeton ne
meurt pas. Cela suffit à rapatrier TON historique, pas celui des autres.

### Ce qu'on garde même après

L'export manuel YouTube Studio → Analytics → **Mode avancé** → « Exporter la vue
actuelle » (CSV, 500 vidéos max) reste le seul chemin pour un artiste qui refuse le
consentement. Ne pas le retirer une fois R105 livrée.

</details>

## 12. ~~R117 — Sortir le dépôt de `/mnt/c` et passer VS Code en Remote-WSL~~ · ✅ FAIT le 2026-09-17 — les deux moitiés sont faites et vérifiées ; détail dans `.claude/dev-docs/roadmap/archive.md`

**Pourquoi c'est ici et pas fait en séance** : ce geste déplace le dépôt. Il tue le
répertoire de travail de la session qui l'exécute, et **la mémoire de Claude Code est
indexée par CHEMIN** (`~/.claude/projects/-mnt-c-Users-timot-Desktop-…`) : sans
renommage du dossier, l'historique et les mémoires du projet sont perdus. Une session ne
peut pas se déplacer elle-même — c'est la seule tâche de la roadmap dont l'exécutant est
aussi la victime.

**Ce que ça rapporte, mesuré le 2026-09-16 en ALTERNANCE et à périmètre égal** (6 572
tests collectés des deux côtés, arbre git propre des deux côtés) :

| | `/mnt/c` | ext4 (`~`) | rapport |
|---|---|---|---|
| collecte pytest | 27,1 s | **4,8 s** | **×5,6** |
| suite complète `-n auto` | 372 s | **109 s** | ×3,4 |
| 2 000 petits fichiers écrits | 4,12 s | **0,06 s** | ×69 |

La cause est structurelle, pas un réglage : `/mnt/*` est monté par `drvfs`, qui parle
**9P** — un protocole réseau. Chaque `open()` et chaque `stat()` devient un message
sérialisé à travers la frontière VM/hôte, et pytest parcourant 375 fichiers de test plus
un `.venv` de 2,2 Go est du travail entièrement métadonnées.

### Les quatre étapes

1. **Copier le dépôt sur ext4** — `git clone` depuis GitHub vers `~/streamlytics`, puis
   recopier à la main ce que `git clone` ne suit pas. **Huit éléments**, et cette liste
   en a compté cinq jusqu'au 2026-09-17 :
   `.mcp.json`, `.env`, `.env.local`, `config/config.yaml`, **`docker-compose.yml`**,
   **`graphify-out/`**, `data/`, et `.venv` (ou `make sync` pour le refabriquer).
   ⚠️ **Les deux en gras manquaient à cette liste, et les deux ont manqué à l'arrivée** —
   constaté le 2026-09-17 au matin, après le déplacement. Sans `docker-compose.yml` :
   ni `make up` ni `make migrate`, le port 5433 fermé, et toute suite lancée sans base.
   Sans `graphify-out/` : `.mcp.json` continuait de servir le graphe de la copie MORTE,
   sans le dire — il répondait, simplement il décrivait un autre arbre.
   La liste se re-dérive, elle ne se recopie pas :
   `git status --porcelain --ignored | grep '^!!'` dans la copie source.
   💡 `graphify-out/` se régénère plutôt qu'il ne se copie (`make graph`), et c'est
   MIEUX : `graphify update` ajoute sans retirer, donc un graphe neuf part à zéro
   fichier fantôme — l'ancien en traînait 24 (177 nœuds).

   ⚠️⚠️ **Et la liste ci-dessus était ENCORE incomplète** — constaté le 2026-09-17 en
   fin de journée, en exécutant enfin la commande de re-dérivation. **24 entrées
   ignorées** vivaient dans la copie source et pas dans la nouvelle, dont onze qui ne
   sont pas du cache : `tests/fixtures/distrokid_bank_sample.csv`,
   `machine_learning/{01_data,mlruns,mlflow.db,data_analysis_ml_perso.ipynb}` (121 Mo),
   `backups/`, `.archive/`, `.claude/settings.local.json`, `.claude/curator/usage.json`,
   le PDF d'architecture et `tools/dev/architecture_dossier/`.

   **Le coût était invisible et mesurable** : `tests/test_distrokid_parser.py` porte un
   `skipif` sur l'absence de sa fixture — ses **21 tests skippaient en silence**, et la
   suite était verte sans eux. `mlruns/` est lu par `src/dashboard/views/ml_performance.py`.

   **La leçon est que ce paragraphe ne doit PAS être une liste.** Elle a été fausse
   deux fois en une journée, à cinq puis à huit entrées. Ce qui marche est la
   commande — `git status --porcelain --ignored | grep '^!!'` dans la copie source,
   le même dans la cible, et `comm -23` entre les deux. Les seules absences
   acceptables au bout sont les caches : `__pycache__/`, `.cache`, `.coverage`,
   `.hypothesis/`, `venv/`, `.audit-venv/`.
   ⚠️ Il a fallu **trois allers-retours** pour compléter la copie de mesure, dont quatre
   fichiers `assets/` à nom accentué. Vérifier par un `git status` des deux côtés.
1bis. ⚠️ **Reposer l'identité git** — trouvé le 2026-09-17, au premier commit qui a
   échoué : `git clone` ne suit PAS la configuration LOCALE du dépôt, et
   `user.name`/`user.email` y étaient locaux, pas globaux. Le clone refuse alors de
   commiter (« Author identity unknown »). À lire à la source, jamais à deviner :
   ```bash
   cd "$SRC" && git config --local --list | grep '^user\.'
   cd ~/streamlytics && git config --local user.email "…" && git config --local user.name "…"
   ```
   C'est le **neuvième** élément que `git clone` ne transporte pas, après les huit
   fichiers gitignorés — et le seul qui ne se voie pas par un `diff` d'arborescences.
   ⚠️ Ce paragraphe disait « sixième … après les cinq » : le compte suivait la liste
   de l'étape 1, qui était elle-même incomplète de deux entrées. Un compte dérivé d'une
   liste fausse a l'air d'une vérification alors qu'il n'en est pas une.

2. **Renommer le dossier de mémoire de Claude**, sans quoi l'historique du projet
   disparaît :
   `mv ~/.claude/projects/-mnt-c-Users-timot-Desktop-Dashboard-music-platform-algo-spotify ~/.claude/projects/-home-timothe-streamlytics`
3. **Recréer les conteneurs une fois** — `docker-compose down && docker-compose up -d`.
   `deploy.sh` et `migrate.sh` détectent le conteneur par NOM : eux suivent sans
   changement.
4. **Basculer l'éditeur** — `code .` depuis un shell WSL, jamais depuis Windows.

### La vérification

```bash
echo $VSCODE_IPC_HOOK_CLI          # doit rendre une valeur — aujourd'hui : VIDE
which code                         # doit pointer dans ~/.vscode-server, pas /mnt/d
time .venv/bin/python -m pytest tests/ --collect-only -q   # doit tomber sous 10 s
```

Tant que `which code` rend `/mnt/d/1_Logiciels/VS Code/bin/code`, VS Code tourne côté
Windows et ouvre le dossier par `/mnt/c` : exactement la combinaison lente. `~/.vscode-server`
existe déjà — Remote-WSL a servi par le passé — donc la bascule ne demande aucune
installation.

## 13. ~~R124 — Une session authentifiée en production, pour savoir si l'instrument enregistre~~ · ✅ FAIT le 2026-09-17 — l'instrument enregistre (28 séries, p50 = 40 ms) ; détail dans `.claude/dev-docs/roadmap/archive.md`

**Pourquoi c'est ici et pas fait en séance** : la couture de métriques ne s'exécute
qu'**après** la porte d'authentification — `require_login()` est à
`src/dashboard/app.py:742`, `end_chrome()` à 976 et `view_timer()` à 979. Une session non
authentifiée ne produit aucune métrique **par construction**. Je n'ai pas d'identifiants
de production, et je n'en veux pas : c'est un geste de propriétaire.

⚠️ **J'ai fait la sonde non authentifiée et j'en ai tiré une conclusion FAUSSE** —
« défaut de production confirmé » — avant de lire le code. La page de connexion s'est
rendue entièrement, l'instrument n'a pas bougé, et c'était le comportement attendu.

### Ce qui est établi, et ne demande pas ce geste

| vérification | résultat |
|---|---|
| cible Prometheus `dashboard` | `up`, scrape 3,8 ms, aucune erreur |
| séries `streamlytics_*` | 2, pour 4 familles déclarées |
| `streamlytics_rerun_duration_seconds_*` | **0 série** — maintenant, à −6 h, et en `query_range` sur 22:00–24:00 UTC |
| `max_over_time(streamlytics_reruns_in_flight[24h])` | **0** — aucun rendu authentifié instrumenté en 24 h |
| `daily_ops_metrics` du 2026-09-17 | `p50 = 50 ms`, `p95 = 220 ms`, `source = prometheus`, **`complete = TRUE`** |

### Le geste

1. Ouvre `https://app.streamlytics.fr/` et **connecte-toi**.
2. Navigue sur deux ou trois pages (l'accueil suffit).
3. Attends une minute, puis lance :

```bash
ssh root@167.233.92.1 "curl -sG --data-urlencode \
  'query=streamlytics_rerun_duration_seconds_count' \
  'http://127.0.0.1:9090/api/v1/query'"
```

### Ce que la passe A AUTHENTIFIÉE a donné le 2026-09-17, et pourquoi elle ne suffit pas

Les identifiants du bac à sable ont été régénérés (`--reset --verified --email …`, script
copié dans `/app/tools/` et non `/tmp`, voir plus bas) et la passe A a tourné **connectée**.

| onglets | 1 | 2 | 4 | 8 | 12 | 16 | 24 |
|---|---|---|---|---|---|---|---|
| p50 (ms) | 226 | 339 | 660 | 1 246 | 1 710 | 2 317 | **3 879** |
| rapport | ×1,00 | ×1,50 | ×2,91 | ×5,50 | ×7,55 | ×10,23 | **×17,13** |
| censure | 0 % | 0 % | 0 % | 10 % | 6 % | 4 % | **28 %** ⚠ |
| reruns perdus (serveur / client) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |

**Le croisement ne fonctionne toujours pas, et pour une raison neuve.** Sur ~400 clics, le
serveur n'a enregistré que **10,2 reruns**, avec un p50 de **27,8 ms** et un p95 de
**179,7 ms**. Les 3 879 ms du client ne s'expliquent pas par 180 ms de rendu serveur.

Test direct : **20 clics → 0 observation serveur** (scrape 15 s, attente 20 s, donc
suffisante). Alors que la couture FONCTIONNE par ailleurs — 28 combinaisons
`(page, phase)` sont observées : `onboarding`, `home`, `youtube`, `onboarding_health`…

**Deux causes émises et RÉFUTÉES le même jour :**
- les fragments — `src/dashboard/views/onboarding.py` n'utilise aucun `@st.fragment` ;
- un `st.stop()` avant la couture — il n'y en a aucun entre `require_login()` (742) et
  `end_chrome` (976).

**La cause restante, NON VÉRIFIÉE** (et écrite comme telle) : les onglets ouverts avec
`browser.new_context(storage_state=…)` ne seraient pas réellement authentifiés. Ils
cliqueraient alors « Pas encore de compte ? Créez-en un » — le seul bouton secondaire de
la page de connexion — donc une page **publique, non instrumentée**. Cohérent avec tout
ce qui est observé ; pas démontré.

**Le geste qui trancherait** : ouvrir un onglet avec le `storage_state` sauvé et vérifier
s'il affiche le tableau de bord ou le formulaire de connexion.

⚠️ **Deux défauts de l'outillage corrigés en chemin, sans quoi rien n'aurait tourné :**
1. Le script de bac à sable doit être copié dans **`/app/tools/`**, pas `/tmp` : il résout
   sa racine par `Path(__file__).resolve().parents[1]`, ce qui donne `/` depuis `/tmp` —
   et `src` n'y est pas. Le patron de `artist-preflight-prod` a le même défaut.
2. **Le mode authentifié du générateur était cassé** : il désignait les champs par
   POSITION (`locator("input").nth(0)`), et le sélecteur de langue 🇫🇷/🇬🇧 est fait de deux
   boutons radio rendus AVANT le formulaire. Playwright échouait sur « waiting for element
   to be visible, enabled and editable ». Corrigé en sélecteurs sémantiques
   (`get_by_role("textbox")`). C'est le mode qu'on n'exerce presque jamais, donc son défaut
   a vécu sans témoin — et c'est précisément pourquoi R114 n'avait jamais pu être rejouée.

### Une option a été étudiée et REJETÉE le 2026-09-17 — ne pas la rouvrir sans lire ceci

L'idée : **instrumenter la page de connexion** pour que le mode anonyme devienne
croisable côté serveur, ce qui dispenserait de ces identifiants. `code-critic` a rendu
**DO-NOT-BUILD**, sur trois motifs :

1. **C'est un contournement de cette procédure-ci**, qui existe et ne coûte rien. Le
   locataire bac à sable est déjà exclu de `tools/scale_check.sh` exactement pour cet
   usage.
2. **Le design avait un trou** : il se branchait sur `session_state['authenticated']` lu
   AVANT l'appel, alors que `require_login()` peut rendre `False` quand ce drapeau valait
   `True` — session expirée ou révoquée. Ce cas serait resté **non instrumenté**. On
   aurait rendu visible le login d'un NOUVEAU visiteur et laissé aveugle celui d'un
   utilisateur dont la session vient d'expirer, probablement le plus fréquent.
3. **Modifier une route d'authentification impose `Spawn security-specialist` AVANT
   d'écrire** (CLAUDE.md règle 13). `app.py` porte en commentaire l'historique d'une
   fuite réelle sur cette exacte surface non authentifiée (2026-08-23).

⚠️ Ce qui resterait vrai si on la rouvrait un jour : **la page la plus visitée du produit
est invisible à la surveillance**, et c'est un angle mort réel — mais indépendant de
R114, et à traiter comme tel (label structurel plutôt qu'un préfixe par convention, test
de garde et les deux documents en prose réécrits dans le même geste).

### Ce que chaque issue veut dire

| résultat | conclusion |
|---|---|
| des séries apparaissent | la couture enregistre. La question devient : **d'où venait `p50 = 50` le 2026-09-17 à 23:00 UTC**, alors que l'histogramme n'avait aucune série ? Et la re-mesure de R114 peut démarrer |
| rien n'apparaît | la couture n'instrumente **aucun** rendu en conteneur. C'est un P2 : ADR-026 mesure le vide, et ADR-027 s'appuierait sur une ligne fabriquée |

### Ce que ça débloque

La remise en service de la seconde réplique (R114) est conditionnée par `deploy/Caddyfile`
à « un chiffre qui ne dépende pas de la saturation du client ». Ce chiffre vient de cet
instrument. Tant qu'on ignore s'il enregistre, mesurer deux topologies reproduirait
l'ambiguïté de R114, plus cher.

## 14. ~~R114 — Les identifiants du bac à sable, pour croiser client et serveur~~ · ✅ FAIT le 2026-09-17 — les quatre passes ont tourné ; la réplique **n'est pas adoptée**, et le chiffre qui la rouvrirait est écrit

### Le verdict, le 2026-09-17 — quatre passes ALTERNÉES, authentifiées

| passe | amonts | p50 @1 | p50 @8 | sérialisation @8 | reruns servis par la réplique |
|---|---|---|---|---|---|
| A  | 1 | 277 ms | 1 451 ms | **×5,24** | — (pas de réplique) |
| B  | 2 | 288 ms | 804 ms | **×2,80** | 98 |
| A2 | 1 | 290 ms | 1 498 ms | **×5,16** | **0** — contrôle : la réplique n'a rien servi |
| B2 | 2 | 292 ms | 778 ms | **×2,67** | 112 |

**Le signal de décision du protocole n'a JAMAIS tiré, et c'est le résultat principal.**
Il demandait « B rend 0 rerun perdu là où A en perd ≥ 9 ». **A en perd 0.** Il n'y avait
rien à supprimer, donc la question posée par R114 reste sans réponse — pas parce que la
mesure a échoué, mais parce que le mode de défaillance ne s'est pas produit.

⚠️ **Et il ne peut pas être produit depuis ce client.** À 8 onglets le navigateur occupe
3 202 Mo pour 3 645 Mo disponibles ; 16 onglets dépassent la mémoire de la machine. Or
mesurer à travers un client saturé est exactement ce que le protocole interdit. Le palier
qui ferait perdre des reruns à un amont unique est **hors de portée de cet instrument**,
et c'est une limite de l'appareil, pas un résultat sur le service.

**Ce qui EST mesuré, et solidement** : la sérialisation est divisée par deux.
A ∈ [5,16 ; 5,24] et B ∈ [2,67 ; 2,80] — **deux intervalles disjoints**, avec une
dispersion intra-condition de 1,5 % et 4,7 %, très en-dessous du plancher de bruit de
±40 %. En absolu, p50 @8 passe de 1 475 ms à 791 ms, soit **×1,87**.

**Le contrôle interne qui rend ces chiffres lisibles** : p50 @1 vaut 277, 288, 290, 292 ms
sur les quatre passes. À un onglet, les deux configurations sont indistinguables — donc
ni le réseau ni le client ne dérivent entre les passes, et le gain porte bien sur la
CONCURRENCE, pas sur une accélération générale.

### La décision : la réplique n'est pas adoptée

`tools/scale_check.sh`, lancé le même jour, rend ses **deux** déclencheurs verts —
« sous le seuil — répliques toujours injustifiées », p50 serveur **64 ms** contre un
seuil de réouverture à 200 ms. Le critère que le dépôt s'était donné AVANT la mesure et
la mesure elle-même convergent : il n'y a aucune perte à supprimer aujourd'hui.

Payer un second conteneur en permanence pour diviser par deux une contention qui ne fait
perdre aucun rerun serait un coût sans contrepartie. La production a donc été **remise
telle qu'elle était avant l'expérience**, et c'est vérifié et non supposé : le Caddyfile
est **identique octet pour octet** à `/root/Caddyfile.avant-R114` (`diff` vide),
`dashboard2` n'existe plus, Prometheus n'a plus qu'une cible, l'application rend 200.

**Ce qui rouvre le dossier**, et il n'y a rien d'autre à surveiller : `scale_check.sh`
qui passe l'un de ses deux seuils. Le montage est prêt et prouvé — `deploy/docker-compose.replica.yml`,
la sonde 8511, la cible Prometheus, `lb_policy cookie streamlytics_lb` — donc le rouvrir
est une affaire de trois gestes, pas d'un chantier.

⚠️ **Un défaut P2 a été trouvé en montant la réplique, et il survit à cette décision** :
la réplique servait une image antérieure de **sept heures et un commit** à celle du
primaire (`extends` reprend `build:`, donc Compose fabrique un tag par service, et
`up -d` sert celui qui traîne). Classe `a-replica-that-builds-its-own-image`, corrigée
sur les deux vecteurs — `extends` et fusion YAML — et gardée par
`tests/test_a_replica_cannot_serve_a_different_artifact.py`. **Sans ce correctif, rouvrir
le dossier remettrait en service un binaire d'un autre commit.**

### L'option écartée, et pourquoi elle l'a été

Instrumenter le chemin public pour mesurer sans identifiants : `code-critic` a rendu
`DO-NOT-BUILD`, pour trois motifs qui tiennent toujours — c'était contourner la procédure
de bac à sable écrite le matin même ; le branchement lisait `session_state['authenticated']`
*avant* l'appel, donc manquait les reconnexions après expiration ; et la règle 13 impose
`Spawn security-specialist` avant de toucher une route d'authentification.

---

<details>
<summary>Historique — l'état de la tâche avant sa clôture</summary>


**Pourquoi c'est ici** : `tools/loadtest_concurrency.py` en mode anonyme mesure la **page
de connexion**. Elle est rendue **avant** `require_login()` (`src/dashboard/app.py:742`),
alors que la couture de métriques s'exécute **après** (`end_chrome` 976, `view_timer` 979).
Les deux instruments ne regardent donc pas le même chemin, et le croisement — la raison
d'être de R115 — est impossible sans se connecter.

### Ce que la passe A a établi SANS identifiants, le 2026-09-17

| onglets | 1 | 2 | 4 | 8 | 12 | 16 | 24 |
|---|---|---|---|---|---|---|---|
| p50 (ms) | 229 | 329 | 552 | 1 088 | 1 864 | 2 474 | 3 657 |
| p50 / p50(1) | ×1,00 | ×1,43 | ×2,40 | ×4,74 | ×8,13 | ×10,79 | **×15,94** |
| reruns perdus (serveur) | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| reruns perdus (client) | 0 | 0 | 0 | 0 | 0 | 0 | **0** |

**Deux lectures, et il faut les tenir ensemble :**

- **×15,94 à 24 onglets est une sérialisation quasi parfaite.** Un processus, un GIL :
  la contention est réelle et mesurée.
- **Zéro rerun perdu, partout.** Le seuil de décision du protocole — « B rend 0 là où A
  en perd ≥ 9 au palier 8 » — n'a **plus d'amplitude** : A marque déjà 0. La ligne de
  base historique (0/0/0/**9**/**33**/—/**98**) ne se reproduit pas.

⚠️ **Ne pas en conclure que le serveur va bien.** Pendant toute la passe, l'histogramme
serveur est resté `nan` et `reruns_in_flight` à 0 : **le serveur n'a rien vu du tout**,
parce que le chemin mesuré n'est pas instrumenté. Le zéro est une absence d'observation,
pas une absence de perte.

### Le geste

1. Récupère les identifiants du locataire **bac à sable** (`is_sandbox`, tenant 18) —
   `tools/scale_check.sh` l'exclut déjà de ses comptes, c'est fait pour ça.
2. Rejoue les quatre passes **alternées** A-B-A-B du protocole
   (`.claude/dev-docs/measurement-protocol-R114.md`), en heures creuses :

```bash
make loadtest-concurrency URL=https://app.streamlytics.fr/ \
  LEVELS=1,2,4,8,12,16,24 REPS=6 LOGIN=<bac-a-sable> PASSWORD=<...>
```

⚠️ **`LOGIN=` et non `USER=`** : `USER` est une variable d'environnement POSIX que `make`
importe, et la cible partait en mode authentifié toute seule avec `--user $USER`. Corrigé
le 2026-09-17 ; `tests/test_a_make_variable_does_not_collide_with_the_environment.py` le garde.

3. Entre A et B, les trois gestes de remise en service de la réplique sont écrits dans
   `deploy/Caddyfile` (démarrer `dashboard2`, repointer `reverse_proxy` en `lb_policy
   cookie`, remettre la cible Prometheus).

### Ce que chaque issue veut dire

| résultat | conclusion |
|---|---|
| B perd 0 rerun là où A en perd ≥ 9, **deux fois** | le levier est prouvé |
| B perd autant que A | **le goulot n'est pas le GIL** — on aurait acheté Redis et des workers pour rien. C'est la découverte visée |
| l'écart reste sous le seuil | on ne conclut pas, et on l'écrit. **C'est un résultat**, pas un échec |

</details>

---

## 15. ~~R125 — Saisir les écoutes réalisées à 28 jours, pour que le modèle apprenne~~ · ✅ FAIT le 2026-09-20 — 33 lignes en production, 11 titres ; détail dans `.claude/dev-docs/roadmap/archive.md`

**Ce que ça débloque** : le jeu d'entraînement vivant du scoring. Aujourd'hui il est vide
et rien ne le dit.

### Ce qui est mesuré, en production, le 2026-09-18

| table | lignes | ce que ça veut dire |
|---|---|---|
| `ml_song_predictions` | **617** | le modèle prédit toutes les nuits, et il écrit |
| `s4a_song_algo_outcomes` | **0** | personne n'a jamais saisi une écoute réalisée |
| `ml_prediction_outcomes` | **0** | donc aucune prédiction n'a jamais été étiquetée |
| `etl_run_log` pour `ml_outcome_labeling` | **aucune entrée** | le DAG hebdomadaire n'a rien à apparier |

Le DAG `ml_outcome_labeling` est **actif** (non suspendu) et tourne le lundi 06:00 UTC.
Il apparie chaque prédiction de plus de 28 jours avec les écoutes **réellement** obtenues
sur Discover Weekly / Release Radar / Radio, saisies à la main dans **Saisie S4A**. Sans
cette saisie, il n'a rien à faire et ne laisse aucune trace — **une table vide se lit
comme « pas encore de données », jamais comme « personne n'a fait le geste »**.

### Le geste

1. Ouvrir le dashboard → **Saisie S4A**.
2. Choisir un morceau **prédit il y a plus de 28 jours** (le scoring tourne depuis la
   brique 16 ; la liste des prédictions est visible dans *Road to Algo*).
3. Entrer, pour ce morceau, les écoutes obtenues **sur la fenêtre de 28 jours** dans les
   trois sources : **Discover Weekly**, **Release Radar**, **Radio**. Ces chiffres se
   lisent dans Spotify for Artists → *Playlists* → filtre 28 jours.
4. Enregistrer. Un seul morceau suffit pour prouver que la chaîne fonctionne ; le jeu
   d'entraînement se construit ensuite au rythme des saisies.

### La commande qui prouve que c'est fait

```bash
ssh root@167.233.92.1 "docker exec \$(docker ps --format '{{.Names}}' | grep -i postgres | head -1) \
  psql -U postgres -d spotify_etl -c \"SELECT
    (SELECT count(*) FROM s4a_song_algo_outcomes) AS saisies_humaines,
    (SELECT count(*) FROM ml_prediction_outcomes) AS etiquetees\""
```

`saisies_humaines > 0` après le geste. `etiquetees > 0` **le lundi suivant** seulement —
l'appariement est hebdomadaire, pas immédiat. Les deux chiffres valaient 0 le 2026-09-18.

⚠️ **Ce qui ne marchera pas** : saisir les écoutes d'un morceau prédit il y a moins de
28 jours. Le DAG l'ignore par construction, la saisie sera correcte et `etiquetees`
restera à 0 — et on conclura à tort que la chaîne est cassée.

---

## 16. ~~R140 — Dix-sept décisions de produit trouvées par le balayage des classes d'erreur~~ · ✅ FAIT le 2026-09-20 — les dix-sept tranchées et intégrées ; détail dans `.claude/dev-docs/roadmap/archive.md`

**Ce que ça débloque** : rien ne se répare tant qu'elles ne sont pas tranchées, et aucune
n'est une question technique. Chacune a sa mesure, rejouable ; aucune n'a été corrigée,
délibérément — les quatre changent soit ce qu'un artiste voit, soit un état partagé avec
la production.

### 16.1 — Un appariement de titres trop large, dans le PDF que l'artiste reçoit

`src/utils/track_matching.py:191` rend `qb == cb or qb in cb or cb in qb` : une inclusion
par **sous-chaîne**, en booléen dur. Le frère de la même famille
(`track_mapping_suggest.py:96`) a été réparé le 2026-09-06 et rend `0,9 × couverture` ;
celui-ci ne pèse jamais ce qui reste dehors.

Rejouable :

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from src.utils.track_matching import track_title_matches as m
from src.utils.track_mapping_suggest import title_similarity as s
for a,b in [('Mix','HOUSE MUSIC MIX #3 BACK TO OLD SCHOOL'),('Sun','Sunset Boulevard'),
            ('Solo','Solomon Dream'),('Nuit','La nuit de tous les dangers')]:
    print(m(a,b), round(s(a,b),4), a, '|', b)"
```

Sortie du 2026-09-18 : **les quatre rendent `True`**, avec des similarités de 0,11 à 0,24.

Les **6 sites d'appel sont tous dans le PDF** (`pdf_exporter/_collectors.py:292,412,435,
842,864,890`), tous sous `single_song` — donc le défaut se manifeste quand un artiste
demande le PDF d'**un seul morceau** au titre **court**.

⚠️ `tests/test_track_title_matches.py:36` croit couvrir le cas : son assertion utilise un
titre LONG, et aucun cas du fichier n'exerce un titre court.

**La décision** : resserrer fait DISPARAÎTRE des lignes de PDF que des artistes ont déjà
reçus. Trois options — (a) laisser, (b) exiger une couverture minimale comme le frère
réparé, (c) resserrer et prévenir les artistes concernés. Je n'ai pas tranché.

### 16.2 — Le jeton SoundCloud est partagé entre une instance de dev et la production

`src/collectors/soundcloud_api_collector.py:123` fait `grant_type=refresh_token`, et son
propre docstring dit que SoundCloud **fait tourner** le jeton à l'usage. Une instance de
développement qui collecte invalide donc celui de la production.

C'est la cause mesurée de l'incident qui a créé la classe
`a-dev-instance-sends-production-shaped-mail` : le 2026-08-24, un scheduler local a échoué
sur ce credential partagé que la prod venait de faire tourner 28 minutes plus tôt.

Étiqueter le mail a réparé le symptôme. `email_alerts._outbound_blocked()` barre les mails
hors production ; **rien n'équivaut côté credentials**.

```bash
grep -n "refresh_token\|_outbound_blocked\|is_production" src/collectors/soundcloud_api_collector.py
```

**La décision** : un second jeu de credentials SoundCloud pour le dev, ou un garde
`is_production()` qui refuse la rotation hors prod. Le premier coûte une app SoundCloud de
plus, le second empêche de tester la collecte en local. Touche les secrets — jamais sans
toi.

### 16.3 — Un bouton « ce locataire » qui déclenche la flotte entière

`src/dashboard/utils/collection_trigger.py:68` fait
`conf = {'artist_id': artist_id} if artist_id is not None else {}`.

⚠️ **Ce n'est pas une fuite de locataire, et je l'ai d'abord écrit comme si.**
`tenant_scope()` (`auth.py:778`) ne rend `None` que pour un **admin** — un non-admin reçoit
`st.stop()`. Et un DAG sans `artist_id` appelle `get_active_artists(include_artist_id=None)`,
donc collecte **tous les artistes actifs** ; le repli sur l'identité de l'environnement
exige `LEGACY_SINGLE_TENANT=1`, explicitement opt-in (`soundcloud_daily.py:123`).

Le docstring du bouton dit « Déclenche les collectes de **CE** locataire ».

**La décision** : quand un admin presse ce bouton, faut-il (a) collecter toute la flotte —
le comportement actuel, à documenter — ou (b) refuser et demander de choisir un artiste ?

### 16.4 — Un script de migration qui interpole des identifiants SQL sans allowlist

`migrations/migrate_saas_artist_id.py:54,57,66,73,82` interpole `table`, `name` et `cols` —
des **paramètres de fonction** — dans `ALTER TABLE` / `UPDATE` / `ADD CONSTRAINT`, sans
aucune allowlist sur le chemin. Les appelants (l. 100-112) passent des littéraux, donc rien
n'est exploitable aujourd'hui.

```bash
grep -nE "ALTER TABLE|ADD CONSTRAINT|UPDATE " migrations/migrate_saas_artist_id.py
```

La règle transverse #8 l'exigerait dans `src/` ; `migrations/` n'est parcouru par aucun
garde.

**La décision** : ce script est à usage unique et déjà passé. Le corriger, le geler avec un
en-tête qui dit qu'il a servi, ou étendre le garde à `migrations/` en acceptant qu'il
rougisse sur les scripts déjà joués.

### 16.5 — Un refresh_token SoundCloud imprimé en clair sur la sortie standard

`airflow/debug_dag/debug_soundcloud_oauth.py:117` fait `print(f"\n   {effective_rt}\n")`.

**Ce n'est pas une escalade** : c'est délibéré, le runbook OAuth frappe le jeton et
demande de le coller dans le dashboard, et l'opérateur le détient déjà. Le reste de ce
fichier a été rédigé le 2026-09-18 ; cette ligne est la seule volontairement laissée.

Ce qui la rend inconfortable : **les deux crons de ce dépôt capturent la sortie standard
d'un sous-processus dans un fichier de log ET dans un corps de mail**
(`tools/schema_drift_cron.sh`, `tools/infra_health_cron.sh`). Si ce script est un jour
enveloppé de la même façon, le jeton est persisté sur disque et posté.

```bash
grep -n "print(f\"\\n   {effective_rt}" airflow/debug_dag/debug_soundcloud_oauth.py
grep -n "2>&1\|tee\|\$(" tools/schema_drift_cron.sh tools/infra_health_cron.sh | head
```

**La décision** : garder tel quel, ajouter un avertissement d'une ligne disant que la
sortie ne doit pas être redirigée, ou passer l'impression derrière `--print-token`. Les
trois sont défendables ; aucune n'est à moi.

### 16.6 — Deux définitions du MRR sous le même libellé

`admin.py:509-521` et `billing.py:323-341` calculent le MRR en SQL : `WHERE status =
'active'`, `SUM(sp.price_monthly)`. `revenue_forecast.py:56-67` le calcule en pandas sur
`status ∈ {'active','trialing'}` **et** `price > 0`.

Dès qu'un abonnement est `trialing` — et `admin.py:524` parle explicitement d'« essai de
bienvenue » — « MRR total » vaut **deux nombres différents sur deux pages**, et
« Artistes payants » aussi. Aucune des trois ne filtre `HUMAN_TENANTS`, alors que le
compteur d'artistes juste au-dessus (`admin.py:501`) le fait.

```bash
grep -n "price_monthly\|trialing\|HUMAN_TENANTS" src/dashboard/views/admin.py \
  src/dashboard/views/billing.py src/dashboard/utils/revenue_forecast.py
```

**La décision** : un essai gratuit compte-t-il dans le MRR ? Les deux réponses sont
défendables (prévisionnel contre encaissé) ; ce qui ne l'est pas, c'est que deux pages
répondent différemment sous le même mot. Et faut-il exclure les locataires techniques du
revenu comme on les exclut du compte d'artistes ?

### 16.7 — Deux pages admin prescrivent deux requêtes pour « la dernière collecte »

`useful_links.py:335-350` rend en `st.code` des commandes `psql` que l'admin copie-colle ;
`admin.py:336-343` calcule la même chose lui-même. Les colonnes divergent sur **cinq
plateformes sur six** — et pour Meta, `useful_links` prescrit `MAX(collected_at)` là où
`admin` lit `MAX(day_date)`.

⚠️ **Ce n'est PAS une violation de règle, et je l'ai d'abord écrit comme si.** Le libellé
dit « Dernière **collecte** », ce à quoi `collected_at` répond correctement.
`freshness_monitor.py:18-19` mesure l'écart : sur `meta_insights_performance_day`,
`collected_at` valait le matin même et `day_date` **2024-09-30**. Les deux colonnes
répondent à deux questions — « quand a-t-on écrit » et « de quand date la donnée ».

**La décision** : laquelle des deux questions l'écran admin doit-il poser ? Une fois
tranchée, les deux pages disent la même chose, et `quality_gate.py:40-41` donne déjà la
règle pour la seconde.

### 16.8 — Quatre artefacts livrés que rien ne compare à leur source

| artefact | ce qui est mesuré |
|---|---|
| `requirements-api.txt:52` | `bcrypt>=4.0,<4.1` contre `<5.1` dans `requirements.txt` et `pyproject.toml`. `uv.lock` résout 4.0.1, qui satisfait les deux — mais les images Docker installent depuis les `requirements*.txt`, pas depuis le lock. bcrypt 4.1+ **refuse** un mot de passe de plus de 72 octets là où 4.0 le tronque : la même inscription peut passer d'un côté et échouer de l'autre. Un cliquet gèle la divergence (`test_the_two_images_pin_the_same_versions`) ; **relever une épingle change ce qu'une image de production installe** |
| 3 PNG d'exemple | `a275ece` (2026-09-12) a changé la palette du générateur ; les images datent de `18b9de5` (2026-09-04). Ce sont les figures servies à tout artiste sans données. `make example-charts` les régénère — c'est un changement **visible par l'artiste** |
| `.claude/dev-docs/api/endpoints.md` | annonce « 8 routes », l'API en sert **11** (10 au schéma OpenAPI + `/metrics`), et les chemins tabulés sont ceux d'avant les préfixes. Son générateur n'a aucun invocateur et ses seuls référents vivants sont dans `.claude/.retired/` — régénérer ou retirer `.claude/dev-docs/api/` est une décision |
| 7 PNG orphelins de `docs/guides/media/` | `_swap()` n'écrit que si absent et **ne supprime jamais** ; 17 des 24 commités sont référencés |

**La décision** : pour chacun, régénérer, aligner, ou retirer.

### 16.9 — Quatre chiffres que l'artiste voit et qui mélangent deux natures

Toutes mesurées le 2026-09-18 ; aucune n'est corrigée, parce que chacune change un nombre
qu'un artiste a déjà lu.

**a. Le PDF trace 152 jours de zéro avant la première mesure.**
`pdf_charts.py:352` (`platform_evolution`, titre « cumulative growth ») laisse la tête de
la courbe à zéro, et le code le justifie : « avant sa première mesure, une plateforme
valait bien zéro ». Mesuré sur l'artiste 1 : **152 seaux à zéro** avant le premier niveau
YouTube (118 032), **155** avant SoundCloud (23 241).

**b. Apple Music : « streams quotidiens » calculés sur des jours non consécutifs.**
`apple_music.py:162-163` et `pdf_exporter/_collectors.py:830-831` font
`plays - LAG(plays) OVER (...)` sans borner la consécutivité. Mesuré : **11 paires,
0 consécutive, plus grand trou 12 jours** — 100 % des points portent la croissance de
plusieurs jours posée sur un seul.

```bash
docker exec $(docker ps --format '{{.Names}}' | grep -i postgres | head -1) \
  psql -U postgres -d spotify_etl -c "
    SELECT COUNT(*) paires, COUNT(*) FILTER (WHERE d = 1) consecutives, MAX(d) plus_grand_trou
      FROM (SELECT date - LAG(date) OVER (PARTITION BY song_name ORDER BY date) d
              FROM apple_songs_history) t WHERE d IS NOT NULL;"
```

**c. Le digest hebdomadaire somme deux générations de lignes Meta.**
`digest_queries.py:97` fait `SUM(spend)` sur `meta_insights_performance`, qui porte
**231 lignes quotidiennes (3 087,82 €)** et **21 lignes de cumul à vie (3 077,83 €)**
datées du seul 2025-12-15 — total mélangé **6 165,65 €**. La borne est un seuil de date,
donc l'e-mail est juste **par accident de calendrier**, pas par construction.

**d. Le compteur public dit 10 artistes, 1 est réel.**
`live_pulse.py:71` compte **10** locataires « humains » ; **9 sont des artefacts de test**
(8 `Oracle Probe`, 1 `Smoke`). Les 8 portent tous `created_at` du **2026-09-15 entre 18h32
et 18h34** — une seule exécution — et plusieurs passes complètes le 2026-09-18 n'en ont
ajouté aucune : **la fuite est refermée**, c'est un résidu. `tenant_kind.py` déclare trois
genres ; les fixtures en produisent un quatrième, qui tombe dans « real ».

**La décision** : pour (a), (b) et (c), resserrer et prévenir, ou laisser et documenter.
Pour (d), effacer 9 lignes d'une base est une opération de données, et déclarer un
quatrième genre est un changement de schéma — les deux t'appartiennent.

### 16.10 — Trois exports cochables qui rendent une feuille vide

`export_csv.py:74,78` propose à l'artiste de cocher **Apple Music** et **YouTube
playlists** ; `csv_exporter.py:58,63,89` en fait des onglets du ZIP. Mesuré :
`apple_daily_plays`, `apple_listeners` et `youtube_playlists` portent **0 ligne** et
**aucun chemin de code ne les écrit**. Les deux parseurs qui les produiraient
(`apple_music_csv_parser.py:179` et `:221`) **n'ont aucun appelant**.

Et le cas le plus coûteux n'est pas une table vide : `apple_songs_history` porte
**22 lignes GELÉES au 2025-12-11**, aucun `INSERT` nulle part, et **sept lecteurs** —
dont deux collecteurs du PDF client et le panneau de fraîcheur admin. Une table figée
ment mieux qu'une table vide : elle affiche un chiffre.

```bash
docker exec $(docker ps --format '{{.Names}}' | grep -i postgres | head -1) \
  psql -U postgres -d spotify_etl -c "
    SELECT relname, n_live_tup FROM pg_stat_user_tables
     WHERE relname IN ('apple_daily_plays','apple_listeners','youtube_playlists',
                       'apple_songs_history') ORDER BY 1;"
```

**La décision** : retirer ces sources de l'export, ou rebrancher les parseurs. Et pour
Apple : la collecte est-elle censée reprendre depuis le 2025-12-11 ?

### 16.11 — Quatre barèmes pour « une source n'a pas collecté récemment »

| surface | seuil API | seuil CSV |
|---|---|---|
| `freshness_monitor.py:8,9` | 48 h | 168 h |
| `kpi_helpers.py:44-47` | 🟢<24 · 🟠<72 · 🔴≥72 | 🟢<168 · 🟠<720 |
| `alert_monitor.py:633,1052` | **36 h** | **36 h** aussi |
| `db_health.py:45,46` | 🟠 336 h · 🔴 720 h | idem |

Mesuré sur les écarts réels entre collectes consécutives : **18 écarts** tombent entre
24 h et 36 h — le tableau de bord peint 🟠 et **aucune surface d'alerte ne parle** ;
**6** tombent entre 36 h et 48 h, où `alert_monitor` déclencherait et
`freshness_monitor` dirait « fraîche ». Et le canari applique 36 h uniformément, **y
compris à S4A que le registre déclare `csv` avec 168 h**.

⚠️ Une cinquième expression est en PROSE et déjà fausse : `alert_monitor.py:1039` écrit
« *past a 48h threshold* » au-dessus d'un code qui utilise 36.

**La décision** : quel barème fait foi, et les autres s'y réfèrent.

### 16.12 — Huit seuils écrits d'instinct, chacun avec ce qui tombe du mauvais côté

Le détail est dans le champ `siblings` de `a-threshold-true-at-one-grain-and-false-at-another`.
Les trois qui demandent une décision, avec leur mesure :

- `_DISCONTINUITY_MIN_POINTS = 10` : **1 série sur 4 est du mauvais côté, à un point
  près** — le locataire 471 a 9 points YouTube, le détecteur est muet pour lui.
- `MIN_BASELINE_ROWS = 5.0` appliqué à 5 tables dont l'unité de « ligne » diffère :
  **1 couple (table, locataire) sur 6 sous le plancher**, et **0 sur 6 ne déclenche**.
  Le seuil est **inerte** — la forme exacte de la leçon des « 30 lignes/jour ».
- Quatre nombres pour le même choix jour↔semaine↔mois — **360/60**, **92**, **90**,
  **120**. Conséquence mesurée : « tout l'historique » (≈1 356 j) se dessine en **mois**
  sur la page d'accueil et en **semaine** dans l'onboarding et le PDF. Même locataire,
  même figure, même jour.

### 16.13 — Deux tables de journal, deux moitiés du même écart

`data_revisions` n'est **ni déclarée ni purgée** — elle est écrite par un **déclencheur
SQL**, donc invisible à l'inventaire de la migration 124, qui a été fait sur les
écrivains Python. `rate_limit_hits` est l'inverse : **purgée sans être déclarée**, donc
`undeclared_tables()` ne peut pas la juger — le prochain inventaire la comptera comme non
purgée, ou retirera la purge sans rien casser d'apparent.

**La décision** : déclarer une rétention est un changement de schéma (`COMMENT ON
TABLE`), donc un geste de migration.

### 16.14 — `/health` dit « ok » sans rien vérifier, et trois systèmes le croient

`src/api/main.py:164` rend `{"status": "ok"}` **sans aucune vérification**. Trois surfaces
en font un verdict FINAL : `railway.toml:24` (`healthcheckPath`),
`docker-compose.yml:171` (`test: curl --fail`), `Dockerfile.api:54` (`HEALTHCHECK`).

**Un conteneur dont la base est injoignable est donc déclaré sain et continue de recevoir
du trafic.**

```bash
grep -n "status.*ok" src/api/main.py
grep -rn "health" railway.toml docker-compose.yml Dockerfile.api
```

**La décision** : ce que `/health` doit vérifier. Y ajouter un ping Postgres change
**quand un conteneur est retiré du service** — une base momentanément lente ferait
redémarrer l'API. C'est un arbitrage de disponibilité, pas un correctif.

### 16.15 — Le scheduler reparse les DAG deux fois par minute, en vrai

```
$ docker exec airflow_scheduler airflow config get-value scheduler min_file_process_interval
30
env: <unset>
```

Le correctif de la classe `orchestrator-costs-more-than-what-it-orchestrates` — « 30 →
300 s, rapport cyclique divisé par 10 » — **n'est pas appliqué au système qui tourne**. Le
réglage n'existe que dans `docker-compose.example.yml:64` ; `docker-compose.yml:43` ne le
porte pas.

⚠️ **Et le garde lit le GABARIT** : `test_the_scheduler_is_not_the_biggest_cost.py:61`
pointe `docker-compose.example.yml`. Il est vert sur le modèle pendant que le système réel
est au défaut.

**Adjacent, mesuré, sans site de code** : `airflow_webserver` occupe **1,047 Gio** à 0,10 %
CPU — ~1,8× le scheduler, ~4,6× Postgres — pour une UI en loopback, sans limite déclarée.
Et **~50 Mo de bases d'échafaudage orphelines** créées le 2026-09-11 (`ci_like_…`,
`freshcheck_…`, `spotify_etl_ci`, `spotify_etl_fresh`) contre 53 Mo pour la base réelle ;
aucun `CREATE DATABASE` du dépôt ne les produit — ce sont des gestes manuels.

**La décision** : modifier `docker-compose.yml` touche la pile déployée.

### 16.16 — Vingt dates affichées sans dire de quelle horloge elles viennent

Les colonnes naïves de cette base portent de l'**UTC** (vérifié : `etl_run_log.started_at`
à 9 min du `now() AT TIME ZONE 'UTC'`), et les `timestamptz` remontent en UTC. Un
`strftime` direct affiche donc l'heure UTC **sans qualificatif** : en été parisien c'est
−2 h, et au bord de minuit c'est le **jour** qui change.

**20 sites** — les badges de fraîcheur de l'accueil, sept colonnes de la page Alertes dont
`locked_until` et la date d'inscription, le journal ETL, les dates de disjoncteur, les
périodes d'abonnement.

⚠️ Ce qui rend la décision facile à prendre et difficile à deviner : **deux sites du MÊME
fichier traitent la MÊME colonne différemment** — `soundcloud.py:57` convertit, `:266`
non ; `instagram.py:70` convertit, `:31` non. Le mécanisme existe (`utils/tz.py`), il
n'est simplement pas appliqué partout.

**La décision** : afficher l'heure locale change ce que l'artiste lit sur vingt écrans.

### 16.17 — Trois pages rendent 38, 34 et 19 figures

`trigger_algo` (page routée) rend **11 graphiques + 27 jauges = 38 figures** au premier
écran — le site historique de la classe, jamais corrigé : `secondary_analyses` n'est
adopté que dans **1 fichier sur 10**. Puis `revenue_forecast` (5 + 29 = 34) et
`airflow_kpi` (3 + 16 = 19, zéro adoption).

⚠️ **Le garde est vert**, pour deux raisons cumulatives : il compte **par fichier** (une
page-paquet de 10 fichiers avec une seule entrée de routage échappe au plafond), et
`_RENDERERS` **n'inclut pas `st.metric`** alors que le `root_cause` de la classe compte
les jauges.

**Nuance à trancher** : les fichiers `_tab_*` sont des ONGLETS. Si un onglet compte comme
un second écran, `trigger_algo` est défendable (1 à 4 graphiques par onglet). Mais le
garde n'exclut que `secondary_analyses` et `expander`, **pas `st.tabs`** — par sa propre
définition, un onglet est du premier écran.

**Vérification que cette section est à jour** :
`python3 -m pytest tests/test_roadmap_index_is_honest.py -q`

## 17. ~~R134 — Lancer le calibrateur de creux contre la base de PRODUCTION~~ · ✅ FAIT le 2026-09-20 — lancé en production, **0 table sur 8 calibrable** ; détail dans `.claude/dev-docs/roadmap/archive.md`

⚠️ **Et la commande écrite ici était infaisable.** Elle prescrivait `make dip-calibrate` « depuis un shell qui voit la production » ; le serveur n'a pas `psycopg2` — tout y tourne en conteneur. La bonne commande est `make dip-calibrate-prod PROD_SSH=…`, qui passe par le scheduler Airflow, seul endroit qui bind-monte `tools/` ET porte la dépendance.

**Ce que j'attends de toi** : une commande, et sa sortie collée ici.

```bash
make dip-calibrate            # depuis un shell qui voit la base de PRODUCTION
```

### Pourquoi je ne peux pas le faire moi-même

Le détecteur de creux (`check_row_dips`) ne surveille que **5 tables**. Un locataire qui
perd ENTIÈREMENT Instagram, Apple, Hypeddit ou SACEM ne déclenche aucune alerte — sa
collecte s'arrête et le mail du soir ne dit rien.

Étendre la liste demande un seuil **par table**, et ce dépôt s'interdit de l'écrire
d'instinct pour une raison mesurée : un plancher de 30 lignes/jour, écrit à vue, avait
rendu ce détecteur aveugle à **2 locataires sur 3**.

**Mesuré le 2026-09-19 sur la base locale : 0 table sur 8 est calibrable.**

| table | observations (locataire, jour) | verdict |
|---|---|---|
| `instagram_daily_stats` | 34 | pas un fait quotidien — **12 %** de jours couverts |
| `hypeddit_daily_stats` | 21 | échantillon trop petit |
| `sacem_statement` | 9 | échantillon trop petit |
| `apple_songs_history` | 2 | échantillon trop petit |
| `instagram_media` | 1 | échantillon trop petit |
| `instagram_media_insights`, `apple_daily_plays`, `apple_listeners` | **0** | vides |

Ce n'est pas une panne de l'outil : c'est une base de développement. Les distributions
existent en production, et nulle part ailleurs.

### Ce qui est déjà livré, et qui t'attend

- `tools/dev/calibrate_dip_thresholds.py` + `make dip-calibrate` — il dérive médiane,
  10ᵉ centile et couverture par table, et **REFUSE** de rendre un seuil quand
  l'échantillon est trop petit ou quand la table n'est pas un fait quotidien.
- `tests/test_a_dip_threshold_is_derived_not_guessed.py` — une table ajoutée à
  `DIP_TENANT_COLUMN` sans dérivation datée fait rougir la suite. Muté : ajouter
  `instagram_daily_stats` sans sa mesure rougit ; avec, passe.

⚠️ **Une correction à la liste des candidates** : `hypeddit_campaigns` avait été comptée
éligible parce qu'elle porte `artist_id` et une date. C'est une table de **dimension** —
des campagnes sont créées de temps en temps, pas chaque jour. Un « creux » y est le
fonctionnement normal, et l'y brancher aurait produit une alerte quotidienne que personne
ne lit, ce qui détruit le détecteur pour les tables où il a raison. Elle est retirée des
candidates, et le critère est désormais « reçoit-elle des lignes CHAQUE JOUR », mesuré,
au lieu de « porte-t-elle un locataire et une date ».

### Ce que je fais de ta réponse

Je reporte chaque seuil dérivé dans `DIP_TENANT_COLUMN` **avec `n=<observations>` et la
date de ta mesure** — c'est ce que le garde exige — puis j'étends le détecteur aux seules
tables que le calibrateur a acceptées. Celles qu'il refuse restent dehors, avec leur
raison écrite.

---

## 18. R151 — La hiérarchie des évènements agrégés Meta (limite iOS 14)

**Cinq minutes dans le Gestionnaire d'évènements, et c'est le geste le plus rentable
des sept ouverts le 2026-09-22.** Il ne change pas une ligne de code : il change la
FIABILITÉ de tous les coûts par résultat que l'app affiche.

### D'où ça sort

*La petite boîte à outils Facebook Ads et Instagram Ads* (Pellerin) :

> « Depuis iOs 14, il est nécessaire de définir une **hiérarchie** entre les
> différentes conversions personnalisées créées, afin que Facebook identifie
> celle(s) à mesurer en priorité. »

Meta ne mesure que **huit évènements par domaine**, dans un ordre que TU choisis. Si la
conversion Hypeddit n'est pas en haut de cette liste, une partie des conversions n'est
pas attribuée du tout — et ça se lit comme des campagnes moins performantes qu'elles ne
le sont. Le chiffre est faux dans le sens qui décourage.

### Les étapes

1. Ouvrir **business.facebook.com** → menu de gauche → **Gestionnaire d'événements**.
2. Colonne de gauche, choisir la **source de données** qui porte le pixel utilisé par
   les campagnes (celui d'Hypeddit, pas un pixel de test).
3. Onglet **Paramètres** (ou **Settings**) → section **Mesure des événements agrégés**
   → bouton **Configurer les événements Web**.
4. Le domaine vérifié apparaît avec ses huit emplacements. Repérer l'évènement de
   conversion personnalisée d'Hypeddit — c'est celui que l'app lit sous le nom
   `custom_conversions`.
5. **Le faire glisser en position 1**, au-dessus de `PageView`, `ViewContent` et
   `Lead` s'ils y sont. La priorité 1 est celle que Meta mesure toujours.
6. Cliquer **Appliquer**. Meta prévient que la modification met **72 heures** à
   prendre effet et suspend l'optimisation pendant ce délai — c'est normal, et c'est
   la raison pour laquelle on le fait une fois, pas tous les mois.

### Si l'étape 4 ne montre aucun domaine

Le domaine n'est pas vérifié. Dans **Paramètres de l'entreprise → Sécurité de la marque
→ Domaines**, ajouter le domaine du smart link Hypeddit et suivre la vérification par
enregistrement DNS. Sans domaine vérifié, la hiérarchie n'existe pas et **aucun**
évènement web n'est priorisé.

### Vérification — ce qui prouve que c'est fait

Capture d'écran de la liste des huit évènements avec la conversion Hypeddit en
position 1. Puis, **soixante-douze heures plus tard**, comparer le nombre de résultats
d'une campagne active avant et après :

```bash
ssh <prod> "docker exec postgres_spotify_airflow psql -U postgres -d spotify_etl -c \
  \"SELECT day, SUM(custom_conversions) FROM v_meta_campaign_daily \
    WHERE artist_id = 1 AND day > CURRENT_DATE - 14 GROUP BY day ORDER BY day;\""
```

⚠️ Une hausse n'est PAS une preuve à elle seule — la dépense varie aussi. Ce qui
tranche est le rapport `custom_conversions / link_clicks` : la priorisation ne crée pas
de clics, elle en fait remonter davantage.

### Ce que ce geste ne corrige pas

R146 reste entier : même parfaitement attribué, ce chiffre compte des **clics
sortants**, pas des écoutes. Les deux tâches sont indépendantes — l'une répare la
mesure, l'autre dit ce qu'elle mesure.

---

## 19. R148 — Trois conversations « combien tu paierais »

**Le prix de 10 €/mois a été posé, jamais mesuré.** *Monetizing Innovation*
(Ramanujam & Tacke) dit de parler du prix AVANT de construire ; ici l'ordre a été
l'inverse. Le livre ne dit pas que 10 € est faux — il dit qu'on n'en sait rien, et
c'est vérifiable : **zéro trace d'un entretien sur la disposition à payer dans tout le
dépôt**.

### ⚠️ Lire ceci avant de décrocher le téléphone

Mesuré en production le 2026-09-22 : sur quatre artistes bêta, **un seul** a une
plateforme qui livre des données. Cuzebo attend depuis **cent jours**, GRiNCH depuis
quarante et un, artiste1 depuis vingt-trois — et l'essai d'artiste1 se termine le
**2026-09-29**.

Demander à quelqu'un ce qu'il paierait pour un produit **qu'il n'a jamais vu
fonctionner** ne mesure rien. Les trois entretiens se font donc avec des gens qui ont
vu leurs propres chiffres à l'écran. Aujourd'hui, ça fait **une** personne.

**L'ordre est donc : activer d'abord (voir §20), interroger ensuite.**

### Les questions — dans cet ordre, et sans en sauter

Elles viennent de la méthode Van Westendorp, qui pose quatre prix et non un. On ne
demande jamais « est-ce que tu paierais 10 € ? » : la réponse est une politesse.

1. « À quel prix ce produit te semblerait-il **trop cher** pour que tu l'envisages ? »
2. « À quel prix te semblerait-il **cher, mais tu réfléchirais** quand même ? »
3. « À quel prix te semblerait-il une **bonne affaire** ? »
4. « À quel prix te semblerait-il **si bas que tu douterais** de la qualité ? »
5. Puis, seulement là : « Qu'est-ce que tu fais aujourd'hui à la place, et combien ça
   te coûte — en argent ou en heures ? »

La question 5 est celle qui vaut le plus. Un prix se compare toujours à une
alternative ; si l'alternative est « je regarde Spotify for Artists gratuitement le
dimanche », le chiffre des questions 1 à 4 ne veut pas dire grand-chose sans elle.

### Le geste

Trois entretiens, **vingt minutes chacun**, en direct (pas par écrit — on perd les
hésitations). Noter les réponses **verbatim**, pas résumées.

### Vérification

Un fichier `docs/wtp-interviews-2026-XX.md` avec, pour chacun des trois : la date, qui,
les quatre prix, la réponse à la question 5. Trois entretiens, douze prix. C'est tout
ce que cette tâche demande — **aucune décision de tarif n'en découle automatiquement**.

---

## 20. R150 — Trois options chiffrées pour la prestation

Le panneau de prestation livré le 2026-09-21 nomme quatre arguments et propose un
appel. Il **ne chiffre rien** — donc chaque appel recommence à zéro, et c'est toi qui
portes la charge de sortir un prix en direct.

*Pricing Creativity* et *The Win Without Pitching* (Blair Enns) : proposer des
**options**, jamais un prix. Et le mécanisme mesuré : « adding a third, higher price
increases the sales of the middle price — previously the highest price — by almost
**50 %** ». Trois options ne servent pas à vendre la plus chère ; elles servent à
rendre celle du milieu évidente.

### Ce qui a changé le 2026-09-22 — l'ordre s'est inversé

Cette section disait « la construction suit le remplissage, pas l'inverse », et
demandait de remplir un tableau **ici**, en Markdown. C'est l'inverse qui a été fait,
et pour une raison : un prix écrit dans un runbook ne s'affiche nulle part, et un prix
écrit dans le code demande un redéploiement pour bouger — donc ne bouge jamais.

**La page existe depuis le 2026-09-22** : `🎯 Faire piloter mes campagnes`, accessible
à tous les plans, trois options en colonnes avec les prix en bas (Enns p. 29), les
livrables typés par agent (🙋 toi / ⚙️ l'outil), les quatre leviers gratuits, et le
bouton de rendez-vous. **Aucun montant n'est écrit dans le code.** Tant que les trois
prix ne sont pas posés, l'artiste voit la page **sans sa grille** — et toi seul vois
un avertissement qui te renvoie ici.

### Le geste — trois champs, dans l'application

1. Ouvrir **⚙️ Admin → onglet Réglages**, section **🎯 Prix de la prestation
   d'optimisation**.
2. Saisir **trois** montants — un nombre entier d'euros, sans décimale ni symbole
   (`450`). Un décimal est refusé, avec sa raison : un prix à la virgule près se lit
   comme un devis calculé, or c'est précisément ce qui n'est pas vendu ici.
3. Enregistrer. Les trois s'appliquent **tout de suite**, sans redéploiement.

Les trois périmètres sont déjà écrits dans `src/dashboard/utils/service_offer.py` et
s'affichent sous chaque nom :

| | périmètre | conditions de paiement |
|---|---|---|
| **Essentiel** | une campagne, une sortie, sur une fenêtre définie | 100 % à la commande |
| **Standard** ← celle que tu veux vendre | le cycle complet d'une sortie : plusieurs angles, et tu itères sur toute la fenêtre | 50 / 50 |
| **Accompagnement** | le cycle Standard répété, sortie après sortie | mensualisé, ou douze mois d'avance avec 10 % de remise |

Deux repères, pas des règles : l'écart entre Essentiel et Standard se lit mieux
autour de ×2, et l'Accompagnement existe même s'il ne se vend jamais — c'est son
rôle.

⚠️ **Les trois, ou aucun.** Afficher le seul prix posé ferait de l'option la moins
chère la seule visible — l'inverse exact de ce que trois options servent à faire.
C'est pour ça que la grille reste masquée tant qu'il en manque un.

### Une décision qui se prend en même temps

Le même mécanisme vaut pour l'**abonnement** : Free et Premium n'ont pas de milieu,
donc Premium à 10 € est le haut de gamme, c'est-à-dire le point de résistance. Un
troisième palier au-dessus déplacerait Premium vers le centre.

⚠️ Ce n'est PAS un axe de valeur — cette question-là est tranchée par **ADR-028**, qui
refuse d'en adopter un tant que l'activation n'est pas réglée. Un troisième palier est
une décision sur la STRUCTURE de l'offre, indépendante de l'unité de facturation.

### Vérification

La preuve que le geste est fait n'est pas « j'ai saisi » : c'est que la grille
s'affiche. Les trois lignes rendent une valeur non vide :

```bash
docker exec -i $(docker ps -qf name=postgres) psql -U postgres -d spotify_etl -c \
  "SELECT key, value FROM app_settings WHERE key LIKE 'service_price_%';"
```

Puis la page, regardée :

```bash
python3 -m pytest tests/test_views_render_smoke.py -q -k "service or billing"
```

---

## 21. ~~R149 — Choisir UNE métrique qui compte pour le stade actuel~~ · ✅ TRANCHÉ le 2026-09-22 — l'activation, mesurée à **2 sur 5** ; le geste commercial qui reste est décrit ci-dessous

**R149 est CLOSE le 2026-09-22** : la métrique est choisie, mesurée et posée en tête du
panneau de supervision admin. Ce n'est pas un choix de goût — la mesure a tranché seule.

**L'activation vaut 2 sur 5** (locataires humains). Trois comptes n'ont jamais reçu
une seule ligne de donnée, et leur `etl_run_log` ne porte aucun échec : il porte
`skipped`, parce qu'aucun identifiant de plateforme n'a été saisi. Le garde d'identité
fait son travail, et `alert_monitor` dit explicitement que `skipped` n'est pas un
signalement. Correct pour l'exploitation, **aveugle pour le commerce**.

### Le geste qui reste — il n'est pas technique

Trois comptes à relancer, par ordre d'urgence :

| artiste | inscrit depuis | essai | quoi faire |
|---|---|---|---|
| **artiste1** (id 17) | 23 jours | **se termine le 2026-09-29** | le plus urgent — sept jours pour qu'il voie quelque chose |
| **GRiNCH** (id 13) | 41 jours | clos le 2026-09-11 | essai déjà perdu ; le rattraper demande une prolongation |
| **Cuzebo** (id 11) | 100 jours | clos le 2026-07-14 | le plus ancien ; savoir s'il est encore joignable avant d'investir |

Ce qui leur manque est **un identifiant de plateforme saisi dans l'app** (Spotify,
SoundCloud, YouTube ou Instagram). La procédure côté artiste est celle de la section
sur la session de test artiste ; côté toi, le geste est de vérifier avec eux, en
direct, que la page de connexion des plateformes est franchissable.

### Vérification

```bash
ssh <prod> "docker exec streamlytics_dashboard python3 -c \"
import sys; sys.path.insert(0,'/app')
from src.database.postgres_handler import PostgresHandler
from src.utils.activation import activation_sql, dormant_tenants_sql
db = PostgresHandler.from_env_or_config()
print('activés :', db.fetch_query(activation_sql())[0])
for r in db.fetch_query(dormant_tenants_sql()): print(' dormant', r)
\""
```

La tâche est close quand cette commande rend **zéro dormant** — ou quand la relance a
eu lieu et que la réponse est écrite, y compris si c'est un non.
