"""Une rotation de roadmap touche TROIS surfaces, et l'outil les connait toutes.

Type: Sub
Uses: subprocess, pathlib
Triggers: pytest
Depends on: tools/dev/roadmap.py, .claude/commands/roadmap-done.md
Persists in: —

Error class `a-procedure-that-omits-a-surface-it-must-touch`.

Les deux frictions MESUREES le 2026-09-17
------------------------------------------
La rotation etait une procedure en PROSE, correcte et detaillee, executee a la main. Elle
a laisse passer deux erreurs dans une seule seance, parce qu'elle ne nomme ni l'une ni
l'autre :

  1. **L'ancre de reprise** `<!-- reprise: open=… -->` est une TROISIEME surface, a cote
     des deux tables d'index. Oubliee -> `test_the_anchor_matches_the_open_index` rouge.
  2. **Le format d'archive.** Le test de conservation ne reconnait un identifiant que
     sous deux formes — ligne de tableau ou case cochee. Une entree ecrite en TITRE
     (`## R128 — …`) lui est invisible, et la tache est declaree disparue des deux
     fichiers. Arrive sur R128 et R129 le meme jour.

Les tests ont rattrape les deux, APRES coup. `tools/dev/roadmap.py` refuse AVANT.

Ce que ce garde tient
---------------------
Que l'outil connaisse les trois surfaces, et qu'il REFUSE une fermeture dont l'entree
d'archive n'est pas dans une forme reconnue — plutot que de la faire et de laisser le
test de conservation echouer plus tard.

Mutation record — 2026-09-17, deux mutations EXECUTEES et vues rouges :
  1. la verification du format d'archive retiree de `cmd_close` -> rouge ;
  2. `_set_anchor` neutralise (l'ancre n'est plus recalee) -> rouge.
0 apres remise en etat.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "dev" / "roadmap.py"


def _fixture(tmp_path: pathlib.Path, archive_body: str) -> pathlib.Path:
    """Un faux dépôt avec les deux fichiers, à la structure minimale que l'outil lit."""
    d = tmp_path / ".claude" / "dev-docs" / "roadmap"
    d.mkdir(parents=True)
    (d / "checklist.md").write_text(
        "# actif\n\n"
        "| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n"
        "| R900 | une tâche | P3 | une commande |\n"
        "| R901 | une autre | P4 | une autre commande |\n\n"
        "<!-- reprise: open=R900, R901 -->\n", encoding="utf-8")
    (d / "archive.md").write_text(archive_body, encoding="utf-8")
    return tmp_path


def _run_in(tmp_path: pathlib.Path, *args) -> subprocess.CompletedProcess:
    """Lance le VRAI outil, avec sa racine deplacee par `ROADMAP_ROOT`.

    ⚠️ Une premiere version copiait `roadmap.py` dans une arborescence temporaire pour
    que son `parents[2]` tombe au bon endroit. Elle LISAIT donc du source Python en
    texte, ce que `tests/test_a_guard_reads_structure_not_text.py` refuse — et il l'a
    prise, a juste titre. La variable d'environnement retire le besoin, et avec lui le
    piege de la copie vers un chemin qui casse la resolution par `__file__`.
    """
    env = {**os.environ, "ROADMAP_ROOT": str(tmp_path)}
    return subprocess.run([sys.executable, str(_TOOL), *args],
                          capture_output=True, text=True, check=False, env=env)


def test_closing_refuses_when_the_archive_entry_is_only_a_heading(tmp_path):
    """Le defaut exact du 2026-09-17 : une entree en titre est invisible au test."""
    repo = _fixture(tmp_path, "# archive\n\n## R900 — livrée\n\nDu texte.\n")
    r = _run_in(repo, "close", "R900")
    assert r.returncode != 0, (
        "L'outil a ferme R900 alors que son entree d'archive n'est qu'un TITRE. "
        "`test_no_brick_id_vanishes_from_both_files` la declarera disparue des deux "
        "fichiers — c'est exactement ce qui est arrive a R128 et R129."
    )
    assert "- [x] **R900" in r.stderr, (
        "Le refus ne montre pas la forme ATTENDUE. Un refus qui ne dit pas quoi ecrire "
        "oblige a aller lire le test, c'est-a-dire a refaire la decouverte."
    )


