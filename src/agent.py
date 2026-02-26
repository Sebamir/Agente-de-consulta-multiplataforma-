import asyncio
import json
from contextlib import AsyncExitStack
from typing import AsyncGenerator

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import build_mcp_servers, get_anthropic_key, SYSTEM_PROMPT

MAX_TURNS = 20


class MCPAgent:
    """
    Agente que conecta a uno o más servidores MCP y usa Claude directamente
    para ejecutar consultas en un loop agentivo.
    """

    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._client = None
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[dict] = []
        self._history: list[dict] = []   # historial de la sesión completa

    async def connect(self):
        """
        Inicializa el cliente Anthropic y conecta a todos los servidores MCP
        definidos en config.build_mcp_servers().
        """
        self._client = anthropic.AsyncAnthropic(api_key=get_anthropic_key())

        for name, cfg in build_mcp_servers().items():
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            # Inicialización obligatoria del protocolo MCP
            await session.initialize()

            # Registrar herramientas del servidor con su prefijo de origen
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                self._tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                    "_server": name,   # campo interno, no se envía a la API
                })
            self._sessions[name] = session

    async def run_query(self, user_prompt: str, on_tool_call=None) -> str:
        """
        Ejecuta una consulta en modo agentivo:
        1. Envía el prompt a Claude con las herramientas disponibles.
        2. Si Claude pide una tool_use, la ejecuta vía MCP y devuelve el resultado.
        3. Repite hasta obtener una respuesta de texto final o alcanzar MAX_TURNS.

        Args:
            user_prompt: La consulta en lenguaje natural.
            on_tool_call: Callback opcional que recibe (tool_name, tool_input, result)
                          después de cada ejecución de herramienta.
        """
        # Herramientas en el formato que espera la API de Anthropic
        api_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._tools
        ]

        # Agregar el nuevo mensaje del usuario al historial persistente
        self._history.append({"role": "user", "content": user_prompt})

        for _ in range(MAX_TURNS):
            response = await self._client.messages.create(
                model="claude-opus-4-6",
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=api_tools,
                messages=self._history,
            )

            # Agregar la respuesta del asistente al historial persistente
            # (model_dump convierte SDK objects a dicts JSON-serializables)
            self._history.append({"role": "assistant", "content": [_serialize_block(b) for b in response.content]})

            # Si Claude terminó de razonar, devolver el texto
            if response.stop_reason == "end_turn":
                return _extract_text(response.content)

            # Si Claude pide herramientas, ejecutarlas todas
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    result = await self._call_tool(block.name, block.input)

                    if on_tool_call:
                        on_tool_call(block.name, block.input, result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                self._history.append({"role": "user", "content": tool_results})
                continue

            # stop_reason inesperado
            break

        return _extract_text(response.content) or "El agente no devolvió una respuesta."

    async def stream_query(self, user_prompt: str) -> AsyncGenerator[dict, None]:
        """
        Versión streaming del loop agentivo para la interfaz web.

        Yields dicts con los siguientes tipos de evento:
          {"type": "text",        "content": "..."}      — token de texto de Claude
          {"type": "tool_call",   "tool": "...", "input": {...}}  — antes de ejecutar tool
          {"type": "tool_result", "tool": "...", "result": "..."} — resultado de la tool
          {"type": "done"}                                — fin de la respuesta
          {"type": "error",       "message": "..."}       — error en cualquier punto
        """
        api_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._tools
        ]

        self._history.append({"role": "user", "content": user_prompt})

        for _ in range(MAX_TURNS):
            tool_results = []

            async with self._client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=api_tools,
                messages=self._history,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "text", "content": text}
                message = await stream.get_final_message()

            self._history.append({"role": "assistant", "content": [_serialize_block(b) for b in message.content]})

            if message.stop_reason == "end_turn":
                yield {"type": "done"}
                return

            if message.stop_reason == "tool_use":
                for block in message.content:
                    if block.type != "tool_use":
                        continue

                    yield {"type": "tool_call", "tool": block.name, "input": block.input}
                    result = await self._call_tool(block.name, block.input)
                    yield {"type": "tool_result", "tool": block.name, "result": result}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                self._history.append({"role": "user", "content": tool_results})
                continue

            # stop_reason inesperado
            yield {"type": "done"}
            return

        yield {"type": "error", "message": "Se alcanzó el límite máximo de turnos."}

    def load_history(self, history: list):
        """Carga historial desde formato JSON (dicts compatibles con la API de Anthropic)."""
        self._history = history

    def clear_history(self):
        """Borra el historial de la conversación (para el comando /limpiar)."""
        self._history.clear()

    async def _call_tool(self, tool_name: str, tool_input: dict) -> str:
        """Llama a la herramienta en el servidor MCP que la provee."""
        # Buscar a qué servidor pertenece la herramienta
        server_name = next(
            (t["_server"] for t in self._tools if t["name"] == tool_name),
            None,
        )
        if server_name is None:
            return f"Error: herramienta '{tool_name}' no encontrada."

        session = self._sessions[server_name]
        result = await session.call_tool(tool_name, tool_input)

        # Convertir el resultado a string para incluirlo en el historial
        if result.content:
            parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return "(sin resultado)"

    async def cleanup(self):
        """Cierra todas las sesiones MCP y libera recursos."""
        await self._exit_stack.aclose()


def _serialize_block(block) -> dict:
    """
    Serializa un bloque de contenido a dict compatible con la API.
    Evita campos internos del SDK (ej: parsed_output) que la API rechaza.
    """
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    # Fallback para otros tipos (thinking, etc.)
    return {"type": block.type}


def _extract_text(content) -> str:
    """Extrae el texto de la lista de bloques de contenido de Anthropic."""
    parts = [block.text for block in content if hasattr(block, "text")]
    return "\n".join(parts)


# ── Prueba rápida desde consola ──────────────────────────────────────────────
if __name__ == "__main__":
    prompt = "Listá todas las tablas disponibles en la base de datos."
    print(f"Consulta: {prompt}\n")

    async def main():
        agent = MCPAgent()
        try:
            print("Conectando a MCP...")
            await agent.connect()
            print("Conectado. Ejecutando consulta...\n")
            response = await agent.run_query(prompt)
            print(f"Respuesta:\n{response}")
        finally:
            await agent.cleanup()

    asyncio.run(main())
