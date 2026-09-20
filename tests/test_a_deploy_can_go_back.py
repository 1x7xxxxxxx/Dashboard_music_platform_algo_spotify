"""Un deploiement qui echoue sa porte de sante REVIENT en arriere.

Type: Test
Uses: pytest, re
Depends on: tools/deploy.sh
Persists in: nothing

Ce qui etait vrai jusqu'au 2026-09-16
-------------------------------------
`tools/deploy.sh` capturait `before="$(git rev-parse --short HEAD)"` a la ligne 19 et
ne s'en servait QUE pour l'affichage a la ligne 22. Quand la porte de sante rougissait,
le script sortait en `exit 1` **en laissant le conteneur casse en service**.

Le script savait ou revenir. Il n'y revenait pas. La seule manoeuvre de secours etait
alors un revert et un second build de plusieurs minutes, a la main, sous trafic.

Ce garde demande deux choses, et les deux comptent
--------------------------------------------------
1. la branche d'echec de la porte APPELLE le retour arriere — pas seulement qu'une
   fonction de retour existe quelque part dans le fichier ;
2. cette fonction utilise vraiment `$before` — une fonction qui ne revient nulle part
   satisferait la premiere condition sans rien garantir.

C'est la distinction « presence != atteignabilite » que ce depot a payee plusieurs
fois : une fonction correcte que rien n'appelle ne protege de rien.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.code_text import code_of

_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY = _ROOT / "tools" / "deploy.sh"

_FAILURE_MARK = "did not return 200"


def _lines() -> list[str]:
    return code_of(_DEPLOY).splitlines()


def _failure_branch() -> list[str]:
    """Les lignes qui suivent immediatement l'echec de la porte de sante."""
    lines = _lines()
    for i, line in enumerate(lines):
        if _FAILURE_MARK in line and not line.strip().startswith("#"):
            return lines[i:i + 5]
    return []


def _rollback_body() -> list[str]:
    lines = _lines()
    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"^\s*rollback\s*\(\)\s*\{", ln)), None)
    if start is None:
        return []
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("}"):
            break
        out.append(ln)
    return out


def test_a_red_health_gate_puts_the_previous_version_back() -> None:
    branch = _failure_branch()
    assert branch, (
        f"aucune branche d'echec trouvee dans `tools/deploy.sh` (marqueur "
        f"{_FAILURE_MARK!r}). Si la porte de sante a disparu, c'est CA le constat."
    )
    assert any("rollback" in ln for ln in branch), (
        "la porte de sante echoue sans appeler de retour arriere : le conteneur casse "
        "reste EN SERVICE, et la seule manoeuvre de secours est manuelle, sous trafic.\n"
        "Branche lue :\n  " + "\n  ".join(ln.strip() for ln in branch)
    )


def test_the_rollback_actually_goes_back() -> None:
    """Une fonction de retour qui ne revient nulle part satisferait le test d'a cote."""
    body = _rollback_body()
    assert body, "aucune fonction `rollback()` au niveau du script"
    joined = "\n".join(body)
    assert "$before" in joined, (
        "`rollback()` ne mentionne jamais `$before` : elle ne revient donc a rien. "
        "C'est la forme « presence != atteignabilite », prise a l'envers."
    )
    assert "reset" in joined or "checkout" in joined, (
        "`rollback()` ne remet aucun code en place — elle affiche peut-etre un message, "
        "ce qui est pire qu'une absence : on croira que le retour a eu lieu."
    )


def test_a_deploy_refuses_to_run_ahead_of_its_migrations() -> None:
    """Migrer APRES avoir deploye demarre une app qui repond 200 et rend 500."""
    body = code_of(_DEPLOY)
    assert "schema_migrations" in body, (
        "`tools/deploy.sh` ne regarde pas le registre des migrations. Quand l'ordre est "
        "inverse, rien n'echoue bruyamment : l'application DEMARRE, repond 200 sur "
        "/health, et rend 500 sur les donnees — la porte de sante ne teste que la "
        "vivacite. La classe a deja coute un `/kpis` casse, vu le lendemain."
    )
    assert "tools/migrate.sh" in body, (
        "le refus doit NOMMER la commande qui debloque, sinon il laisse l'operateur "
        "chercher (classe `a-printed-command-is-runnable-as-printed`)."
    )


