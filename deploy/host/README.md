# `deploy/host/` — la configuration de l'HÔTE, versionnée

Ce dossier porte les fichiers qui vivent **hors des conteneurs**, sur le VPS lui-même.
Ils ne sont appliqués par aucun `docker compose` : ils se copient et se rechargent à la
main, et c'est précisément pourquoi ils sont ici.

Le dépôt a déjà payé la classe `une-configuration-qui-diverge-de-la-prod` : un fichier
modifié directement sur la cible n'est comparé à rien, et la dérive se découvre des
semaines plus tard. `deploy/Caddyfile` est le précédent — il est comparé **octet pour
octet** avec `/etc/caddy/Caddyfile` par `make sync-check`.

## `docker-daemon.json` → `/etc/docker/daemon.json`

**Le défaut qu'il ferme**, mesuré le 2026-09-16 : il n'existait **aucun**
`/etc/docker/daemon.json` sur le VPS. Docker utilise alors le pilote `json-file` **sans
aucune limite de taille** : les journaux de conteneurs grossissent jusqu'à remplir le
disque. Relevé ce jour-là, sur un disque à 49 % :

```
14M  …/38ef39ad…-json.log
8.4M …/c86fa6b4…-json.log
2.1M …/ed878e96…-json.log
```

Ce n'est pas encore un incident — c'est une croissance que rien ne borne, sur la seule
machine du produit, et le seul contrôle de disque qui existe (`tools/infra_health_cron.sh`,
seuil 85 %) est un **booléen quotidien** qui dirait « plein » sans dire pourquoi.

### ⚠️ `reload` NE SUFFIT PAS — mesuré, après l'avoir écrit faux

La première version de ce fichier affirmait : *« `reload` suffit pour les options de
journalisation et ne coupe rien »*. **C'est faux, et la mesure l'a montré en trente
secondes.**

Protocole, rejouable :

```bash
docker run -d --name rotatest alpine sh -c 'i=0; while [ $i -lt 400000 ]; do echo "…"; i=$((i+1)); done'
sleep 30
ls -la /var/lib/docker/containers/$(docker inspect -f '{{.Id}}' rotatest)/ | grep json.log
docker rm -f rotatest
```

Après `scp` du fichier **et** `systemctl reload docker`, le conteneur témoin a produit
**un seul fichier de 65 Mo**, sans aucun `…-json.log.1`. La rotation n'était pas active.
Le démon avait bien le fichier, il n'en avait pas pris les options.

Et `docker inspect <conteneur> --format '{{json .HostConfig.LogConfig}}'` **ne sait pas
répondre** : il rend `{"Type":"json-file","Config":{}}` — la surcharge PROPRE au
conteneur, vide, pas le défaut effectif du démon. Vérifier par là aurait donné une
réponse rassurante et fausse. C'est la classe « mesurer un artefact là où la question
est un effet ».

**Application, corrigée** :

```bash
scp deploy/host/docker-daemon.json root@167.233.92.1:/etc/docker/daemon.json
ssh root@167.233.92.1 'systemctl restart docker'     # ⚠️ COUPE tous les conteneurs
```

⚠️ **`restart` est une interruption de service délibérée**, d'environ trente secondes.
Les conteneurs portent `restart: unless-stopped` et reviennent seuls, mais le site est
indisponible pendant l'opération. À faire en heure creuse, jamais pendant qu'un artiste
teste, et **jamais pendant une collecte Airflow** (23 h UTC).

**Vérification — l'EFFET, pas le fichier** :

```bash
# 1. le demon porte la configuration
ssh root@167.233.92.1 'cat /etc/docker/daemon.json'

# 2. et la rotation se produit VRAIMENT (le seul test qui tranche)
ssh root@167.233.92.1 'docker run -d --name rotatest alpine sh -c "i=0; while [ \$i -lt 400000 ]; do echo x; i=\$((i+1)); done"; sleep 30; ls /var/lib/docker/containers/$(docker inspect -f "{{.Id}}" rotatest)/ | grep -c json.log; docker rm -f rotatest'
#    2 fichiers ou plus  ->  rotation ACTIVE
#    1 seul fichier      ->  le demon n a pas pris les options
```
