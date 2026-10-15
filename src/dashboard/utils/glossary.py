"""The glossary — every technical word the app uses, defined ONCE (R592).

Type: Utility
Uses: src.dashboard.utils.i18n
Triggers: views/glossary.py, tools/dev/glossary_inventory.py
Persists in: nothing

Owner, 2026-10-15 : « une vue Glossaire dans Compte, juste après Mon compte : le schéma du
fonctionnement de l'app et toutes les définitions techniques ». The pages are read by the
chart alone (R565–R570); the words they cannot define in place are defined here, and the
inventory (`make glossary-inventory`) lists where a view still defines one in prose.

Each entry: (key, group, FR term, FR definition, detection patterns). The EN strings are
`glossary.term.<key>` / `glossary.def.<key>` in `i18n_catalog/glossary.py`; the patterns are
what the inventory looks for in the views' text (case-insensitive regexes).
"""
from __future__ import annotations

from src.dashboard.utils.i18n import t
from src.utils.algo_order import ALGO_ORDER

GROUPS = (
    ("algo", "🎚️ Algorithmes Spotify"),
    ("meta", "📣 Publicité Meta"),
    ("money", "💰 Argent"),
    ("model", "🧠 Prédiction"),
    ("data", "🗄️ Données"),
)

# The three algorithms, read in the one order (src.utils.algo_order.ALGO_ORDER).
_ALGOS = {
    "DW": ("dw", "algo", "Discover Weekly (DW)",
     "Playlist personnelle hebdomadaire envoyée à des auditeurs qui ne te connaissent pas "
     "encore : la découverte pure, la porte la plus dure à ouvrir.", (r"discover weekly",)),
    "RADIO": ("radio", "algo", "Radio",
     "Flux algorithmique sans fin qui enchaîne des titres similaires : le signe que Spotify "
     "te juge fiable pour nourrir ses recommandations.", (r"\bradio\b",)),
    "RR": ("rr", "algo", "Release Radar (RR)",
     "Playlist hebdomadaire poussée à tes abonnés à chaque sortie, pendant environ quatre "
     "semaines.", (r"release radar",)),
}

