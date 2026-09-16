"""Des compteurs en MÉMOIRE de processus interdisent une seconde réplique.

Type: Test
Uses: pytest, re, yaml
Depends on: src/dashboard/utils/throttle.py, src/api/security.py,
            src/utils/request_throttle.py, docker-compose*.yml, deploy/Caddyfile,
            tools/deploy.sh
Persists in: nothing

Ce qui est en jeu, et pourquoi c'est un test et pas une phrase
--------------------------------------------------------------
Les budgets anti-force-brute du produit ont longtemps été exacts **parce qu'il y avait un
processus par surface**. Le jour où une seconde réplique apparaît, cette exactitude
disparaît **sans qu'une ligne des limiteurs ne change** : le budget de connexion passe de
`LOGIN_MAX` à `LOGIN_MAX × N`, sur un chemin d'authentification, en silence. Rien ne
reliait les deux faits — l'un vit dans `docker-compose`, l'autre dans `throttle.py`.

Ce que ce garde lit — et ce qu'il ne lit PLUS
---------------------------------------------
Il interroge le **magasin réellement branché** sous chaque seau d'authentification
(`limiter.is_shared`), jamais le nom d'une variable. C'est la correction du 2026-09-16 :
la version d'origine lisait par AST les NOMS affectés au niveau module
(`_LIMITERS`, `_AUTH_LIMITER`). Un tel garde reste rouge sur un correctif correct — les
noms ne bougent pas quand on leur donne un magasin partagé — et vert sur un simple
renommage. Il aurait fallu le réécrire pour faire passer le fix qu'il réclamait, ce qui
est exactement le mode d'aveuglement que ce dépôt a déjà mesuré cinq fois.

Ce que ce garde N'exige PAS
---------------------------
Il n'interdit pas les répliques, et il n'impose pas Redis. Il interdit **la combinaison**.
Trois sorties le satisfont, et le choix reste ouvert :

1. rester à une réplique ;
2. déplacer les compteurs dans un magasin partagé (c'est ce qui a été fait : Postgres,
   `rate_limit_hits`) ;
3. rendre l'affinité de session obligatoire ET prouver que la même IP retombe toujours
   sur la même réplique.

⚠️ La 3 est la plus séduisante et la plus fausse des trois pour CE problème : un
forceur de mots de passe scripté n'a pas de bocal à cookies, donc `lb_policy cookie` le
répartit en tourniquet. L'affinité sert `st.session_state`, elle ne borne rien.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_CADDY = _ROOT / "deploy" / "Caddyfile"
_DEPLOY_SH = _ROOT / "tools" / "deploy.sh"

# Un `reverse_proxy` peut porter plusieurs amonts sur la même ligne — c'est la forme
# d'équilibrage de Caddy. On lit donc les ADRESSES, pas le mot-clé.
_UPSTREAM = re.compile(r"\b(?:[\w.-]+|\[[0-9a-fA-F:]+\]):\d{2,5}\b")


# ─────────────────────────────────────────────────────────────────────────────
# Côté déploiement : qui déclare plus d'une instance ?
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Côté limiteurs : les seaux d'AUTHENTIFICATION, et le magasin sous chacun
# ─────────────────────────────────────────────────────────────────────────────
#
# La liste est explicite parce que l'appartenance à cette famille est un JUGEMENT, pas
# une propriété syntaxique : `_GLOBAL_LIMITER` est un limiteur et n'en fait pas partie
# (120 req/min sur toutes les routes — il protège l'abus et le coût, aucune décision de
# sécurité n'en dépend, et son plafond `× N` est écrit à sa construction).
#
# Y ajouter un seau est donc un geste délibéré, et `test_the_family_is_complete` échoue
# si un seau d'authentification naît sans y entrer.

def auth_limiters() -> dict[str, object]:
    """{étiquette lisible: limiteur} pour les quatre seaux d'authentification."""
    from src.api import security
    from src.dashboard.utils import throttle

    out: dict[str, object] = {
        f"src/dashboard/utils/throttle.py::_LIMITERS[{name!r}]": lim
        for name, lim in throttle._LIMITERS.items()
    }
    out["src/api/security.py::_AUTH_LIMITER"] = security._AUTH_LIMITER
    return out


def unshared_auth_limiters() -> list[str]:
    """Les seaux d'authentification dont le compteur ne quitte PAS le processus."""
    return [label for label, lim in auth_limiters().items() if not lim.is_shared]


def _login_budget() -> int:
    """`LOGIN_MAX` tel qu'il vaut à l'exécution, pour que le message porte le chiffre."""
    from src.dashboard.utils import throttle

    return int(throttle.LOGIN_MAX)


# ─────────────────────────────────────────────────────────────────────────────
# Le garde
# ─────────────────────────────────────────────────────────────────────────────

