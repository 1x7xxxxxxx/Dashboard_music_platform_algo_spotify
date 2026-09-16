# ADR-026 — L'observabilité est adoptée pour SURVEILLER les déclencheurs, pas parce qu'un utilisateur s'est plaint

- **Status:** Accepted — **supersede ADR-002 §4** (« Observability: keep
  `docker-compose logs` + the existing email alert system. No Prometheus / Grafana /
  OpenTelemetry. »)
- **Date:** 2026-09-16
- **Deciders:** @1x7xxxxxxx

## Context

ADR-002 a refusé, le 2026-05-14, la pile d'observabilité du projet Airbus
`msdr_predictive_maintenance`. Le refus était **juste à la date où il a été écrit**, et
son raisonnement tient toujours :

> « A Prometheus+Grafana stack here would be **~5 services** in `docker-compose.yml` for
> **two dashboards nobody watches**. Defer until there is an actual operator role to
> consume them. » — ADR-002:63

ADR-002 s'est donné trois déclencheurs de réouverture : des **données régulées**, une
architecture **multi-région avec des SLA durs**, ou des **plaintes d'utilisateurs pour
la latence**. Le 2026-08-21, la ré-évaluation notait pour le §4 : *« aucune plainte ;
requêtes mesurées à 0,4 ms »*.

**Aucun des trois n'est tiré aujourd'hui, et cet ADR ne prétend pas le contraire.** Le
premier parcours artiste complet a produit ~20 remarques, **aucune sur la lenteur**.

### Ce qui a changé, et qui n'est aucun des trois déclencheurs

**1. Trois ADR reposent sur des déclencheurs que rien n'observe.** ADR-007 le dit
lui-même, dans sa propre section « conséquence négative » :

> « **A trigger nobody watches is a decision nobody revisits.** Three of the four
> triggers are load-related and this product has one live tenant, so in practice they
> will fire when the first real traffic arrives — which is also when they will be
> obvious. » — ADR-007

Cette phrase décrit un pari : que le franchissement sera *évident*. Le 2026-09-16 a
montré qu'il ne l'est pas. Le seuil de R87 (« p50 > 200 ms à 12 rendus ») a été **lu
avec un instrument différent de celui qui l'avait défini** — deux échelles, un seuil
transporté, classe `a-threshold-carried-across-instruments`. Et la requête de sessions
du même déclencheur comptait les canaris et le bac à sable : **320 des 1 043 événements
(31 %) venaient de nous**.

**2. La mesure qui devait conclure R114 est ambiguë, et son instrument est cassé.**
Doubler les instances divise le p50 par 2,25 à 24 onglets, mais les « reruns perdus » ne
suivent pas. L'audit de `tools/loadtest_concurrency.py` a ensuite établi que cette
colonne mélange trois causes dont une seule parle du serveur, que le marqueur
(`stStatusWidget`) sert aussi à l'état de connexion websocket, et que le p50 est calculé
**sur les seuls survivants** — 68 à 82 % des échantillons censurés à 24 onglets.

**3. Il n'existe aucun chiffre de latence côté serveur.** Caddy ne voit pas les reruns
(ils passent dans le websocket, dont la durée p50 de session est de 252 s). Le seul
chronomètre applicatif (`src/dashboard/app.py:975`) mesure `_render_page` **hors barre
latérale** — or le rendu par vue est de 61 ms contre 468-538 ms pour la page complète,
un facteur 8 que personne ne voit. Et il n'est ni persisté ni exposé.

**4. Le précédent du §7 de la même ADR.** ADR-002 avait rejeté l'automatisation de la
reprise après sinistre. La ré-évaluation du 2026-08-21 a constaté : *« **dépassé par les
faits** : cron `pg_dump` actif en production, 17 sauvegardes sur disque, plus
`make backup-test`. **L'ADR n'avait pas été mis à jour.** »* Le §4 est aujourd'hui dans
la même situation — `R115` est une tâche ouverte de la roadmap active — et cet ADR
existe pour que le refus ne soit pas contredit **en silence** une seconde fois.

