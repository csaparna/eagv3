"""
Web UI Server for AgentSwitch Forms Agent.
Provides an interactive web dashboard for natural language interaction, live graph execution,
UI chat bot polling, and form preview.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .runner import FormsAgentRunner
from .gateway import GatewayClient

app = FastAPI(title="AgentSwitch Forms Agent UI", version="1.0.0")

STATIC_DIR = Path(__file__).parent.parent / "static"
runner = FormsAgentRunner()
gateway = GatewayClient()


class PromptRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h2>Forms Agent UI Dashboard</h2><p>Static index.html not found.</p>")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "agent_seat": "Seat 25 (forms)",
        "live_platform": runner.client.is_live(),
        "glc_gateway_online": gateway.is_online(),
    }


@app.post("/api/run")
async def run_prompt(req: PromptRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")
    result = runner.execute_prompt(req.prompt, session_id=req.session_id)
    return result


@app.post("/api/chat/poll")
async def poll_ui_chat():
    """Polls AgentSwitch UI chat bot for incoming questions and executes them."""
    result = runner.process_latest_ui_chat_question()
    if not result:
        return {"found": False, "message": "No unhandled questions in UI chat session."}
    return {"found": True, "data": result}