TERMS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = tuple(
    _ALGOS[a] for a in ALGO_ORDER) + (
    ("trigger", "algo", "Déclenchement",
     "Le moment où une playlist algorithmique se met à pousser un titre : ses écoutes "
     "dépassent le seuil qu'elle produit d'elle-même.", (r"d[ée]clench",)),
    ("elbow", "algo", "Seuil de déclenchement (elbow)",
     "Volume d'écoutes produites PAR la playlist sur 28 jours qui marque le début d'un "
     "déclenchement : ~137 (DW), ~639 (Radio), ~130 (RR).", (r"elbow",)),
    ("pi", "algo", "Popularity Index (PI)",
     "La note de popularité 0–100 que Spotify donne à un titre ; chaque algorithme a un "
     "minimum.", (r"popularity index",)),
    ("velocity", "algo", "Vélocité",
     "La vitesse à laquelle les écoutes récentes accélèrent.", (r"velocity|v[ée]locit[ée]",)),
    ("discovery_mode", "algo", "Discovery Mode",
     "Option Spotify, payée en commission sur tes royalties, qui force l'entrée en Radio.",
     (r"discovery mode",)),
    ("playlist_adds", "algo", "Ajouts en playlist",
     "Le nombre de playlists d'auditeurs où ton titre a été ajouté, relevé dans Spotify for "
     "Artists.", (r"ajouts? en playlist",)),
    ("cpr", "meta", "CPR (coût par résultat)",
     "Ce que coûte un résultat de pub — ici un clic sortant vers ta musique : dépense "
     "totale ÷ résultats totaux.", (r"\bCPR\b",)),
    ("ctr", "meta", "CTR (taux de clic)",
     "Clics ÷ impressions : la part des gens qui ont vu la pub et cliqué.", (r"\bCTR\b",)),
    ("cpm", "meta", "CPM",
     "Coût pour mille impressions.", (r"\bCPM\b",)),
    ("cpc", "meta", "CPC",
     "Coût par clic sur la pub.", (r"\bCPC\b",)),
    ("impression", "meta", "Impression",
     "Une fois où ta pub s'est affichée à l'écran de quelqu'un.", (r"impressions?\b",)),
    ("reach", "meta", "Couverture (reach)",
     "Le nombre de personnes différentes qui ont vu la pub au moins une fois.",
     (r"\breach\b|couverture",)),
    ("outbound", "meta", "Clic sortant",
     "Un clic qui quitte Meta vers ton lien (smart link, Spotify).", (r"clics? sortants?",)),
    ("creative", "meta", "Créative",
     "Une version de ta pub : le visuel ou la vidéo, et son texte.", (r"cr[ée]atives?",)),
    ("hook", "meta", "Accroche (hook)",
     "Les premières secondes d'une vidéo, ce qui retient ou non le pouce.",
     (r"\bhook\b|accroche",)),
    ("adset", "meta", "Ensemble de pubs (ad set)",
     "Le niveau d'une campagne Meta qui porte l'audience, le budget et l'optimisation.",
     (r"ad ?set",)),
    ("placement", "meta", "Placement",
     "L'endroit où la pub s'affiche : fil Instagram, stories, Reels, Facebook…",
     (r"placements?",)),
    ("frequency", "meta", "Fréquence",
     "Impressions ÷ personnes touchées : combien de fois, en moyenne, une même personne a "
     "vu la pub.", (r"fr[ée]quence",)),
    ("engagement", "meta", "Engagement",
     "Réactions + commentaires + partages + enregistrements sur la pub.",
     (r"\bengagement\b",)),
    ("step", "meta", "% de l'étape d'avant",
     "Dans un entonnoir, la part des gens de l'étape précédente qui ont atteint celle-ci "
     "(1,1 % = 11 sur 1 000).", (r"[ée]tape",)),
    ("unit_cost", "meta", "Coût à l'unité",
     "La dépense divisée par le nombre à cette étape (0,127 € l'unité = 1 € pour ~8 clics).",
     (r"co[uû]t (?:à|a) l'unit[ée]|l'unit[ée]",)),
    ("smartlink", "meta", "Smart link",
     "La page de destination (Hypeddit) qui renvoie vers chaque plateforme d'écoute.",
     (r"smart ?link",)),
    ("roi", "money", "ROI",
     "Retour sur investissement : (revenus − dépenses) ÷ dépenses.", (r"\bROI\b",)),
    ("breakeven", "money", "Point mort",
     "Le moment où le cumul des revenus rattrape le cumul des dépenses.",
     (r"point mort",)),
    ("per_stream", "money", "Taux par écoute",
     "Ce que rapporte une écoute, mesuré sur tes propres relevés de revenus.",
     (r"par [ée]coute",)),
    ("ltv", "money", "LTV",
     "Ce qu'un abonné rapporte sur toute sa durée d'abonnement.", (r"\bLTV\b",)),
    ("mrr", "money", "MRR",
     "Revenu mensuel récurrent des abonnements.", (r"\bMRR\b",)),
    ("p50", "model", "Médiane (P50)",
     "La valeur du milieu : la moitié des titres comparables font moins, l'autre moitié "
     "plus.", (r"\bP50\b|m[ée]diane",)),
    ("p25_p75", "model", "Fourchette P25–P75",
     "La bande où tombe la moitié centrale des titres comparables.", (r"P25|P75",)),
    ("probability", "model", "Probabilité calibrée",
     "50 % veut dire vraiment une chance sur deux : la probabilité a été corrigée sur les "
     "titres passés.", (r"calibr",)),
    ("shap", "model", "Poids des paramètres (SHAP)",
     "Ce que chaque paramètre d'un titre a pesé dans la prédiction du modèle.",
     (r"\bSHAP\b",)),
    ("cohort", "model", "Cohorte",
     "Des titres comparés au même âge depuis leur sortie.", (r"cohorte",)),
    ("s4a", "data", "Spotify for Artists (S4A)",
     "L'espace artiste de Spotify, dont on importe les exports CSV.",
     (r"spotify for artists|\bS4A\b",)),
    ("collect", "data", "Collecte",
     "La lecture automatique de chaque plateforme, chaque nuit.", (r"collecte",)),
    ("mapping", "data", "Correspondance des titres (mapping)",
     "Le lien entre un même titre vu par plusieurs plateformes, et entre une campagne et "
     "le titre qu'elle promeut.", (r"\bmapping\b",)),
)


def term(key: str) -> str:
    fr = next(e[2] for e in TERMS if e[0] == key)
    return t(f"glossary.term.{key}", fr)


def definition(key: str) -> str:
    fr = next(e[3] for e in TERMS if e[0] == key)
    return t(f"glossary.def.{key}", fr)


def by_group() -> list[tuple[str, list[str]]]:
    """[(group label, [term keys])] in GROUPS order."""
    return [(t(f"glossary.group.{g}", label), [e[0] for e in TERMS if e[1] == g])
            for g, label in GROUPS]
