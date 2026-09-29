# AgentSwitch — Forms Agent (Seat 25: `forms`)

An autonomous, multi-jurisdiction AI agent for **Seat 25 (Forms)** on the **AgentSwitch** business platform. The agent plans and executes end-to-end form authoring, response analytics, cryptographic consent management, and CRM synchronization over Model Context Protocol (MCP) JSON-RPC 2.0, with full support for the AgentSwitch web UI chatbot, local web dashboard, and strict seat privacy boundaries.

---

## 1. Domain Charter & Milestone Goal

- **Seat Ownership**: Seat 25 (`forms`)
- **Allowed Apps**: `forms`, `crm`, `agent`
- **Primary Milestone Request (§8)**:
  > *"Build a supplier onboarding form, and summarise what came back this week."*
- **Jurisdictions Supported**:
  1. **Suryodaya Precision Works** (India): Ind AS, GSTIN (15-digit), PAN (10-digit), Bank IFSC, MSME/Udyam compliance, DPDP consent.
  2. **Keystone Precision Works LLC** (United States): US GAAP, EIN (9-digit), W-9 filing verification, ABA routing transit numbers, state sales tax exemptions, CCPA/privacy consent.

---

## 2. Architecture & Key Features

```
                              ┌──────────────────────────────────────────────┐
                              │            Natural Language Asks             │
                              │  (CLI Prompt / Web UI Chatbot / Local UI)     │
                              └──────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
┌────────────────────────┐         ┌───────────────────────────────────┐
│ Local Web Dashboard    │         │       Forms Task Planner          │
│ (FastAPI + HTML5 UI)   │◄────────┤   - Dynamic 5-step task graph     │
│ http://127.0.0.1:8125  │         │   - Verified boundary refusal     │
└────────────────────────┘         └─────────────────┬─────────────────┘
                                                     │
                                                     ▼
┌────────────────────────┐         ┌───────────────────────────────────┐
│ Jurisdiction Adapter   │         │       Forms Agent Runner          │
│ Schema Builder         ├────────►│   - Executes task graph nodes     │
│ (India GST vs US GAAP) │         │   - Computes rolling 7-day KPIs   │
└────────────────────────┘         └─────────────────┬─────────────────┘
                                                     │
                                                     ▼
                                   ┌───────────────────────────────────┐
                                   │   AgentSwitch MCP Interface       │
                                   │   POST $AS/api/mcp (JSON-RPC 2.0) │
                                   └─────────────────┬─────────────────┘
                                                     │
                   ┌─────────────────────────────────┴─────────────────────────────────┐
                   ▼                                                                   ▼
       [Forms App Operations]                                              [Private Agent Space]
  Form.create / Form.update / Form.get                                AgentSession / AgentMessage
  FormResponse.list / mark_reviewed                                   AgentMemory / AgentSkill
  endpoint.forms.consent_receipt.issue                                Boundary 403 Checks
```

- **Dynamic Schema Builder (`agent/schema_builder.py`)**:
  Probes `endpoint.storefront.locale` or `GET /api/accounting/locale` and programmatically synthesizes a compliant 10+ block form with regional input validations, conditional logic rules, and cryptographic consent declarations.
- **Task Graph Planner (`agent/planner.py`)**:
  Translates unstructured natural language into structured, executable graphs (`step_1_1_locale` → `step_1_2_synthesize` → `step_1_3_create_draft` → `step_1_4_publish` → `step_1_5_verify`).
- **Strict Seat Privacy Enforcement (§3, §8)**:
  Enforces a strict boundary against cross-seat data access. Natural language prompts or tool calls attempting to read Payroll records (`SalarySlip`, `PayrollEntry`), Contracts, or other seats private chat messages are rejected with formal 403 Forbidden envelopes.
- **Web UI Chatbot Listener (`agent/chat_listener.py`)**:
  Polls active user sessions (`AgentSession.list`), fetches incoming messages (`AgentMessage.list`), executes the requested workflow, and writes the assistant response directly back to the session.
- **Local Web Dashboard (`agent/ui_server.py`)**:
  FastAPI server serving an interactive dashboard (`static/index.html`) with real-time execution graphs, node states, and direct links to live published forms.

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Virtual environment (`.venv`)

### Installation
From the repository root or inside `AgentSwitchForms/`:

```bash
cd AgentSwitchForms

# If creating a fresh virtual environment:
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
# Or using uv:
# uv sync
```

### Environment Configuration (for Live Mode)
To connect to the live AgentSwitch platform, set your tenant URL and session bearer token in your environment:

```bash
# For Suryodaya (India)
export AS="https://agentswitch.theschoolofai.in"

# Or for Keystone (US)
# export AS="https://class.agentswitch.theschoolofai.in"

# Login and export Bearer token
export TOKEN=$(curl -s -X POST "$AS/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"team25@theschoolofai.in\",\"password\":\"YOUR_PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[\"token\"])")
```

*(Note: When `$AS` and `$TOKEN` are not set, the agent seamlessly operates in offline/mock mode for local development and test execution.)*

---

## 4. How to Run the Agent

### Mode A: Interactive Web UI Dashboard (Recommended)

Start the local web server to launch the visual dashboard:

```bash
cd AgentSwitchForms
.venv/bin/python -m agent.main --serve --port 8125
```

Open your browser to:
```
http://127.0.0.1:8125
```

Features available in the dashboard:
- **Interactive Natural Language Prompting**: Run custom asks or click sample prompts (UC-01 Form Authoring, Refusal Test, Weekly Audit).
- **Live Task Graph Visualization**: Watch task nodes transition dynamically from `pending` → `running` → `success`.
- **Live Form URL**: Directly preview the published form in AgentSwitch (`/p/form/{slug}`).
- **UI Chat Bot Polling**: Trigger polling of active chat sessions from the AgentSwitch main shell.

