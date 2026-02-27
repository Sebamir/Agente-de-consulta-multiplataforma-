@echo off
cd /d "%~dp0.."

echo Mostrando logs del agente (Ctrl+C para salir)...
echo.
docker compose logs -f
