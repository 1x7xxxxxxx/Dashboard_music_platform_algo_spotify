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
from src.utils.diagnosis_text import as_markdown

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
    """{platform: (ok, reason, probed_at, category)} — the verdicts. Never raises.

    `category` names the SITUATION (migration 086) and is `None` for a verdict
    written before it, or by a probe that does not name one.

    The fallback is not decoration. This module's `except` turns an unreadable
    memory into « never measured », which blanks the whole « Répond » column — so a
    target where 086 has not run yet would silently lose it. It reads the four old
    columns instead, which is exactly today's behaviour.
    """
    try:
        rows = db.fetch_query(
            "SELECT platform, ok, reason, probed_at, category FROM "
            "tenant_platform_probe WHERE artist_id = %s", (artist_id,))
        return {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}
    except Exception as e:  # noqa: BLE001 — column absent, or no table at all
        logger.warning("probe memory: reading without `category` (%s)", type(e).__name__)
    try:
        rows = db.fetch_query(
            "SELECT platform, ok, reason, probed_at FROM tenant_platform_probe "
            "WHERE artist_id = %s", (artist_id,))
    except Exception as e:  # noqa: BLE001 — no table yet is "never measured"
        logger.warning("probe memory unreadable: %s", type(e).__name__)
        return {}
    return {r[0]: (r[1], r[2], r[3], None) for r in rows}


def save_probe(db, artist_id: int, platform: str, ok: bool, reason: str,
               category: str | None = None) -> None:
    """Remember one verdict. Overwrites — we want the latest, not a history."""
    db.execute_query(
        "INSERT INTO tenant_platform_probe "
        "  (artist_id, platform, ok, reason, category, probed_at) "
        "VALUES (%s, %s, %s, %s, %s, now()) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "  ok = EXCLUDED.ok, reason = EXCLUDED.reason, "
        "  category = EXCLUDED.category, probed_at = EXCLUDED.probed_at",
        (artist_id, platform, bool(ok), (reason or "")[:500], category))


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
        # La situation voyage SUR le message (`platform_probes.tagged`) : `(ok,
        # reason)` est un contrat public, dépaqueté en deux à dix-neuf endroits.
        from src.utils.platform_probes import category_of
        category = category_of(reason)
        try:
            save_probe(db, artist_id, platform, ok, reason, category)
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
    ok, reason, probed_at = remembered[0], remembered[1], remembered[2]
    age = _age_label(probed_at)
    if ok:
        return "amber", "✅", t(
            "matrix.tip_ok_no_data",
            "La plateforme répond ({age}) mais aucune donnée n'est encore arrivée — "
            "la première collecte n'a peut-être pas eu lieu.").format(age=age)
    return "red", "✖", f"{reason or ''} ({age})"


# Les deux sources de Spotify, dites avec les mots de l'artiste. « Spotify API » et
# « Spotify S4A » sont des étiquettes internes de `freshness_monitor` ; S4A est un
# sigle, et « API » un mot qu'il n'a pas à connaître pour déposer un fichier.
_SOURCE_LABELS = {
    "Spotify API": "Spotify (automatique, via ton lien d'artiste)",
    "Spotify S4A": "Spotify for Artists (ton fichier CSV)",
}
_SOURCE_HINTS = {
    "Spotify API": "Se règle dans Credentials API → Spotify. Rien à déposer.",
    "Spotify S4A": ("Se dépose dans « Ajouter mes chiffres Spotify for Artists & "
                    "Apple ». C'est ce fichier qui porte tes playlists et Discovery "
                    "Mode."),
}


