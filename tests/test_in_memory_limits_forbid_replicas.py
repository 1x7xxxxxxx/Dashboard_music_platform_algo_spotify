"""Des compteurs en MÉMOIRE de processus interdisent une seconde réplique.

Type: Test
Uses: pytest, ast, yaml, re
Depends on: src/dashboard/utils/throttle.py, src/api/security.py,
            docker-compose*.yml, deploy/Caddyfile, tools/deploy.sh
Persists in: nothing

Ce qui est en jeu, et pourquoi c'est un test et pas une phrase
--------------------------------------------------------------
Les budgets anti-force-brute du produit sont exacts **parce qu'il y a un processus par
surface**. `src/utils/request_throttle.py:22-24` le dit : « The counters are per-process
and reset on restart — deliberate … Both the uvicorn API and the Streamlit dashboard run
as one process each, so "per process" is "per surface". »

Le jour où une seconde réplique apparaît, cette phrase devient fausse **sans que rien ne
change dans le code des limiteurs** : le budget de connexion passe de `LOGIN_MAX` à
`LOGIN_MAX × N`, sur un chemin d'authentification, en silence. Aucun test existant ne
relie les deux faits — l'un vit dans `docker-compose`, l'autre dans `throttle.py`.

C'est exactement la forme que ce dépôt attrape le plus souvent : deux endroits qui
doivent s'accorder et que rien ne compare. La différence ici est que la divergence n'est
pas cosmétique, elle **affaiblit une protection**.

Ce que ce garde N'exige PAS
---------------------------
Il n'interdit pas les répliques, et il n'impose pas Redis. Il interdit **la combinaison**.
Trois sorties le satisfont, et le choix reste ouvert :

1. rester à une réplique (l'état d'aujourd'hui, justifié par la mesure — R87 est close
   sur un pic de 12 sessions/minute contre un seuil de 20) ;
2. déplacer les compteurs dans un magasin partagé (Postgres, Redis) ;
3. rendre l'affinité de session obligatoire ET prouver que la même IP retombe toujours
   sur la même réplique — ce que `deploy/Caddyfile` ne fait pas aujourd'hui (aucun
   `lb_policy`, aucune directive d'affinité).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_THROTTLE = _ROOT / "src" / "dashboard" / "utils" / "throttle.py"
_API_SECURITY = _ROOT / "src" / "api" / "security.py"
_CADDY = _ROOT / "deploy" / "Caddyfile"
_DEPLOY_SH = _ROOT / "tools" / "deploy.sh"

# Un `reverse_proxy` peut porter plusieurs amonts sur la même ligne — c'est la forme
# d'équilibrage de Caddy. On lit donc les ADRESSES, pas le mot-clé.
_UPSTREAM = re.compile(r"\b(?:[\w.-]+|\[[0-9a-fA-F:]+\]):\d{2,5}\b")


def _caddy_upstreams() -> list[tuple[int, list[str]]]:
    """(numéro de ligne, amonts) pour chaque directive `reverse_proxy` NON commentée."""
    if not _CADDY.is_file():
        return []
    out = []
    for n, line in enumerate(_CADDY.read_text(encoding="utf-8").splitlines(), 1):
        bare = line.strip()
        if bare.startswith("#") or not bare.startswith("reverse_proxy"):
            continue
        out.append((n, _UPSTREAM.findall(bare)))
    return out


def _compose_replicas() -> list[str]:
    """Les services déclarant `deploy.replicas > 1`."""
    out = []
    for path in sorted(_ROOT.glob("docker-compose*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, svc in (doc.get("services") or {}).items():
            n = ((svc or {}).get("deploy") or {}).get("replicas")
            if isinstance(n, int) and n > 1:
                out.append(f"{path.name}::{name} → replicas: {n}")
    return out


def _deploy_script_scales() -> bool:
    """`docker compose up --scale` dans le script de déploiement."""
    if not _DEPLOY_SH.is_file():
        return False
    for line in _DEPLOY_SH.read_text(encoding="utf-8").splitlines():
        bare = line.strip()
        if not bare.startswith("#") and "--scale" in bare:
            return True
    return False


def declared_replicas() -> list[str]:
    """Tout ce qui, dans le dépôt, DÉCLARE plus d'une instance d'une même surface."""
    reasons = list(_compose_replicas())
    for n, ups in _caddy_upstreams():
        if len(ups) > 1:
            reasons.append(f"Caddyfile:{n} → {len(ups)} amonts : {', '.join(ups)}")
    if _deploy_script_scales():
        reasons.append("tools/deploy.sh → `--scale`")
    return reasons


def _module_level_limiters(path: Path, names: set[str]) -> set[str]:
    """Les noms de `names` affectés AU NIVEAU MODULE — donc un état par processus."""
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in tree.body:                    # `.body`, pas `ast.walk` : le niveau module
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id in names:
                found.add(t.id)
    return found


def in_process_limiters() -> dict[str, set[str]]:
    return {
        "src/dashboard/utils/throttle.py": _module_level_limiters(_THROTTLE, {"_LIMITERS"}),
        "src/api/security.py": _module_level_limiters(
            _API_SECURITY, {"_GLOBAL_LIMITER", "_AUTH_LIMITER"}),
    }


def _login_budget() -> int:
    """`LOGIN_MAX` lu dans le fichier, pour que le message porte le vrai chiffre."""
    tree = ast.parse(_THROTTLE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LOGIN_MAX" for t in node.targets):
            # `int(os.getenv("...", "30"))` — le défaut est le dernier littéral
            literals = [c.value for c in ast.walk(node.value)
                        if isinstance(c, ast.Constant) and isinstance(c.value, str)
                        and c.value.isdigit()]
            if literals:
                return int(literals[-1])
    return 0


def test_replicas_and_in_memory_counters_are_never_declared_together() -> None:
    """La combinaison est interdite ; chacun séparément ne l'est pas."""
    replicas = declared_replicas()
    in_memory = {f: names for f, names in in_process_limiters().items() if names}
    if not replicas or not in_memory:
        return                                 # l'état d'aujourd'hui, et deux sorties

    budget = _login_budget()
    assert False, (
        "Le dépôt déclare plus d'une instance d'une surface ALORS QUE ses compteurs "
        "anti-force-brute vivent en mémoire de processus.\n\n"
        f"Conséquence directe : le budget de connexion passe de {budget} à "
        f"{budget} × N tentatives par fenêtre, sur un chemin d'authentification, sans "
        "qu'aucune ligne des limiteurs n'ait changé.\n\n"
        "Répliques déclarées :\n  " + "\n  ".join(replicas) + "\n\n"
        "Compteurs encore en mémoire :\n  "
        + "\n  ".join(f"{f} → {', '.join(sorted(n))}" for f, n in in_memory.items())
        + "\n\nTrois sorties, au choix : rester à une réplique ; déplacer les compteurs "
        "dans un magasin partagé ; ou rendre l'affinité de session obligatoire et le "
        "prouver (`deploy/Caddyfile` n'a aujourd'hui ni `lb_policy` ni directive "
        "d'affinité)."
    )


