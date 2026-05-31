"""Algorithm domain knowledge derived from offline SHAP / model evaluation.

Type: Reference
Depends on: (none — pure data + stdlib, no streamlit/db)
Persists in: nothing (in-memory constants)

Single source of truth for the Discover-Weekly findings extracted from
machine_learning/ analysis: per-feature decision zones (SHAP inflection points),
calibration bands (the model is NOT calibrated), and classification scorecard
metrics. Everything is keyed by algorithm so RR/Radio drop in later. Rendering
lives in ml_widgets.py; this module stays import-light and unit-testable.
"""
import math

# ── Per-feature decision zones (Discover Weekly) ──────────────────────────────
# Each entry keyed by clean feature id. `json_key` = key in ml_song_predictions
# features_json; `decode` = how to recover the raw human value from it.
# zones = ordered (low_inclusive, high_exclusive, verdict, note); None = open end.
# `target` = nearest critical threshold to cross; `live_unavailable` flags the
# 6 features imputed to 0/neutral at inference; `divergent` flags a definition
# mismatch between the live feature and the SHAP analysis.
DW_FEATURE_ZONES = {
    "StreamsLast7Days": {
        "json_key": "StreamsLast7Days_log", "decode": "expm1",
        "label": "Streams 7 jours", "unit": "streams/7j",
        "zones": [
            (0, 2000, "malus", "Vallée de la mort — sous le péage des 2 000"),
            (2000, 5000, "bonus", "Au-dessus du péage — bonus croissant"),
            (5000, None, "bonus", "Bonus maximal (≥ 5k/sem)"),
        ],
        "target": 2000,
        "lever": "Le 1er euro pour franchir ~1 000→2 000 streams/7j est le plus "
                 "rentable ; au-delà de 2 500 l'impact marginal diminue.",
    },
    "NonAlgoStreams28Days": {
        "json_key": "NonAlgoStreams28Days_log", "decode": "expm1", "live_unavailable": True,
        "label": "Streams non-algo (28j)", "unit": "streams/28j",
        # Recalibrated 2026-05-31 from data (bonus knee ~3 886, not 5 000).
        "zones": [
            (0, 3840, "malus", "Vallée organique — traction insuffisante"),
            (3840, None, "bonus", "Proof-of-concept organique validé (~3.9k/28j)"),
        ],
        "target": 3900,
        "lever": "Génère ≥ ~3 900 streams organiques actifs/28j (recherche, profil) "
                 "— l'autoplay ne compte pas (knee empirique).",
    },
    "DaysSinceRelease": {
        "json_key": "DaysSinceRelease", "decode": "identity", "actionable": False,
        "label": "Âge du titre", "unit": "jours",
        "zones": [
            (0, 60, "malus", "Purgatoire des nouveautés — l'IA collecte ses données"),
            (60, 400, "bonus", "Âge d'or algorithmique (≈ 2 mois → 1 an)"),
            (400, None, "neutral", "Déclin progressif"),
        ],
        "target": 60,
        "lever": "Passe le cap des 60 jours : l'âge d'or DW va de ~2 mois → 1 an.",
    },
    "Velocity_Streams": {
        "json_key": "Velocity_Streams", "decode": "identity",
        "label": "Vélocité", "unit": "ratio",
        # Recalibrated 2026-05-31 from data_anon.csv (derive_thresholds.py): no
        # success knee in the 1.2-2.0 range — the old (1.2,5,malus) wrongly
        # penalised healthy growth. Penalty kept only at the suspect-peak (>3.5).
        "zones": [
            (0, 3.5, "neutral", "Croissance fluide — pas de pénalité (sweet 1.2-2.0)"),
            (3.5, 5, "malus", "Pic suspect (> 3.5) — anti-fraude Spotify"),
        ],
        "target": None,
        "lever": "Une croissance 1.2-2.0 est idéale et non pénalisée ; seul un pic "
                 "> 3.5 (volume soudain, suspicion de bots) déclenche un malus.",
    },
    "CurrentSpotifyFollowers": {
        "json_key": "CurrentSpotifyFollowers_log", "decode": "expm1",
        "label": "Followers Spotify", "unit": "followers",
        # Recalibrated 2026-05-31: malus<1 000 kept (consistent narrative), but the
        # strong-bonus knee is ~2 650 in the data (was 1 600).
        "zones": [
            (0, 1000, "malus", "Crédibilité non validée (< 1 000)"),
            (1000, 2650, "neutral", "En cours de qualification"),
            (2650, None, "bonus", "Autorité confirmée (≥ ~2 650)"),
        ],
        "target": 2650,
        "lever": "Le seuil de bascule est ~1 000 abonnés ; le vrai bonus d'autorité "
                 "n'arrive qu'à ~2 650 (knee empirique).",
    },
    "HowManySongsDoYouHaveInRadioRightNow": {
        "json_key": "HowManySongsDoYouHaveInRadioRightNow", "decode": "identity",
        "live_unavailable": True, "label": "Titres en Radio", "unit": "titres",
        "zones": [
            (0, 8, "malus", "Catalogue inactif"),
            (8, 9, "neutral", "Seuil de momentum"),
            (9, None, "bonus", "Bonus de catalogue"),
        ],
        "target": 9,
        "lever": "Avoir ≥ 9 titres en rotation Radio donne un bonus de momentum.",
    },
    "ListenersStreamRatio28Days": {
        "json_key": "ListenersStreamRatio28Days_adj", "decode": "identity",
        "label": "Écoutes / auditeur (28j)", "unit": "ratio",
        # Recalibrated 2026-05-31: data malus knee ~1.6 (not 2.2); no sustained
        # bonus zone for DW — the >4 suspect band is kept.
        "zones": [
            (0, 1.6, "malus", "Faible réécoute (< ~1.6)"),
            (1.6, 4, "neutral", "Réécoute correcte"),
            (4, None, "malus", "Ratio suspect (bots / méga-hit)"),
        ],
        "target": 1.6,
        "lever": "Dépasse ~1.6 écoute/auditeur ; au-delà de 4 le ratio devient suspect.",
    },
    "SavesLast28Days": {
        "json_key": "SavesLast28Days_adj", "decode": "identity",
        "label": "Saves (28j)", "unit": "saves",
        # Recalibrated 2026-05-31 from data (knee: malus<=76, bonus>=165). The old
        # bonus@50 was too low; the user's 350-500 note too high — data says ~165.
        "zones": [
            (0, 76, "malus", "Engagement faible (< ~76/28j)"),
            (76, 165, "neutral", "Zone de bascule"),
            (165, None, "bonus", "Signal de qualité — bonus DW"),
        ],
        "target": 165,
        "lever": "Vise ≥ ~165 saves/28j : c'est là que l'impact DW devient nettement "
                 "positif (knee empirique, pas la valeur survendue de 500).",
    },
    "PlaylistAddsLast28Days": {
        "json_key": "PlaylistAddsLast28Days_adj", "decode": "identity",
        "label": "Ajouts playlist (28j)", "unit": "ajouts",
        # Recalibrated 2026-05-31 from data (bonus knee ~172).
        "zones": [
            (0, 175, "malus", "Sous le seuil de bascule"),
            (175, None, "bonus", "Signal d'engagement le plus fort (Or)"),
        ],
        "target": 175,
        "lever": "Dépasse ~175 ajouts playlist utilisateurs/28j — le signal "
                 "d'intention le plus fort pour le DW.",
    },
    "ReleaseConsistencyNum": {
        "json_key": "ReleaseConsistencyNum", "decode": "identity",
        "label": "Cadence de sortie", "unit": "semaines entre sorties",
        "zones": [
            (0, 6, "malus", "Cannibalisation — sorties trop rapprochées"),
            (6, 14, "bonus", "Cadence saine (jusqu'à ~14 sem / 3 mois)"),
            (14, None, "neutral", "Trop espacé"),
        ],
        "target": 6,
        "lever": "Espace tes sorties d'au moins ~6 semaines (idéal jusqu'à 14) pour "
                 "ne pas cannibaliser la vélocité de l'ancienne.",
    },
    "HowManySongsHasThisArtistEverReleased": {
        "json_key": "HowManySongsHasThisArtistEverReleased", "decode": "identity",
        "label": "Taille du catalogue", "unit": "titres",
        "zones": [
            (0, 40, "neutral", "Sain"),
            (40, None, "malus", "Catalogue dilué (> 40)"),
        ],
        "target": None,
        "lever": "Mieux vaut 10 titres exploités à fond que 50 qui dorment.",
    },
    "IsThisSongOptedIntoSpotifyDiscoveryMode": {
        "json_key": "IsThisSongOptedIntoSpotifyDiscoveryMode", "decode": "identity",
        "live_unavailable": True, "label": "Discovery Mode", "unit": "0/1",
        "zones": [
            (0, 1, "neutral", "Désactivé"),
            (1, 2, "bonus", "Micro-bonus"),
        ],
        "target": 1,
        "lever": "Discovery Mode : léger avantage mais impact microscopique.",
    },
    "ReleasePhaseEarly": {
        "json_key": "ReleasePhaseEarly", "decode": "identity", "actionable": False,
        "label": "Phase de sortie", "unit": "0/1",
        "zones": [
            (0, 1, "bonus", "Installé — favorable"),
            (1, 2, "malus", "Probation nouveauté — DW attend la preuve organique"),
        ],
        "target": 0,
        "lever": "Les 4-5 premières semaines, DW applique un malus de probation ; "
                 "c'est le Release Radar qui te porte à ce stade.",
    },
}

