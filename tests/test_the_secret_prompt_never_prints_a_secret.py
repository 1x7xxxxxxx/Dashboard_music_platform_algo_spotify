"""`tools/dev/secret_prompt.sh` writes a secret into an env file and never prints it.

Type: Sub
Uses: tools/dev/secret_prompt.sh with SECRET_PROMPT_CMD standing in for the Windows dialog
Depends on: bash, python3 — throwaway env file, no GUI

2026-09-25: two Gmail app passwords pasted into the chat had to be revoked. The dialog
lets Claude run the gesture while the value never reaches a command line or an output.
"""
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "tools/dev/secret_prompt.sh"
_VALUE = "abcd efgh ijkl mnop"  # pragma: allowlist secret


def _run(env_file: Path, *args: str, value: str = _VALUE) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_SCRIPT), *args], text=True, capture_output=True,
                          timeout=30, env={"PATH": "/usr/bin:/bin",
                                           "SECRET_PROMPT_CMD": f"printf '%s' '{value}'"})


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """Replaced when present, appended when absent, and absent from every output."""
    f = tmp_path / ".env"
    f.write_text("A=1\nGMAIL_APP_PASSWORD_X=old\n")
    r = _run(f, "--nospace", str(f), "GMAIL_APP_PASSWORD_X", "GMAIL_APP_PASSWORD_Y")
    assert r.returncode == 0, r.stdout + r.stderr
    text = f.read_text()
    assert "A=1" in text and "=old" not in text
    assert "GMAIL_APP_PASSWORD_X=abcdefghijklmnop\n" in text  # pragma: allowlist secret
    assert "GMAIL_APP_PASSWORD_Y=abcdefghijklmnop\n" in text  # pragma: allowlist secret
    for leak in (_VALUE, "abcdefghijklmnop"):
        assert leak not in r.stdout and leak not in r.stderr, "the secret was printed"
    assert "16 caractères" in r.stdout


def test_a_closed_dialog_changes_nothing(tmp_path) -> None:
    f = tmp_path / ".env"
    f.write_text("K=old\n")
    r = _run(f, str(f), "K", value="")
    assert r.returncode == 1 and f.read_text() == "K=old\n"


def test_a_malformed_variable_name_is_refused(tmp_path) -> None:
    f = tmp_path / ".env"
    f.write_text("")
    r = _run(f, str(f), "X=1;rm")
    assert r.returncode == 2 and f.read_text() == ""
