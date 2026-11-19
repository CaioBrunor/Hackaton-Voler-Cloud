"""Como o servidor se comporta ao ser aberto do jeito errado ou pelo navegador."""

import os
import subprocess
import sys
from pathlib import Path

from starlette.testclient import TestClient

from main import criar_servidor

RAIZ = Path(__file__).resolve().parent.parent


def test_python_sem_as_dependencias_mostra_como_iniciar():
    # "-S" desliga o site-packages: simula rodar main.py com o Python do sistema.
    processo = subprocess.run(
        [sys.executable, "-S", "main.py"],
        cwd=RAIZ,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=30,
    )
    assert processo.returncode == 1
    assert "Traceback" not in processo.stderr
    assert "iniciar.bat" in processo.stderr
    assert ".venv\\Scripts\\python.exe main.py" in processo.stderr


def test_pagina_de_status_no_navegador(backend):
    resposta = TestClient(criar_servidor().streamable_http_app()).get("/")
    assert resposta.status_code == 200
    status = resposta.json()
    assert status["status"] == "rodando"
    assert status["enderecoMcp"] == "http://testserver/mcp"
    assert status["tools"] == 13
    assert status["backend"]["acessivel"] is True


def test_pagina_de_status_avisa_backend_fora_do_ar(backend_desligado):
    status = TestClient(criar_servidor().streamable_http_app()).get("/").json()
    assert status["status"] == "rodando"
    assert status["backend"]["acessivel"] is False
    assert status["backend"]["detalhe"] == "Não foi possível consultar o backend. Serviço temporariamente indisponível."