# ── Per-feature decision zones (Radio) ────────────────────────────────────────
# Radio rules differ sharply from DW (notably DaysSinceRelease is INVERTED: a
# new release is favoured, then the bonus is removed but stays flat — no death).
RADIO_FEATURE_ZONES = {
    "StreamsLast7Days": {
        "json_key": "StreamsLast7Days_log", "decode": "expm1",
        "label": "Streams 7 jours", "unit": "streams/7j",
        "zones": [
            (0, 1500, "malus", "Volume insuffisant"),
            (1500, 2000, "neutral", "Bascule"),
            (2000, None, "bonus", "Ticket d'entrée Radio garanti"),
        ],
        "target": 2000,
        "lever": "Franchis ~2 000 streams/7j (palier critique) — au-delà, ticket "
                 "d'entrée Radio garanti.",
    },
    "Velocity_Streams": {
        "json_key": "Velocity_Streams", "decode": "identity",
        "label": "Vélocité", "unit": "ratio",
        "zones": [
            (0, 1.5, "bonus", "Croissance lisse (sweet 0.5-1.2)"),
            (1.5, 5.1, "malus", "Hyper-croissance — Radio classe « suspect »"),
        ],
        "target": None,
        "lever": "La Radio déteste l'hyper-croissance : garde la vélocité < 1.5 "
                 "(idéal 0.5-1.2). Un pic = blacklist. Lisse le trafic.",
    },
    "NonAlgoStreams28Days": {
        "json_key": "NonAlgoStreams28Days_log", "decode": "expm1", "live_unavailable": True,
        "label": "Streams non-algo (28j)", "unit": "streams/28j",
        "zones": [
            (0, 2000, "malus", "Demande organique insuffisante"),
            (2000, None, "bonus", "Demande organique prouvée"),
        ],
        "target": 2000,
        "lever": "Amène ≥ 2 000 streams organiques/28j : la Radio relaie une "
                 "demande réelle, elle ne la crée pas.",
    },
    "CurrentSpotifyFollowers": {
        "json_key": "CurrentSpotifyFollowers_log", "decode": "expm1",
        "label": "Followers Spotify", "unit": "followers",
        "zones": [
            (0, 1000, "malus", "Confiance non établie"),
            (1000, 2000, "neutral", "Qualification"),
            (2000, None, "bonus", "Cap de confiance Radio"),
        ],
        "target": 2000,
        "lever": "Atteins 2 000 abonnés — cap de sécurité Radio.",
    },
    "HowManySongsDoYouHaveInRadioRightNow": {
        "json_key": "HowManySongsDoYouHaveInRadioRightNow", "decode": "identity",
        "live_unavailable": True, "label": "Titres en Radio", "unit": "titres",
        "zones": [
            (0, 1, "malus", "Aucun titre en Radio — malus d'entrée"),
            (1, None, "bonus", "Effet boule de neige — bonus systématique"),
        ],
        "target": 1,
        "lever": "Faire entrer 1 seul titre en Radio débloque un bonus de "
                 "confiance sur toutes les sorties suivantes.",
    },
    "HowManySongsHasThisArtistEverReleased": {
        "json_key": "HowManySongsHasThisArtistEverReleased", "decode": "identity",
        "label": "Taille du catalogue", "unit": "titres",
        "zones": [
            (0, 10, "malus", "Débutant (< 10 titres)"),
            (10, 20, "bonus", "Montagne verte — confiance max (10-20)"),
            (20, 30, "neutral", "Stable"),
            (30, None, "malus", "Dilution de l'audience (> 30)"),
        ],
        "target": 10,
        "lever": "Vise 10-20 titres au catalogue — pic de confiance Radio.",
    },
    "DaysSinceRelease": {
        "json_key": "DaysSinceRelease", "decode": "identity", "actionable": False,
        "label": "Âge du titre", "unit": "jours",
        "zones": [
            (0, 50, "bonus", "Lune de miel — coup de pouce nouveauté"),
            (50, None, "malus", "Bonus nouveauté retiré (mais stable — pas de mort)"),
        ],
        "target": 50,
        "lever": "La Radio retire le bonus nouveauté après ~50j mais ne te tue "
                 "pas : avec une bonne rétention, elle te joue des années.",
    },
    "IsThisSongOptedIntoSpotifyDiscoveryMode": {
        "json_key": "IsThisSongOptedIntoSpotifyDiscoveryMode", "decode": "identity",
        "live_unavailable": True, "label": "Discovery Mode", "unit": "0/1",
        "zones": [
            (0, 1, "malus", "Non activé — porte Radio plus dure"),
            (1, 2, "bonus", "Pay-to-play : force la porte Radio"),
        ],
        "target": 1,
        "lever": "Cocher Discovery Mode (Spotify for Artists, −30% royalties) "
                 "force quasi la porte de la Radio.",
    },
    "SavesLast28Days": {
        "json_key": "SavesLast28Days_adj", "decode": "identity",
        "label": "Saves (28j)", "unit": "saves",
        "zones": [
            (0, 50, "neutral", "Rétention faible — pénalisant"),
            (50, None, "bonus", "Bonne rétention"),
        ],
        "target": 50,
        "lever": "Augmente les saves (rétention) — la Radio récompense la fidélité "
                 "sur la durée.",
    },
}

