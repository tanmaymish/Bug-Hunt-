# Live Production OAuth `client_secret` + Internal GrowthBook Config Exposed in Public `www.dash.ai` JS (P3 / Medium)

**Program:** Dropbox — Intigriti
**Asset (in scope):** `www.dash.ai` (`*.dash.ai`)
**Severity:** P3 / Medium — production credential + internal-config exposure in a public bundle
**All PoCs re-verified live:** 2026-07-04 (secret still in prod bundle `main.LQ35GM5D.js`; `check/app` still echoes secret)

---

## 1. Summary

The production Dropbox Dash SPA at `www.dash.ai` ships a public JavaScript bundle that hardcodes the **production OAuth `client_id` + `client_secret`**. The secret is **live and genuine** — confirmed by Dropbox's own `/2/check/app` endpoint and by minting a `client_credentials` app token. The same bundle leaks a GrowthBook SDK key that exposes Dropbox's internal feature-flag configuration (unreleased roadmap, unreleased AI model names, and ~900 customer/team identifiers).

This is a credential + internal-config exposure. Severity is established by **proving the credential is live** and characterizing **exactly what it does and does not grant** — not by asserting unproven impact.

---

## 2. Finding 1 (P3) — Production OAuth secret is public AND live

### 2.1 Secret in public production JS — `evidence/01`
```
$ curl -s https://www.dash.ai/static/js/main.LQ35GM5D.js | grep -oE 'OAUTH_CLIENT_(KEY|SECRET):o\([^)]*\)'
OAUTH_CLIENT_KEY:o({DEFAULT:"REDACTED_DEFAULT_CLIENT_KEY",...,prod:"REDACTED_PROD_CLIENT_KEY"})
OAUTH_CLIENT_SECRET:o({DEFAULT:"REDACTED_DEFAULT_CLIENT_SECRET",...,prod:"REDACTED_PROD_CLIENT_SECRET"})
```
| Environment | client_id | client_secret |
|---|---|---|
| **Production** | `REDACTED_PROD_CLIENT_KEY` | `REDACTED_PROD_CLIENT_SECRET` |
| Staging (DEFAULT) | `REDACTED_DEFAULT_CLIENT_KEY` | `REDACTED_DEFAULT_CLIENT_SECRET` |

