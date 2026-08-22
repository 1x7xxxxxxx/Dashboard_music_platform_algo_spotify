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

### Ce que le filet couvre RÉELLEMENT — mesuré le 2026-08-22 sur la prod

La ligne « préflight vert de bout en bout » était trop généreuse. Exécutée sur le canari
de production (`artist_id=14`), la préflight complète est **ROUGE** à l'étape 2 :

```
❌ ☁️ SoundCloud — ton User ID SoundCloud numérique
✅ 🎵 Spotify
✅ 🎬 YouTube
❌ 📱 Meta Ads — ton Ad Account ID
❌ 📸 Instagram — ton Instagram Business Account ID
```

Restreinte aux deux plateformes que le canari possède, elle est verte de bout en bout —
identité, test de connexion, données arrivées, **contamination propre** — et l'outil
imprime lui-même le bon avertissement :

> `✅ Pre-flight green FOR spotify, youtube ONLY — the other platforms were not proven.`

Autrement dit **le filet ne couvre pas les deux plateformes qui ont cassé** : Meta chez
Benken, Instagram chez GRiNCH. Inviter aujourd'hui, c'est réintroduire exactement le
risque que R20 devait supprimer, pour trois plateformes sur cinq.

Le compléter demande **tes** identifiants, parce qu'une identité de locataire n'a par
construction aucune valeur par défaut (`.claude/rules/python.md`) : un user id SoundCloud
numérique, un Ad Account Meta, un IG Business Account — sur des comptes réels que le
canari puisse utiliser sans polluer les tiens.

### Étapes

0. **Déployer la séance du 2026-08-22.** `make sync-check PROD_SSH=root@167.233.92.1`
   nomme aujourd'hui une seule dérive, `saas_users.token_version` — la migration 072.
   Ordre : `make deploy` puis `make migrate-prod`, jamais l'inverse (classe
   `migration-ahead-of-its-code`).
1. Donner au canari les trois identités manquantes, puis :
   ```bash
   docker run --rm --network container:streamlytics_api \
     -v /opt/streamlytics/tools:/app/tools -w /app --env-file .env \
     streamlytics-dashboard python3 tools/artist_preflight.py --artist 14
   ```
   Sans `--platforms`, et **vert**. C'est ça, le filet complet. (`tools/` n'est monté
   dans aucun conteneur par défaut — d'où le `-v` ; et l'image `python:3.12-slim` ne
   suffit pas, il faut celle du dashboard.)
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

---

## 6. R22 — Le volet non-code du pentest · P2

Le volet code est clos (R21, 2026-08-22 : six constats CRITIQUE/HAUT corrigés et
déployés). Il restait trois choses qui **ne se lisent pas dans le dépôt**. L'une
d'elles est faite ; les deux autres demandent un accès ou un outil qui n'est pas ici.

### 6a. `pip-audit` — ✅ FAIT le 2026-08-22

```bash
python3 -m venv /tmp/auditvenv && /tmp/auditvenv/bin/pip install -q pip-audit
/tmp/auditvenv/bin/pip-audit -r requirements.txt
```

Résultat : **une** vulnérabilité, `ecdsa 0.19.2` / PYSEC-2026-1325 — attaque
temporelle Minerva sur la courbe P-256, qui touche la **signature**, la génération de
clé et l'ECDH, **pas** la vérification. Le projet python-ecdsa considère les canaux
auxiliaires hors périmètre : **aucun correctif n'est prévu**, il n'y a donc pas de
version vers laquelle monter.

Non applicable ici, et c'est vérifiable en une commande plutôt qu'en confiance :
`ecdsa` n'arrive que transitivement par `python-jose`, et nos JWT sont HS256 de bout
en bout (`src/api/auth.py` — `ALGORITHM = "HS256"`, `encode` et `decode` l'épinglent
tous les deux). Le chemin de signature ECDSA n'est jamais atteint.

`make audit-deps` rejoue le contrôle et échoue sur toute **autre** vulnérabilité ;
celle-ci est ignorée nommément, avec cette raison, dans la cible.

### 6b. Test d'intrusion réseau externe — ✅ FAIT le 2026-08-22

Fait depuis WSL, qui **est** une machine hors du VPS — c'est ce que ce point demandait,
et je l'avais classé « en attente de toi » à tort.

Les trois noms d'hôte résolvent sur Cloudflare (`2a06:98c1:…`), donc **on ne scanne pas
le nom** : ce serait l'infrastructure d'un tiers. On scanne l'origine, la boîte Hetzner.

