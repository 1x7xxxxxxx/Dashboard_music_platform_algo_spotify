"""Les définitions de la couche or qui DOIVENT coïncider, et la preuve qu'elles coïncident.

Type: Utility
Uses: nothing (stdlib only — importable sans Airflow, comme value_monitor)
Triggers: alert_monitor.check_gold_invariants, tests/test_the_gold_layer_agrees_with_itself.py
Depends on: les vues or (migrations 097, 101-111)
Persists in: nothing

Le trou que ce module ferme
---------------------------
ADR-019 garantit qu'une métrique a **une seule définition**. Elle ne garantit pas que
deux définitions *censées* coïncider coïncident — et c'est une propriété différente,
qu'il faut vérifier sur les DONNÉES, pas sur le code.

Mesuré le 2026-09-12 : `meta_insights_performance` et `meta_insights_performance_day`
répondent à la même question et divergeaient d'un **facteur deux** (6 165,65 € contre
3 087,82 € pour l'artiste 1, en production, depuis des semaines). Le code était
cohérent de chaque côté ; aucun test ne comparait les deux côtés.

Ce que `check_metric_bounds` couvre déjà, et ce qu'il ne couvre pas
-------------------------------------------------------------------
`src/utils/metric_bounds.py` réconcilie déjà deux PORTES Python
(`platform_totals` contre `daily_streams_by_platform`) pour **trois** plateformes —
`KINDS = {spotify, soundcloud, youtube}`. Il ne regarde ni Apple, ni Meta, ni le
revenu, et surtout il compare des portes, pas des VUES : une vue or qui diverge de sa
vue sœur lui est invisible.

Depuis les migrations 101-111 il y a **quatorze vues or et une fonction**. Les
définitions derrière trois d'entre elles sont réconciliées. Ce module couvre les
autres.

Pourquoi une ÉGALITÉ et pas un seuil
-------------------------------------
Chaque paire ci-dessous est la même somme, des mêmes lignes, par deux chemins. Un
écart n'est pas « une dérive à surveiller » : c'est une erreur, aujourd'hui, dans un
chiffre affiché. La tolérance ne couvre donc que la représentation flottante —
Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p. 107, distinguent explicitement
le suivi d'une distribution (un seuil) de l'assertion (une égalité) ; ce sont des
assertions.

Ce que ce module ne fait PAS
-----------------------------
Il ne détecte pas une dérive graduelle, ni une valeur aberrante, ni un changement de
distribution. Ces trois-là relèvent du pilier « distribution » et ont leurs propres
détecteurs (`value_monitor` pour le retour à zéro d'un cumul, `check_row_dips` pour le
volume). Ici on ne pose qu'une question : **ces deux chemins rendent-ils le même
nombre ?**
"""
from __future__ import annotations

from dataclasses import dataclass

# La représentation flottante, rien de plus. Un écart relatif masquerait le défaut :
# le double, sur une base à un euro près, est un écart relatif de 100 % — mais sur un
# locataire à 3 €, un facteur deux fait 3 € et passerait sous n'importe quel seuil
# relatif « raisonnable ». C'est la raison pour laquelle ce n'est pas un seuil.
TOLERANCE = 1e-6


@dataclass(frozen=True)
class Invariant:
    name: str
    left_sql: str
    right_sql: str
    left_label: str
    right_label: str
    why: str


