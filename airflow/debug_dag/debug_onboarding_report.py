"""Debug script — exercise onboarding_report locally without Airflow.

Type: Sub
Uses: src.dashboard.utils.pdf_exporter, src.database.postgres_handler
Persists in: /tmp/onboarding_<artist>.pdf (dry-run); nothing else

Default = DRY RUN: lists eligible users (verified, active, non-admin, report pending,
S4A data present) and writes each built PDF to /tmp — sends NO email, stamps NOTHING.
Pass --send to actually email via EmailAlert + stamp onboarding_report_sent_at.

Usage:
    python airflow/debug_dag/debug_onboarding_report.py            # dry run
    python airflow/debug_dag/debug_onboarding_report.py --send     # real send
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
from src.dashboard.utils.pdf_exporter import generate_pdf, ALL_SECTIONS


def _slug(s: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in (s or "").strip())
    return ("_".join(p for p in out.split("_") if p) or "artiste")[:40]


def main(send: bool = False):
    cfg = config_loader.load()['database']
    db = PostgresHandler(host=cfg['host'], port=cfg['port'], database=cfg['database'],
                         user=cfg['user'], password=cfg['password'])
    pending = db.fetch_query(
        """
        SELECT u.id, u.email, u.username, u.artist_id, a.name
        FROM saas_users u JOIN saas_artists a ON a.id = u.artist_id
        WHERE u.email_verified = TRUE AND u.active = TRUE AND u.role <> 'admin'
          AND u.artist_id IS NOT NULL AND u.onboarding_report_sent_at IS NULL
        """
    )
    print(f"Eligible (report pending): {len(pending)}")
    for uid, email, username, artist_id, artist_name in pending:
        has_data = bool(db.fetch_query(
            "SELECT 1 FROM s4a_song_timeline WHERE artist_id = %s "
            "AND song NOT ILIKE '%%1x7xxxxxxx%%' LIMIT 1", (artist_id,)))
        print(f"  - {username} <{email}> · artist={artist_name} (id={artist_id}) · "
              f"S4A data={has_data}")
        if not has_data:
            continue
        pdf = generate_pdf(db, artist_id=artist_id, artist_name=artist_name,
                           from_date=date(2015, 1, 1), to_date=date.today(),
                           sections={k: True for k in ALL_SECTIONS})
        out = Path("/tmp") / f"onboarding_{_slug(artist_name)}.pdf"
        out.write_bytes(pdf)
        print(f"    PDF built ({len(pdf):,} bytes) → {out}")
        if send:
            from src.utils.email_alerts import EmailAlert
            ok = EmailAlert().send_email(
                email, f"📊 Votre premier rapport streaMLytics — {artist_name}",
                f"<p>Bonjour {username}, votre rapport pour {artist_name} est en pièce jointe.</p>",
                attachment_bytes=pdf, attachment_name=out.name)
            print(f"    Email sent: {ok}")
            if ok:
                db.execute_query(
                    "UPDATE saas_users SET onboarding_report_sent_at = now() WHERE id = %s",
                    (uid,))
                print("    Stamped onboarding_report_sent_at.")
    db.close()


if __name__ == "__main__":
    main(send="--send" in sys.argv)
