# ADR-013 — Un artiste a N comptes publicitaires Meta, mais un seul profil par plateforme

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** @timothe

## Context

Deux questions sont arrivées ensemble, et elles se ressemblent assez pour qu'on
les traite pareil. C'est le piège.

**La première** vient d'un cas réel : un artiste passant par une agence a
plusieurs comptes publicitaires Meta. Le formulaire n'en acceptait qu'un, et les
dix tables d'insights à la maille campagne étaient uniques sur `campaign_name`
sans discriminant de compte — deux comptes ayant une campagne « Release FR »,
le nom le plus banal qui soit, écrivaient **la même ligne**.

**La seconde** est venue en réaction : *faut-il faire pareil pour Spotify,
YouTube, SoundCloud — et choisir le profil avant l'export PDF ?* La forme de la
question est identique : « plusieurs identités sous un seul compte payant ».

## Decision

**Meta est plural, les profils d'artiste ne le sont pas** : N comptes
publicitaires sous une seule ligne de credentials, affichés **séparément** ; et
**un locataire = un profil** sur Spotify, YouTube, SoundCloud et Instagram.

### Ce qui rend Meta différent, et ce n'est pas une question de volume

| | Meta — N comptes publicitaires | Spotify/YouTube/SoundCloud — N profils |
|---|---|---|
| Ce qui est pluriel | l'identité du **payeur** | l'identité **artistique** |
| Le cumul veut dire quelque chose ? | oui — « ce qu'a coûté cette sortie » | non — additionner les streams de deux alias ne décrit personne |
| La credential | **une seule** (token System User partagé, ADR-006) | une par profil |
| Portée du changement | 13 tables, 1 colonne | la dimension de scoping de 93 tables |

Le cas Meta est une **identité de compte** qui se multiplie sous une credential
unique. Le cas Spotify est une **identité d'artiste** qui se multiplie : chaque
KPI, chaque score ML, chaque déclenchement d'algorithme et chaque PDF de ce dépôt
est construit autour d'un artiste et d'un seul.

### Structurellement, un profil de plus est déjà un locataire de plus

`saas_artists` n'a pas de colonne propriétaire : une connexion = une ligne, et
`tenant_scope()` rend cet identifiant partout. Un deuxième profil Spotify sous le
même locataire voudrait dire ajouter une **seconde dimension de scoping** à
chaque requête du dépôt. Le mécanisme qui répond déjà au besoin existe : un
deuxième projet artistique est un deuxième compte. Ce qui manque, le jour où
quelqu'un le demandera vraiment, c'est qu'**une même connexion puisse posséder
plusieurs locataires et basculer entre eux** — c'est une brique de comptes, pas
une brique de données, et elle ne touche aucune table métier.

### Le sélecteur avant l'export PDF

Il est livré, avec la portée qui a un sens : **le compte publicitaire**. Le
formulaire d'export affiche un sélecteur « Compte publicitaire » dès que le
locataire en déclare deux ou plus, et les cinq sections publicitaires du rapport
s'y restreignent. Le PDF est un document qu'on envoie à un tiers : un CPR qui
mélange les budgets de deux annonceurs distincts n'est le CPR d'aucun des deux, et
le lecteur n'a aucun moyen de s'en apercevoir.

Côté artiste, il n'y a rien à choisir sur le profil : le rapport porte sur le
locataire connecté. Le sélecteur d'artiste du formulaire reste **réservé à
l'admin**, comme avant.

## Consequences

### Positive
- Deux comptes ne s'écrasent plus. La clé d'unicité des dix tables à la maille
  campagne inclut `ad_account_id` (migration 077), et le `DELETE` de
  `_prune_renamed_campaigns` porte le même discriminant que ce qu'il vient
  d'écrire — sans quoi la passe du second compte effaçait le travail du premier.
- **Zéro changement pour les locataires mono-compte**, qui sont 100 % de la
  flotte aujourd'hui : le sélecteur ne s'affiche pas en dessous de deux comptes,
  et `account_clause(None)` rend la requête d'avant, à l'identique.
- Le test de connexion sonde **tous** les comptes déclarés. Un vert qui ne
  prouvait qu'un compte sur trois serait exactement le cas Benken (partage
  d'asset manquant, découvert un jour plus tard, à la collecte).
- Une panne sur un compte n'emporte pas les autres : tous sont parcourus, puis
  l'exception est levée avec la liste — la tâche reste rouge (règle transverse
  #6) et les données déjà écrites le restent.

### Negative / Trade-offs
- `account_ids` (liste canonique) et `account_id` (son premier élément) sont un
  **miroir**, et ce dépôt documente ailleurs qu'un miroir dont un seul écrivain a
  connaissance est la façon dont le canari est passé au vert sur rien. Assumé
  ici : l'écrivain est unique (`with_meta_accounts`), le lecteur aussi
  (`meta_ad_account_ids`), et `tests/test_meta_multi_account.py` garde la
  correspondance. L'alternative — `UNIQUE(artist_id, platform, account)` — aurait
  dupliqué le token partagé autant de fois que de comptes, pour une valeur
  identique, et cassé les six lecteurs qui supposent une ligne par plateforme.
- Les clés d'unicité utilisent `NULLS NOT DISTINCT` (PostgreSQL 15+). Sans cela,
  l'historique resté à `NULL` aurait cessé d'être dédupliqué et chaque nuit y
  aurait AJOUTÉ un doublon : la contrainte serait passée verte en produisant
  exactement le défaut qu'elle empêche.
- Un artiste réellement multi-projets doit ouvrir deux comptes et payer deux
  fois. C'est le prix assumé de ne pas ajouter une dimension de scoping partout.

### Neutral / Operational
- Le backfill de la migration 077 ne rattache l'historique au compte courant que
  pour les locataires déclarant **exactement un** compte. C'est correct tant que
  ce compte est le seul qui ait jamais collecté — vrai de toute la flotte
  aujourd'hui, faux dès la première agence. C'était donc le dernier moment où ce
  rattachement était vrai plutôt que deviné.
- La revendication d'un compte publicitaire est vérifiée sur **la liste entière**,
  pas sur le seul scalaire : sinon le deuxième compte d'un artiste n'apparaît dans
  le scalaire de personne, et un autre locataire peut le revendiquer comme son
  premier.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Comptes Meta **fusionnés** (un total unique) | Chaque compte a son budget, son CPR et ses campagnes ; un total les mélange sans le dire. Tranché par l'auteur des notes de test. |
| `UNIQUE(artist_id, platform, account_id)` sur `artist_credentials` | Duplique le token System User partagé (valeur identique) autant de fois que de comptes, et casse les six lecteurs qui supposent une ligne par plateforme. |
| Multi-profils Spotify/YouTube/SoundCloud sous un locataire | Ajoute une seconde dimension de scoping à 93 tables et à chaque vue, pour un besoin que « un profil = un locataire » couvre déjà. |
| Sélecteur de **profil d'artiste** avant l'export PDF côté locataire | Il n'y a qu'un profil par locataire — le sélecteur n'aurait qu'une option. Le choix qui existe vraiment est celui du compte publicitaire, et c'est lui qui est livré. |
| Livrer l'interface multi-comptes avant la migration des clés | Produirait des données silencieusement fausses : deux campagnes homonymes sur la même ligne. D'où l'ordre schéma → collecteur → clés → interface. |
