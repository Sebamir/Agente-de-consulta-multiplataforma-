"""
Interfaz web del agente — FastAPI + SSE.

Arranca con: python main.py --web
Acceder en:  http://localhost:8000
"""
import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import MCPAgent

# Directorio raíz del proyecto (un nivel arriba de src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

# Pool de sesiones: session_id → MCPAgent
_sessions: dict[str, MCPAgent] = {}


async def get_or_create_session(session_id: str) -> MCPAgent:
    """Devuelve la sesión existente o crea una nueva y la conecta."""
    if session_id not in _sessions:
        agent = MCPAgent()
        await agent.connect()
        _sessions[session_id] = agent
    return _sessions[session_id]

 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Limpia todas las sesiones MCP al cerrar el servidor."""
    yield
    for agent in _sessions.values():
        await agent.cleanup()
    _sessions.clear()


app = FastAPI(title="Agente de Consulta", lifespan=lifespan)

# Servir archivos estáticos (CSS, JS)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Schemas ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    session_id: str
    prompt: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/api/query")
async def query(body: QueryRequest):
    """
    Recibe un prompt y devuelve un stream SSE con eventos del agente.
    El cliente debe leer el stream hasta recibir un evento de tipo 'done' o 'error'.
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")

    agent = await get_or_create_session(body.session_id)

    async def event_stream():
        try:
            async for event in agent.stream_query(body.prompt):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # desactiva buffering en proxies nginx
        },
    )


@app.post("/api/session/{session_id}/clear")
async def clear_session(session_id: str):
    """Borra el historial de conversación de una sesión sin cerrar la conexión MCP."""
    if session_id in _sessions:
        _sessions[session_id].clear_history()
    return {"ok": True}


@app.get("/api/session/{session_id}/status")
async def session_status(session_id: str):
    """Informa si una sesión existe y cuántos mensajes tiene en el historial."""
    if session_id not in _sessions:
        return {"active": False, "history_length": 0}
    agent = _sessions[session_id]
    return {"active": True, "history_length": len(agent._history)}
