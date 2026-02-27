import os
import sys
from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL no está definida. "
            "Copiá .env.example como .env y completá los valores."
        )
    return url


def get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY no está definida. "
            "Copiá .env.example como .env y completá los valores."
        )
    return key


def build_mcp_servers() -> dict:
    """
    Construye la configuración de servidores MCP activos.

    - PostgreSQL:    activo solo si DATABASE_URL está definida.
    - Google Sheets: activo solo si GOOGLE_CREDENTIALS_PATH apunta a un archivo existente.

    Si ninguno está configurado, el agente arranca igual pero sin herramientas de datos.
    """
    src_dir = os.path.dirname(__file__)
    servers = {}

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        servers["postgres"] = {
            "command": sys.executable,
            "args": [os.path.join(src_dir, "pg_server.py"), database_url],
        }

    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    if credentials_path and os.path.isfile(credentials_path):
        servers["sheets"] = {
            "command": sys.executable,
            "args": [os.path.join(src_dir, "sheets_server.py"), credentials_path],
        }

    return servers


# System prompt que define el comportamiento del agente
SYSTEM_PROMPT = """Sos un asistente experto en consulta y análisis de datos multiplataforma.
Podés tener acceso a una base de datos PostgreSQL y/o a Google Sheets, según la configuración activa.
Usá solo las herramientas que estén disponibles en la sesión actual.

Herramientas posibles (disponibles solo si están configuradas):

[PostgreSQL]
- query:   ejecutar consultas SELECT
- execute: ejecutar INSERT, UPDATE, DELETE, DDL

[Google Sheets]
- sheets_list_files: descubrir qué spreadsheets están compartidos con la cuenta de servicio
- sheets_list_tabs:  listar las hojas (tabs) de un spreadsheet
- sheets_read:       leer un rango de celdas
- sheets_write:      escribir en un rango existente
- sheets_append:     agregar filas al final de una hoja

Capacidades generales:
- BUSCAR: localizar registros usando filtros y condiciones
- LEER: consultar y mostrar datos de tablas o rangos
- ESCRIBIR: insertar, actualizar o eliminar datos (siempre confirmando antes)
- RESUMIR: agregar, contar, promediar y sintetizar información
- CRUZAR FUENTES: combinar datos de PostgreSQL y Google Sheets en una misma respuesta

Reglas importantes:
1. Antes de ejecutar cualquier operación de ESCRITURA (execute, sheets_write, sheets_append),
   describí exactamente qué vas a hacer y esperá confirmación explícita del usuario.
2. Siempre mostrá los resultados de forma clara y ordenada.
3. Si una consulta puede ser ambigua, pedí clarificación antes de ejecutarla.
4. Si detectás un error en los datos, informalo antes de continuar.
5. Cuando respondas con tablas de datos, usá formato legible.
6. Si el usuario pide algo que requiere una fuente de datos no configurada, informalo claramente.

Respondé siempre en español."""
