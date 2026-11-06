# AgentSwitch Forms Agent Harness (Seat 25: `forms`)

An autonomous agent harness repository for **Seat 25 (Forms)** on the **AgentSwitch** business platform, built following the official template of `agentswitch-harness-example`.

This harness executes on the AgentSwitch server when clicking **Our harness → Submit for a run**, and can also be run locally for testing and verification.

---

## 1. What the Runner Does

1. Checks out the exact commit on the saved branch in **Our harness**.
2. Runs `install` (`pip install -r requirements.txt`).
3. Runs `run` once per instance listed in `instances` (`suryodaya` and `keystone`) against a fresh copy of that instance.
4. Reads `results.json` and evaluates pass/fail per task and a score in the panel.

---

## 2. Platform Environment Variables

When running on the AgentSwitch test runner, no passwords or API keys are required:

| Variable | Use |
|---|---|
| `AGENTSWITCH_BASE_URL` | The tenant instance base URL (e.g. `POST $AGENTSWITCH_BASE_URL/api/mcp`) |
| `AGENTSWITCH_TOKEN` | Seat 25 bearer token: `Authorization: Bearer $AGENTSWITCH_TOKEN` |
| `AGENTSWITCH_INSTANCE` | Active business: `suryodaya` (India) or `keystone` (US) |
| `OPENAI_BASE_URL` | Platform LLM base URL (OpenAI-compatible) |
| `OPENAI_API_KEY` | Platform model authentication key |
| `OPENAI_MODEL` | Platform model name supporting tool calls |

---

## 3. Harness Specification (`agentswitch-harness.toml`)

```toml
install = "pip install -r requirements.txt"
run     = "python -m harness.runner"
results = "results.json"
instances = ["suryodaya", "keystone"]
timeout_minutes = 20
```

---

## 4. Evaluated Verification Tasks

The harness runs 9 end-to-end verification tasks on every run:

1. **`mcp_tools_list`**: MCP endpoint reachable with seat token, verifying Seat 25 tools (`Form.create`, `Form.list`, etc.).
2. **`team_harness_check`**: Direct tool invocation (`TeamHarness.get_mine` / `Form.list`).
3. **`jurisdiction_discovery`**: Probes `endpoint.storefront.locale` to detect accounting jurisdiction (`IN` / Ind AS / GST vs `US` / US GAAP).
4. **`schema_synthesis_uc01`**: Synthesizes region-compliant dynamic form schema (GSTIN, PAN, IFSC, MSME for India; EIN, W-9, ABA for US) with schema validation.
5. **`planner_graph_uc01`**: Assembles 5-step task graph DAG (`step_1_1_locale` -> `step_1_2_synthesize` -> `step_1_3_create_draft` -> `step_1_4_publish` -> `step_1_5_verify`).
6. **`autonomous_form_lifecycle_uc01`**: End-to-end UC-01 execution; creates draft, publishes, and reads back from database verifying live status and UI link.
7. **`mandatory_boundary_refusal`**: Strict seat boundary defense (§3, §8); verifies explicit refusal on payroll/salary slip prompts and 403 on forbidden tools.
8. **`agentic_model_loop`**: Model loop with tool calling using platform model or gateway fallback.
9. **`ui_chatbot_channel_integration`**: Verifies UI chatbot channel listener (`AgentSession.list`, `AgentMessage.list`, persona resolution).

---

## 5. Repository Structure

```
.
├── agentswitch-harness.toml     # AgentSwitch harness configuration
├── requirements.txt             # Runner dependencies
├── pyproject.toml               # Project metadata & pytest configuration
├── README.md                    # Documentation
├── harness/
│   ├── __init__.py
│   └── runner.py                # Main test harness runner producing results.json
├── agent/                       # Forms Agent (Seat 25)
│   ├── __init__.py
│   ├── chat_listener.py         # UI chatbot listener (AgentSession/AgentMessage)
│   ├── gateway.py               # Gateway LLM client with offline fallback
│   ├── main.py                  # CLI and server entry point
│   ├── planner.py               # 5-step DAG planner & boundary refusal logic
│   ├── runner.py                # Graph execution runner
│   ├── schema_builder.py        # Dynamic jurisdiction schema builder
│   └── ui_server.py             # Interactive FastAPI dashboard server
├── testing/                     # Client and schema validation framework
│   ├── __init__.py
│   ├── client.py                # MCP client (live JSON-RPC & offline mock)
│   ├── fixtures.py              # Test payloads & data builders
│   └── validator.py             # Schema validator & seat boundary checker
├── mcp_tools.json               # Seat 25 tool definitions & schemas
├── seat_info.json               # Seat 25 permissions and roles
├── static/
│   └── index.html               # Agent Web UI dashboard
└── tests/                       # Unit and integration test suite
    ├── conftest.py
    ├── test_agent_uc01_nl.py
    ├── test_harness_smoke.py
    └── test_payroll_message_privacy.py
```

---

## 6. How to Run Locally

### Run the Harness:
```bash
python -m harness.runner
# Or specify custom output path:
python -m harness.runner --out results.json
```

### Run the Test Suite:
```bash
pytest
```

### Run the Forms Agent CLI:
```bash
python -m agent.main "Build and publish our supplier onboarding form with compliance consent."
```

### Run the Interactive Web UI:
```bash
python -m agent.main --serve --port 8125
```
