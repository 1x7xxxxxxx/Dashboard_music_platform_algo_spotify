# ADR-025 — Le produit est Spotify + Meta + ML, pas « toutes les plateformes »

- **Statut** : accepté
- **Date** : 2026-09-13
- **Remplace** : la partie YouTube d'**ADR-024** (l'historique reste récupérable ; on ne
  le récupérera pas) et **R105**, abandonnée.
- **Déclencheur** : « le but de l'app c'est de mêler insta meta ads spotify hyppedit s4a
  et shazam + ML, pas forcément soundcloud et youtube ».

## Le constat qui tranche

Mesuré en production le 2026-09-13, artiste 1, sur tout l'historique :

| plateforme | écoutes observées | part du signal |
|---|---|---|
| Spotify (S4A) | **165 065** | **99,2 %** |
| SoundCloud | 323 | 0,2 % |
| YouTube | 304 | 0,2 % |
| Apple Music | 3 718 (relevés de dépôt) | — |

YouTube et SoundCloud pèsent **0,4 %** du signal réunis. Et ce ne sont pas des chiffres
faux : ce sont des compteurs qui ne bougent presque pas, sur des plateformes qui ne sont
pas là où l'artiste travaille.

**Le coût, lui, n'était pas proportionnel.** La journée du 2026-09-12 au 2026-09-13 a
été consacrée pour moitié à ces deux plateformes : la rupture de méthode du 11 juin
(+18 438 vues d'artefact), le recalage des niveaux, la falaise du cumulé, les deux dates
de première mesure, la recherche sur les API d'historique, et un flux OAuth complet.
Pendant ce temps, **Shazam n'est pas sur la page d'accueil**.

## Décision

### Le cœur, qui a droit au travail

`instagram` · `meta_ads` · `spotify` (API + S4A) · `hypeddit` · `shazam` · et la couche
**ML** qui les relie. C'est la chaîne que le produit raconte : on dépense, on mesure
l'audience, on regarde si le titre entre en playlist.

### La périphérie, qui reste en l'état

`youtube` · `soundcloud` restent collectées **comme aujourd'hui** : un compteur à vie,
une boîte KPI, une courbe. Rien de plus ne leur est ajouté sans un déclencheur mesuré.

### Ce qui est abandonné, et ne doit pas être rebâti

**L'étape d'onboarding OAuth YouTube (R105).** Elle a été écrite le 2026-09-13 —
helper OAuth, collecteur Analytics, migration, étape dans la page Credentials, tâche
Airflow, 14 assertions de garde — puis **retirée sans être livrée**, le jour même,
quand l'arbitrage a été posé.

Retirée et non désactivée : « une couche débranchée pourrit » est une leçon que ce dépôt
a déjà payée trois fois. Du code que rien n'exécute cesse d'être vrai sans que personne
le voie, et se rebranche un jour sur un produit qui a changé sous lui.

Ce qu'elle aurait coûté, en plus de son écriture :

- un **consentement Google par artiste**, donc une étape de plus dans un parcours
  d'onboarding qu'on passe notre temps à raccourcir ;
- une **vérification Google** (politique de confidentialité, domaine vérifié, vidéo de
  démonstration) avant de servir à qui que ce soit d'autre que le propriétaire du
  projet ;
- en attendant, des **refresh tokens expirant tous les 7 jours** — donc un artiste qui
  reconnecte chaque semaine, ou une collecte qui meurt en silence.

Tout cela pour dater 0,2 % du signal.

## Ce qui rouvrirait la question

- un artiste dont **YouTube ou SoundCloud dépasse 20 % de ses écoutes observées** — la
  requête qui le dit vit dans `platform_totals`, et ce seuil est délibérément loin des
  0,2 % actuels ;
- une demande explicite d'un artiste payant.

## Ce qui est ouvert par cette décision

**Shazam n'est pas sur la page d'accueil** alors qu'il est dans le cœur. C'est
l'incohérence que cet arbitrage rend visible, et elle devient une tâche — voir la
roadmap. Décider ce qu'une boîte Shazam affiche demande de trancher ce que la donnée
permet : un compteur de Shazams à vie, un delta sur la période, ou les deux.
