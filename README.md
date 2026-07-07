<div align="center">

# 🕵️ Bug Bounty Field Notes

### A Master Class in OAuth & GraphQL Auth‑Bypass Hunting

*Three real, responsibly‑disclosed vulnerabilities in the auth layers of major platforms —
taught as case studies, with attack‑flow diagrams and a repeatable methodology.*

<br/>

![Focus](https://img.shields.io/badge/focus-web%20security-1f6feb?style=for-the-badge)
![Topics](https://img.shields.io/badge/OAuth%20·%20GraphQL-auth%20bypass-8957e5?style=for-the-badge)
![Disclosure](https://img.shields.io/badge/disclosure-responsible-2ea043?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge)

![Case studies](https://img.shields.io/badge/case%20studies-3-1f6feb?style=flat-square)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-2ea043?style=flat-square)
[![Stars](https://img.shields.io/github/stars/tanmaymish/Bug-Hunt-?style=social)](https://github.com/tanmaymish/Bug-Hunt-/stargazers)
[![Forks](https://img.shields.io/github/forks/tanmaymish/Bug-Hunt-?style=social)](https://github.com/tanmaymish/Bug-Hunt-/network/members)

<br/>

**[The Idea](#-the-through-line)  ·  [Case Studies](#-case-studies)  ·  [Methodology](methodology/)  ·  [Disclosure Ethics](#-on-secrets-and-disclosure)  ·  [Author](#-author)**

</div>

---

> **This isn't a list of findings.** It's a teardown of **how to think** when you hunt OAuth
> and GraphQL systems: how to read the seams between services, how to tell a real break from a
> reflected‑parameter mirage, and how to write up a finding a triager trusts on the first read.

### What you'll learn

- 🚪 **Find the forgotten door** — how the *same* privileged capability gets exposed through a second, unhardened path.
- 🔬 **Diff, don't guess** — using control requests and error‑provenance fields to prove a control was *skipped*, not just that a request failed.
- ⚖️ **Right‑size severity** — proving impact honestly instead of inflating a reflected parameter into "account takeover."
- 📦 **Report like a pro** — one‑command PoCs and write‑ups that get triaged first.

---

## 🎯 The through-line

Every case here comes from the same core idea:

> **The same privileged operation is often reachable through more than one door — and the doors don't enforce the same rules.**

- **Atlassian** — one GraphQL gateway enforces step-up MFA; a second gateway forwards the *same* mutation straight to the backend.
- **Shopify** — the `authorization_code` flow routes a privileged scope through employee SSO; the *device* flow serves it a normal activation link.
- **Dropbox** — a production OAuth `client_secret` is shipped to every browser, and the interesting work is proving *exactly* how far that does — and doesn't — go.

```mermaid
flowchart LR
    A(["😈 Attacker wants<br/>a privileged capability"]):::neutral
    A --> D1["🔒 Door 1<br/>the hardened path<br/>(MFA / SSO / PKCE)"]:::good
    A --> D2["🚪 Door 2<br/>the forgotten path<br/>(device flow / 2nd gateway / leaked secret)"]:::bad
    D1 -->|"checks RUN"| G[["🎯 Same backend capability"]]:::neutral
    D2 -->|"checks SKIPPED"| G

    classDef good fill:#0b3d1a,stroke:#2ecc71,stroke-width:2px,color:#eafff0;
    classDef bad fill:#4d0b0b,stroke:#e74c3c,stroke-width:2px,color:#ffecec;
    classDef neutral fill:#16233f,stroke:#5dade2,stroke-width:1px,color:#eaf2ff;
```

Read **[`methodology/`](methodology/)** first for the repeatable process behind all three.

---

## 📚 Case studies

| # | Target | Vulnerability class | Severity | The lesson |
|---|--------|--------------------|----------|------------|
| [**01**](01-atlassian-graphql-gateway-bypass/) | 🟦 **Atlassian** | Inconsistent authN/MFA enforcement between GraphQL gateways | `P1` | Read *where* an error comes from, not just its status code |
| [**02**](02-shopify-oauth-device-scope-bypass/) | 🟩 **Shopify** | OAuth device flow bypasses employee SSO gate | `High · CVSS 8.7` | The same scope can take two code paths — test *all* of them |
| [**03**](03-dropbox-oauth-secret-in-public-js/) | 🟦 **Dropbox** | Live production `client_secret` in public JS bundle | `Medium` | Prove impact honestly; a leaked secret is only worth what it actually unlocks |

Each folder contains:
- **`README.md`** — the illustrated case study (start here)
- **`original-report.md`** — the actual write-up submitted to the program
- **`poc/`**, **`evidence/`** — reproduction scripts and captured request/response pairs

---

## 🔒 On secrets and disclosure

Every live credential, token, private key, and API key in this repository has been
**removed or replaced with a `REDACTED_*` placeholder**. Nothing here is a working secret.

All research was performed against assets explicitly in scope for their programs, and
each finding was reported to the vendor before publication. **Findings still inside a
coordinated-disclosure window are deliberately not included here** — responsible
disclosure is part of the craft, not an afterthought.

---

## 👤 Author

**tanmaymish** — independent security researcher (OAuth · GraphQL · web app security).

- 🔗 LinkedIn: `<add your profile link>`
- 🐙 GitHub: [@tanmaymish](https://github.com/tanmaymish)

> ⭐ **If these teardowns helped you learn something, star the repo** — it helps other
> hunters find it, and it makes my day.

---

<div align="center">

*For education only. Never run these techniques against systems you are not explicitly authorized to test.*

<sub>Licensed under the [MIT License](LICENSE).</sub>

</div>
