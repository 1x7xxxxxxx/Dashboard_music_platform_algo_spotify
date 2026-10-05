# YouTube Analytics API — inventaire pour le propriétaire (R394)

> **Ce document décide de rien.** Il liste ce que la YouTube Analytics API (v2,
> `reports.query`) et la YouTube Reporting API (bulk) exposent pour la chaîne d'un
> artiste, ce que chaque donnée permettrait d'afficher, et le geste de branchement.
> **Le propriétaire choisit ce qui entre en roadmap.** Aucune collecte n'est écrite.
>
> Aujourd'hui (2026-10-05), streaMLytics ne lit que la **Data API v3** : statistiques de
> chaîne et, par vidéo, vues / likes / commentaires — des **instantanés cumulés**, pas
> des séries. C'est pourquoi les abonnés gagnés PAR VIDÉO (V40, V41) n'existent pas dans
> l'app : la Data API ne les donne pas, l'Analytics API oui.
>
> Recherche du 2026-10-05, sources **officielles uniquement** (`developers.google.com`).
> « non documenté » = absent des pages officielles lues ; rien n'a été comblé de mémoire.

Pages de référence :
[métriques](https://developers.google.com/youtube/analytics/metrics) ·
[dimensions](https://developers.google.com/youtube/analytics/dimensions) ·
[rapports de chaîne](https://developers.google.com/youtube/analytics/channel_reports) ·
[modèle de données](https://developers.google.com/youtube/analytics/data_model) ·
[`reports.query`](https://developers.google.com/youtube/analytics/reference/reports/query) ·
[exemples](https://developers.google.com/youtube/analytics/sample-requests) ·
[révisions](https://developers.google.com/youtube/analytics/revision_history)

Les ancres exactes de chaque métrique n'ont pas été vérifiées : la colonne « doc »
renvoie à la page et au tableau où la métrique est définie.

## 1. Scopes OAuth

| Scope | Ce qu'il débloque |
|---|---|
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Activité : vues, durée de visionnage, engagement, abonnés, géographie, sources de trafic, appareils, démographie, rétention (`reports.query` et Reporting API) |
| `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` | Revenus et performance publicitaire (`reports.query` et Reporting API) |
| `https://www.googleapis.com/auth/youtube.readonly` | Lecture du compte ; [`reports.query`](https://developers.google.com/youtube/analytics/reference/reports/query) dit que ses requêtes « require access to the `youtube.readonly` scope » (changement du 2018-06-18) |

Les trois sont à demander ; le monétaire seulement pour les revenus. Flux « device » et
compte de service : **non supportés**
([guide d'autorisation](https://developers.google.com/youtube/reporting/guides/authorization)).

## 2. Métriques

« Par vidéo » = filtre `video==ID` ou dimension `video` ; « par chaîne » = `ids=channel==MINE`
sans filtre vidéo.

| Nom API | Ce qu'elle mesure | Vidéo | Chaîne | Ce qu'on pourrait afficher | Doc |
|---|---|---|---|---|---|
| `views` | Lectures. Depuis le 2025-04-24, un Short compte à chaque démarrage/relecture | ✅ | ✅ | **Vraie série quotidienne** au lieu des instantanés | [metrics § View](https://developers.google.com/youtube/analytics/metrics) |
| `engagedViews` | Vues au-delà de la première image (ancien comptage des Shorts) | ✅ | ✅ | Vues « réelles » vs vues Shorts brutes | idem |
| `estimatedMinutesWatched` | Minutes visionnées | ✅ | ✅ | Temps d'écoute par jour | [metrics § Watch time](https://developers.google.com/youtube/analytics/metrics) |
| `averageViewDuration` | Durée moyenne d'une lecture (s), boucles exclues depuis 2021-12-13 | ✅ | ✅ | Durée moyenne par titre | idem |
| `averageViewPercentage` | % moyen de la vidéo regardé | ✅ | ✅ | « On écoute X % du clip » | idem — incompatible avec `liveOrOnDemand` |
| `subscribersGained` | Abonnements | ✅ | ✅ | **Abonnés gagnés par jour et par titre (V40, V41)** | [metrics § Engagement](https://developers.google.com/youtube/analytics/metrics) |
| `subscribersLost` | Désabonnements | ✅ | ✅ | Solde net d'abonnés | idem |
| `likes` / `comments` | J'aime / commentaires | ✅ | ✅ | Séries quotidiennes (aujourd'hui : cumuls) | idem |
| `dislikes` | Pouces vers le bas (listé) | ✅ | ✅ | Disponibilité réelle non confirmée | idem |
| `shares` | Partages via le bouton Partager | ✅ | ✅ | Partages, par service avec `sharingService` | idem |
| `videosAddedToPlaylists` / `videosRemovedFromPlaylists` | Ajouts / retraits de playlists YouTube (depuis 2014-10-01) | ✅ | ✅ | Signal de « sauvegarde », solde net | idem |
| `annotation*` (7 métriques) | Annotations (fonctionnalité retirée) | ✅ | ✅ | Peu de valeur | [metrics § Annotation](https://developers.google.com/youtube/analytics/metrics) |
| `cardImpressions`, `cardClicks`, `cardClickRate`, `cardTeaser*` | Cartes (liens dans la vidéo) | ✅ | ✅ | Clics vers billetterie / boutique | [metrics § Card](https://developers.google.com/youtube/analytics/metrics) |
| `playlistViews`, `playlistEstimatedMinutesWatched`, `playlistAverageViewDuration`, `playlistSaves`, `playlistStarts`, `viewsPerPlaylistStart`, `averageTimeInPlaylist` | Playlists (les trois derniers : web seulement ; `playlistSaves` est un net) | ❌ | playlist | Performance d'un album / d'une playlist officielle | [metrics § Playlist](https://developers.google.com/youtube/analytics/metrics) — filtre `playlist` ou `group` obligatoire |
| `estimatedRevenue` / `estimatedAdRevenue` | Revenu net estimé, total / publicitaire ; ajusté en fin de mois | ✅ | ✅ | Revenu YouTube (si YPP) — voir C1 | [metrics § Estimated Revenue](https://developers.google.com/youtube/analytics/metrics) |
| `cpm` / `playbackBasedCpm` | Revenu brut / 1 000 impressions pub / 1 000 lectures | ✅ | ✅ | idem | [metrics § Ad Performance](https://developers.google.com/youtube/analytics/metrics) |
| `monetizedPlaybacks` | Lectures avec ≥ 1 pub (±2 %) | ✅ | ✅ | idem | idem |
| `audienceWatchRatio` | Part des spectateurs à chaque point de la vidéo (> 1 en cas de relecture) | 1 vidéo | ❌ | **Courbe de rétention** : où l'on décroche | [metrics § Audience Retention](https://developers.google.com/youtube/analytics/metrics) |
| `relativeRetentionPerformance` | Rétention vs vidéos YouTube de durée similaire (0-1) | 1 vidéo | ❌ | Score de rétention vs référence | idem |

Autres métriques de rétention par segment : `startedWatching`, `stoppedWatching`,
`totalSegmentImpressions`.

## 3. Dimensions

Restrictions : [rapports de chaîne](https://developers.google.com/youtube/analytics/channel_reports)
et [dimensions](https://developers.google.com/youtube/analytics/dimensions).

| Dimension | Se combine avec | Restrictions documentées |
|---|---|---|
| `day`, `month` | presque toutes les métriques de base | une seule des deux ; `month` exige des dates au 1er du mois |
| `video` | rapports « Top videos » | `maxResults` ≤ 200, `sort` obligatoire ; vidéos supprimées absentes des ventilations |
| `playlist` | métriques de playlist | filtre `playlist` ou `group` obligatoire |
| `country` | « User geography » + métriques de base | ISO-3166-1 alpha-2 |
| `province` | idem | États-Unis seulement (`country==US`) |
| `city` | idem | `maxResults` ≤ 250, `sort` obligatoire ; données depuis 2022-01-01 |
| `insightTrafficSourceType` | vues, durées | erreur si vidéos × jours > 50 000 ; `YT_SEARCH`, `RELATED_VIDEO`, `SUBSCRIBER`, `SHORTS`, `SOUND_PAGE`, `EXT_URL`, `PLAYLIST`, `ADVERTISING`… |
| `insightTrafficSourceDetail` | idem | 25 résultats max, `sort` obligatoire, filtre sur un type de source ; non pris en charge pour `VIDEO_REMIXES`, `NOTIFICATION`, `END_SCREEN`, `CAMPAIGN_CARD`, `NO_LINK_EMBEDDED` |
| `deviceType` | vues, durées | `DESKTOP`, `MOBILE`, `TABLET`, `TV`, `GAME_CONSOLE`, `AUTOMOTIVE`, `WEARABLE`, `UNKNOWN_PLATFORM` |
| `operatingSystem` | idem | 20+ valeurs, combinable avec `deviceType` |
| `ageGroup`, `gender` | `viewerPercentage` seulement | utilisateurs connectés ; non normalisé entre combinaisons ; **soumis à seuils** (§4) |
| `sharingService` | `shares` seulement | 100+ services |
| `subscribedStatus` | métriques d'activité | `SUBSCRIBED` / `UNSUBSCRIBED` |
| `youtubeProduct` | « Top videos by YouTube product » | `CORE`, `GAMING`, `KIDS`, `MUSIC`, `UNKNOWN` ; depuis 2015-07-18 |
| `elapsedVideoTimeRatio` | métriques de rétention | 100 points 0,01 → 1,0 ; filtre `video` obligatoire, **un seul ID** |
| `liveOrOnDemand` | « Playback details » | exclusif avec `averageViewPercentage` ; depuis 2014-04-01 |
| `creatorContentType` | rapports vidéo de chaîne | `VIDEO_ON_DEMAND`, `SHORTS`, `LIVE_STREAM`, `STORY`, `UNSPECIFIED` ; depuis 2019-01-01 |

Non demandée mais utile pour la musique : `insightPlaybackLocationType` (page de
visionnage, intégré…).

## 4. Quotas et limites

- **Quota** : « The API server evaluates each query to determine its quota cost. » Le
  quota quotidien par défaut de l'Analytics API **n'a pas été trouvé** dans les pages
  lues. Les 10 000 unités/jour sont ceux de la **Data API v3** — ne pas les appliquer ici.
  Voir C2.
- **Fraîcheur** : « latency of 48 to 72 hours » ; les réponses s'arrêtent au dernier
  jour complet traité ([data_model](https://developers.google.com/youtube/analytics/data_model)).
- **Historique** : aucune fenêtre documentée pour `reports.query`, seulement des dates de
  début par dimension (ci-dessus).
- **Seuils** : « Some YouTube Analytics data is limited when metrics do not meet a certain
  threshold. » Valeurs non publiées. Touchent la démographie, la géographie (pas les
  revenus) et le détail des sources de trafic. **Pour un petit artiste, l'âge et le
  genre peuvent revenir vides** — c'est la donnée, pas une panne.
- **Objets supprimés** : présents dans les agrégats, absents des ventilations — un total
  peut dépasser la somme de ses lignes.

## 5. Reporting API (bulk)

[Référence](https://developers.google.com/youtube/reporting/v1/reports).

- Rapports CSV prédéfinis, téléchargés une fois puis interrogés localement — pas de
  problème de quota. Un rapport = 24 h (heure du Pacifique), livré quotidiennement.
- Plus fin que `reports.query` : `channel_reach_basic_a1` donne les **impressions de
  miniature et leur CTR** (`video_thumbnail_impressions`, `video_thumbnail_impressions_ctr`).
- Branchement : `reportTypes.list()` → `jobs.create(reportTypeId, name)` → premiers
  rapports **sous 48 h**.
- Rétention : 60 jours (standard), 30 jours (historiques, couvrant 30 jours avant le job).
- [Types de chaîne](https://developers.google.com/youtube/reporting/v1/reports/channel_reports) :
  `channel_basic_a3`, `channel_province_a3`, `channel_combined_a3`,
  `channel_playback_location_a3`, `channel_traffic_source_a3`, `channel_device_os_a3`,
  `channel_demographics_a1`, `channel_sharing_service_a2`, `channel_cards_a1`,
  `channel_end_screens_a2`, `channel_subtitles_a3`, `channel_reach_basic_a1`,
  `channel_reach_combined_a1`, `playlist_*_a2`. Aucun rapport de revenus côté chaîne.

## 6. Le geste de branchement

1. **Projet Google Cloud** : activer « YouTube Analytics API » (et « YouTube Reporting
   API » si §5), dans le projet qui porte déjà les identifiants OAuth YouTube. À
   confirmer dans la console — la page lue ne détaille pas l'étape.
2. **Écran de consentement + vérification** : des scopes sensibles exigent une
   vérification Google avant publication — justification de chaque scope, politique de
   confidentialité sur le domaine, domaine vérifié dans Search Console, scopes déclarés
   dans « Data Access », **vidéo de démonstration** du consentement. Délai typique 3-5
   jours ouvrés ([vérification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)).
   En mode « Testing », nombre d'utilisateurs et durée de vie du refresh token plafonnés.
3. **Le jeton est celui du propriétaire de la chaîne** : « All YouTube Analytics and
   YouTube Reporting API requests must be authorized by the channel or content owner
   that owns the requested data. » Requête type `ids=channel==MINE`. Même règle que le
   reste du dépôt : **l'identité d'un locataire n'a jamais de valeur par défaut**.
4. **Brand Account** : le choix du compte pour une chaîne rattachée à un Brand Account
   n'est **pas documenté** dans les pages lues. À tester avec un vrai compte.

## Contradictions entre sources

- **C1 — revenus par chaîne.** [`revenue_reports`](https://developers.google.com/youtube/analytics/revenue_reports)
  les dit « pas disponibles pour les chaînes individuelles » ; `channel_reports` et
  `sample-requests` montrent un rapport « Revenue » sur la chaîne (scope monétaire +
  YPP). **Non tranché** : seul un appel réel avec le jeton d'un artiste YPP le dirait.
- **C2 — coût d'une requête.** `limits`/`quota_usage` : coût évalué par requête ; un
  extrait de recherche dit « one unit per request », non vérifié par lecture de la page.
- **C3 — `youtube.readonly`.** Exigé par `reports.query`, cité sans être dit
  obligatoire par le guide d'autorisation. Deux formulations, pas de désaccord de fond.
- **C4 — `redViews`.** Dépréciés en 2018 (révisions), encore listés comme tri dans
  « Top videos ».

## 7. Recommandation — 5 métriques pour un artiste indépendant

Classement par valeur **supposée**, à trancher par le propriétaire :

1. `views` (ou `engagedViews`) × `day` — une vraie série au lieu des instantanés : elle
   rend correcte toute figure YouTube qui différencie aujourd'hui des cumuls.
2. `subscribersGained` / `subscribersLost` × `day` et × `video` — la demande V40/V41 :
   quel titre fait venir l'audience.
3. `estimatedMinutesWatched` + `averageViewPercentage` × `video` — la qualité d'écoute.
4. `views` × `insightTrafficSourceType` — d'où vient l'audience ; juge l'effet d'une
   campagne (`ADVERTISING`, `EXT_URL`).
5. `audienceWatchRatio` × `elapsedVideoTimeRatio` — la rétention d'un clip (un ID par
   requête).

Hors classement : `country` × `views` ; âge / genre sous réserve des seuils ; revenus
sous réserve de C1 et de l'éligibilité YPP.
