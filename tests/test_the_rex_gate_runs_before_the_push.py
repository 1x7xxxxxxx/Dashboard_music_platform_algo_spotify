"""Le garde REX bloquant en CI a aussi un exemplaire local.

Type: Test
Uses: yaml, pathlib
Depends on: .pre-commit-config.yaml, .github/workflows/ci.yml, .claude/scripts/validate_rex.py
Persists in: nothing

Pourquoi ce test existe
-----------------------
Le 2026-09-04, le commit `8176e97` a ajouté deux blocs `rex:` dont le champ `issue`
dépassait le plafond de 350 caractères du schéma (376 et 399). `pre-commit` est
installé sur ce poste et il est passé au vert : il ne lançait pas `validate_rex.py`.
La CI, elle, le lance en étape **bloquante** — huit runs consécutifs rouges sur
`main`, du commit fautif à `a0cd505a`, découverts par mail treize heures plus tard.
Sept commits ont été poussés par-dessus une CI déjà rouge sans que rien ne le dise.

Le défaut n'était pas le validateur : il était correct et il a trouvé les deux
entrées. Le défaut est **l'endroit où il tournait**. Classe
`ci-gate-with-no-local-counterpart`.

Ce que ce test n'exige pas
--------------------------
Que *tous* les gardes de la CI soient dans `pre-commit`. `audit_runner.py
--deterministic` lance des `pytest` : plusieurs minutes sur ce poste, ce qui n'a rien
à faire dans un hook de commit. Le critère qui range `validate_rex.py` du bon côté est
mesuré : **0,6 s**, aucun réseau, et il ne lit que `.claude/`.

Lecture STRUCTURELLE, jamais textuelle : le commentaire qui documente le hook nomme
lui-même `validate_rex.py`, donc un `grep` resterait vert après suppression du hook
(classe `guard-matches-its-own-comment`).
"""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_PRECOMMIT = _ROOT / ".pre-commit-config.yaml"
_CI = _ROOT / ".github/workflows/ci.yml"
_SCRIPT = "validate_rex.py"


def _precommit_hooks() -> list[dict]:
    cfg = yaml.safe_load(_PRECOMMIT.read_text(encoding="utf-8"))
    return [h for repo in cfg.get("repos", []) for h in repo.get("hooks", [])]


def test_pre_commit_runs_the_rex_validator():
    hooks = [h for h in _precommit_hooks() if _SCRIPT in str(h.get("entry", ""))]
    assert hooks, (
        f"aucun hook de .pre-commit-config.yaml n'exécute {_SCRIPT}. La CI le lance en "
        "étape bloquante : sans exemplaire local, une entrée REX hors schéma passe le "
        "commit et rougit `main` (2026-09-04, commit 8176e97, huit runs)."
    )
    entry = str(hooks[0]["entry"])
    assert "--strict" in entry, (
        f"le hook lance {_SCRIPT} sans `--strict`, alors que la CI l'exige : le hook "
        "passerait sur ce que la CI refuse."
    )


def test_the_hook_fires_on_the_files_the_validator_reads():
    hook = next(h for h in _precommit_hooks() if _SCRIPT in str(h.get("entry", "")))
    files = str(hook.get("files", ""))
    assert ".claude" in files, (
        "le hook REX ne se déclenche pas sur `.claude/`, les seuls fichiers que "
        f"{_SCRIPT} lit (_SCAN_DIRS). Déclenché ailleurs, il ne verra jamais le défaut."
    )
    assert hook.get("pass_filenames") is False, (
        "le validateur balaie tout l'arbre `.claude/` et n'accepte pas de chemins en "
        "argument ; `pass_filenames: false` est obligatoire."
    )


def test_the_ci_step_still_exists():
    """Si la CI cesse de le lancer, le hook local devient le seul garde — et ce test
    doit le dire plutôt que de continuer à parler d'un « exemplaire local ».

    Lu dans le YAML, jamais dans le texte : une étape mise en commentaire laisse le
    nom du script dans le fichier, et une recherche de chaîne resterait verte sur
    exactement la disparition qu'on veut voir.
    """
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    # Un `run:` est un bloc SHELL : une ligne mise en commentaire reste dans la
    # chaine YAML. Verifie par mutation — commenter l'etape laissait ce test vert,
    # la classe `guard-matches-its-own-comment` dans le garde lui-meme.
    runs = [line.strip()
            for job in ci.get("jobs", {}).values()
            for step in job.get("steps", [])
            for line in str(step.get("run", "")).splitlines()
            if not line.strip().startswith("#")]
    assert any(_SCRIPT in r and "--strict" in r for r in runs), (
        f"aucune étape de ci.yml ne lance {_SCRIPT} --strict. Ce test garde une "
        "PAIRE ; si la CI abandonne sa moitié, c'est une décision à prendre, pas un "
        "détail."
    )
