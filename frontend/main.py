"""FastAPI server for LoL Counter Coach (Hextech AI Assistant).

Supports two execution modes:
1. Local ADK Runner mode (default when AGENT_ENGINE_RESOURCE_NAME is not set):
   Runs `app.agent.root_agent` directly in-process using `GEMINI_API_KEY` from `.env`.
2. Remote Agent Engine A2A Proxy mode (when AGENT_ENGINE_RESOURCE_NAME is set):
   Proxies chat requests to a deployed Vertex AI Agent Runtime via A2A protocol.
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from app.a2ui_utils import _extract_a2ui_messages  # noqa: E402
from app.agent import app as adk_app  # noqa: E402
from google.adk.artifacts import InMemoryArtifactService  # noqa: E402
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

app = FastAPI()

_local_runner = Runner(
    app=adk_app,
    session_service=InMemorySessionService(),
    artifact_service=InMemoryArtifactService(),
    memory_service=InMemoryMemoryService(),
    auto_create_session=True,
)
_user_sessions: dict[str, str] = {}
_DATAPART_RE = re.compile(
    r"<a2a_datapart_json>(.*?)</a2a_datapart_json>", re.DOTALL
)


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


def _extract_adk_event_parts(content: types.Content | None) -> list[dict]:
    if not content or not content.parts:
        return []
    out: list[dict] = []
    for part in content.parts:
        if getattr(part, "thought", False):
            continue
        if getattr(part, "function_call", None) or getattr(part, "function_response", None):
            continue
        if getattr(part, "executable_code", None) or getattr(part, "code_execution_result", None):
            continue

        if part.inline_data and part.inline_data.data:
            raw_bytes = part.inline_data.data
            raw_str = (
                raw_bytes.decode("utf-8", errors="replace")
                if isinstance(raw_bytes, (bytes, bytearray))
                else str(raw_bytes)
            )
            matches = _DATAPART_RE.findall(raw_str)
            for m in matches:
                try:
                    payload = json.loads(m)
                    if isinstance(payload, dict) and "data" in payload:
                        out.append({"kind": "a2ui", "data": payload["data"]})
                except Exception:
                    pass
            continue

        text = (part.text or "").strip()
        if not text:
            continue

        a2ui_msgs = _extract_a2ui_messages(text)
        if a2ui_msgs:
            for msg in a2ui_msgs:
                out.append({"kind": "a2ui", "data": msg})
        else:
            out.append({"kind": "text", "text": text})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"

    session_id = _user_sessions.get(user_id)
    if not session_id:
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        _user_sessions[user_id] = session_id

    parts: list[dict] = []
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    async for event in _local_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        if event.author == "user":
            continue
        extracted = _extract_adk_event_parts(event.content)
        if extracted:
            parts = extracted

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
