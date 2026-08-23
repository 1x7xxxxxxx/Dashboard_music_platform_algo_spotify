# Couverture thématique de l'app, adossée au corpus `knowledge-rag`

> Établi le 2026-08-23. Chaque ligne « Ce que dit le corpus » porte **livre + page** ;
> chaque ligne « Ce que fait l'app » porte un **fichier** ou une **mesure de production**.
> Rien ici n'est de mémoire : ce qui n'a pas de source est marqué **hors-corpus**.

## Ce que le corpus peut et ne peut pas répondre

| Domaine | Livres | Verdict pour ce projet |
|---|---|---|
| `ux-frontend` | 10 | **Riche et directement applicable** — Few ×2, Cooper *About Face*, Kirk, Wroblewski, Yifrah, Podmajersky, Johnson |
| `data-eng` | 2 | Utile sur les **dimensions** de la qualité de donnée |
| `mlops` | 5 | Utile sur **quoi surveiller** en production |
| `ml-ia` | 17 | Utile sur **incertitude et explicabilité** |
| `marketing-musical` | 1 | Mince (une newsletter), mais **une trouvaille actionnable** |
| `industrial` | 10 | ❌ **Aucun rapport** — manuels Siemens PLC/TIA Portal. Cherché « fatigue d'alarme » : ne renvoie que de la config d'automate. |
| `algo-dev` | 4 | ❌ **Aucun rapport** — notes de backtesting trading, pas de génie logiciel |
| `reseaux-systemes` | 4 | ❌ **Quasi rien** — OSI/TCP-IP, temps réel embarqué, *Linux pour les Nuls* |

