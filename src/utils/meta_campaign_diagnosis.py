"""Pourquoi la liste des campagnes Meta est vide — la vraie raison, pas la première.

Type: Utility
Uses: — (pure)
Triggers: src/dashboard/views/meta_mapping/_campaigns.py
Depends on: rien
Persists in: rien

Le 2026-09-06, un artiste dont Meta est branché — pastille verte, sonde OK, 224
lignes d'insights, collecte lancée vingt minutes plus tôt et retournée `success`
avec 879 lignes — a lu ceci sur l'onglet Mapping :

    « Aucune campagne. Connecte Meta Ads dans 🔑 Credentials API, puis lance
      🚀 Lancer TOUTES les collectes dans la barre latérale. »

Les deux gestes demandés étaient faits. Le message ne mesurait rien : il énonçait
la cause la plus fréquente d'une liste vide comme si c'était la seule.

Une liste vide a QUATRE causes, et elles appellent quatre gestes différents — dont
deux qui ne sont pas des gestes du tout. Les distinguer demande trois faits que
l'application possède déjà : l'identité déclarée, le dernier run de collecte, et
la présence de lignes de performance.
"""
from __future__ import annotations

NO_IDENTITY = "no_identity"
NEVER_RAN = "never_ran"
RUN_FAILED = "run_failed"
NO_CAMPAIGN_AT_ALL = "no_campaign_at_all"
CAMPAIGNS_ELSEWHERE = "campaigns_elsewhere"


def diagnose_empty_campaigns(*, identity_present: bool, last_run_status: str | None,
                             insight_rows: int) -> str:
    """La cause d'une liste de campagnes vide, à partir de trois faits mesurés.

    `last_run_status` est le statut du dernier run Meta de CE locataire
    (`etl_run_log`), `None` s'il n'y en a jamais eu.

    L'ordre des tests est celui de la chaîne : sans identité rien ne part, sans run
    rien n'arrive, un run raté explique tout, et si le run a réussi la question
    change complètement — ce n'est plus « pourquoi ça n'a pas marché » mais « ce
    compte publicitaire a-t-il des campagnes ».

    `CAMPAIGNS_ELSEWHERE` est le cas mesuré du 2026-09-06 : des lignes de
    performance existent, donc l'API a bien répondu pour ce compte, mais aucune
    campagne n'est rattachée à ce locataire. `meta_campaigns` a pour clé de conflit
    `campaign_id` SEUL — délibérément, sa clé primaire est référencée par quinze
    clés étrangères et un upsert ne transfère jamais la propriété d'une ligne. Deux
    locataires qui déclarent le MÊME compte publicitaire se partagent donc les
    identifiants de campagne, et le second n'en reçoit aucune.
    """
    if not identity_present:
        return NO_IDENTITY
    if last_run_status is None:
        return NEVER_RAN
    if last_run_status != "success":
        return RUN_FAILED
    return CAMPAIGNS_ELSEWHERE if insight_rows else NO_CAMPAIGN_AT_ALL
