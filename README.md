# Agente de Consulta Multiplataforma

Agente de IA conversacional que se conecta a **PostgreSQL** y **Google Sheets** para realizar operaciones de lectura y escritura en lenguaje natural. El agente interpreta consultas del usuario, genera y ejecuta las operaciones necesarias, y devuelve respuestas claras — sin necesidad de escribir SQL ni fórmulas manualmente.

## Capacidades

| Operación | Descripción |
|-----------|-------------|
| **Buscar** | Localizar registros con filtros, condiciones y búsqueda de texto |
| **Leer** | Consultar y visualizar datos de tablas o rangos de celdas |
| **Escribir** | Insertar, actualizar y eliminar registros (con confirmación previa) |
| **Resumir** | Agregaciones, conteos, promedios y síntesis de información |
| **Cruzar fuentes** | Combinar datos de PostgreSQL y Google Sheets en una misma respuesta |

## Stack tecnológico

- **Modelo:** Claude Opus 4.6 (Anthropic)
- **MCP:** `mcp` Python client — servidores propios en Python
  - PostgreSQL → `src/pg_server.py` (lectura + escritura)
  - Google Sheets → `src/sheets_server.py` (lectura + escritura + descubrimiento)
- **API:** `anthropic` Python SDK — loop agentivo directo con streaming
- **Web:** FastAPI + uvicorn + SSE — interfaz web multi-usuario con autenticación JWT
- **Auth:** JWT (`PyJWT`) — usuarios definidos en `.env`, tokens con expiración
- **Lenguaje:** Python 3.11+
- **CLI:** `rich` para formato y colores

## Instalación

### Opción A — Docker (recomendado para producción)

**Prerrequisito:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd agente-de-consulta

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con ANTHROPIC_API_KEY, WEB_USERS, JWT_SECRET
# y opcionalmente DATABASE_URL y GOOGLE_CREDENTIALS_PATH

# 3. Iniciar
deploy\start.bat        # Windows
# o: docker compose up -d --build
```

El contenedor arranca automáticamente con Windows gracias a `restart: always`.

**Scripts disponibles en `deploy/`:**

| Script | Acción |
|--------|--------|
| `start.bat` | Construye la imagen y arranca el contenedor |
| `stop.bat` | Detiene el contenedor |
| `logs.bat` | Muestra los logs en tiempo real |
| `update.bat` | `git pull` + reconstruye + reinicia |

> **Nota Docker + DB local:** si `DATABASE_URL` apunta a `localhost`, reemplazarlo por
> `host.docker.internal` (Windows/Mac) o la IP de la red (`192.168.x.x`).

### Opción B — Python directo (desarrollo / CLI)

**Prerrequisitos:** Python 3.11+  _(Node.js no requerido)_

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd agente-de-consulta

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con las credenciales necesarias

# 5. Ejecutar
python main.py
```

## Configuración de Google Sheets (opcional)

Si no se configura, el agente arranca igual sin las herramientas de Sheets.

