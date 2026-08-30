# Runbook — inviter un artiste à tester l'app

Deux sessions, deux échecs, la même heure perdue. Ce runbook existe pour que la
troisième se passe autrement. **La règle tient en une ligne : on n'invite personne
tant que `make artist-preflight` n'est pas vert.**

## Avant la session (5 minutes, la veille)

```bash
make artist-preflight PROD_SSH=root@167.233.92.1
```

Cinq étapes, arrêt au premier rouge :

| # | Étape | Ce qu'elle attrape |
|---|---|---|
| 1 | Apps centrales présentes **et** authentifiées (`--require`) | « toutes les credentials ont échoué » — token Meta expiré, variable absente du conteneur |
| 2 | Le locataire a déclaré ses propres identifiants | un compte qui n'a jamais rien connecté |
| 3 | Tests de connexion des 4 plateformes | un identifiant saisi mais faux, un compte pub non partagé |
| 4 | Des données sont réellement arrivées | le silence : DAG vert, zéro ligne |
| 5 | Aucune ligne d'un autre locataire sous ce compte | « les datas étaient celles de l'admin » |

Le préflight vise par défaut le **locataire canari** : un vrai compte non-admin,
avec **tes** identifiants publics mais **différents de ceux de l'admin**. C'est ce
choix qui donne sa valeur à l'étape 5 — si le canari voit les données de l'admin,
le rouge est mécanique, pas interprétatif.

Créer le canari une fois :

```sql
-- après l'avoir inscrit normalement via le funnel, avec SES identifiants
UPDATE saas_artists SET is_canary = TRUE WHERE id = <id>;
```

Pour vérifier un artiste précis plutôt que le canari :
`make artist-preflight ARTIST=12`.

## Si une étape est rouge

Le préflight nomme le geste. Les correspondances les plus fréquentes :

- **Étape 1 rouge** → variable d'env absente du conteneur (`tools/prod_introspect.sh`
  liste SET/MISSING par conteneur), ou token expiré → R13 pour Meta.
- **Étape 3 rouge sur Meta** → compte publicitaire non partagé avec le Business
  Manager (asset sharing) — le message le dit.
- **Étape 4 rouge (🔴 connecté, aucune donnée)** → l'identité est bonne mais la
  collecte ne ramène rien : chaîne YouTube vide (chercher la chaîne « … - Topic »),
  profil SoundCloud sans titre public.
- **Étape 5 rouge** → `make tenant-check` pour le détail, sauvegarde
  (`tools/db_backup.sh`), puis nettoyage délibéré. **Ne jamais inviter quelqu'un
  avec une étape 5 rouge** : il verra les données de quelqu'un d'autre.

## Pendant la session — le parcours complet, pas à pas

Chaque étape a **ce qu'il fait**, **ce que tu dois voir**, et **la commande qui le
prouve**. Une étape sans preuve est une étape qu'on croit faite.

### Étape 0 — voir l'app par ses yeux, avant qu'il arrive

```bash
make artist-firstlook          # locataire jetable, créé puis supprimé
```

Imprime ce qui est à l'écran sur les 6 pages du début : titres, boutons, messages.
Différent du render-smoke, qui n'asserte que « ça ne plante pas » — et qui était vert
pendant les deux séances ratées. Les ~30 notes de terrain ne décrivaient jamais un
crash, mais du **code correct que rien n'atteignait**.

### Étape 1 — l'inscription

| | |
|---|---|
| Il fait | `app.streamlytics.fr` → « Créez-en un » → nom d'artiste, e-mail, mot de passe, CGU |
| Tu vois | « Compte créé. Cliquez sur le lien dans l'email pour activer votre compte. » |
| Preuve | `SELECT id, username, email_verified FROM saas_users ORDER BY id DESC LIMIT 1;` → la ligne existe, `email_verified = f` |

⚠️ **`email` et `username` sont UNIQUE.** Pour enchaîner plusieurs essais, utilise des
alias Gmail : `ton.adresse+artiste1@gmail.com` — vérifié, le regex de validation les
accepte, et tout arrive dans la même boîte. Budget : **8 inscriptions / 10 min par IP**.

### Étape 2 — l'e-mail de vérification

| | |
|---|---|
| Il reçoit | un e-mail avec un lien `?page=verify&uid=…&token=…`, **valable 48 h** |
| ⚠️ | si le sujet porte le préfixe `[LOCAL]`, l'e-mail vient d'une instance locale, pas de la prod |
| Preuve | `SELECT verification_token IS NOT NULL FROM saas_users WHERE id = <id>;` |

### Étape 3 — la vérification, et les DEUX e-mails qui suivent

| | |
|---|---|
| Il fait | clique le lien |
| Tu vois | « ✅ Email vérifié ! » **puis** un second e-mail : le mot de bienvenue **avec le guide PDF en pièce jointe** |
| Pourquoi après | le guide ne part qu'une fois l'adresse prouvée délivrable |
| Preuve | `email_verified = t`, et la pièce jointe est bien présente dans l'e-mail reçu |

