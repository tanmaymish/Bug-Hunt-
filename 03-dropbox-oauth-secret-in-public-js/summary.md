# Dropbox Dash — Production OAuth `client_secret` + Internal Config Exposure (Intigriti P3 / Medium)

Submission-ready evidence package. Everything re-verified live **2026-07-04**.

## The one-line pitch for the triager
Production OAuth `client_secret` is public in `www.dash.ai` JS **and proven live** by Dropbox's own
`/2/check/app` endpoint → an attacker can impersonate the Dash app to Dropbox's app-authenticated API.
Same bundle leaks a GrowthBook key exposing internal feature-flags, unreleased roadmap/AI-model names,
and ~900 customer/team identifiers.

## Scope of the claim (read this first)
- **Demonstrated:** live production `client_secret` (app impersonation) + internal GrowthBook config exposure.
- **NOT claimed:** user account/file takeover. The `client_credentials` app token is rejected by user
  endpoints, and the code-exchange chain is likely blocked by PKCE. See `report.md` §3 — the ATO path is
  recorded as an *unverified, contingent* escalation, not a demonstrated impact.

## Contents
| Path | What it is |
|---|---|
| `report.md` | The submission. Paste into Intigriti. |
| `pocs/01_extract_secret.sh` | Pull the secret from public prod JS |
| `pocs/02_prove_secret_live.sh` | Prove secret is live + genuine (the money shot) |
| `pocs/03_oauth_takeover_chain_self_account.sh` | Code-exchange test — run vs YOUR OWN account ONLY; determines whether PKCE is server-side optional |
| `pocs/04_growthbook_exposure.sh` | Internal feature-flag/customer-ID exposure (single GET) |
| `evidence/01..06` | Captured raw outputs (timestamped) |
| `evidence/hashes.txt` | SHA-256 manifest for integrity |

## Order of proof (how to read it)
1. `evidence/01` — secret is public
2. `evidence/02` + `evidence/03` — secret is **live and genuine** ← severity driver
3. `evidence/04` — honest limit: app token alone can't read user files (keeps report credible)
4. `evidence/06` — internal data blast radius (redacted)
5. `report.md` §3 — code-exchange/ATO path recorded as unverified pending an own-account test

## Deliberate boundaries
- Customer identifiers (`pid_eci`) are **counted, never exfiltrated/stored**.
- No production writes re-run (PAP/Sentry) — capability noted, not exploited.
- No ATO asserted without a demonstrated code exchange; the code-exchange test is run against **your own
  account only**, never a real user's session.
- Over-claiming or over-collection gets bounties cut or researchers banned — accuracy is the strategy.
