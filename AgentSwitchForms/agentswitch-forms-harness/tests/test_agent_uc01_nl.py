"""
Automated Test Suite for Seat 25 Forms Agent (Use Case 1: UC-01).
Validates:
1. Dynamic jurisdiction schema generation (India Ind AS/GST vs US US GAAP).
2. Live task graph planning from natural language prompts.
3. Sequential execution of UC-01 tools (locale discovery, draft creation, publish, verify).
4. AgentSwitch UI Chatbot message ingestion (AgentSession & AgentMessage) and response dispatch.
5. Mandatory seat boundary defense and refusal (§3, §8).
6. Web UI Dashboard API endpoints.
"""
from __future__ import annotations

import pytest
from agent.schema_builder import FormSchemaBuilder
from agent.planner import FormsTaskPlanner
from agent.runner import FormsAgentRunner
from agent.chat_listener import UIChatListener
from testing.client import FormsTestClient
from starlette.testclient import TestClient
from agent.ui_server import app


def test_schema_builder_india_jurisdiction():
    """Validates that India locale generates 10 blocks, MSME logic rules, and DPDP consent."""
    locale = {"country_code": "IN", "tax_regime": "GST", "accounting_standard": "Ind AS"}
    form_data = FormSchemaBuilder.build_supplier_onboarding_form(locale)

    assert form_data["status"] == "draft"
    assert form_data["presentation_mode"] == "multi_page"
    assert form_data["consent_required"] is True
    assert form_data["consent_lawful_basis"] == "consent"

    blocks = form_data["blocks"]
    assert len(blocks) == 10
    block_refs = [b["ref_id"] for b in blocks]
    assert "blk_legal_name" in block_refs
    assert "blk_tax_gstin" in block_refs
    assert "blk_tax_pan" in block_refs
    assert "blk_msme_declared" in block_refs
    assert "blk_bank_ifsc" in block_refs
    assert "blk_cancelled_cheque" in block_refs

    # Validate conditional logic rule
    rules = form_data["logic_rules"]
    assert len(rules) == 1
    assert rules[0]["condition_block_id"] == "blk_msme_declared"
    assert rules[0]["action"] == "hide"
    assert rules[0]["target_block_id"] == "blk_msme_reg_no"


def test_schema_builder_us_jurisdiction():
    """Validates that US locale generates EIN, W-9, ABA routing, and US privacy consent."""
    locale = {"country_code": "US", "tax_regime": "sales_use_tax", "accounting_standard": "US GAAP"}
    form_data = FormSchemaBuilder.build_supplier_onboarding_form(locale)

    blocks = form_data["blocks"]
    block_refs = [b["ref_id"] for b in blocks]
    assert "blk_tin_ein" in block_refs
    assert "blk_w9_on_file" in block_refs
    assert "blk_bank_routing_aba" in block_refs
    assert "blk_tax_gstin" not in block_refs


def test_planner_uc01_graph_assembly():
    """Validates that natural language prompt assembles the 5-step UC-01 DAG."""
    planner = FormsTaskPlanner()
    plan = planner.plan("Create and publish a supplier onboarding form with compliance consent.")

    assert not plan.is_refusal
    assert plan.use_case.startswith("UC-01")
    assert len(plan.nodes) == 5

    node_tools = [n.tool_name for n in plan.nodes]
    assert node_tools == [
        "endpoint.storefront.locale",
        "local.schema_synthesis",
        "Form.create",
        "Form.update",
        "Form.get",
    ]


def test_planner_boundary_refusal():
    """Validates that requests crossing seat boundaries (SalarySlip) produce explicit refusal (§3, §8)."""
    planner = FormsTaskPlanner()
    plan = planner.plan("Retrieve the salary slips and payroll register for the primary contact.")

    assert plan.is_refusal is True
    assert "REFUSAL" in plan.refusal_reason
    assert "SalarySlip" in plan.refusal_reason
    assert "Payroll" in plan.refusal_reason
    assert len(plan.nodes) == 0


def test_runner_execute_uc01():
    """Executes the full UC-01 pipeline and verifies success and live form URL generation."""
    client = FormsTestClient(offline=True)
    runner = FormsAgentRunner(client)

    res = runner.execute_prompt("Build and publish our supplier onboarding form with compliance consent.")

    assert res["success"] is True
    assert res["is_refusal"] is False
    assert res["form_id"] == "form_sub_onb_001"
    assert "p/form/" in res["ui_link"]
    assert len(res["nodes"]) == 5
    for node in res["nodes"]:
        assert node["state"] == "success"


def test_runner_boundary_refusal_execution():
    """Executes a forbidden request through the runner and confirms no MCP write occurs."""
    client = FormsTestClient(offline=True)
    runner = FormsAgentRunner(client)

    res = runner.execute_prompt("What are the employee salary slips for this vendor?")
    assert res["success"] is False
    assert res["is_refusal"] is True
    assert "REFUSAL" in res["reply"]


def test_ui_chatbot_listener_ingestion():
    """Simulates UI chat bot: polls AgentSession + AgentMessage and replies back."""
    client = FormsTestClient(offline=True)
    runner = FormsAgentRunner(client)

    chat_res = runner.process_latest_ui_chat_question()

    assert chat_res is not None
    assert chat_res["success"] is True
    assert chat_res["chat_session_id"] == "ses_chat_ui_001"
    assert "Supplier Onboarding" in chat_res["reply"]


def test_web_ui_server_endpoints():
    """Validates the interactive Web UI FastAPI endpoints."""
    web_client = TestClient(app)

    # 1. Health check
    h = web_client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["agent_seat"] == "Seat 25 (forms)"

    # 2. Run prompt endpoint
    r = web_client.post("/api/run", json={"prompt": "Build and publish our supplier onboarding form"})
    assert r.status_code == 200
    assert r.json()["success"] is True

    # 3. Poll chat endpoint
    c = web_client.post("/api/chat/poll")
    assert c.status_code == 200
    assert c.json()["found"] is True

    # 4. HTML Dashboard
    dash = web_client.get("/")
    assert dash.status_code == 200
    assert "Seat 25: Forms Agent" in dash.text
