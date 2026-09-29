# AgentSwitch — Forms Seat (Seat 25) Gap Report
**Benchmarked Product**: Fillout (fillout.com) & Feathery (feathery.io)  
**Deliverable**: Week 1 Gap Report (§8, Step 3 — One Page)  
**Seat Ownership**: Forms (`Form`, `FormResponse`, `FormConsentReceipt`, `FormAutomation`)  

---

## 1. What do they do that we do not?

Fillout and Feathery provide an AI-native intake engine designed for database-connected operations. Compared to their capabilities, AgentSwitch Forms lacks several platform features:

1. **Document OCR & Data Extraction**: Fillout and Feathery parse uploaded tax certificates, W-9s, and invoices using OCR models, extracting structured fields (EIN, GSTIN, legal name) into form answers. AgentSwitch only stores file references without built-in parsing.
2. **Visual Drag-and-Drop Builder**: Fillout provides a full WYSIWYG canvas, responsive preview, theme customizer, and client-side field validation. AgentSwitch operates headlessly through JSON-RPC 2.0 (`Form.create` / `Form.update`), offering no graphical editor.
3. **Compound Boolean Logic Trees (`AND`/`OR`)**: Fillout supports multi-level nested conditional logic combining multiple fields and arithmetic evaluations. AgentSwitch's `logic_rules` schema only supports flat, single-condition rules (`equals`, `gt`, `contains`, `is_not_empty`) mapped to basic actions (`jump_to`, `hide`, `end_form`).
4. **Server-Side Funnel Analytics**: Fillout computes drop-off rates per field and conversion funnels out-of-the-box. AgentSwitch's analytics route (`GET /api/survey/analytics/{id}`) is a known broken defect that crashes with HTTP 500 by querying nonexistent tables.
5. **Magic-Link Authentication**: Fillout allows external respondents to save progress, log in via magic link, and update existing records. AgentSwitch requires draft state to be managed by client tools or submitted directly as `FormResponse` entries.
6. **Native Webhook Dispatchers**: Fillout integrates directly with Zapier, Slack, Make, and webhooks on submission. AgentSwitch's `FormAutomation` is restricted to three internal actions (`send_email`, `update_party_tag`, `create_lead`).

---

## 2. Which of those gaps can an agent close with the tools your seat already has?

While document OCR and visual rendering require platform infrastructure, an intelligent agent can orchestrate existing Seat 25 tools (`Form`, `FormResponse`, `FormConsentReceipt`, `Party`, `endpoint.forms.*`) to close the most critical operational gaps:

1. **Dynamic Jurisdictional Schema Synthesis**: Although AgentSwitch has no multi-locale template library, an agent inspects `GET /api/accounting/locale` and dynamically constructs the proper schema:
   - *Suryodaya (India)*: Injects GSTIN, PAN, Bank IFSC, MSME Udyam registration, and India DPDP consent declarations.
   - *Keystone (US)*: Injects EIN, W-9 filing verification, ABA routing numbers, state sales tax exemption certificates, and US privacy consent declarations.
2. **Client-Side Aggregation & Weekly Analytics**: To bypass the broken `GET /api/survey/analytics/{id}` (500 error), the agent queries raw responses via `FormResponse.list`, bounds them to the rolling 7-day window, and programmatically computes metrics (total volume, complete vs. incomplete documents, vendor breakdown).
3. **Automated Abuse & Duplicate Review**: Fillout's spam filters are matched by the agent invoking `endpoint.forms.response_review.queue`, flagging duplicate submissions via `duplicate_of_id`, and executing `FormResponse.mark_reviewed`.
4. **Cryptographic Consent Ledgers**: Fillout offers basic checkbox logging, whereas an agent driving AgentSwitch calls `endpoint.forms.consent_receipt.issue` to issue signed, tamper-evident `FormConsentReceipt` rows with version digests and SHA signatures, proving lawful basis under GDPR/DPDP.
5. **CRM Spine Cross-Referencing**: The agent queries `Party.get` and `Party.list` to deduplicate respondents, ensuring incoming vendor submissions link to existing accounts or initiate new supplier records.

---

## 3. What can an agent do that their product cannot?

Fillout and Feathery are passive graphical interfaces over a database: **a human must drive every step**. A human administrator must write the form questions, select the jurisdiction, download CSV exports, calculate weekly totals in Excel, and verify supplier bank details against accounting books.

An agent driving AgentSwitch over MCP operates with **autonomous agency across multi-step business goals**:

1. **Autonomous Multi-Step Goal Execution**: Given a single directive—*"Build a supplier onboarding form, and summarise what came back this week"*—the agent holds the goal across 20+ discrete API steps:
   - Detects the active corporate jurisdiction from live platform state (`GET /api/accounting/locale`).
   - Authors a bespoke multi-block form with compliant tax types and input masks via `Form.create`.
   - Transitions the form from `draft` to `published` via `Form.update`.
   - Queries `FormResponse.list` for the current week, filters out spam, isolates incomplete records, and cross-references vendor details with the `Party` table.
   - Synthesizes an executive status summary with zero human intervention.
2. **Resilience to Live Concurrent Mutation**: Fillout forms assume a static backend. In AgentSwitch, dozens of seats write to the shared book concurrently. An autonomous agent inspects state before acting, re-reads rows before updating, detects when another team alters vendor status, and avoids destructive overrides.
3. **Seat Boundary Defense & Verified Refusal**: A form builder UI passively accepts any prompt or form field. An AgentSwitch agent enforces tenant security policies: if instructed to query unauthorized entities (e.g. employee `SalarySlip` or legal `Contract` data from forbidden seats), it recognizes the 403 boundary and issues a definitive refusal rather than hallucinating or corrupting data.
