"""
Dynamic Jurisdiction Schema Builder for Forms Seat (Seat 25).
Synthesizes region-specific supplier onboarding forms tailored to active jurisdiction (India Ind AS vs US GAAP).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class FormSchemaBuilder:
    """Constructs compliant multi-block Form payloads based on accounting locale."""

    @staticmethod
    def build_supplier_onboarding_form(
        locale_data: Dict[str, Any],
        title: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        country = locale_data.get("country_code", "IN").upper()
        tax_regime = locale_data.get("tax_regime", "GST").upper()
        is_india = (country == "IN" or "GST" in tax_regime)

        if is_india:
            return FormSchemaBuilder._build_india_schema(title, slug)
        return FormSchemaBuilder._build_us_schema(title, slug)

    @staticmethod
    def _build_india_schema(title: Optional[str], slug: Optional[str]) -> Dict[str, Any]:
        blocks: List[Dict[str, Any]] = [
            {"ref_id": "blk_legal_name", "type": "short_text", "title": "Registered Legal Entity Name", "required": True},
            {"ref_id": "blk_contact_email", "type": "email", "title": "Accounts Receivable / Compliance Email", "required": True},
            {"ref_id": "blk_phone", "type": "phone", "title": "Business Contact Telephone", "required": True},
            {"ref_id": "blk_tax_gstin", "type": "short_text", "title": "Goods & Services Tax Identification Number (GSTIN)", "description": "15-digit alphanumeric tax identifier.", "required": True},
            {"ref_id": "blk_tax_pan", "type": "short_text", "title": "Permanent Account Number (PAN)", "description": "10-digit entity PAN.", "required": True},
            {"ref_id": "blk_msme_declared", "type": "boolean", "title": "MSME / Udyam Registered Entity?", "required": False},
            {"ref_id": "blk_msme_reg_no", "type": "short_text", "title": "Udyam Registration Certificate Number", "required": False},
            {"ref_id": "blk_bank_account", "type": "short_text", "title": "Remittance Bank Account Number", "required": True},
            {"ref_id": "blk_bank_ifsc", "type": "short_text", "title": "Bank Branch IFSC Code", "description": "11-digit alphanumeric branch identifier.", "required": True},
            {"ref_id": "blk_cancelled_cheque", "type": "file_upload", "title": "Bank Proof / Cancelled Cheque PDF", "required": True},
        ]
        logic_rules: List[Dict[str, Any]] = [
            {"condition_block_id": "blk_msme_declared", "condition_operator": "equals", "condition_value": "false", "action": "hide", "target_block_id": "blk_msme_reg_no"}
        ]
        return {
            "name": title or "Supplier Onboarding & Compliance Intake - 2026",
            "slug": slug or "supplier-onboarding-2026",
            "status": "draft",
            "presentation_mode": "multi_page",
            "description": "Standard compliance, tax, and banking onboarding intake for industrial procurement partners in India (Ind AS / GST / DPDP compliant).",
            "consent_required": True,
            "consent_text": "I certify that all tax declarations, banking particulars, and identification documents are authentic and lawful under applicable trade regulations.",
            "consent_lawful_basis": "consent",
            "blocks": blocks,
            "logic_rules": logic_rules,
        }

    @staticmethod
    def _build_us_schema(title: Optional[str], slug: Optional[str]) -> Dict[str, Any]:
        blocks: List[Dict[str, Any]] = [
            {"ref_id": "blk_legal_name", "type": "short_text", "title": "Registered Legal Entity Name", "description": "Full corporate trade name as filed with the IRS.", "required": True},
            {"ref_id": "blk_contact_email", "type": "email", "title": "Accounts Receivable / Remittance Email", "required": True},
            {"ref_id": "blk_phone", "type": "phone", "title": "Business Contact Telephone", "required": True},
            {"ref_id": "blk_tin_ein", "type": "short_text", "title": "Federal Employer Identification Number (EIN / SSN)", "description": "9-digit US Federal Tax ID (XX-XXXXXXX).", "required": True},
            {"ref_id": "blk_w9_on_file", "type": "boolean", "title": "Form W-9 Signed and on File?", "required": True},
            {"ref_id": "blk_tax_exemption_cert", "type": "file_upload", "title": "State Resale / Tax Exemption Certificate PDF", "required": False},
            {"ref_id": "blk_bank_account", "type": "short_text", "title": "ACH Remittance Account Number", "required": True},
            {"ref_id": "blk_bank_routing_aba", "type": "short_text", "title": "ABA 9-Digit Bank Routing Number", "description": "9-digit Fedwire / ACH routing number.", "required": True},
        ]
        return {
            "name": title or "Supplier Onboarding & Tax Intake - US GAAP 2026",
            "slug": slug or "supplier-onboarding-us-2026",
            "status": "draft",
            "presentation_mode": "multi_page",
            "description": "Standard US vendor intake, W-9 verification, and ACH banking details under US GAAP and Sales Tax rules.",
            "consent_required": True,
            "consent_text": "I certify that all federal tax representations, banking details, and trade documentation are authentic and lawful under US regulations.",
            "consent_lawful_basis": "consent",
            "blocks": blocks,
            "logic_rules": [],
        }
