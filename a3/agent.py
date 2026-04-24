"""
Uses model:
gemini-3.1-flash-lite-preview
"""
from google import genai
import json
import re
import math
import os
import time
from dotenv import load_dotenv

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
THROTTLE_SECONDS = 6  # Wait before each LLM call to stay under free-tier RPM limits

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response.

    Sleeps for THROTTLE_SECONDS before each call to stay under the free-tier
    rate limit (Gemini 3.1 Flash Lite: 15 RPM, 500 RPD).
    """
    print(f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


# ============================================================
# System Prompt — This is what turns an LLM into an agent
# ============================================================
system_prompt = """You are a helpful AI agent that can use tools to find academic papers.

You have access to the following tools:

1. find_doi(first_author: str, paper_name: str) -> str
   Find the DOI of an academic paper given the first author and name of paper.
   Examples: find_doi("Vaswani", "Attention is all you need")

2. download_paper(doi: str) -> str
   Get the direct PDF URL from Sci-Hub for a given DOI.
   Examples: download_paper("10.48550/arXiv.1706.03762")

3. save_pdf(pdf_url: str, file_name: str, folder: str = "papers") -> str
   Download and save a PDF file from a URL to a specified folder.
   Create an appropriate 'file_name' safely representing the paper title (e.g., 'attention_is_all_you_need.pdf').
   Examples: save_pdf("https://...", "attention_is_all_you_need.pdf")

4. add_to_csv(file_name: str, doi: str, paper_name: str, csv_path: str = "papers.csv") -> str
   Add the downloaded file's name, DOI, and paper name to a CSV file.
   Examples: add_to_csv("attention_is_all_you_need.pdf", "10.48550/arXiv.1706.03762", "Attention is all you need", "papers.csv")

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
- Only find the paper asked. After successfully finding one paper, do not try to find another paper.
"""


# ============================================================
# Tools — The functions the agent can call
# ============================================================

def find_doi(first_author: str, paper_name: str) -> str:
    """Find the DOI of an academic paper given the first author and paper title."""
    import urllib.request
    import urllib.parse
    import json
    try:
        query = urllib.parse.urlencode({
            'query.author': first_author,
            'query.title': paper_name,
            'select': 'DOI',
            'rows': 1
        })
        url = f"https://api.crossref.org/works?{query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:user@example.com'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            items = data.get('message', {}).get('items', [])
            if items:
                return json.dumps({"doi": items[0].get('DOI')})
            return json.dumps({"error": "No DOI found"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def download_paper(doi: str) -> str:
    """Get the direct PDF download URL for a given DOI using Sci-Hub."""
    import urllib.request
    import re
    import json
    try:
        domains = ["https://sci-hub.se", "https://sci-hub.st", "https://sci-hub.ru"]
        for domain in domains:
            try:
                url = f"{domain}/{doi}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    # Check if the response is directly a PDF file
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/pdf' in content_type or response.geturl().endswith('.pdf'):
                        return json.dumps({"pdf_url": response.geturl()})
                        
                    html = response.read().decode('utf-8', errors='ignore')
                    # Look for the PDF link in various tags (iframe, embed, object, download button)
                    patterns = [
                        r"id='target'.*?src='(.*?)'",
                        r"id='pdf'.*?src='(.*?)'",
                        r"<iframe.*?src=['\"](.*?)['\"]",
                        r"<embed.*?src=['\"](.*?)['\"]",
                        r"<object[^>]*?(?:data|src)\s*=\s*['\"]([^'\"]+)['\"]",
                        r"<div[^>]*class\s*=\s*['\"]download['\"][^>]*>\s*<a\s*href\s*=\s*['\"]([^'\"]+)['\"]"
                    ]
                    match = None
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            break

                    if match:
                        pdf_url = match.group(1).split('#')[0]
                        if pdf_url.startswith('//'):
                            pdf_url = 'https:' + pdf_url
                        elif pdf_url.startswith('/'):
                            pdf_url = domain + pdf_url
                        return json.dumps({"pdf_url": pdf_url})
            except Exception:
                continue
        return json.dumps({"error": "PDF link not found on Sci-Hub after trying multiple domains"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def save_pdf(pdf_url: str, file_name: str, folder: str = "papers") -> str:
    """Download and save a PDF file from a URL to a specified folder."""
    import urllib.request
    import os
    import json
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        if not file_name.endswith('.pdf'):
            file_name += '.pdf'
        filepath = os.path.join(folder, file_name)
        
        req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response, open(filepath, 'wb') as out_file:
            out_file.write(response.read())
            
        return json.dumps({"status": "Success", "saved_path": filepath})
    except Exception as e:
        return json.dumps({"error": str(e)})


def add_to_csv(file_name: str, doi: str, paper_name: str, csv_path: str = "papers.csv") -> str:
    """Add the file name, DOI, and paper name to a CSV file."""
    import csv
    import os
    import json
    try:
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['File Name', 'DOI', 'Paper Name'])
            writer.writerow([file_name, doi, paper_name])
        return json.dumps({"status": "Success", "csv_file": csv_path})
    except Exception as e:
        return json.dumps({"error": str(e)})


# Tool registry — maps tool names to functions
tools = {
    "find_doi": find_doi,
    "download_paper": download_paper,
    "save_pdf": save_pdf,
    "add_to_csv": add_to_csv,
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
# Run the agent!
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RESEARCH AGENT")
    print("  Let's see the agent loop in action!")
    print("=" * 60)

    # Test 1: Academic paper retrieval
    print("\n\n>>> TEST 1: Paper processing agent")
    run_agent(
        "Save the paper on Crispr Cas9 by Doudna, download it, and document it."
    )