def test_closing_accepts_a_ticked_line(tmp_path):
    repo = _fixture(tmp_path, "# archive\n\n- [x] **R900 — livrée.**\n")
    r = _run_in(repo, "close", "R900")
    assert r.returncode == 0, r.stderr
    text = (repo / ".claude/dev-docs/roadmap/checklist.md").read_text(encoding="utf-8")
    assert "| R900 |" not in text, "la ligne d'index n'a pas été retirée"
    assert "<!-- reprise: open=R901 -->" in text, (
        "L'ancre n'a pas ete recalee apres la fermeture. C'est la TROISIEME surface, "
        "celle que la procedure en prose ne nomme pas — et celle qui a ete oubliee."
    )


def test_sync_realigns_the_anchor_with_both_index_tables(tmp_path):
    repo = _fixture(tmp_path, "# archive\n")
    cl = repo / ".claude/dev-docs/roadmap/checklist.md"
    cl.write_text(cl.read_text(encoding="utf-8").replace(
        "<!-- reprise: open=R900, R901 -->", "<!-- reprise: open=R900 -->"),
        encoding="utf-8")
    r = _run_in(repo, "sync")
    assert r.returncode == 0, r.stderr
    assert "<!-- reprise: open=R900, R901 -->" in cl.read_text(encoding="utf-8")


def test_the_prose_procedure_now_names_the_two_things_it_omitted():
    """La prose et l'outil doivent dire la meme chose — sinon on relit la mauvaise."""
    doc = (_ROOT / ".claude" / "commands" / "roadmap-done.md").read_text(encoding="utf-8")
    assert "reprise: open=" in doc, (
        "`/roadmap-done` ne nomme toujours pas l'ancre de reprise. C'est la surface "
        "oubliee le 2026-09-17 ; la laisser hors de la procedure garantit la recidive."
    )
    assert "roadmap-close" in doc, (
        "`/roadmap-done` ne renvoie pas vers `make roadmap-close`, qui fait le geste "
        "mecanique et refuse AVANT plutot que d'echouer apres."
    )


# ── R199 (2026-09-26) : LE chemin de rotation ÉCRIT l'archive, preuve de livraison exigée ──

def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = _fixture(tmp_path, "# archive\n\nEn-tête.\n\n---\n\n## ✅ R1 — ancienne\n\n- [x] **R1**\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _commit(repo: pathlib.Path, rel: str, message: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(message, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--no-verify", "-m", message], check=True)


def test_a_roadmap_only_commit_is_not_a_delivery(tmp_path):
    """« Roadmap : R900 inscrite » cite l'id sans rien livrer : la fermeture est refusée."""
    repo = _git_repo(tmp_path)
    _commit(repo, ".claude/dev-docs/roadmap/checklist.md",
            (repo / ".claude/dev-docs/roadmap/checklist.md").read_text() + "\nRoadmap : R900 inscrite\n")
    r = _run_in(repo, "close", "R900")
    assert r.returncode != 0 and "LIVRE" in r.stderr, r.stderr
    assert "- [x] **R900" in r.stderr


def test_closing_writes_the_archive_entry_at_the_top_then_refuses_twice(tmp_path):
    repo = _git_repo(tmp_path)
    _commit(repo, "tools/x.py", "R900 : la livraison")
    r = _run_in(repo, "close", "R900", "--note", "Déployée.")
    assert r.returncode == 0, r.stderr
    archive = (repo / ".claude/dev-docs/roadmap/archive.md").read_text(encoding="utf-8")
    head, _, rest = archive.partition("\n---\n")
    assert rest.lstrip().startswith("## ✅ R900 — une tâche"), "the entry is not at the TOP"
    assert "- [x] **R900 — une tâche** (P3)" in rest and "Déployée." in rest
    assert "R900 : la livraison" in rest, "the delivering commit is not named"
    assert rest.index("R900") < rest.index("## ✅ R1"), "older entries must stay below"
    cl = (repo / ".claude/dev-docs/roadmap/checklist.md").read_text(encoding="utf-8")
    assert "| R900 |" not in cl and "<!-- reprise: open=R901 -->" in cl
    again = _run_in(repo, "close", "R900")
    assert again.returncode != 0 and "pas ouverte" in again.stderr, (
        "a second close must fail — else it would write a second archive entry")
    assert archive.count("- [x] **R900") == 1
