# `data_quality_check` : pourquoi il est en pause, et ce qu'il faudrait avant de le rallumer

> Enquête du 2026-08-23, décidée plutôt que le geste « dépauser ». Rien n'a été changé
> en production. Chaque chiffre vient d'une requête sur la base de prod ce jour.

## Le fait qui resserre la question

`is_paused = t`, **et `last_start` est vide : il n'a jamais tourné**. Ce n'est donc pas
« il a cassé et on l'a coupé » — c'est **« il n'a jamais été mis en service »**. Son code
n'a jamais été éprouvé contre une vraie base, et il envoie des alertes.

## Tâche 1 — `check_meta_ads_freshness` : elle passerait au VERT sur la source la plus périmée de la prod

Elle lit `MAX(collected_at) FROM meta_campaigns` et alerte au-delà de 48 h. Mesuré :

| Ce qu'elle lirait | Ce que la donnée dit vraiment |
|---|---|
| `MAX(collected_at)` = **il y a 8 h** ✅ | `MAX(day_date)` sur les insights = **2024-09-30**, soit **16 623 h** ❌ |

C'est **exactement** `freshness-measured-on-write-time`, la classe cataloguée le
2026-08-21 : le DAG Meta tourne et **réécrit les mêmes vieilles lignes**, donc la date
d'écriture avance chaque nuit pendant que la donnée a deux ans. `freshness_monitor` a été
corrigé pour lire `day_date` ; **ce DAG porte la version d'avant le correctif**.

Rallumer cette tâche ajouterait donc une **seconde voix qui contredit la bonne**, sur la
seule source réellement morte en production. C'est pire que rien.

Son second contrôle compte les campagnes `ACTIVE` : **0 sur 34**. C'est précisément la
condition que `expected_silence` / `meta_no_active_campaign` traite déjà, avec sa raison
mesurée.

→ **Verdict : superseded. À retirer, pas à réparer.**

## Tâche 2 — `check_spotify_data_consistency` : la seule implémentation d'Accuracy et Completeness du dépôt, et elle est inutilisable en l'état

Ses cinq contrôles sont exactement les dimensions que le corpus dit manquantes
(Reis & Housley p.90-91 ; *MLOps* p.12) :

| # | Contrôle | Dimension |
|---|---|---|
| 1 | artistes actifs sans aucune donnée S4A | Completeness |
| 2 | lignes de la timeline absentes du global | Consistency |
| 3 | **> 1 000 000 streams en un jour** | **Accuracy — valeurs aberrantes** |
| 4 | trous dans la timeline | Completeness |
| 5 | lignes dupliquées | Accuracy |

**Mais** : `s4a_song_timeline` est interrogée **5 fois, et aucune** des cinq ne porte le
filtre `AND song NOT ILIKE '%1x7xxxxxxx%'` que `CLAUDE.md` déclare **obligatoire** — la
ligne « Total » de chaque CSV S4A. Conséquence directe : le contrôle 3 se déclencherait
sur la ligne Total de tout artiste ayant du volume réel. Faux positif garanti.

Et le contrôle 1 remonterait **tout locataire qui utilise l'API sans jamais déposer de
CSV** — sur la flotte actuelle : Cuzebo, Benken, GRiNCH et le canari, soit 4 constats sur
6 locataires, chaque nuit, aucun actionnable.

Enfin la tâche **lève** (`raise ValueError(f'{len(issues)} problème(s) critique(s)')`),
donc le DAG partirait en `FAILED` dès la première nuit, et `check_dag_failures` en ferait
une alerte quotidienne.

→ **Verdict : à garder, à réécrire.** L'idée est juste et n'existe nulle part ailleurs ;
l'implémentation ne l'est pas.

## Ce que ça a révélé au passage, et qui compte plus

**La règle obligatoire du filtre S4A n'a AUCUN garde.** Mesuré : `s4a_song_timeline` est
mentionnée **109 fois** dans `src/` et `airflow/`, le filtre apparaît **30 fois**. Toutes
les mentions ne sont pas des requêtes, mais le rapport est assez large pour qu'une seule
requête oubliée soit invisible — et c'est déjà arrivé deux fois (`trigger_algo`, audit du
2026-06-11 : le coût par stream affiché était divisé par ~2).

