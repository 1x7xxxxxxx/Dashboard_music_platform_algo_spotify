"""Ce que chaque plan ouvre — écrit UNE fois, dérivé du verrou réel.

Type: Utility
Uses: stripe_schema (PLAN_FEATURES, page_is_locked), i18n
Depends on: src/database/stripe_schema.py
Persists in: nothing

Pourquoi ce module existe — mesuré le 2026-09-21
------------------------------------------------
Le catalogue des plans était écrit **trois fois**, et les trois se contredisaient :

    surface              Export PDF      « génération vidéo 60+ »
    billing.py           dans FREE  ❌   annoncée en Premium  ❌
    upgrade.py           absent          absente
    onboarding.py        dans PREMIUM ✅ absente

Les deux erreurs sont de nature différente, et c'est ce qui rend la troisième copie
nécessaire à supprimer :

* **Export PDF** a QUITTÉ Free le 2026-09-04, décision explicite (commit 5fdc65a :
  « ce qui se vend n'est pas la donnée … c'est le RAPPORT »). `onboarding.py` a
  suivi, `billing.py` ne l'a jamais su. Une page de facturation promettait donc
  gratuitement ce que le menu verrouille — dix-sept jours durant.
* **« 🎬 Génération de créatives vidéo (60+ par campagne) »** n'a jamais existé
  dans le produit : aucun `ffmpeg`, aucun `moviepy`, aucune génération de vidéo
  nulle part dans l'arbre. C'est une prestation HUMAINE, et elle vit désormais où
  elle est vraie — le panneau de service, pas la carte d'un abonnement à 10 €.

Le contrat de ce module
-----------------------
Chaque ligne d'argumentaire NOMME la page qu'elle vend. Le tiers d'affichage n'est
donc pas écrit à la main : il se LIT dans `page_is_locked`. Une page qui change de
plan déplace sa ligne toute seule, et une ligne qui ne correspond à aucune page se
fait attraper par `tests/test_the_plan_pitch_matches_the_gate.py`.

C'est la leçon que le commit 5fdc65a avait déjà tirée pour son propre garde — « un
garde qui recopie une décision se périme avec elle » — appliquée cette fois au
texte que l'artiste lit.
"""
from __future__ import annotations

from src.database.stripe_schema import ALWAYS_ACCESSIBLE, page_is_locked
from src.dashboard.utils.i18n import t

