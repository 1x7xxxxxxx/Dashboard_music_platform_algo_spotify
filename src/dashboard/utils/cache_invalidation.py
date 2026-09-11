"""Un seul endroit où l'on dit : « la donnée vient de changer, oublie ce que tu sais ».

Type: Utility
Uses: kpi_helpers, series_cache
Triggers: appelé par tout chemin d'écriture du dashboard
Persists in: nothing

Pourquoi cette fonction existe plutôt que trois appels
------------------------------------------------------
Le dashboard sert ses compteurs et ses séries depuis deux caches de 600 s. Cette
durée longue n'est sûre que parce que les moments où la donnée change en pleine
journée purgent explicitement — « on ne fait pas confiance à l'horloge, on
écoute l'événement ».

Trois chemins d'écriture ne purgeaient rien, trouvés le 2026-09-11 : le dépôt de
CSV (`views/upload_csv.py`), l'import fait par un admin pour le compte d'un
artiste (`views/admin.py`) et la saisie manuelle de revenus
(`views/imusician.py`). Le symptôme est le même dans les trois cas : l'écran
confirme, et le chiffre ne bouge pas pendant dix minutes sans que rien
n'explique pourquoi.

En corrigeant les trois, la même explication a été écrite trois fois — et la
première version faisait grandir un fichier que le cliquet de longueur
n'autorise qu'à raccourcir. Le cliquet avait raison sur le fond : trois copies
d'une règle sont trois endroits où la quatrième sera oubliée.

Le cache Streamlit est GLOBAL AU PROCESSUS, pas à la session : c'est pourquoi
une purge côté admin atteint bien l'entrée d'un artiste.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def purge_after_write(rows_written: int | bool = 1) -> None:
    """Vide les caches de lecture après une écriture. Ne lève jamais.

    `rows_written` à 0 ou False : rien n'a été écrit, il n'y a rien à invalider.
    """
    if not rows_written:
        return
    try:
        from src.dashboard.utils.kpi_helpers import clear_kpi_caches
        clear_kpi_caches()      # purge aussi le cache des séries
    except Exception:           # noqa: BLE001 — une purge ratée ne casse pas l'écriture
        logger.warning("purge des caches impossible après une écriture")
