"""
Gateway Client for Forms Agent (Seat 25).
Connects to glc_v4 over HTTP at http://127.0.0.1:8111 without holding any provider API keys.
Reuses the S13Code Gateway pattern and provides fallback when glc_v4 is offline.
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class GatewayClient:
    """Client to invoke glc_v4 model completions and budget-controlled chat endpoints."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("GLC_BASE_URL", "http://127.0.0.1:8111")).rstrip("/")
        self.provider = os.getenv("GLC_PROVIDER", "gemini")

    def is_online(self) -> bool:
        """Checks if glc_v4 gateway is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/healthz", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def complete(
        self,
        prompt: str,
        system: str = "You are the Forms Agent for Seat 25 on AgentSwitch.",
        *,
        session: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Request a model completion from glc_v4."""
        payload: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "system": system,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "agent": "forms_agent",
            "session": session or "forms_session",
            "provider": self.provider,
        }

        if HAS_HTTPX:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{self.base_url}/v1/chat", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return {
                            "text": data.get("text", ""),
                            "provider": data.get("provider", self.provider),
                            "model": data.get("model", "unknown"),
                            "status": "success",
                        }
            except Exception as e:
                pass  # Fall through to fallback below

        # Synchronous urllib fallback or offline mock reasoning
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/v1/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "text": data.get("text", ""),
                    "provider": data.get("provider", self.provider),
                    "model": data.get("model", "unknown"),
                    "status": "success",
                }
        except Exception as e:
            # Deterministic offline mock response aligned with UC-01
            return {
                "text": "UC-01 Autonomous Dynamic Supplier Onboarding Form Authoring & Activation Plan.",
                "provider": "offline_fallback",
                "model": "deterministic_v1",
                "status": "fallback",
                "fallback_reason": str(e),
            }
