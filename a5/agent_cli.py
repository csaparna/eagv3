"""
CLI Agent that uses the tools defined in mcp_server.py.
Interactive terminal interface for the API Endpoint Discovery Agent.

Usage:
  $ uv run python agent_cli.py
"""
from google import genai
import json
import re
import os
import time
from dotenv import load_dotenv
from mcp_server import (
    fetch_api_docs,
    discover_endpoints,
    check_endpoint_availability,
    generate_pg_schema,
    plan_data_pipeline,
)

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
THROTTLE_SECONDS = 2

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response."""
    from google.genai import errors
    print(f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    except errors.APIError as e:
        if getattr(e, 'code', None) == 503:
            print(f"  [503 error, retrying with gemma-4-31b-it...]", flush=True)
            response = client.models.generate_content(model="gemma-4-31b-it", contents=prompt)
            return response.text
        raise e


# ============================================================
# System Prompt
# ============================================================
system_prompt_template = """You are an expert API analyst and data engineer. Your task is to analyze an API's
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


# Tool registry
tools = {
    "fetch_api_docs": fetch_api_docs,
    "discover_endpoints": discover_endpoints,
    "check_endpoint_availability": check_endpoint_availability,
    "generate_pg_schema": generate_pg_schema,
    "plan_data_pipeline": plan_data_pipeline,
}


# ============================================================
# Response Parser
# ============================================================

def parse_llm_response(text: str) -> dict:
    """Parse the LLM's response, handling common formatting issues."""
    text = text.strip()

    # Remove markdown code fences
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


# ============================================================
# The Agent Loop
# ============================================================

def run_agent(api_doc_url: str, question: str, max_iterations: int = 10, verbose: bool = True):
    """
    Run the agent loop:
    User inputs → LLM → [Tool call → Result → LLM]* → Final answer
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  API Doc URL: {api_doc_url}")
        print(f"  Question:    {question}")
        print(f"{'='*60}")

    system_prompt = system_prompt_template.format(
        api_doc_url=api_doc_url,
        question=question,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analyze the API at {api_doc_url} to answer: {question}"},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- Iteration {iteration + 1} ---")

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

        response_text = call_llm(prompt)
        if verbose:
            print(f"LLM: {response_text.strip()[:200]}...")

        try:
            parsed = parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"Parse error: {e}")
                print("Asking LLM to retry...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        if "answer" in parsed:
            if verbose:
                print(f"\n{'='*60}")
                print(f"  FINAL ANSWER:")
                print(f"{'='*60}")
                print(parsed["answer"])
                print(f"{'='*60}")
            return parsed["answer"]

        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})

            if verbose:
                print(f"→ Calling tool: {tool_name}({list(tool_args.keys())})")

            if tool_name not in tools:
                error_msg = json.dumps({"error": f"Unknown tool: {tool_name}. Available: {list(tools.keys())}"})
                if verbose:
                    print(f"→ Error: {error_msg}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                continue

            tool_result = tools[tool_name](**tool_args)
            if verbose:
                # Truncate long results in terminal
                display = tool_result[:300] + "..." if len(tool_result) > 300 else tool_result
                print(f"→ Result: {display}")

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool", "content": tool_result})

    print("\nMax iterations reached. Agent could not complete the task.")
    return None


# ============================================================
# Interactive CLI
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔍 API ENDPOINT DISCOVERY AGENT")
    print("  Analyze API docs, discover endpoints, plan data pipelines.")
    print("=" * 60)

    while True:
        print()
        api_doc_url = input("Enter the API documentation URL (or 'exit' to quit): ").strip()
        if api_doc_url.lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
        if not api_doc_url:
            print("Please enter a valid URL.")
            continue

        question = input("What question do you want to answer with this API's data? ").strip()
        if not question:
            print("Please enter a question.")
            continue

        print("\n>>> Analyzing API documentation & discovering endpoints...")
        run_agent(api_doc_url, question)

        while True:
            another = input("\nAnalyze another API? (y/n): ").strip().lower()
            if another in ['y', 'yes', 'n', 'no']:
                break
            print("Please enter 'y' or 'n'.")

        if another in ['n', 'no']:
            print("Goodbye!")
            break
