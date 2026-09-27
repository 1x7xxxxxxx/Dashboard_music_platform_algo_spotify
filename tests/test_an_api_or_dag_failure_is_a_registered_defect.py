"""R265 — an API exception or a DAG failure lands in `app_error_log`, like a dashboard one.

Type: Test
Uses: src/api/error_capture.py, src/utils/dag_callbacks.py, airflow/dags/*.py (ast)

Before: the registry `make error-inbox` reads was fed by the dashboard alone; twelve DAGs
carried the same six-line callback that only mailed. Critic (R265 b): factor first, then
register once — and never change the 500 the API returns or measures.

Mutation record (2026-09-28) : the handler no longer calling `_record` → red ; `on_failure`
letting the mail's exception escape → red ; one DAG given a local callback again → red.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import error_capture
from src.utils import dag_callbacks

ROOT = Path(__file__).resolve().parents[1]


def test_an_unhandled_api_exception_is_registered_and_stays_a_bare_500(monkeypatch):
    seen = []
    monkeypatch.setattr(error_capture, "_record", lambda req, exc: seen.append(
        (req.scope["route"].path, type(exc).__name__)))
    app = FastAPI()
    error_capture.install_error_registry(app)

    @app.get("/boom/{x}")
    def boom(x: int):
        raise RuntimeError("secret=abc")

    r = TestClient(app, raise_server_exceptions=False).get("/boom/3")
    assert r.status_code == 500 and r.text == "Internal Server Error"
    assert "secret" not in r.text
    assert seen == [("/boom/{x}", "RuntimeError")], "the route TEMPLATE groups the defect"


def test_a_dag_failure_mails_and_registers_even_when_the_mail_fails(monkeypatch):
    import src.utils.email_alerts as ea
    import src.utils.error_registry as er
    import src.database.postgres_handler as ph

    def mail_down(ctx):
        raise OSError("smtp down")
    got = []
    monkeypatch.setattr(ea, "dag_failure_callback", mail_down)
    monkeypatch.setattr(er, "record_error", lambda db, page, exc, **kw: got.append((page, kw)))
    monkeypatch.setattr(ph.PostgresHandler, "from_env_or_config",
                        classmethod(lambda cls: SimpleNamespace(close=lambda: None)))
    ctx = {"dag": SimpleNamespace(dag_id="youtube_daily"),
           "task_instance": SimpleNamespace(task_id="collect"),
           "dag_run": SimpleNamespace(conf={"artist_id": "12"}),
           "exception": ValueError("x")}
    dag_callbacks.on_failure(ctx)            # must not raise
    assert got == [("dag:youtube_daily.collect", {"artist_id": 12, "environment": "airflow"})]


def _local_callbacks() -> list[str]:
    out = []
    for p in sorted((ROOT / "airflow" / "dags").glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        out += [f"{p.name}:{n.name}" for n in tree.body if isinstance(n, ast.FunctionDef)
                and "failure_callback" in n.name]
    return out


def test_no_dag_carries_its_own_callback_not_vacuous():
    assert not _local_callbacks(), f"rappels locaux : {_local_callbacks()}"
    def wired_to_on_failure(path: Path) -> bool:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return any(isinstance(k, ast.Constant) and k.value == "on_failure_callback"
                   and isinstance(v, ast.Name) and v.id == "on_failure"
                   for d in ast.walk(tree) if isinstance(d, ast.Dict)
                   for k, v in zip(d.keys, d.values))
    wired = [p for p in (ROOT / "airflow" / "dags").glob("*.py") if wired_to_on_failure(p)]
    assert len(wired) >= 12, f"seulement {len(wired)} DAG(s) branchés sur on_failure"


def test_the_handler_never_runs_on_the_event_loop():
    """security-specialist (R265, HIGH): a sync psycopg2 call in an `async def` handler
    froze the API's single process. The handler must be a plain function."""
    import inspect
    app = FastAPI()
    error_capture.install_error_registry(app)
    handler = app.exception_handlers[Exception]
    assert not inspect.iscoroutinefunction(handler)


def test_a_database_failure_is_not_written_to_the_database(monkeypatch):
    import src.database.postgres_handler as ph
    opened = []
    monkeypatch.setattr(ph.PostgresHandler, "from_env_or_config",
                        classmethod(lambda cls: opened.append(1)))
    OperationalError = type("OperationalError", (Exception,), {})
    error_capture._record(SimpleNamespace(scope={}), OperationalError("db down"))
    assert opened == []


def test_the_secret_shapes_without_a_name_are_redacted():
    from src.utils.safe_error import redact
    jwt = "eyJ" + "hbGciOiJIUzI1" + ".eyJzdWIiOiIxMjM0" + ".SflKxwRJSMeKKF2QT4"
    stripe = "sk_" + "live_" + "abcdef123456"  # pragma: allowlist secret — a synthetic, split test value
    hook = "whsec_" + "ABCdef12345678"  # pragma: allowlist secret
    bearer = "Bearer " + "abcdefghijklmnop123"
    out = redact(f"{jwt} {stripe} {hook} {bearer} status=500")
    for secret in (jwt, stripe, hook, bearer.split()[1]):
        assert secret not in out
    assert "status=500" in out, "the rest of the message is kept"


def test_the_api_latency_has_a_measured_alert_per_route():
    """REQ-API-02 — p95 per route, with a threshold derived from a production measure."""
    import yaml
    rules = yaml.safe_load((ROOT / "deploy/prometheus/rules/streamlytics.yml").read_text(encoding="utf-8"))
    by_name = {r["alert"]: r for g in rules["groups"] for r in g["rules"]}
    lat = by_name["ApiLatencyDegraded"]
    assert "0.95" in lat["expr"] and "route" in lat["expr"]
    assert "0,93 s" in lat["annotations"]["symptom"], "the threshold names the measure it came from"
    assert "ApiServerErrors" in by_name