# ── Per-feature decision zones (Release Radar) ────────────────────────────────
# RR is the new-release notification playlist: a short firing window (~first
# month). Zones are read off the offline SHAP zoom plots of the rr_classifier
# (machine_learning/mlruns/4/.../5_SHAP_Zoom_*_RR.png), NOT the prose notes — the
# plots refine them: DaysSinceRelease has a "too fresh" dip (days 0-7) before the
# 7-40d sweet window, and ReleaseConsistencyNum (#4 by importance, absent from the
# notes) rewards SPACED releases. DiscoveryMode is dead-flat (no RR impact) and
# PlaylistAdds is a chronological confound (proxy of age), not a lever.
RR_FEATURE_ZONES = {
    "DaysSinceRelease": {
        "json_key": "DaysSinceRelease", "decode": "identity", "actionable": False,
        "label": "Âge du titre", "unit": "jours",
        "zones": [
            (0, 7, "neutral", "Trop frais — l'algo n'a pas encore de signal"),
            (7, 40, "bonus", "Fenêtre de tir RR — fraîcheur maximale"),
            (40, None, "malus", "Hors fenêtre — la porte RR se referme"),
        ],
        "target": 40,
        "lever": "Le RR ne frappe que dans la fenêtre ~7→40 jours : c'est une porte "
                 "temporelle, pas un levier. Concentre tout l'effort sur ce créneau.",
    },
    "StreamsLast7Days": {
        "json_key": "StreamsLast7Days_log", "decode": "expm1",
        "label": "Streams 7 jours", "unit": "streams/7j",
        "zones": [
            (0, 1500, "malus", "Pas de signal de vie le jour J"),
            (1500, 2000, "neutral", "Bascule"),
            (2000, None, "bonus", "Signal de vie validé — RR amplifie"),
        ],
        "target": 2000,
        "lever": "Génère ≥ 2 000 streams sur la semaine de sortie (Meta Ads « Trafic » "
                 "le vendredi) : c'est l'impulsion qui déclenche le RR à plein régime.",
    },
    "CurrentSpotifyFollowers": {
        "json_key": "CurrentSpotifyFollowers_log", "decode": "expm1",
        "label": "Followers Spotify", "unit": "followers",
        "zones": [
            (0, 1000, "malus", "Audience non qualifiée"),
            (1000, 2300, "neutral", "Qualification en cours"),
            (2300, None, "bonus", "Pass VIP — RR notifie en masse tes abonnés"),
        ],
        "target": 2300,
        "lever": "Le RR est une notification aux abonnés : convertis ≥ 2 300 followers "
                 "pour que Spotify soit forcé de déclencher l'envoi.",
    },
    "ReleaseConsistencyNum": {
        "json_key": "ReleaseConsistencyNum", "decode": "identity",
        "label": "Cadence de sortie", "unit": "semaines entre sorties",
        "zones": [
            (0, 11, "malus", "Sorties trop rapprochées — notifs RR cannibalisées"),
            (11, 14, "neutral", "Bascule"),
            (14, None, "bonus", "Espacé — chaque titre capte une fenêtre RR pleine"),
        ],
        "target": 14,
        "lever": "Espace tes sorties (~14 sem) : chaque titre récupère alors une "
                 "fenêtre de notification RR complète au lieu de se cannibaliser.",
    },
    "IsThisSongOptedIntoSpotifyDiscoveryMode": {
        "json_key": "IsThisSongOptedIntoSpotifyDiscoveryMode", "decode": "identity",
        "live_unavailable": True, "actionable": False,
        "label": "Discovery Mode", "unit": "0/1",
        "zones": [
            (0, 1, "neutral", "Désactivé — aucun effet RR"),
            (1, 2, "neutral", "Activé — aucun effet RR non plus"),
        ],
        "target": None,
        "lever": "SHAP plat à zéro : le Discovery Mode n'a AUCUN impact sur le RR. "
                 "Ne sacrifie pas 30% de royalties en semaine 1 — active-le au mois 2 "
                 "pour la Radio.",
    },
    "PlaylistAddsLast28Days": {
        "json_key": "PlaylistAddsLast28Days_adj", "decode": "identity",
        "divergent": True, "actionable": False,
        "label": "Ajouts playlist (28j)", "unit": "ajouts",
        "zones": [
            (0, None, "neutral", "Signal confondu avec l'âge du titre"),
        ],
        "target": None,
        "divergent_note": "SHAP négatif trompeur : les titres à forts ajouts sont déjà "
                          "vieux (3-4 sem) et hors fenêtre RR — c'est un proxy de l'âge, "
                          "pas un levier. Ne réduis surtout pas tes ajouts playlist.",
        "lever": "Ignore ce signal pour le RR : il mesure l'âge, pas l'engagement.",
    },
}

