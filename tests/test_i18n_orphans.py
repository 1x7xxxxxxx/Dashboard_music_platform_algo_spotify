"""Guard: no orphan EN translation keys (an EN entry never referenced by a t() call).

Complements test_i18n.test_every_static_t_key_has_en_entry (used→has-EN); this checks
the reverse (has-EN→used) so deleted/renamed features don't leave dead translations.
"""
import pathlib
import re

from src.dashboard.utils import i18n

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

# Keys built dynamically as t(f"<prefix>.{var}") — they can't be matched to a string
# literal, so their EN entries are legitimate even without a literal reference. Keep in
# sync with: grep -rhoE 't\(\s*f"[a-z0-9_.]+\.\{' src/dashboard
# `email.*` keys are consumed in src/utils/verification_email.py via the `_tr()` wrapper
# (and `email.welcome.step{i}` is built in a loop) — neither shape the literal matcher sees.
_DYNAMIC_PREFIXES = (
    # Les livrables, options et leviers de la prestation sont construits
    # depuis `utils/service_offer.py` — `t(liv.cle, liv.texte)`. Ce sont des
    # DONNÉES, pas des littéraux d'appel, exactement comme
    # `billing.service_credential.*`. Leur cohérence est gardée par
    # `tests/test_the_service_offer_says_who_does_the_work.py`.
    "service.liv.", "service.opt.", "service.levier.",
    "service.qui_fait_quoi",
    "email.",
    "algo.calib.", "algo.divnote.", "algo.label.", "algo.lever.", "algo.model.",
    "algo.regressor.", "algo.suppressed.", "common.month.", "credentials.field.",
    "credentials.guide.",
    # Built as t(f"credentials.resolve.{code}") from ResolutionError.code — the codes
    # themselves are enumerated in `platform_identity_resolver.RESOLUTION_CODES`, and
    # `test_a_link_is_enough_to_identify_a_tenant` checks every one has an entry.
    "credentials.resolve.",
    "export_csv.source.", "export_pdf.period.", "export_pdf.section.",
    # Construites par `t(f"meta_creatives.rank.{col}", label)` — les quatre
    # cadres du classement des créatives. `_RANG_PANNEAUX` les énumère, et
    # `test_the_ranking_names_every_panel_it_draws` vérifie que chacun a sa clé.
    "meta_creatives.rank.",
    # Idem pour les six cadres de la performance globale Meta Ads —
    # `test_the_global_perf_names_every_panel_it_draws` tient l'autre bout.
    "meta_ads_overview.perf.",
    # Les sources, catégories et fréquences de la page « Mon argent », construites
    # par `t(f"revenue_forecast.source.{s}")`, `…cat.{k}` et `…period.{k}`.
    # `_FLUX_NOMS`, `_CAT_COUTS` et le sélecteur de fréquence les énumèrent, et
    # `test_every_money_label_has_a_translation` tient l'autre bout.
    "revenue_forecast.source.",
    "revenue_forecast.cat.",
    "revenue_forecast.period.",
    # L'argumentaire des plans (`utils/plan_pitch._PITCH`) et les arguments du
    # service (`stripe_schema.SERVICE_CREDENTIALS`) sont des DONNÉES : leurs clés
    # ne sont pas des littéraux d'appel. `test_the_plan_pitch_matches_the_gate`
    # exige une traduction pour chacune — c'est lui qui tient l'autre bout.
    "pitch.",
    "billing.service_credential.",
    # Construites par `t(f"home.mode_{k}", MODES[k])` — les trois modes d'affichage de
    # la courbe. `MODES` les énumère, et `test_every_mode_is_offered_and_named`
    # (test_the_live_chart_matches_the_illustration) vérifie qu'aucun n'est sans
    # libellé : le prefix n'ouvre donc pas une porte sans contrôle.
    "home.mode_",
    "home.dag.", "meta_ads_overview.dim.", "meta_ads_overview.gender.", "meta_breakdowns.dim.",
    "meta_breakdowns.family.", "meta_breakdowns.grain.", "meta_cpr_optimizer.rec.",
    "meta_creatives.metric.", "nav.item.", "nav.section.",
    "onboarding.caveat.", "onboarding.value.",
    # `t(f"spotify_s4a_combined.source.{src}")` — une clé par SOURCE d'abonnés, et
    # les sources sont énumérées par `v_spotify_followers_daily` (migration 120) :
    # 's4a_csv' et 'spotify_api'. `test_every_follower_source_is_named` (dans
    # test_the_spotify_page_reads_only_the_gold_layer) vérifie qu'aucune n'est sans
    # libellé — le préfixe n'ouvre donc pas une porte sans contrôle.
    "spotify_s4a_combined.source.",
    # `t(f"meta_x_spotify.series_{col}")` — une clé par COLONNE tracée, et les
    # colonnes sont énumérées par `_SERIES` dans la vue.
    # `test_every_plotted_series_is_named` (dans
    # `test_the_campaign_view_plots_what_it_promises.py`) vérifie qu'aucune n'est
    # sans libellé : le préfixe n'ouvre donc pas une porte sans contrôle.
    "meta_x_spotify.series_",
    # `for key, default, image in (…)` : les trois promesses du bloc 1 passent
    # leur clé en VARIABLE, une par figure d'exemple (2026-09-04).
    #
    # `t(f"onboarding.col.{name}")` et `col_hint` : un titre et une aide par colonne
    # du sélecteur, construits en bouclant sur `SETUP_COLUMN_ORDER` (2026-09-04).
    # `onboarding.download_guide_` a disparu le même jour avec les deux boutons de
    # téléchargement du guide, retirés de la page de bienvenue.
    "onboarding.brief_", "onboarding.col.", "onboarding.col_hint.", "upgrade.page.",
    "upload_csv.platform.",
)

