# ADR-024 — L'historique d'avant notre première collecte n'est récupérable que sur YouTube

- **Statut** : accepté
- **Date** : 2026-09-13
- **Déclencheur** : « j'ai fait des streams avant le 1er novembre 2025 avec soundcloud et
  youtube mais ça me les marque en cumulé de 0 à des dizaines de milliers directement,
  est-ce qu'on peut calculer via couche or le nombre de streams journaliers depuis le
  début de soundcloud ou ce sont des données inaccessibles ? »

## Le constat

Nos deux collecteurs de compteur ne demandent aujourd'hui qu'un **cumul à vie** :

| plateforme | appel | ce qu'on obtient |
|---|---|---|
| YouTube | Data API v3, `videos.list(part='statistics')` | `statistics.viewCount` — cumul depuis publication |
| SoundCloud | `GET /tracks/{id}` | `playback_count` — cumul à vie |

Ni l'un ni l'autre ne porte de date. Notre série commence donc à notre **première
collecte** — mesuré en production, artiste 1 : YouTube le **29/11/2025**, SoundCloud le
**16/12/2025** — et tout ce qui précède existe dans le compteur sans pouvoir être placé
sur un jour. D'où la falaise verticale en mode cumulé : la pile infère zéro avant la
première mesure, puis saute à 118 336.

**Ce n'est ni un défaut de nos KPI ni une donnée manquante côté API.** C'est la nature
d'un compteur : il dit COMBIEN, jamais QUAND.

## Décision

### YouTube — récupérable, et ce sera une brique

L'API **YouTube Analytics** (`youtubeAnalytics.reports.query`) rend les vues
**journalières** historiques : `dimensions=day`, métrique `views`, et même
`dimensions=day,video` pour le détail par vidéo. Aucune limite d'ancienneté documentée
sur `startDate`.

⚠️ **Ne pas confondre avec la YouTube _Reporting_ API**, dont les fichiers ne sont
conservés que 30 à 60 jours. C'est une API différente, et cette confusion est la source
de l'idée reçue « YouTube ne garde que 60 jours ».

Conditions, et elles ne sont pas gratuites :

- OAuth 2.0 en tant que **propriétaire de la chaîne** (scope
  `https://www.googleapis.com/auth/yt-analytics.readonly`, plus `youtube.readonly`).
  C'est un consentement PAR ARTISTE, pas une clé d'application — notre clé Data API v3
  actuelle ne suffit pas ;
- donc un geste humain par locataire, à ajouter au parcours d'onboarding.

Tracé en roadmap sous **R105**. Repli sans OAuth : export manuel depuis YouTube Studio →
Analytics → **Mode avancé** → « Exporter la vue actuelle » (CSV, **500 vidéos maximum**
par export).

### SoundCloud — inaccessible, et c'est définitif

**Aucune API publique ou partenaire ne donne l'historique journalier.** Les issues #68 et
#180 du dépôt officiel `soundcloud/api` le réclament depuis des années sans réponse.
L'inscription libre à l'API est fermée ; l'accès se fait par formulaire, au cas par cas.

Et **il n'y a pas d'export CSV** : la page d'aide « Exporting Insights » de SoundCloud
dit explicitement qu'Insights n'offre qu'une vue graphique, sans téléchargement.

**Conséquence assumée** : pour SoundCloud, `23 564` restera un total à vie dont la part
antérieure au 16/12/2025 ne sera jamais datable. La figure ne peut pas la dessiner, et
l'inventer — en l'étalant uniformément, par exemple — produirait une histoire que
l'artiste lirait comme vraie. On ne le fera pas.

## Ce qui est fait en attendant

1. La boîte KPI porte le total à vie **et** dit en infobulle depuis quelle date nous
   relevons, avec ce que nous avons vu croître depuis. Les deux nombres sont justes et
   répondent à deux questions ; c'est leur écart qui faisait dire « nos KPI sont faux ».
2. La note sous la figure nomme la date de première mesure par plateforme — et depuis le
   2026-09-13 elle en donne **une seule**, lue dans les niveaux : elle en donnait deux
   selon le pas (SoundCloud « 31/03/2026 » au jour, « décembre 2025 » au mois), parce que
   la série quotidienne d'un compteur est une différence entre relevés CONSÉCUTIFS et ne
   peut pas commencer avant le deuxième.

## Ce qui rouvrirait la question SoundCloud

Un endpoint de statistiques par date dans l'API SoundCloud, ou un export CSV depuis
Insights. À revérifier à la source avant toute démarche : l'information sur la fermeture
des inscriptions date de 2019-2023.