Une règle écrite en prose et vérifiée par rien est une règle que le système n'a pas.

## Recommandation, dans l'ordre

1. **Ne pas dépauser.** (fait — rien n'a été changé)
2. **Écrire le garde du filtre S4A** — il protège 109 sites, pas seulement ce DAG.
3. **Retirer `check_meta_ads_freshness`** : `freshness_monitor` fait la même chose,
   correctement, et est déjà branché sur l'e-mail nocturne.
4. **Réécrire `check_spotify_data_consistency`** en `reported`, pas `guarded` : un
   détecteur neuf commence par se faire mesurer. Le registre `etl_run_log` du chantier 1
   donne déjà la Completeness par locataire (chute de `rows_inserted`) sans nouvelle
   requête.

---

## Le verdict, tranché par l'exécution — 2026-08-23 (soir), R46

Le DAG a été **lancé une fois à la main en production** (`airflow dags test`), sans être
dépausé, après les correctifs de R42. Il passe (`state=success`). Ce qu'il dit :

```
⏸️  Circuit ouvert — donnée S4A périmée de 77 j (dernier jour porté : 2026-06-07) :
    contrôles de qualité non exécutés.
```

Le circuit breaker fonctionne. Reste la question qu'il pose : **faut-il dépauser ?**

### Les trois mesures qui répondent

| Question | Mesure du 2026-08-23 |
|---|---|
| Depuis quand la source est-elle muette ? | Dernière écriture **2026-06-08**, dernier jour porté **2026-06-07**. Les deux s'accordent : personne n'a déposé de CSV S4A depuis 77 jours. |
| Qui a déjà déposé ? | **Le seul locataire 1 (admin)**, 13 794 lignes. Ni Benken, ni GRiNCH, ni le canari n'ont jamais déposé de CSV. |
| La flotte est-elle aveugle à cette péremption ? | **Non.** `freshness_monitor` la signale déjà, correctement : `stale: True`, `age_h: 1867`, `measured_on: 'metric'` — il lit `date`, pas `collected_at`. |

### Décision : rester en pause, et ce n'est plus une précaution

Dépausé, ce DAG **s'abstiendrait chaque nuit** — c'est la seule chose qu'il puisse faire
tant que la source est muette — et sa tâche `send_summary_notification` enverrait un
second e-mail quotidien à côté de l'alerte consolidée d'`alert_monitor`, sans porter un
seul constat neuf. **ADR-011** l'interdit explicitement : une alerte nomme un symptôme
visible par l'artiste ET une action possible. Celui-ci n'en nomme aucun des deux, et la
péremption qu'il constaterait est déjà dite ailleurs, mieux.

Ce n'est donc plus « on ne sait pas, alors on ne touche pas ». C'est **mesuré** : la
valeur du DAG est nulle tant que S4A ne reçoit rien, et son coût est un e-mail par nuit.

### Le déclencheur qui rouvre la question, pour qu'il puisse effectivement se produire

**Le jour où un artiste dépose un CSV S4A** — c'est-à-dire dès que
`freshness_monitor` cesse de marquer « Spotify S4A » comme `stale` — relancer
`airflow dags test data_quality_check <date>` à la main et lire ce que
`check_spotify_consistency` trouve pour de bon. Ses cinq contrôles restent la seule
implémentation d'Accuracy et de Completeness du dépôt ; ils n'ont simplement jamais eu
de données fraîches à juger.

Vérification du déclencheur, en une commande :
```bash
ssh root@167.233.92.1 'docker exec postgres_spotify_airflow psql -U postgres -d spotify_etl \
  -tAc "SELECT MAX(date) FROM s4a_song_timeline WHERE song NOT ILIKE '"'"'%1x7xxxxxxx%'"'"'"'
```
Tant que la réponse est `2026-06-07`, il n'y a rien à décider.

### Une chose apprise en le lançant

`airflow dags test` **exécute réellement** `send_summary_notification` : le test manuel a
envoyé un vrai e-mail de résumé. Ce n'est pas un défaut du DAG — c'est le comportement
d'Airflow — mais ça se sait avant de lancer, pas après.
