# Protocole de séance longue — ce qu'on fait quand personne ne regarde

> **À lire EN PREMIER à chaque réveil**, avant la roadmap. Une page, et elle tient
> dans un écran : un protocole qu'on ne relit pas est un protocole qui n'existe pas.

## Pourquoi ce fichier existe

Une séance de plusieurs heures est **compactée** plusieurs fois. Après chaque
compaction je reviens avec un résumé : je sais ce qu'on fait, pas *où j'en suis
exactement*. La roadmap dit **quoi** ; elle ne dit pas **où j'en étais** — elle se met à
jour quand une brique est livrée, pas quand un lot de six classes est à mi-chemin. Entre
les deux il y a plusieurs heures, et c'est précisément la granularité d'un réveil.

`make night-status` remplit ce trou, et c'est la **première commande de chaque réveil**.

## La boucle, en cinq gestes

```bash
make night-status                                  # 1. où j'en suis — un écran
make night-start  TASK=R122 W="lot 6 — six portées"  # 2. j'ouvre UNE unité
#    … le travail …
make test-changed                                  # 3. les tests atteignables (règle 16)
git add -A && git commit && git push               # 4. je commite AVANT la suivante
make night-done   TASK=R122 W="six portées, plafond 332 → 326"
```

Et pour un fait qu'on trouve en chemin sans vouloir dévier — `make night-note TASK=R122
W="…"`. Une mesure, un chiffre, un défaut repéré ailleurs : le journal le garde, la
prochaine unité le retrouve. Sans lui, la seule façon de ne pas perdre un constat est de
s'arrêter dessus tout de suite.

**Une unité = un commit poussé.** Ce n'est pas de l'hygiène : un arrêt ne coûte alors
qu'une unité. Par lots de six, il coûte la nuit.

## Bloqué ⇒ on PARQUE, on ne s'arrête jamais

```bash
make night-park TASK=R116 W="ADR-027 demande une décision produit : 2 répliques ou Redis ?"
```

Puis **on écrit la même question dans « 🙋 En attente de toi » de `checklist.md`** et on
passe à la tâche suivante de l'index. Un blocage qui arrête la séance consomme toutes les
heures restantes ; un blocage parqué en coûte deux minutes.

Est bloquant — et seulement ça :

| | |
|---|---|
| une **décision produit** | quel comportement l'artiste doit voir |
| un geste **hors du dépôt** | migration en prod, DNS, un identifiant à créer |
| un **envoi réel** | e-mail, paiement, quoi que ce soit qui sorte vers un humain |
| un **rouge dont le correctif est un choix**, pas une erreur | |

N'est PAS bloquant, et se traite seul : un test rouge dont la cause se lit, un document
généré périmé, un plafond à resserrer, un garde à écrire, une portée à rédiger.

## Ce qu'on ne fait jamais sans un humain

- pousser sur autre chose que `main`, ou forcer un push ;
- toucher à la **base de production**, aux DAG en prod, aux secrets ;
- **supprimer** une classe d'erreur, un test ou une entrée de roadmap pour faire baisser
  un compteur — déplacer, oui ; supprimer, jamais ;
- desserrer un plafond **pour le faire taire**. Le relever se fait avec sa raison écrite
  dans le même commit, sinon ce n'est pas un plafond ;
- écrire dans l'arbre **pendant qu'une suite complète tourne** — son verdict décrirait un
  arbre qui n'existe plus. `make night-status` le dit.

## ⚠️ La machine peut cesser de pouvoir travailler — et le dire prend deux commandes

Mesuré le 2026-09-17, après **cinq** suites tuées d'affilée puis un fichier de test seul
passé de 6 s à plus de 120 s :

```bash
free -m | sed -n '2,3p'        # la ligne Swap, pas seulement la ligne Mem
cat /proc/pressure/memory      # avg60 / avg300 — la pression SOUTENUE
```

L'état trouvé : **2,9 Go de swap sur 4 utilisés**, `avg300=1,73`. Le système paginait
depuis un moment, et c'est pour ça que tout ralentissait d'un facteur 20.

**J'ai donné trois diagnostics avant de lire ces deux chiffres** — « trop de workers »,
puis « le harnais tue les tâches de fond », puis seulement la pagination. Les deux
premiers ont produit trois correctifs successifs sur le nombre de workers, qui ne
traitaient pas la cause. `free` annonçait 6,9 Go « disponibles » pendant tout ce temps :
ce chiffre compte du cache réclamable, pas de la mémoire prête à servir.

Quand ces deux commandes disent que la machine pagine : **on arrête d'essayer**. On
commite ce qui est vérifié en le disant, et on n'annonce aucun total de suite qu'on n'a
pas obtenu.

## Les trois pièges déjà payés dans ce dépôt

1. **`pytest tests/` à la main perd `-n auto`** : 1 146 s au lieu de 418 s. Toujours
   `make test` / `make test-fast` / `make test-changed`.
2. **`ps | grep` est avalé par le wrapper RTK** — il rend une sortie vide, ce qui se lit
   comme « rien ne tourne ». Quatre conclusions fausses le 2026-09-16.
3. **Une sonde matche le shell qui la porte.** `night_run.py` s'est fait avoir en
   l'écrivant : il annonçait « une suite tourne » parce que son propre shell contenait le
   mot. Il lit désormais les jetons d'argv et exclut sa lignée.

## L'ordre de travail

Celui de l'index `## 📋 Tâches ouvertes` de `checklist.md`, que `make night-status`
affiche. **R122 est volontairement en dernier** : elle est du volume (363 → 332 portées
en 89 min mesurées, ~16 h pour une seule de ses trois colonnes), donc mise en tête elle
mangerait la séance sans qu'aucune autre tâche avance. ⚠️ **R117 a été faite le 2026-09-17, AVEC un humain** — c'était la bonne façon : une
session ne peut pas se déplacer elle-même. Le dépôt vit sur `~/streamlytics`, la suite
passe de 418 s à **193,5 s**. Il reste la bascule VS Code, qui demande aussi une fenêtre,
donc un humain. À l'intérieur d'une tâche, l'ordre est écrit dans son bloc de détail.

Une tâche terminée : `Spawn roadmap-keeper` (règle 17) — jamais une suppression à la
main.

## L'invariant, vérifiable

```bash
make night-check     # sort ≠ 0 si : arbre sale, commits non poussés, unité ouverte > 3 h
```

Un `night-check` rouge en fin d'unité veut dire qu'on a commencé la suivante sans fermer
la précédente. C'est la seule façon dont ce protocole peut se périmer en silence.

⚠️ Le **journal** est exclu du contrôle d'arbre sale, et c'est un correctif trouvé à la
première unité de la première nuit : `night-done` écrit sa ligne APRÈS le commit — il ne
peut pas faire autrement, il enregistre le sha — donc l'arbre était sale à chaque fin
d'unité et `night-check` rouge à coup sûr. **Un invariant qui ne peut jamais tenir est un
invariant qu'on apprend à ignorer**, ce qui est pire que pas d'invariant. Le journal part
avec le commit de l'unité suivante.
