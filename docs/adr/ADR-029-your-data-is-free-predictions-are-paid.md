# ADR-029 — Tes données sont gratuites, les prédictions sont payantes

- **Statut** : accepté (2026-09-26)
- **Décideur** : le propriétaire
- **Remplace** : la liste de ce qui se vend écrite le 2026-09-04 / 2026-09-22 (`stripe_schema.py`)
- **Laisse intact** : ADR-028 — le prix reste plat à 10 €/mois jusqu'à ce que l'activation soit réglée

## Contexte

« Là c'est compliqué de savoir ce qu'on met dans chaque vue en free. » Le découpage était une
liste de pages : les quatre vues Meta avancées, le rapport PDF, Road to Algo et les prévisions
étaient Premium. Aucun principe ne permettait de ranger une page neuve. ADR-028 mesurait :
4 locataires humains, 1 activé, 0 payant — le blocage est l'activation, pas le prix.

## Décision

**Une règle, qu'un artiste peut répéter : tes données sont gratuites, les prédictions sont
payantes.**

- **Gratuit** — tout ce qui LIT les données de l'artiste, et leur fusion : chaque plateforme,
  Meta × plateformes (`meta_x_spotify`), créas (`meta_creatives`), répartitions
  (`meta_breakdowns`), le rapport PDF à la demande (`export_pdf`, hors sections ML).
- **Premium** — tout ce qui PRÉDIT : Road to Algo (`trigger_algo`), l'optimiseur de coût par
  résultat (`meta_cpr_optimizer`, il lit `ml_song_predictions`), les prévisions de revenus
  (`revenue_forecast`), les sections ML du PDF (`songs`, `ml_explain`, `revenue_forecast`) et
  l'ENVOI automatique du rapport chaque semaine (`weekly_digest`).
- **Un aperçu gratuit de ce qui est payant** — `algo_preview` (🔓 vert, juste au-dessus de Road
  to Algo) : pour la dernière sortie, la porte la plus proche, les actions et un budget en
  ordre de grandeur. Il ne montre aucune probabilité que le modèle ne tient pas (toutes au
  plancher en production ce jour-là).

## Pourquoi (le corpus, `business-offre`)

- *Monetizing Innovation* (Ramanujam & Tacke, p. 87-94) : une fonction est un **leader** (on
  paie pour elle), un **filler**, ou un **killer** (la faire payer fait échouer la vente).
  Faire payer à un artiste la lecture de SES propres données est un killer ; la prédiction de
  déclenchement est le leader.
- *Product-Led Growth* (Wes Bush, p. 25, 45, 70) : le gratuit doit livrer le « aha » — ici,
  voir sa pub Meta agir sur ses écoutes — et le payant est ce dont on a besoin APRÈS avoir vu la
  valeur ; donner trop en gratuit retire toute raison de payer. D'où un payant resserré sur UN
  leader, et un aperçu qui le montre au lieu d'un cadenas muet.

## Alternatives écartées

1. **Seul Road to Algo payant** (la proposition initiale à la lettre) — plus simple, mais le
   Premium tient sur une page, et sur la confiance dans un modèle dont les probabilités sont
   aujourd'hui au plancher. L'optimiseur et les prévisions prédisent aussi : même règle.
2. **Statu quo** (quatre vues Meta payantes) — c'est ce qui rendait la frontière illisible, et
   il cache le « aha » derrière le paywall pendant que l'activation est le blocage mesuré.
3. **Un aperçu SANS garde-fou d'honnêteté** — refusé (code-critic) : un pourcentage au
   plancher, lu par quelqu'un sans contexte, vend un chiffre que le modèle ne tient pas.

## Conséquences

- Un abonné Premium ne perd rien (`'*'`). Un essai qui se termine perd les prédictions et
  l'envoi hebdomadaire — l'onboarding et le mail J-3 le disent désormais.
- La valeur du Premium repose sur la qualité des prédictions : c'est ce que R148 (les
  entretiens « combien tu paierais », backlog produit) doit tester en premier.
- La conversion de l'aperçu n'est pas prouvée : tant que l'activation n'est pas réglée, la
  plupart des artistes verront son état vide (aucune prédiction). À mesurer, pas à supposer.
- Garde : `tests/test_plan_gating.py` (les pages qui prédisent restent verrouillées ; les pages
  de données et l'aperçu restent ouverts ; `weekly_digest` reste payant).

## Rouvrir si

- R148 montre que les artistes paieraient pour une fonction de DONNÉES (et pas de prédiction) ;
- ou ≥ 5 abonnements actifs et un Premium qui ne convertit pas après 3 mois d'aperçu.
