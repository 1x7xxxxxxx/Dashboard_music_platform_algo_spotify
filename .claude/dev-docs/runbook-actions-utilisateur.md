# Runbook — les 4 actions qui n'appartiennent qu'à toi

Écrit le 2026-08-21. Ce sont les seuls items encore ouverts de la ROADMAP : aucun ne
peut être fait depuis une session Claude Code, chacun demande un accès, un fichier ou
une décision qui est à toi. Ils sont classés par ce qu'ils débloquent.

Après chacun, la vérification est donnée — ne pas la sauter : c'est elle qui distingue
« fait » de « cru fait », et cette distinction a coûté deux sessions de test artiste.

---

## 1. R13 — Régénérer le token Meta System User  · P2

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

## 4. R17 — Ingérer un corpus ergonomie / front-end · P3

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

## 5. R1 — Ouvrir la bêta privée · P3

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
