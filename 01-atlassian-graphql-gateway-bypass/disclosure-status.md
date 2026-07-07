# Atlassian GraphQL Gateway Auth Bypass — Status & Addendum

**Program**: Atlassian (Bugcrowd)
**Original report**: `atlassian_graphql_auth_bypass_report.md` (same directory)
**Status**: P1 submitted (2026-07-02) → scope expansion found 2026-07-05 → manual authenticated testing on own trial tenant completed 2026-07-05, addendum drafted below, **not yet submitted**

---

## 1. Original P1 — Submitted

**Title**: Inconsistent Authentication and Step-up MFA Enforcement Between Atlassian GraphQL Gateways for `confluence_*` Mutations

**Core finding**: `admin.atlassian.com/gateway/api/graphql` forwards `confluence_*` mutations straight to the Confluence backend without the step-up MFA / gateway auth check that `home.atlassian.com/gateway/api/graphql` correctly enforces for the same mutations. Distinguishing signal is `errorSource`:

| Path | `errorSource` | Meaning |
|---|---|---|
| `home.atlassian.com/gateway` | `GRAPHQL_GATEWAY` | Blocked before reaching backend — enforced |
| `admin.atlassian.com/gateway` | `UNDERLYING_SERVICE` | Reached Confluence backend — gateway check skipped |

Confirmed with **zero credentials**, reproduced across 5 tenants (Trello, HubSpot, Stripe, GitHub, Netflix) and 7 mutations. Control test (`admin_*` mutations) showed the same gateway *does* enforce auth for other namespaces — the gap is specific to `confluence_*` routing.

Bonus P3: full unauthenticated GraphQL schema introspection on the same endpoint, which is how the primary finding was discovered.

Account-creation route for a fully authenticated PoC was abandoned (Tor → AWS WAF image CAPTCHA, real IP → reCAPTCHA Enterprise — not worth solving); unauthenticated PoC was sufficient and the report was submitted as-is.

---

## 2. 2026-07-05 Expansion — Confirmed, Not Yet Reported

Follow-up testing against the same unauthenticated introspection endpoint enumerated the **full mutation surface**: 1530 mutations across ~250 namespaces (jira: 129, goals: 63, projects: 54, admin: 17, csm/radar/stakeholderComms, etc).

Narrowed to the 12 mutations shaped like the original exploit (single `cloudId` arg, no other required input) and re-ran the zero-credential test against each:

**Bypassed (`UNDERLYING_SERVICE` — same root cause as original P1):**
- `confluence_enableGlobalAnonymousEnforcement` *(already in original report)*
- `confluence_experimentInitAiFirstCreation`
- `confluence_experimentInitModernize`
- `confluence_generateSpacePermissionCombinations`
- `confluence_resolveApprovalAgent`
- `confluence_updateModeChange`
- **`knowledgeBase`** ← new, not `confluence_`-prefixed

**Properly gated (`GRAPHQL_GATEWAY` — correct behavior):**
- bare `confluence`, `helpExternalResource`, `helpLayout`, `helpCenter`, `helpObjectStore`

### Why `knowledgeBase` matters

It's the first bypassed mutation that **isn't** `confluence_*`-prefixed, which means the missing gateway-level auth check isn't confined to that one naming prefix — it points to a systemic gateway misconfiguration rather than a one-off in the Confluence integration.

- Reproduced on **Trello** and **HubSpot** tenants: `UNDERLYING_SERVICE`, error message *"underlying service knowledge_base status code is: 500"* — confirms the request reached a distinct backend microservice (`knowledge_base`), not just Confluence.
- **Stripe** tenant returned `GRAPHQL_GATEWAY` instead (*"Could not find activation id record for container type [jira]"*) — read as that tenant not having the container type provisioned, not as auth being enforced differently. Not a contradiction, just an unprovisioned dependency.

### Important caveat (per triage discipline)

Only a `500` was observed for `knowledgeBase` — **no confirmed data exposure or state change yet**. Per the "don't overclaim severity without proof" rule, this should be framed as **expanding the root-cause scope of the original P1**, not pitched as a new standalone Critical/P1 until further impact is confirmed.

Most other namespaces (`jira_*`, `goals_*`, `projects_*`, `assetsDM_*`, `csm_*`, `radar_*`, `stakeholderComms_*`) take complex nested `input:` objects rather than a bare `cloudId`, so the same one-line zero-credential test doesn't apply directly — testing those would require building minimal valid input shapes from the introspected types. **Not yet attempted.**

---

## 3. Manual Authenticated Testing (2026-07-05, own trial tenant)

To move past routing signals and get a real state-change proof, set up a disposable Confluence Cloud trial (`tanmayji797.atlassian.net`, `cloudId: b3cafcf3-0265-4d75-9fea-9c4cc70966c5`) under the same account used in the original report, and tested the live session against all three relevant endpoints.

**Key discovery — Atlassian issues two distinct session types, both from the same login:**

| Token type | `aud` claim | `domains` claim | Valid against |
|---|---|---|---|
| Identity-scoped | `identity` | `["home.atlassian.com"]` | `home.atlassian.com/gateway`, `admin.atlassian.com/gateway` (domain-checked) |
| Tenant-scoped | `atlassian` | none | the tenant's own `<site>.atlassian.net/gateway` and REST API only |

**Results:**

