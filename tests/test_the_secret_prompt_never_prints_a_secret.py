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


def test_every_secret_the_tools_ask_for_names_its_account() -> None:
    """The dialog says WHICH account and WHERE — a bare variable name left the owner guessing."""
    lib = _SCRIPT.parent / "secret_dialog.sh"
    rotate = (_SCRIPT.parent / "rotate_secret.sh").read_text()
    allowed = rotate.split('ALLOWED="', 1)[1].split('"', 1)[0].split()
    wanted = allowed + ["GMAIL_APP_PASSWORD_NINEKA", "GMAIL_APP_PASSWORD_127BPMIN",
                        "GMAIL_APP_PASSWORD_1X7"]
    for var in wanted + ["UNKNOWN_VAR"]:
        out = subprocess.run(["bash", "-c", f'source "{lib}"; secret_hint {var}'],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        who, _, where = out.partition("|")
        if var == "UNKNOWN_VAR":
            assert who == "UNKNOWN_VAR" and not where, "the fallback must stay the bare name"
        else:
            assert who != var and where, f"{var}: the dialog would not say which account"


def test_the_labels_cross_to_windows() -> None:
    """Env vars reach powershell.exe only through WSLENV — without it the window is blank."""
    text = (_SCRIPT.parent / "secret_dialog.sh").read_text()
    call = text.split("powershell.exe", 1)[0].rsplit("dialog()", 1)[1]
    for var in ("VAR_LABEL", "VAR_WHO", "VAR_WHERE", "VAR_STEP"):
        assert 'WSLENV="' in call and var in call.split('WSLENV="', 1)[1].split('"', 1)[0], \
            f"{var} is not exported through WSLENV — the dialog would show it empty"