def _shape_cell(row: dict, identities: dict) -> tuple:
    """(state, glyph, tooltip) pour « Format » — la valeur a-t-elle la bonne forme ?

    Demandé le 2026-09-04 : « rajoute un step saisie des identifiants qui n'est pas
    le même que configuré, car on peut l'avoir mal renseigné ». C'est exactement la
    distinction que la matrice ne portait pas : « Configuré » ne disait que « une
    valeur est là », et une valeur peut être là ET fausse.

    La forme n'est PAS la validité. Un Channel ID bien formé peut désigner une chaîne
    qui n'existe pas — c'est « Répond » qui tranche, et l'infobulle le dit pour que ce
    ✅ ne soit pas lu comme une garantie. Ce que cette colonne attrape, c'est ce que
    le formulaire ne peut plus laisser passer mais que d'anciennes lignes portent
    encore : une URL entière dans un champ numérique, un @pseudo à la place d'un id.
    """
    if row["status"] == "todo":
        return "grey", "—", t("matrix.tip_shape_na",
                              "Rien à vérifier tant qu'aucun identifiant n'est saisi.")
    value = (identities or {}).get(row["key"])
    if not value:
        # Saisi mais illisible ici (identité miroir, plateforme sans motif) : on ne
        # sait pas, et « on ne sait pas » ne se dessine pas en vert.
        return "grey", "?", t("matrix.tip_shape_unknown",
                              "Forme non vérifiable pour cette plateforme.")
    from src.utils.tenant_identity import identity_is_well_formed
    if identity_is_well_formed(row["key"], value):
        return "green", "✅", t(
            "matrix.tip_shape_ok",
            "L'identifiant a la forme attendue. Cela ne prouve pas qu'il est le "
            "bon — c'est la colonne « Répond » qui le dit.")
    return "red", "✖", t(
        "matrix.tip_shape_bad",
        "Cet identifiant n'a pas la forme attendue : il a probablement été collé "
        "avec du texte autour. Ressaisis-le.")


def read_identities(db, artist_id: int) -> dict:
    """{plateforme logique: valeur d'identité} — ce qui est réellement stocké.

    Une seule requête, sur la connexion du rendu (règle transverse #9). Ne lève
    jamais : une forme non vérifiable s'affiche « ? », jamais « ✖ ».
    """
    import json

    from src.utils.tenant_identity import PLATFORM_IDENTITIES
    out: dict = {}
    try:
        rows = db.fetch_query(
            "SELECT platform, extra_config FROM artist_credentials WHERE artist_id = %s",
            (artist_id,))
    except Exception as e:  # noqa: BLE001 — la colonne « Format » est un bonus
        logger.warning("identities unreadable: %s", type(e).__name__)
        return {}
    extra_by_platform = {}
    for platform, extra in rows:
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
    for logical, spec in PLATFORM_IDENTITIES.items():
        value = (extra_by_platform.get(spec.storage) or {}).get(spec.field)
        if value:
            out[logical] = str(value)
    return out


def row_cells(r: dict, identities: dict, probes: dict) -> list[tuple]:
    """Les QUATRE cellules d'une ligne : Saisi · Format · Répond · Données.

    Extraites de `render_status_matrix` le 2026-09-05 pour que l'onglet de saisie
    montre les mêmes — « intègre les indicateurs verts orange rouge sur toutes les
    colonnes ». La matrice les calculait dans sa boucle d'affichage ; les recopier
    dans l'onglet aurait créé deux verdicts pour un même fait, ce qui est le défaut
    que le partage de `_box` et `_responds_cell` évitait déjà à moitié.

    Rend `(state, glyph, tooltip)` par colonne, dans l'ordre de la matrice.
    """
    configured = r["status"] != "todo"
    data_state = {"ok": "green", "stale": "amber", "quiet": "amber",
                  "no_data": "red", "broken": "amber", "todo": "grey"}[r["status"]]
    return [
        ("green" if configured else "grey",
         "✅" if configured else "○",
         t("matrix.tip_set", "Identifiant saisi.") if configured
         else t("matrix.tip_unset", "Aucun identifiant saisi.")),
        _shape_cell(r, identities),
        _responds_cell(r, probes),
        (data_state, r["icon"], r["status_label"]),
    ]


_COLUMN_TITLES = ("Saisi", "Format", "Répond", "Données")


