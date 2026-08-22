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

### 6b. Test d'intrusion réseau externe — ⬜ demande un accès depuis l'extérieur

Ce qu'un audit du dépôt ne peut pas voir : ce que la boîte expose réellement.

```bash
# depuis une machine HORS du VPS (pas depuis WSL, pas depuis le serveur)
nmap -Pn -sV --top-ports 1000 167.233.92.1
curl -sI https://app.streamlytics.fr | head -20     # en-têtes Caddy + HSTS
testssl.sh --quiet --color 0 https://app.streamlytics.fr
```

Ce qu'on cherche : un port ouvert qui n'est ni 22, ni 80, ni 443 (le **5433** de
Postgres en particulier — il est publié en local par `docker-compose`, et le compose
de production est gitignoré, donc le dépôt ne peut pas répondre à sa place) ; une
suite TLS obsolète ; un en-tête de sécurité que Cloudflare réécrit.

**Vérification** : `nmap` ne renvoie que 22/80/443, et `testssl.sh` ne renvoie aucun
`NOT ok` en rouge.

### 6c. Fuzzing des endpoints — ⬜ demande un outil qui n'est pas installé

```bash
pip install schemathesis
schemathesis run https://api.streamlytics.fr/openapi.json \
    --checks all --hypothesis-max-examples 200 \
    -H "Authorization: Bearer $TOKEN"
```

L'API expose son schéma OpenAPI, donc le fuzzing est dirigé plutôt qu'aveugle.
Ce qu'on cherche : un 500 (une entrée qu'un validateur Pydantic laisse passer et
qu'une requête SQL ne supporte pas), et une réponse qui contient un nom de table.

**Vérification** : `schemathesis` sort en 0, et aucun cas ne renvoie 500.

**Ce que ça débloque** : la dernière ligne ouverte de R21/R22. Le reste du pentest
est clos et gardé par des tests.
