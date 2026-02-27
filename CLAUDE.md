# CLAUDE.md — Instrucciones para Claude Code

Este archivo define las convenciones, estructura y reglas del proyecto para Claude Code.

## Descripción del proyecto

Agente de consulta y escritura multiplataforma que se conecta a PostgreSQL y Google Sheets
mediante servidores MCP (Model Context Protocol) propios escritos en Python.
El agente usa Claude Opus 4.6 como modelo central y se puede operar desde una CLI interactiva
o desde una interfaz web con streaming en tiempo real (FastAPI + SSE + autenticación JWT).

## Stack técnico

- **Lenguaje:** Python 3.11+
- **Modelo:** `claude-opus-4-6`
- **MCP client:** `mcp` Python — `ClientSession` + `stdio_client` + `session.initialize()`
- **API:** `anthropic.AsyncAnthropic` — loop agentivo directo (sin claude-agent-sdk)
- **MCP PostgreSQL:** `src/pg_server.py` (servidor Python propio)
- **MCP Google Sheets:** `src/sheets_server.py` (servidor Python propio)
- **Web:** `fastapi` + `uvicorn` — interfaz web multi-usuario con SSE
- **Auth:** `PyJWT` — tokens JWT firmados con `JWT_SECRET`, usuarios en `WEB_USERS`
- **CLI:** `rich` para formato y colores
- **Node.js:** no requerido

## Estructura del proyecto

```
agente-de-consulta/
├── src/
│   ├── agent.py          # MCPAgent — loop agentivo, run_query, stream_query
│   ├── auth.py           # JWT — authenticate_user, create_token, verify_token
│   ├── cli.py            # Interfaz de usuario (Rich CLI)
│   ├── config.py         # Configuración: MCPs opcionales, system prompt, env vars
│   ├── pg_server.py      # Servidor MCP PostgreSQL (query + execute)
│   ├── sheets_server.py  # Servidor MCP Google Sheets (5 herramientas)
│   └── web.py            # App FastAPI — auth, sesiones, endpoints SSE, static files
├── static/
│   ├── index.html        # Interfaz web de chat
│   ├── login.html        # Página de login
│   ├── app.js            # Cliente SSE, streaming, rendering, JWT en localStorage
│   └── style.css         # Estilos del chat y login
├── deploy/
│   ├── start.bat         # docker compose up -d --build
│   ├── stop.bat          # docker compose down
│   ├── logs.bat          # docker compose logs -f
│   └── update.bat        # git pull + rebuild + restart
├── sessions/             # Historiales por usuario (runtime, ignorado en git)
│   └── {username}/
│       └── history.json
├── credentials/          # Credenciales Google (no commitear)
├── Dockerfile            # Imagen Python 3.11-slim para producción
├── docker-compose.yml    # Puertos, volúmenes, restart always
├── .dockerignore
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

5. **`load_history(history)`** — carga historial desde formato JSON (dicts). Usado por `web.py`
   al restaurar sesiones desde disco.

6. **`_serialize_block(block)`** — convierte bloques del SDK de Anthropic a dicts con solo los
   campos que la API acepta de vuelta (`type`, `text` / `type`, `id`, `name`, `input`).
   Evita campos internos del SDK como `parsed_output` que la API rechaza en el historial.

## Autenticación web (JWT)

- `src/auth.py` centraliza toda la lógica: `authenticate_user`, `create_token`, `verify_token`
- Usuarios definidos en `WEB_USERS=user1:pass1,user2:pass2` en el `.env`
- Tokens firmados con `JWT_SECRET` (HS256), expiran a las 12 horas
- `web.py` usa la dependencia FastAPI `get_current_user` en todos los endpoints `/api/*`
- La sesión del agente se deriva del username del JWT (una sesión por usuario)
- El frontend guarda el token en `localStorage` y lo manda como `Authorization: Bearer`
- Un 401 en cualquier endpoint redirige al browser a `/login` automáticamente

## Persistencia del historial

- Al finalizar cada `stream_query`, `web.py` escribe `sessions/{username}/history.json`
- Al crear una sesión nueva, se carga el historial previo desde ese archivo
- El historial usa dicts JSON-serializables (no objetos SDK), gracias a `_serialize_block()`
- La carpeta `sessions/` está en `.gitignore`

## Convenciones de código

- Todo el código en **español funcional**: variables y funciones en inglés (snake_case),
  comentarios, docstrings y mensajes al usuario en español.
- Funciones asíncronas (`async/await`) para todas las llamadas al agente y a los MCPs.
- Cada módulo en `src/` tiene una responsabilidad única (separación de concerns).
- No hardcodear credenciales. Siempre usar `os.environ` o `python-dotenv`.
- Antes de agregar dependencias nuevas, verificar que no exista una forma nativa.

## Reglas para modificaciones

- `config.py` es el único lugar donde se define el `SYSTEM_PROMPT` y la config de MCPs.
- `auth.py` es el único lugar donde se define la lógica de JWT y usuarios.
- `agent.py` no debe tener lógica de presentación (prints, colores). Solo lógica del agente.
- `cli.py` no debe contener lógica de negocio. Solo UI y llamadas a `agent.py`.
- `web.py` no debe contener lógica de negocio. Solo routing HTTP, auth, sesiones y SSE.
- Al agregar un nuevo MCP, hacerlo en `build_mcp_servers()` en `config.py` y crear el
  servidor correspondiente en `src/` siguiendo el patrón de `pg_server.py`.
- Los servidores MCP se agregan como entrada opcional: si la variable de entorno no está
  definida o el archivo no existe, el agente arranca sin ese servidor.
- El frontend en `static/` no debe hacer lógica de negocio — solo renderizar eventos SSE.

## Variables de entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `ANTHROPIC_API_KEY` | API key de Anthropic | Sí |
| `WEB_USERS` | Usuarios web: `user1:pass1,user2:pass2` | Sí (modo web) |
| `JWT_SECRET` | Clave para firmar tokens JWT (mín. 32 chars) | Sí (modo web) |
| `DATABASE_URL` | Connection string de PostgreSQL | No (agente arranca sin DB) |
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

# Generar un JWT_SECRET seguro
python -c "import secrets; print(secrets.token_hex(32))"
```

## Comandos Docker (producción)

```bash
# Iniciar (construye imagen si no existe)
docker compose up -d --build

# Ver estado
docker compose ps

# Ver logs en tiempo real
docker compose logs -f

# Detener
docker compose down

# Actualizar (git pull + rebuild)
deploy\update.bat
```

## Fases del proyecto

Ver `README.md` para el roadmap completo.

- **Fase 1 ✅** Base del proyecto + PostgreSQL vía MCP propio
- **Fase 2 ✅** Escritura con confirmación + historial multi-turno + visibilidad de tools
- **Fase 3 ✅** Google Sheets MCP (lectura, escritura, append, descubrimiento)
- **Fase 4** Exportación de resultados + extended thinking
- **Fase 5 ✅** Interfaz web FastAPI con streaming SSE, sesiones multi-usuario,
  autenticación JWT, historial persistente por usuario y deploy Docker con scripts en `deploy/`
