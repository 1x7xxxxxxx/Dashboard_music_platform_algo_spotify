"""Le réécriveur de commandes ne doit pas fausser une mesure.

Type: Test
Uses: tomllib
Depends on: ~/.config/rtk/config.toml
Persists in: nothing

Error class `a-command-wrapper-that-returns-a-plausible-wrong-measurement`.

Le défaut
---------
Un hook `PreToolUse` global (`rtk hook claude`) réécrit TOUTES les commandes Bash.
Mesuré le 2026-09-17, quatre résultats faux et plausibles : `diff u v | wc -l` rendait
**5** au lieu de 4 ; `grep 'a' f > out.txt` rendait exit 0 et un fichier **VIDE** ;
`ps | grep` rendait une sortie vide ; `git diff -- a b c d` rendait `fatal: bad revision`.

⚠️ La cause de la redirection vidée n'était PAS le wrapper `grep` — c'était
`[tee] mode = "failures"`, qui n'écrivait le fichier **que si la commande échouait**.
Exclure `grep` n'a rien changé, et c'est ce résultat NÉGATIF qui a désigné `[tee]`.

Pourquoi ce test SKIPPE au lieu de passer, hors de cette machine
---------------------------------------------------------------
La configuration vit dans le HOME du développeur, pas dans le dépôt. En CI le fichier
est absent, et un test qui passerait alors serait vert **par vacuité** — exactement ce
que ce dépôt refuse. Un skip motivé se compte dans les skips et se lit ; un vert
silencieux ment. C'est aussi ce que dit le `ne couvre pas:` de la classe.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_CONFIG = Path.home() / ".config/rtk/config.toml"
# Les trois dont la sortie est une DÉCISION, et qui ont menti le 2026-09-17.
# `make`, `git stash`, `gh` ajoutés le 2026-09-25 : trois mensonges de plus en une séance —
# `make test-changed` tronqué (« 281 lines truncated », verdict perdu), `git stash show`
# → « Empty stash » sur un stash de 5 fichiers, `gh run list` sans le statut du run.
_MUST_BE_EXCLUDED = {"grep", "diff", "ps", "make", "git stash", "gh"}


def _config() -> dict:
    if not _CONFIG.exists():
        pytest.skip(f"{_CONFIG} absent — le réécriveur n'est pas installé ici")
    try:
        import tomllib
    except ImportError:  # pragma: no cover — Python < 3.11
        pytest.skip("tomllib indisponible")
    return tomllib.loads(_CONFIG.read_text(encoding="utf-8"))


def test_the_redirect_interceptor_is_off() -> None:
    """`[tee] enabled = true` détruit la sortie de toute commande qui RÉUSSIT."""
    assert _config().get("tee", {}).get("enabled") is not True, (
        "`[tee] enabled = true` est revenu. En mode `failures`, RTK n'écrit le fichier "
        "de redirection QUE si la commande échoue : tout `cmd > f` d'une commande qui "
        "réussit produit un fichier VIDE, en silence.\n"
        "Reproduction : `printf 'a\\nb\\n' > u; grep a u > o; wc -l < o` doit rendre 1.")


def test_the_measuring_commands_are_not_rewritten() -> None:
    """Une commande dont la sortie est une décision ne passe pas par le réécriveur."""
    excluded = set(_config().get("hooks", {}).get("exclude_commands", []))
    missing = _MUST_BE_EXCLUDED - excluded
    assert not missing, (
        f"{sorted(missing)} ne sont plus exclus du réécriveur. Leur sortie est une "
        "MESURE, et le réécriveur ne se trompe jamais bruyamment : il rend un "
        "résultat plausible.\n"
        "Ce que ça coûte de les exclure, mesuré par `rtk gain` sur 45 258 commandes : "
        "`read` porte 99,5 % du gain, ces trois-là pèsent 0,2 %.")
