import sys
import os
import asyncio

# Agrega src/ al path para que los imports funcionen desde la raíz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    asyncio.run(main())