## Decision

streaMLytics adopte **trois conteneurs** — `prometheus`, `grafana`, `node_exporter` — et
instrumente ses deux processus applicatifs avec `prometheus_client`, **dans le seul but
de rendre observables les déclencheurs sur lesquels ADR-002, ADR-007 et ADR-014 reposent
déjà**.

Ce n'est pas l'adoption de la pile msdr. C'est l'adoption du **minimum qui transforme
des seuils écrits en seuils surveillés**.

### Ce que les objections d'ADR-002 deviennent

| Objection d'ADR-002 | Réponse, vérifiable |
|---|---|
| « ~5 services » | **3**. Pas d'OpenTelemetry, pas de collecteur, pas de `cadvisor`, pas de `postgres_exporter` — le pool de connexions est instrumenté par notre propre code, qui le connaît mieux qu'un exportateur générique |
| « two dashboards **nobody watches** » | Faux depuis : le produit porte **quatre** vues de surveillance (`perf_monitor`, `db_health`, `airflow_kpi`, le bloc santé d'`admin`). Elles seront **retirées** au profit de Grafana — le solde net de code est **négatif** |
| « Defer until there is an actual **operator role** » | Le rôle existe et c'est le propriétaire : il lit déjà ces quatre vues, et il a demandé cette pile. Ce qui manquait n'était pas le lecteur, c'était le chiffre |

### Périmètre, arrêté

* **Quatre familles de métriques**, pas quarante : durée de rendu (histogramme, avec la
  phase `chrome` / `vue` que le chronomètre actuel omet), reruns en cours, connexions du
  pool, erreurs par page.
* **Grafana écoute sur `127.0.0.1` uniquement.** Accès par tunnel SSH. Aucune surface
  publique, aucun identifiant supplémentaire à durcir, aucun sous-domaine.
* **Rétention Prometheus : 30 jours.** Un **résumé quotidien** part dans Postgres
  (`daily_ops_metrics`), écrit par une tâche du DAG `alert_monitor` qui existe déjà.
* **Les alertes obéissent à ADR-011** — un symptôme observable ET une action faisable ce
  soir — et passent par le canal mail existant, **pas** par un Alertmanager de plus.
* **Les tableaux sont versionnés** (`deploy/grafana/dashboards/`), jamais cliqués dans
  l'interface : un tableau cliqué meurt avec le volume.

## Consequences

### Positive
- Les déclencheurs d'ADR-007 (rendu > 1,5 s sur `trigger_algo`, > 1 s sur
  `onboarding_health`) et d'ADR-014 (agrégat > 1 s) deviennent **surveillés** au lieu
  d'être seulement écrits.
- Le facteur 8 entre le rendu d'une vue et celui d'une page complète devient visible,
  donc attaquable. Il ne l'était pas.
- R119 (réparer la mesure client) obtient sa référence : croiser l'histogramme serveur
  avec le compte client est **le seul moyen** de dire si un « rerun perdu » est un
  défaut du serveur ou de l'instrument.
- Le solde de code est négatif : quatre vues retirées contre un module d'instrumentation.

### Negative / Trade-offs
- **Trois conteneurs de plus** sur une machine qui en porte déjà six. Budget vérifié :
  4,48 Go disponibles, 75 Go de disque libre, 4 cœurs, charge 0,48 ; les trois pèsent
  ~500-700 Mo quand Airflow en consomme 1,9 Go à lui seul.
- **Un port d'écoute dans le processus Streamlit.** C'est le point qui casse : Streamlit
  ré-exécute son script à chaque rerun, et sans drapeau de module le second rerun tente
  de relier le port et lève.
