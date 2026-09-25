"""`tools/dev/rotate_secret.sh` writes a new secret everywhere it lives and never prints it.

Type: Sub
Uses: tools/dev/rotate_secret.sh (local-files mode: ROTATE_PROD_SSH empty)
Depends on: bash, python3 — throwaway .env files, no network, no prod

R177 (2026-09-25): 12 real secrets in the public history, two still in service. The
console gesture is human; the rest must not become a copy-paste of a secret into a chat.
"""
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "tools/dev/rotate_secret.sh"
_NEW = "n3w-s3cr3t-value-for-test-only"  # pragma: allowlist secret


def _run(tmp_path: Path, *args: str, value: str = _NEW) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_SCRIPT), *args], input=value + "\n", text=True,
                          capture_output=True, timeout=30,
                          env={"PATH": "/usr/bin:/bin", "ROTATE_PROD_SSH": "",
                               "ROTATE_ENV_FILES": f"{tmp_path}/.env {tmp_path}/.env.local"})


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """The value lands in every file that carries the variable, and in no output."""
    (tmp_path / ".env").write_text("A=1\nSPOTIFY_CLIENT_SECRET=old\nB=2\n")
    (tmp_path / ".env.local").write_text("SPOTIFY_CLIENT_SECRET=old-local\n")
    r = _run(tmp_path, "SPOTIFY_CLIENT_SECRET")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"SPOTIFY_CLIENT_SECRET={_NEW}" in (tmp_path / ".env").read_text()
    assert "A=1" in (tmp_path / ".env").read_text() and "B=2" in (tmp_path / ".env").read_text()
    assert f"SPOTIFY_CLIENT_SECRET={_NEW}" in (tmp_path / ".env.local").read_text()
    assert _NEW not in r.stdout and _NEW not in r.stderr, "the secret was printed"
    assert f"{len(_NEW)} caractères" in r.stdout


def test_the_database_password_is_refused(tmp_path) -> None:
    (tmp_path / ".env").write_text("DATABASE_PASSWORD=old\n")
    r = _run(tmp_path, "DATABASE_PASSWORD")
    assert r.returncode == 2 and "DATABASE_PASSWORD=old" in (tmp_path / ".env").read_text()


def test_an_empty_value_changes_nothing(tmp_path) -> None:
    (tmp_path / ".env").write_text("YOUTUBE_API_KEY=old\n")
    r = _run(tmp_path, "YOUTUBE_API_KEY", value="")
    assert r.returncode == 1 and "YOUTUBE_API_KEY=old" in (tmp_path / ".env").read_text()
