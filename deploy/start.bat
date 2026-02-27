@echo off
cd /d "%~dp0.."

echo Construyendo e iniciando el agente...
docker compose up -d --build

if %errorLevel% neq 0 (
    echo.
    echo ERROR: No se pudo iniciar el agente. Verificá que Docker Desktop esté corriendo.
    pause
    exit /b 1
)

echo.
echo Agente iniciado correctamente.
echo.
echo URL para los empleados:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo   http://!IP!:8000
    goto :done
)
:done
echo.
echo Para ver los logs: deploy\logs.bat
echo Para detener:      deploy\stop.bat
echo.
pause
