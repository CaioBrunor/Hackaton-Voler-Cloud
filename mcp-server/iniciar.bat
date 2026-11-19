@echo off
rem Inicia o MCP Server com o Python do ambiente virtual (.venv) do projeto.
rem Na primeira vez, cria o .venv e instala as dependencias automaticamente.
rem Pode ser aberto com dois cliques ou pelo terminal (iniciar.bat).

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Criando o ambiente virtual .venv ...
    python -m venv .venv
    if errorlevel 1 goto erro
)

".venv\Scripts\python.exe" -c "import mcp, httpx, dotenv" 2>nul
if errorlevel 1 (
    echo Instalando as dependencias ^(requirements.txt^) ...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto erro
)

".venv\Scripts\python.exe" main.py
echo.
echo O MCP Server foi encerrado.
pause
exit /b 0

:erro
echo.
echo Nao foi possivel preparar o ambiente. Confira se o Python 3.10+ esta instalado.
pause
exit /b 1
