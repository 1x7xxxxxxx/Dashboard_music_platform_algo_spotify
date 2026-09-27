#!/usr/bin/env python3
"""Airflow's API, recorded in production and replayed during the dossier render (R242).

Type: Utility
Uses: src/dashboard/utils/airflow_monitor.py (AirflowMonitor — its `session` is replaced)
Triggers: `make charts-dossier AIRFLOW_REPLAY=1` (records, then capture.py replays)
Persists in: <out>/airflow_replay.json — OUTSIDE the repository (DAG names and run times,
             no secret: the record holds response bodies, never a header)

Fiches 74–76 were never rendered: the Airflow page reads Airflow's REST API, and the local
stack has no Airflow running. A tunnel to the production API answers 403 — the local
credentials are not production's, and production's are not ours to read. The dashboard
container in production already talks to its Airflow; the record is made THERE, with its
own session, and only the JSON bodies come back.

    python3 airflow_replay.py record <out>     # over ssh, in the prod dashboard container
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # the app package, from anywhere

# Runs INSIDE the production dashboard container: wraps the monitor's session, calls every
# getter the Airflow page uses, prints {request key: [status, body]}.
RECORDER = r'''
import json, sys, threading
sys.path.insert(0, "/app")
import requests
from urllib.parse import urlsplit
from src.dashboard.utils.airflow_monitor import AirflowMonitor
rec, lock = {}, threading.Lock()
def key(method, url, params=None, body=None):
    p = urlsplit(url).path.split("/api/v1", 1)[-1]
    return json.dumps([method, p, sorted((params or {}).items()), body], sort_keys=True, default=str)
real_get, real_post = requests.Session.get, requests.Session.post
def get(self, url, params=None, **kw):
    r = real_get(self, url, params=params, **kw)
    with lock:
        rec[key("GET", url, params)] = [r.status_code, r.json() if r.content else None]
    return r
def post(self, url, json=None, **kw):
    r = real_post(self, url, json=json, **kw)
    with lock:
        rec[key("POST", url, None, json)] = [r.status_code, r.json() if r.content else None]
    return r
requests.Session.get, requests.Session.post = get, post
m = AirflowMonitor()
m.get_dag_list(); m.get_all_dags_last_state(); m.get_dag_runs(); m.get_dag_runs(limit=100); m.get_kpis()
print(json.dumps(rec, default=str))
'''


def request_key(method: str, url: str, params=None, body=None) -> str:
    """The same key the recorder writes — the API path, never the host. Pure."""
    path = urlsplit(url).path.split("/api/v1", 1)[-1]
    return json.dumps([method, path, sorted((params or {}).items()), body],
                      sort_keys=True, default=str)


class _Response:
    def __init__(self, status: int, body):
        self.status_code, self._body = status, body
        self.content = b"x" if body is not None else b""

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"replay: HTTP {self.status_code}")


class ReplaySession:
    """A `requests.Session` stand-in answering from the record; unknown requests get a 404."""

    def __init__(self, records: dict):
        self.records, self.auth, self.headers = records, None, {}

    def _answer(self, key: str):
        status, body = self.records.get(key, [404, None])
        return _Response(status, body)

    def get(self, url, params=None, **_):
        return self._answer(request_key("GET", url, params))

    def post(self, url, json=None, **_):
        return self._answer(request_key("POST", url, None, json))

    def close(self) -> None:
        pass


def install(path: Path) -> bool:
    """Every AirflowMonitor built after this call reads the record. False when absent."""
    if not path.exists():
        return False
    records = json.loads(path.read_text(encoding="utf-8"))
    import types

    from src.dashboard.utils import airflow_monitor as mod
    real_init = mod.AirflowMonitor.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        self.session = ReplaySession(records)
    mod.AirflowMonitor.__init__ = init
    # `_runs_per_dag` builds one `requests.Session()` per thread: the module's `requests`
    # is swapped for one whose Session answers from the record too.
    mod.requests = types.SimpleNamespace(Session=lambda: ReplaySession(records))
    return True


def record(out: Path, host: str = "root@167.233.92.1") -> int:
    """Run the recorder in the production dashboard container; write <out>/airflow_replay.json."""
    cmd = ["ssh", host, 'docker exec -i $(docker ps --format "{{.Names}}" | grep -m1 dashboard) python -']
    res = subprocess.run(cmd, input=RECORDER, capture_output=True, text=True, timeout=180)
    line = next((ln for ln in reversed(res.stdout.splitlines()) if ln.startswith("{")), None)
    if res.returncode != 0 or line is None:
        print(f"❌ enregistrement Airflow impossible : {res.stderr.strip()[-200:]}", file=sys.stderr)
        return 1
    records = json.loads(line)
    (out / "airflow_replay.json").write_text(json.dumps(records), encoding="utf-8")
    print(f"✅ {len(records)} réponse(s) de l'API Airflow enregistrée(s) en production")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "record":
        sys.exit(record(Path(sys.argv[2]).resolve()))
    print(__doc__.split("\n\n")[-1], file=sys.stderr)
    sys.exit(2)
