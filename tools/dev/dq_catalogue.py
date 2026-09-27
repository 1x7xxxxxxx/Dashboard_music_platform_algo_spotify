"""Data quality by CATEGORY — every existing check, filed where the owner looks for it.

Type: Utility
Uses: nothing (data)
Triggers: tools/dev/gold_coverage.py (section « La qualité des données par catégorie »),
          tests/test_every_quality_check_has_a_category.py
Persists in: nothing

R230 (2026-09-27). The owner listed seven families of data-quality checks: duplicates,
impossible values, time breaks, abnormal variations, cross-platform divergences,
mapping, missing data. The repository already cites FOUR pillars (Moses/Gavish/
Vorwerck, *Data Quality Fundamentals*): freshness, volume, distribution, schema — plus
the one this repository added, the computed value (`metric_bounds`, `gold_invariants`).
Two taxonomies classifying the same check would compete (code-critic, R230), so each
check carries BOTH: the owner's category (where he looks) and the pillar (how it
measures). Lineage is out of scope by ADR-012.

A check is a POINTER — `file::function` — resolved in the AST by the test, never a
copy. A category with no check says so in `GAPS`, with what would fill it.
"""
from __future__ import annotations

from dataclasses import dataclass

DOUBLONS = "doublons"
IMPOSSIBLES = "valeurs impossibles"
RUPTURES = "ruptures temporelles"
VARIATIONS = "variations anormales"
DIVERGENCES = "divergences entre plateformes"
MAPPING = "mapping"
MANQUANTES = "données manquantes"
CATEGORIES = (DOUBLONS, IMPOSSIBLES, RUPTURES, VARIATIONS, DIVERGENCES, MAPPING, MANQUANTES)

FRAICHEUR, VOLUME, DISTRIBUTION, SCHEMA, CALCUL = (
    "fraîcheur", "volume", "distribution", "schéma", "valeur calculée")
PILLARS = (FRAICHEUR, VOLUME, DISTRIBUTION, SCHEMA, CALCUL)

_AM = "airflow/dags/alert_monitor.py"


@dataclass(frozen=True)
class Check:
    pointer: str          # file::function, resolved in the AST
    category: str
    pillar: str
    when: str             # soir · import · requête · lecture
    what: str


CHECKS: tuple[Check, ...] = (
    Check("airflow/dags/data_quality_check.py::check_spotify_data_consistency", DOUBLONS,
          SCHEMA, "soir", "un (titre, jour) S4A présent deux fois — et les titres absents "
                          "du catalogue, les séries de moins de 7 jours"),
    Check(f"{_AM}::check_row_anomalies", DOUBLONS, VOLUME, "soir",
          "un jour à plus de 10× la moyenne des 7 précédents : un double passage"),
    Check(f"{_AM}::check_zero_resets", IMPOSSIBLES, DISTRIBUTION, "soir",
          "un compteur CUMULÉ qui retombe à 0 (19 titres SoundCloud le 2026-06-01)"),
    Check(f"{_AM}::check_metric_bounds", IMPOSSIBLES, CALCUL, "soir",
          "une somme de quotidiens qui dépasse le total à vie de la plateforme"),
    Check(f"{_AM}::check_data_freshness", RUPTURES, FRAICHEUR, "soir",
          "une source dont la dernière donnée a passé son seuil d'âge"),
    Check(f"{_AM}::check_collection_outcomes", RUPTURES, FRAICHEUR, "soir",
          "une collecte qui n'a pas tourné, ou a échoué, POUR CE locataire"),
    Check(f"{_AM}::check_row_dips", VARIATIONS, VOLUME, "soir",
          "un jour à bien moins de lignes que d'habitude, sans être vide"),
    Check(f"{_AM}::check_drift_anomalies", VARIATIONS, DISTRIBUTION, "soir",
          "une entrée du modèle hors de sa distribution sur la plupart des titres"),
    Check(f"{_AM}::check_resurrection_sparks", VARIATIONS, DISTRIBUTION, "soir",
          "un vieux titre dont les sauvegardes bondissent — une opportunité, pas un défaut"),
    Check(f"{_AM}::check_gold_invariants", DIVERGENCES, CALCUL, "soir",
          "deux définitions or censées rendre le même nombre (dépense, écoutes, "
          "trésorerie de la flotte…) qui en rendent deux"),
    Check("src/utils/metric_bounds.py::run", DIVERGENCES, CALCUL, "soir",
          "deux portes Python (total contre série) pour Spotify, SoundCloud, YouTube"),
    Check(f"{_AM}::check_tenant_contamination", MAPPING, SCHEMA, "soir",
          "des lignes rangées sous un locataire auquel elles ne peuvent pas appartenir"),
    Check(f"{_AM}::check_csv_rejections", MANQUANTES, FRAICHEUR, "soir",
          "un fichier déposé par un artiste que l'import n'a pas su lire"),
    Check("src/utils/quality_gate.py::source_is_fresh_enough", MANQUANTES, FRAICHEUR,
          "lecture", "une prévision qui s'abstient quand sa source est trop vieille"),
)

# What the category lacks, and what would fill it — said, not hidden.
GAPS: dict[str, str] = {
    DOUBLONS: "couvert par CONSTRUCTION plus que par détection : 119 tables sur 131 ont "
              "une clé naturelle UNIQUE (un doublon y est impossible, le chercher chaque "
              "soir coûterait pour un verdict qui ne peut pas changer — code-critic R230) ; "
              "les 12 autres sont des journaux, sauf `artist_history`, dédoublonnée par sa "
              "vue or (migration 120).",
    IMPOSSIBLES: "une borne par NATURE de mesure (un taux dans [0, 100], un indice de "
                 "popularité 0-100) : le registre ne distingue pas encore un taux d'un "
                 "niveau, il faudrait l'y ajouter avant d'écrire la borne une seule fois.",
    MAPPING: "une campagne sans titre lié n'alerte pas : elle se voit dans la page de "
             "rattachement, et le coût par écoute de cette campagne reste « — ».",
}
