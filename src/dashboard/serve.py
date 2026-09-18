"""Le point d'entrée du conteneur : l'exportateur de métriques, PUIS Streamlit.

Type: Core
Uses: src.utils.metrics, streamlit.web.cli
Triggers: le `CMD` du Dockerfile du dashboard
Persists in: nothing

Pourquoi ce fichier existe
--------------------------
`start_metrics_server()` n'était appelé que par `start_rerun()`, donc **au premier rendu
de page**. Conséquence mesurée le 2026-09-16, juste après un déploiement : le port 9102
n'existait pas, la cible Prometheus `dashboard` était `down`, et l'histogramme de rendu
ne portait **aucune page** — alors que tout allait bien.

Le défaut n'est pas l'exportateur, c'est **qui l'appelle** : la durée de vie de
l'instrument était accrochée à la visite d'un utilisateur. Entre un redémarrage et le
premier visiteur — une nuit, un week-end — la surveillance était absente, et son absence
ressemblait à une panne. C'est la forme la plus coûteuse : un rouge permanent apprend à
lire le rouge comme du bruit, et le prochain vrai `down` passera avec lui.

Pourquoi dans le MÊME processus
--------------------------------
`prometheus_client` tient son registre en mémoire de processus. Streamlit exécute chaque
rendu dans un THREAD du serveur, pas dans un sous-processus : un exportateur démarré ici,
avant de passer la main, voit donc exactement les mêmes compteurs que les rendus.

Un `python -c '…' &` dans le `CMD` ne marcherait PAS — il exposerait un registre vide,
dans un autre processus, et la cible serait `up` en ne mesurant rien. C'est pire que
`down` : un instrument muet qui se déclare sain.

Ce que ça ne corrige pas, et qu'il faut savoir
-----------------------------------------------
Les compteurs sont **remis à zéro à chaque déploiement**, parce qu'ils vivent dans le
processus. C'est normal pour Prometheus (`rate()` et `increase()` gèrent les remises à
zéro de compteur), et c'est précisément pourquoi le résumé QUOTIDIEN vit en base
(`daily_ops_metrics`, migration 125) : lui survit aux redémarrages.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    """Démarre l'exportateur, puis rend la main à `streamlit run`. Ne rend jamais 0."""
    try:
        from src.utils.metrics import start_metrics_server

        if start_metrics_server():
            print("▶ métriques exposées avant le démarrage de Streamlit", flush=True)
        else:
            # On le DIT, et on continue : l'observabilité ne casse pas le produit.
            print("⚠ exportateur de métriques non démarré — le dashboard démarre quand "
                  "même, la cible Prometheus restera `down`", flush=True)
    except Exception as exc:  # noqa: BLE001 — jamais au prix du produit
        print(f"⚠ exportateur de métriques en échec ({type(exc).__name__}) — "
              "le dashboard démarre quand même", flush=True)

    # La jauge des défauts ouverts, lue depuis `app_error_log`. Elle est installée ICI
    # et nulle part ailleurs : `metrics_payload()` de l'API fait `generate_latest()` sur
    # le registre par DÉFAUT, donc un enregistrement dans `_build()` ferait exposer la
    # même jauge par les deux processus — `sum()` doublerait, et l'API exécuterait la
    # requête à chaque scrutation. Contrôle :
    # `tests/test_the_api_measures_itself_without_unbounded_labels.py:118-122` — il exige
    # l'appel ICI et son ABSENCE dans `src/api/main.py`. Le nom annonce ici jusqu'au
    # 2026-09-18 (`test_the_defect_gauge_is_installed_once_and_only_by_the_dashboard.py`)
    # n'a jamais existe : un renvoi qui manque ne se plaint pas, il envoie chercher.
    try:
        from src.utils.defect_gauge import install_open_defects_collector

        if install_open_defects_collector():
            print("▶ jauge des défauts ouverts enregistrée", flush=True)
        else:
            print("⚠ jauge des défauts ouverts non enregistrée — le panneau des "
                  "erreurs restera muet, le dashboard démarre quand même", flush=True)
    except Exception as exc:  # noqa: BLE001 — jamais au prix du produit
        print(f"⚠ jauge des défauts ouverts en échec ({type(exc).__name__}) — "
              "le dashboard démarre quand même", flush=True)

    # Le compteur de lignes de journal, par niveau. Il n'écrit nulle part : il incrémente.
    try:
        from src.utils.log_metrics import install_log_counter

        install_log_counter()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠ compteur de journaux non installé ({type(exc).__name__})", flush=True)

    from streamlit.web import cli as stcli

    port = os.getenv("PORT", "8501")
    sys.argv = ["streamlit", "run", "src/dashboard/app.py",
                "--server.port", port, "--server.address", "0.0.0.0"]
    return stcli.main()


if __name__ == "__main__":
    sys.exit(main())
