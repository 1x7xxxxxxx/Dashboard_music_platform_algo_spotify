# ADR-028 — Le prix reste plat, et l'activation passe devant

- **Status:** Accepted
- **Date:** 2026-09-22
- **Deciders:** @timothe

## Context

R152 relevait, depuis *Product-Led Growth* (Wes Bush), que streaMLytics facture
**10 €/mois à plat**, sans *value metric* : l'axe sur lequel on facture ne suit
aucune grandeur qui bouge avec la valeur reçue. « Jusqu'à 10 artistes » ne veut
rien dire pour un artiste solo, c'est-à-dire pour tout le marché visé. Le revenu
par client est donc plafonné le jour de l'inscription, qu'il branche cinq
plateformes ou une, qu'il dépense 50 € ou 5 000 € de publicité.

Le constat est juste. Ce qui manquait, c'est la mesure de ce qu'il coûte
**aujourd'hui**. Relevée en production le 2026-09-22 :

| grandeur | valeur |
|---|---|
| locataires humains (hors toi, hors canari, hors bac à sable) | **4** |
| dont **activés** — au moins une plateforme qui livre une ligne | **1** (Benken) |
| essais de 30 jours arrivés à terme | **3** |
| conversions payantes | **0** |
| abonnements actifs dans `artist_subscriptions` | **0** |
| MRR | **0 €** |

Trois comptes sur quatre n'ont jamais reçu une seule ligne de donnée — Cuzebo
depuis **cent jours**, GRiNCH depuis quarante et un, artiste1 depuis vingt-trois.
Leur `etl_run_log` ne porte aucun échec : il porte `skipped`, parce qu'aucun
identifiant de plateforme n'a été saisi.

Un axe de valeur multiplie un revenu par client. Ici le multiplicande est nul, et
il l'est pour une raison qui n'a rien à voir avec le prix.

## Decision

**Aucun axe de valeur n'est adopté maintenant. Le prix reste plat à 10 €/mois, et
l'effort va à l'activation** — mesurée par la métrique unique posée en tête du
panneau de supervision le même jour (R149, `src/utils/activation.py`).

Ce n'est pas un refus de R152 : c'est la réponse prévue par son propre libellé,
« un axe de facturation choisi, **ou la décision écrite de ne pas en avoir** ».

## Consequences

### Positive
- Aucun travail de facturation n'est engagé sur une hypothèse que zéro client
  peut confirmer ou infirmer. Motif d'ADR-007 : un travail dont le bénéfice mesuré
  est nul n'entre pas dans l'index.
- L'ordre de bataille devient lisible et vérifiable : activer, puis convertir,
  puis tarifer. R148 (entretiens sur la disposition à payer) et R150 (options de
  prestation) gardent tout leur sens — ils ne dépendent pas d'un axe de valeur,
  ils dépendent d'avoir des gens qui utilisent le produit.

### Negative / Trade-offs
- Si un artiste à gros budget publicitaire arrive demain, il paiera le même prix
  qu'un artiste sans budget. On l'accepte : on n'a pas encore rencontré ce cas.
- Un axe de valeur se conçoit plus facilement AVANT d'avoir des abonnés qu'après
  — changer l'unité de facturation d'une base existante est un chantier de
  migration et de communication. On paie ce risque sciemment, contre le risque
  plus grand de construire une grille tarifaire pour personne.

### Neutral / Operational
- Les axes plausibles sont déjà dans la donnée collectée et le resteront : la
  dépense publicitaire suivie (`v_meta_campaign_daily.spend`), le nombre de
  plateformes qui livrent (`etl_run_log`), le volume d'écoutes
  (`s4a_song_timeline`). Rien n'est à instrumenter le jour où on rouvrira.

## Le déclencheur de réouverture — calculable, pas prudentiel

Cette décision se rouvre quand **les deux** conditions suivantes tiennent :

1. `SELECT count(*) FROM artist_subscriptions WHERE status IN ('active','trialing')`
   rend **≥ 5** — il existe une base à qui un changement d'axe s'appliquerait ;
2. l'écart de dépense publicitaire entre le décile haut et le décile bas des
   abonnés dépasse **un facteur 10** — c'est-à-dire qu'un axe ferait réellement
   varier la facture.

Tant que la première est fausse, la seconde ne se calcule pas. `make reopen-check`
porte les déclencheurs de ce type ; celui-ci y est ajouté le 2026-09-22.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Facturer à la dépense publicitaire suivie | L'axe est mesuré (`v_meta_campaign_daily`) et il discrimine — mais **un seul locataire humain a des campagnes**. Un axe calibré sur un point est une supposition, pas un modèle. |
| Facturer au nombre de plateformes connectées | Il punit exactement le geste qu'on cherche à provoquer. Trois comptes sur quatre n'en ont connecté aucune : faire payer la quatrième plateforme, c'est tarifer l'activation qu'on n'obtient pas. |
| Facturer au volume d'écoutes | L'artiste ne contrôle pas ses écoutes, et sa facture monterait le mois où il a du succès — mécaniquement corrélé à sa capacité à payer, mais ressenti comme une punition. À reconsidérer si le produit devient un outil de campagne plutôt qu'un tableau de bord. |
| Ajouter un troisième palier au-dessus de Premium | **Pas rejeté — différé, et c'est une décision distincte.** *Pricing Creativity* (Enns) mesure qu'un troisième prix plus élevé augmente les ventes du prix médian de près de 50 %. Deux plans n'ont pas de milieu. Cet effet joue sur la STRUCTURE de l'offre, pas sur l'axe de facturation ; il se décide avec R150. |