ALGO_FEATURE_ZONES = {
    "DW": DW_FEATURE_ZONES,
    "RR": RR_FEATURE_ZONES,
    "RADIO": RADIO_FEATURE_ZONES,
}

# Display labels + canonical ordering for stacked rendering.
ALGO_LABELS = {"DW": "💎 Discover Weekly", "RR": "📡 Release Radar", "RADIO": "📻 Radio"}

# ── VOLUME zones (regressor) — distinct logic from the entry/classification zones above ─
# Read off the dw_regressor SHAP analysis: the volume of DW streams is driven by RAW
# fuel (recent streams + organic traffic), NOT by the quality signals that buy the
# *entry ticket* (saves, playlist adds — flat for volume). Entry = classification;
# volume = regression. These zones are keyed identically to ALGO_FEATURE_ZONES so the
# same gauge/coach machinery renders them, but live via the `registry=` arg.
# `volume_flat: True` marks the "ticket d'entrée vs volume" paradox levers — present
# on purpose to TEACH that they do nothing for volume, never as a malus to fix.
DW_VOLUME_ZONES = {
    "StreamsLast7Days": {
        "json_key": "StreamsLast7Days_log", "decode": "expm1",
        "label": "Étincelle récente (streams 7j)", "unit": "streams/7j",
        "zones": [
            (0, 4000, "neutral", "Sous le palier — impact volume plat ou négatif"),
            (4000, 6000, "neutral", "Approche du palier de scaling"),
            (6000, None, "bonus", "Palier franchi — bonus vertical +400 à +800 streams DW"),
        ],
        "target": 6000,
        "lever": "Franchis ~6 000 streams sur 7 jours : au-delà, le DW ajoute un bonus "
                 "vertical de +400 à +800 streams au volume prédit (effet d'étincelle).",
    },
    "NonAlgoStreams28Days": {
        "json_key": "NonAlgoStreams28Days_log", "decode": "expm1", "live_unavailable": True,
        "label": "Carburant organique (28j)", "unit": "streams/28j",
        "zones": [
            (0, 5000, "neutral", "Sous le seuil — l'impact volume reste plat"),
            (5000, 6000, "neutral", "Bascule"),
            (6000, None, "bonus", "Spotify ouvre les vannes — scaling organique"),
        ],
        "target": 6000,
        "lever": "Amène 6 000–10 000 streams organiques actifs/28j (recherche, profil — "
                 "l'autoplay ne compte pas) : c'est le multiplicateur n°1 du volume DW.",
    },
    "SavesLast28Days": {
        "json_key": "SavesLast28Days_adj", "decode": "identity", "volume_flat": True,
        "label": "Saves (28j)", "unit": "saves",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — ticket d'entrée, pas multiplicateur")],
        "target": None,
        "lever": "Les saves achètent l'ENTRÉE en DW (classification) mais n'augmentent "
                 "pas le VOLUME une fois dedans : ne sur-investis pas ici pour scaler.",
    },
    "PlaylistAddsLast28Days": {
        "json_key": "PlaylistAddsLast28Days_adj", "decode": "identity", "volume_flat": True,
        "label": "Ajouts playlist (28j)", "unit": "ajouts",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — utile à l'entrée, neutre sur le débit")],
        "target": None,
        "lever": "Comme les saves : levier d'entrée, pas de volume. Le débit DW vient "
                 "du carburant organique, pas des ajouts playlist.",
    },
}

