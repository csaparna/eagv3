"""
Reusable test data builders and fixture payloads for Seat 25 (Forms).
"""

from typing import Any, Dict, List

class SampleDataBuilder:
    """Convenience builder to generate test payloads for all 5 use cases."""

    @staticmethod
    def dynamic_form_payload(country_code: str = "IN") -> Dict[str, Any]:
        """Builds a compliant Form.create payload based on country jurisdiction."""
        common_blocks = [
            {"ref_id": "blk_legal_name", "type": "short_text", "title": "Registered Legal Entity Name", "required": True},
            {"ref_id": "blk_contact_email", "type": "email", "title": "Contact Email", "required": True},
            {"ref_id": "blk_phone", "type": "phone", "title": "Business Telephone", "required": True},
        ]

        if country_code == "IN":
            tax_blocks = [
                {"ref_id": "blk_tax_gstin", "type": "short_text", "title": "GSTIN", "required": True},
                {"ref_id": "blk_tax_pan", "type": "short_text", "title": "PAN", "required": True},
                {"ref_id": "blk_msme_declared", "type": "boolean", "title": "MSME Registered?", "required": False},
                {"ref_id": "blk_msme_reg_no", "type": "short_text", "title": "Udyam Registration Number", "required": False},
                {"ref_id": "blk_bank_ifsc", "type": "short_text", "title": "Bank IFSC Code", "required": True},
            ]
        else:
            tax_blocks = [
                {"ref_id": "blk_tax_ein", "type": "short_text", "title": "Federal EIN / SSN", "required": True},
                {"ref_id": "blk_w9_certified", "type": "boolean", "title": "W-9 Tax Certification", "required": True},
                {"ref_id": "blk_bank_routing", "type": "short_text", "title": "ABA Routing Number", "required": True},
            ]

        return {
            "name": f"Supplier Onboarding & Compliance Intake - {country_code}",
            "slug": f"supplier-onboarding-{country_code.lower()}",
            "status": "draft",
            "presentation_mode": "multi_page",
            "consent_required": True,
            "consent_text": "I certify all tax and banking particulars are authentic.",
            "consent_lawful_basis": "consent",
            "blocks": common_blocks + tax_blocks,
            "logic_rules": []
        }

    @staticmethod
    def vendor_party_payload() -> Dict[str, Any]:
        """Builds a valid Party.create payload for CRM sync."""
        return {
            "name": "Apex Precision Components Pvt Ltd",
            "email": "accounts@apexprecision.in",
            "phone": "+91 98200 12345",
            "type": "organization",
            "contact_type": "vendor",
            "customer_sub_type": "business",
            "gst_treatment": "business_gst",
            "place_of_supply": "27-Maharashtra",
            "is_msme": True,
            "msme_type": "small",
            "vendor_bank_name": "Axis Bank",
            "vendor_bank_code": "UTIB0000123"
        }

    @staticmethod
    def form_automation_payload(form_id: str) -> Dict[str, Any]:
        """Builds a valid FormAutomation.create payload."""
        return {
            "name": "Tag Onboarded Supplier as Qualified Vendor",
            "form_id": form_id,
            "trigger_on": "submission",
            "condition_operator": "always",
            "action_type": "update_party_tag",
            "action_payload": '{"tag":"qualified_supplier_2026"}'
        }
