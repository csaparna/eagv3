"""
MCP Server for academic paper research tools.
Uses FastMCP to expose search_semantic_scholar and log_paper_record as MCP tools.
The app tool (research_papers) takes a natural language question, runs the
LLM agent loop behind the scenes, and renders the CSV result.

Run the server in development mode with inspector:
  $ fastmcp dev inspector mcp_server.py

Run the server as an app:
  $ fastmcp dev apps mcp_server.py
"""
import time
import json
import csv
import re
import os
import requests
from google import genai
from dotenv import load_dotenv
from fastmcp import FastMCP
from prefab_ui.app import PrefabApp
from prefab_ui.components.column import Column
from prefab_ui.components.row import Row
from prefab_ui.components.data_table import DataTable, DataTableColumn
from prefab_ui.components.typography import H1, H2, Muted, P
from prefab_ui.components.metric import Metric
from prefab_ui.components.alert import Alert, AlertTitle, AlertDescription

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
THROTTLE_SECONDS = 6

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

llm_client = genai.Client(api_key=GEMINI_API_KEY)

mcp = FastMCP("Research Agent")


# ============================================================
# MCP Tools — called by the agent loop behind the scenes
# ============================================================

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")


@mcp.tool()
def search_semantic_scholar(query: str, offset: int = 0, limit: int = 1, year: int =2026) -> str:
    """Search Semantic Scholar for papers and return details including title, authors, tldr, citationCount, doi, and year."""
    query = '+'.join(query.split())
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&offset={offset}&limit={limit}&year={year}&fields=externalIds,authors,title,tldr,citationCount,year"

    # Use proper headers — x-api-key gives a dedicated rate limit (vs shared global pool)
    headers = {'User-Agent': 'ResearchAgent/1.0 (academic-tool)'}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers['x-api-key'] = SEMANTIC_SCHOLAR_API_KEY

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()

            if 'data' not in data or not data['data']:
                return json.dumps({"error": "No results found."})

            results = []
            for item in data['data']:
                doi = item.get('externalIds', {}).get('DOI', 'Unknown DOI') if item.get('externalIds') else 'Unknown DOI'
                authors = ", ".join([a.get('name', '') for a in item.get('authors', [])]) if item.get('authors') else 'Unknown Authors'
                tldr = item.get('tldr', {}).get('text', 'No TLDR') if item.get('tldr') else 'No TLDR'

                results.append({
                    "title": item.get('title', 'Unknown Title'),
                    "authors": authors,
                    "tldr": tldr,
                    "citationCount": item.get('citationCount', 0),
                    "doi": doi,
                    "year": item.get('year', 0)
                })

            return json.dumps({"results": results})
        except Exception as e:
            if attempt == max_retries - 1:
                return json.dumps({"error": str(e)})
            time.sleep(2 ** (attempt + 1))

    return json.dumps({"error": "Max retries exceeded due to rate limiting (429)."})


@mcp.tool()
def log_paper_record(title: str, authors: str, doi: str, tldr: str, citation_count: int, year: int, csv_path: str = "papers.csv") -> str:
    """Add a paper's details to a CSV file as a separate row."""
    try:
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Title', 'Authors', 'DOI', 'TLDR', 'Citation Count', 'Year'])
            writer.writerow([title, authors, doi, tldr, citation_count, year])
        return json.dumps({"status": "Success", "csv_file": csv_path})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# Agent Loop internals (same logic as agent_cli.py)
# ============================================================

# Tool registry for the agent loop
_tools = {
    "search_semantic_scholar": search_semantic_scholar,
    "log_paper_record": log_paper_record,
}

_system_prompt = """You are a helpful AI agent that can use tools to find academic papers.

You have access to the following tools:

1. search_semantic_scholar(query: str, offset: int = 0) -> str
   Search Semantic Scholar for papers and return details including title, authors, tldr, citationCount, and doi.
   Examples: search_semantic_scholar("Attention is all you need", 0)

2. log_paper_record(title: str, authors: str, doi: str, tldr: str, citation_count: int, year: int, csv_path: str = "papers.csv") -> str
   Add a paper's details to a CSV file as a separate row. Call this for each paper you want to log.
   Examples: log_paper_record("Attention is all you need", "Ashish Vaswani, Noam Shazeer...", "10.48550/arXiv.1706.03762", "A new network architecture based on attention mechanisms.", 10000, 2017, "papers.csv")

You must respond in ONE of these two JSON formats:

If you need to use a tool:
{"tool_name": "<name>", "tool_arguments": {"<arg_name>": "<value>"}}

If you have the final answer:
{"answer": "<your final answer>"}

IMPORTANT RULES:
- Respond with ONLY the JSON. No other text. No markdown code fences.
- Use tools when you need to interact with external services.
- After receiving a tool result, either use another tool or provide your final answer.
- You can chain these tools to find, download, and log academic papers.
- Only call the tools necessary to answer the question. After successful response to the question, do not make other tool calls.
- If a tool result contains an error about rate limiting (429), do NOT retry the same tool. Instead, immediately return a final answer explaining that Semantic Scholar rate-limited the request and the user should try again later.
"""


