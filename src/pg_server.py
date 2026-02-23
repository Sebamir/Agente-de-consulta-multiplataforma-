#!/usr/bin/env python3
"""
Servidor MCP de PostgreSQL con soporte completo de lectura y escritura.

Expone dos herramientas:
  - query:   SELECT (transacción de solo lectura)
  - execute: INSERT / UPDATE / DELETE / DDL (transacción de escritura con commit)

Uso: python pg_server.py <DATABASE_URL>
"""
import asyncio
import json
import os
import sys

import psycopg2
import psycopg2.extras
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# DATABASE_URL: primer argumento de línea de comandos o variable de entorno
DATABASE_URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL", "")

server = Server("postgres-rw")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query",
            description=(
                "Ejecuta una consulta SELECT en PostgreSQL y devuelve los resultados como JSON.  "
                "Usar para leer datos sin modificar la base."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "La consulta SQL SELECT a ejecutar.",
                    }
                },
                "required": ["sql"],
            },
        ),
        types.Tool(
            name="execute",
            description=(
                "Ejecuta una sentencia de escritura en PostgreSQL "
                "(INSERT, UPDATE, DELETE, CREATE, ALTER, etc.) y confirma los cambios. "
                "Usar SOLO después de confirmación explícita del usuario."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "La sentencia SQL de escritura a ejecutar.",
                    }
                },
                "required": ["sql"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    sql = (arguments.get("sql") or "").strip()
    if not sql:
        return [types.TextContent(type="text", text="Error: SQL vacío.")]

    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            if name == "query":
                # Transacción de solo lectura — cualquier intento de escritura falla
                conn.set_session(readonly=True, autocommit=True)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql)
                    rows = cur.fetchall()
                if not rows:
                    return [types.TextContent(type="text", text="(sin resultados)")]
                text = json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)
                return [types.TextContent(type="text", text=text)]

            elif name == "execute":
                # Transacción de escritura con commit explícito
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute(sql)
                    affected = cur.rowcount
                conn.commit()
                return [types.TextContent(
                    type="text",
                    text=f"Operación completada. Filas afectadas: {affected}.",
                )]

            else:
                return [types.TextContent(type="text", text=f"Herramienta desconocida: {name}")]

        finally:
            conn.close()

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error de base de datos: {e}")]


async def main():
    if not DATABASE_URL:
        print("Error: DATABASE_URL no definida.", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
