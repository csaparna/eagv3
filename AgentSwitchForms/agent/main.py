"""
CLI and Service entry point for Forms Agent (Seat 25).
"""
from __future__ import annotations

import argparse
import sys
import uvicorn
from .runner import FormsAgentRunner


def main():
    parser = argparse.ArgumentParser(description="AgentSwitch Forms Agent (Seat 25)")
    parser.add_argument("prompt", nargs="?", default="", help="Natural language ask to execute")
    parser.add_argument("--serve", action="store_true", help="Start the interactive Agent Web UI server")
    parser.add_argument("--port", type=int, default=8125, help="Port for the UI server (default 8125)")
    parser.add_argument("--poll-chat", action="store_true", help="Poll the AgentSwitch UI chat bot for incoming questions")

    args = parser.parse_args()
    runner = FormsAgentRunner()

    if args.serve:
        print(f"Starting Forms Agent Web UI on http://127.0.0.1:{args.port} ...")
        uvicorn.run("agent.ui_server:app", host="127.0.0.1", port=args.port, reload=False)
        return

    if args.poll_chat:
        print("Polling AgentSwitch UI chat bot for latest question...")
        res = runner.process_latest_ui_chat_question()
        if not res:
            print("No new chat questions found.")
        else:
            print(f"Executed question: {res.get('prompt')}")
            print(f"Reply: {res.get('reply')}")
        return

    prompt = args.prompt.strip()
    if not prompt:
        prompt = "Build and publish our supplier onboarding form with compliance consent."

    print(f"Executing ask: {prompt}")
    res = runner.execute_prompt(prompt)
    print("\n--- Execution Result ---")
    print(f"Success: {res.get('success')}")
    print(f"Is Refusal: {res.get('is_refusal')}")
    print(f"Reply: {res.get('reply')}")
    if res.get("ui_link"):
        print(f"Live Form UI: {res.get('ui_link')}")


if __name__ == "__main__":
    main()