# Chaque invariant rend (artist_id, valeur). La comparaison est par locataire : un
# total de flotte qui s'équilibre peut cacher deux locataires qui se compensent.
INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        name="meta_spend_two_grains",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_campaign_daily GROUP BY 1",
        left_label="v_meta_daily",
        right_label="v_meta_campaign_daily",
        why="LE défaut du 2026-09-12. Les deux vues lisent deux tables différentes "
            "qui portent la même dépense ; l'une d'elles contenait 21 lignes de cumul "
            "à vie d'un ancien collecteur, et la page affichait le double. La vue or "
            "les écarte — cet invariant est ce qui le prouve chaque nuit.",
    ),
    Invariant(
        name="meta_spend_creative_vs_adset",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_creative_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_adset_daily GROUP BY 1",
        left_label="v_meta_creative_daily",
        right_label="v_meta_adset_daily",
        why="La même dépense à deux mailles (créative, ad set), par deux chaînes de "
            "jointures distinctes. Un euro qui tombe d'un côté et pas de l'autre est "
            "une jointure qui a perdu une ligne — la classe que la migration 106 "
            "nomme et que la 108 a vue se reproduire.",
    ),
    Invariant(
        name="meta_spend_totals_vs_daily",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_spend_totals GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_daily GROUP BY 1",
        left_label="v_meta_spend_totals",
        right_label="v_meta_daily",
        why="Le TOTAL et son grain temporel, lus sur la même table de fait. "
            "`v_meta_spend_totals` n'avait aucun lecteur au 2026-09-12 ; un objet or "
            "que rien ne lit dérive sans bruit, et c'est le premier à le faire.",
    ),
    Invariant(
        name="spotify_total_vs_song_grain",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'spotify' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(streams) FROM v_s4a_song_daily GROUP BY 1",
        left_label="v_platform_totals[spotify]",
        right_label="v_s4a_song_daily",
        why="Le total et le grain TITRE. Depuis la migration 107 le total DÉRIVE du "
            "grain, donc l'invariant est vrai par construction — et c'est exactement "
            "pour ça qu'il est ici : le jour où quelqu'un réécrit la branche spotify "
            "en repartant de la table brute, cette égalité casse avant l'affichage.",
    ),
    Invariant(
        name="soundcloud_total_vs_track_grain",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'soundcloud' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(playback_count) FROM v_soundcloud_track_latest "
                  "GROUP BY 1",
        left_label="v_platform_totals[soundcloud]",
        right_label="v_soundcloud_track_latest",
        why="Idem pour un COMPTEUR : le total est la somme du dernier relevé de chaque "
            "titre. La version d'avant le 2026-09-12 dédupliquait sans le locataire, "
            "et deux artistes partageant un titre n'en gardaient qu'un.",
    ),
    Invariant(
        name="sacem_revenue_vs_statement_grain",
        left_sql="SELECT artist_id, SUM(revenue_eur) FROM v_artist_monthly_revenue "
                 "WHERE source = 'sacem' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(amount) FROM v_sacem_monthly "
                  "WHERE line_type = 'repartition' GROUP BY 1",
        left_label="v_artist_monthly_revenue[sacem]",
        right_label="v_sacem_monthly[repartition]",
        why="Le prédicat `line_type = 'repartition'` était écrit DEUX fois avant la "
            "migration 111 — dans la vue de revenu et dans la page SACEM, qui sommait "
            "en pandas. Il n'est plus écrit qu'une fois ; cet invariant garde qu'il le "
            "reste.",
    ),
    Invariant(
        name="apple_total_vs_function",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'apple' GROUP BY 1",
        right_sql="SELECT DISTINCT artist_id, gold_apple_lifetime(artist_id, 'plays') "
                  "FROM apple_songs_performance WHERE artist_id IS NOT NULL",
        left_label="v_platform_totals[apple]",
        right_label="gold_apple_lifetime()",
        why="La seule règle en PL/pgSQL du dépôt (ADR-022) : sélection gloutonne "
            "d'intervalles non chevauchants. Une fonction procédurale ne se relit pas "
            "en diff ; cet invariant est la seule façon de savoir qu'elle rend encore "
            "ce que la vue annonce. Son ajout en surcharge avait déjà fait afficher "
            "**zéro** à la tuile « Total Streams ».",
    ),
    # ── Les quatre suivants confrontent une vue or à CE QU'ELLE RÉSUME ─────────
    #
    # Ils sont d'une autre nature que les sept ci-dessus : ceux-là comparent deux
    # définitions or entre elles, ceux-ci comparent une vue or à la table qu'elle
    # agrège. C'est un invariant plus faible — il ne dit rien de la RÈGLE, seulement
    # qu'aucune ligne ne s'est perdue en chemin. Mais « une jointure a perdu des
    # lignes » est la moitié des défauts de cette famille, et un objet or que rien
    # ne confronte est le premier à dériver en silence.
    Invariant(
        name="levels_vs_total_youtube",
        left_sql="SELECT DISTINCT ON (artist_id) artist_id, level FROM v_platform_levels "
                 "WHERE platform = 'youtube' ORDER BY artist_id, day DESC",
        right_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                  "WHERE platform = 'youtube' GROUP BY 1",
        left_label="v_platform_levels[youtube] au dernier jour",
        right_label="v_platform_totals[youtube]",
        why="Le meilleur des onze : deux calculs VRAIMENT différents du même "
            "compteur. Les niveaux reportent en avant le dernier relevé de chaque "
            "vidéo jour par jour ; le total prend le dernier relevé de chaque vidéo. "
            "Ils doivent finir au même nombre, et c'est la figure de l'accueil qui "
            "lit les premiers pendant que la tuile lit le second — les deux "
            "surfaces où ×2,7 avait été mesuré le 2026-09-10.",
    ),
    Invariant(
        name="levels_vs_total_soundcloud",
        left_sql="SELECT DISTINCT ON (artist_id) artist_id, level FROM v_platform_levels "
                 "WHERE platform = 'soundcloud' ORDER BY artist_id, day DESC",
        right_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                  "WHERE platform = 'soundcloud' GROUP BY 1",
        left_label="v_platform_levels[soundcloud] au dernier jour",
        right_label="v_platform_totals[soundcloud]",
        why="Même propriété sur l'autre compteur. Elle vaut d'être vérifiée "
            "séparément : les niveaux filtrent `playback_count > 0` et non "
            "`IS NOT NULL`, parce qu'une collecte ratée écrit des ZÉROS — une "
            "distinction qui n'existe que d'un côté.",
    ),
    Invariant(
        name="hypeddit_view_loses_no_row",
        left_sql="SELECT artist_id, SUM(visits) FROM v_hypeddit_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(visits) FROM hypeddit_daily_stats "
                  "WHERE artist_id IS NOT NULL GROUP BY 1",
        left_label="v_hypeddit_daily",
        right_label="hypeddit_daily_stats",
        why="La vue est un pur `GROUP BY` : elle ne doit RIEN perdre. Un écart veut "
            "dire qu'un prédicat s'est glissé dans la vue, ou que le `artist_id IS "
            "NOT NULL` écarte des lignes que la page affichait encore la veille.",
    ),
    Invariant(
        name="meta_active_budget_matches_its_filter",
        left_sql="SELECT artist_id, SUM(lifetime_budget) FROM v_meta_active_budget "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, SUM(COALESCE(lifetime_budget, 0)) FROM meta_campaigns "
                  "WHERE artist_id IS NOT NULL AND status = 'ACTIVE' GROUP BY 1",
        left_label="v_meta_active_budget",
        right_label="meta_campaigns[status=ACTIVE]",
        why="Le prédicat `status = 'ACTIVE'` vivait recopié dans quatre branches de "
            "deux fichiers avant la migration 110. Il n'est plus écrit qu'une fois ; "
            "cet invariant garde qu'il dit encore la même chose que ce qu'il "
            "remplaçait — c'est la seule façon de savoir qu'un repointage n'a pas "
            "silencieusement changé le sens.",
    ),
    Invariant(
        name="instagram_view_loses_no_post_that_has_a_date",
        left_sql="SELECT artist_id, SUM(likes) FROM v_instagram_media_monthly GROUP BY 1",
        right_sql="SELECT artist_id, SUM(COALESCE(like_count, 0)) FROM instagram_media "
                  "WHERE artist_id IS NOT NULL AND timestamp IS NOT NULL GROUP BY 1",
        left_label="v_instagram_media_monthly",
        right_label="instagram_media[timestamp non nul]",
        why="⚠️ Le côté droit porte `timestamp IS NOT NULL` parce que la VUE le "
            "porte : un post sans date de publication est EXCLU du mensuel, et "
            "aligner l'invariant sur la vue est la seule façon qu'il ne sonne pas "
            "chaque fois qu'Instagram rend un post sans horodatage. C'est aussi une "
            "information sur le produit — ces posts-là ne sont comptés nulle part, "
            "et personne ne le dit à l'écran.",
    ),
)