**Non couvert par la bibliothèque, à assumer comme tel** : multi-locataire / SaaS,
sécurité applicative, observabilité SRE (SLO, budget d'erreur), stratégie de tests.
Sur ces quatre sujets ce dépôt n'a **que** son propre catalogue d'erreurs — c'est une
raison de plus de le tenir.

---

## 1. UI — l'état vide

**Corpus** — *Microcopy: The Complete Guide* (Yifrah) p.127 :
> « When you leave the empty state empty, you are basically telling your users what
> there **isn't**. You are missing out on the opportunity to tell them what there **is** —
> what could have been here. »

Il précise que l'état vide survient **deux fois** : au premier contact, et *en résultat
d'usage* (une recherche sans résultat).

**L'app** — c'est le point fort. La matrice **Configuré / Répond / Données**
(`src/utils/artist_readiness.py::status_matrix`) ne montre jamais un vide muet : chaque
plateforme porte un `status_label` et un `next_action`. Quatre surfaces, un seul renderer,
zéro appel API au rendu.

**L'écart mesuré** — `nodata_hint` est une **devinette statique** quand aucune sonde n'a
tourné. C'est la divergence GRiNCH : l'écran disait « vérifie ton User ID ; l'app partagée
doit être configurée (admin) », la vérité était « ce profil n'a aucun titre public ». Le
budget de sondes (`READINESS_PROBE_BUDGET=25`, à l'échelle de la flotte) fait retomber
l'app sur la devinette dès ~25 locataires, **et l'épuisement n'est visible que dans un log**.

---

## 2. UI — le message d'erreur

**Corpus** — trois auteurs convergents :
- *Microcopy* p.107 : « Error messages are the only text we write that we **hope users
  will never see** » ; ils arrivent quand la motivation est déjà fragile et peuvent être
  la goutte qui fait abandonner.
- *About Face* (Cooper) p.311 : un mauvais message « tells the user something he doesn't
  care about **or demands that he fix a situation that the application can and should
  usually fix just as well** ». p.678 : un bon message « doesn't suggest that the user's
  behavior is anything but impeccable ».
- *Designing with the Mind in Mind* (Johnson) p.12 : l'utilisateur **ne voit pas** le
  message — « A-ha! Has that error message been there all along? »

**L'app** — le statut `BROKEN` respecte Cooper à la lettre : « Rien à faire de ton côté —
la vérification a échoué, on regarde. » Il ne demande **rien** à l'artiste.

**L'écart mesuré, et le corpus le condamne explicitement** — `alert_monitor.check_data_freshness`
**ne sérialise pas `error`** et filtre sur `stale` seul. Une sonde cassée est donc envoyée
à l'artiste comme « 🟡 Données stale · relance le DAG » : exactement le message qui
« demands that he fix a situation the application should fix ». → **chantier 2 du plan.**

---

## 3. UI — la validation de formulaire

**Corpus** — *Web Form Design* (Wroblewski) ch. 9, p.243-258 :
- La validation en ligne sert à **confirmer ou suggérer**, pas seulement à refuser ;
- elle vaut surtout « for questions with **potentially high error rates or specific
  formatting requirements** » ;
- et p.256 : si l'utilisateur saisit une valeur valide dans un autre format, **on la
  reformate pour lui — mais après qu'il a fini, jamais pendant la frappe**.

**L'app** — conforme sur le fond : `identity_is_well_formed` valide **à la sauvegarde**
avec `re.fullmatch`, et `extract_spotify_artist_id` transforme une URL Spotify collée en
identifiant de 22 caractères. C'est précisément le « reformat after they are done ».

**L'écart** — les cinq identités (`UC…`, `spotify_artist_id` 22 car., `user_id` numérique,
`account_id`, `ig_user_id`) sont *le* cas « specific formatting requirements » de
Wroblewski, et il n'y a **aucune confirmation en ligne** : l'artiste ne sait que son
`channel_id` est mal formé qu'après avoir soumis. Le registre `PLATFORM_IDENTITIES` porte
déjà le `pattern` — l'indice en ligne serait dérivé, pas retapé.

---

## 4. UI — couleur et accessibilité

**Corpus** — *Data Visualisation* (Kirk) p.55 liste ce qui fait échouer une visualisation,
en premier : « It is **visually inaccessible**. There is no appreciation of potential
impairments like **colour blindness** » — et, dans la même liste, « **It has too many
functions.** You failed to focus. » p.195 : distinguer par la **teinte**, pas la saturation.

**L'app** — **conforme, et par construction** : les statuts sont 🟢🟡🔴⚪⏸️ **plus un
`status_label` textuel** (« OK », « Données anciennes », « Connecté — aucune donnée »,
« À connecter »). L'information n'est jamais portée par la seule couleur.

**À faire** — c'est une propriété qu'aucun test ne tient. Un garde qui exige que tout
statut expose un libellé non vide coûte cinq lignes et empêche la régression silencieuse.

---

## 5. UI — la densité du tableau de bord

**Corpus** — *Information Dashboard Design* (Few) p.27 et p.36 : un tableau de bord porte
« information of whatever type that is **needed to do a job** », pas nécessairement des
KPI, et pas nécessairement quantitatif (une liste « Top 10 » en est). Kirk p.55 : « too
many functions ».

**L'app** — déjà mesuré : `make chart-budget` rend **22 vues, 83 graphiques, médiane 3**,
quatre vues au-delà du double, `trigger_algo` à **15**. Le critère retenu (R29) est le
coup d'œil de Few, pas un seuil inventé.

---

## 6. UI — provenance et confiance

**Corpus** — *Data Visualisation* (Kirk) p.391 : « il est important d'expliquer **comment
la donnée a été recueillie et quels critères ont été appliqués pour inclure ou exclure**
certains aspects », et de mentionner les hypothèses et transformations. p.302 : les
projets qui collectent de la donnée saisie par l'utilisateur portent **un risque de
confiance supplémentaire** — « you need to alleviate any such concerns upfront ». p.125 :
une conclusion inexacte sur ce que dit la donnée abîme plus la confiance qu'une donnée
manquante.

**L'écart, et c'est le plus intéressant du balayage** — l'app applique un critère
d'exclusion **que l'artiste ne voit nulle part** : `ARTIST_NAME_FILTER` retire la ligne
« Total » des CSV S4A (`AND song NOT ILIKE '%1x7xxxxxxx%'` sur toute requête
`s4a_song_timeline`). C'est exactement le « criteria applied to include or exclude » de
Kirk p.391. De même, `measured_on` (`metric` vs `write`) existe **en interne** et ne
remonte à aucun écran : l'artiste ne sait pas si « à jour » veut dire « écrit ce matin »
ou « décrit hier ».

---

## 7. Data — les dimensions de la qualité

**Corpus** — *Fundamentals of Data Engineering* (Reis & Housley) p.90-91, trois
caractéristiques : **Accuracy** (factuellement juste, pas de doublons), **Completeness**
(tous les champs requis valides), **Timeliness** (disponible à temps). Et p.90 la question
que tout le monde pose : « **Can I trust this data?** »
Le cours *MLOps — de la donnée brute à la mise en production* p.12 en donne la version
opérationnelle : validation des **schémas et formats**, identification des **valeurs
aberrantes**, **alertes sur dégradation de qualité**, **% de valeurs manquantes**, et
**fraîcheur**.

**L'app, par dimension :**

| Dimension | État |
|---|---|
| **Timeliness** | ✅ solide — `freshness_monitor` sur 7 sources, `measured_on` metric/write, `expected_silence`, une seule horloge (Postgres) |
| **Completeness** | ❌ **rien** — aucun % de valeurs manquantes, aucun contrôle de champs requis à l'ingestion |
| **Accuracy** | ⚠️ partiel — `check_row_anomalies` voit un pic (>10× la moyenne 7j, plancher 100 lignes) mais **jamais l'autre direction ni une valeur fausse** ; pas de détection d'aberrant |
| **Schéma / format** | ⚠️ en base seulement — `schema_drift_cron.sh` compare la structure, rien ne valide une **ligne entrante** |

Et le DAG qui porterait ce sujet, **`data_quality_check`, est EN PAUSE en production**
(mesuré aujourd'hui : `is_paused = t`, aucun run jamais). C'est le trou le plus net que ce
balayage ait produit.

---

## 8. MLOps — quoi surveiller

**Corpus** — *MLOps* p.41, les métriques essentielles : **performance du modèle**
(accuracy/précision/rappel), **latence**, **débit**, **santé du système** ; p.39 : le
déclencheur de ré-entraînement est « **dégradation des performances du modèle** » ou une
planification régulière. *Machine Learning Production Systems* p.286 : la **validation de
donnée avant l'entraînement** décide si on ré-entraîne ou si on **arrête le pipeline**.

**L'app** — `check_drift_anomalies` couvre la dérive d'entrée (feature hors distribution
sur >50 % des dernières prédictions). La **performance** du modèle n'est pas surveillée, et
c'est **assumé et documenté** : elle exige des étiquettes, `ml_prediction_outcomes` est à
**0 ligne** (ADR-008). La boucle qui les produit tourne ; elles s'accumuleront seules.
Cohérent avec le corpus — le manque est nommé, pas caché.

---

## 9. ML — présenter une probabilité

**Corpus** — Géron, *Hands-On ML* p.387 / *Deep Learning avec Keras* p.154 : devant une
prédiction dont l'écart-type des estimations est élevé, « vous prendriez probablement avec
**extrême prudence** une prédiction aussi incertaine ; vous ne la considéreriez certainement
pas comme une prédiction sûre à 99 % ». *Optimisation, Explicabilité et Scalabilité* p.20
donne la grille de restitution à un **non-expert** : Feature Importance (globale, comprendre
le modèle), Waterfall (locale, expliquer **une** décision), Force Plot (locale, **communiquer
à un public non technique**).

**L'app** — les jauges et la scorecard `algo_knowledge`/`ml_widgets` existent, avec
calibration. **À vérifier** : l'écran distingue-t-il une probabilité **calibrée** d'une
probabilité **incertaine** ? C'est la seule ligne de ce document que je n'ai pas mesurée.

---

## 10. Marketing musical — la seule trouvaille actionnable

**Corpus** — la newsletter Southworth (2026-06-29) sur les Meta Ads pour la musique :
> « Quand vous laissez Advantage+ audiences activé, **même en sélectionnant une tranche
> 18-44**, leur IA dépensera souvent l'essentiel de votre budget sur les **65+**. J'ai vu
> des cas où un titre hip-hop moderne finit avec presque tout son budget sur les 65+, et
> **aucun stream sur Spotify**. »

**L'app** — on collecte déjà `meta_insights_performance_age`. Le rapprochement
« budget concentré sur une tranche d'âge incohérente avec le genre **et** zéro stream » est
donc calculable **avec les données déjà en base**, et c'est exactement le genre de constat
qu'un artiste ne peut pas voir seul. Piste produit, pas une correction.

---

## Ce que ce balayage change dans le plan en cours

Le corpus **confirme** deux chantiers déjà décidés et en **ajoute** un :

1. **Chantier 2 renforcé** — perdre `error` et envoyer « relance le DAG » est nommément
   le mauvais message chez Cooper (p.311). Ce n'est plus un choix esthétique.
2. **Chantier 5 confirmé** — Kirk p.55 met « too many functions / failed to focus » dans
   la liste des causes d'échec, au même rang que l'inaccessibilité.
3. **Nouveau** — la qualité de donnée est couverte sur **une dimension sur trois**
   (fraîcheur), et le DAG qui porterait les deux autres est **en pause en production**.
   Aucun des six trous du plan ne le disait.
