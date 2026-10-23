"""R646 — a PDF to validate comes out twice, numbered, A_VALIDER, on the Desktop; validated, it leaves.

Type: Guard
Uses: tools/dev/validation_pdf.py, tools/dev/charts_dossier/main.py (decisions_html,
      publish_for_validation)
Depends on: nothing outside tmp_path — the Desktop and the revision state are redirected

Baseline REQ-PARC-133 (owner's review « Master puis parc », 2026-10-22): the charts dossier, when it
waits on the owner, is also published as A_VALIDER_dossier-graphiques_revNN_<date>.pdf in its folder
and on the Desktop; the revision moves only when the sources move; the old copy leaves. Ported from
the master's tools/dev/test_validation_pdf.py (its decision_pdf case has no counterpart here).
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
import validation_pdf as vp  # noqa: E402

_D = ROOT / "tools" / "dev" / "charts_dossier"
_spec = importlib.util.spec_from_file_location("charts_dossier_main", _D / "main.py")
dossier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dossier)

TODAY = datetime.date.today().isoformat()
OK = "<h1>x</h1><h2 data-owner-first='1'>1. À valider</h2>"


def _dirs(tmp_path):
    folder, desk = tmp_path / "repo", tmp_path / "Desktop"
    folder.mkdir()
    desk.mkdir()
    return folder, desk, tmp_path / "state.json"


def test_both_copies_are_written_and_the_revision_moves_with_the_key_only(tmp_path):
    folder, desk, st = _dirs(tmp_path)
    vp.publish(b"%PDF-1", folder, "D", "review v1", desk, st, html=OK)
    assert (folder / f"A_VALIDER_D_rev01_{TODAY}.pdf").read_bytes() == b"%PDF-1"
    assert (desk / f"A_VALIDER_D_rev01_{TODAY}.pdf").exists()
    vp.publish(b"%PDF-1bis", folder, "D", "review v1", desk, st, html=OK)   # re-captured, same sources
    assert (desk / f"A_VALIDER_D_rev01_{TODAY}.pdf").read_bytes() == b"%PDF-1bis"
    vp.publish(b"%PDF-2", folder, "D", "review v2", desk, st, html=OK)
    assert sorted(p.name for p in desk.iterdir()) == [f"A_VALIDER_D_rev02_{TODAY}.pdf"]   # rev01 removed
    assert sorted(p.name for p in folder.iterdir()) == [f"A_VALIDER_D_rev02_{TODAY}.pdf"]


def test_a_file_it_did_not_write_is_never_removed(tmp_path):
    folder, desk, st = _dirs(tmp_path)
    (desk / "mine.pdf").write_bytes(b"x")
    vp.publish(b"a", folder, "D", "k1", desk, st, html=OK)
    vp.publish(b"b", folder, "D", "k2", desk, st, html=OK)
    assert (desk / "mine.pdf").exists()


def test_validate_renames_in_the_folder_and_clears_the_desktop_until_the_sources_change(tmp_path, monkeypatch):
    folder, desk, st = _dirs(tmp_path)
    monkeypatch.setattr(vp, "DESKTOP", desk)
    vp.publish(b"a", folder, "D", "k1", desk, st, html=OK)
    assert vp.pending(st)
    vp.validate("D", st)
    assert [p.name for p in folder.iterdir()] == [f"VALIDE_D_rev01_{TODAY}.pdf"]
    assert list(desk.iterdir()) == [] and vp.pending(st) == []
    assert "déjà validée" in vp.publish(b"a", folder, "D", "k1", desk, st, html=OK)
    assert list(desk.iterdir()) == []
    vp.publish(b"b", folder, "D", "k2", desk, st, html=OK)
    assert [p.name for p in desk.iterdir()] == [f"A_VALIDER_D_rev02_{TODAY}.pdf"]


def test_a_locked_desktop_copy_is_reported_not_raised(tmp_path, monkeypatch):
    folder, desk, st = _dirs(tmp_path)
    real = Path.write_bytes

    def locked(self, data):
        if self.parent == desk:
            raise PermissionError("in use")
        return real(self, data)
    monkeypatch.setattr(Path, "write_bytes", locked)
    out = vp.publish(b"a", folder, "M", "k", desk, st, html=OK)
    assert "verrouillé" in out and (folder / f"A_VALIDER_M_rev01_{TODAY}.pdf").exists()


def test_the_name_leads_with_its_status_then_the_revision_and_its_day():
    assert vp.name("dossier-graphiques", 20, day="2026-10-22") == "A_VALIDER_dossier-graphiques_rev20_2026-10-22.pdf"
    assert vp.name("D", 3, vp.DONE, "2026-10-22") == "VALIDE_D_rev03_2026-10-22.pdf"


def test_a_document_that_does_not_open_on_the_owners_decisions_is_refused(tmp_path):
    folder, desk, st = _dirs(tmp_path)
    for bad in ("<h1>x</h1><h2>Contexte</h2><h2 data-owner-first='1'>À valider</h2>", "<h1>x</h1><p>rien</p>"):
        with pytest.raises(ValueError, match="REQ-GOV-23"):
            vp.publish(b"a", folder, "D", "k", desk, st, html=bad)
    assert not list(folder.iterdir()) and not list(desk.iterdir()) and not st.exists()
    assert vp.owner_first_error(OK) is None


def _decisions(place_of, monkeypatch, tmp_path):
    import questions
    monkeypatch.setattr(questions, "SHARED_REVIEWED", {})
    review = {k: {"q": f"question {k}"} for k in place_of}
    no_of = {k: i + 1 for i, k in enumerate(place_of)}
    return dossier.decisions_html(review, no_of, place_of, tmp_path)


def test_the_dossier_opens_on_what_waits_on_the_owner_and_mine_comes_after(tmp_path, monkeypatch):
    html = _decisions({"a": "corriger", "b": "revalider"}, monkeypatch, tmp_path)
    assert vp.owner_first_error("<h1>x</h1>" + html) is None
    assert html.index("À valider") < html.index("Encore à faire de mon côté")


def test_the_dossier_is_published_twice_only_when_something_waits_on_the_owner(tmp_path, monkeypatch):
    folder, desk, st = _dirs(tmp_path)
    pdf = folder / "dossier-graphiques.pdf"
    pdf.write_bytes(b"%PDF-d")
    waits = "<h1>x</h1>" + _decisions({"a": "a-trancher"}, monkeypatch, tmp_path)
    assert dossier.publish_for_validation(pdf, waits, folder, desk, st)
    assert (desk / f"A_VALIDER_dossier-graphiques_rev01_{TODAY}.pdf").read_bytes() == b"%PDF-d"
    assert (folder / f"A_VALIDER_dossier-graphiques_rev01_{TODAY}.pdf").exists()

    folder2, desk2, st2 = tmp_path / "f2", tmp_path / "d2", tmp_path / "s2.json"
    folder2.mkdir()
    desk2.mkdir()
    mine_only = "<h1>x</h1>" + _decisions({"a": "corriger"}, monkeypatch, tmp_path)
    assert dossier.publish_for_validation(pdf, mine_only, folder2, desk2, st2) == ""
    assert not list(desk2.iterdir()) and not list(folder2.iterdir()) and not st2.exists()
