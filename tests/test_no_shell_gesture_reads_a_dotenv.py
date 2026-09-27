"""R267 (critic d) — no shell gesture of Claude Code READS a `.env` file.

Type: Test
Uses: .claude/hooks/guard_destructive.py (_reads_an_env_file, check_command)

The settings deny the Read tool on `.env` files; the shell was open. The guard reads the
STRUCTURE of each segment: a reader command given a `.env`, any command fed one by `<`,
and both inside `$( )` or backticks. Writing a `.env` (`> .env`), testing its presence
(`test -f`), listing it, or TALKING about it (a commit message, a heredoc) is not reading.
`.env.example` is committed and public: exempt.

Mutation record (2026-09-28) : the reader set emptied → red ; the redirect branch removed
→ red ; the `.env.example` exemption removed → red on the allowed side ; the wrapper
branch (`_remote_command`) disabled → red on `bash -c`, `docker exec`, `ssh`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))
import guard_destructive as g  # noqa: E402

READS = ["cat .env", "grep KEY .env.local", "source ~/streamlytics/.env.local",
         "sudo cat /opt/app/.env.prod", "python3 x.py < .env", "python3 x.py <.env.local",
         "echo $(cat .env)", "echo `grep A .env`", "head -3 .env | wc -l",
         # security-specialist review (R267): the wrappers and the glob.
         "bash -c 'cat .env'", "docker exec -it api cat /opt/airflow/.env",
         "ssh root@host cat /opt/app/.env", "echo .env | xargs cat", "cat .env*"]
ALLOWED = ["cat .env.example", 'git commit -m "never cat .env"', "test -f .env.local",
           "ls -la .env", "cat <<EOF > .env\nA=1\nEOF", "cat x >> .env.local",
           "grep -rn dotenv src/", "docker exec api ls /app", "ssh root@host uptime",
           'bash -c "echo hi"', "echo hi | xargs cat"]


@pytest.mark.parametrize("cmd", READS)
def test_a_read_of_a_dotenv_is_blocked(cmd):
    assert g._reads_an_env_file(cmd), cmd
    verdict = g.check_command(cmd)
    assert verdict and verdict[0] == "block"


@pytest.mark.parametrize("cmd", ALLOWED)
def test_what_does_not_read_it_passes(cmd):
    assert g._reads_an_env_file(cmd) is None, cmd