def compare(left: dict[int, float], right: dict[int, float],
            tolerance: float = TOLERANCE) -> list[tuple[int, float, float]]:
    """Les locataires où les deux côtés diffèrent : (locataire, gauche, droite).

    Un locataire absent d'UN SEUL côté compte comme un désaccord — c'est la moitié
    des défauts de cette famille : une jointure qui perd des lignes fait disparaître
    un locataire entier, et comparer les seules clés communes rendrait ça invisible.
    `None` des deux côtés n'existe pas ici : un côté absent vaut zéro, et zéro contre
    un nombre est un désaccord.
    """
    out: list[tuple[int, float, float]] = []
    for tenant in sorted(set(left) | set(right)):
        a = float(left.get(tenant) or 0.0)
        b = float(right.get(tenant) or 0.0)
        if abs(a - b) > tolerance:
            out.append((tenant, a, b))
    return out


def finding(inv: Invariant, tenant: int, left: float, right: float) -> str:
    """Le constat, dans la forme que l'e-mail consolidé sait rendre."""
    gap = abs(left - right)
    ratio = f" (×{max(left, right) / min(left, right):.2f})" if min(left, right) else ""
    return (f"artiste {tenant} — {inv.name} : {inv.left_label} = {left:,.2f} mais "
            f"{inv.right_label} = {right:,.2f}, écart {gap:,.2f}{ratio}. {inv.why}")


