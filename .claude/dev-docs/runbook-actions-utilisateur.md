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

## 2. R20 — Créer le canari en PRODUCTION · P2  *(le local est fait)*

**Local : fait le 2026-08-21.** `artist_id=471`, `slug='canary-isolation'`, Spotify
`4tZwfgrHOc3mvqYlEYSvVi` + YouTube `UC_x5XG1OV2P6uZZ5FSM9Ttw`.
`python3 tools/artist_preflight.py --platforms youtube` passe **vert de bout en bout**,
contamination comprise.

**Ce qu'il a rapporté en une heure** — c'est l'argument, pas l'anecdote. Trois défauts
réels, tous structurellement invisibles à une base mono-locataire :

| classe | ce qui se passait |
|---|---|
| `identity-mirrored-but-written-once` (P1) | l'identité Spotify vit dans **deux** tables ; l'outil n'en écrivait qu'une. Affichage « Connecté — Daft Punk ✅ » partout, **zéro ligne collectée**. |
| `api-partial-date-into-date-column` (P2) | Spotify renvoie `release_date` à précision variable ; « 2013 » faisait perdre à l'artiste **tous** ses top tracks du run. Latent depuis des années — ton catalogue n'a que des dates complètes. |
| `env-resolved-against-cwd` (P2) | le `.env` était résolu contre le répertoire courant : rouges qui mentaient sur leur cause, et un dashboard qui ne chargeait rien lancé de la façon documentée. |

### Ce qui reste : la même commande, sur le serveur

⚠️ **Dans cet ordre.** Le correctif du miroir d'identité doit être déployé **avant**, sinon
le canari de prod naîtra avec le même défaut que celui qu'il vient de révéler.

**Déjà fait pour toi le 2026-08-21** : code déployé (`15f3a19`), registre de migrations
posé en prod (**71/71**, second passage « nothing to apply »), clé primaire de
`s4a_song_playlist_adds` vérifiée intacte.

**Il reste une étape manuelle, une seule fois.** Le compose de production est
**gitignoré**, donc le montage que je viens d'ajouter à `docker-compose.example.yml`
**n'arrive pas par `git pull`**. Sans lui la commande suivante échoue sur
`can't open file '/app/tools/create_canary.py'` : `tools/` est sur l'hôte, où
psycopg2 n'est pas installé, et psycopg2 est dans les conteneurs, où `tools/` n'était
pas monté.

```bash
ssh root@167.233.92.1
cd /opt/streamlytics
nano docker-compose.yml     # sous CHAQUE service airflow, à côté de « - ./src:/opt/airflow/src » :
                            #       - ./tools:/opt/airflow/tools:ro
docker compose up -d airflow-scheduler airflow-webserver

# puis le canari lui-même :
docker exec airflow_scheduler python3 /opt/airflow/tools/create_canary.py \
    --name "Canary prod" --slug canary-prod \
    --spotify 4tZwfgrHOc3mvqYlEYSvVi --youtube UC_x5XG1OV2P6uZZ5FSM9Ttw --dry-run
```
Retire `--dry-run` quand la sortie te convient. `make` n'existe pas sur le serveur —
d'où l'appel direct au script.

**L'identité n'a pas besoin de t'appartenir** — vérifié le 2026-08-21 : Spotify, YouTube et
SoundCloud lisent des endpoints **publics** avec les credentials de l'app admin. C'est ce
qui débloque ton cas « tous mes identifiants admin sont mes propres profils ». Seul **Meta**
exige une propriété réelle ; le canari ne le couvre donc pas, sans conséquence puisque Meta
est à l'arrêt (§1).

### Vérification

```bash
docker exec airflow_scheduler python3 /opt/airflow/tools/artist_preflight.py --platforms youtube
```
Doit finir sur `✅ Pre-flight green FOR youtube ONLY`.

⚠️ **Effet de bord à connaître** : le canari sera collecté chaque nuit par les DAG de flotte.
C'est voulu — c'est ce qui le rend détecteur — mais il consomme un peu de quota d'API.

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

### Étapes

1. Faire **R20** d'abord, puis `make artist-preflight` — il doit être vert. C'est le
   filet : deux sessions bêta ont brûlé une heure chacune sur des choses que ce contrôle
   voit d'avance.
2. Idéalement R13 aussi, sinon Meta et Instagram resteront vides pour tes invités.
3. Inviter les proches sur `https://streamlytics.fr`.
4. Après leur inscription :
   ```bash
   make artist-preflight ARTIST=<leur id>
   make tenant-check
   ```

**R2** (landing + pixel + CAPI) démarre avec la **première campagne**, pas avant — voir
`docs/adr/ADR-008`. Retiens seulement ceci : l'attribution est la seule partie qui a une
échéance, parce que `_fbp`/`_fbc` et les UTM ne se récupèrent pas rétroactivement.