# ── RADIO VOLUME zones (regressor — MLflow exp 6) ─────────────────────────────
# Read off the radio_regressor SHAP analysis. The paradigm flips vs classification:
# recent fuel (StreamsLast7Days) DOMINATES volume, while the quality signals that buy
# the entry ticket (saves, playlist adds, listener ratio) go DEAD FLAT. Two notes are
# unique to Radio:
#   • HowManySongsDoYouHaveInRadioRightNow is the FIRST non-flat catalogue feature —
#     a positive-slope "superstar" bonus (Spotify over-distributes new tracks once an
#     artist already has many tracks live in Radio).
#   • Discovery Mode is flat-for-volume (entry ticket only) → the margin-recovery
#     coach action keys off this (see radio_discovery_recovery_note).
# Thresholds are PROVISIONAL — read off a qualitative SHAP summary on ~300 tracks, no
# sharp knee published. The "cruising velocity" target (~70k/7j ≈ 10k/day) is the
# Discovery-Mode-recovery trigger, not a hard scaling cliff.
RADIO_VOLUME_ZONES = {
    "StreamsLast7Days": {
        "json_key": "StreamsLast7Days_log", "decode": "expm1",
        "label": "Carburant récent (streams 7j)", "unit": "streams/7j",
        "zones": [
            (0, 7000, "neutral", "Sous le palier — l'amplificateur Radio est au repos"),
            (7000, 70000, "neutral", "Le titre accélère — l'amplificateur monte progressivement"),
            (70000, None, "bonus", "Vitesse de croisière (~10k/j) — Spotify amplifie jusqu'à +100k streams"),
        ],
        "target": 70000,
        "lever": "Le VOLUME Radio est piloté par le carburant récent (SHAP dominant) : "
                 "injecte du trafic externe pour franchir la vitesse de croisière "
                 "(~10 000 streams/jour). Au-delà, l'algo amplifie massivement. Seuils "
                 "provisoires (SHAP qualitatif, ~300 titres).",
    },
    "HowManySongsDoYouHaveInRadioRightNow": {
        "json_key": "HowManySongsDoYouHaveInRadioRightNow", "decode": "identity",
        "live_unavailable": True,
        "label": "Catalogue actif en Radio (effet superstar)", "unit": "titres",
        "zones": [
            (0, 3, "neutral", "Catalogue Radio naissant — pas encore d'effet d'échelle"),
            (3, 10, "neutral", "L'écosystème Radio se construit"),
            (10, None, "bonus", "Effet superstar — Spotify sur-distribue tes nouveaux titres"),
        ],
        "target": 10,
        "lever": "Seule feature catalogue NON plate pour le volume : plus tu as de titres "
                 "actifs en Radio, plus Spotify sur-distribue les suivants (score de "
                 "confiance artiste). Construis un catalogue Radio régulier.",
    },
    "IsThisSongOptedIntoSpotifyDiscoveryMode": {
        "json_key": "IsThisSongOptedIntoSpotifyDiscoveryMode", "decode": "identity",
        "volume_flat": True, "live_unavailable": True,
        "label": "Discovery Mode", "unit": "0/1",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — ticket d'entrée Radio, jamais multiplicateur")],
        "target": None,
        "lever": "PARADOXE : Discovery Mode garantit quasi l'ENTRÉE en Radio (classification) "
                 "mais SHAP plat à zéro sur le VOLUME. Une fois en vitesse de croisière, "
                 "désactive-le pour récupérer 30% de royalties — l'algo continue de pousser "
                 "via ta vélocité organique.",
    },
    "SavesLast28Days": {
        "json_key": "SavesLast28Days_adj", "decode": "identity", "volume_flat": True,
        "label": "Saves (28j)", "unit": "saves",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — qualité = ticket d'entrée, pas amplificateur")],
        "target": None,
        "lever": "Les saves achètent l'ENTRÉE en Radio (classification) mais n'augmentent "
                 "pas le VOLUME diffusé : ne sur-investis pas ici pour scaler le débit.",
    },
    "PlaylistAddsLast28Days": {
        "json_key": "PlaylistAddsLast28Days_adj", "decode": "identity", "volume_flat": True,
        "label": "Ajouts playlist (28j)", "unit": "ajouts",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — levier d'entrée, neutre sur le débit Radio")],
        "target": None,
        "lever": "Comme les saves : levier d'entrée, pas de volume. Le débit Radio vient "
                 "du carburant récent, pas des ajouts playlist.",
    },
    "ListenersStreamRatio28Days": {
        "json_key": "ListenersStreamRatio28Days_adj", "decode": "identity", "volume_flat": True,
        "label": "Ratio écoutes/auditeurs (28j)", "unit": "ratio",
        "zones": [(0, None, "neutral",
                   "Plat pour le VOLUME — signal de rétention, utile à l'entrée seulement")],
        "target": None,
        "lever": "Le ratio de réécoute prouve la qualité à l'entrée mais reste plat sur le "
                 "VOLUME : il ne multiplie pas le nombre de streams diffusés.",
    },
}

