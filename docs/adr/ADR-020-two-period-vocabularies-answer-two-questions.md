# ADR-020 — Deux vocabulaires de période, parce qu'ils répondent à deux questions

- **Status**: Accepted
- **Date**: 2026-09-10
- **Related**: ADR-007 (le travail de performance est conditionné), ADR-019 (la couche or)

## Context

L'audit du 2026-09-10 a relevé, parmi trente-deux constats, que le produit porte **deux
systèmes de filtre de période** sans aucun état partagé :

| Module | Vocabulaire | Surfaces |
|---|---|---|
| celui de l'accueil | Depuis le début · Cette année · 12 mois · 90 j · 30 j · sur mesure | **l'accueil seul** |
| celui des pages plateforme | En cours · Depuis dernière release · Tout l'historique · plage personnalisée, avec un grain Semaine / **Mois** / Année | **onze vues** |

Conséquences observables : la période choisie sur l'accueil est perdue dès qu'on ouvre
une page plateforme, et le grain s'y appelle « Mois » — que l'accueil ne propose pas —
tandis que l'accueil propose un pas « jour » que l'autre n'a pas.

La proposition initiale était de les unifier. En l'instruisant, la prémisse s'est
révélée partiellement fausse.

## Ce que l'instruction a trouvé

**Les deux filtres ne répondent pas à la même question.**

- L'accueil demande : *« toutes mes plateformes, sur une fenêtre calendaire »*. Ses
  raccourcis sont des durées, parce qu'on y compare des sources entre elles.
- Une page plateforme demande : *« cette entité, depuis un événement »*. Son préréglage
  central est **« depuis la dernière sortie »**, une borne qui n'a de sens que rapportée
  à un titre : elle est calculée à partir de la date de sortie de l'entité choisie.

Un vocabulaire unique devrait donc soit porter « depuis la dernière sortie » sur
l'accueil — où il n'y a pas d'entité pour l'ancrer — soit le retirer des pages
plateforme, où il est le réglage le plus utile. Unifier reviendrait à appauvrir la
moitié la plus riche.

## Decision

**Garder les deux vocabulaires.** Ils ne sont pas une duplication : ce sont deux
contrats distincts, l'un calendaire, l'autre ancré sur un événement.

**Ce qui est corrigé sans les unifier** — ce qui relevait vraiment du défaut :

- La « journée » du produit suit désormais le fuseau d'affichage déclaré, et non
  l'horloge de la machine, dans les deux systèmes.
- Le grain d'un côté et le pas de l'autre ne se contredisent plus dans les textes : chacun
  nomme ce qu'il fait sur sa propre surface.

## Alternatives rejetées

| Option | Pourquoi rejetée |
|---|---|
| Un vocabulaire unique | Il faudrait retirer « depuis la dernière sortie » des pages plateforme, où c'est le réglage le plus utile, ou l'inventer sur l'accueil, où rien ne l'ancre. |
| Faire suivre la période de l'accueil vers les pages | Les préréglages ne se traduisent pas : « 30 jours » n'a pas d'équivalent, et « depuis la dernière sortie » n'a pas d'antécédent. Traduire au plus proche ferait mentir le libellé affiché. |
| Un état partagé sur la seule plage personnalisée | Le seul préréglage commun aux deux, et le moins utilisé. Un mécanisme de partage pour ce cas coûte plus que le confort qu'il rend. |

## Consequences

### Positives
- Chaque surface garde le filtre qui répond à sa question.
- Aucune des douze vues concernées n'est touchée : le risque d'un refactor transverse est
  évité, conformément à ADR-007 — un balayage « pour la cohérence » a déjà failli donner à
  chaque administrateur les données d'un autre locataire.

### Négatives / compromis assumés
- L'artiste re-choisit sa période en changeant de page. C'est un frottement réel, et il
  est **assumé** plutôt que résolu par une traduction approximative.
- Deux vocabulaires sont deux choses à apprendre. La documentation produit doit les
  présenter comme deux outils, jamais comme deux versions du même.

### Le déclencheur qui rouvre cet ADR
**Un troisième vocabulaire de période apparaît**, ou **l'accueil gagne un préréglage
ancré sur un événement** (donc une entité à ancrer). L'un ou l'autre signifierait que la
distinction posée ici a cessé d'être vraie — et c'est alors l'unification qu'il faudrait
instruire, avec les mêmes exigences de mesure.
