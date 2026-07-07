# Case 02 — The Scope That Took the Wrong Door: Shopify's Device-Flow SSO Bypass

**Target:** `accounts.shopify.com` (HackerOne, Core) · **Class:** Missing Authentication
for Critical Function (CWE-306) · **Severity:** High · **CVSS 3.1:** 8.7
(`AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:N`) · **Status:** reported

> **The one-line lesson:** an OAuth authorization server can expose one privileged scope
> through several grant types. If one grant type routes that scope through a hard gate and
> another doesn't, the soft path *is* the vulnerability. Test every grant type, not just
> the one in the docs.

---

## Background: `employee` is a real, gated scope

Shopify's account server supports a privileged `employee` OAuth scope — a genuine
authentication pathway into internal systems. OIDC discovery confirms it:

```
GET /.well-known/openid-configuration
"scopes_supported": [ ..., "employee", ... ]
```

When you request `scope=employee` through the **standard** `authorization_code` flow, the
server does the right thing: it recognizes the privileged scope and redirects you to a
dedicated internal SSO portal.

```
GET /oauth/authorize?...&scope=employee
→ HTTP 302  Location: https://accounts.shopify.com/login/employee?RelayState=...
```

`/login/employee` requires Shopify employee credentials (Okta/SAML). An external attacker
cannot complete it. **This is the intended access control.**

## The observation that broke it

The same authorization server exposes a **second** grant type — the OAuth 2.0 Device
Authorization Grant — and it is **not** in the discovery document
(`device_authorization_endpoint: null`). Undocumented surface tends to get fewer reviews.
So: request the same privileged scope through *that* door.

```
POST /oauth/device_authorization
client_id=<public Shopify CLI client>&scope=employee

→ HTTP 200
{
  "verification_uri_complete":
    "https://accounts.shopify.com/activate-with-code?device_code[user_code]=SFHQ-ZTPM",
  ...
}
```

No `302` to `/login/employee`. The device flow accepts `scope=employee` and hands back a
**standard merchant activation link** on `accounts.shopify.com` — the employee SSO gate is
never invoked.

### Same scope, two doors

```mermaid
flowchart TD
    S(["Request scope=employee"]):::neutral

    S -->|"authorization_code flow"| AZ["GET /oauth/authorize"]:::neutral
    S -->|"device_authorization flow"| DV["POST /oauth/device_authorization"]:::neutral

    AZ --> G{{"Recognizes privileged scope"}}:::good
    G --> SSO["302 → /login/employee<br/>🔒 Okta / SAML employee SSO<br/>external attacker STOPPED"]:::good

    DV --> B{{"Scope check missing"}}:::bad
    B --> ACT["200 → shopify.com/activate<br/>🪤 normal merchant activation link<br/>SSO gate NEVER invoked"]:::bad

    classDef good fill:#0b3d1a,stroke:#2ecc71,stroke-width:2px,color:#eafff0;
    classDef bad fill:#4d0b0b,stroke:#e74c3c,stroke-width:2px,color:#ffecec;
    classDef neutral fill:#16233f,stroke:#5dade2,stroke-width:1px,color:#eaf2ff;
```

The filtering logic even looks **inverted**: a mundane OIDC scope like `email` is *rejected*
(`400`), while the privileged `employee` scope passes through.

```
employee         → ACCEPTED (user_code issued)   ← bug
employee openid  → ACCEPTED                        ← bug
openid           → ACCEPTED (expected)
email            → REJECTED (400)
```

## Why the impact is real

The device flow's `verification_uri_complete` is a **pre-filled magic link** entirely on
`accounts.shopify.com` — no spoofed domain, no code for the victim to type. An attacker:

1. Mints a `scope=employee` device code (no account needed).
2. Sends a Shopify employee the genuine `accounts.shopify.com/activate-with-code?...` link
   ("Re-authorize your Shopify CLI").
3. Polls `/oauth/token`; the moment the victim clicks **Authorize**, the poll returns an
   `employee`-scoped access token — using the victim's *existing* session, so 2FA and
   password never re-enter the picture.

And there's no rate limiting on `/oauth/device_authorization`, so campaigns scale.

### The attack, end to end

```mermaid
sequenceDiagram
    autonumber
    actor Atk as 😈 Attacker · no account
    participant SH as accounts.shopify.com
    actor Emp as 👤 Shopify employee

    Atk->>SH: POST /oauth/device_authorization (scope=employee)
    SH-->>Atk: 200 · user_code + verification_uri_complete
    Note over Atk,SH: pre-filled magic link, 100% on accounts.shopify.com
    Atk->>Emp: 🎣 "Re-authorize your Shopify CLI" + genuine link
    Emp->>SH: clicks link (real Shopify domain, existing session)
    Emp->>SH: clicks "Authorize" ✅
    loop every 5s
        Atk->>SH: POST /oauth/token (device_code)
    end
    SH-->>Atk: 🔑 employee-scoped access_token
    Note over Atk: 2FA & password never re-entered
```

## Honest boundary

The report is careful about what it does **not** prove: it did not access an employee
account or inspect the resulting token's internal claims — that would require a real
Shopify employee account, outside authorized scope. The disclosed bug is the
**authentication-pathway bypass**; Shopify can verify the downstream token internally. That
line — "here is the broken gate; I did not walk through it into your internal systems" — is
what keeps the testing in-scope while still landing a High.

## Reproduce it

One self-contained script, four evidence steps, runs in seconds:

```bash
python3 poc/poc_device_scope_bypass.py
```

Live output for all four steps is in [`poc/output.txt`](poc/output.txt); the full
submission (including the `client_id` provenance from Shopify's open-source CLI) is in
[`original-report.md`](original-report.md).

## Takeaways you can reuse

- **Enumerate grant types, not just endpoints.** `authorization_code`, `device_code`,
  `token-exchange`, `client_credentials` — each is a separate code path to the same scopes.
- **Undocumented endpoints are soft targets.** A capability missing from the discovery doc
  is a capability that may have skipped the security review the documented ones got.
- **Device-code phishing gets nastier with `verification_uri_complete`.** A pre-filled link
  removes the one bit of friction (typing the code) that RFC 9700 relies on. Flag it.
