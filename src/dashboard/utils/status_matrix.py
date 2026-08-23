"""The setup matrix: three boxes per platform, one renderer, four surfaces.

Type: Utility
Uses: artist_readiness, platform_probes, tenant_platform_probe
Triggers: credentials page, onboarding wizard, home banner, 🚦 Santé onboarding
Persists in: tenant_platform_probe (only when someone presses "Vérifier maintenant")

Why one module — 2026-08-22.

Before this, every surface drew its own indicator: `_ICON` in artist_readiness,
`_STATE_ICON` in credentials, `_STATE_COLOR` in home, and an inline tri-state in the
credentials KPI strip. Four conventions, none shared, and the KPI strip's second axis
was the FLEET's Airflow state — it could read 🟢 while this particular artist had zero
rows. Putting the matrix on four pages without one renderer would have made that
worse, not better.

The three boxes, which are steps 2, 3 and 4 of `make artist-preflight` made visible:

    Configuré  — the artist entered an identity           (declared_identities)
    Répond     — the platform answered correctly          (see below)
    Données    — rows actually landed                     (artist_readiness status)

**Rendering costs zero API calls**, and the reason is the same one that made the
nightly probe cheap: data arriving already PROVES the credential works. So

  * status OK / STALE / QUIET  → Répond is ✅ by implication, nothing is called;
  * status NO_DATA / BROKEN with a remembered probe → that verdict and its age;
  * status NO_DATA / BROKEN with none → `?`, never a ✅.

The last line is the rule that matters: a platform nobody has measured must never
render as one that was measured and passed.
"""
from __future__ import annotations

import html as _html
import logging
from datetime import datetime, timezone

import streamlit as st

from src.dashboard.utils.i18n import t

logger = logging.getLogger(__name__)

# One place, and one only, that says what a box looks like.
_GREEN, _RED, _GREY, _AMBER = "#28a745", "#dc3545", "#adb5bd", "#e67e22"

# Statuts qui prouvent la connexion par la donnée elle-même, sans sonde.
#
# Le set existe encore pour nommer l'idée, mais `_responds_cell` les traite désormais
# SÉPARÉMENT : les trois prouvent la connexion, un seul (`ok`) prouve qu'elle est vivante
# AUJOURD'HUI. Les fondre dans un unique « ✅ Des données arrivent » a fait lire « tout va
# bien » à un artiste dont la source était morte depuis des mois.
_DATA_PROVES_IT = frozenset({"ok", "stale", "quiet"})


def _box(state: str, glyph: str, tip: str) -> str:
    """One coloured cell. `state` ∈ green|red|grey|amber."""
    colour = {"green": _GREEN, "red": _RED, "grey": _GREY, "amber": _AMBER}[state]
    return (f'<div title="{_html.escape(tip)}" style="display:inline-block;'
            f'min-width:34px;text-align:center;border-radius:6px;padding:2px 6px;'
            f'margin-right:4px;background:{colour}22;border:1px solid {colour};'
            f'font-size:0.95em">{glyph}</div>')


