# CLAUDE.md — Instrucciones para Claude Code

Este archivo define las convenciones, estructura y reglas del proyecto para Claude Code.

## Descripción del proyecto

Agente de consulta y escritura multiplataforma que se conecta a PostgreSQL y Google Sheets
mediante servidores MCP (Model Context Protocol) propios escritos en Python.
El agente usa Claude Opus 4.6 como modelo central y se puede operar desde una CLI interactiva
o desde una interfaz web con streaming en tiempo real (FastAPI + SSE).

## Stack técnico

- **Lenguaje:** Python 3.11+
- **Modelo:** `claude-opus-4-6`
- **MCP client:** `mcp` Python — `ClientSession` + `stdio_client` + `session.initialize()`
- **API:** `anthropic.AsyncAnthropic` — loop agentivo directo (sin claude-agent-sdk)
- **MCP PostgreSQL:** `src/pg_server.py` (servidor Python propio)
- **MCP Google Sheets:** `src/sheets_server.py` (servidor Python propio)
- **Web:** `fastapi` + `uvicorn` — interfaz web multi-usuario con SSE
- **CLI:** `rich` para formato y colores
- **Node.js:** no requerido

## Estructura del proyecto

```
agente-de-consulta/
├── src/
│   ├── agent.py          # MCPAgent — loop agentivo, run_query, stream_query
│   ├── cli.py            # Interfaz de usuario (Rich CLI)
│   ├── config.py         # Configuración: MCPs, system prompt, env vars
│   ├── pg_server.py      # Servidor MCP PostgreSQL (query + execute)
│   ├── sheets_server.py  # Servidor MCP Google Sheets (5 herramientas)
│   └── web.py            # App FastAPI — sesiones, endpoint SSE, static files
├── static/
│   ├── index.html        # Interfaz web de chat
│   ├── app.js            # Cliente SSE, streaming, rendering
│   └── style.css         # Estilos del chat
├── credentials/          # Credenciales Google (no commitear)
├── main.py               # Punto de entrada — python main.py / --web
├── test_concurrency.py   # Test de sesiones simultáneas
├── .env                  # Variables de entorno (no commitear)
├── .env.example          # Plantilla de variables
├── .gitignore
├── requirements.txt
├── CLAUDE.md             # Este archivo
└── README.md
```

## Arquitectura del agente

`MCPAgent` en `agent.py` funciona así:

1. **`connect()`** — itera `build_mcp_servers()`, inicia cada servidor con `stdio_client`,
   crea una `ClientSession`, llama `await session.initialize()` y registra las herramientas
   con su campo interno `_server` (para routing).

2. **`run_query(prompt)`** — loop agentivo (usado por la CLI):
   - Envía el historial completo + todas las herramientas a la API de Claude
   - Si `stop_reason == "tool_use"`: ejecuta cada tool vía `session.call_tool()` y agrega
     el resultado al historial
   - Repite hasta `stop_reason == "end_turn"` o alcanzar `MAX_TURNS`

3. **`stream_query(prompt)`** — variante async generator (usada por la web):
   - Idéntica lógica que `run_query`, pero usa `client.messages.stream()` de Anthropic
   - Emite eventos `{"type": "text"|"tool_call"|"tool_result"|"done"|"error", ...}`
   - El endpoint SSE de `web.py` convierte estos eventos en líneas `data: ...\n\n`

4. **`_call_tool(name, input)`** — busca en `_tools` el `_server` que provee la herramienta
   y despacha al `ClientSession` correcto.

## Convenciones de código

- Todo el código en **español funcional**: variables y funciones en inglés (snake_case),
  comentarios, docstrings y mensajes al usuario en español.
- Funciones asíncronas (`async/await`) para todas las llamadas al agente y a los MCPs.
- Cada módulo en `src/` tiene una responsabilidad única (separación de concerns).
- No hardcodear credenciales. Siempre usar `os.environ` o `python-dotenv`.
- Antes de agregar dependencias nuevas, verificar que no exista una forma nativa.

## Reglas para modificaciones

- `config.py` es el único lugar donde se define el `SYSTEM_PROMPT` y la config de MCPs.
- `agent.py` no debe tener lógica de presentación (prints, colores). Solo lógica del agente.
- `cli.py` no debe contener lógica de negocio. Solo UI y llamadas a `agent.py`.
- `web.py` no debe contener lógica de negocio. Solo routing HTTP, sesiones y serialización SSE.
- Al agregar un nuevo MCP, hacerlo en `build_mcp_servers()` en `config.py` y crear el
  servidor correspondiente en `src/` siguiendo el patrón de `pg_server.py`.
- Los servidores MCP se agregan como entrada opcional: si la variable de entorno no está
  definida o el archivo no existe, el agente arranca sin ese servidor.
- El frontend en `static/` no debe hacer lógica de negocio — solo renderizar eventos SSE.

## Variables de entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `ANTHROPIC_API_KEY` | API key de Anthropic | Sí |
| `DATABASE_URL` | Connection string de PostgreSQL | Sí |
| `GOOGLE_CREDENTIALS_PATH` | Ruta al JSON de la cuenta de servicio Google | No |

## Comandos de desarrollo

```bash
# Activar entorno virtual (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# CLI interactiva
python main.py

# Interfaz web (http://localhost:8000)
python main.py --web

# Test de concurrencia (requiere --web corriendo en otra terminal)
python test_concurrency.py

# Probar el agente sin CLI (modo directo)
python src/agent.py
```

## Fases del proyecto

Ver `README.md` para el roadmap completo.

- **Fase 1 ✅** Base del proyecto + PostgreSQL vía MCP propio
- **Fase 2 ✅** Escritura con confirmación + historial multi-turno + visibilidad de tools
- **Fase 3 ✅** Google Sheets MCP (lectura, escritura, append, descubrimiento)
- **Fase 4** Exportación de resultados + extended thinking
- **Fase 5 ✅** Interfaz web FastAPI con streaming SSE y sesiones multi-usuario