# DW + Radio populated. RR regressor zones plug in here when their notes arrive
# (same schema, no code change).
ALGO_VOLUME_ZONES = {
    "DW": DW_VOLUME_ZONES,
    "RADIO": RADIO_VOLUME_ZONES,
}

# ── Calibration bands (Discover Weekly) ───────────────────────────────────────
# Raw classifier score → real-world reliability, read off the calibration curve.
ALGO_CALIBRATION_BANDS = {
    "DW": [
        (0.0, 0.2, "⚠️ Sur-confiance sur les flops : fiabilité réelle proche de 0%."),
        (0.2, 0.4, "Sous-estimé : réussite réelle ~50-65% (mieux que le score affiché)."),
        (0.4, 0.7, "Zone intermédiaire : fiabilité variable, à confirmer."),
        (0.7, 1.01, "⚠️ Sur-confiance : un score ~0.85 ne vaut qu'~50% de réussite réelle."),
    ],
}

# ── Regressor (volume forecast) metadata ──────────────────────────────────────
# The *_streams_forecast_7d outputs come from XGBoost regressors that systematically
# UNDER-predict big hits (>90% of the catalogue scores low, so the model plays it
# safe). Consequence: the forecast must be read as a conservative FLOOR (worst-case),
# never a ceiling. These numbers feed the "hungry model" badge + the floor disclaimer.
ALGO_REGRESSOR_METRICS = {
    "DW": {
        "model_version": "v1", "train_n": 300, "mrd_pct": 347.99,
        "best_n_estimators": 143, "bias": "under",
        "interpretation": (
            "Régresseur très conservateur : il sous-estime systématiquement les gros "
            "succès (ex. 12 000 streams réels prédits ~1 500). À lire comme un PLANCHER "
            "(pire cas), jamais un plafond. Erreur relative (MRD) ~348 % et ~300 titres "
            "d'entraînement seulement → précision en hausse à mesure que le dataset grandit."
        ),
    },
    "RADIO": {
        "model_version": "v1", "train_n": 300, "r2": 0.63, "bias": "under",
        "interpretation": (
            "Régresseur Radio robuste (R²=0.63) mais conservateur : il refuse de parier "
            "sur la viralité extrême — un hit réel à +400 000 streams a été largement "
            "sous-estimé. À lire comme un VOLUME DE CROISIÈRE plancher, jamais un plafond : "
            "les emballements externes (TikTok, sync) sont hors-modèle. La learning curve "
            "montre un écart train/validation qui se resserre avec les données → précision "
            "croissante au-delà de ~300 titres."
        ),
    },
    # RR volume is NOT reliably predictable (R²=0.32) — driven by notification open-rate
    # (a human/chaotic Friday-morning factor), not by the algorithm. SHAP is a flat line
    # at zero broken by 2-3 outliers; every lever (followers, recent streams, saves,
    # playlist-adds) is flat. `volume_reliable: False` gates the forecast OUT of every
    # user-facing surface — RR ships as classification-only (AUC 0.96). The regression
    # artifacts stay in the admin model-perf tab + the diagnostic scatter as honest
    # "R²=0.32 — diagnostic, not a forecast" evidence.
    "RR": {
        "model_version": "v1", "train_n": 300, "r2": 0.32, "bias": "noise",
        "volume_reliable": False,
        "suppressed_note": (
            "Abonnés notifiés ✅ — le volume Release Radar n'est PAS prédictible : il dépend "
            "du taux d'ouverture des notifications (facteur humain), pas de l'algorithme. "
            "On s'appuie sur la classification (AUC 0.96), pas sur une prévision de streams/€."
        ),
        "interpretation": (
            "Régresseur Release Radar NON fiable (R²=0.32) : il cherche de la logique dans "
            "du bruit. Cassé par 2-3 outliers viraux, il prédit même des volumes négatifs sur "
            "de vrais hits. Volume masqué des surfaces utilisateur pour éviter de fausses "
            "promesses financières ; conservé ici comme diagnostic uniquement."
        ),
    },
}

