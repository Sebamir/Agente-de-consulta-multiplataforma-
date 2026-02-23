#!/usr/bin/env python3
"""
Servidor MCP de Google Sheets con soporte de lectura y escritura.

Expone cinco herramientas:
  - sheets_list_files: lista todos los spreadsheets accesibles (via Drive API)
  - sheets_list_tabs:  lista las hojas (tabs) de un spreadsheet
  - sheets_read:       lee un rango de celdas
  - sheets_write:      escribe en un rango existente (UPDATE)
  - sheets_append:     agrega filas al final de una hoja

Autenticación: Service Account — JSON de credenciales pasado como primer argumento.

Uso: python sheets_server.py <GOOGLE_CREDENTIALS_PATH>
"""
import asyncio
import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",   # para listar archivos
]

# Ruta al JSON de la cuenta de servicio: argumento CLI o variable de entorno
CREDENTIALS_PATH = (
    sys.argv[1] if len(sys.argv) > 1
    else os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
)

server = Server("sheets-rw")


def _get_credentials():
    return service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )

def _get_service():
    """Crea y devuelve un cliente autenticado de la Sheets API."""
    return build("sheets", "v4", credentials=_get_credentials())

def _get_drive_service():
    """Crea y devuelve un cliente autenticado de la Drive API."""
    return build("drive", "v3", credentials=_get_credentials())


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="sheets_list_files",
            description=(
                "Lista todos los Google Spreadsheets accesibles por la cuenta de servicio. "
                "Devuelve el nombre y el ID de cada archivo. "
                "Usar para descubrir qué spreadsheets están disponibles sin necesitar el ID de antemano."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de archivos a devolver (por defecto 50).",
                        "default": 50,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="sheets_list_tabs",
            description=(
                "Lista el nombre de todas las hojas (tabs) dentro de un Google Spreadsheet. "
                "Usar para descubrir qué hojas existen antes de leer o escribir."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "El ID del spreadsheet (parte de la URL entre /d/ y /edit).",
                    }
                },
                "required": ["spreadsheet_id"],
            },
        ),
        types.Tool(
            name="sheets_read",
            description=(
                "Lee un rango de celdas de un Google Spreadsheet y devuelve los valores como JSON. "
                "El rango puede ser 'Sheet1!A1:D10', 'A:Z', o solo 'Sheet1'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "El ID del spreadsheet.",
                    },
                    "range": {
                        "type": "string",
                        "description": "Rango en notación A1, por ejemplo 'Sheet1!A1:D10'.",
                    },
                },
                "required": ["spreadsheet_id", "range"],
            },
        ),
        types.Tool(
            name="sheets_write",
            description=(
                "Escribe valores en un rango existente de un Google Spreadsheet (UPDATE). "
                "Usar SOLO después de confirmación explícita del usuario."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "El ID del spreadsheet.",
                    },
                    "range": {
                        "type": "string",
                        "description": "Rango destino en notación A1, por ejemplo 'Sheet1!B2:D4'.",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "Array de arrays con los valores a escribir (filas × columnas).",
                    },
                },
                "required": ["spreadsheet_id", "range", "values"],
            },
        ),
        types.Tool(
            name="sheets_append",
            description=(
                "Agrega filas al final de una hoja de Google Sheets. "
                "Usar SOLO después de confirmación explícita del usuario."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "El ID del spreadsheet.",
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Nombre de la hoja (tab) donde se agregarán las filas.",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "Array de arrays con las filas a agregar.",
                    },
                },
                "required": ["spreadsheet_id", "sheet_name", "values"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "sheets_list_files":
            limit = int(arguments.get("limit", 50))
            drive = _get_drive_service()
            results = drive.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                fields="files(id, name)",
                pageSize=min(limit, 100),
                orderBy="modifiedTime desc",
            ).execute()
            files = results.get("files", [])
            if not files:
                return [types.TextContent(
                    type="text",
                    text="No se encontraron spreadsheets. Asegurate de compartirlos con el email de la cuenta de servicio.",
                )]
            return [types.TextContent(
                type="text",
                text=json.dumps(files, ensure_ascii=False),
            )]

        service = _get_service()
        sheets = service.spreadsheets()

        if name == "sheets_list_tabs":
            spreadsheet_id = arguments["spreadsheet_id"]
            meta = sheets.get(spreadsheetId=spreadsheet_id).execute()
            tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
            return [types.TextContent(
                type="text",
                text=json.dumps(tabs, ensure_ascii=False),
            )]

        elif name == "sheets_read":
            spreadsheet_id = arguments["spreadsheet_id"]
            range_ = arguments["range"]
            result = sheets.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_,
            ).execute()
            values = result.get("values", [])
            if not values:
                return [types.TextContent(type="text", text="(sin datos en el rango)")]
            return [types.TextContent(
                type="text",
                text=json.dumps(values, ensure_ascii=False),
            )]

        elif name == "sheets_write":
            spreadsheet_id = arguments["spreadsheet_id"]
            range_ = arguments["range"]
            values = arguments["values"]
            result = sheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            ).execute()
            updated = result.get("updatedCells", 0)
            return [types.TextContent(
                type="text",
                text=f"Escritura completada. Celdas actualizadas: {updated}.",
            )]

        elif name == "sheets_append":
            spreadsheet_id = arguments["spreadsheet_id"]
            sheet_name = arguments["sheet_name"]
            values = arguments["values"]
            result = sheets.values().append(
                spreadsheetId=spreadsheet_id,
                range=sheet_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
            updates = result.get("updates", {})
            added = updates.get("updatedRows", len(values))
            return [types.TextContent(
                type="text",
                text=f"Append completado. Filas agregadas: {added}.",
            )]

        else:
            return [types.TextContent(type="text", text=f"Herramienta desconocida: {name}")]

    except HttpError as e:
        return [types.TextContent(type="text", text=f"Error de Google API: {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main():
    if not CREDENTIALS_PATH:
        print("Error: GOOGLE_CREDENTIALS_PATH no definida.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(CREDENTIALS_PATH):
        print(f"Error: archivo de credenciales no encontrado: {CREDENTIALS_PATH}", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