def render_platform_state(db, artist_id: int, platform_key: str) -> None:
    """Les mêmes pastilles que la matrice, pour UNE plateforme, en tout petit.

    Demandé le 2026-09-05 : « mets uniquement des états vert orange rouge très petit
    que pour l'onglet sélectionné, copié de l'onglet état de tes plateformes ».

    Elles REMPLACENT la phrase « Valeur enregistrée le … — enregistrée ne veut pas
    dire vérifiée ». Cette phrase disait la bonne chose et la disait mal : elle
    expliquait en une ligne de prose une nuance que trois pastilles montrent d'un
    coup d'œil, et elle la répétait sous chaque onglet.

    « Copié de » est à prendre au pied de la lettre : `_box` et `_responds_cell` sont
    les fonctions de la matrice, pas des jumelles. Deux surfaces qui décrivent le même
    état avec deux codes couleur, c'est le désaccord qu'aucune des deux ne peut voir —
    et ce dépôt l'a payé assez souvent.
    """
    from src.utils.artist_readiness import artist_readiness

    try:
        rows = artist_readiness(db, artist_id)
        probes = read_probes(db, artist_id)
    except Exception:      # noqa: BLE001 — décoratif : jamais un mur devant la saisie
        return

    # `platform_key` est une clé d'ONGLET (`meta`), la matrice raisonne en clés
    # LOGIQUES (`meta`, `instagram`). Un onglet peut donc porter deux lignes, et
    # c'est voulu : Instagram peut être muet pendant que Meta Ads répond.
    from src.dashboard.views.credentials.router import platform_destination
    mine = [r for r in rows
            if platform_destination(r["key"]) == f"tab:{platform_key}"]
    if not mine:
        return

    identities = read_identities(db, artist_id)
    blocks = []
    for r in mine:
        # Le NOM de la colonne sous sa pastille : quatre carrés colorés sans étiquette
        # sont un rébus. La matrice a un en-tête de tableau ; ici il n'y a qu'une ligne
        # ou deux, donc l'étiquette voyage avec la pastille.
        boxes = []
        for (state, glyph, tip), title in zip(row_cells(r, identities, probes),
                                              _COLUMN_TITLES):
            cell = _box(state, glyph, f'{r["label"]} — {tip}')
            caption = (f'<div style="font-size:0.7em;opacity:.65;margin-top:1px">'
                       f'{_html.escape(title)}</div>')
            boxes.append('<div style="display:inline-block;text-align:center;'
                         f'margin-right:10px">{cell}{caption}</div>')
        # Le nom de la plateforme n'est écrit QUE s'il y a deux lignes — c'est-à-dire
        # sur l'onglet Meta / Instagram, où il distingue deux sources qui se saisissent
        # au même endroit et échouent séparément. Ailleurs, l'onglet sélectionné le dit
        # déjà : « retire SoundCloud situé à gauche des barres, on a déjà l'info dans
        # le menu sélectionné » (2026-09-05).
        label = ""
        if len(mine) > 1:
            label = (f'<span style="font-size:0.8em;opacity:.75;margin-right:6px">'
                     f'{_html.escape(r["label"])}</span>')
        blocks.append(label + "".join(boxes))
    st.markdown('<div style="font-size:0.85em;margin-bottom:6px">'
                + "<br>".join(blocks) + "</div>", unsafe_allow_html=True)


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

    # Lue APRÈS le retour compact : le bandeau d'accueil n'affiche pas la colonne
    # « Format », il ne doit pas payer sa requête (règle transverse #9 — une vue
    # ouvre une connexion, on n'y ajoute pas des lectures qu'elle n'affiche pas).
    identities = read_identities(db, artist_id)

    # La légende, ICI et une seule fois — pas recopiée par chaque page qui appelle.
    # Trois surfaces l'écrivaient chacune à sa façon, et deux d'entre elles ne
    # disaient pas ce que « Répond » et « Données » veulent dire. Demandé le
    # 2026-09-04 : « explique ce que veulent dire la colonne répond et données +
    # rajoute une légende en petit à côté d'état des plateformes ».
    st.caption(t(
        "matrix.legend_inline",
        "**Saisi** : tu as entré un identifiant · **Format** : il a la forme "
        "attendue · **Répond** : la plateforme nous a répondu quand on l'a "
        "interrogée · **Données** : des chiffres sont réellement arrivés chez nous. "
        "L'objectif est quatre ✅ par ligne."))

    _W = [3, 1, 1, 1, 1, 4]
    header = st.columns(_W)
    for col, label, tip in zip(header, (
            t("matrix.col_platform", "**Plateforme**"),
            t("matrix.col_set", "**Saisi**"),
            t("matrix.col_shape", "**Format**"),
            t("matrix.col_responds", "**Répond**"),
            t("matrix.col_data", "**Données**"),
            t("matrix.col_action", "**Prochaine étape**")), (
            None,
            t("matrix.help_set", "Un identifiant est enregistré pour cette plateforme."),
            t("matrix.help_shape",
              "Cet identifiant a la forme que la plateforme attend. Il peut être "
              "bien formé et rester faux — c'est « Répond » qui le dit."),
            t("matrix.help_responds",
              "La plateforme a répondu correctement la dernière fois qu'on l'a "
              "interrogée. Des données fraîches valent réponse : dans ce cas rien "
              "n'est appelé."),
            t("matrix.help_data",
              "Des lignes sont arrivées dans notre base pour toi. C'est la seule "
              "preuve qui compte pour tes graphiques."),
            None)):
        col.markdown(label, help=tip)

    for r in rows:
        cols = st.columns(_W)
        # Le nom, et SOUS lui l'endroit où ça se règle. « Meta Ads » et « Instagram »
        # sont deux lignes parce que ce sont deux collectes, mais elles se saisissent
        # dans le même onglet — et rien ne le disait.
        cols[0].markdown(_html.escape(r["label"]))
        if r.get("where"):
            cols[0].caption(_html.escape(r["where"]))

        # Les quatre cellules viennent de `row_cells`, comme celles de l'onglet de
        # saisie. Elles étaient calculées ICI, dans la boucle d'affichage ; les
        # extraire sans rebrancher la matrice aurait laissé DEUX copies de la règle —
        # et c'est exactement ce qui s'est produit le 2026-09-05, pendant une heure,
        # jusqu'à ce que le garde le dise.
        for _i, (_state, _glyph, _tip) in enumerate(row_cells(r, identities, probes), 1):
            cols[_i].markdown(_box(_state, _glyph, _tip), unsafe_allow_html=True)

        remembered = probes.get(r["key"])
        action = r["next_action"]
        # LE MÊME ORDRE QUE `_responds_cell`, qui rend sur `status` AVANT de lire
        # `probes`. Ici il manquait : `next_action(…, OK)` rend `""`, donc une ligne
        # entièrement verte affichait en « Prochaine étape » la raison d'une sonde
        # rouge — « User ID 377065610 joignable, mais aucun titre public », à côté de
        # 358 lignes réellement collectées (2026-09-05). Une mesure qui a eu lieu bat
        # une prédiction ; la sonde n'a rien à dire d'une source qui livre.
        if (remembered is not None and not remembered[0]
                and r["status"] not in _DATA_PROVES_IT):
            action = remembered[1] or action
        # `as_markdown` only fixes the line breaks: a single `\n` is not a break in
        # markdown, so the two bullets of a two-case diagnosis would run into one.
        # The escape stays — the tail of this string is a platform's own answer.
        cols[5].caption(
            as_markdown(_html.escape(action)) if action else "—")

        # Une plateforme prouvée par PLUSIEURS sources se détaille sous sa ligne.
        # Spotify en a deux — l'API et l'import CSV Spotify for Artists — et la
        # ligne unique ne montrait que la meilleure : « 🟢 » pouvait vouloir dire
        # « l'API remonte » aussi bien que « tu as déposé un CSV il y a trois mois »,
        # deux situations qui appellent des gestes opposés. Demandé le 2026-09-04.
        _sources = r.get("by_source") or {}
        if len(_sources) > 1:
            for _src, _d in _sources.items():
                sub = st.columns(_W)
                sub[0].caption("　↳ " + _html.escape(_SOURCE_LABELS.get(_src, _src)))
                sub[4].markdown(
                    _box({"ok": "green", "stale": "amber", "quiet": "amber",
                          "no_data": "red", "broken": "amber",
                          "todo": "grey"}[_d["status"]],
                         _d["icon"], _d["status_label"]),
                    unsafe_allow_html=True)
                sub[5].caption(_html.escape(
                    _SOURCE_HINTS.get(_src, _d["status_label"])))

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