1. Ir a [console.cloud.google.com](https://console.cloud.google.com) → crear un proyecto
2. Habilitar **Google Sheets API** y **Google Drive API**
3. Crear una **cuenta de servicio** → generar clave JSON → guardar en `credentials/`
4. Compartir cada spreadsheet con el `client_email` del JSON
5. Agregar en `.env`:
   ```
   GOOGLE_CREDENTIALS_PATH=./credentials/google-service-account.json
   ```

## Modos de uso

### Interfaz web (multi-usuario, con autenticación y streaming)

```bash
python main.py --web
# Abrir http://localhost:8000
```

- Login con usuario y contraseña (definidos en `WEB_USERS` del `.env`)
- Cada usuario tiene su propia sesión aislada
- Historial de conversación persistente (sobrevive reinicios del servidor)
- Respuestas en tiempo real token a token
- Acordeón amarillo que muestra cada herramienta ejecutada (SQL, inputs, resultados)
- Botón "Nueva sesión" para limpiar el historial
- Botón "Cerrar sesión" para hacer logout

### CLI interactiva (un usuario)

```bash
python main.py
```

```
╔══════════════════════════════════════════╗
║     AGENTE DE CONSULTA MULTIPLATAFORMA   ║
║         PostgreSQL + Google Sheets       ║
╚══════════════════════════════════════════╝

Consulta: Listá todas las tablas disponibles
Consulta: Mostrá los últimos 10 pedidos del cliente "Acme Corp"
Consulta: ¿Cuántas ventas hubo por mes en 2024?
Consulta: Actualizá el stock del producto 42 a 150 unidades
Consulta: Qué spreadsheets tengo disponibles en Sheets?
Consulta: Leé el rango A1:D20 del sheet "Presupuesto"
```

**Comandos de la CLI:**

| Comando | Acción |
|---------|--------|
| `/ayuda` | Muestra la ayuda |
| `/limpiar` | Limpia la pantalla y reinicia el historial de conversación |
| `/salir` | Termina la sesión |

## Estructura del proyecto

```
agente-de-consulta/
├── src/
│   ├── agent.py          # MCPAgent — loop agentivo, run_query, stream_query
│   ├── auth.py           # Autenticación JWT — usuarios, tokens, verificación
│   ├── cli.py            # Interfaz de usuario (Rich CLI)
│   ├── config.py         # Configuración: MCPs (opcionales), system prompt, env vars
│   ├── pg_server.py      # Servidor MCP PostgreSQL (query + execute)
│   ├── sheets_server.py  # Servidor MCP Google Sheets (5 herramientas)
│   └── web.py            # API FastAPI + auth + sesiones + endpoints SSE
├── static/
│   ├── index.html        # Interfaz web de chat
│   ├── login.html        # Página de login
│   ├── app.js            # Cliente SSE, streaming, rendering, auth
│   └── style.css         # Estilos del chat y login
├── deploy/
│   ├── start.bat         # docker compose up -d --build
│   ├── stop.bat          # docker compose down
│   ├── logs.bat          # docker compose logs -f
│   └── update.bat        # git pull + rebuild + restart
├── sessions/             # Historiales por usuario (generado en runtime, no commitear)
│   └── {username}/
│       └── history.json
├── credentials/          # Credenciales Google (no commitear)
├── Dockerfile            # Imagen Python 3.11-slim
├── docker-compose.yml    # Puertos, volúmenes, restart always
├── .dockerignore
├── main.py               # Punto de entrada — CLI o --web
├── test_concurrency.py   # Test de sesiones simultáneas
├── .env                  # Variables de entorno (no commitear)
├── .env.example          # Plantilla de variables
├── .gitignore
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Variables de entorno

Copiá `.env.example` como `.env` y completá los valores:

```env
ANTHROPIC_API_KEY=sk-ant-...

# Autenticación web
WEB_USERS=admin:mi-contraseña,usuario2:otra-clave
JWT_SECRET=clave-aleatoria-de-al-menos-32-caracteres

# PostgreSQL (opcional — si no está, el agente arranca sin herramientas de DB)
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/nombre_db

# Google Sheets (opcional)
GOOGLE_CREDENTIALS_PATH=./credentials/google-service-account.json
```

Para generar un `JWT_SECRET` seguro:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Roadmap

### Fase 1 — Base del proyecto ✅
- [x] Estructura del proyecto
- [x] Servidor MCP propio para PostgreSQL (`pg_server.py`)
- [x] Agente central con Claude Opus 4.6
- [x] CLI interactiva con Rich

### Fase 2 — Escritura y contexto ✅
- [x] Operaciones de escritura con confirmación del usuario
- [x] Historial de conversación (contexto multi-turno)
- [x] Visibilidad de herramientas ejecutadas (SQL y resultados)

### Fase 3 — Google Sheets ✅
- [x] Servidor MCP propio para Google Sheets (`sheets_server.py`)
- [x] Autenticación con cuenta de servicio Google
- [x] Descubrimiento automático de spreadsheets (`sheets_list_files`)
- [x] Lectura de rangos y hojas específicas
- [x] Escritura y append de filas

### Fase 4 — Consultas complejas multi-fuente
- [ ] Exportación de resultados (CSV, JSON)
- [ ] Resúmenes automáticos con extended thinking
- [ ] Soporte para múltiples bases de datos simultáneas

### Fase 5 — Interfaz web ✅
- [x] API FastAPI con endpoints SSE para streaming
- [x] Frontend HTML/JS servido por FastAPI (sin build step)
- [x] Sesiones independientes por usuario (pool de MCPAgents)
- [x] Streaming token a token con acordeón de tool calls
- [x] Autenticación JWT con usuarios definidos en `.env`
- [x] Historial persistente por usuario (sobrevive reinicios)
- [x] Deploy con Docker — imagen portable, restart automático, scripts en `deploy/`
- [x] Fuentes de datos opcionales — el agente arranca sin DB si `DATABASE_URL` no está definida
- [ ] Panel de administración de conexiones / sesiones activas

---

## Licencia

MIT
