# Case 01 — Two Gateways, One Backend: Atlassian's Inconsistent GraphQL Auth

**Target:** Atlassian Cloud (Bugcrowd) · **Class:** Broken Access Control / inconsistent
authN + step-up MFA enforcement · **Severity:** P1 · **Status:** reported, coordinated disclosure

> **The one-line lesson:** when the same operation is reachable through two gateways,
> the security control on one gateway is worthless if the other gateway forwards the
> request untouched. The proof isn't the status code — it's the field that tells you
> *which layer* answered.

---

## Background: how it's supposed to work

Atlassian fronts its services with GraphQL **gateways**. A gateway is meant to be a
security choke point: authenticate the caller, enforce policy (including **step-up MFA**
for sensitive actions), and only then route the query to the backend service (here, the
Confluence monolith).

`confluence_*` mutations are exactly the kind of sensitive operation that should require
step-up MFA. And on the main gateway, they do.

## The observation that broke it

Atlassian exposes **more than one** GraphQL gateway:

- `home.atlassian.com/gateway/api/graphql`
- `admin.atlassian.com/gateway/api/graphql`

Sending the *same* `confluence_*` mutation to each produced two different rejections —
and the difference wasn't the HTTP status, it was **where the error came from**:

| Path | Error `errorSource` | What it means |
|------|--------------------|---------------|
| `home` gateway + valid session | `GRAPHQL_GATEWAY` | Blocked **at the gateway** — step-up MFA enforced, request never reached Confluence |
| `admin` gateway + valid session | `UNDERLYING_SERVICE` | Request **reached the Confluence backend** — the gateway check never ran |
| `admin` gateway + **no credentials** | `UNDERLYING_SERVICE` | *Identical* — the gateway forwarded it regardless of auth |

`GRAPHQL_GATEWAY` means the gateway itself rejected you. `UNDERLYING_SERVICE` means your
request went **through** the gateway and the Confluence application answered. That single
field is the whole finding: on the `admin` path, the gateway's authentication and step-up
MFA enforcement for `confluence_*` mutations **does not execute**.

## Why this is a real finding and not noise

Two disciplines separate this from a false positive:

1. **The control request.** `admin_*` mutations on the *same* `admin` gateway return
   `GRAPHQL_GATEWAY` — proof the gateway *can* and *does* enforce auth. The gap is specific
   to the `confluence_*` namespace routing, not a broken gateway in general.

2. **Honest scoping.** The backend still returns its own `403` ("current user not permitted
   to use Confluence"). The report does **not** claim data was exfiltrated. It claims the
   gateway-level control is being skipped — and asks Atlassian to verify which `confluence_*`
   mutations rely on that gateway control as their primary defense. That's the accurate,
   defensible claim.

## Reproduce it

Cloud IDs are public, so discovery needs zero credentials:

```bash
curl https://trello.atlassian.net/_edge/tenant_info
# {"cloudId":"3f48f622-...","displayName":"Trello"}
```

Then diff the two gateways with the same mutation. Full request/response pairs, the
five-tenant reproduction matrix, and the `admin_*` control are in
[`original-report.md`](original-report.md). Disclosure state and the follow-up addendum
are in [`disclosure-status.md`](disclosure-status.md).

## Takeaways you can reuse

- **Enumerate every gateway/host that fronts the same backend.** Auth is implemented per
  door. Find the door someone forgot to lock.
- **Look for an error-provenance field** (`errorSource`, `x-served-by`, upstream headers).
  It tells you whether a control *ran* or was *skipped* — far more than a status code does.
- **A bonus fell out of the same enumeration:** unauthenticated GraphQL introspection was
  open, which is *how* the mutation names were discovered in the first place. Recon and
  exploitation are the same motion.
