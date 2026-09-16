#!/usr/bin/env python3
"""Un service de conteneur ne se lie pas à la loopback DU CONTENEUR.

Classe `a-bind-address-that-hides-the-service`, trouvée le 2026-09-16 en écrivant la
pile d'observabilité.

`--web.listen-address=127.0.0.1:9090` avait été mis dans la commande de Prometheus pour
« ne pas l'exposer ». Mais c'est la loopback du CONTENEUR : ni le mappage
`ports: ['127.0.0.1:9090:9090']` ni Grafana — qui l'atteint par
`streamlytics_prometheus:9090` sur le réseau Docker — n'auraient pu s'y connecter. La
restriction voulue venait déjà du mappage ; celle du binaire coupait tout le monde.

Ce qui rend la classe méchante est la DISTANCE entre la cause et le symptôme : le
conteneur est sain, le service tourne, ses journaux sont propres — et c'est un panneau
Grafana vide qu'on regarde trois jours plus tard en concluant que la métrique n'existe
pas.

⚠️ Le chargeur tolère `!override` et `!reset`, que Docker Compose comprend et que PyYAML
refuse. Sans eux ce script lèverait sur `deploy/docker-compose.replica.yml` — une
signature qui plante ne garde rien.
"""
import pathlib
import re
import sys
import yaml


class T(yaml.SafeLoader):
    pass


for tag in ("!override", "!reset"):
    T.add_constructor(tag, lambda ld, n: (ld.construct_sequence(n, deep=True)
                                          if isinstance(n, yaml.SequenceNode) else None))

pat = re.compile(r"--(?:web|http)[.-]listen-address[= ]127\.0\.0\.1")
bad = []
for f in sorted(pathlib.Path("deploy").glob("docker-compose*.y*ml")):
    doc = yaml.load(f.read_text(encoding="utf-8"), Loader=T) or {}
    for name, svc in (doc.get("services") or {}).items():
        if any(pat.search(str(c)) for c in (svc.get("command") or [])):
            bad.append(f"{f.name}::{name}")
print(*bad, sep="\n")
sys.exit(1 if bad else 0)
