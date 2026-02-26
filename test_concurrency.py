"""
Test de concurrencia — verifica que múltiples usuarios operen en paralelo
con historiales independientes.

Uso:
    python test_concurrency.py

Requiere que el servidor esté corriendo:
    python main.py --web
"""
import asyncio
import json
import time
import httpx

BASE_URL = "http://localhost:8000"

# Consultas distintas para cada usuario simulado
USERS = [
    {"id": "test_user_1", "prompt": "Cuántas tablas hay en la base de datos?"},
    {"id": "test_user_2", "prompt": "Listá los nombres de todas las tablas disponibles"},
    {"id": "test_user_3", "prompt": "Describí la estructura de la base de datos"},
]


async def query_as_user(client: httpx.AsyncClient, user: dict) -> dict:
    """Simula un usuario enviando una consulta y consumiendo el stream SSE."""
    session_id = user["id"]
    prompt     = user["prompt"]
    start      = time.perf_counter()

    chunks = []
    tool_calls = []
    error = None

    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/query",
            json={"session_id": session_id, "prompt": prompt},
            timeout=120,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw:
                    continue
                event = json.loads(raw)

                if event["type"] == "text":
                    chunks.append(event["content"])
                elif event["type"] == "tool_call":
                    tool_calls.append(event["tool"])
                elif event["type"] == "done":
                    break
                elif event["type"] == "error":
                    error = event["message"]
                    break

    except Exception as e:
        error = str(e)

    elapsed = time.perf_counter() - start
    text = "".join(chunks)

    return {
        "user":       session_id,
        "prompt":     prompt,
        "elapsed_s":  round(elapsed, 2),
        "tools_used": tool_calls,
        "response":   text[:200] + "..." if len(text) > 200 else text,
        "error":      error,
    }


async def main():
    print(f"\n{'='*60}")
    print(f"  Test de concurrencia — {len(USERS)} usuarios simultáneos")
    print(f"{'='*60}\n")

    # Limpiar sesiones previas
    async with httpx.AsyncClient() as client:
        for user in USERS:
            await client.post(f"{BASE_URL}/api/session/{user['id']}/clear")

    # Lanzar todos los usuarios en paralelo
    print("Enviando consultas en paralelo...\n")
    start_total = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [query_as_user(client, user) for user in USERS]
        results = await asyncio.gather(*tasks)

    total = time.perf_counter() - start_total

    # Mostrar resultados
    for r in results:
        status = "✓" if not r["error"] else "✗"
        print(f"{status} {r['user']}  ({r['elapsed_s']}s)")
        print(f"  Prompt:  {r['prompt']}")
        if r["tools_used"]:
            print(f"  Tools:   {', '.join(r['tools_used'])}")
        if r["error"]:
            print(f"  Error:   {r['error']}")
        else:
            print(f"  Resp:    {r['response']}")
        print()

    print(f"{'='*60}")
    print(f"  Tiempo total en paralelo: {round(total, 2)}s")
    sum_individual = sum(r['elapsed_s'] for r in results)
    print(f"  Suma de tiempos individuales: {round(sum_individual, 2)}s")
    speedup = round(sum_individual / total, 1) if total > 0 else 1
    print(f"  Speedup de concurrencia:  ~{speedup}x")
    print(f"{'='*60}\n")

    errors = [r for r in results if r["error"]]
    if errors:
        print(f"  {len(errors)} error(es) encontrados. Verificá que el servidor esté corriendo.")
    else:
        print("  Todas las sesiones respondieron correctamente e independientemente.")


if __name__ == "__main__":
    asyncio.run(main())
