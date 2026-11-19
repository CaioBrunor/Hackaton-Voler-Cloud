@echo off
rem Serve o frontend TechZone em http://127.0.0.1:5500 e abre o navegador.
rem O front precisa ser aberto por HTTP (nao como arquivo) para conseguir falar com o MCP.

cd /d "%~dp0"

set PYTHON=python
if exist "mcp-server\.venv\Scripts\python.exe" set PYTHON=mcp-server\.venv\Scripts\python.exe

start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5500/"
echo Frontend em http://127.0.0.1:5500  (Ctrl+C para encerrar)
%PYTHON% -m http.server 5500 --bind 127.0.0.1 --directory frontend
echo.
echo O servidor do frontend foi encerrado.
pause
