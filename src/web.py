"""
Interfaz web del agente — FastAPI + SSE + JWT.

Arranca con: python main.py --web
Acceder en:  http://localhost:8000
"""
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import MCPAgent
from auth import authenticate_user, create_token, verify_token
from config import build_mcp_servers

# Directorios
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR   = os.path.join(PROJECT_ROOT, "static")
SESSIONS_DIR = Path(PROJECT_ROOT) / "sessions"

# Pool de sesiones: username → MCPAgent
_sessions: dict[str, MCPAgent] = {}


# ── Persistencia del historial ────────────────────────────────────────────────

def _history_path(username: str) -> Path:
    return SESSIONS_DIR / username / "history.json"


def _load_history(username: str) -> list:
    """Carga el historial desde disco. Devuelve lista vacía si no existe."""
    path = _history_path(username)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_history(username: str, history: list):
    """Persiste el historial en disco (sessions/<username>/history.json)."""
    path = _history_path(username)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


# ── Sesiones MCP ──────────────────────────────────────────────────────────────

async def get_or_create_session(username: str) -> MCPAgent:
    """Devuelve la sesión existente o crea una nueva, cargando el historial previo."""
    if username not in _sessions:
        agent = MCPAgent()
        await agent.connect()
        agent.load_history(_load_history(username))
        _sessions[username] = agent
    return _sessions[username]


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


# ── Autenticación ─────────────────────────────────────────────────────────────

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Dependencia FastAPI: valida el JWT Bearer y devuelve el username."""
    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return username


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class QueryRequest(BaseModel):
    prompt: str


# ── Endpoints públicos ────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.post("/auth/login")
async def login(body: LoginRequest):
    """Valida credenciales y devuelve un JWT. No requiere autenticación previa."""
    if not authenticate_user(body.username, body.password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_token(body.username)
    return {"access_token": token, "token_type": "bearer"}


# ── Endpoints protegidos ──────────────────────────────────────────────────────

@app.post("/api/query")
async def query(
    body: QueryRequest,
    username: str = Depends(get_current_user),
):
    """
    Recibe un prompt y devuelve un stream SSE con eventos del agente.
    La sesión se deriva del username del JWT (una sesión por usuario).
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")

    agent = await get_or_create_session(username)

    async def event_stream():
        try:
            async for event in agent.stream_query(body.prompt):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
        finally:
            # Persistir historial después de cada consulta
            _save_history(username, agent._history)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/session/clear")
async def clear_session(username: str = Depends(get_current_user)):
    """Borra el historial de conversación sin cerrar la conexión MCP."""
    if username in _sessions:
        _sessions[username].clear_history()
        _save_history(username, [])
    return {"ok": True}


@app.get("/api/session/status")
async def session_status(username: str = Depends(get_current_user)):
    """Informa si la sesión del usuario existe y cuántos mensajes tiene."""
    if username not in _sessions:
        return {"active": False, "history_length": 0}
    agent = _sessions[username]
    return {"active": True, "history_length": len(agent._history)}


@app.get("/api/services")
async def services(username: str = Depends(get_current_user)):
    """
    Devuelve qué servicios están configurados y cuáles conectados exitosamente.
    Crea la sesión si aún no existe (dispara la conexión a los MCPs).
    """
    agent = await get_or_create_session(username)
    configured = list(build_mcp_servers().keys())
    connected  = agent.connected_servers()
    return {"configured": configured, "connected": connected}
