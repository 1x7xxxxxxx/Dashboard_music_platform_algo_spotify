"""« Périmé » veut dire la même chose sur toutes les surfaces qui le disent.

Type: Test
Uses: ast
Depends on: src/utils/freshness_monitor, src/dashboard/utils/kpi_helpers,
            airflow/dags/alert_monitor.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Quatre barèmes de fraîcheur coexistaient, et deux se contredisaient devant le même fait.
Mesuré le 2026-09-20 sur **4 702 écarts réels** entre collectes consécutives :

  * **26 écarts entre 24 h et 36 h** — le badge peint 🟠 et aucune surface d'alerte ne
    parle. ⚠️ **Ce n'est PAS un défaut**, contrairement à ce que R140 §16.11 supposait :
    un badge informe, il ne réveille personne, et une nuit manquée n'est pas une panne.
  * **6 entre 36 h et 48 h** — le canari criait pendant que `freshness_monitor`
    répondait « fraîche ». **Voilà la vraie contradiction** : deux surfaces de
    SUPERVISION, deux verdicts, un seul fait.

⚠️ Et le canari appliquait **36 h à TOUT**, y compris à `Spotify S4A` et `Apple Music`
que le registre déclare nourries à la main, à **168 h**. Un export déposé chaque semaine
— la cadence de publication de S4A — était « en retard » dès le deuxième jour.

⚠️ **Ce garde n'exige PAS un chiffre unique, et il fige même une NON-coïncidence.**
L'unification a lieu entre les deux surfaces de SUPERVISION — le canari demande désormais
son seuil au registre au lieu de porter un 36 h uniforme. Le badge de l'artiste garde le
sien, sur une demande explicite du propriétaire, et
`test_the_artist_badge_is_NOT_aligned_and_that_is_the_measured_answer` empêche qu'on le
« corrige ».
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dashboard.utils.kpi_helpers import _WARN_H  # noqa: E402
from src.utils.freshness_monitor import (  # noqa: E402
    _CSV_STALE_H, _DEFAULT_STALE_H, _MANUAL_STALE_H, MONITOR_TARGETS, stale_hours_for,
)

_DAG = ROOT / "airflow" / "dags" / "alert_monitor.py"


def test_the_registry_is_the_only_place_a_stale_hour_is_chosen() -> None:
    """ANTI-VACUITÉ : le registre distingue les CADENCES, et elles sont ordonnées.

    ⚠️ Ce test exigeait `seuils == {48, 168}` — exactement deux, ni plus ni moins.
    Le 2026-09-22, trois sources saisies à la MAIN sont entrées (distributeur, SACEM,
    Hypeddit) avec un seuil de 30 jours, et il a rougi. Il avait raison de parler,
    et tort dans sa forme : il figeait un INSTANTANÉ (« deux seuils ») là où sa
    propre phrase d'échec nomme une PROPRIÉTÉ (« il doit distinguer une source
    nourrie par un DAG d'une source nourrie à la main »).

    Un troisième palier n'est pas un desserrage, c'est la même distinction poussée
    d'un cran : un relevé SACEM arrive par trimestre, un relevé de distributeur par
    mois. Les juger à sept jours les ferait crier onze mois sur douze — c'est la
    leçon des 85 nuits d'affilée du 2026-09-14.

    Ce qui est exigé ici est donc : au moins trois paliers, STRICTEMENT croissants du
    robot vers l'humain. Un seuil manuel plus court qu'un seuil de DAG serait une
    erreur de saisie, et celle-là rougit encore.
    """
    seuils = {t["stale_h"] for t in MONITOR_TARGETS}
    assert len(seuils) >= 3, (
        f"le registre ne porte que {sorted(seuils)} — il doit distinguer au moins "
        "trois cadences : un DAG quotidien, un dépôt de fichier, une saisie mensuelle. "
        "Sans ça, `stale_hours_for` ne sert à rien.")
    assert _DEFAULT_STALE_H < _CSV_STALE_H < _MANUAL_STALE_H, (
        f"les paliers ne sont pas ordonnés : DAG={_DEFAULT_STALE_H} h, "
        f"fichier={_CSV_STALE_H} h, saisie={_MANUAL_STALE_H} h. Plus un humain est "
        "dans la boucle, plus la source a le droit d'être vieille sans être fautive.")
    assert {_DEFAULT_STALE_H, _CSV_STALE_H, _MANUAL_STALE_H} <= seuils, (
        "un palier déclaré n'est utilisé par aucune source — il ne garde rien.")


def test_the_artist_badge_is_NOT_aligned_and_that_is_the_measured_answer() -> None:
    """⚠️ MA RECOMMANDATION ÉTAIT FAUSSE ICI, et un test préexistant l'a dit.

    R140 §16.11 proposait d'aligner les quatre barèmes sur `freshness_monitor`. Appliqué
    au badge de l'artiste, l'alignement faisait rougir une source `api` de DEUX jours —
    ce que `tests/test_a_scale_matches_the_contract_it_judges.py` interdit nommément,
    parce qu'il porte une demande EXPLICITE du propriétaire : « passe le seuil rouge à
    30 j et orange à partir de 1 semaine », née de la plainte « c'est en rouge alors
    qu'on a que 3 jours de retard ».

    **Un rouge qui s'allume sur un comportement normal cesse d'être lu**, et il ne dira
    plus rien le jour où la source casse vraiment.

    Ce test fige donc la NON-coïncidence, pour qu'un futur alignement bien intentionné
    rencontre une raison écrite plutôt qu'un nombre qui traîne.
    """
    assert _WARN_H != _DEFAULT_STALE_H, (
        f"le badge de l'artiste a été aligné sur le seuil de supervision ({_WARN_H} h). "
        "Une source `api` de deux jours rougirait, contre une demande explicite du "
        "propriétaire. Les deux barèmes répondent à deux questions : « que montre-t-on "
        "à l'artiste » et « réveille-t-on quelqu'un ».")
    # ⚠️ IL N'Y A PAS DE SECONDE ASSERTION SUR LA PRÉSENCE DU COMMENTAIRE, et c'est
    # une décision. La première version vérifiait `"cesse d'être lu" in texte` — une
    # comparaison de chaîne contre le SOURCE d'un fichier Python, que deux méta-gardes
    # de ce dépôt interdisent : `test_a_guard_reads_structure_not_text` (cliquet gelé
    # par fichier) et `test_a_presence_assertion_is_not_satisfied_by_prose`. Ils ont
    # raison — trois gardes ont été pris au vert sur leur propre défaut le 2026-09-04,
    # dont deux sur le commentaire expliquant le correctif.
    # Les ajouter à leurs listes d'exemption aurait été desserrer un plafond pour le
    # faire taire. L'invariant qui compte est la VALEUR, assertée ci-dessus ; la raison
    # écrite dans `kpi_helpers.py` la rend compréhensible, elle ne la garde pas.


def test_the_canary_asks_the_registry_instead_of_a_flat_number() -> None:
    """Le canari ne doit plus porter son propre seuil.

    Lu à l'AST : un commentaire qui raconte l'ancien `STALE_HOURS = 36` contient le
    texte, et un prédicat textuel rougirait sur sa propre documentation.
    """
    arbre = ast.parse(_DAG.read_text(encoding="utf-8"))
    assignations = [n for n in ast.walk(arbre)
                    if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") in ("STALE_HOURS", "WINDOW_H")
                            for t in n.targets)]
    en_dur = [ast.unparse(n) for n in assignations
              if isinstance(n.value, ast.Constant)]
    assert not any("STALE_HOURS" in e for e in en_dur), (
        f"le canari porte encore son propre seuil : {en_dur}. Il doit appeler "
        "`stale_hours_for(table)` — sinon il juge à 36 h une source que le registre "
        "déclare à 168 h, et il crie sur un export hebdomadaire dès le deuxième jour.")
    assert "stale_hours_for" in _DAG.read_text(encoding="utf-8"), (
        "le canari n'importe pas `stale_hours_for` — il ne peut donc pas connaître le "
        "seuil de la table qu'il juge.")


def test_no_prose_announces_a_threshold_the_code_does_not_use() -> None:
    """⚠️ Une cinquième expression du seuil vivait en PROSE, et elle était fausse.

    `alert_monitor.py:1039` écrivait « *past a 48h threshold* » au-dessus d'un code qui
    utilisait 36. Une prose qui annonce un nombre que le code n'emploie pas est le
    défaut le moins cher à écrire et le plus cher à découvrir.
    """
    texte = _DAG.read_text(encoding="utf-8")
    fautifs = [m.group(0) for m in re.finditer(r"past a \d+ ?h threshold", texte)]
    assert not fautifs, (
        f"prose annonçant un seuil fixe : {fautifs}. Le seuil vient du registre et vaut "
        "48 h ou 168 h selon la source — aucune phrase ne peut en nommer un seul.")


def test_the_lookup_gives_each_source_its_declared_threshold() -> None:
    """AUTO-PREUVE : la fonction rend bien ce que le registre déclare, source par source."""
    for t in MONITOR_TARGETS:
        assert stale_hours_for(t["table"]) == t["stale_h"], (
            f"{t['source']} : le registre déclare {t['stale_h']} h et `stale_hours_for` "
            f"rend {stale_hours_for(t['table'])} h.")
    assert stale_hours_for("une_table_inconnue") == _DEFAULT_STALE_H, (
        "une table hors registre doit recevoir le seuil des sources automatiques — le "
        "plus strict des deux, parce qu'entre crier à tort et se taire à tort, c'est le "
        "silence qui coûte.")
