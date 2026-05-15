"""
MCP Server for API Endpoint Discovery Agent.
Uses FastMCP to expose tools for fetching API docs, discovering endpoints,
and generating PostgreSQL schemas. The app tool (api_discovery) provides a
Prefab UI with two input fields: API doc URL and a question.

Run the server in development mode with inspector:
  $ fastmcp dev inspector mcp_server.py

Run the server as an app:
  $ fastmcp dev apps mcp_server.py
"""
import time
import json
import re
import os
import requests
from bs4 import BeautifulSoup
from google import genai
from dotenv import load_dotenv
from fastmcp import FastMCP
from prefab_ui.app import PrefabApp
from prefab_ui.components.column import Column
from prefab_ui.components.row import Row
from prefab_ui.components.data_table import DataTable, DataTableColumn
from prefab_ui.components.typography import H1, H2, H3, Muted, P
from prefab_ui.components.metric import Metric
from prefab_ui.components.alert import Alert, AlertTitle, AlertDescription
from prefab_ui.components.card import Card, CardHeader, CardContent, CardTitle
from prefab_ui.components.separator import Separator
from prefab_ui.components.badge import Badge

from models import DiscoveryRequest

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
THROTTLE_SECONDS = 2          # Agent loop throttle
TOOL_THROTTLE_SECONDS = 1     # Internal tool LLM calls (faster to avoid MCP timeout)

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

llm_client = genai.Client(api_key=GEMINI_API_KEY)

mcp = FastMCP("API Discovery Agent")


# ============================================================
# MCP Prompt — System prompt for the endpoint discovery agent
# ============================================================

@mcp.prompt()
def endpoint_discovery_prompt(api_doc_url: str, question: str) -> str:
    """System prompt that guides the LLM through API endpoint discovery."""
    return f"""You are an expert API analyst and data engineer. Your task is to analyze an API's
documentation and determine how to answer a specific question using data from that API.

The user has provided:
- API Documentation URL: {api_doc_url}
- Question: {question}

You have access to the following tools:

1. fetch_api_docs(url: str) -> str
   Fetches and parses the content of an API documentation page. Returns the text content.
   Always call this first with the provided URL.

2. discover_endpoints(api_doc_text: str, question: str) -> str
   Analyzes the API documentation text to identify all endpoints, determine which are relevant
   to the question, extract query parameters and response fields. Returns structured JSON.

3. check_endpoint_availability(base_url: str, endpoint_path: str, method: str) -> str
   Probes an endpoint to verify it's live and returning data. Use this to validate
   that the endpoints you identified actually work.

4. generate_pg_schema(endpoints_json: str, question: str) -> str
   Given the relevant endpoints and question, produces PostgreSQL CREATE TABLE DDL,
   recommended indexes, and transformation SQL.

5. plan_data_pipeline(endpoints_json: str, question: str, pg_schema: str) -> str
   Produces the final execution plan: how to query endpoints, pagination strategy,
   data transformations, and the SQL to answer the question.

MANDATORY WORKFLOW — You MUST complete ALL 5 steps before giving a final answer:
1. fetch_api_docs — fetch the documentation
2. discover_endpoints — analyze endpoints from the doc text
3. check_endpoint_availability — probe ONE relevant endpoint
4. generate_pg_schema — REQUIRED: produce the PostgreSQL table DDL
5. plan_data_pipeline — REQUIRED: produce the data pipeline and final SQL
6. ONLY THEN return your final answer

DO NOT return a final answer until you have called generate_pg_schema AND plan_data_pipeline.

You must respond in ONE of these two JSON formats:

If you need to use a tool:
{{"tool_name": "<name>", "tool_arguments": {{"<arg_name>": "<value>"}}}}

If you have the final answer (ONLY after completing all 5 tool calls):
{{"answer": "<your comprehensive final answer>"}}

IMPORTANT RULES:
- Respond with ONLY the JSON. No other text. No markdown code fences.
- Follow the workflow steps in order. Do NOT skip steps 4 or 5.
- After receiving a tool result, call the NEXT tool in the workflow.
- If a tool returns an error, note the limitation and move on to the next step.
- Do not repeat tool calls with the same arguments.
- Keep tool arguments concise — pass only the relevant endpoints JSON, not the full doc text.
"""


# ============================================================
# MCP Tools — called by the agent loop
# ============================================================
MAX_DOC_CHARS = 8000  # Max chars to pass directly without summarization


