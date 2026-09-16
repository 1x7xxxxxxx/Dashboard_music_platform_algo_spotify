"""Un service déployé sans sonde de santé est déployé sans filet.

Type: Test
Uses: pytest, re, subprocess
Depends on: tools/deploy.sh, deploy/Caddyfile
Persists in: nothing

Ce qui est en jeu
-----------------
`tools/deploy.sh` reconstruit `$SERVICES`, puis sonde la santé de chacun et revient en
arrière si une sonde reste rouge. La sonde était choisie par un `case` dont la branche
par défaut était **`*) continue`** : un service demandé mais absent du `case` traversait
tout le déploiement **sans aucune vérification**, et le script sortait en 0.

Tant qu'il n'y avait que `api` et `dashboard`, les deux branches existaient et le trou
ne se voyait pas. Le jour où une seconde réplique arrive (R114), c'est exactement ce qui
se serait passé : `dashboard2` reconstruite, jamais sondée, jamais couverte par un
retour arrière — et Caddy y envoyant du trafic par cookie.

Trouvé par `code-critic` sur le DESIGN de R114, avant qu'une ligne soit écrite.

Le second défaut, plus discret
------------------------------
`rollback()` recevait le service en cause en argument et reconstruisait quand même
`$SERVICES` en entier. À deux répliques, l'échec de l'une aurait reconstruit **les
deux** sous trafic : couper le site pour réparer une moitié.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY = _ROOT / "tools" / "deploy.sh"
_CADDY = _ROOT / "deploy" / "Caddyfile"

_UPSTREAM = re.compile(r"\b127\.0\.0\.1:(\d{2,5})\b")


def _source() -> str:
    return _DEPLOY.read_text(encoding="utf-8")


def _probed_ports() -> set[str]:
    """Les ports que `service_probe()` sait sonder."""
    src = _source()
    i = src.index("service_probe()")
    j = src.index("\n}", i)
    return set(_UPSTREAM.findall(src[i:j]))


def _caddy_upstream_ports() -> set[str]:
    """Les ports vers lesquels Caddy envoie du trafic, lignes NON commentées."""
    if not _CADDY.is_file():
        return set()
    out: set[str] = set()
    for line in _CADDY.read_text(encoding="utf-8").splitlines():
        bare = line.strip()
        if bare.startswith("#") or not bare.startswith("reverse_proxy"):
            continue
        out.update(_UPSTREAM.findall(bare))
    return out


def test_every_caddy_upstream_has_a_health_probe() -> None:
    """Tout amont qui reçoit du trafic est sondé par le déploiement.

    C'est LE lien que rien ne faisait : l'un vit dans `deploy/Caddyfile`, l'autre dans
    `tools/deploy.sh`. Ajouter une réplique à Caddy sans sonde la met en service sans
    filet, et le déploiement sort quand même en 0.
    """
    served = _caddy_upstream_ports()
    probed = _probed_ports()
    assert served, "aucun amont lu dans `deploy/Caddyfile` — la lecture est cassée"
    missing = sorted(served - probed)
    assert not missing, (
        f"Caddy envoie du trafic vers {missing} et `tools/deploy.sh` ne sait pas "
        f"sonder ce(s) port(s) (il sonde {sorted(probed)}).\n\n"
        "Conséquence : cette instance est reconstruite et remise en service sans "
        "vérification de santé, et n'est couverte par aucun retour arrière — le "
        "déploiement sort en 0 quoi qu'il arrive.\n"
        "Remède : ajouter sa ligne dans `service_probe()`."
    )


def test_an_unknown_service_is_refused_not_skipped() -> None:
    """Demander un service sans sonde doit ARRÊTER, jamais être ignoré en silence."""
    src = _source()
    assert "n'a pas de sonde de sante dans ce script" in src, (
        "le refus explicite d'un service inconnu a disparu de `tools/deploy.sh`"
    )
    i = src.index("service_probe()")
    j = src.index("\n}", i)
    assert '*)          echo "" ;;' in src[i:j], (
        "`service_probe()` ne rend plus la chaîne vide sur un service inconnu — "
        "le refus en amont ne peut plus se déclencher."
    )


def test_the_health_gate_no_longer_skips_silently() -> None:
    """La boucle de santé n'a plus de branche qui passe son tour sans rien dire."""
    src = _source()
    i = src.index("# Health gates")
    j = src.index("rollback \"$s\"", i)
    gate = src[i:j]
    assert "continue" not in gate, (
        "la porte de santé porte de nouveau un `continue` : un service y traverserait "
        "le déploiement sans être sondé.\n" + gate[:400]
    )