# Single-sourced wording for the floor reframing of *_streams_forecast_7d.
FORECAST_FLOOR_DISCLAIMER = (
    "Estimation = **plancher garanti** (worst-case). Le modèle sous-estime les hits : "
    "le potentiel réel est souvent bien supérieur si la sauce prend."
)

# ── Classification scorecard metrics ──────────────────────────────────────────
ALGO_MODEL_METRICS = {
    "DW": {
        "model_version": "v1", "test_n": 102,
        "confusion": {"TN": 74, "FP": 5, "FN": 11, "TP": 12},
        "auc": 0.878, "f1": 0.60, "accuracy": 0.843,
        "precision": 0.705, "recall": 0.521, "pr_ap": 0.77, "lift_top10": 3.5,
        "baseline_accuracy": 0.774,
        "interpretation": (
            "Quand le modèle lève le drapeau, il a raison ~7 fois sur 10 (précision 70%), "
            "mais il rate ~48% des hits (recall 52%). AUC 0.88 = bon pouvoir de classement. "
            "Piège : l'accuracy 84% n'est que +7 pts vs un modèle qui prédirait toujours "
            "« échec » (77%)."
        ),
    },
    "RR": {
        "model_version": "v1", "test_n": 102,
        "confusion": {"TN": 76, "FP": 6, "FN": 4, "TP": 16},
        "auc": 0.961, "f1": 0.762, "accuracy": 0.902,
        "precision": 0.727, "recall": 0.80, "pr_ap": 0.88, "lift_top10": 5.1,
        "baseline_accuracy": 0.804,
        "interpretation": (
            "AUC 0.961 = sniper : quand il dit « Release Radar », il a ~73% de raison "
            "(précision) et capte 80% des hits (recall). Lift top-décile ×5.1 = un label "
            "qui investit en Meta Ads sur ses prédictions multiplie par 5 ses chances de "
            "ROI vs un tir à l'aveugle. Piège accuracy modéré : 90% vs 80% (toujours-échec) "
            "— la fenêtre RR est rare, d'où une base déséquilibrée."
        ),
    },
    "RADIO": {
        "model_version": "v1", "test_n": 102,
        "confusion": {"TN": 47, "FP": 7, "FN": 7, "TP": 41},
        "auc": 0.941, "f1": 0.854, "accuracy": 0.863,
        "precision": 0.854, "recall": 0.854, "pr_ap": None, "lift_top10": 2.1,
        "baseline_accuracy": 0.529,
        "interpretation": (
            "AUC 0.941 = discrimination quasi parfaite : quand il dit « Radio », tu peux "
            "y aller. Jeu de test équilibré (54 échecs / 48 succès) → l'accuracy 86% est un "
            "vrai gain vs 53% (toujours-échec), contrairement au DW. Symétrie des erreurs "
            "(7 FP / 7 FN)."
        ),
    },
}


# ── Pure helpers ──────────────────────────────────────────────────────────────
# Helpers default to the entry/classification registry (ALGO_FEATURE_ZONES) but
# accept `registry=ALGO_VOLUME_ZONES` to operate on the volume/regressor zones with
# the same code path.
def _spec(algo: str, feature: str, registry: dict | None = None) -> dict | None:
    reg = registry if registry is not None else ALGO_FEATURE_ZONES
    return reg.get(algo, {}).get(feature)


def feature_ids(algo: str) -> list[str]:
    return list(ALGO_FEATURE_ZONES.get(algo, {}).keys())


def volume_feature_ids(algo: str) -> list[str]:
    return list(ALGO_VOLUME_ZONES.get(algo, {}).keys())


def volume_algos() -> list[str]:
    """Algorithms with a populated volume/regressor zone set, in display order."""
    return [a for a in ("DW", "RR", "RADIO") if a in ALGO_VOLUME_ZONES]


def volume_scaling_threshold(algo: str):
    """Organic-streams scaling threshold (NonAlgoStreams28Days target) for an algo.

    Single source of truth for the budget-scaling calculator — never hardcode it.
    """
    spec = _spec(algo, "NonAlgoStreams28Days", registry=ALGO_VOLUME_ZONES)
    return spec.get("target") if spec else None


def regressor_note(algo: str) -> str | None:
    """Interpretation text for the volume regressor (hungry-model badge), or None."""
    m = ALGO_REGRESSOR_METRICS.get(algo)
    return m.get("interpretation") if m else None


def volume_forecast_reliable(algo: str) -> bool:
    """Whether the volume regressor is trustworthy enough to show a forecast to users.

    Defaults True; only False when a regressor is explicitly flagged unreliable (RR,
    R²=0.32 — noise). Single source of truth so every user-facing surface gates the
    same way instead of hardcoding `if algo == "RR"`.
    """
    return ALGO_REGRESSOR_METRICS.get(algo, {}).get("volume_reliable", True)