---

### Mode B: Direct CLI Natural Language Execution

Run a one-off natural language instruction directly from your terminal:

```bash
cd AgentSwitchForms

# 1. Author and activate a supplier onboarding form:
.venv/bin/python -m agent.main "Build and publish our supplier onboarding form with compliance consent."

# 2. Test verified seat refusal on out-of-scope payroll data:
.venv/bin/python -m agent.main "Retrieve the salary slips and compensation details for our suppliers."
```

Example CLI Output:
```text
Executing ask: Build and publish our supplier onboarding form with compliance consent.

--- Execution Result ---
Success: True
Is Refusal: False
Reply: Successfully authored and published 'Supplier Onboarding & Compliance Intake - 2026' (ID: form_sub_onb_001). Configured with 10 jurisdiction blocks. View live on UI at: https://agentswitch.theschoolofai.in/p/form/supplier-onboarding-2026
Live Form UI: https://agentswitch.theschoolofai.in/p/form/supplier-onboarding-2026
```

---

### Mode C: Poll AgentSwitch UI Chatbot Sessions

Poll the live AgentSwitch chat bot (`AgentSession` and `AgentMessage`) for questions submitted by users in the main app shell:

```bash
cd AgentSwitchForms
.venv/bin/python -m agent.main --poll-chat
```

The agent resolves the Forms persona, fetches the newest user message, executes the task graph, and posts the reply back to the session transcript.

---

## 5. Running the Test Suite

The test suite validates dynamic schema authoring, planner graph assembly, seat privacy boundary enforcement, chatbot listeners, and API endpoints without requiring external network access.

Run all tests via pytest:

```bash
cd AgentSwitchForms
.venv/bin/pytest -v
```

Run specific test modules:
```bash
# 1. Test UC-01 Natural Language Planning & Execution
.venv/bin/pytest tests/test_agent_uc01_nl.py -v

# 2. Test Payroll Chat Message Privacy & Refusal (§3, §8)
.venv/bin/pytest tests/test_payroll_message_privacy.py -v

# 3. Test Harness Schema Validation & Smoke Tests
.venv/bin/pytest tests/test_harness_smoke.py -v
```

Expected output:
```text
========================== test session starts ==========================
tests/test_agent_uc01_nl.py::test_schema_builder_india_jurisdiction PASSED
tests/test_agent_uc01_nl.py::test_schema_builder_us_jurisdiction PASSED
tests/test_agent_uc01_nl.py::test_planner_uc01_graph_assembly PASSED
tests/test_agent_uc01_nl.py::test_planner_boundary_refusal PASSED
tests/test_agent_uc01_nl.py::test_runner_execute_uc01 PASSED
tests/test_agent_uc01_nl.py::test_runner_boundary_refusal_execution PASSED
tests/test_agent_uc01_nl.py::test_ui_chatbot_listener_ingestion PASSED
tests/test_agent_uc01_nl.py::test_web_ui_server_endpoints PASSED
tests/test_harness_smoke.py::test_harness_client_initialization PASSED
tests/test_harness_smoke.py::test_validator_and_seat_refusal PASSED
tests/test_harness_smoke.py::test_sample_data_builder PASSED
tests/test_payroll_message_privacy.py::test_forms_seat_cannot_read_payroll_chat_message_via_mcp_get PASSED
tests/test_payroll_message_privacy.py::test_forms_seat_cannot_read_payroll_chat_message_via_rest_get PASSED
tests/test_payroll_message_privacy.py::test_chat_listener_get_methods_refuse_payroll_access PASSED
tests/test_payroll_message_privacy.py::test_forms_agent_refuses_natural_language_request_to_get_payroll_chat PASSED

===================== 15 passed in 0.68s =====================
```

---

## 6. Directory Structure

```
AgentSwitchForms/
├── README.md                      # This file (Agent execution and setup guide)
├── assignment.md                  # AgentSwitch course assignment & team brief
├── gap_report.md                  # Week 1 competitive gap report (vs Fillout/Feathery)
├── pyproject.toml                 # Package definition & pytest config
├── mcp_tools.json                 # Catalog of Seat 25 MCP tools and schemas
├── raw_schemas.json               # Full platform entity schemas
│
├── agent/                         # Core Autonomous Agent Package
│   ├── __init__.py                # Package exports
│   ├── main.py                    # CLI entrypoint (--serve, --poll-chat, prompt)
│   ├── runner.py                  # Task graph executor & event logging
│   ├── planner.py                 # NL prompt planner & boundary refusal engine
│   ├── schema_builder.py          # Dynamic jurisdiction schema generator (IN vs US)
│   ├── chat_listener.py           # AgentSwitch UI chatbot polling & reply poster
│   ├── ui_server.py               # FastAPI dashboard server
│   └── gateway.py                 # LLM Gateway client (glc_v4 integration)
│
├── static/
│   └── index.html                 # Interactive Web UI Dashboard
│
├── testing/                       # Testing Harness & Platform Clients
│   ├── client.py                  # FormsTestClient (Live MCP JSON-RPC + Offline mock)
│   ├── validator.py               # SchemaValidator & boundary refusal assertions
│   └── fixtures.py                # Sample payload builder for IN and US
│
└── tests/                         # Automated Pytest Test Suite
    ├── conftest.py                # Pytest fixtures and assertion helpers
    ├── test_agent_uc01_nl.py      # End-to-end tests for natural language UC-01
    ├── test_payroll_message_privacy.py # Strict cross-seat privacy tests (§3, §8)
    └── test_harness_smoke.py      # Harness verification and smoke tests
```