def _summarize_api_docs(raw_text: str) -> str:
    """Use the LLM to condense long API docs while preserving all endpoints."""
    prompt = f"""You are an API documentation analyst. The following API documentation is too long
to process in full. Create a CONDENSED version that preserves ALL of the following for EVERY endpoint:

- HTTP method (GET, POST, etc.)
- Full URL path
- Query parameters (name, type, required/optional)
- Brief one-line description of what it does
- Response field names (if mentioned)

REMOVE:
- Lengthy prose descriptions and background info
- Detailed examples and sample responses (keep only field names)
- Tutorials, guides, and non-reference content
- Repeated boilerplate text

Format each endpoint as:
  METHOD /path — brief description
    Params: param1 (type, required), param2 (type, optional)
    Response fields: field1, field2, field3

ORIGINAL DOCUMENTATION:
{raw_text[:20000]}

Respond with ONLY the condensed documentation. No JSON wrapping, no preamble."""

    try:
        condensed = _call_llm(prompt, fast=True)
        return condensed.strip()
    except Exception:
        # Fallback: return first + last chunk if LLM fails
        return raw_text[:4000] + "\n\n[... middle omitted ...]\n\n" + raw_text[-4000:]


@mcp.tool()
def fetch_api_docs(url: str) -> str:
    """Fetch and parse the content of an API documentation page. Returns cleaned text."""
    try:
        headers = {
            "User-Agent": "APIDiscoveryAgent/1.0 (endpoint-discovery-tool)",
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")

        # If JSON (e.g., OpenAPI/Swagger spec), return formatted JSON
        if "json" in content_type or url.endswith(".json"):
            try:
                data = response.json()
                text = json.dumps(data, indent=2)
                if len(text) > MAX_DOC_CHARS:
                    text = _summarize_api_docs(text)
                return json.dumps({"status": "success", "content_type": "json", "text": text})
            except json.JSONDecodeError:
                pass

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Summarize if too long — preserves all endpoints while reducing noise
        if len(text) > MAX_DOC_CHARS:
            text = _summarize_api_docs(text)

        return json.dumps({"status": "success", "content_type": "html", "text": text})

    except requests.RequestException as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def discover_endpoints(api_doc_text: str, question: str) -> str:
    """Analyze API documentation text to identify endpoints relevant to a question.
    Returns structured JSON with endpoint details, query params, and response fields."""
    try:
        prompt = f"""Analyze the following API documentation and identify ALL endpoints mentioned.
Then determine which endpoints are relevant to answering this question: "{question}"

API Documentation:
{api_doc_text[:12000]}

Respond with ONLY valid JSON in this exact format:
{{
  "base_url": "<the API's base URL>",
  "total_endpoints": <number>,
  "endpoints": [
    {{
      "method": "GET",
      "path": "/endpoint/path",
      "description": "What this endpoint does",
      "query_params": [
        {{"name": "param_name", "type": "string", "required": false, "description": "what it does"}}
      ],
      "response_fields": [
        {{"name": "field_name", "type": "string", "description": "what it contains"}}
      ],
      "is_relevant": true,
      "relevance_reason": "Why this endpoint helps answer the question"
    }}
  ],
  "limitations": ["Any limitations in answering the question with this API"]
}}

IMPORTANT:
- List ALL endpoints you can find, marking relevant ones with is_relevant: true
- For relevant endpoints, be thorough about query_params and response_fields
- Note any limitations (rate limits, pagination, missing data, etc.)
- Respond with ONLY the JSON, no other text"""

        response_text = _call_llm(prompt, fast=True)
        # Validate it's parseable JSON
        parsed = _extract_json(response_text)
        return json.dumps(parsed)

    except Exception as e:
        return json.dumps({"error": f"Failed to analyze endpoints: {str(e)}"})


@mcp.tool()
def check_endpoint_availability(base_url: str, endpoint_path: str, method: str = "GET") -> str:
    """Probe an API endpoint to verify it's live and returning data.
    Makes a lightweight request to check availability."""
    try:
        url = base_url.rstrip("/") + "/" + endpoint_path.lstrip("/")
        headers = {"User-Agent": "APIDiscoveryAgent/1.0 (endpoint-probe)"}

        if method.upper() == "HEAD":
            response = requests.head(url, headers=headers, timeout=10)
        else:
            # GET with minimal params to check availability
            response = requests.get(url, headers=headers, timeout=10, params={"limit": 1})

        # Check if we got data back
        is_available = response.status_code == 200
        has_data = False
        sample_keys = []

        if is_available:
            try:
                data = response.json()
                has_data = True
                if isinstance(data, dict):
                    sample_keys = list(data.keys())[:10]
                elif isinstance(data, list) and len(data) > 0:
                    sample_keys = list(data[0].keys())[:10] if isinstance(data[0], dict) else []
            except (json.JSONDecodeError, ValueError):
                pass

        return json.dumps({
            "url": url,
            "status_code": response.status_code,
            "is_available": is_available,
            "has_data": has_data,
            "sample_response_keys": sample_keys,
            "content_type": response.headers.get("Content-Type", "unknown"),
        })

    except requests.RequestException as e:
        return json.dumps({
            "url": base_url.rstrip("/") + "/" + endpoint_path.lstrip("/"),
            "status_code": None,
            "is_available": False,
            "has_data": False,
            "error": str(e),
        })


@mcp.tool()
def generate_pg_schema(endpoints_json: str, question: str) -> str:
    """Given relevant endpoint data and a question, generate PostgreSQL DDL,
    recommended indexes, and notes on data types. Returns SQL as text."""
    try:
        prompt = f"""You are a PostgreSQL database architect. Given the following API endpoint data
and a question the user wants to answer, generate the optimal PostgreSQL table schema.

Question: "{question}"

API Endpoint Data:
{endpoints_json[:10000]}

Respond with ONLY valid JSON in this exact format:
{{
  "table_name": "descriptive_table_name",
  "columns": [
    {{"name": "id", "pg_type": "SERIAL", "nullable": false, "description": "Primary key"}},
    {{"name": "column_name", "pg_type": "VARCHAR(255)", "nullable": true, "description": "what it stores"}}
  ],
  "primary_key": "id",
  "indexes": ["CREATE INDEX idx_name ON table_name(column_name)"],
  "create_table_ddl": "CREATE TABLE table_name (\\n  id SERIAL PRIMARY KEY,\\n  ...\\n);",
  "notes": "Any notes about the schema design choices"
}}

IMPORTANT:
- Choose appropriate PostgreSQL types (VARCHAR, INTEGER, NUMERIC, TIMESTAMP, JSONB, TEXT, BOOLEAN, etc.)
- Include indexes that would help efficiently query the data for the user's question
- The DDL should be ready to execute
- Respond with ONLY the JSON"""

        response_text = _call_llm(prompt, fast=True)
        parsed = _extract_json(response_text)
        return json.dumps(parsed)

    except Exception as e:
        return json.dumps({"error": f"Failed to generate schema: {str(e)}"})


@mcp.tool()
def plan_data_pipeline(endpoints_json: str, question: str, pg_schema: str) -> str:
    """Produce the final data pipeline plan: how to query endpoints, handle pagination,
    transform data, and the SQL to answer the question."""
    try:
        prompt = f"""You are a data engineer. Given API endpoints, a PostgreSQL table schema, and
a question, create a comprehensive data pipeline plan.

Question: "{question}"

API Endpoints:
{endpoints_json[:8000]}

PostgreSQL Schema:
{pg_schema[:4000]}

Respond with ONLY valid JSON in this exact format:
{{
  "query_strategy": "Step-by-step description of how to query the API endpoints to get the needed data",
  "pagination_approach": "How to handle pagination if the API paginates results",
  "transformations": [
    {{
      "step_number": 1,
      "description": "What this transformation does",
      "sql_or_code": "SQL or Python code for the transformation"
    }}
  ],
  "insert_strategy": "How to insert the data into PostgreSQL (batch INSERT, COPY, etc.)",
  "final_sql": "The SQL query to run on the populated table to answer the user's question",
  "estimated_complexity": "low|medium|high",
  "notes": "Any additional notes or caveats"
}}

IMPORTANT:
- Be specific about API query parameters to use
- Include any data cleaning or type conversion steps
- The final SQL should directly answer the user's question
- Respond with ONLY the JSON"""

        response_text = _call_llm(prompt, fast=True)
        parsed = _extract_json(response_text)
        return json.dumps(parsed)

    except Exception as e:
        return json.dumps({"error": f"Failed to create pipeline plan: {str(e)}"})


# ============================================================
# Agent Loop internals
# ============================================================

# Tool registry for the agent loop
_tools = {
    "fetch_api_docs": fetch_api_docs,
    "discover_endpoints": discover_endpoints,
    "check_endpoint_availability": check_endpoint_availability,
    "generate_pg_schema": generate_pg_schema,
    "plan_data_pipeline": plan_data_pipeline,
}

# Build system prompt from the MCP prompt
_system_prompt_template = """You are an expert API analyst and data engineer. Your task is to analyze an API's
documentation and determine how to answer a specific question using data from that API.

The user has provided:
- API Documentation URL: {api_doc_url}
- Question: {question}

You have access to the following tools:

1. fetch_api_docs(url: str) -> str
   Fetches and parses the content of an API documentation page. Returns the text content.
   Always call this first with the provided URL.

2. discover_endpoints(api_doc_text: str, question: str) -> str
   Analyzes the API documentation text to identify all endpoints, determine which are relevant
   to the question, extract query parameters and response fields. Returns structured JSON.

3. check_endpoint_availability(base_url: str, endpoint_path: str, method: str) -> str
   Probes an endpoint to verify it's live and returning data. Use this to validate
   that the endpoints you identified actually work.

4. generate_pg_schema(endpoints_json: str, question: str) -> str
   Given the relevant endpoints and question, produces PostgreSQL CREATE TABLE DDL,
   recommended indexes, and transformation SQL.

5. plan_data_pipeline(endpoints_json: str, question: str, pg_schema: str) -> str
   Produces the final execution plan: how to query endpoints, pagination strategy,
   data transformations, and the SQL to answer the question.

MANDATORY WORKFLOW — You MUST complete ALL 5 steps before giving a final answer:
1. fetch_api_docs — fetch the documentation
2. discover_endpoints — analyze endpoints from the doc text
3. check_endpoint_availability — probe ONE relevant endpoint
4. generate_pg_schema — REQUIRED: produce the PostgreSQL table DDL
5. plan_data_pipeline — REQUIRED: produce the data pipeline and final SQL
6. ONLY THEN return your final answer

DO NOT return a final answer until you have called generate_pg_schema AND plan_data_pipeline.

You must respond in ONE of these two JSON formats:

If you need to use a tool:
{{"tool_name": "<name>", "tool_arguments": {{"<arg_name>": "<value>"}}}}

If you have the final answer (ONLY after completing all 5 tool calls):
{{"answer": "<your comprehensive final answer>"}}

IMPORTANT RULES:
- Respond with ONLY the JSON. No other text. No markdown code fences.
- Follow the workflow steps in order.
- After receiving a tool result, call the NEXT tool in the workflow.
- If a tool returns an error, note the limitation and move on to the next step.
- Do not repeat tool calls with the same arguments.
- Keep tool arguments concise — do not pass the full API doc text to generate_pg_schema or plan_data_pipeline, pass only the relevant endpoints JSON.
"""


def _call_llm(prompt: str, fast: bool = False) -> str:
    """Send a prompt to Gemini and return the text response.
    
    Args:
        fast: If True, use shorter throttle (for tool-internal calls).
    """
    from google.genai import errors
    wait = TOOL_THROTTLE_SECONDS if fast else THROTTLE_SECONDS
    time.sleep(wait)
    try:
        response = llm_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    except errors.APIError as e:
        if getattr(e, 'code', None) in (500, 503):
            # Retry once with fallback model on server errors
            time.sleep(2)
            try:
                response = llm_client.models.generate_content(model="gemma-4-31b-it", contents=prompt)
                return response.text
            except Exception:
                pass
            # If fallback also fails, try original model with truncated prompt
            if len(prompt) > 8000:
                truncated = prompt[:4000] + "\n\n[... middle truncated ...]\n\n" + prompt[-4000:]
                time.sleep(2)
                response = llm_client.models.generate_content(model=GEMINI_MODEL, contents=truncated)
                return response.text
        raise e


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and other noise."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse LLM response as JSON: {text[:200]}")


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM's response for tool calls or final answers."""
    return _extract_json(text)


