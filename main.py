import sys
import os
import asyncio

# Agrega src/ al path para que los imports funcionen desde la raíz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    if "--web" in sys.argv:
        print("access on http://localhost:8000")  
        import uvicorn
        uvicorn.run(
            "web:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
        )
          
    else:
        from cli import main
        asyncio.run(main())
