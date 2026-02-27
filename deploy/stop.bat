@echo off
cd /d "%~dp0.."

echo Deteniendo el agente...
docker compose down

echo Agente detenido.
pause
