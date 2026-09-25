#!/usr/bin/env bash
# Pre-commit hook: refuse a commit whose STAGED changes carry a secret.
#
# Type: Hook
# Uses: gitleaks (pinned by tools/dev/install_gitleaks.sh), .gitleaks.toml
# Triggers: .pre-commit-config.yaml, hook `gitleaks-staged`
# Persists in: nothing
#
# detect-secrets (the hook before this one) judges by ENTROPY; gitleaks knows provider
# FORMATS (GCP keys, Stripe, Slack…). The 12 secrets of the public history (2025-10) were
# committed before either existed here. A missing binary FAILS the commit and names the
# fix — a secret scanner that skips when absent is the defect it guards against.
set -uo pipefail
g="$(command -v gitleaks || echo "$HOME/.local/bin/gitleaks")"
[ -x "$g" ] || { echo "❌ gitleaks absent — run: make hooks-install"; exit 1; }
exec "$g" git --pre-commit --staged --redact --no-banner -v --config .gitleaks.toml