def _call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response."""
    from google.genai import errors
    time.sleep(THROTTLE_SECONDS)
    try:
        response = llm_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    except errors.APIError as e:
        if getattr(e, 'code', None) == 503:
            response = llm_client.models.generate_content(model="gemma-4-31b-it", contents=prompt)
            return response.text
        raise e


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM's response, handling common formatting issues."""
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
    raise ValueError(f"Could not parse LLM response: {text[:200]}")


def _run_agent(user_query: str, max_iterations: int = 4) -> str:
    """Run the agent loop and return the final answer."""
    messages = [
        {"role": "system", "content": _system_prompt},
        {"role": "user", "content": user_query},
    ]
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 2  # Bail after 2 consecutive tool errors

    for _ in range(max_iterations):
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += msg["content"] + "\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg["role"] == "tool":
                prompt += f"Tool Result: {msg['content']}\n\n"

        response_text = _call_llm(prompt)

        try:
            parsed = _parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError):
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        if "answer" in parsed:
            return parsed["answer"]

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

                # Check if the tool returned an error (rate limit, etc.)
                try:
                    result_data = json.loads(tool_result)
                    if "error" in result_data:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0
                except (json.JSONDecodeError, TypeError):
                    consecutive_errors = 0

            # Bail early if tools keep failing (e.g. rate-limited)
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                return ("Semantic Scholar is rate-limiting requests. "
                        "Showing existing paper log below. Please try again later.")

    return "Max iterations reached. Agent could not complete the task."


# ============================================================
# App Tool — Natural language interface with rendered CSV output
# ============================================================

@mcp.tool(app=True)
def research_papers(question: str) -> PrefabApp:
    """Ask a natural language question about academic papers. The agent will search, log results to CSV, and display the paper log."""

    # Run the agent loop (LLM decides which tools to call)
    agent_answer = None
    agent_error = None
    try:
        agent_answer = _run_agent(question)
    except Exception as e:
        agent_error = f"Agent encountered an error: {e}. Showing existing paper log."

    # Read the CSV for display (always, even if agent failed)
    csv_path = "papers.csv"
    rows = []
    try:
        if os.path.isfile(csv_path):
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = [
                    {k: v for k, v in row.items() if k is not None}
                    for row in reader
                ]
    except Exception:
        pass

    # Build the UI
    with Column(gap=4) as view:
        H1("📚 Research Agent")

        if agent_error:
            with Alert(variant="destructive"):
                AlertTitle("Agent Error")
                AlertDescription(agent_error)
        elif agent_answer:
            with Alert(variant="success"):
                AlertTitle("Agent Response")
                AlertDescription(str(agent_answer))
        else:
            with Alert(variant="warning"):
                AlertTitle("Notice")
                AlertDescription("Agent did not return a response. Showing existing paper log.")

        with Row(gap=4):
            Metric(label="Total Papers in Log", value=str(len(rows)))

        if rows:
            H2("Paper Log")
            DataTable(
                columns=[
                    DataTableColumn(key="Title", header="Title", sortable=True, min_width="200px"),
                    DataTableColumn(key="Authors", header="Authors", min_width="150px"),
                    DataTableColumn(key="Year", header="Year", sortable=True, width="80px", align="center"),
                    DataTableColumn(key="Citation Count", header="Citations", sortable=True, width="100px", align="right"),
                    DataTableColumn(key="DOI", header="DOI", min_width="120px"),
                    DataTableColumn(key="TLDR", header="TLDR", min_width="250px"),
                ],
                rows=rows,
                search=True,
                paginated=True,
                page_size=10,
            )
        else:
            Muted("No papers logged yet.")

    return PrefabApp(view=view)


if __name__ == "__main__":
    mcp.run()
