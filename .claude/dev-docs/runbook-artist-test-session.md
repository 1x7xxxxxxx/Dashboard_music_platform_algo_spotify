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

## Pendant la session

- L'artiste s'inscrit et suit l'onboarding (sélection à cocher, Spotify + Instagram
  recommandés). Les guides s'adaptent à son OS — il y a une bascule 💻/🍎 en haut.
- Après chaque connexion, **cliquer « Tester la connexion »**. Un ✅ prouve
  désormais que *ses* données arrivent, pas seulement que l'app de la plateforme
  répond. Un ❌ nomme le geste suivant.
- La collecte se déclenche depuis la barre latérale ; elle est scopée sur son
  compte. Les données arrivent en ~2 min.
- En cas de doute sur ce qu'il voit : `make artist-preflight ARTIST=<son id>`.

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