- Une surface d'exploitation de plus à maintenir, sauvegarder et un jour retirer.
- **Ce que ça ne donne pas** : ni traces distribuées, ni corrélation inter-services, ni
  logs structurés. Chacun a son déclencheur ci-dessous.

### Neutral / Operational
- `opentelemetry-api` et `opentelemetry-exporter-otlp` sont **déjà** dans `uv.lock`
  comme dépendances transitives d'`apache-airflow`, sans qu'aucun code du dépôt les
  utilise. Cet ADR ne les active pas.
- Une skill `observability-engineer` a été **retirée** (`.claude/.retired/skills/`).
  Rien ne la réactive ici.
- ⚠️ **REX importé de msdr, et il a coûté une panne là-bas** : `GF_INSTALL_PLUGINS`
  fait appeler grafana.com **au démarrage**, donc Grafana ne boote pas hors ligne
  (classe `b-grafana-offline-boot`). La variable reste vide.
- ⚠️ **La contamination msdr est un risque mesuré ici** : la sonde Docker du hook Stop a
  déjà viré au vert **parce que des conteneurs `msdr_*` tournaient sur cette machine**
  pendant que `postgres_spotify_airflow` était à terre. La configuration de scrape ne
  vise que des cibles nommées explicitement, jamais une découverte automatique.

## Alternatives rejected

| Option | Pourquoi rejetée |
|---|---|
| **Ne rien faire, attendre un déclencheur d'ADR-002** | Les trois déclencheurs (données régulées, multi-région, plainte de latence) ne décrivent pas le problème rencontré. Attendre reviendrait à laisser trois ADR reposer sur des seuils que rien ne lit — ce qu'ADR-007 nomme lui-même comme sa faiblesse |
| **La pile msdr complète** (Prometheus + Grafana + OTel + QuestDB) | C'est exactement le « ~5 services » d'ADR-002, et msdr n'est pas comparable : attaché au matériel, contraintes de sécurité machine, rejeu déterministe, pas d'opérateur d'astreinte |
| **Tout stocker dans Postgres, pas de TSDB** | Une écriture par rendu sur le chemin chaud, et Grafana moins à l'aise. Le résumé quotidien donne la traçabilité longue sans le coût |
| **Prometheus seul, sans Postgres** | La traçabilité mourrait avec le conteneur, et rien ne serait interrogeable en SQL à côté des données métier |
| **Exposer Grafana sur un sous-domaine** | Une surface publique et un jeu d'identifiants de plus, pour un lecteur unique qui a déjà un accès SSH |
| **`cadvisor` / `postgres_exporter`** | `node_exporter` plus nos propres métriques répondent à la question posée. Déclencheur d'adoption : une question par conteneur, ou sur les internes de Postgres, à laquelle ils ne savent pas répondre |
| **Alertmanager** | Le canal mail d'`alert_monitor` existe et obéit déjà à ADR-011. Déclencheur : plus de ~10 règles, ou un besoin d'astreinte |
| **Loki** | La rotation `json-file` posée en même temps suffit tant qu'on lit peu de logs. Déclencheur : un incident que les métriques ne suffisent pas à expliquer |

## Déclencheur de relecture de CET ADR

Cet ADR se relit si **l'une** de ces trois conditions tient :

1. la pile dépasse **6 conteneurs** ou **10 règles d'alerte** — le signe qu'elle a
   grossi toute seule, ce qui est le risque propre de ce genre de chantier ;
2. **aucun tableau Grafana n'a été ouvert pendant 60 jours** — l'objection « nobody
   watches » d'ADR-002 serait alors redevenue vraie, et il faudrait retirer la pile,
   pas la garder par habitude ;
3. les métriques n'ont permis de trancher **aucun** des déclencheurs d'ADR-007 ni
   l'ambiguïté de R114 — auquel cas elles mesurent la mauvaise chose.

La condition 2 est la plus importante, et c'est celle qu'on oublie : **une pile
d'observabilité que personne ne regarde est exactement ce qu'ADR-002 refusait.**
