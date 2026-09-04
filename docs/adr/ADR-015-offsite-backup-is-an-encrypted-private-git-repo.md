# ADR-015 — La copie hors-site est un dépôt git privé chiffré, pas un bucket

- **Date** : 2026-09-04
- **Statut** : Accepté
- **Remplace partiellement** : le plan R57 (« créer un bucket Cloudflare R2 »), qui reste
  la cible préférée et le chemin de code par défaut.

## Contexte

Mesuré sur la production le 2026-09-03, puis reconfirmé le 2026-09-04 :

| Fait | Valeur |
|---|---|
| Archives quotidiennes | 21, toutes sous `/opt/streamlytics/backups` |
| Le disque qui les porte | `/dev/sda1` — **celui de la base qu'elles sauvegardent** |
| `crontab -l` | ni `rsync`, ni `s3`, ni `rclone` |
| Taille d'une archive | 1,89 Mo gzippée (croissante, +5,6 %/jour de lignes) |

Une sauvegarde qui meurt avec ce qu'elle protège est une copie. Le code de la copie
hors-site était écrit depuis le 2026-09-04 matin et attendait **une seule chose** :
un bucket. Or créer le bucket n'était pas un travail d'ingénierie, c'était un geste
humain — et il ne s'est pas produit.

## Ce qui bloquait vraiment

**Tous les stockages objet à palier gratuit exigent une carte bancaire pour activer le
service**, y compris quand le palier est ensuite à 0 € : Cloudflare R2, Backblaze B2,
Scaleway, Wasabi, Storj. Aucune API ne permet d'amorcer cette étape ; il n'existe pas
de jeton avant le compte, et pas de compte avant le moyen de paiement.

Vérifié aussi sur la machine : **aucun jeton Cloudflare** n'existe nulle part (ni dans
`/opt/streamlytics/.env`, ni dans les conteneurs — Caddy utilise le challenge HTTP), et
**aucune seconde machine** n'est joignable (`known_hosts` et `ssh_config` n'en portent
qu'une). Le repli « pousser vers un autre serveur » n'existait pas non plus.

Reste ce qui était déjà là : un compte GitHub, un jeton fonctionnel, `git` et `gpg` sur
l'hôte. C'est le seul stockage distant configurable **sans aucun geste humain**.

## Décision

La copie hors-site part vers un **dépôt GitHub privé dédié**
(`streamlytics-db-backups`), et :

1. **L'archive est chiffrée avant de partir** — `gpg --symmetric --cipher-algo AES256`,
   phrase de passe de 44 caractères. Ce qui rend la cible acceptable n'est pas que le
   dépôt soit privé, c'est que les octets soient opaques avant de bouger. Un dépôt
   privé est une permission ; un chiffrement est une propriété.
2. **L'accès est une clé de déploiement en écriture, limitée à ce seul dépôt.** Pas de
   PAT sur le serveur : une clé volée sur la machine ne donne accès ni au code, ni au
   compte, seulement au dépôt de sauvegardes — dont le contenu est chiffré.
3. **L'historique est réécrit chaque nuit** (commit orphelin + `push --force`). Le dépôt
   porte la fenêtre de rétention (30 jours ≈ 57 Mo) et jamais l'accumulation ; git
   n'envoie que le blob de la nuit, ~1,9 Mo.
4. **La phrase de passe vit à deux endroits**, sur le serveur et sur la machine de
   l'auteur (`~/streamlytics-backup-passphrase.txt`). Une sauvegarde qu'on ne sait plus
   déchiffrer n'est pas une sauvegarde : la clé ne doit pas partager le sort de ce
   qu'elle ouvre, exactement comme l'archive.
5. **Le drill hebdomadaire restaure l'archive CHIFFRÉE**, pas la claire. Le maillon
   faible du dispositif n'est pas le `pg_dump`, c'est la phrase de passe ; restaurer la
   copie claire laisserait la seule question qui compte sans réponse.

`R2_REMOTE` reste prioritaire dans `tools/db_backup.sh` : le jour où le bucket existe,
poser la variable suffit, et le chemin git s'éteint de lui-même sans rien réécrire.

## Le défaut que cette décision a fait apparaître

En câblant la vérification, on a mesuré que **le conteneur `airflow_scheduler` n'a ni
`rclone` ni `git`**. `check_offsite_backup` appelait `subprocess.run(['rclone', ...])` :
il aurait répondu `unreadable` **toutes les nuits, y compris une fois R2 correctement
configuré sur l'hôte**. Un contrôle qui appelle un binaire absent de sa propre image ne
devient jamais vert.

Classe d'erreur : `check-calls-a-binary-its-image-lacks`. Balayage du dépôt le
2026-09-04 : c'était le **seul** site dans les 12 DAGs.

Le contrôle lit désormais un **reçu** (`data/offsite_receipt.json`) que le script d'hôte
n'écrit qu'**après avoir relu le distant** — `rclone lsf` pour R2, comparaison des SHA
local/distant pour git. Le reçu atteste une présence, jamais une intention, et le
contrat est le même pour les deux cibles.

## Alternatives écartées

| Option | Pourquoi non |
|---|---|
| **Cloudflare R2** | Meilleure cible techniquement (egress 0 $, rétention native). Exige une carte bancaire pour activer R2. **Différée, pas rejetée** — le code l'attend. |
| Backblaze B2 / Scaleway / Wasabi / Storj | Même blocage : palier gratuit, carte obligatoire. |
| Second serveur / Storage Box Hetzner | Payant, et aucune seconde machine n'existe. |
| Tirer les archives sur le PC de l'auteur | Gratuit, mais le PC est derrière un NAT et éteint la plupart du temps : la fraîcheur dépendrait de sa présence. Reste un bon **troisième** exemplaire, pas le premier. |
| `git` sans chiffrement | Non. Les dumps portent des adresses e-mail, des mots de passe hachés et les données de chaque locataire. |
| Releases GitHub plutôt qu'une branche | Les assets se suppriment proprement, mais l'API exige un PAT sur le serveur ; la clé de déploiement, elle, ne donne rien d'autre. |

## Ce qui rouvre cette décision

- Une carte est posée sur un compte Cloudflare → créer le bucket, poser `R2_REMOTE`,
  recréer le scheduler. Le chemin git s'éteint sans modification de code.
- L'archive dépasse **~50 Mo** par nuit (aujourd'hui 1,89 Mo) : le force-push d'un arbre
  complet cesse d'être gratuit, et GitHub cesse d'être un hôte raisonnable.
- Une seconde machine apparaît dans le parc → `rclone sftp` la rend préférable aux deux.

## Conséquences

- La perte du disque `/dev/sda1` ne détruit plus les sauvegardes.
- Un tiers (GitHub) détient des octets chiffrés ; il ne détient pas de données lisibles.
- Le contrôle nocturne peut enfin passer au vert — ce qu'il ne pouvait structurellement
  pas faire avant, quelle que soit la cible.