Si le PDF manque : il reste téléchargeable dans l'app (page **Guide de démarrage** et
première étape de l'onboarding) — c'était R50, un document qui n'existait qu'en pièce
jointe est un document qu'on perd.

### Étape 4 — les plateformes externes, qui fait quoi

C'est l'étape qui a coûté les deux séances. **Le modèle est celui d'une app centrale**
(ADR-006) : les clés d'application sont les tiennes, l'artiste ne fournit que **son
identité**. Sauf deux exceptions, ci-dessous.

| Plateforme | Ce que l'ARTISTE fait | Ce que TOI tu dois avoir fait avant |
|---|---|---|
| **🎵 Spotify** | ouvre sa page artiste → **⋯ → Partager → Copier le lien** → colle l'URL | app `client_credentials` créée, `SPOTIFY_CLIENT_ID/SECRET` dans le conteneur |
| **☁️ SoundCloud** | ouvre `soundcloud.com/discover`, **affiche le code source**, cherche `soundcloud:users:` → colle le nombre | OAuth `refresh_token` frappé (runbook SoundCloud) |
| **📱 Meta Ads** | ouvre `adsmanager.facebook.com`, lit `act=…` dans **l'URL** → colle le nombre | System User + token 5 scopes |
| **📱 Instagram** *(optionnel)* | l'**ID du compte Instagram Business** — le compte doit être en **Business/Créateur** et relié à une **Page Facebook** | idem Meta |
| **🎬 YouTube** | crée une **clé API** sur Google Cloud Console (7 étapes) + relève son **Channel ID** | — |

**⚠️ L'étape qui manque dans l'app, et qui a bloqué Benken.** Pour Meta, coller l'ID du
compte publicitaire **ne suffit pas** : ton token System User ne peut pas le lire tant
que l'artiste n'a pas **partagé ce compte avec ton Business Manager** (Business Manager
→ Paramètres → Comptes publicitaires → *Attribuer un partenaire*). `token-management-bilan.md`
écrit « the artist does nothing » — c'est vrai pour le **token**, faux pour le **partage**.
Le guide dans l'app ne le dit nulle part. **Dis-le à l'artiste de vive voix**, jusqu'à ce
que ce soit corrigé.

**⚠️ Deux gestes de développeur.** YouTube (créer une clé API Google Cloud) et SoundCloud
(afficher le code source d'une page) ne sont pas des gestes d'artiste. Attends-toi à les
faire **avec lui**, en partage d'écran. Note son hésitation : c'est une donnée produit.

### Étape 5 — après chaque connexion, le verdict est immédiat

| | |
|---|---|
| Il fait | **💾 Enregistrer** sur une plateforme |
| Tu vois | « Vérification de la connexion… » puis le verdict **dans sa matrice** *Configuré / Répond / Données* — sur l'accueil, l'onboarding et la page Credentials |
| Avant le 2026-08-30 | rien : il fallait attendre 23 h, ou savoir qu'un bouton « 🔌 Vérifier maintenant » existait |
| Preuve | `SELECT platform, ok, reason, probed_at FROM tenant_platform_probe WHERE artist_id = <id>;` |

Un ✅ prouve que **ses** données arrivent, pas seulement que l'API répond.

### Étape 6 — la première collecte

| | |
|---|---|
| Il fait | l'enregistrement déclenche la collecte ; sinon, barre latérale → synchroniser |
| Tu vois | « 🚀 Collecte lancée — données disponibles dans ~2 min » |
| Preuve | `make artist-preflight ARTIST=<son id>` → étape 4 verte, ou `SELECT platform, status, rows_written FROM etl_run_log WHERE artist_id = <id> ORDER BY started_at DESC LIMIT 5;` |

### Étape 7 — le contrôle qu'aucune sonde ne peut faire

```bash
make artist-preflight ARTIST=<son id>    # les 5 étapes, sur SON compte
make tenant-check                        # rien n'a contaminé un autre locataire
```



Les guides s'adaptent à son OS — bascule 💻/🍎 en haut de page.

## Après la session

- `make tenant-check` — rien ne doit avoir contaminé un autre locataire.
- Noter ce qui a bloqué. Si c'est une classe (pas un incident isolé) :
  `.claude/dev-docs/error-classes.md` avec une signature vue rouge.

## Pourquoi ce runbook plutôt qu'une préproduction

Les deux échecs venaient de la production elle-même : une variable d'environnement
manquante et un jeu de règles de repli dans le code. Une préproduction n'aurait
montré ni l'une ni l'autre. Le couple **E2E deux-locataires en CI**
(`tests/test_e2e_two_tenants.py`, à chaque commit) + **canari en prod**
(`make artist-preflight`, avant chaque session) couvre les deux, pour un coût
sans commune mesure.
