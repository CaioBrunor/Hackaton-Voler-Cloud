@echo off
rem Inicia o backend Spring Boot (pasta backend) em http://localhost:8080.
rem Precisa do Java 25 e do MySQL rodando (banco centro_comando_defesa, criado sozinho se nao existir).
rem A senha do usuario root do MySQL e pedida ao abrir (deixe vazio se o root nao tiver senha).
rem Ela fica so nesta janela e nao e gravada em nenhum arquivo.

cd /d "%~dp0backend"

if not defined SPRING_DATASOURCE_PASSWORD (
    set /p SPRING_DATASOURCE_PASSWORD=Senha do usuario root do MySQL ^(Enter se nao tiver^):
)

call mvnw.cmd spring-boot:run
echo.
echo O backend foi encerrado. Se apareceu "Access denied", a senha do MySQL esta incorreta.
pause
