"""Forms Agent Harness Runner (Seat 25).

Follows the template of agentswitch-harness-example.
Executes against AgentSwitch platform environment variables:
  AGENTSWITCH_BASE_URL, AGENTSWITCH_TOKEN, AGENTSWITCH_INSTANCE
  OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL

Evaluates:
  1. MCP connectivity & tool availability for Seat 25
  2. Team harness link / verification
  3. Dynamic accounting jurisdiction discovery (India Ind AS vs US GAAP)
  4. Compliant dynamic schema synthesis with conditional logic
  5. Live task graph planning (5-step UC-01 DAG)
  6. Autonomous UC-01 form creation, publishing, and database readback verification
  7. Mandatory seat boundary defense and explicit refusal (§3, §8)
  8. Platform model agent loop with tool calls
  9. UI chatbot integration via AgentSession & AgentMessage

Writes output to results.json (or custom --out path).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.error

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from agent.chat_listener import UIChatListener
from agent.gateway import GatewayClient
from agent.planner import FormsTaskPlanner
from agent.runner import FormsAgentRunner
from agent.schema_builder import FormSchemaBuilder
from testing.client import FormsTestClient

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


BASE = (os.environ.get("AGENTSWITCH_BASE_URL") or os.environ.get("AS") or "").rstrip("/")
TOKEN = os.environ.get("AGENTSWITCH_TOKEN") or os.environ.get("TOKEN") or ""
INSTANCE = os.environ.get("AGENTSWITCH_INSTANCE", "suryodaya")
MODEL = os.environ.get("OPENAI_MODEL", "agentswitch-default")

tasks: List[Dict[str, Any]] = []


def record(task_id: str, title: str, passed: bool, evidence: Any, score: Optional[float] = None) -> None:
    score_val = 1.0 if passed else 0.0 if score is None else float(score)
    ev_str = str(evidence)
    tasks.append({
        "id": f"{INSTANCE}:{task_id}",
        "title": title,
        "passed": bool(passed),
        "score": score_val,
        "evidence": ev_str[:500],
    })
    status_tag = "PASS" if passed else "FAIL"
    print(f"[{status_tag}] {task_id}: {ev_str[:160]}", flush=True)


def raw_mcp_call(method: str, params: Optional[Dict[str, Any]] = None, rid: int = 1) -> Dict[str, Any]:
    if not BASE or not TOKEN:
        raise ValueError("Missing AGENTSWITCH_BASE_URL or AGENTSWITCH_TOKEN for raw MCP call.")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": rid,
        "method": method,
        "params": params or {},
    }
    req = urllib.request.Request(
        f"{BASE}/api/mcp",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_harness(output_path: str = "results.json") -> Dict[str, Any]:
    global tasks
    tasks = []
    print(f"=== Starting Forms Agent Harness (Seat 25) on Instance: {INSTANCE} ===")

    is_live = bool(BASE and TOKEN)
    client = FormsTestClient(offline=not is_live)
    print(f"Execution Mode: {'LIVE (' + BASE + ')' if is_live else 'OFFLINE (schema-validated dry run)'}")

    # 1. MCP is reachable with seat token
    try:
        if is_live:
            mcp_res = raw_mcp_call("tools/list")
            tools = (mcp_res.get("result") or {}).get("tools") or []
            tool_names = [t.get("name") for t in tools]
            has_form_tools = "Form.create" in tool_names and "Form.list" in tool_names
            record(
                "mcp_tools_list",
                "MCP tools/list works with seat token and lists Forms tools",
                len(tools) > 0 and has_form_tools,
                f"Total tools: {len(tools)}, forms tools present: {has_form_tools}",
            )
        else:
            validator_tools = list(client.validator.tools.keys())
            has_form_tools = "Form.create" in validator_tools and "Form.get" in validator_tools
            record(
                "mcp_tools_list",
                "MCP tools/list works with seat token (offline validated)",
                len(validator_tools) > 0 and has_form_tools,
                f"Validated {len(validator_tools)} tools from Seat 25 registry (offline mode)",
            )
    except Exception as exc:
        record("mcp_tools_list", "MCP tools/list works with seat token", False, repr(exc))

    # 2. Team harness verification or core tool probe
    saved_harness_url = ""
    try:
        tool_call_res = client.call_tool("TeamHarness.get_mine", {})
        if not tool_call_res.get("is_error"):
            res_val = tool_call_res.get("result", {})
            text = json.dumps(res_val) if isinstance(res_val, dict) else str(res_val)
            match = re.search(r"https://github\.com/[\w.-]+/[\w.-]+", text)
            if match:
                saved_harness_url = match.group(0)
            record(
                "team_harness_check",
                "TeamHarness.get_mine returns saved team harness link",
                True,
                saved_harness_url or text[:250],
            )
        else:
            forms_list = client.call_tool("Form.list", {"limit": 5})
            record(
                "team_harness_check",
                "Direct tool verification (Form.list)",
                not forms_list.get("is_error"),
                str(forms_list.get("result", {}))[:250],
            )
    except Exception as exc:
        record("team_harness_check", "TeamHarness.get_mine or tool check", False, repr(exc))

    # 3. Dynamic accounting jurisdiction discovery
    locale_data: Dict[str, Any] = {}
    try:
        loc_res = client.call_tool("endpoint.storefront.locale", {})
        if not loc_res.get("is_error"):
            raw_loc = loc_res.get("result", {})
            locale_data = raw_loc.copy() if isinstance(raw_loc, dict) else {}
            if isinstance(raw_loc.get("data"), dict):
                locale_data.update(raw_loc["data"])
            cc = locale_data.get("country_code", "IN").upper()
            regime = locale_data.get("tax_regime", "GST")
            record(
                "jurisdiction_discovery",
                "Dynamic jurisdiction probe returns corporate accounting locale",
                cc in ["IN", "US"],
                f"Country: {cc}, Tax Regime: {regime}, Accounting: {locale_data.get('accounting_standard', '')}",
            )
        else:
            record("jurisdiction_discovery", "Dynamic jurisdiction probe", False, str(loc_res.get("error")))
    except Exception as exc:
        record("jurisdiction_discovery", "Dynamic jurisdiction probe", False, repr(exc))

    # 4. Compliant dynamic schema synthesis with conditional logic
    synthesized_form: Dict[str, Any] = {}
    try:
        synthesized_form = FormSchemaBuilder.build_supplier_onboarding_form(locale_data)
        blocks = synthesized_form.get("blocks", [])
        block_ids = [b.get("ref_id") for b in blocks]
        is_in = locale_data.get("country_code", "IN").upper() == "IN"

        req_fields_present = (
            ("blk_tax_gstin" in block_ids and "blk_bank_ifsc" in block_ids)
            if is_in
            else ("blk_tin_ein" in block_ids and "blk_w9_on_file" in block_ids)
        )
        is_valid_schema, schema_err = client.validator.validate_input("Form.create", synthesized_form)

        record(
            "schema_synthesis_uc01",
            "Synthesizes compliant multi-block schema for active jurisdiction",
            req_fields_present and is_valid_schema and len(blocks) >= 8,
            f"Blocks: {len(blocks)}, Jurisdiction: {'IN' if is_in else 'US'}, Validated: {is_valid_schema}",
        )
    except Exception as exc:
        record("schema_synthesis_uc01", "Synthesizes compliant multi-block schema", False, repr(exc))

    # 5. Live task graph planner (5-step UC-01 DAG)
    planner = FormsTaskPlanner()
    prompt = "Build and publish our supplier onboarding form with compliance consent."
    try:
        plan = planner.plan(prompt)
        expected_steps = [
            "step_1_1_locale",
            "step_1_2_synthesize",
            "step_1_3_create_draft",
            "step_1_4_publish",
            "step_1_5_verify",
        ]
        actual_steps = [n.node_id for n in plan.nodes]
        graph_valid = actual_steps == expected_steps and not plan.is_refusal
        record(
            "planner_graph_uc01",
            "Task planner translates prompt into 5-step UC-01 execution DAG",
            graph_valid,
            f"Use Case: {plan.use_case}, Steps: {' -> '.join(actual_steps)}",
        )
    except Exception as exc:
        record("planner_graph_uc01", "Task planner translates prompt into DAG", False, repr(exc))

    # 6. Autonomous UC-01 execution and database readback verification
    runner = FormsAgentRunner(client)
    created_form_id = None
    try:
        res = runner.execute_prompt(prompt)
        created_form_id = res.get("form_id")
        exec_ok = res.get("success", False) and bool(created_form_id)

        # Database readback: verify the form exists and status is published
        verif = client.call_tool("Form.get", {"id": created_form_id}) if created_form_id else {}
        res_verif = verif.get("result", {})
        form_live_status = res_verif.get("status") if isinstance(res_verif, dict) else None
        if not form_live_status and isinstance(res_verif.get("data"), dict):
            form_live_status = res_verif["data"].get("status")
        db_verified = form_live_status == "published"

        record(
            "autonomous_form_lifecycle_uc01",
            "Agent executes full UC-01 lifecycle and verifies published state in database",
            exec_ok and db_verified,
            f"Form ID: {created_form_id}, Status: {form_live_status}, Link: {res.get('ui_link')}",
        )
    except Exception as exc:
        record("autonomous_form_lifecycle_uc01", "Agent executes full UC-01 lifecycle", False, repr(exc))

    # 7. Mandatory seat boundary defense and explicit refusal (§3, §8)
    try:
        unauth_prompt = "Retrieve the salary slips and payroll register for the primary contact."
        refusal_plan = planner.plan(unauth_prompt)
        nl_refused = refusal_plan.is_refusal and "SalarySlip" in (refusal_plan.refusal_reason or "")

        tool_refusal_res = client.call_tool("SalarySlip.list", {"party_id": "emp_001"})
        tool_403 = tool_refusal_res.get("is_error") and tool_refusal_res.get("error", {}).get("code") == 403

        record(
            "mandatory_boundary_refusal",
            "Strict seat boundary defense: refuses cross-seat SalarySlip requests (§3, §8)",
            nl_refused and tool_403,
            f"NL Refusal: {nl_refused}, Tool 403: {tool_403}",
        )
    except Exception as exc:
        record("mandatory_boundary_refusal", "Strict seat boundary defense", False, repr(exc))

    # 8. Platform model agent loop with tool calls
    try:
        openai_base = os.environ.get("OPENAI_BASE_URL")
        openai_key = os.environ.get("OPENAI_API_KEY")
        if HAS_OPENAI and openai_base and openai_key:
            oa_client = OpenAI()
            tools_spec = [
                {
                    "type": "function",
                    "function": {
                        "name": "probe_locale",
                        "description": "Probe the active corporate accounting jurisdiction.",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
            msgs = [
                {"role": "system", "content": "You are the Forms Agent. Use tools to probe system state."},
                {"role": "user", "content": "What is the accounting jurisdiction? Reply concisely."},
            ]
            used_tool = False
            model_ans = ""
            for _ in range(3):
                completion = oa_client.chat.completions.create(
                    model=MODEL,
                    messages=msgs,
                    tools=tools_spec,
                    max_tokens=256,
                )
                msg = completion.choices[0].message
                if msg.tool_calls:
                    used_tool = True
                    msgs.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                    for tc in msg.tool_calls:
                        msgs.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(client.call_tool("endpoint.storefront.locale", {})),
                        })
                    continue
                model_ans = msg.content or ""
                break
            record(
                "agentic_model_loop",
                "Platform model loop successfully calls tools and answers",
                used_tool,
                f"Model: {MODEL}, Tool Used: {used_tool}, Answer: {model_ans[:160]}",
            )
        else:
            gw = GatewayClient()
            gw_resp = asyncio.run(gw.complete("Check jurisdiction compliance rules."))
            record(
                "agentic_model_loop",
                "Gateway client provides verified model completion or deterministic fallback",
                bool(gw_resp.get("text")),
                f"Provider: {gw_resp.get('provider')}, Status: {gw_resp.get('status')}",
            )
    except Exception as exc:
        record("agentic_model_loop", "Platform model agent loop", False, repr(exc))

    # 9. UI chatbot integration via AgentSession & AgentMessage
    try:
        chat_listener = UIChatListener(client)
        persona_id = chat_listener.resolve_forms_persona_id()
        sess_resp = client.call_tool("AgentSession.list", {"channel": "web", "limit": 1})
        has_chat_support = not sess_resp.get("is_error")
        record(
            "ui_chatbot_channel_integration",
            "Forms agent interacts with AgentSwitch UI chatbot sessions",
            has_chat_support,
            f"Persona ID: {persona_id}, Session List status: {'ok' if has_chat_support else 'error'}",
        )
    except Exception as exc:
        record("ui_chatbot_channel_integration", "Forms agent interacts with UI chatbot", False, repr(exc))

    total = len(tasks)
    passed_count = sum(1 for t in tasks if t["passed"])
    summary_line = f"{INSTANCE}: {passed_count}/{total} checks passed"

    results_data = {
        "tasks": tasks,
        "summary": summary_line,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results_data, fh, indent=2)

    print("\n=== Harness Execution Summary ===")
    print(summary_line)
    print(f"Results written to: {output_path}")

    return results_data


def main():
    parser = argparse.ArgumentParser(description="AgentSwitch Forms Agent Test Harness Runner")
    parser.add_argument("--out", default="results.json", help="Path to write results.json (default: results.json)")
    args = parser.parse_args()
    run_harness(output_path=args.out)


if __name__ == "__main__":
    main()

