@echo off
rem Inicia o backend simulado, que substitui o Spring Boot so para demonstracao.
rem Desligue-o quando o backend real estiver rodando na porta 8080.

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Rode primeiro o iniciar.bat da pasta do projeto para criar o ambiente .venv.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" simulador\backend_simulado.py
echo.
echo O backend simulado foi encerrado.
pause
