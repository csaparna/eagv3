# Step 1: Domain Analysis & Architecture Specification
**Seat 25: Forms (`forms`) | AgentSwitch Platform**

---

## 1. Executive Summary & Seat Scope
- **Seat Assignment**: Seat 25 — `Forms`
- **Application Ownership**: `forms` app
- **Domain Responsibilities**: Form building & schemas, response ingestion & analytics, consent management.
- **Auxiliary Spaces**:
  - `agent`: Private workspace for the agent (`AgentMemory`, `AgentMessage`, `AgentSkill`).
  - `crm`: Shared customer spine (`Lead`, `Opportunity`, `Account`, `Contact`, `Party`).
- **Core Milestone Request (§8)**:
  > *"Build a supplier onboarding form, and summarise what came back this week."*

---

## 2. Jurisdiction & Accounting Locale Architecture
The platform runs across two distinct jurisdictions with identical table schemas but contrasting data semantics and regulatory requirements.

### Locales Comparison
| Attribute | Suryodaya Precision Works | Keystone Precision Works LLC |
| :--- | :--- | :--- |
| **Jurisdiction** | India (IN) | United States (US) |
| **Accounting Standard** | Ind AS, Schedule III | US GAAP, ASC |
| **Tax Regime** | GST (CGST, SGST, IGST) | State Sales & Use Tax |
| **Locale Inspection Endpoint**| `GET /api/accounting/locale` | `GET /api/accounting/locale` |
| **Supplier Tax IDs** | GSTIN (15-digit), PAN (10-digit alphanumeric) | EIN (9-digit `XX-XXXXXXX`), W-9 / W-8BEN |
| **Banking Identifiers** | Bank Account #, IFSC code (11-digit alphanumeric) | Routing Transit Number (ABA 9-digit), Account # |
| **Compliance Declarations** | MSME / Udyam registration, GST declaration | State Tax Exemption, Certificate of Insurance (COI) |
| **Data Protection / Consent**| Digital Personal Data Protection (DPDP) Act | State Privacy / CCPA regulations |

> **Key Architectural Rule**: The agent must inspect `GET /api/accounting/locale` before building forms or generating summaries. Tax and identifier fields must be dynamic, never hardcoded.

---

## 3. Seat Boundaries & Security Envelope (§3, §5, §10)
- **What Seat 25 Can Access**:
  - `forms`: `Form`, `FormField`, `FormResponse`, `Consent`
  - `crm`: `Account`, `Contact`, `Party`, `Lead`
  - `agent`: `AgentMemory`, `AgentSkill`, `AgentMessage`
- **What Seat 25 CANNOT Access (403 Forbidden)**:
  - `SalarySlip`, `PayrollEntry` (Payroll seat boundary)
  - `Contract` (Contracts seat boundary)
  - `EsignDocument` (E-sign seat boundary)
  - Raw General Ledger / `JournalEntry` / Bank accounts / Tax configs
  - *Refusal requirement*: Any instruction attempting to query these entities must trigger a clean refusal naming the seat boundary.



## 4. MCP & API Interface Rules (§6, §7, §10)
- **Protocol**: Model Context Protocol (MCP) JSON-RPC 2.0 over HTTP POST (`POST /api/mcp`).
  - Protocol version: `2025-11-25`.
  - HTTP 200 with error envelope on failure (`{"jsonrpc":"2.0", "error": {...}}`).
  - No SSE stream (Allow: POST). No batching.
  - Closed argument schemas: excess or unmapped arguments are rejected.
- **REST Endpoints**:
  - `GET /api/schemas` — All entity field types, options, and validation rules.
  - `GET /api/accounting/locale` — Accounting regime indicator.
  - `GET /api/auth/me` — Roles and allowed apps validation.
- **Platform Bug Workarounds & Invariants (§10)**:
  1. `PATCH` is disallowed (returns 405) — updates must use `PUT`.
  2. Workflow transitions require key `target_state` in arguments.
  3. `GET /api/survey/analytics/{id}` 500s — query raw responses via `<Entity>.list` with date filtering instead of relying on server-side analytics endpoints.
  4. `created_at` is server-stamped — time filtering must parse server timestamps rather than relying on custom back-dated inputs.

---

## 5. Domain Data Model for Forms
- **`Form`**: `id`, `company_id`, `title`, `description`, `schema` (field definitions), `workflow_state` (`draft` -> `active` -> `archived`).
- **Jurisdiction Fields**:
  - *Common*: Legal Name, Contact Person, Email, Phone, Address, Bank Account Number, Payment Terms.
  - *India (Suryodaya)*: GSTIN, PAN, IFSC Code, MSME/Udyam Number, DPDP Consent.
  - *US (Keystone)*: EIN, W-9 Status, ABA Routing Number, Sales Tax Exemption Status, Privacy Consent.
- **`FormResponse`**: `id`, `form_id`, `respondent_id`, `answers` (JSON payload), `submitted_at`, `status`.
- **`Consent`**: `id`, `party_id`, `purpose`, `status`, `granted_at`.

---

## 6. End-to-End Workflow for Section 8 Request
*"Build a supplier onboarding form, and summarise what came back this week."*
1. **Locale Inspection**: Query `GET /api/accounting/locale` to resolve jurisdiction (India vs US).
2. **Form Definition**: Assemble dynamic schema containing common and jurisdiction-specific fields.
3. **Form Creation**: Call `Form.create` (initial status `draft`).
4. **Form Activation**: Call `Form.transition` with `target_state="active"`.
5. **Response Query**: Fetch responses for the current week window (`FormResponse.list`).
6. **Aggregation & Summary**: Aggregate metrics (total counts, completeness, document status).
7. **Verification**: Assure database state satisfies `GoalPredicate.check(db, company_id, job)`.