def _run_agent(api_doc_url: str, question: str, max_iterations: int = 6) -> dict:
    """Run the agent loop and return structured results.

    Returns a dict with keys:
        answer: str — the final answer text
        tool_results: dict — raw results from each tool call
    """
    system_prompt = _system_prompt_template.format(
        api_doc_url=api_doc_url,
        question=question,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analyze the API at {api_doc_url} to answer: {question}"},
    ]

    tool_results = {}  # Store results keyed by tool name
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 2

    for iteration in range(max_iterations):
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += msg["content"] + "\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg["role"] == "tool":
                # Truncate long tool results to keep prompt within context limits
                content = msg['content']
                if len(content) > 4000:
                    content = content[:4000] + "\n... [TRUNCATED]"
                prompt += f"Tool Result: {content}\n\n"

        response_text = _call_llm(prompt)

        try:
            parsed = _parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError):
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        if "answer" in parsed:
            return {"answer": parsed["answer"], "tool_results": tool_results}

        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})

            if tool_name not in _tools:
                error_msg = json.dumps({"error": f"Unknown tool: {tool_name}. Available: {list(_tools.keys())}"})
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                consecutive_errors += 1
            else:
                tool_result = _tools[tool_name](**tool_args)
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": tool_result})

                # Store the result for UI rendering
                tool_results[tool_name] = tool_result

                try:
                    result_data = json.loads(tool_result)
                    if "error" in result_data:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0
                except (json.JSONDecodeError, TypeError):
                    consecutive_errors = 0

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                return {
                    "answer": "Multiple consecutive tool errors occurred. Please try again later.",
                    "tool_results": tool_results,
                }

    return {
        "answer": "Max iterations reached. The agent could not complete the full analysis.",
        "tool_results": tool_results,
    }


