"""
    GEMINI_MODEL=gemini-2.5-flash-lite
"""
from google import genai
import os
import time
from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
THROTTLE_SECONDS = 10  # Wait before each LLM call to stay under free-tier RPM limits

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def ask(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response.

    Sleeps for THROTTLE_SECONDS before each call to stay under the free-tier
    rate limit (Gemini 3.1 Flash Lite: 15 RPM, 500 RPD).
    """
    print(f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text

print(f"Using model: {GEMINI_MODEL}\n")

# Test 1:
print("=" * 50)
print("Test agentic question")
print("=" * 50)
q1 = "Save the paper on Crispr Cas9 by Doudna, download it, and document it."
print(f"Q: {q1}")
print(f"A: {ask(q1)}")
