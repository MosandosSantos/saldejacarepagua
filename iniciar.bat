@echo off
title CRMCronos.Cloud — Servidor Web (porta 8009)
cd /d "%~dp0"

echo ============================================================
echo   CRMCronos.Cloud — servidor web
echo   Acesse:  http://localhost:8009
echo   Para parar: feche esta janela (ou Ctrl+C)
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    echo Para criar:  py -m venv .venv
    echo Para instalar as dependencias:  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

rem Abre o navegador depois que o servidor estiver de pe
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8009"

.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8009

pause