def test_a_rollback_with_nowhere_to_go_says_so_instead_of_concluding() -> None:
    """⚠️ MESURE EN PRODUCTION LE 2026-09-20, et la conclusion etait FAUSSE.

    La porte de `api` est sortie rouge. Le retour arriere a annonce
    « ba9c361 -> ba9c361 » puis conclu :

        « api ne repond TOUJOURS PAS apres le retour arriere. La panne ne vient donc
          pas du code deploye : regarder la base, le reseau, ou l'hote. »

    Le `git reset` n'avait RIEN annule — `$before` et `$after` etaient identiques,
    parce que le `git pull` avait eu lieu a l'invocation PRECEDENTE, celle qui s'etait
    arretee sur les migrations en attente. Et la panne venait bien du code deploye :
    une sonde `/health` qui ne savait pas lire `DATABASE_URL`.

    Un raisonnement « le retour n'a rien change, donc la cause est ailleurs » ne vaut
    QUE si le retour a reellement recule. Sinon il envoie chercher au mauvais endroit,
    au pire moment.
    """
    corps = "\n".join(_rollback_body())
    assert corps, "corps de `rollback()` introuvable — le garde ne lit plus rien"
    assert 'if [ "$before" = "$after" ]' in corps, (
        "le retour arriere ne verifie pas qu'il a quelque part ou revenir. Quand "
        "`$before` == `$after`, le `git reset` est un no-op et le service reste rouge — "
        "et le script en conclut que le code est hors de cause. C'est faux, et c'est la "
        "conclusion qui coute le plus cher : elle envoie enqueter ailleurs.")
    assert "PAS DE RETOUR POSSIBLE" in corps, (
        "le cas « nulle part ou revenir » n'est pas NOMME. Un operateur doit pouvoir "
        "distinguer « j'ai recule et ca reste rouge » de « je n'ai pas recule ».")


def test_the_deploy_offers_a_one_command_path_and_keeps_the_refusal() -> None:
    """La friction mesuree : TROIS commandes pour un geste.

    Le 2026-09-20, sur un ecart de 50 commits : `make deploy` s'arrete sur les
    migrations, `make migrate-prod`, puis `make deploy` a nouveau.

    ⚠️ Le refus par defaut RESTE, et c'est le point de ce test. `MIGRATE=1` est un
    choix pris EXPLICITEMENT, pas un assouplissement : sans le drapeau, le script
    refuse toujours. La fenetre est la bonne — le pull a eu lieu, le build n'a pas
    commence — donc les migrations tournent contre le code qu'elles accompagnent.
    """
    body = code_of(_DEPLOY)
    assert 'if [ "${MIGRATE:-0}" = "1" ]' in body, (
        "`tools/deploy.sh` n'offre pas de voie en une commande. La friction se paie a "
        "chaque deploiement portant une migration.")
    assert "exit 1" in body.split('if [ "${MIGRATE:-0}" = "1" ]')[1].split("fi")[0] \
           or "STOP :" in body, (
        "le drapeau ne verifie pas que les migrations sont PASSEES avant de construire. "
        "Appliquer puis construire sans relire le registre, c'est deployer sur une "
        "migration qui a echoue.")
    apres = body.split('if [ "${MIGRATE:-0}" = "1" ]')[1]
    assert "else" in apres and "STOP :" in apres, (
        "le refus par defaut a disparu : `MIGRATE=1` doit AJOUTER une voie, jamais "
        "remplacer le garde. Sans drapeau, le script doit toujours s'arreter.")
