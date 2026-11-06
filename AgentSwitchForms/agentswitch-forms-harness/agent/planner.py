"""
Live Task Graph Planner for Seat 25 Forms Agent.
Translates natural language questions/requests into inspectable, step-by-step DAGs for Use Case 1 (UC-01)
or produces clear seat boundary refusals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentTaskNode:
    """Represents a discrete node in the agent's task execution graph."""
    node_id: str
    tool_name: str
    description: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    state: str = "queued"  # queued, running, success, failed, skipped
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AgentPlan:
    """The complete execution plan derived from the user's natural language input."""
    goal: str
    use_case: str
    nodes: List[AgentTaskNode]
    is_refusal: bool = False
    refusal_reason: Optional[str] = None


class FormsTaskPlanner:
    """Plans UC-01 execution or enforces boundary refusals."""

    FORBIDDEN_PATTERNS = [
        (r"\b(salary\s*slips?|payroll|compensation|wages?)\b", "SalarySlip", "Payroll (Seats 12 & 13)"),
        (r"\b(contracts?|clauses?|nda|legal\s*agreements?)\b", "Contract", "Contracts (Seat 17)"),
        (r"\b(esign|signatures?\s*evidence|signed\s*docs?)\b", "EsignDocument", "E-sign (Seat 18)"),
        (r"\b(journal\s*entry|ledger\s*raw|bank\s*accounts?)\b", "JournalEntry", "Ledger (Seats 01, 02 & 03)"),
    ]

    def plan(self, prompt: str) -> AgentPlan:
        """Analyzes prompt and returns either a UC-01 task DAG or a verified boundary refusal."""
        prompt_lower = prompt.lower()

        # 1. Check for unauthorized cross-seat boundaries (§3, §8)
        for pattern, entity, domain_owner in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt_lower):
                return AgentPlan(
                    goal=prompt,
                    use_case="REFUSAL",
                    nodes=[],
                    is_refusal=True,
                    refusal_reason=(
                        f"REFUSAL: Forbidden request for '{entity}'. Seat 25 (forms) holds authorization "
                        f"only for 'forms', 'crm', and 'agent' workspaces. Accessing '{entity}' falls strictly under "
                        f"{domain_owner}. Please escalate to an Administrator."
                    ),
                )

        # 2. Extract potential custom form title from quotes if present
        title_match = re.search(r"['\"]([^'\"]*form[^'\"]*)['\"]", prompt, re.IGNORECASE)
        custom_title = title_match.group(1) if title_match else "Supplier Onboarding & Compliance Intake - 2026"

        slug = re.sub(r"[^a-z0-9]+", "-", custom_title.lower()).strip("-")

        # 3. Assemble UC-01 Task Graph
        nodes = [
            AgentTaskNode(
                node_id="step_1_1_locale",
                tool_name="endpoint.storefront.locale",
                description="Probe active corporate accounting jurisdiction (Suryodaya IN vs Keystone US).",
                arguments={},
            ),
            AgentTaskNode(
                node_id="step_1_2_synthesize",
                tool_name="local.schema_synthesis",
                description="Synthesize dynamic region-compliant form blocks and logic rules.",
                arguments={"title": custom_title, "slug": slug},
            ),
            AgentTaskNode(
                node_id="step_1_3_create_draft",
                tool_name="Form.create",
                description="Create the multi-block supplier onboarding form record in draft state.",
                arguments={},  # Will be populated with output from step_1_2
            ),
            AgentTaskNode(
                node_id="step_1_4_publish",
                tool_name="Form.update",
                description="Transition the form status to 'published' so it becomes live on the UI.",
                arguments={"status": "published"},
            ),
            AgentTaskNode(
                node_id="step_1_5_verify",
                tool_name="Form.get",
                description="Verify published state, block persistence, and database invariants.",
                arguments={},
            ),
        ]

        return AgentPlan(
            goal=prompt,
            use_case="UC-01: Autonomous Dynamic Supplier Onboarding Form Authoring & Activation",
            nodes=nodes,
        )