def test_the_rollback_rebuilds_the_failing_service_only() -> None:
    """Un retour arrière ne coupe pas ce qui marche encore.

    À deux répliques, reconstruire `$SERVICES` en entier pour l'échec de l'une revient
    à couper le site pour réparer une moitié.
    """
    src = _source()
    i = src.index("rollback() {")
    j = src.index("\n}", i)
    body = src[i:j]
    assert 'docker compose up -d --build "$_svc"' in body, (
        "le retour arrière ne reconstruit plus seulement le service en cause :\n"
        + body[:500]
    )
    assert "--build $SERVICES" not in body, (
        "le retour arrière reconstruit toute la liste des services — à deux "
        "répliques, l'échec de l'une couperait les deux."
    )


def test_the_script_still_parses() -> None:
    """Non-vacuité : un `deploy.sh` cassé ferait passer tout ce fichier sur du texte."""
    import subprocess

    r = subprocess.run(["bash", "-n", str(_DEPLOY)], capture_output=True, text=True)
    assert r.returncode == 0, f"`bash -n tools/deploy.sh` échoue :\n{r.stderr}"


# ─────────────────────────────────────────────────────────────────────────────
# La seconde réplique : versionnée, et ARRÊTÉE par défaut
# ─────────────────────────────────────────────────────────────────────────────

def _compose() -> dict:
    import pytest

    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(
        (_ROOT / "docker-compose.example.yml").read_text(encoding="utf-8")) or {}


def test_the_replica_is_versioned_and_not_started_by_default() -> None:
    """Elle existe dans le dépôt, et `docker compose up -d` ne la lève pas.

    Les deux moitiés comptent. **Versionnée** : sans définition dans le dépôt, la
    seconde instance serait un geste manuel sur le VPS — invisible à qui relit le code,
    invisible à `make sync-check`, et le vrai `docker-compose.yml` de prod est
    gitignoré par construction. **Arrêtée** : c'est une EXPÉRIENCE (R114), pas l'état
    nominal ; la lever par défaut changerait le développement local et la production
    sans que personne ne l'ait demandé.

    `profiles` est ce qui tient les deux à la fois.
    """
    svc = (_compose().get("services") or {}).get("dashboard2")
    assert svc, (
        "`dashboard2` a disparu de `docker-compose.example.yml`. La seconde réplique "
        "redeviendrait un geste manuel non versionné sur le VPS."
    )
    assert svc.get("profiles"), (
        "`dashboard2` n'est plus derrière un `profiles:` — `docker compose up -d` la "
        "démarrerait, en local comme en production. Ce n'est pas l'état nominal."
    )
    ports = " ".join(str(p) for p in (svc.get("ports") or []))
    assert "8511" in ports, f"la réplique n'expose plus 8511 : {ports}"
    assert svc.get("container_name") != "streamlytics_dashboard", (
        "la réplique porte le nom du conteneur d'origine — elle le remplacerait."
    )


def test_the_replica_shares_the_image_and_the_data_bind() -> None:
    """Même image, même `./data` — sinon ce n'est pas une réplique.

    Une seconde instance construite autrement, ou pointant ailleurs, ne mesure pas ce
    que R114 prétend mesurer : elle mesure deux applications différentes.
    """
    services = _compose().get("services") or {}
    ref, rep = services.get("dashboard") or {}, services.get("dashboard2") or {}
    assert rep.get("build") == ref.get("build"), (
        f"la réplique ne se construit plus comme l'originale : "
        f"{rep.get('build')} vs {ref.get('build')}"
    )
    assert sorted(rep.get("volumes") or []) == sorted(ref.get("volumes") or []), (
        "les montages diffèrent — les archives d'upload cesseraient d'être cohérentes "
        "entre les deux instances."
    )