```bash
# scan TCP connect de l'origine (33 ports usuels) — lecture seule
python3 - <<'EOF'
import socket, concurrent.futures as cf
HOST="167.233.92.1"
PORTS=[21,22,23,25,53,80,110,143,443,445,873,1433,2375,2376,3000,3306,5000,5432,5433,
       5672,6379,8000,8080,8081,8443,8501,8888,9000,9090,9200,11211,15672,27017]
def probe(p):
    s=socket.socket(); s.settimeout(3)
    try:
        return p if s.connect_ex((HOST,p))==0 else None
    finally: s.close()
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    print(sorted(x for x in ex.map(probe,PORTS) if x))
EOF
```

**Résultat** : `[22]`. Seul SSH répond (OpenSSH 9.6p1 Ubuntu). Postgres 5433, Airflow
8080, Streamlit 8501 : fermés. **80 et 443 ne sont pas joignables en direct non plus** —
Cloudflare atteint la boîte autrement, donc il n'y a pas d'origine à contourner.

TLS des trois noms (`sslyze`, via l'edge Cloudflare, requête client ordinaire) :
SSLv2/SSLv3/TLS 1.0/TLS 1.1 tous à **0 suite acceptée** ; TLS 1.2 (7) et 1.3 (3) ;
Heartbleed, CCS injection, ROBOT : non vulnérable ; certificats valides sur 5/5 magasins
de confiance, expiration 2026-11-09.

**Un constat, corrigé** : le dashboard répondait avec 4 en-têtes de sécurité et l'API
avec 6 — les deux de plus viennent du middleware FastAPI, pas de Caddy, donc l'écart
était invisible depuis le dépôt. `deploy/Caddyfile` porte désormais
`Permissions-Policy`, `X-Permitted-Cross-Domain-Policies` et une CSP volontairement
étroite (`object-src`/`base-uri`/`form-action`/`frame-ancestors` — aucune directive
`script-src`/`style-src`, qui blanchirait Streamlit).
⚠️ **Non validée par un binaire Caddy** (pas d'image disponible ici) : à vérifier avec
`caddy validate --config /etc/caddy/Caddyfile` sur la boîte avant de recharger.

### 6c. Fuzzing des endpoints — ✅ FAIT le 2026-08-22

**Pas contre la prod** : `/openapi.json` et `/docs` y sont désactivés (`API_ENABLE_DOCS`
n'est pas à 1 — bonne posture, mais ça rendait fausse la commande que ce runbook portait
d'abord), et fuzzer une base de production écrit des lignes. On lance le **même code** en
local contre la base locale.

```bash
python3 -m venv .audit-venv && .audit-venv/bin/pip install -q schemathesis
# 1. l'API, docs activées, limiteur relevé pour ne pas se 429 soi-même.
#    La clé de signature est jetable et générée ici : ne jamais écrire une valeur
#    littérale dans ce fichier, le scan de secrets pré-commit la refuse (à raison).
export API_SECRET_KEY=$(openssl rand -hex 32)
export DATABASE_URL="postgresql://postgres:<mot-de-passe>@localhost:5433/spotify_etl"
export API_ENABLE_DOCS=1 API_RATE_LIMIT_MAX=1000000 API_AUTH_RATE_LIMIT_MAX=1000000
python3 -m uvicorn src.api.main:app --port 8599 &
# 2. un jeton pour un compte qui EXISTE (depuis R24, un `sub` inconnu répond 401)
TOKEN=$(python3 -c "from src.api.auth import create_access_token; \
  print(create_access_token({'sub':'<username admin>','role':'admin','artist_id':None,'tv':<son token_version>}))")
# 3. le fuzz
.audit-venv/bin/schemathesis run http://127.0.0.1:8599/openapi.json \
  -H "Authorization: Bearer $TOKEN" --max-examples 300 --workers 2
```

**Vérification** : aucune ligne `Server error` dans la sortie. Avant de fuzzer, vérifier
que les 7 endpoints de données répondent **200** — sinon on mesure son propre
environnement, ce qui est arrivé au premier essai (mauvais mot de passe DB → neuf faux
« Server error » à 503).

**Résultat** : un vrai défaut, `GET /streams/timeline?song=a%00b` → 500
(`ValueError: A string literal cannot contain NUL`, non rattrapée). Corrigé à la
frontière (`security.reject_nul_bytes_middleware` → 400), gardé par
`tests/test_api_survives_hostile_input.py`, classe
`input-nobody-would-type-reaches-the-driver`. Re-fuzzé sur **4 graines, 1730 cas,
zéro 5xx**.

**Ce que ça débloque** : R22 est close. Le pentest n'a plus de volet ouvert.