# ============================================================
# App Tool — Prefab UI with two input fields + rendered results
# ============================================================

@mcp.tool(app=True)
def api_discovery(api_doc_url: str, question: str) -> PrefabApp:
    """Analyze an API's documentation to discover endpoints relevant to your question.
    Produces a PostgreSQL schema and data pipeline plan."""

    # Run the agent loop
    agent_result = None
    agent_error = None
    try:
        agent_result = _run_agent(api_doc_url, question)
    except Exception as e:
        agent_error = f"Agent encountered an error: {e}"

    # Build the UI
    with Column(gap=4) as view:
        H1("🔍 API Endpoint Discovery Agent")
        P(f"Analyzing: {api_doc_url}")
        P(f"Question: {question}")
        Separator()

        if agent_error:
            with Alert(variant="destructive"):
                AlertTitle("Agent Error")
                AlertDescription(agent_error)
        elif agent_result:
            # Show the agent's summary answer
            with Alert(variant="success"):
                AlertTitle("✅ Discovery Complete")
                AlertDescription(str(agent_result.get("answer", "No answer returned.")))

            tool_results = agent_result.get("tool_results", {})

            # ── Endpoints Section ──
            if "discover_endpoints" in tool_results:
                try:
                    endpoints_data = json.loads(tool_results["discover_endpoints"])
                    total = endpoints_data.get("total_endpoints", 0)
                    endpoints = endpoints_data.get("endpoints", [])
                    relevant = [e for e in endpoints if e.get("is_relevant")]
                    limitations = endpoints_data.get("limitations", [])

                    Separator()
                    H2("📊 Endpoint Discovery Results")

                    with Row(gap=4):
                        Metric(label="Total Endpoints Found", value=str(total))
                        Metric(label="Relevant Endpoints", value=str(len(relevant)))
                        Metric(label="Limitations", value=str(len(limitations)))

                    if relevant:
                        H3("Relevant Endpoints")
                        endpoint_rows = []
                        for ep in relevant:
                            params = ", ".join([p.get("name", "") for p in ep.get("query_params", [])])
                            fields = ", ".join([f.get("name", "") for f in ep.get("response_fields", [])])
                            endpoint_rows.append({
                                "Method": ep.get("method", "GET"),
                                "Path": ep.get("path", ""),
                                "Description": ep.get("description", ""),
                                "Query Params": params or "None",
                                "Response Fields": fields or "N/A",
                                "Relevance": ep.get("relevance_reason", ""),
                            })

                        DataTable(
                            columns=[
                                DataTableColumn(key="Method", header="Method", width="80px"),
                                DataTableColumn(key="Path", header="Path", min_width="150px"),
                                DataTableColumn(key="Description", header="Description", min_width="200px"),
                                DataTableColumn(key="Query Params", header="Query Params", min_width="150px"),
                                DataTableColumn(key="Response Fields", header="Response Fields", min_width="200px"),
                                DataTableColumn(key="Relevance", header="Why Relevant", min_width="200px"),
                            ],
                            rows=endpoint_rows,
                            search=True,
                            paginated=True,
                            page_size=10,
                        )

                    if limitations:
                        H3("⚠️ Limitations")
                        for lim in limitations:
                            with Alert(variant="warning"):
                                AlertDescription(str(lim))

                except (json.JSONDecodeError, TypeError):
                    pass

            # ── Endpoint Availability Section ──
            if "check_endpoint_availability" in tool_results:
                try:
                    avail_data = json.loads(tool_results["check_endpoint_availability"])
                    Separator()
                    H2("🟢 Endpoint Availability Check")
                    with Card():
                        with CardHeader():
                            CardTitle(avail_data.get("url", "Unknown URL"))
                        with CardContent():
                            status = "✅ Available" if avail_data.get("is_available") else "❌ Unavailable"
                            has_data = "✅ Yes" if avail_data.get("has_data") else "❌ No"
                            P(f"Status: {status} (HTTP {avail_data.get('status_code', 'N/A')})")
                            P(f"Has Data: {has_data}")
                            if avail_data.get("sample_response_keys"):
                                P(f"Sample Response Keys: {', '.join(avail_data['sample_response_keys'])}")
                except (json.JSONDecodeError, TypeError):
                    pass

            # ── PostgreSQL Schema Section ──
            if "generate_pg_schema" in tool_results:
                try:
                    schema_data = json.loads(tool_results["generate_pg_schema"])
                    Separator()
                    H2("🗄️ PostgreSQL Table Schema")

                    if schema_data.get("create_table_ddl"):
                        with Card():
                            with CardHeader():
                                CardTitle(f"Table: {schema_data.get('table_name', 'unknown')}")
                            with CardContent():
                                P(schema_data["create_table_ddl"])

                    if schema_data.get("columns"):
                        H3("Column Details")
                        col_rows = []
                        for col in schema_data["columns"]:
                            col_rows.append({
                                "Column": col.get("name", ""),
                                "Type": col.get("pg_type", ""),
                                "Nullable": "Yes" if col.get("nullable", True) else "No",
                                "Description": col.get("description", ""),
                            })
                        DataTable(
                            columns=[
                                DataTableColumn(key="Column", header="Column", min_width="120px"),
                                DataTableColumn(key="Type", header="PostgreSQL Type", min_width="120px"),
                                DataTableColumn(key="Nullable", header="Nullable", width="80px", align="center"),
                                DataTableColumn(key="Description", header="Description", min_width="200px"),
                            ],
                            rows=col_rows,
                        )

                    if schema_data.get("indexes"):
                        H3("Indexes")
                        for idx in schema_data["indexes"]:
                            P(str(idx))

                except (json.JSONDecodeError, TypeError):
                    pass

            # ── Data Pipeline Plan Section ──
            if "plan_data_pipeline" in tool_results:
                try:
                    pipeline_data = json.loads(tool_results["plan_data_pipeline"])
                    Separator()
                    H2("🔧 Data Pipeline Plan")

                    if pipeline_data.get("query_strategy"):
                        with Card():
                            with CardHeader():
                                CardTitle("Query Strategy")
                            with CardContent():
                                P(str(pipeline_data["query_strategy"]))

                    if pipeline_data.get("pagination_approach"):
                        with Card():
                            with CardHeader():
                                CardTitle("Pagination Approach")
                            with CardContent():
                                P(str(pipeline_data["pagination_approach"]))

                    if pipeline_data.get("transformations"):
                        H3("Transformation Steps")
                        transform_rows = []
                        for t in pipeline_data["transformations"]:
                            transform_rows.append({
                                "Step": str(t.get("step_number", "")),
                                "Description": t.get("description", ""),
                                "SQL / Code": t.get("sql_or_code", ""),
                            })
                        DataTable(
                            columns=[
                                DataTableColumn(key="Step", header="#", width="50px", align="center"),
                                DataTableColumn(key="Description", header="Description", min_width="200px"),
                                DataTableColumn(key="SQL / Code", header="SQL / Code", min_width="250px"),
                            ],
                            rows=transform_rows,
                        )

                    if pipeline_data.get("final_sql"):
                        H3("Final SQL Query")
                        with Card():
                            with CardContent():
                                P(str(pipeline_data["final_sql"]))

                    if pipeline_data.get("estimated_complexity"):
                        complexity = pipeline_data["estimated_complexity"]
                        variant_map = {"low": "success", "medium": "warning", "high": "destructive"}
                        Badge(f"Complexity: {complexity}")

                except (json.JSONDecodeError, TypeError):
                    pass
        else:
            with Alert(variant="warning"):
                AlertTitle("Notice")
                AlertDescription("Agent did not return a response. Please try again.")

    return PrefabApp(view=view)


if __name__ == "__main__":
    mcp.run()
