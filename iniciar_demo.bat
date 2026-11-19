@echo off
rem Demonstracao SEM o Spring Boot, cada parte em uma janela:
rem   1. backend simulado (porta 8080) - imita o backend da pasta backend
rem   2. MCP Server        (porta 8000)
rem   3. assistente de IA  (porta 8100) - Claude, precisa da chave no assistente\.env
rem   4. frontend TechZone (porta 5500) - abre o navegador

cd /d "%~dp0"

start "Backend simulado (8080)" cmd /c mcp-server\simulador\iniciar_simulador.bat
start "MCP Server (8000)" cmd /c mcp-server\iniciar.bat
start "Assistente IA (8100)" cmd /c iniciar_assistente.bat
start "Frontend TechZone (5500)" cmd /c iniciar_front.bat