# (clé de page, clé i18n, texte FR)
#
# Le texte nomme une DÉCISION, pas une page — c'est la règle posée le 2026-09-04
# (« le tableau des plans nomme des décisions, pas des pages ») et la seule des
# trois copies qui la respectait était `onboarding.py`. On garde sa voix.
#
# `page=None` = un avantage qui n'est pas une page (support, nombre d'artistes).
# Il est alors rangé à la main, et le garde l'exige explicitement.
_PITCH: tuple[tuple[str | None, str, str], ...] = (
    # ── Ce que le plan gratuit ouvre ─────────────────────────────────────────
    ("spotify_s4a_combined", "pitch.spotify",
     "🎵 **Tes écoutes Spotify**, titre par titre, avec tes sorties et tes "
     "auditeurs sur la même figure"),
    ("apple_music", "pitch.apple", "🎎 **Apple Music** — écoutes et Shazam"),
    ("youtube", "pitch.youtube", "🎬 **YouTube** — chaîne et vidéos"),
    ("soundcloud", "pitch.soundcloud", "☁️ **SoundCloud** — écoutes et engagement"),
    ("instagram", "pitch.instagram", "📸 **Instagram** — abonnés et publications"),
    ("meta_ads_overview", "pitch.meta_overview",
     "📱 **Tes campagnes Meta Ads** — dépense, coût par résultat, par campagne"),
    ("hypeddit", "pitch.hypeddit", "📱 **Hypeddit** — visites et clics de tes smart links"),
    ("imusician", "pitch.imusician",
     "💰 **Ce que tes écoutes t'ont rapporté** — iMusician, DistroKid, et le "
     "point d'équilibre avec ta pub"),
    ("sacem", "pitch.sacem", "🎼 **Tes royalties SACEM**"),
    ("meta_mapping", "pitch.mapping",
     "🔗 **Relier tes titres entre plateformes** — suggestions automatiques"),
    ("export_csv", "pitch.export_csv",
     "⬇️ **Tes données restent les tiennes** — export CSV complet, sur les deux plans"),
    ("credentials", "pitch.credentials",
     "🔑 **Brancher tes comptes** et importer tes exports CSV / XLSX"),
    ("saisie_s4a", "pitch.saisie",
     "📝 **Saisir tes ajouts en playlist** — ils nourrissent les prédictions"),
    ("data_wrapped", "pitch.wrapped", "🎁 **Ton Data Wrapped** annuel"),
    ("referral", "pitch.referral", "🎁 **Parrainage** — 1 mois offert par filleul"),

    ("algo_preview", "pitch.preview",
     "🔓 **Un aperçu de Road to Algo** sur ta dernière sortie — les actions à faire et "
     "le budget pour déclencher les algos"),

    # ── Ce que l'abonnement ouvre en plus ────────────────────────────────────
    ("trigger_algo", "pitch.trigger",
     "🚀 **Savoir si un titre va déclencher Discover Weekly** — avant de dépenser "
     "en promo"),
    ("revenue_forecast", "pitch.money",
     "💰 **Où va ton argent, et quand tu rentres dans tes frais** — revenus, "
     "publicité et coûts de sortie sur une seule figure, avec la date du point mort"),
    ("meta_x_spotify", "pitch.meta_x",
     "🔀 **Quel euro de pub a produit quelles écoutes** — Meta × Spotify × "
     "Hypeddit, et le coût d'une écoute pays par pays"),
    # R146 — un argumentaire d'abonnement qui promet un « coût par résultat »
    # promet plus que ce que la donnée porte. Le mot juste est le clic sortant :
    # une promesse fausse dans une page de vente se paie en confiance, et ce dépôt
    # a mesuré le 2026-09-22 ce que coûtent deux promesses non tenues.
    ("meta_cpr_optimizer", "pitch.cpr",
     "💶 **Combien remettre sur quelle campagne** — augmenter, tenir ou couper, "
     "d'après le coût par clic sortant et l'âge de ton audience"),
    ("meta_creatives", "pitch.creatives",
     "🎨 **Quelle créative et quel hook coûtent le moins cher** par clic sortant"),
    ("meta_breakdowns", "pitch.breakdowns",
     "🌍 **Qui a vu tes pubs** — pays, âge, placement"),
    ("export_pdf", "pitch.pdf",
     "📄 **Ton rapport PDF filtrable** — à la demande, et envoyé par mail chaque "
     "semaine"),
)

# Les avantages qui ne sont pas des pages. Rangés à la main, donc NOMMÉS ici : le
# garde vérifie que cette liste et `_PITCH` ne se recouvrent pas.
_HORS_PAGE: dict[str, tuple[tuple[str, str], ...]] = {
    "free": (("pitch.one_artist", "1 artiste"),),
    "premium": (
        ("pitch.ten_artists", "Jusqu'à 10 artistes sur le même compte"),
        ("pitch.support", "Support prioritaire"),
    ),
}


def tier_of(page: str) -> str:
    """Le plan qui ouvre cette page — LU dans le verrou, jamais recopié."""
    if page in ALWAYS_ACCESSIBLE:
        return "free"
    return "premium" if page_is_locked("free", page) else "free"


def bullets(tier: str) -> list[str]:
    """Les arguments de ce plan, traduits, dans l'ordre du fichier.

    Premium ne répète pas les lignes de Free : la carte dit « tout ce que contient
    Free » et n'énumère que le surplus. Répéter vingt lignes pour en distinguer
    sept est la meilleure façon de n'en faire lire aucune.
    """
    out = [t(cle, txt) for page, cle, txt in _PITCH
           if page is not None and tier_of(page) == tier]
    out += [t(cle, txt) for cle, txt in _HORS_PAGE.get(tier, ())]
    return out


def pages_of(tier: str) -> set[str]:
    """Les pages que cet argumentaire nomme pour ce plan — pour le garde."""
    return {page for page, _c, _t in _PITCH
            if page is not None and tier_of(page) == tier}