def run(db) -> tuple[list[str], int]:
    """`(constats, couples comparés)` — le contrôle entier, hors d'Airflow.

    Il vit ICI et pas dans le DAG pour deux raisons. La première est un cliquet :
    `alert_monitor.py` ne grandit pas, et ce qui y entre doit en faire sortir
    autant. La seconde est la bonne : un contrôle enfermé dans un DAG n'est
    testable que par Airflow, et ce dépôt a mesuré que **aucun DAG n'était
    importable hors conteneur** — un prédicat qu'on ne peut pas lancer est un
    prédicat qu'on n'exerce pas.

    Le second membre du tuple n'est pas décoratif : « zéro désaccord » sur zéro
    couple comparé est vrai et ne dit rien. L'appelant doit pouvoir le journaliser.
    """
    findings: list[str] = []
    compared = 0

    def side(sql: str) -> dict[int, float]:
        rows = db.fetch_query(sql) or []
        return {int(t): float(v or 0) for t, v in rows if t is not None}

    for inv in INVARIANTS:
        left, right = side(inv.left_sql), side(inv.right_sql)
        compared += len(set(left) | set(right))
        findings += [finding(inv, t, a, b) for t, a, b in compare(left, right)]
    return findings, compared


def email_section(findings: list[str], escape) -> str:
    """Le bloc HTML du courriel consolidé, ou une chaîne vide.

    `escape` est injecté plutôt qu'importé : ce module ne dépend de rien, et c'est
    ce qui le rend importable depuis un test, un DAG et un script.
    """
    if not findings:
        return ""
    items = "".join(f"<li>{escape(m)}</li>" for m in findings)
    return f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🧮 Définitions or en désaccord ({len(findings)})
        </h2>
        <p style="color:#888;font-size:0.9em">Deux définitions de la couche or qui
          doivent rendre le MÊME nombre n'en rendent pas le même. Ce n'est pas une
          dérive à surveiller : c'est un chiffre faux, aujourd'hui, sur une surface
          que quelqu'un lit. Chaque ligne nomme le défaut qu'elle attrape.</p>
        <ul style="font-size:0.9em">{items}</ul>"""
