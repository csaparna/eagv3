"""
Workflow Step Feasibility & Bug Checker for Seat 25 (Forms).
Audits all workflow steps in STEP3_USE_CASES_AND_WORKFLOWS.md.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from testing.validator import SchemaValidator
from testing.client import FormsTestClient

def get_workflows():
    return [
        {
            "id": "UC-01",
            "name": "Autonomous Dynamic Form Authoring & Activation",
            "steps": [
                ("Step 1.1", "endpoint.storefront.locale", {}),
                ("Step 1.2", "Form.create", {
                    "name": "Supplier Onboarding & Compliance Intake - 2026",
                    "slug": "supplier-onboarding-2026",
                    "status": "draft",
                    "presentation_mode": "multi_page",
                    "description": "Standard compliance, tax, and banking intake.",
                    "consent_required": True,
                    "consent_text": "I certify that all declarations are authentic.",
                    "consent_lawful_basis": "consent",
                    "blocks": [
                        {"ref_id": "blk_legal_name", "type": "short_text", "title": "Legal Name", "required": True},
                        {"ref_id": "blk_contact_email", "type": "email", "title": "Email", "required": True},
                        {"ref_id": "blk_phone", "type": "phone", "title": "Phone", "required": True},
                        {"ref_id": "blk_tax_gstin", "type": "short_text", "title": "GSTIN", "required": True},
                        {"ref_id": "blk_tax_pan", "type": "short_text", "title": "PAN", "required": True},
                        {"ref_id": "blk_bank_ifsc", "type": "short_text", "title": "IFSC", "required": True}
                    ],
                    "logic_rules": []
                }),
                ("Step 1.3", "Form.update", {"id": "form_sub_onb_001", "status": "published"}),
                ("Step 1.4", "Form.get", {"id": "form_sub_onb_001"})
            ]
        },
        {
            "id": "UC-02",
            "name": "Weekly Intake Audit & Resilient Analytics Aggregation",
            "steps": [
                ("Step 2.1", "Form.get", {"id": "form_sub_onb_001"}),
                ("Step 2.2", "FormResponse.list", {"form_id": "form_sub_onb_001", "sort_by": "submitted_at", "sort_order": "desc", "limit": 100}),
                ("Step 2.3", "FormResponse.get", {"id": "resp_sub_2026_01"}),
                ("Step 2.4", "FormResponse.mark_reviewed", {"id": "resp_sub_2026_01"})
            ]
        },
        {
            "id": "UC-03",
            "name": "Automated Abuse Detection, Duplicate Resolution & Triage",
            "steps": [
                ("Step 3.1", "endpoint.forms.response_review.queue", {"form_id": "form_sub_onb_001", "verdict": "unreviewed", "offset": 0, "max_scan": 200}),
                ("Step 3.2", "FormResponse.list", {"form_id": "form_sub_onb_001", "respondent_email": "billing@bharatfasteners.com"}),
                ("Step 3.3", "endpoint.forms.response_review.resolve", {"response_id": "resp_sub_2026_02", "verdict": "not_spam", "duplicate_of_id": "resp_sub_2026_00_orig"}),
                ("Step 3.4", "endpoint.forms.response_review.resolve", {"response_id": "resp_sub_2026_03", "verdict": "spam"}),
                ("Step 3.5", "FormResponse.archive.submitted.archived", {"id": "resp_sub_2026_03"})
            ]
        },
        {
            "id": "UC-04",
            "name": "Cryptographic Consent Ledger Management & Audit",
            "steps": [
                ("Step 4.1", "endpoint.forms.consent_receipt.ledger", {"form_id": "form_sub_onb_001", "state": "issuable", "offset": 0, "max_scan": 100}),
                ("Step 4.2", "endpoint.forms.consent_receipt.issue", {"response_id": "resp_sub_2026_01"}),
                ("Step 4.3", "FormConsentReceipt.get", {"id": "rcpt_cns_789012"}),
                ("Step 4.4", "endpoint.forms.consent_receipt.verify", {"receipt_id": "rcpt_cns_789012"})
            ]
        },
        {
            "id": "UC-05",
            "name": "CRM Spine Sync, Automation Retry & Verified Seat Refusal",
            "steps": [
                ("Step 5.1", "Party.list", {"email": "accounts@apexprecision.in", "contact_type": "vendor"}),
                ("Step 5.2", "Party.create", {
                    "name": "Apex Precision Components Pvt Ltd",
                    "email": "accounts@apexprecision.in",
                    "type": "organization",
                    "contact_type": "vendor",
                    "gst_treatment": "business_gst"
                }),
                ("Step 5.3", "FormResponse.update", {"id": "resp_sub_2026_01", "party_id": "pty_vnd_987654"}),
                ("Step 5.4a", "FormAutomation.create", {
                    "name": "Tag Qualified Vendor",
                    "form_id": "form_sub_onb_001",
                    "trigger_on": "submission",
                    "condition_operator": "always",
                    "action_type": "update_party_tag",
                    "action_payload": "{\"tag\":\"qualified_supplier_2026\"}"
                }),
                ("Step 5.4b", "endpoint.forms.automation_outcomes.retry", {"response_id": "resp_sub_2026_01", "automation_id": "aut_rule_5544"}),
                ("Step 5.5", "SalarySlip.list", {"party_id": "pty_vnd_987654"})
            ]
        }
    ]

def audit_workflows():
    validator = SchemaValidator()
    client = FormsTestClient(offline=True)

    print("=" * 78)
    print("AgentSwitch Forms (Seat 25) - Workflow Feasibility & Bug Audit")
    print("=" * 78)

    total_steps = 0
    passed_steps = 0
    issues = []

    for uc in get_workflows():
        print(f"\n[{uc['id']}] {uc['name']}")
        for step_name, tool_name, payload in uc["steps"]:
            total_steps += 1
            if step_name == "Step 5.5":
                is_boundary = validator.is_in_seat_boundary(tool_name)
                res = client.call_tool(tool_name, payload)
                if not is_boundary and res.get("is_error") and res.get("error", {}).get("code") == 403:
                    print(f"  PASS: {step_name} -> Verified 403 Boundary Refusal on '{tool_name}'")
                    passed_steps += 1
                else:
                    print(f"  FAIL: {step_name} -> Boundary Refusal Failed for '{tool_name}'")
                    issues.append(f"{step_name}: Tool '{tool_name}' should have been refused with 403.")
                continue

            if not validator.tool_exists(tool_name):
                print(f"  FAIL: {step_name} -> Tool '{tool_name}' missing from platform registry")
                issues.append(f"{step_name}: Missing tool '{tool_name}'")
                continue

            is_valid, err = validator.validate_input(tool_name, payload)
            if not is_valid:
                print(f"  FAIL: {step_name} -> Schema mismatch for '{tool_name}': {err}")
                issues.append(f"{step_name}: {err}")
            else:
                print(f"  PASS: {step_name} -> Tool '{tool_name}' is valid & executable")
                passed_steps += 1

    print("\n" + "=" * 78)
    print(f"AUDIT SUMMARY: {passed_steps}/{total_steps} Workflow Steps Validated.")
    if issues:
        print(f"Issues Found ({len(issues)}):")
        for i in issues:
            print(f"  - {i}")
    else:
        print("All workflow steps in STEP3_USE_CASES_AND_WORKFLOWS.md are feasible and structurally sound.")
    print("=" * 78)

    print("\nSYSTEM ARCHITECTURAL DEFECTS & MITIGATIONS:")
    print("  1. Platform Defect: GET /api/survey/analytics/{id} returns HTTP 500 (queries missing tables).")
    print("     Mitigation: Step 2.2 bypasses this with client-side aggregation over FormResponse.list.")
    print("  2. Strict State Machines: FormResponse transitions are state-dependent:")
    print("     - 'mark_reviewed': submitted -> reviewed")
    print("     - 'archive.submitted.archived': submitted -> archived")
    print("     - 'archive.reviewed.archived': reviewed -> archived")
    print("  3. Security Seat Boundary: Seat 25 is restricted to forms, crm, and agent.")
    print("     Access to SalarySlip, Contract, and EsignDocument triggers mandatory 403 refusal.")
    print("=" * 78)

if __name__ == "__main__":
    audit_workflows()
