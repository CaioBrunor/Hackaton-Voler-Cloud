@echo off
rem Projeto completo com o backend REAL, cada parte em uma janela (o backend pede a senha do MySQL):
rem   1. backend Spring Boot (porta 8080) - precisa do MySQL rodando
rem   2. MCP Server          (porta 8000)
rem   3. frontend TechZone   (porta 5500) - abre o navegador
rem O backend demora alguns segundos para subir; se o front mostrar "MCP: Offline", clique em Conectar Live.

cd /d "%~dp0"

start "Backend Spring Boot (8080)" cmd /c iniciar_backend.bat
start "MCP Server (8000)" cmd /c mcp-server\iniciar.bat
start "Frontend TechZone (5500)" cmd /c iniciar_front.bat