def test_the_detector_reads_both_sides_for_real() -> None:
    """Non-vacuité : sans elle, un parseur cassé rendrait le test ci-dessus vert à vide."""
    ups = _caddy_upstreams()
    assert len(ups) >= 2, (
        f"seulement {len(ups)} directive(s) `reverse_proxy` lue(s) dans "
        "`deploy/Caddyfile` — la lecture est cassée, ou le fichier a changé de forme."
    )
    assert all(len(u) >= 1 for _, u in ups), (
        f"une directive `reverse_proxy` sans aucun amont reconnu : {ups}. "
        "L'expression des adresses ne matche plus rien."
    )

    limiters = in_process_limiters()
    assert limiters["src/dashboard/utils/throttle.py"] == {"_LIMITERS"}, limiters
    assert limiters["src/api/security.py"] == {"_GLOBAL_LIMITER", "_AUTH_LIMITER"}, limiters
    assert _login_budget() > 0, "LOGIN_MAX illisible — le message ne porterait aucun chiffre"


def test_the_detector_is_not_fooled_by_prose_or_by_one_upstream() -> None:
    """Il doit voir DEUX amonts sur une ligne, et ne pas compter un commentaire."""
    assert len(_UPSTREAM.findall("reverse_proxy 127.0.0.1:8501 {")) == 1
    assert len(_UPSTREAM.findall("reverse_proxy 127.0.0.1:8501 127.0.0.1:8511")) == 2
    # Une ligne commentée qui DÉCRIT l'équilibrage n'est pas de l'équilibrage.
    assert declared_replicas() == [] or all(
        not r.startswith("#") for r in declared_replicas())