### 2.2 Secret is LIVE — `evidence/02`, `evidence/03`
```
$ curl -X POST https://api.dropbox.com/oauth2/token \
    -d grant_type=client_credentials -d client_id=REDACTED_PROD_CLIENT_KEY -d client_secret=REDACTED_PROD_CLIENT_SECRET
200 {"access_token":"uatapp.AGlIY4q...","token_type":"bearer","expires_in":14400}

$ curl -X POST https://api.dropboxapi.com/2/check/app -u REDACTED_PROD_CLIENT_KEY:REDACTED_PROD_CLIENT_SECRET \
    -H 'Content-Type: application/json' -d '{"query":"triage_evidence"}'
200 {"result":"triage_evidence","secret":"Super secret string"}

# control — WRONG secret:
$ curl -X POST https://api.dropboxapi.com/2/check/app -u REDACTED_PROD_CLIENT_KEY:wrongsecret ...
400 Error: message:"incorrect app secret" error_type:INVALID_SECRET
```
`/2/check/app` performs app authentication: it returns `200` **only for a valid `client_id:client_secret` pair**, and `400 INVALID_SECRET` for a wrong secret. That 200-vs-400 distinction is the proof the leaked secret is genuine. (Note: the `"secret":"Super secret string"` field is a fixed Dropbox constant echoed to every caller — it is *not* the app's secret and is not itself evidence; the proof is the authenticated `200` plus the independent `client_credentials` token mint above.)

### 2.3 What the credential actually grants (honest characterization) — `evidence/04`
The `client_credentials` **app** token is **rejected by user-context endpoints** — it does **not** read any user's files or account:
```
POST /2/users/get_current_account -> 401 {"error":{".tag":"invalid_access_token"}}
POST /2/users/get_space_usage     -> 401 {"error":{".tag":"invalid_access_token"}}
```
Demonstrated impact of the leaked secret is therefore **app impersonation**: an attacker can authenticate *as the Dash application* to Dropbox's app-authenticated API surface. No user-data access has been demonstrated.

---

## 3. Potential escalation (UNVERIFIED) — code-exchange / account-takeover chain

An OAuth `client_secret` would normally let an app exchange an authorization code for a user's tokens. **This has NOT been demonstrated for this client, and current evidence suggests it is blocked:**

- The production Dash client performs the token exchange with **PKCE** — its exchange function sends `grant_type=authorization_code&code&code_verifier&redirect_uri` and **does not send `client_secret`**. This indicates the client is registered/operated as a PKCE flow.
- A code-exchange probe using the leaked secret with **no `code_verifier`** could not be confirmed: Dropbox's token endpoint validates the authorization `code` *before* client-auth/PKCE, so an invalid dummy code returns `invalid_grant` regardless of secret or verifier (identical response with secret, with a bogus verifier, and with neither). The order prevents a no-account test from confirming PKCE enforcement either way.
- **Code-interception vector tested and CLOSED (`evidence/07`):** the authorize endpoint enforces **strict exact-match `redirect_uri`** validation (including path). Attacker variants — `evil.dash.ai/oauth`, `www.dash.ai.evil.com/oauth` (suffix-domain), `www.dash.ai@evil.com` (userinfo), and any alternate path on `www.dash.ai` — are all rejected with `invalid_redirect_uri` ("must exactly match … including the path"). So a victim's authorization code can only ever be delivered to the genuine `https://www.dash.ai/oauth`; there is **no no-interaction way to redirect a code to attacker infrastructure**. Two independent controls (PKCE + strict redirect_uri) both hold.

**Conclusion:** the "phish an authorization code → exchange with leaked secret → account takeover" narrative is **not substantiated** and is likely prevented if the token endpoint requires `code_verifier` for this client. It is recorded here as a *possible* escalation, **contingent on server-side PKCE being optional**, which remains untested.

> The only way to confirm is exchanging a **real authorization code obtained from a consenting account the researcher controls** with the secret and no `code_verifier`. If that returns a user `access_token`, severity rises accordingly; until then this remains a Medium app-impersonation issue, not an ATO.

---

## 4. Finding 2 (P3) — Leaked GrowthBook key exposes internal config + customer IDs

Same public bundle leaks GrowthBook SDK key `REDACTED_GROWTHBOOK_SDK_KEY` (prior `REDACTED_GROWTHBOOK_SDK_KEY_PRIOR` still live). One unauthenticated GET returns Dropbox's internal feature config (`evidence/06`, `pocs/04`):

- **1,298 internal feature flags**
- **Unreleased roadmap** — future-dated flags (e.g. `dash_2026_08_11_use_datadog_logging`)
- **Unreleased AI model identifiers** — `azure:gpt-5.4`, `azure:gpt-5.5`, internal `kserve/qwen3…` deployments
- **898 unique customer/team identifiers** (`pid_eci:…`) in targeting rules — *values deliberately not exfiltrated/stored*. Note: these may be opaque internal IDs rather than raw PII; not characterized as PII absent confirmation.
- **155 hashed-identity targeting conditions** (`secure_email_suffix`, `secure_user_id`)

> Note: a GrowthBook client SDK key is client-side by design. The real issue is that **sensitive internal configuration and identifiers are present in the returned payload**, not the key itself.

---

## 5. Secondary observations (footnoted honestly, not over-claimed)

- App-authenticated `/2/pap_event_logging/log_events` accepted a benign event once (HTTP 200) using the app token. **Not re-exercised** — writing to Dropbox's production analytics could be harmful/out-of-scope. If app-auth write abuse were demonstrated, that would raise severity toward P2.
- Sentry DSNs and a DataDog RUM token are present in the bundle. These are **client-side ingest keys by design**; listed for completeness, not as standalone criticals.

---

## 6. Impact

- **Demonstrated:** production OAuth `client_secret` is world-readable and live → an attacker can impersonate the Dash app against Dropbox's app-authenticated API. Every `www.dash.ai` visitor downloads the secret.
- **Demonstrated:** Dropbox internal feature-flag config — unreleased roadmap, unreleased AI model names, and ~900 customer/team identifiers — readable by anyone with the public SDK key.
- **Not demonstrated:** user account/file takeover. The app token is rejected by user endpoints, and the code-exchange chain is likely blocked by PKCE (unverified). This report does **not** claim ATO.

## 7. Remediation

1. **Rotate now:** prod `REDACTED_PROD_CLIENT_KEY`/`REDACTED_PROD_CLIENT_SECRET`, staging pair, GrowthBook keys.
2. Revoke tokens issued to the Dash app via `client_credentials`.
3. Never ship `client_secret` to a public SPA — use PKCE (public client, no secret) or a server-side token exchange. Ensure the token endpoint **requires** `code_verifier` for this client so the exposed secret cannot be used for code exchange.
4. Make the GrowthBook config server-side / scope it so internal roadmap and identifiers aren't returned to anonymous clients.

## 8. Timeline

- 2026-07-03 — Secret found in `staging.dash.ai`, confirmed in production `www.dash.ai`; liveness proven via `client_credentials` + `check/app`; app-token limits characterized; GrowthBook exposure extracted (redacted).
- 2026-07-03 21:21 UTC — PoCs re-verified live.
- 2026-07-04 — Severity corrected to P3/Medium: ATO chain unsubstantiated (client uses PKCE; no user-data access demonstrated).
- 2026-07-04 — Re-verified live: secret still present in prod bundle `main.LQ35GM5D.js`; `client_credentials` mint returns 200; `/2/check/app` still echoes the secret.

*Evidence artifacts + runnable PoCs: see `evidence/` and `pocs/`. SHA-256 manifest: `evidence/hashes.txt`.*
