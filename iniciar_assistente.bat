@echo off
rem Inicia o Assistente de IA (Claude) em http://127.0.0.1:8100.
rem Na primeira vez cria o ambiente e abre o .env no Bloco de Notas para voce colar a chave da API.

cd /d "%~dp0assistente"

if not exist ".venv\Scripts\python.exe" (
    echo Criando o ambiente virtual do assistente ...
    python -m venv .venv
    if errorlevel 1 goto erro
)
".venv\Scripts\python.exe" -c "import anthropic, mcp, dotenv" 2>nul
if errorlevel 1 (
    echo Instalando as dependencias ...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto erro
)
if not exist ".env" (
    copy .env.example .env >nul
    echo Cole a sua chave em ANTHROPIC_API_KEY=, salve e feche o Bloco de Notas.
    notepad .env
)

".venv\Scripts\python.exe" main.py
echo.
echo O assistente foi encerrado.
pause
exit /b 0

:erro
echo Nao foi possivel preparar o ambiente. Confira se o Python 3.10+ esta instalado.
pause
exit /b 1
