@echo off
cd /d "%~dp0.."

echo Actualizando el agente...
echo.

echo [1/2] Descargando últimos cambios...
git pull
if %errorLevel% neq 0 (
    echo ERROR: No se pudo actualizar el código. Verificá la conexión y el repositorio.
    pause
    exit /b 1
)

echo.
echo [2/2] Reconstruyendo y reiniciando el contenedor...
docker compose up -d --build

if %errorLevel% neq 0 (
    echo ERROR: No se pudo reiniciar el agente.
    pause
    exit /b 1
)

echo.
echo Agente actualizado y corriendo.
pause
