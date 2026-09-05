"""The one place that builds a shell command shown to a reader.

Type: Utility
Uses: pathlib, re
Triggers: views that must print a command to paste
Depends on: the `venv/` of this checkout (read, never guessed)
Persists in: nothing

Class `printed-command-assumes-a-shell-the-reader-does-not-have` (2026-09-05). A page
printed `python -c "…"` on its own. The command was correct and not runnable as shown:
the only interpreter carrying the project's dependencies lives in `venv/`, and on
Windows PowerShell refuses `Activate.ps1` under its default execution policy.

Two rules this module exists to keep:

- The activation prelude is built ONCE. A second copy diverges, and the reader gets
  whichever page they happened to open.
- The venv is READ off disk, never inferred from `sys.platform`. This checkout is
  shared between WSL and Windows and carries exactly one `venv/`. No OS selector —
  one was removed from the credentials tabs on 2026-09-04 because it asked the reader
  a question the filesystem already answers.

Nothing here decides WHETHER a command should be shown. A command an artist cannot
run does not become acceptable by being runnable — three such lines were removed from
artist-facing pages on 2026-09-05 rather than routed through here.
"""
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def windows_path(path) -> str:
    r"""`/mnt/c/x` → `C:\x`. Identity on a real Windows interpreter.

    The dashboard is launched from PowerShell on the operator's box
    (`venv/Scripts/python.exe`, Makefile `check-env`), but the same checkout is read
    from WSL, where `__file__` is a `/mnt/<drive>/` path. A block that pastes
    `/mnt/c/...` into PowerShell does not run.
    """
    text = str(path)
    m = re.match(r"^/mnt/([a-zA-Z])/(.*)$", text)
    if m:
        return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")
    return text


def venv_prelude(root=None) -> tuple:
    """`(language, [lines])` — what must run BEFORE any project command.

    `root` is injectable for the guard: `venv/` is gitignored, so on a runner both
    branches are absent and a test reading this checkout would only ever assert the
    empty case — the shape of `guard-reads-the-box-not-its-subject` (2026-09-05).
    """
    root = _REPO_ROOT if root is None else Path(root)
    ps1 = root / "venv" / "Scripts" / "Activate.ps1"
    posix = root / "venv" / "bin" / "activate"
    if ps1.exists():
        return "powershell", [
            "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned",
            f"& {windows_path(ps1)}",
        ]
    if posix.exists():
        return "bash", [f"source {posix}"]
    return "bash", []


def command_block(command: str, root=None) -> tuple:
    """`(language, block)` — `command` preceded by whatever its shell needs first."""
    lang, prelude = venv_prelude(root)
    return lang, "\n".join([*prelude, command])