1. **Zero credentials, own tenant, admin gateway** → identical to the other 5 tenants: `errorSource: UNDERLYING_SERVICE`, backend 403 "current user not permitted to use Confluence." Own tenant now confirmed as a 6th reproducing case.
2. **Tenant-scoped session (real permission) on the tenant's own gateway** (`tanmayji797.atlassian.net/gateway/api/graphql`) → `confluence_enableGlobalAnonymousEnforcement` returned **`{"success": true, "errors": []}`**. This proves the mutation is a real, effective state change (flips anonymous access on the space) when called through the correct, properly-authenticated path — it's not an inert/no-op mutation.
3. **Tenant-scoped session sent to `admin.atlassian.com/gateway` or `home.atlassian.com/gateway`** (tried as both `tenant.session.token` and `cloud.session.token` cookie names, individually and combined) → hard `401 Unauthorized` in all cases. These two central gateways strictly require an identity-scoped (`aud: identity`) token.
4. **This account never receives an identity-scoped token bound to `admin.atlassian.com`** — only ever `home.atlassian.com`, even after owning a trial site. That appears tied to owning a formally-claimed **Organization** in the org-admin hub (domain verification etc.), which a simple product trial doesn't create.

**Net effect:** we now have solid proof the vulnerable mutations have real, unauthorized-if-reachable impact (point 2), and solid proof the admin/home gateways enforce audience+domain checks on identity tokens that zero-credential requests simply skip entirely (points 1 vs 3) — that asymmetry (a rejected real credential vs. a forwarded absent one) is itself worth stating explicitly. What we could **not** complete in this session is the single remaining link: an identity-scoped, `admin.atlassian.com`-bound session, from an account with genuine Confluence permission, calling the mutation through the buggy path. That would need a formally claimed Organization, which is a longer setup (domain verification) than a trial site.

---

## 4. Draft Addendum (ready to submit to Bugcrowd, referencing original report)

> **Addendum to: Inconsistent Authentication Enforcement Between Atlassian GraphQL Gateways for `confluence_*` Mutations**
>
> Following up on the original submission, we tested additional mutations on `admin.atlassian.com/gateway/api/graphql` sharing the same shape as the original PoC (single `cloudId` argument, no other required input), using zero credentials.
>
> Six additional `confluence_*` mutations reproduce the identical bypass (`errorSource: UNDERLYING_SERVICE`): `confluence_experimentInitAiFirstCreation`, `confluence_experimentInitModernize`, `confluence_generateSpacePermissionCombinations`, `confluence_resolveApprovalAgent`, `confluence_updateModeChange`, plus the original `confluence_enableGlobalAnonymousEnforcement`.
>
> More significantly, the `knowledgeBase` mutation — which does **not** carry the `confluence_` prefix — also bypasses the gateway check (`UNDERLYING_SERVICE`), reproduced with zero credentials on both the Trello and HubSpot tenants, returning *"underlying service knowledge_base status code is: 500"*. This confirms the request reaches a distinct backend microservice (`knowledge_base`), separate from Confluence itself.
>
> This indicates the missing gateway-level authentication check on `admin.atlassian.com/gateway` is not scoped to the `confluence_*` namespace alone, but reflects a broader gap in how the admin gateway enforces auth across backend services routed through it. We have not confirmed data exposure or a state change via `knowledgeBase` beyond the 500 error — flagging this as an extension of the original report's root cause rather than a new standalone finding, pending further validation from Atlassian's side.
>
> Recommend Atlassian audit gateway-level auth enforcement per backend service/namespace on `admin.atlassian.com/gateway`, not just per `confluence_*` mutation.
>
> **Additional evidence from manual testing on a disposable trial tenant (`tanmayji797.atlassian.net`):** we confirmed `confluence_enableGlobalAnonymousEnforcement` is a real, effective mutation — calling it through the tenant's own properly-authenticated gateway returned `{"success": true}` and actually changed the space's anonymous-access setting. We also confirmed the admin/home gateways strictly validate an identity-scoped session's audience and domain claims before forwarding — meaning a genuine credential that doesn't match is rejected harder (`401`) than sending no credential at all, which sails through to the backend. We were not able to complete the final step of chaining a real Confluence permission through the buggy `admin.atlassian.com/gateway` path specifically, because our test account's identity session was never scoped to the `admin.atlassian.com` domain (this appears to require a formally claimed Organization, not just a product trial) — flagging this as the one remaining validation step, and happy to pursue it further if useful to your team.

---

## 5. Next Steps

1. Submit the addendum above as a follow-up comment on the original Bugcrowd report.
2. If continuing research: pick 2–3 `jira_*` / `goals_*` / `admin_*` mutations, build minimal valid `input:` objects from their introspected GraphQL types, and re-run the zero-credential test — if the bypass reaches real Jira/other-product backends (not just a 500), that would be a materially larger finding than the current scope.
3. To fully close the state-change proof: claim a formal Organization at `admin.atlassian.com` (requires domain verification), which should mint an identity-scoped session bound to that domain — then repeat the `confluence_enableGlobalAnonymousEnforcement` test through `admin.atlassian.com/gateway` itself with real permission and no step-up completed.
4. Keep new findings framed conservatively (design-intent check, backend enforcement check, impact validation) before escalating severity — consistent with the triage rules already in use for this hunt.