def _age_label(probed_at) -> str:
    if probed_at is None:
        return ""
    now = datetime.now(timezone.utc)
    if probed_at.tzinfo is None:
        probed_at = probed_at.replace(tzinfo=timezone.utc)
    hours = (now - probed_at).total_seconds() / 3600
    if hours < 1:
        return t("matrix.age_now", "à l'instant")
    if hours < 48:
        return t("matrix.age_hours", "il y a {n} h").format(n=int(hours))
    return t("matrix.age_days", "il y a {n} j").format(n=int(hours // 24))


def read_probes(db, artist_id: int) -> dict:
    """{platform: (ok, reason, probed_at)} — the remembered verdicts. Never raises."""
    try:
        rows = db.fetch_query(
            "SELECT platform, ok, reason, probed_at FROM tenant_platform_probe "
            "WHERE artist_id = %s", (artist_id,))
    except Exception as e:  # noqa: BLE001 — no table yet is "never measured"
        logger.warning("probe memory unreadable: %s", type(e).__name__)
        return {}
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def save_probe(db, artist_id: int, platform: str, ok: bool, reason: str) -> None:
    """Remember one verdict. Overwrites — we want the latest, not a history."""
    db.execute_query(
        "INSERT INTO tenant_platform_probe (artist_id, platform, ok, reason, probed_at) "
        "VALUES (%s, %s, %s, %s, now()) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "  ok = EXCLUDED.ok, reason = EXCLUDED.reason, probed_at = EXCLUDED.probed_at",
        (artist_id, platform, bool(ok), (reason or "")[:500]))


def run_probes_now(db, artist_id: int, platforms) -> int:
    """Probe each platform once and remember the answer. Returns how many ran.

    Isolated per platform: one unreachable API must not lose the other four.
    """
    from src.utils.platform_probes import probe

    done = 0
    for platform in platforms:
        try:
            result = probe(db, artist_id, platform)
        except Exception as e:  # noqa: BLE001
            logger.warning("probe crashed for %s: %s", platform, type(e).__name__)
            continue
        if result is None:          # unavailable ≠ a verdict
            continue
        ok, reason = result
        try:
            save_probe(db, artist_id, platform, ok, reason)
            done += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("could not remember the probe for %s: %s",
                           platform, type(e).__name__)
    return done


def _responds_cell(row: dict, probes: dict) -> tuple:
    """(state, glyph, tooltip) for the « Répond » box."""
    platform, status = row["key"], row["status"]
    if status == "todo":
        return "grey", "—", t("matrix.tip_not_set",
                              "Rien à vérifier tant que l'identifiant n'est pas saisi.")
    # « Des données arrivent » n'est vrai qu'au PRÉSENT. `stale` et `quiet` prouvent
    # aussi que la connexion a fonctionné, mais les annoncer en vert avec la même phrase
    # a fait lire « tout va bien » à un artiste dont la source était morte depuis des
    # mois (remonté en test, 2026-08-23). Le constat ne change pas — la connexion EST
    # prouvée — seule la couleur et le temps du verbe le disent honnêtement.
    if status == "ok":
        return "green", "✅", t(
            "matrix.tip_data_proves",
            "Des données arrivent — la connexion fonctionne, aucune vérification "
            "nécessaire.")
    if status == "stale":
        return "amber", "✅", t(
            "matrix.tip_data_proved_then_stopped",
            "La connexion a fonctionné — des données sont arrivées, mais plus "
            "récemment. Rien à reconfigurer : voir la colonne « Données ».")
    if status == "quiet":
        return "amber", "⏸️", t(
            "matrix.tip_connected_nothing_to_send",
            "La connexion fonctionne ; cette source n'a simplement rien à envoyer en "
            "ce moment. Ce n'est pas une panne.")
    remembered = probes.get(platform)
    if remembered is None:
        return "grey", "?", t(
            "matrix.tip_never_probed",
            "Jamais vérifié. Clique sur « Vérifier maintenant » pour interroger la "
            "plateforme.")
    ok, reason, probed_at = remembered
    age = _age_label(probed_at)
    if ok:
        return "amber", "✅", t(
            "matrix.tip_ok_no_data",
            "La plateforme répond ({age}) mais aucune donnée n'est encore arrivée — "
            "la première collecte n'a peut-être pas eu lieu.").format(age=age)
    return "red", "✖", f"{reason or ''} ({age})"


def render_status_matrix(db, artist_id: int, *, compact: bool = False,
                         allow_probe: bool = True, key_suffix: str = "") -> list:
    """Draw the matrix and return the readiness rows.

    NEVER opens a database connection: `db` is handed in. Every view file in this
    repo is capped at one `get_db_connection()` by
    `tests/test_view_connection_budget.py`, and the pages this renders on already
    spend theirs.

    `compact=True` collapses to a single line of glyphs, for the home banner.
    """
    from src.utils.artist_readiness import artist_readiness

    rows = artist_readiness(db, artist_id)      # no probe= : zero API calls on render
    probes = read_probes(db, artist_id)

    if compact:
        line = "".join(
            _box(*_responds_cell(r, probes)[:2],
                 f'{r["label"]} — {r["status_label"]}') for r in rows)
        st.markdown(line, unsafe_allow_html=True)
        return rows

    header = st.columns([3, 1, 1, 1, 4])
    for col, label in zip(header, (
            t("matrix.col_platform", "**Plateforme**"),
            t("matrix.col_set", "**Configuré**"),
            t("matrix.col_responds", "**Répond**"),
            t("matrix.col_data", "**Données**"),
            t("matrix.col_action", "**Prochaine étape**"))):
        col.markdown(label)

    for r in rows:
        cols = st.columns([3, 1, 1, 1, 4])
        cols[0].markdown(_html.escape(r["label"]))

        configured = r["status"] != "todo"
        cols[1].markdown(
            _box("green" if configured else "grey",
                 "✅" if configured else "○",
                 t("matrix.tip_set", "Identifiant saisi.") if configured
                 else t("matrix.tip_unset", "Aucun identifiant saisi.")),
            unsafe_allow_html=True)

        cols[2].markdown(_box(*_responds_cell(r, probes)), unsafe_allow_html=True)

        # `quiet` était vert : un compte Meta sans campagne active s'affichait « ✅ »
        # avec ZÉRO ligne de données. C'est le bon état (rien à collecter n'est pas une
        # panne), mais ce n'est pas la même chose que « des données sont là ». L'icône
        # portait déjà la nuance (⏸️, `artist_readiness._ICON`) ; la couleur la niait.
        data_state = {"ok": "green", "stale": "amber", "quiet": "amber",
                      "no_data": "red", "broken": "amber", "todo": "grey"}[r["status"]]
        cols[3].markdown(
            _box(data_state, r["icon"], r["status_label"]), unsafe_allow_html=True)

        # The next step, and for a red platform that is the LIVE reason when we have
        # one — the same sentence the nightly alert carries.
        remembered = probes.get(r["key"])
        action = r["next_action"]
        if remembered is not None and not remembered[0]:
            action = remembered[1] or action
        cols[4].caption(_html.escape(action) if action else "—")

    if allow_probe:
        checkable = [r["key"] for r in rows if r["status"] != "todo"]
        if checkable and st.button(
                t("matrix.check_now", "🔌 Vérifier maintenant"),
                key=f"matrix_probe_{artist_id}_{key_suffix}",
                help=t("matrix.check_help",
                       "Interroge chaque plateforme configurée et mémorise sa "
                       "réponse. Rien n'est appelé tant que tu ne cliques pas.")):
            with st.spinner(t("matrix.checking", "Vérification en cours…")):
                n = run_probes_now(db, artist_id, checkable)
            st.toast(t("matrix.checked", "{n} plateforme(s) vérifiée(s)").format(n=n),
                     icon="✅")
            st.rerun()

    return rows
