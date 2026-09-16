# Ce que chaque vue de surveillance montrait → où c'est dans Grafana

> **Condition bloquante de R115 étape 6.** Le plan prévoyait de retirer quatre surfaces
> (`perf_monitor`, la partie santé de `db_health`, celle d'`airflow_kpi`, le bloc santé
> d'`admin`) « après vérification que Grafana couvre chaque chiffre ». Ce document EST
> cette vérification. Il est écrit avant toute suppression, et il en contredit la moitié.

Établi le 2026-09-16, contre `deploy/grafana/dashboards/streamlytics-ops.json` (9 panneaux).

---

## Le constat qui change le plan

**Trois des quatre surfaces ne font pas doublon.** Le plan les rangeait ensemble parce
qu'elles sont toutes admin et qu'elles affichent toutes des voyants ; c'est une
ressemblance d'aspect, pas de sujet. Lues, elles répondent à des questions que Grafana
ne pose pas et ne devrait pas poser.

| Vue | Ce qu'elle répond vraiment | Grafana peut-il ? | Verdict |
|---|---|---|---|
| `perf_monitor` | Combien de temps met une page à se rendre, et cette machine tient-elle | **Oui** (voir le détail ci-dessous) | **Doublon — à retirer**, sous une condition |
| `db_health` | Les jeux de données de CE locataire sont-ils frais, et leurs imports grossissent-ils | **Non** | À garder |
| `airflow_kpi` | Quel DAG a tourné, avec quel taux de succès, et l'insertion a-t-elle eu lieu | **Non** | À garder |
| `admin` § « 🩺 Technique » | La fraîcheur par plateforme, **par locataire** | **Non** | À garder |

La raison est la même pour les trois : ce sont des données **métier et par locataire**,
lues depuis Postgres. Prometheus est une base de séries temporelles d'infrastructure ;
y faire entrer « le locataire 12 n'a pas reçu de CSV Apple depuis 9 jours » demanderait
une étiquette par locataire sur des métriques d'infrastructure — c'est-à-dire une
cardinalité qui croît avec le nombre de clients, exactement ce qu'on ne met pas dans
Prometheus. Et aucun exportateur Airflow n'a été installé : ADR-026 n'en prévoit pas.

**Le solde de code de l'étape 6 est donc `-181` lignes (`perf_monitor.py`), pas les
quatre surfaces annoncées.** Le dire est le point : un plan qu'on exécute sans le
relire fait disparaître des vues utiles pour tenir un chiffre qu'il a lui-même écrit.

---

## `perf_monitor.py` — ligne à ligne

| Ce que la vue montre | Où c'est dans Grafana | Fidèle ? |
|---|---|---|
| **Dernier rendu** (ms, badge vert/orange/rouge) | Panneau 1 « Latence de rendu — CHROME vs VUE (p95) » | **Mieux.** La vue montre UN rendu, celui de l'admin qui regarde. Le panneau montre le p95 de toutes les sessions. |
| **Historique session par page** (moy / max / min, tableau) | Panneau 7 « Latence de rendu — PAR PAGE (p95) », ajouté pour cette correspondance | **Mieux, et c'est mesuré.** La vue ne comptait que la phase `view` — 61 ms, quand la page complète en prend 468-538. Un facteur ~8 que la vue n'affichait pas. |
| **Sparkline des 100 derniers rendus** | Panneaux 1 et 7 (séries temporelles) | Équivalent, sur une fenêtre choisie au lieu de 100 points. |
| **Log brut (100 derniers rendus)** | — | **Perdu, et assumé.** Un journal ligne à ligne n'est pas une métrique ; le remplacer demanderait Loki, dont ADR-026 écarte l'adoption avec son déclencheur. |
| **RAM process** (RSS psutil, seuil 800 Mo) | Panneau 8 « Processus — RAM résidente » | Équivalent. La série vient du collecteur que `prometheus_client` enregistre **par défaut** — rien à instrumenter, et pas de `cadvisor` : son déclencheur d'ADR-026 n'a pas été tiré. |
| **CPU process** (psutil sur 0,1 s) | Panneau 9 « Processus — CPU » | **Mieux.** `interval=0.1` mesure un dixième de seconde pris au hasard ; le panneau donne un taux sur 5 min. |
| **DB ping** (`SELECT 1` aller-retour) | — | **Perdu, délibérément.** Voir ci-dessous. |
| **Tableau des seuils** (1 s / 3 s, 800 Mo, 70 %) | `deploy/prometheus/rules/streamlytics.yml` | Déplacé, et devenu actif : un seuil écrit dans un tableau Markdown ne déclenche rien. |

### Pourquoi le « DB ping » n'est pas réinstrumenté

C'est le seul chiffre réellement abandonné, et l'abandon se défend plutôt qu'il ne se
subit :

1. **C'est un échantillon unique, pris par la mauvaise personne.** Le ping se mesurait
   au moment où un admin ouvrait la page. Il décrit le chemin réseau de l'admin, à cet
   instant — pas celui des artistes pendant la journée.
2. **La question a déjà deux meilleures réponses.** Un Postgres lent se voit dans la
   latence de rendu (panneau 1, toutes sessions) et dans
   `streamlytics_postgres_pool_connections{state="direct_fallback"}` (panneau 3), qui
   compte les fois où le pool était vide — un fait, pas une impression.
3. **Le réinstrumenter coûterait une requête par rendu** sur le chemin chaud, pour une
   grandeur que les deux panneaux ci-dessus encadrent déjà.

Déclencheur de réouverture : un incident où la latence de rendu est normale et où
Postgres est pourtant en cause.

---

## La condition qui reste avant de supprimer

Les panneaux 7, 8 et 9 existent ; **les panneaux 1 et 7 sont VIDES au 2026-09-16**, et
c'est attendu : `streamlytics_rerun_duration_seconds` ne reçoit d'observation qu'au
premier rendu **authentifié**. Les routes publiques (connexion, inscription,
vérification) font `st.stop()` avant la couture — délibérément, elles ne rendent aucune
vue. Personne ne s'est connecté depuis la mise en service de l'instrument.

> **Retirer `perf_monitor.py` avant qu'un panneau ait porté un chiffre reviendrait à
> remplacer une surface qui marche par une surface vide.** Une figure vide se lit « tout
> va bien », et ce dépôt a déjà payé cette lecture.

Le geste qui lève la condition tient en une phrase : **se connecter une fois au tableau
de bord et naviguer sur deux ou trois pages**, puis vérifier —

```bash
ssh root@167.233.92.1 \
  'curl -s --get localhost:9090/api/v1/query \
     --data-urlencode "query=sum by (page, phase) (streamlytics_rerun_duration_seconds_count)"'
```

Une réponse non vide, avec au moins une page et les deux phases `chrome` et `view`,
autorise la suppression. Tant qu'elle est vide, `perf_monitor` reste — et
`src/dashboard/utils/metrics_seam.py:record_session_render()` continue de l'alimenter,
ce que son docstring dit déjà.
