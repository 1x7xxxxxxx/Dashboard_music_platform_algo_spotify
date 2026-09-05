"""The Credentials page must not print a command the reader's shell cannot run.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/views/credentials/_core.py, .../router.py
Persists in: nothing

Class `printed-command-assumes-a-shell-the-reader-does-not-have`. The Fernet banner
handed out `python -c "from cryptography.fernet import Fernet; ..."` as inline Markdown
code. On this box that line fails twice over: the only interpreter carrying
`cryptography` lives in `venv/`, and PowerShell refuses `Activate.ps1` under its default
execution policy. Reaching the page therefore told the reader to do something that does
not work, in one line, with no way to tell which half was wrong.

Nothing here reads this checkout's own `venv/`: it is gitignored, so on a runner both
branches would be absent and the guard would only ever assert the fallback — the shape
of `guard-reads-the-box-not-its-subject`, found on 2026-09-05. Each situation is POSED
on a `tmp_path`.
"""
import ast
from pathlib import Path

import pytest

from src.dashboard.views.credentials._core import (
    _windows_path,
    fernet_key_command_block,
)

_CREDENTIALS = Path(__file__).resolve().parents[1] / "src/dashboard/views/credentials"
_ROUTER = _CREDENTIALS / "router.py"


def _make_venv(root: Path, *parts: str) -> Path:
    target = root.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    return target


def test_a_windows_venv_gets_the_execution_policy_before_the_activation(tmp_path):
    """`Activate.ps1` alone is refused by default — the unlock must come first."""
    ps1 = _make_venv(tmp_path, "venv", "Scripts", "Activate.ps1")
    lang, block = fernet_key_command_block(tmp_path)
    lines = block.splitlines()

    assert lang == "powershell"
    assert lines[0] == "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned"
    # The activation call names the file that actually exists, not a guessed path.
    # (`/mnt/c` → `C:\` rewriting has its own case below; `tmp_path` is not under
    # `/mnt`, so the path is passed through here — which is the point: no invention.)
    assert lines[1] == f"& {_windows_path(ps1)}"
    assert ps1.exists()
    assert lines[2].startswith("python -c ")
    # Scoped to the process: the block must not change the machine's policy.
    assert "-Scope Process" in lines[0]
    assert "LocalMachine" not in block and "CurrentUser" not in block


def test_a_posix_venv_is_sourced_and_never_told_about_powershell(tmp_path):
    _make_venv(tmp_path, "venv", "bin", "activate")
    lang, block = fernet_key_command_block(tmp_path)

    assert lang == "bash"
    assert block.splitlines()[0] == f"source {tmp_path / 'venv' / 'bin' / 'activate'}"
    assert "ExecutionPolicy" not in block


def test_no_venv_at_all_still_yields_the_bare_generator(tmp_path):
    """No venv on disk is not an error — but it is the ONLY case that may be bare."""
    lang, block = fernet_key_command_block(tmp_path)
    assert lang == "bash"
    assert block.splitlines() == [
        'python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"'
    ]


@pytest.mark.parametrize(
    "given,expected",
    [
        ("/mnt/c/Users/x/venv/Scripts/Activate.ps1", r"C:\Users\x\venv\Scripts\Activate.ps1"),
        ("/mnt/d/proj/a", r"D:\proj\a"),
        (r"C:\already\windows", r"C:\already\windows"),
        ("/home/timothe/proj", "/home/timothe/proj"),
    ],
)
def test_a_wsl_path_is_rewritten_for_the_shell_that_reads_it(given, expected):
    """`/mnt/c/...` pasted into PowerShell does not resolve — the block is read there."""
    assert _windows_path(Path(given) if given.startswith("/") else given) == expected


def test_the_banner_renders_the_block_instead_of_inlining_a_command():
    """Structural, not textual: a `grep` would stay green on the comment above the fix.

    The docstring and the comment in `router.py` both quote `python -c` while
    explaining why it was removed (`guard-matches-its-own-comment`). So the tree is
    walked: the call to `fernet_key_command_block` must exist and its result must
    reach an `st.code(...)`, and no string constant left in the module may carry an
    interpreter invocation.
    """
    tree = ast.parse(_ROUTER.read_text(encoding="utf-8"))

    produced = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "fernet_key_command_block" in produced, (
        "the router no longer builds the command block for the reader's shell"
    )

    code_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "code"
    ]
    assert code_calls, "nothing renders the block — `st.code` disappeared"

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "python -c" not in node.value, (
                f"router.py still hands out an inline interpreter call: {node.value!r}"
            )


# ── Ce que la page montre vraiment ────────────────────────────────────────────
# Les assertions ci-dessus lisent la fonction et l'arbre du router. Aucune ne dit ce
# que le lecteur voit : `st.code` peut être appelé et le bloc n'arriver jamais à
# l'écran (`verdict-exists-but-not-when-it-is-needed`, 2026-09-04, où un `st.rerun()`
# effaçait un message calculé). Ici la page est rendue et le bloc relu à la sortie.
#
# `fernet_state` est REMPLACÉE dans le module qui l'appelle : la clé de ce poste est
# valide, et la retirer de `config/config.yaml` pour voir la bannière rendrait
# indéchiffrables les credentials déjà enregistrés.

def _db_ready() -> bool:
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return False


_RENDER_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
import src.dashboard.views.credentials.router as router
router.fernet_state = lambda: 'absent'
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
router.show()
"""


@pytest.mark.skipif(not _db_ready(), reason="render needs the live spotify_etl DB on 5433")
def test_the_page_actually_shows_the_block_when_the_key_is_missing():
    import os

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_RENDER_SCRIPT.format(root=os.getcwd()))
    at.run(timeout=120)
    assert not at.exception, at.exception

    blocks = [c for c in at.code if "Fernet.generate_key" in c.value]
    assert blocks, "la page n'affiche aucun bloc de génération de clé"
    shown = blocks[0]
    lines = shown.value.splitlines()
    assert lines[0] == "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned"
    assert lines[1].startswith("& ") and lines[1].endswith("Activate.ps1")
    assert shown.language == "powershell"

    # Le message d'accompagnement ne doit plus porter la commande : deux copies
    # divergent, et c'est celle du Markdown que le lecteur attrapait avec ses
    # backticks.
    assert not any("python -c" in w.value for w in at.warning)