# ─────────────────────────────────────────────────────────────────────────────
# La surcharge de production — ce que `check-yaml` ne peut plus vérifier
# ─────────────────────────────────────────────────────────────────────────────
#
# `deploy/docker-compose.replica.yml` est exclu de `check-yaml` : il porte
# `ports: !override`, que Docker Compose comprend et que PyYAML refuse. L'exemption
# déplace la vérification ici plutôt que de la supprimer — une exemption qui ne
# déplace rien est un trou.

_REPLICA_OVERRIDE = _ROOT / "deploy" / "docker-compose.replica.yml"


def _load_with_compose_tags() -> tuple[dict, set[str]]:
    """Le fichier, et l'ensemble des CHEMINS portant un tag `!override` / `!reset`.

    Le loader retient les tags qu'il a vus, et c'est la seule façon de les tester :
    PyYAML les consomme, donc le document chargé est IDENTIQUE avec ou sans eux. Une
    première version de ce test lisait la liste des ports et restait verte quand on
    retirait `!override` — elle vérifiait la valeur, jamais le tag, alors que c'est le
    tag qui décide si `extends` fusionne ou remplace.
    """
    import pytest

    yaml = pytest.importorskip("yaml")
    seen: set[str] = set()

    class _Tolerant(yaml.SafeLoader):
        pass

    def _override(loader, node):
        seen.add("override")
        return loader.construct_sequence(node, deep=True)

    def _reset(loader, node):  # noqa: ARG001
        seen.add("reset")
        return None

    _Tolerant.add_constructor("!override", _override)
    _Tolerant.add_constructor("!reset", _reset)
    doc = yaml.load(_REPLICA_OVERRIDE.read_text(encoding="utf-8"), Loader=_Tolerant)
    return doc or {}, seen


def test_the_production_override_publishes_only_the_replica_port() -> None:
    """La réplique publie 8511, et SURTOUT pas 8501.

    Mesuré le 2026-09-16 : sans `!override`, `extends` FUSIONNE les listes, donc la
    réplique héritait `127.0.0.1:8501:8501` de l'originale EN PLUS du sien. Docker a
    refusé de la démarrer — « port is already allocated ». Le symptôme nommait le bon
    port et la mauvaise cause : ce n'était pas un conflit entre deux services, c'était
    un héritage.
    """
    doc, tags = _load_with_compose_tags()
    svc = (doc.get("services") or {}).get("dashboard2") or {}
    ports = [str(x) for x in (svc.get("ports") or [])]
    assert ports, "la surcharge ne publie plus aucun port — Caddy ne l'atteindra pas"
    assert "override" in tags, (
        "`ports:` n'est plus marqué `!override`. Sans ce tag, `extends` FUSIONNE les "
        "listes : la réplique hérite `127.0.0.1:8501:8501` de l'originale EN PLUS du "
        "sien, et Docker refuse de la démarrer (« port is already allocated »). Le "
        "fichier chargé est identique dans les deux cas — seul le tag fait la "
        "différence, donc c'est le tag qu'il faut vérifier."
    )
    assert any("8511" in p for p in ports), f"8511 absent : {ports}"
    assert not any(":8501:" in p or p.startswith("127.0.0.1:8501") for p in ports), (
        f"la réplique publie le port de l'originale : {ports}. `extends` fusionne les "
        "listes — il faut `ports: !override`, sinon le conteneur refuse de démarrer."
    )


def test_the_override_extends_from_the_project_root() -> None:
    """`extends.file` se résout depuis le RÉPERTOIRE DU PROJET, pas depuis ce fichier.

    Écrit `../docker-compose.yml`, il a cherché `/opt/docker-compose.yml` en production
    et rendu `no such file or directory`.
    """
    doc, _ = _load_with_compose_tags()
    svc = (doc.get("services") or {}).get("dashboard2") or {}
    ref = (svc.get("extends") or {}).get("file", "")
    assert ref == "docker-compose.yml", (
        f"`extends.file` vaut {ref!r}. Il se résout depuis le répertoire du projet — "
        "celui du PREMIER `-f` — donc un `../` le fait sortir du dépôt."
    )