def test_replicas_and_in_memory_counters_are_never_declared_together() -> None:
    """La combinaison est interdite ; chacun séparément ne l'est pas."""
    replicas = declared_replicas()
    in_memory = unshared_auth_limiters()
    if not replicas or not in_memory:
        return                                 # l'état d'aujourd'hui, et deux sorties

    budget = _login_budget()
    assert False, (
        "Le dépôt déclare plus d'une instance d'une surface ALORS QUE des compteurs "
        "anti-force-brute vivent encore en mémoire de processus.\n\n"
        f"Conséquence directe : le budget de connexion passe de {budget} à "
        f"{budget} × N tentatives par fenêtre, sur un chemin d'authentification, sans "
        "qu'aucune ligne des limiteurs n'ait changé.\n\n"
        "Répliques déclarées :\n  " + "\n  ".join(replicas) + "\n\n"
        "Seaux d'authentification encore en mémoire :\n  " + "\n  ".join(in_memory)
        + "\n\nDeux sorties : rester à une réplique, ou donner à ces seaux le magasin "
        "partagé (`shared_hit_store()`). L'affinité de session n'en est PAS une — un "
        "forceur scripté n'a pas de bocal à cookies, `lb_policy cookie` le répartit en "
        "tourniquet."
    )


def test_the_global_api_bucket_stays_in_memory_on_purpose() -> None:
    """Le seau global N'EST PAS de la famille, et ce n'est pas un oubli.

    Le déplacer en base coûterait une écriture par requête d'API pour borner un abus
    dont aucune décision de sécurité ne dépend. Son plafond effectif est donc
    `RATE_LIMIT_MAX × nombre d'instances de l'API`, et c'est acceptable.

    ⚠️ Une version de ce test vérifiait AUSSI que cette phrase était écrite dans
    `src/api/security.py`, par `in source`. C'est un garde TEXTUEL, et le dépôt en
    interdit l'ajout (`tests/test_a_guard_reads_structure_not_text.py`) pour une raison
    mesurée : une assertion satisfaite par un commentaire est verte le jour où le code
    change et où seul le commentaire reste. Elle aurait surveillé une phrase, pas un
    fait. Le fait, lui, est structurel et se lit ci-dessous.
    """
    from src.api import security

    assert "src/api/security.py::_GLOBAL_LIMITER" not in auth_limiters()
    assert not security._GLOBAL_LIMITER.is_shared, (
        "_GLOBAL_LIMITER a reçu un magasin partagé : une écriture en base par requête "
        "d'API, pour un seau dont aucune décision de sécurité ne dépend."
    )


def test_the_family_is_complete() -> None:
    """Les quatre seaux d'authentification du produit sont dans la famille.

    Non-vacuité, et détection d'un CINQUIÈME : un seau de mot de passe ou de code
    ajouté demain sans entrer ici passerait sous le garde ci-dessus.
    """
    from src.dashboard.utils import throttle

    labels = set(auth_limiters())
    assert len(labels) == 4, f"{len(labels)} seau(x) d'authentification lus : {labels}"
    assert set(throttle._LIMITERS) == {"register", "totp", "login"}, (
        f"les seaux du dashboard ont changé : {sorted(throttle._LIMITERS)} — "
        "un seau neuf doit entrer dans `auth_limiters()` ou être justifié ici."
    )
    assert _login_budget() > 0, "LOGIN_MAX illisible — le message ne porterait aucun chiffre"


def test_the_backend_reader_is_not_vacuous() -> None:
    """Un limiteur délibérément en mémoire DOIT être rapporté non partagé.

    Sans cette assertion, `is_shared` pourrait rendre True partout — y compris sur un
    `dict` de processus — et le garde serait vert sur le défaut même qu'il existe pour
    attraper.
    """
    from src.utils.request_throttle import (
        InMemoryHitStore,
        SlidingWindowLimiter,
        shared_hit_store,
    )

    assert SlidingWindowLimiter(3, 60).is_shared is False
    assert SlidingWindowLimiter(3, 60, store=InMemoryHitStore()).is_shared is False
    assert SlidingWindowLimiter(3, 60, store=shared_hit_store()).is_shared is True


def test_the_replica_detector_reads_both_sides_for_real() -> None:
    """Non-vacuité côté déploiement : un parseur cassé rendrait le garde vert à vide."""
    ups = _caddy_upstreams()
    assert len(ups) >= 2, (
        f"seulement {len(ups)} directive(s) `reverse_proxy` lue(s) dans "
        "`deploy/Caddyfile` — la lecture est cassée, ou le fichier a changé de forme."
    )
    assert all(len(u) >= 1 for _, u in ups), (
        f"une directive `reverse_proxy` sans aucun amont reconnu : {ups}. "
        "L'expression des adresses ne matche plus rien."
    )


def test_the_detector_is_not_fooled_by_prose_or_by_one_upstream() -> None:
    """Il doit voir DEUX amonts sur une ligne, et ne pas compter un commentaire."""
    assert len(_UPSTREAM.findall("reverse_proxy 127.0.0.1:8501 {")) == 1
    assert len(_UPSTREAM.findall("reverse_proxy 127.0.0.1:8501 127.0.0.1:8511")) == 2
    # Une ligne commentée qui DÉCRIT l'équilibrage n'est pas de l'équilibrage.
    assert declared_replicas() == [] or all(
        not r.startswith("#") for r in declared_replicas())
