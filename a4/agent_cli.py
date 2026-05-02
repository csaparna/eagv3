"""
CLI Agent that uses the tools defined in mcp_server.py (MCP server).
This file contains the LLM configuration, system prompt, response parser,
agent loop, and interactive CLI.

Uses model:
gemini-3.1-flash-lite-preview
"""
from google import genai
import json
import re
import os
import time
from dotenv import load_dotenv
from mcp_server import search_semantic_scholar, log_paper_record

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
THROTTLE_SECONDS = 6  # Wait before each LLM call to stay under free-tier RPM limits

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response.

    Sleeps for THROTTLE_SECONDS before each call to stay under the free-tier
    rate limit (Gemini 3.1 Flash Lite: 15 RPM, 500 RPD).
    """
    from google.genai import errors
    print(f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    except errors.APIError as e:
        if getattr(e, 'code', None) == 503:
            print(f"  [503 error encountered, retrying with gemma-4-31b-it...]", flush=True)
            response = client.models.generate_content(model="gemma-4-31b-it", contents=prompt)
            return response.text
        raise e


# ============================================================
# System Prompt — This is what turns an LLM into an agent
# ============================================================
system_prompt = """You are a helpful AI agent that can use tools to find academic papers.

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
"""


# Tool registry — maps tool names to functions
tools = {
    "search_semantic_scholar": search_semantic_scholar,
    "log_paper_record": log_paper_record,
}


# ============================================================
# Response Parser — Handles messy LLM output
# ============================================================

def parse_llm_response(text: str) -> dict:
    """Parse the LLM's response, handling common formatting issues"""
    text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (opening fence)
        lines = lines[1:]
        # Remove last line if it's a closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        # Remove language identifier
        if text.startswith("json"):
            text = text[4:].strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response: {text[:200]}")


# ============================================================
# The Agent Loop — This is where the magic happens
# ============================================================

def run_agent(user_query: str, max_iterations: int = 10, verbose: bool = True):
    """
    Run the agent loop:
    User query → LLM → [Tool call → Result → LLM]* → Final answer

    This is THE pattern. Everything else in this course builds on this loop.
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  User: {user_query}")
        print(f"{'='*60}")

    # Conversation history — this is the agent's "working memory"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- Iteration {iteration + 1} ---")

        # Build prompt from message history
        # Each iteration, the LLM sees EVERYTHING that happened before
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

        # Call the LLM
        response_text = call_llm(prompt)
        if verbose:
            print(f"LLM: {response_text.strip()}")

        # Parse the response
        try:
            parsed = parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"Parse error: {e}")
                print("Asking LLM to retry...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        # Check if it's a final answer
        if "answer" in parsed:
            if verbose:
                print(f"\n{'='*60}")
                print(f"  Agent Answer: {parsed['answer']}")
                print(f"{'='*60}")
            return parsed["answer"]

        # It's a tool call — execute it
        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})

            if verbose:
                print(f"→ Calling tool: {tool_name}({tool_args})")

            # Check if tool exists
            if tool_name not in tools:
                error_msg = json.dumps({"error": f"Unknown tool: {tool_name}. Available: {list(tools.keys())}"})
                if verbose:
                    print(f"→ Error: {error_msg}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                continue

            # Execute the tool
            tool_result = tools[tool_name](**tool_args)
            if verbose:
                print(f"→ Result: {tool_result}")

            # Add to conversation history — the LLM will see this next iteration
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool", "content": tool_result})

    print("\nMax iterations reached. Agent could not complete the task.")

    # Print full conversation for debugging
    if verbose:
        print(f"\n{'='*60}")
        print("Full conversation history:")
        print(f"{'='*60}")
        for i, msg in enumerate(messages):
            print(f"[{i}] {msg['role']}: {msg['content'][:100]}...")

    return None


# ============================================================
# Run the agent intelligently!
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RESEARCH AGENT")
    print("  Hello! Let's find, download, and log academic papers.")
    print("=" * 60)

    while True:
        paper_details = input("\nWhat papers do you want to search for? (or type 'exit'/'quit' to stop): ")
        if paper_details.strip().lower() in ['exit', 'quit']:
            print("Goodbye!")
            break

        if not paper_details.strip():
            continue

        print("\n>>> Searching & Processing...")
        run_agent(paper_details)

        while True:
            another = input("\nDo you want to search for another paper? (y/n): ").strip().lower()
            if another in ['y', 'yes', 'n', 'no']:
                break
            print("Please enter 'y' or 'n'.")

        if another in ['n', 'no']:
            print("Goodbye!")
            break
