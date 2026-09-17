"""Tout état MUTÉ au niveau module est déclaré, avec son verdict à deux instances.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/**, src/api/**, src/utils/**
Persists in: nothing

La forme qui a traversé toute la séance du 2026-09-16
------------------------------------------------------
**Du code exact parce qu'il n'existe qu'un exemplaire de chaque chose**, et faux le
jour où il y en a deux — sans qu'une ligne change. Quatre fois la même forme, trouvées
séparément et chacune par un chemin différent :

1. les seaux anti-force-brute (`budget × N` sur un chemin d'authentification) ;
2. la purge de cache (`clear_kpi_caches()` ne touche que son propre processus) ;
3. la sonde de santé du déploiement (`*) continue` sur un service inconnu) ;
4. le retour arrière (reconstruit `$SERVICES` au lieu du service en panne).

Les trois premières ont été trouvées APRÈS avoir été écrites. Ce test existe pour que
la question se pose AVANT : *cet état est-il encore juste s'il en existe deux
exemplaires ?*

Ce que ce test n'est pas
------------------------
Il n'interdit pas l'état de processus. Il en est plein, et c'est souvent correct — un
cache d'artefact immuable n'a aucune raison d'être partagé. Il exige que chaque site
soit **déclaré avec sa raison**, exactement comme `_NOT_A_QUANTITY` le fait pour les
colonnes numériques d'une table de dimension. Le registre est une assertion, pas une
liste de confiance.

⚠️ Deux formes de détecteur ont été mesurées avant de retenir celle-ci. « Tout
littéral mutable au niveau module » rend **209 sites**, presque tous des registres
constants jamais mutés : un détecteur qui crie 209 fois est un détecteur que personne
ne lit. Le signal n'est pas le TYPE, c'est la **mutation** — le conteneur doit être
muté quelque part dans son propre module. Cette version en rend 8.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
# `src/database` ajouté le 2026-09-16 : c'est là que vit le POOL de connexions —
# `_POOL`, `_POOL_LIMITS`, `_DIRECT_FALLBACKS` — c'est-à-dire l'état de processus
# le plus directement concerné par « et s'il en existe deux ? ». L'omettre était un
# trou du détecteur, pas une exemption : la déclaration que j'y avais écrite n'avait
# aucun site correspondant, et c'est le test de péremption qui l'a dit.
_SURFACES = ("src/dashboard", "src/api", "src/utils", "src/database")

_MUT_LITERAL = (ast.Dict, ast.List, ast.Set)
_MUT_CALL = {"dict", "list", "set", "deque", "defaultdict", "OrderedDict", "Counter"}
_MUTATORS = {"append", "extend", "insert", "pop", "popitem", "remove", "clear",
             "update", "add", "discard", "setdefault", "move_to_end"}

# Chaque état de processus MUTÉ, et pourquoi il reste juste à deux instances.
# Une entrée neuve n'est pas un refus : c'est une question à trancher, et la réponse
# s'écrit ici. Les trois réponses possibles sont « per-instance voulu », « inoffensif
# parce que la donnée est immuable », et « il faut le partager » — la troisième a déjà
# été tirée deux fois le 2026-09-16 (limiteurs, caches KPI).
_DECLARED: dict[str, str] = {
    "src/utils/defect_gauge.py::_WARNED_TRUNCATION":
        "PER-INSTANCE VOULU, et sans conséquence. C'est un drapeau « j'ai déjà prévenu "
        "une fois » devant un `logger.warning` qui signale que le nombre de séries "
        "dépasse le plafond de cardinalité. À deux instances, le pire cas est DEUX "
        "lignes d'avertissement au lieu d'une — et c'est même souhaitable : chaque "
        "processus a son propre journal, et taire l'avertissement du second ferait "
        "croire que seul le premier a tronqué. Aucune donnée n'en dépend : le "
        "repliement lui-même conserve la somme exacte, drapeau ou pas.",
    "src/dashboard/utils/cache_epoch.py::_SEEN":
        "PER-INSTANCE VOULU. C'est la dernière époque que CE processus a vue ; chaque "
        "instance doit avoir la sienne, sinon aucune ne saurait qu'elle a raté une "
        "écriture. Partager cet état détruirait le mécanisme qu'il sert.",
    "src/dashboard/utils/error_alert.py::_last_sent":
        "INOFFENSIF. C'est un chemin rapide devant `_email_due()`, qui lit le REGISTRE "
        "en base — le vrai verrou de refroidissement, et il traverse les instances "
        "comme il traverse les redémarrages. À deux instances, le pire cas est un "
        "aller-retour en base de plus, jamais un doublon de mail.",
    "src/dashboard/utils/pdf_exporter/_config.py::_LANG":
        "INOFFENSIF. Posé et lu dans le même export, synchrone. Deux instances "
        "exportent deux PDF indépendants ; il n'y a rien à partager entre eux.",
    "src/dashboard/views/trigger_algo/_common/_loaders.py::_json_artifact_cache":
        "INOFFENSIF. Cache d'artefacts de MODÈLE, lus sur disque et immuables. Deux "
        "instances chargent le même fichier deux fois — c'est de la mémoire, pas une "
        "divergence.",
    "src/dashboard/views/trigger_algo/_common/_loaders.py::_xgb_booster_cache":
        "INOFFENSIF. Même raison, et le fichier `.ubj` est versionné dans le dépôt : "
        "deux instances chargent le même octet. Le coût est de la mémoire en "
        "double, jamais deux prédictions différentes pour la même entrée.",
    "src/utils/ml_inference.py::_aux_cache":
        "INOFFENSIF. Des tables auxiliaires du modèle, lues une fois et jamais "
        "réécrites. Rien ne circule entre deux instances qui aurait besoin de "
        "s'accorder — chacune relit le même fichier.",
    "src/database/postgres_handler.py::_DIRECT_FALLBACKS":
        "PER-INSTANCE VOULU. Combien de fois CE processus est retombé sur une connexion "
        "directe faute de pool. Chaque instance a son propre pool, donc son propre "
        "compteur ; l'agréger fondrait deux saturations distinctes en une seule courbe "
        "illisible. Prometheus le somme au besoin, avec le label d'instance.",
    "src/dashboard/utils/metrics_seam.py::_CHROME_T0":
        "PER-INSTANCE VOULU, et même per-RERUN : c'est l'instant d'entrée dans le rendu "
        "courant, écrasé à chaque fois. Une seconde instance a ses propres rendus ; "
        "partager cette case n'aurait aucun sens.",
    "src/utils/ml_inference.py::_model_cache":
        "INOFFENSIF. Le modèle lui-même, chargé depuis un artefact versionné. Deux "
        "instances qui le chargent chacune répondent la même chose ; c'est le "
        "cas où dupliquer est exactement équivalent à partager.",
}


def _module_state_sites() -> dict[str, list[int]]:
    """{`chemin::NOM`: [lignes de mutation]} pour tout conteneur de niveau module."""
    out: dict[str, list[int]] = {}
    for surface in _SURFACES:
        for path in sorted((_ROOT / surface).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            names: set[str] = set()
            for node in tree.body:
                targets = node.targets if isinstance(node, ast.Assign) else (
                    [node.target] if isinstance(node, ast.AnnAssign) else [])
                value = node.value if targets else None
                if value is None:
                    continue
                mutable = isinstance(value, _MUT_LITERAL) or (
                    isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id in _MUT_CALL)
                if mutable:
                    names.update(t.id for t in targets if isinstance(t, ast.Name))
            if not names:
                continue
            rel = path.relative_to(_ROOT).as_posix()
            for node in ast.walk(tree):
                hit = None
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _MUTATORS
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in names):
                    hit = node.func.value.id
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                and t.value.id in names):
                            hit = t.value.id
                # `X[k] += 1` est une AugAssign, pas une Assign — et c'est la façon la
                # plus idiomatique de muter un compteur de module. Le détecteur la
                # ratait, donc `_DIRECT_FALLBACKS` était invisible : la déclaration que
                # j'avais écrite pour lui n'avait « aucun site correspondant », et c'est
                # le test de PÉREMPTION qui a signalé l'aveuglement du test de DÉTECTION.
                elif (isinstance(node, ast.AugAssign)
                      and isinstance(node.target, ast.Subscript)
                      and isinstance(node.target.value, ast.Name)
                      and node.target.value.id in names):
                    hit = node.target.value.id
                if hit:
                    out.setdefault(f"{rel}::{hit}", []).append(node.lineno)
    return out


def test_the_detector_finds_the_state_it_is_meant_to_find() -> None:
    """Non-vacuité. Un parseur cassé rendrait l'assertion suivante vraie de rien.

    L'ancre est `cache_epoch._SEEN` : il est muté au niveau module, à dessein, et son
    existence est la raison d'être de R113. S'il n'est plus vu, le détecteur est mort.
    """
    sites = _module_state_sites()
    assert "src/dashboard/utils/cache_epoch.py::_SEEN" in sites, (
        f"le détecteur ne voit plus `cache_epoch._SEEN` — il est cassé. Vus : "
        f"{sorted(sites)[:10]}"
    )
    assert len(sites) >= 5, f"seulement {len(sites)} site(s) vus : {sorted(sites)}"


def test_every_mutated_module_state_is_declared() -> None:
    """Un état de processus neuf se déclare, avec son verdict à deux instances."""
    sites = _module_state_sites()
    undeclared = sorted(set(sites) - set(_DECLARED))
    assert not undeclared, (
        "état(s) muté(s) au niveau module, non déclaré(s) :\n  "
        + "\n  ".join(f"{k} (lignes {sorted(set(sites[k]))})" for k in undeclared)
        + "\n\nCe n'est pas un refus : c'est une QUESTION à trancher — **cet état "
        "est-il encore juste s'il en existe deux exemplaires ?** Trois réponses "
        "possibles, et la réponse s'écrit dans `_DECLARED` :\n"
        "  · per-instance VOULU (chaque instance doit avoir le sien) ;\n"
        "  · inoffensif (la donnée est immuable, au pire de la mémoire en double) ;\n"
        "  · IL FAUT LE PARTAGER — et là c'est un chantier, pas une déclaration.\n\n"
        "La troisième a été tirée deux fois le 2026-09-16 : les seaux anti-force-brute "
        "(budget × N sur un chemin d'authentification) et la purge de cache (dix "
        "minutes de chiffres périmés). Les deux ont été écrits corrects, et les deux "
        "sont devenus faux le jour où une seconde instance a été envisagée."
    )


def test_no_declaration_outlives_its_site() -> None:
    """Une déclaration qui ne correspond plus à rien fait croire qu'on a tranché.

    C'est la même forme que `named-guard-deleted-while-the-class-reads-guarded` : le
    registre se lit comme une assertion, donc une entrée morte ment.
    """
    sites = _module_state_sites()
    stale = sorted(set(_DECLARED) - set(sites))
    assert not stale, (
        "déclaration(s) sans site correspondant :\n  " + "\n  ".join(stale)
        + "\n\nL'état a disparu ou a été renommé. Retirer l'entrée — le registre se "
        "lit comme une assertion sur ce qui existe."
    )


def test_every_declaration_says_why() -> None:
    """Une entrée sans raison n'est pas une déclaration, c'est une exemption."""
    thin = sorted(k for k, v in _DECLARED.items() if len(v) < 80)
    assert not thin, (
        f"déclaration(s) trop courte(s) pour dire quoi que ce soit : {thin}. "
        "La raison est ce qui distingue un registre d'une liste de confiance."
    )
