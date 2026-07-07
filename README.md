# Bug Bounty Field Notes — A Master Class in Auth Bypass Hunting

> Three real, responsibly-disclosed vulnerabilities in the authentication and
> authorization layers of major platforms — taught as case studies. Each one walks
> from *how the technology is supposed to work*, to *the observation that broke it*,
> to *the exact reproduction*, to *the transferable lesson* you can reuse on your own targets.

This isn't a list of findings. It's a teardown of **how to think** when you hunt
OAuth and GraphQL systems: how to read the seams between services, how to tell a real
break from a reflected-parameter mirage, and how to write up a finding that a triager
trusts on the first read.

---

## The through-line

Every case here comes from the same core idea:

> **The same privileged operation is often reachable through more than one door — and the doors don't enforce the same rules.**

- **Atlassian** — one GraphQL gateway enforces step-up MFA; a second gateway forwards the *same* mutation straight to the backend.
- **Shopify** — the `authorization_code` flow routes a privileged scope through employee SSO; the *device* flow serves it a normal activation link.
- **Dropbox** — a production OAuth `client_secret` is shipped to every browser, and the interesting work is proving *exactly* how far that does — and doesn't — go.

Read [`methodology/`](methodology/) first for the repeatable process behind all three.

---

## Case studies

| # | Target | Vulnerability class | Severity | The lesson |
|---|--------|--------------------|----------|------------|
| [01](01-atlassian-graphql-gateway-bypass/) | **Atlassian** | Inconsistent authN/MFA enforcement between GraphQL gateways | P1 | Read *where* an error comes from, not just its status code |
| [02](02-shopify-oauth-device-scope-bypass/) | **Shopify** | OAuth device flow bypasses employee SSO gate | High (CVSS 8.7) | The same scope can take two code paths — test *all* of them |
| [03](03-dropbox-oauth-secret-in-public-js/) | **Dropbox** | Live production `client_secret` in public JS bundle | Medium | Prove impact honestly; a leaked secret is only worth what it actually unlocks |

Each folder contains:
- **`README.md`** — the case study (start here)
- **`original-report.md`** — the actual write-up submitted to the program
- **`poc/`**, **`evidence/`** — reproduction scripts and captured request/response pairs

---

## On secrets and disclosure

Every live credential, token, private key, and API key in this repository has been
**removed or replaced with a `REDACTED_*` placeholder**. Nothing here is a working secret.

All research was performed against assets explicitly in scope for their programs, and
each finding was reported to the vendor before publication. **Findings still inside a
coordinated-disclosure window are deliberately not included here** — responsible
disclosure is part of the craft, not an afterthought.

---

*Independent security research. Everything here is for education. Never run these
techniques against systems you are not explicitly authorized to test.*
