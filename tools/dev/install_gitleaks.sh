#!/usr/bin/env bash
# Install the pinned gitleaks binary, checksum-verified.
#
#   tools/dev/install_gitleaks.sh [bin-dir]      (default: ~/.local/bin)
#
# Type: Utility
# Uses: curl, sha256sum, tar
# Triggers: `make hooks-install` (local pre-commit), .github/workflows/ci.yml job `secrets`
# Persists in: <bin-dir>/gitleaks
#
# One version for the commit hook and the CI job: the nightly action embeds 8.24.3, which
# silently ignored `[[allowlists]]` (2026-09-25) — two scanners of two versions give two
# verdicts. The checksum is pinned here, not fetched next to the tarball it verifies.
set -euo pipefail
VERSION=8.28.0
SHA256=a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb
dir="${1:-$HOME/.local/bin}"
if [ -x "$dir/gitleaks" ] && [ "$("$dir/gitleaks" version 2>/dev/null)" = "$VERSION" ]; then
    echo "✅ gitleaks $VERSION déjà installé ($dir)"; exit 0
fi
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/g.tgz" \
    "https://github.com/gitleaks/gitleaks/releases/download/v$VERSION/gitleaks_${VERSION}_linux_x64.tar.gz"
got="$(sha256sum "$tmp/g.tgz" | cut -d' ' -f1)"
[ "$got" = "$SHA256" ] || { echo "❌ gitleaks : somme de contrôle fausse — rien n'est installé"; exit 1; }
tar -xzf "$tmp/g.tgz" -C "$tmp" gitleaks
mkdir -p "$dir"
install -m 0755 "$tmp/gitleaks" "$dir/gitleaks"
echo "✅ gitleaks $VERSION installé dans $dir"
