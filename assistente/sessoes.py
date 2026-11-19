"""Memória das conversas e limite de uso.

O assistente guarda a conversa inteira no servidor (e não no navegador), sempre só
acrescentando mensagens ao final, nunca editando as anteriores. Assim cada pergunta
reaproveita o que já foi processado (cache de prompt) e os blocos de raciocínio do modelo
continuam válidos. O navegador só guarda o id da conversa.
"""

import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import config


@dataclass
class Sessao:
    id: str
    mensagens: list[Any] = field(default_factory=list)
    turnos: int = 0
    perfil: str = "defesa_civil"
    ultimo_uso: float = field(default_factory=time.monotonic)


class Sessoes:
    """Conversas em memória: expiram por inatividade e o total é limitado."""

    def __init__(self) -> None:
        self._por_id: dict[str, Sessao] = {}

    def _limpar(self) -> None:
        agora = time.monotonic()
        for id_ in [i for i, s in self._por_id.items() if agora - s.ultimo_uso > config.SESSAO_TTL]:
            del self._por_id[id_]
        # Se ainda passar do limite, esquece as mais antigas.
        while len(self._por_id) >= config.LIMITE_SESSOES:
            mais_antiga = min(self._por_id.values(), key=lambda s: s.ultimo_uso)
            del self._por_id[mais_antiga.id]

    def obter_ou_criar(self, id_: str | None, perfil: str = "defesa_civil") -> Sessao:
        sessao = self._por_id.get(id_) if id_ else None
        # Trocar de perfil começa uma conversa nova: as instruções do assistente são outras.
        if sessao is not None and sessao.perfil != perfil:
            sessao = None
        if sessao is None:
            self._limpar()  # só ao criar uma conversa nova
            sessao = Sessao(id=secrets.token_urlsafe(16), perfil=perfil)
            self._por_id[sessao.id] = sessao
        sessao.ultimo_uso = time.monotonic()
        return sessao

    def __len__(self) -> int:
        return len(self._por_id)


class LimiteDeUso:
    """Máximo de perguntas por minuto de cada origem (janela deslizante)."""

    def __init__(self) -> None:
        self._registros: dict[str, deque[float]] = {}

    def permitir(self, origem: str) -> bool:
        agora = time.monotonic()
        fila = self._registros.setdefault(origem, deque())
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= config.LIMITE_POR_MINUTO:
            return False
        fila.append(agora)
        return True
