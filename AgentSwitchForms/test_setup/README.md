# Forms Seat (Seat 25) Test Setup & Workflow Audit

This package provides the complete testing harness for Seat 25 (`forms`). It enables writing and executing unit, integration, and security-boundary tests easily against the 5 operational use cases defined in `STEP3_USE_CASES_AND_WORKFLOWS.md`.

---

## 1. Status: Are the Workflow Steps Tested?

**No**, prior to this setup, the workflow steps in `STEP3_USE_CASES_AND_WORKFLOWS.md` were **not tested**.
- `STEP3_USE_CASES_AND_WORKFLOWS.md` provided the architecture specification and planned file mappings (Section 3).
- No test files existed in `AgentSwitchForms/tests/`.
- No harness existed to validate MCP payloads, test transitions, or verify seat boundary refusals.

---

## 2. Feasibility & System Bugs Analysis

Running the feasibility audit (`python3 AgentSwitchForms/test_setup/check_feasibility.py`) against `mcp_tools.json` and platform schemas yields the following findings:

### A. Step Feasibility Summary
- **UC-01 (Dynamic Authoring & Activation)**: **100% Feasible**. `endpoint.storefront.locale`, `Form.create`, `Form.update`, `Form.get` all exist and match payload schemas.
- **UC-02 (Weekly Audit & Analytics)**: **100% Feasible** via mitigation.
- **UC-03 (Abuse & Duplicate Resolution)**: **100% Feasible**. Queue, resolve, duplicate linking, and archive transitions match schema.
- **UC-04 (Consent Ledger & Audit)**: **100% Feasible**. Consent ledger, issue, get, and verify endpoints match schema.
- **UC-05 (CRM Spine Sync & Refusal)**: **100% Feasible**. `Party` creation, `FormAutomation`, retry, and 403 refusal are all supported.

### B. System Bugs & Platform Constraints to Be Aware Of

1. **Known Platform Defect (Gap 1.4 / Assignment §10)**:
   - Direct call to `GET /api/survey/analytics/{id}` crashes with **HTTP 500** because the platform queries nonexistent survey analytics tables.
   - **Mitigation in UC-02**: Agent client-side aggregates raw responses fetched via `FormResponse.list`.

2. **State Machine Strictness on `FormResponse`**:
   - `FormResponse.create` creates records with status `'draft'`.
   - `FormResponse.submit` must be called to reach `'submitted'`.
   - `FormResponse.mark_reviewed` only accepts status `'submitted'`.
   - `FormResponse.archive.submitted.archived` only accepts status `'submitted'`.
   - `FormResponse.archive.reviewed.archived` only accepts status `'reviewed'`.
   - Calling the wrong transition for a state returns a state machine conflict error.

3. **Seat 25 Security Boundary (Assignment §8)**:
   - Seat 25 permissions: allowed apps are `forms`, `crm`, and private `agent`.
   - Strictly forbidden entities: `SalarySlip`, `PayrollEntry`, `Contract`, `EsignDocument`, and raw GL.
   - Any attempt to invoke forbidden entities must return HTTP 403.

---

## 3. Harness Architecture

```
AgentSwitchForms/
├── .venv/                         # Virtual environment with pytest & dependencies
├── pyproject.toml                 # Package definition & pytest options
├── testing/
│   ├── client.py                  # FormsTestClient (Live MCP JSON-RPC + Offline mock mode)
│   ├── validator.py               # SchemaValidator (mcp_tools.json & seat boundary checks)
│   └── fixtures.py                # SampleDataBuilder (jurisdiction & CRM test payloads)
├── test_setup/
│   ├── check_feasibility.py       # Turnkey diagnostic script auditing all 23 workflow steps
│   └── README.md                  # This documentation
└── tests/
    ├── conftest.py                # Pytest fixtures & assertion helpers
    └── test_harness_smoke.py      # Verification smoke test
```

---

## 4. How to Easily Write New Tests

With the harness in place, writing a test for any workflow step takes just a few lines:

```python
def test_create_supplier_form(client, sample_data, assert_mcp_success):
    payload = sample_data.dynamic_form_payload("IN")
    response = client.call_tool("Form.create", payload)
    result = assert_mcp_success(response)
    assert result["status"] == "draft"

def test_salary_slip_refusal(client, assert_seat_refusal):
    response = client.call_tool("SalarySlip.list", {"party_id": "pty_123"})
    err = assert_seat_refusal(response)
    assert err["code"] == 403
```

---

## 5. Execution Commands

- **Run feasibility audit across all workflow steps**:
  ```bash
  python3 AgentSwitchForms/test_setup/check_feasibility.py
  ```

- **Run the test suite**:
  ```bash
  AgentSwitchForms/.venv/bin/pytest AgentSwitchForms/tests
  ```
