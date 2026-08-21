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

## 2. R20 — Créer le locataire canari en production · P2

C'est le prérequis dur de `make artist-preflight`, donc du filet de sécurité avant toute
session avec un artiste réel. Une seule commande ; il ne manque que **tes** identifiants.

### Étapes

1. Choisis une identité **différente de celle de l'admin**. C'est tout l'intérêt : un
   canari qui emprunte la chaîne de l'admin passe au vert pendant que l'isolation qu'il
   teste est cassée. L'outil refuse ce cas, et refuse aussi une identité qu'un autre
   locataire réclame déjà.

   > **Elle n'a pas besoin de t'appartenir.** Vérifié le 2026-08-21 : Spotify, YouTube et
   > SoundCloud sont lus avec les credentials **de l'app admin** sur des endpoints
   > **publics** — `client_credentials` pour Spotify et SoundCloud, `developerKey` seule
   > pour YouTube. Aucun ne demande la propriété du profil. Prouvé en production : les top
   > tracks de deux artistes publics quelconques remontent, 10 titres chacun.
   >
   > C'est ce qui débloque le cas « tous mes identifiants admin sont mes propres profils
   > d'artiste » : prends **n'importe quel artiste public** — le test d'isolation est
   > exactement aussi valide, puisqu'il vérifie que les lignes atterrissent sous le bon
   > locataire, pas qui possède le compte.
   >
   > Seule exception : **Meta**, qui exige un accès réel au compte publicitaire. Le canari
   > ne couvre donc pas Meta — sans conséquence, Meta est de toute façon à l'arrêt (R13).
2. À blanc d'abord :
   ```bash
   make canary NAME="Canary 1x7" SPOTIFY=<artist id> YOUTUBE=<UC…> DRY_RUN=1
   ```
3. Puis pour de vrai, en retirant `DRY_RUN=1`. Ajoute `SOUNDCLOUD=<user id>` et
   `META=<account id>` si tu veux les couvrir aussi.

### Vérification

```bash
make artist-preflight
```
Il doit dépasser l'étape 1 et nommer précisément ce qui manque encore, au lieu de
s'arrêter sur « no canary tenant ».

---

## 3. ~~R18 — `.env` ligne 67~~ · ✅ FAIT le 2026-08-21

La ligne était `nom entreprise=BAUDRY Timothé` — une étiquette écrite sans `#`, que
Docker lisait comme une clé. Commentée. `check_env.py` affiche désormais **10/10** et
`make up` démarre.

Ce que sa correction a révélé vaut plus que la correction : lancer la suite contre la
**vraie** base locale, au lieu d'un Postgres jetable, a fait tomber 8 tests — dont un
défaut de DAG réel (`collect_spotify_top_tracks` ignorait `dag_run.conf`, donc un clic
per-tenant dépensait le quota Spotify de toute la flotte). Détail dans `archive.md`.

**Leçon à garder** : une base de test vide cache les défauts multi-locataires. La suite
doit tourner contre une base à **au moins deux locataires**.

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