def volume_suppressed_note(algo: str) -> str | None:
    """Short user-facing caption shown INSTEAD of a forecast for an unreliable
    regressor (e.g. RR ships classification-only). None when the forecast is reliable."""
    if volume_forecast_reliable(algo):
        return None
    return ALGO_REGRESSOR_METRICS.get(algo, {}).get("suppressed_note")


def radio_discovery_recovery_note(feats: dict) -> str | None:
    """Margin-recovery advice for Radio: once a track reaches cruising velocity, the
    Discovery Mode opt-in (−30% royalties) buys entry but adds ZERO volume (flat SHAP),
    so recommend turning it off. Returns None below the cruising threshold.

    DiscoveryMode is imputed-to-0 in production (no live source) so this can't read the
    actual opt-in state — the note is therefore phrased conditionally ("if enabled").
    """
    spec = _spec("RADIO", "StreamsLast7Days", registry=ALGO_VOLUME_ZONES)
    if not spec:
        return None
    val = decode_feature_value("RADIO", "StreamsLast7Days", feats, registry=ALGO_VOLUME_ZONES)
    target = spec.get("target")
    if val is None or target is None or val < target:
        return None
    return (
        f"💸 Vitesse de croisière atteinte (~{val:,.0f} streams/7j ≥ {target:,.0f}). "
        "Si Discovery Mode est activé sur ce titre, désactive-le : il a fait son travail "
        "d'entrée en Radio mais n'ajoute aucun volume (SHAP plat à zéro). Tu récupères "
        "~30% de royalties — l'algo continue de pousser via ta vélocité organique."
    )


def populated_algos() -> list[str]:
    """Algorithms with feature zones, in canonical display order (DW, RR, RADIO)."""
    order = ["DW", "RR", "RADIO"]
    return [a for a in order if a in ALGO_FEATURE_ZONES]


def decode_feature_value(algo: str, feature: str, feats: dict, registry: dict | None = None):
    """Recover the raw human value of a feature from a features_json dict."""
    spec = _spec(algo, feature, registry)
    if spec is None or not feats:
        return None
    raw = feats.get(spec["json_key"])
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return math.expm1(val) if spec.get("decode") == "expm1" else val


def zone_for_value(algo: str, feature: str, value, registry: dict | None = None):
    """Return the verdict ('malus'|'neutral'|'bonus') for a raw value, or None."""
    spec = _spec(algo, feature, registry)
    if spec is None or value is None:
        return None
    for low, high, verdict, _note in spec["zones"]:
        if (low is None or value >= low) and (high is None or value < high):
            return verdict
    return None


def velocity_penalty_threshold(algo: str):
    """Lower bound of the Velocity_Streams 'malus' (too-high) zone for an algo.

    Single source of truth for the hyper-growth cutoff so views never hardcode it.
    """
    spec = _spec(algo, "Velocity_Streams")
    if spec is None:
        return None
    for low, _high, verdict, _note in spec["zones"]:
        if verdict == "malus" and low is not None and low > 0:
            return low
    return None


def nearest_target(algo: str, feature: str, value):
    """Gap to the feature's critical threshold. None if no target / no value."""
    spec = _spec(algo, feature)
    if spec is None or value is None or spec.get("target") is None:
        return None
    target = spec["target"]
    gap = target - value
    return {"target": target, "gap": gap, "reached": gap <= 0}


def calibration_note(algo: str, raw):
    """Reliability text for a raw classifier score, or None if unknown."""
    bands = ALGO_CALIBRATION_BANDS.get(algo)
    if not bands or raw is None:
        return None
    for low, high, text in bands:
        if low <= raw < high:
            return text
    return None


def build_coach_actions(algo: str, feats: dict) -> list[dict]:
    """Ranked prescriptive actions for an algo's malus-zone, actionable, measured
    features. Velocity-too-high becomes a high-priority 'smooth' action; the rest
    are 'raise' actions ranked by how close they are to their target.
    """
    feats = feats or {}
    actions: list[dict] = []
    for fid, spec in ALGO_FEATURE_ZONES.get(algo, {}).items():
        if (spec.get("live_unavailable") or spec.get("divergent")
                or spec.get("actionable") is False):
            continue
        val = decode_feature_value(algo, fid, feats)
        if val is None or zone_for_value(algo, fid, val) != "malus":
            continue
        if fid == "Velocity_Streams":  # malus = too high → smooth, top priority
            actions.append({"feature": fid, "label": spec["label"], "unit": spec["unit"],
                            "current": val, "target": None, "gap": None,
                            "urgency": -1.0, "kind": "smooth", "lever": spec["lever"]})
            continue
        nt = nearest_target(algo, fid, val)
        if not nt or nt.get("reached"):
            continue
        target = nt["target"]
        urgency = abs(nt["gap"]) / abs(target) if target else abs(nt["gap"])
        actions.append({"feature": fid, "label": spec["label"], "unit": spec["unit"],
                        "current": val, "target": target, "gap": nt["gap"],
                        "urgency": urgency, "kind": "raise", "lever": spec["lever"]})
    actions.sort(key=lambda a: a["urgency"])
    return actions