_KEY_RE = re.compile(r'\b_?t(?:ranslate)?\(\s*["\']([a-zA-Z0-9_.]+)["\']')


def _used_keys() -> set[str]:
    used: set[str] = set()
    for p in _SRC.rglob("*.py"):
        if "i18n_catalog" in str(p):
            continue
        used |= set(_KEY_RE.findall(p.read_text(encoding="utf-8")))
    return used


def test_no_orphan_en_keys():
    used = _used_keys()
    en = set(i18n._TR.get("en", {}))
    orphans = sorted(
        k for k in en
        if k not in used and not any(k.startswith(p) for p in _DYNAMIC_PREFIXES)
    )
    assert not orphans, (
        f"{len(orphans)} orphan EN key(s) — no t() reference, remove them or add the "
        f"dynamic prefix to _DYNAMIC_PREFIXES:\n" + "\n".join(orphans)
    )


# ── Un marqueur qu'une traduction PERD — 2026-09-18 ─────────────────────────
#
# `test_no_orphan_en_keys` vérifie qu'une clé anglaise a bien un emploi. Il ne regarde
# jamais ce que la TRADUCTION fait des marqueurs de format, et c'est par là qu'un
# message perd son contenu sans que rien ne rougisse.
#
# Mesuré ce jour-là : `credentials.meta.test_ok_account`
#   FR (défaut, `_platform_meta.py:84`) : « … accessible ✅**{ig}** »
#   EN (catalogue)                      : « … reachable ✅ »   ← `{ig}` absent
#
# L'appel est `.format(name=…, acc=…, ig=ig_suffix)`. **`str.format` ignore un kwarg en
# trop sans lever** : le lecteur francophone voyait la confirmation Instagram construite
# dix lignes plus haut, le lecteur anglophone la perdait **en silence**.
#
# La forme INVERSE — une traduction portant un marqueur que le défaut n'a pas — lève un
# `KeyError` en production. Elle est donc bruyante, et les deux directions méritent le
# même garde : celle qui perd est muette, celle qui ajoute plante.
# ⚠️ La spécification de format fait partie du marqueur (`{total:,.2f}`), et la
# comparer ferait rougir sur une traduction PARFAITEMENT valide. On compare les
# NOMS. Mon premier motif exigeait `\}` juste après le nom : il a signalé
# `imusician.roi_total_help` comme « perdant {total} » alors que la traduction le
# porte — un faux positif. Mais en le lisant, on a trouvé un VRAI défaut dessous,
# et c'est pour ça que la ligne suivante existe.
_MARQUEUR = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)[^{}]*\}")


def _defauts_du_code() -> dict[str, str]:
    """`{clé: texte par DÉFAUT}` — le second argument littéral de chaque `t(...)`."""
    import ast
    out: dict[str, str] = {}
    for path in _SRC.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:      # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") in {"t", "_t"}
                    and len(node.args) >= 2):
                continue
            cle, defaut = node.args[0], node.args[1]
            if (isinstance(cle, ast.Constant) and isinstance(cle.value, str)
                    and isinstance(defaut, ast.Constant)
                    and isinstance(defaut.value, str)):
                out.setdefault(cle.value, defaut.value)
    return out


def test_the_default_extraction_is_not_vacuous() -> None:
    """Sans extraction, le test ci-dessous est vert sur un catalogue entièrement faux."""
    d = _defauts_du_code()
    assert len(d) > 200, (
        f"seulement {len(d)} défaut(s) littéral(aux) extrait(s) des appels `t(...)` — "
        "l'extraction a raté sa cible.")
    porteurs = [k for k, v in d.items() if _MARQUEUR.search(v)]
    assert len(porteurs) > 20, (
        f"seulement {len(porteurs)} défaut(s) portent un marqueur `{{nom}}` — "
        "le prédicat de marqueur ne mord pas, donc il ne peut rien séparer.")


def test_a_translation_keeps_every_marker_its_default_carries() -> None:
    """Une traduction porte exactement les marqueurs de son défaut.

    Les deux sens comptent, pour deux raisons opposées : un marqueur EN PLUS lève un
    `KeyError` chez l'utilisateur ; un marqueur EN MOINS ne lève rien et lui retire
    l'information. C'est le second qui a vécu six mois.
    """
    defauts = _defauts_du_code()
    en = i18n._TR.get("en", {})
    perdus, ajoutes = [], []
    for cle, defaut in defauts.items():
        trad = en.get(cle)
        if not isinstance(trad, str):
            continue
        m_def = set(_MARQUEUR.findall(defaut))
        m_tra = set(_MARQUEUR.findall(trad))
        if m_def - m_tra:
            perdus.append((cle, sorted(m_def - m_tra)))
        if m_tra - m_def:
            ajoutes.append((cle, sorted(m_tra - m_def)))
    assert not perdus, (
        "".join(f"\n  {c} perd {m}" for c, m in sorted(perdus)) +
        "\n\nLa traduction anglaise ne porte pas un marqueur que son défaut porte. "
        "`str.format` ignore le kwarg en trop SANS LEVER : le lecteur anglophone perd "
        "l'information en silence. Ajouter le marqueur, ou retirer le kwarg des deux "
        "côtés si l'information n'a plus lieu d'être.")
    assert not ajoutes, (
        "".join(f"\n  {c} ajoute {m}" for c, m in sorted(ajoutes)) +
        "\n\nLa traduction porte un marqueur que son défaut n'a pas : `.format()` "
        "lèvera un `KeyError` chez l'utilisateur anglophone.")
