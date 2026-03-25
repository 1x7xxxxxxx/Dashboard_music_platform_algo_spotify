"""Quick test for SMTP verification email.

Usage (run from project root):
    python scripts/test_email.py <recipient_email>

Sends a real verification email using the SMTP config in config/config.yaml.
Prints success or the exact SMTP error.
"""
import sys
from pathlib import Path

# Make src/ importable from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.verification_email import send_verification_email

FAKE_TOKEN = "test_token_abc123_do_not_click"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_email.py <recipient_email>")
        sys.exit(1)

    recipient = sys.argv[1]
    print(f"Sending test verification email to: {recipient}")

    ok = send_verification_email(
        to_email=recipient,
        username="test_user",
        token=FAKE_TOKEN,
    )

    if ok:
        print("✅ Email sent successfully. Check your inbox.")
    else:
        print("❌ Failed — check SMTP config in config/config.yaml or run with logging:")
        print("   python -c \"import logging; logging.basicConfig(level='DEBUG')\" && python scripts/test_email.py <email>")
