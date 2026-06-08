"""Tests for the onboarding-guide HTML/PDF renderer + welcome-email attachment.

Pure-string + behaviour assertions — no WeasyPrint or live SMTP needed.
"""
from pathlib import Path

from src.dashboard.guides import guide_pdf
from src.utils import verification_email


def test_img_tag_missing_returns_placeholder(monkeypatch):
    monkeypatch.setattr(guide_pdf, "screenshot_path", lambda f: Path("/no/such/file.png"))
    out = guide_pdf._img_tag("s4a_step1_login.png", "cap")
    assert "capture à venir" in out
    assert "data:image" not in out


def test_img_tag_present_embeds_base64(monkeypatch, tmp_path):
    png = tmp_path / "shot.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    monkeypatch.setattr(guide_pdf, "screenshot_path", lambda f: png)
    out = guide_pdf._img_tag("whatever.png", "My caption")
    assert "data:image/png;base64," in out
    assert "My caption" in out


def test_build_guide_html_lists_all_platforms():
    html = guide_pdf.build_guide_html()
    for title in ("Spotify for Artists", "Apple Music for Artists", "iMusician"):
        assert title in html
    # expected-CSV tables present
    assert "Nom attendu" in html


def test_attach_pdf_missing_file_is_noop():
    from email.mime.multipart import MIMEMultipart
    msg = MIMEMultipart("mixed")
    assert verification_email._attach_pdf(msg, "/no/such/guide.pdf") is False
    assert msg.get_payload() == []  # nothing attached


def test_send_html_unconfigured_smtp_returns_false(monkeypatch):
    monkeypatch.setattr(verification_email, "_smtp_config", lambda: {})
    assert verification_email._send_html("a@b.c", "subj", "<p>hi</p>") is False


def test_send_welcome_email_non_raising_without_smtp(monkeypatch):
    monkeypatch.setattr(verification_email, "_smtp_config", lambda: {})
    # Must not raise even though it resolves the guide PDF path internally.
    assert verification_email.send_welcome_email("a@b.c", "tester") is False
