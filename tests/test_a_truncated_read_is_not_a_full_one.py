"""Une lecture tronquée ne s'enregistre pas comme une lecture complète.

Type: Test
Uses: pytest, ast
Depends on: src/collectors/instagram_api_collector.py, airflow/dags/instagram_daily.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`fetch_media` plafonne à 10 pages. Au-delà, les publications les plus anciennes ne
sont **pas** relues cette nuit — et le seul signal était un `logger.warning` dans le
journal d'un conteneur. Le run s'enregistrait `success`, donc un historique amputé
était indiscernable d'un historique complet, sur toutes les surfaces qui lisent
`etl_run_log`.

Le dépôt a déjà payé cette classe : 672 échecs de surveillance de CSV en une semaine,
tous journalisés, aucun rapporté. Un fait sur les DONNÉES ne se dit pas dans un log.

Ce qui n'est PAS fait ici
-------------------------
On ne lève pas : un plafond n'est pas une erreur, c'est une lecture bornée, et le
collecteur a raison de rendre ce qu'il a lu. On ne relève pas non plus le plafond —
ce serait échanger une troncature mesurée contre un quota d'API inconnu. On rend la
troncature VISIBLE, avec le statut qui la décrit : `partial`, celui que la tâche
d'alerte remonte déjà.

Contexte, vérifié au passage : R81 supposait que ces collecteurs « relisent tout
chaque nuit sans repère de progression » et qu'un repère les accélérerait. C'est
FAUX, et le vérifier a évité une régression. Ces API rendent des compteurs CUMULÉS
par entité (`playback_count`, `view_count`, `like_count`) : relire chaque entité
chaque nuit n'est pas du gaspillage, c'est la MESURE — tout `platform_timeseries`
(max déjà vu · jours consécutifs · par entité) en dépend. Un repère de progression
aurait figé le compteur de tout titre cessant d'être récent.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=8)
def _read(rel: str) -> str:
    """Lu à l'APPEL, pas à l'import — voir `test_a_test_file_is_collectable_without_what_it_watches`."""
    return (ROOT / rel).read_text(encoding="utf-8")


def COLLECTOR() -> str:
    return _read("src/collectors/instagram_api_collector.py")


def DAG() -> str:
    return _read("airflow/dags/instagram_daily.py")


def test_the_collector_carries_the_truncation_beyond_the_log() -> None:
    """Un `logger.warning` ne sort pas du conteneur ; un attribut, si."""
    tree = ast.parse(COLLECTOR())
    sets_true = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "media_truncated"
                for t in n.targets)
        and isinstance(n.value, ast.Constant) and n.value.value is True]
    assert sets_true, (
        "le plafond de pagination n'est plus porté par `media_truncated` : la "
        "troncature redevient une ligne de journal que personne ne lit")


def test_the_flag_is_reset_before_each_read() -> None:
    """Sinon un locataire tronqué contamine tous les suivants du même processus."""
    tree = ast.parse(COLLECTOR())
    fetch = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "fetch_media")
    resets = [n for n in fetch.body
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Attribute) and t.attr == "media_truncated"
                      for t in n.targets)
              and isinstance(n.value, ast.Constant) and n.value.value is False]
    assert resets, (
        "`media_truncated` n'est pas remis à faux en tête de `fetch_media` : le "
        "premier locataire tronqué marquerait tous les suivants de la même nuit")


def test_the_dag_records_partial_rather_than_success() -> None:
    tree = ast.parse(DAG())
    guarded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "media_truncated" not in ast.dump(node.test):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        guarded.append("'partial'" in body or '"partial"' in body)
    assert guarded, (
        "le DAG Instagram n'examine plus `media_truncated` : une nuit tronquée "
        "s'enregistre de nouveau `success`, et l'historique amputé de l'artiste "
        "devient indiscernable d'un historique complet")
    assert all(guarded), (
        "le DAG voit la troncature mais n'enregistre pas `partial` — or c'est le "
        "seul statut que la tâche d'alerte remonte pour ce cas")


def test_partial_is_a_status_the_alert_actually_reports() -> None:
    """Un statut que personne ne remonte serait un garde muet.

    Lu par l'AST et non par une recherche de chaîne : le dépôt a mesuré quatre gardes
    passés au vert sur leur PROPRE commentaire. Ici c'est la comparaison réelle qu'on
    cherche — `status not in ('failed', 'partial')` — pas ses lettres.
    """
    tree = ast.parse(_read("airflow/dags/alert_monitor.py"))
    reported = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            continue
        for comparator in node.comparators:
            if isinstance(comparator, (ast.Tuple, ast.List, ast.Set)):
                reported |= {e.value for e in comparator.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    assert {"failed", "partial"} <= reported, (
        "la tâche d'alerte ne compare plus un statut à un ensemble contenant "
        "`failed` ET `partial` : enregistrer `partial` ne produirait plus aucun "
        f"signal, et la troncature redeviendrait invisible. Vu : {sorted(reported)}")


# ── La population, DÉRIVÉE — ajoutée le 2026-09-17 ───────────────────────────
#
# Tout ce qui précède nomme Instagram. C'est le site où la classe a été trouvée, et
# c'était le seul gardé — alors que la cause (« une lecture bornée dont la troncature
# ne sort pas du log ») n'a rien d'instagrammien.
#
# Balayé le 2026-09-17 sur `src/collectors/` : **deux** boucles de pagination portent
# un plafond `max_pages`. `instagram_api_collector.fetch_media` (gardée ci-dessus) et
# `soundcloud_api_collector.fetch_tracks`, qui plafonnait à 200 pages en ne le disant
# qu'à `logger.warning` — exactement le défaut du 2026-09-10, vivant depuis, dans un
# collecteur que personne n'avait relu parce que la classe portait le nom de l'autre.
#
# Ce qui suit ne nomme donc plus un fichier : il DÉRIVE sa population de la présence
# d'un plafond de pagination, et un collecteur neuf qui en pose un y entre sans qu'on
# y pense. C'est la règle que ce dépôt a payée cinq fois : la portée d'un garde est le
# défaut, pas la connaissance.
_COLLECTORS = ROOT / "src" / "collectors"
_DAGS = ROOT / "airflow" / "dags"

# Le drapeau porté par l'objet, et le DAG qui le lit. Dérivé du NOM du collecteur pour
# les DAG, ce que la convention du dépôt garantit (`<plateforme>_daily.py`).
_KNOWN_FLAGS = {
    "instagram_api_collector.py": ("media_truncated", "instagram_daily.py"),
    "soundcloud_api_collector.py": ("tracks_truncated", "soundcloud_daily.py"),
}


def _capped_readers(racine: Path | None = None) -> list[tuple[str, str]]:
    """(fichier, fonction) de chaque lecture bornée par un plafond de PAGES.

    La racine est un PARAMÈTRE pour que le garde puisse se soumettre un collecteur
    fabriqué. Sans elle, la seule preuve de non-vacuité disponible était le plancher
    de population (`>= 2`) — qui attrape un détecteur totalement aveugle, mais pas un
    détecteur qui trouve la population et rate la FORME.
    """
    out = []
    for path in sorted((racine or _COLLECTORS).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:                              # pragma: no cover
            continue
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            seg = ast.get_source_segment(src, fn) or ""
            # `max_pages` est la convention du dépôt pour un plafond de pagination.
            # Une borne de tranche (`[:200]`) n'en est pas une : elle tronque un
            # message de log, pas une lecture.
            if "max_pages" in seg:
                out.append((path.name, fn.name))
    return out


def test_the_population_of_capped_readers_is_not_empty() -> None:
    """Anti-vacuité : sans lecture bornée à surveiller, tout ce bloc est vert à vide."""
    readers = _capped_readers()
    assert len(readers) >= 2, (
        f"seulement {len(readers)} lecture(s) bornée(s) trouvée(s) dans "
        "`src/collectors/` — il y en avait 2 le 2026-09-17. Soit la convention "
        "`max_pages` a changé de nom, soit le lecteur AST est cassé ; dans les deux "
        "cas le test d'à côté ne garde plus rien.")


def test_the_detector_sees_the_cap_it_is_written_for(tmp_path: Path) -> None:
    """Non-vacuité : sur un collecteur FABRIQUÉ, le détecteur doit nommer la fonction.

    Le plancher de population ci-dessus rougit sur un détecteur totalement aveugle.
    Il ne dit rien d'un détecteur qui trouverait les deux lecteurs connus et raterait
    le TROISIÈME — celui qu'on ajoutera. C'est cette moitié-là qu'on fabrique.
    """
    faux = tmp_path / "collectors"
    faux.mkdir()
    (faux / "fake_api_collector.py").write_text(
        "class FakeCollector:\n"
        "    def fetch_all(self, max_pages=10):\n"
        "        return []\n"
        "\n"
        "    def fetch_one(self):\n"
        "        return []\n",
        encoding="utf-8",
    )
    vus = _capped_readers(faux)
    assert vus == [("fake_api_collector.py", "fetch_all")], (
        f"le détecteur rend {vus} : il ne reconnaît pas un plafond `max_pages` écrit "
        "noir sur blanc, ou il accuse la fonction voisine qui n'en porte pas. Dans "
        "les deux cas, un lecteur borné ajouté demain passerait sans drapeau de "
        "troncature, et son DAG enregistrerait une lecture partielle comme complète.")


def test_every_capped_reader_carries_its_truncation() -> None:
    """Chaque lecture bornée porte sa troncature sur l'objet, et son DAG la lit."""
    manquants = []
    for fichier, fonction in _capped_readers():
        connu = _KNOWN_FLAGS.get(fichier)
        if connu is None:
            manquants.append(
                f"{fichier}::{fonction} pose un plafond `max_pages` et n'est déclaré "
                "nulle part ici — ajouter son drapeau et son DAG à `_KNOWN_FLAGS`, "
                "après avoir vérifié que les deux existent.")
            continue
        drapeau, dag = connu
        src = (_COLLECTORS / fichier).read_text(encoding="utf-8")
        tree = ast.parse(src)
        cible = next((n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and n.name == fonction), None)
        if cible is None:                                # pragma: no cover
            continue
        pose = [n for n in ast.walk(cible)
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute) and t.attr == drapeau
                        for t in n.targets)]
        vrai = [n for n in pose
                if isinstance(n.value, ast.Constant) and n.value.value is True]
        faux = [n for n in pose
                if isinstance(n.value, ast.Constant) and n.value.value is False]
        if not vrai:
            manquants.append(
                f"{fichier}::{fonction} ne pose jamais `self.{drapeau} = True` : le "
                "plafond ne sort pas du journal du conteneur.")
        if not faux:
            manquants.append(
                f"{fichier}::{fonction} ne remet pas `self.{drapeau}` à faux en tête : "
                "un locataire tronqué marquerait tous les suivants du même processus.")
        # `and url` : sans lui, une collecte finissant PILE au plafond est annoncée
        # tronquée alors qu'elle est complète.
        garde = [n for n in ast.walk(cible)
                 if isinstance(n, ast.If) and isinstance(n.test, ast.BoolOp)
                 and isinstance(n.test.op, ast.And)
                 and any(drapeau in ast.dump(s) for s in n.body)]
        if not garde:
            manquants.append(
                f"{fichier}::{fonction} pose `{drapeau}` sans condition composée : "
                "`page >= max_pages` SEUL annonce tronquée une lecture qui s'est "
                "terminée pile au plafond.")
        dag_src = (_DAGS / dag).read_text(encoding="utf-8")
        if drapeau not in dag_src or "'partial'" not in dag_src:
            manquants.append(
                f"{dag} ne lit pas `{drapeau}` pour enregistrer `partial` : la "
                "troncature est portée par l'objet et personne ne la ramasse.")
    assert not manquants, (
        f"{len(manquants)} maillon(s) manquant(s) dans la chaîne de la troncature.\n"
        "Une lecture bornée est légitime ; l'enregistrer `success` ne l'est pas.\n  "
        + "\n  ".join(manquants))
