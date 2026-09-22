# Step 2: Competitive Benchmark & Domain Gold Standard
**Benchmark Target: Fillout (fillout.com) & Feathery (feathery.io)**
*Domain: Modern AI-Native Forms & Data Intake Systems*

---

## 1. Why Fillout & Feathery Define the Bar in 2026

Modern data collection has shifted away from static web forms (Google Forms, SurveyMonkey) toward **AI-native, database-connected workflow engines**. Two products lead this space:

1. **Fillout (www.fillout.com)**:
   - Ranked the top AI form platform for database-first organizations.
   - Built around native 2-way database synchronization (Postgres, Airtable, Notion, HubSpot, Salesforce).
   - Features the **Fillout AI Agent**: generates multi-page forms, conditional branching logic, scoring, and automated validation rules directly from plain-language requirements or uploaded supplier compliance documents.
   - Advanced field primitives: dynamic cascading lookups, e-signatures, file uploads with MIME inspection, date ranges, and live calculated expressions.
   - Edit-response workflows: suppliers can log in to update, amend, and track submission statuses.

2. **Feathery (www.feathery.io)**:
   - Developer-grade workflow engine powered by the **Robin AI Workflow Assistant**.
   - Specialized in multi-step enterprise onboarding, KYC/vendor verification, document extraction (OCR/AI parsing of tax cards and certificates), and approval routing.

---

## 2. Core Capabilities of the Gold Standard

### A. Intelligent Form Generation & Logic
- **Natural Language Schema Synthesis**: Plain-text prompts generate complete forms with proper types (e.g. regex-validated tax IDs, address subfields, file upload limits).
- **Deep Conditional Logic**: Page-level and block-level branching based on prior answers, arithmetic comparisons, or external database queries (e.g. hide GST fields if entity is outside India).
- **Pre-fill & Dynamic Record Lookups**: Querying existing supplier registries to pre-populate known vendor records, preventing duplicate entries.

### B. Document Intake & Identity Verification
- **Identity & Compliance Verification**: Automated verification of business IDs (EIN, GSTIN, PAN) and automated document validity checks (Certificates of Insurance, W-9, MSME certificates).
- **Audit-Proof E-Signatures**: Integrated electronic signatures bound to cryptographic timestamps and tamper-evident audit trails.

### C. 2-Way Sync & Workflow Lifecycle
- **Real-Time Database Sync**: Submissions write directly to ERP/CRM tables with rollbacks on foreign key failure.
- **Respondent Management**: Magic link / SSO respondent portal allowing suppliers to resume drafts or update banking information.
- **Approval & Review Queues**: Integrated triage queues where compliance teams review, flag spam, request revisions, and verify vendor documents.


---

## 3. Detailed Feature Comparison: Fillout vs. AgentSwitch Forms

| Capability Area | Fillout / Feathery (Gold Standard) | AgentSwitch Forms (Platform Reality) |
| :--- | :--- | :--- |
| **Form Builder UI** | Visual drag-and-drop, real-time preview, theme customizer, AI prompt builder | Schema-driven JSON data model; no WYSIWYG canvas for agents (driven via MCP/REST) |
| **Supported Block Types** | 50+ rich field types, including dynamic SQL lookups, document OCR, calendar scheduling | 40+ block types declared in schema (`short_text`, `email`, `file_upload`, `signature`, `legal_consent`, etc.) |
| **Logic & Branching** | Complex boolean trees (`AND`/`OR`), cross-page jumps, multi-field dependency rules | Linear `logic_rules` array with single condition (`equals`, `gt`, `contains`) and actions (`jump_to`, `hide`, `end_form`) |
| **Database Sync** | 2-way native sync to Postgres/Airtable/Salesforce; instant field mapping | In-database entities: `Form` and `FormResponse` stored locally in the platform book |
| **Consent & Compliance** | Checkbox consent with IP/UserAgent logging; GDPR/CCPA cookie banners | First-class `FormConsentReceipt` ledger with cryptographic signature, algorithm, digest, and lawful basis |
| **Automations & Routing** | Multi-step visual automation canvas, webhooks, Zapier/Make integrations | Built-in `FormAutomation` records (`trigger_on`: `submission`/`update`, `action_type`: `send_email`, `update_party_tag`, `create_lead`) |
| **Abuse & Review Queue**| Built-in bot protection, ReCaptcha v3, duplicate detection dashboard | Dedicated review queue endpoint (`endpoint.forms.response_review.queue`) with spam/not-spam triage |
| **Analytics Engine** | Real-time drop-off funnels, conversion rates, time-per-field heatmaps | Known platform bug: `GET /api/survey/analytics/{id}` returns 500. Analytics must be computed client-side |
| **Locale / Jurisdiction**| Multi-lingual forms via AI translation; static currency/tax selector | Accounting locale is live database state (`GET /api/accounting/locale`) with Ind AS/GST vs US GAAP distinction |

---

## 4. Key Takeaways for Step 3 (The Gap Report)

1. **What Fillout does that AgentSwitch lacks (Platform Gaps)**:
   - External document OCR (auto-extracting tax ID from uploaded PDF/image).
   - Complex nested boolean conditional trees (`AND` + `OR` logic).
   - Dedicated server-side analytics API (broken in AgentSwitch with 500 error).
   - Native third-party webhook integrations (Slack/ERP push notifications).

2. **Gaps an Agent can close with current Seat 25 tools (Agent Orchestration)**:
   - **Dynamic Locale Adaptation**: Agent probes `GET /api/accounting/locale` and constructs the appropriate jurisdiction schema (GSTIN/PAN/IFSC vs EIN/W-9/ACH).
   - **Client-Side Analytics & Weekly Summarization**: Agent fetches raw `FormResponse.list` records within the 7-day window and computes completion rates, document readiness, and supplier breakdown.
   - **Automated Triage & Deduplication**: Agent inspects incoming responses, flags duplicates using `duplicate_of_id`, and executes `FormResponse.mark_reviewed`.
   - **Consent Issuance**: Agent triggers `endpoint.forms.consent_receipt.issue` to cryptographically sign compliant consent receipts.

3. **What an Agent can do that Fillout's UI cannot**:
   - Fillout requires a human operator to design the form, configure logic rules, export CSVs, and manually calculate weekly onboarding progress.
   - An AgentSwitch agent can accept a high-level goal (*"Build a supplier onboarding form, and summarise what came back this week"*), autonomously resolve the company's tax jurisdiction, author the form with 10+ custom blocks, publish it, query the live response queue, cross-reference suppliers against the `Party` table, and output an executive summary without human intervention.

