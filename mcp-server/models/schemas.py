"""Formatos de entrada e saída do MCP.

Este módulo é a fronteira entre o JSON do backend Spring Boot e o que a IA recebe:

1. Valores aceitos nos parâmetros das tools (status, níveis, períodos). Eles viram
   o JSON Schema que a IA lê para saber como chamar cada ferramenta.
2. Modelos das entidades (sensor, canal, barragem...). Aceitam pequenas variações
   de nome vindas do backend (ex.: "entrada" ou "vazaoEntrada") e entregam sempre
   o mesmo formato para a IA. Se o backend renomear um campo, o ajuste é só aqui.
3. Formatos das análises (fluxo, tendência, risco).
4. Formatos das respostas (listas e erros).
"""

import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    model_validator,
)

# =============================================================================
# 1. Valores aceitos
# =============================================================================

StatusMonitoramento = Literal["NORMAL", "ATENCAO", "ALERTA", "CRITICO"]
NivelRisco = Literal["BAIXO", "MEDIO", "ALTO", "CRITICO"]
PeriodoHistorico = Literal["1h", "6h", "12h", "24h", "48h", "7d"]
NivelConfianca = Literal["BAIXO", "MEDIO", "ALTO"]
Tendencia = Literal["AUMENTO", "REDUCAO", "ESTABILIDADE", "DADOS_INSUFICIENTES"]
SituacaoFluxo = Literal["ACUMULO_POTENCIAL", "ESCOAMENTO", "EQUILIBRIO", "DADOS_INSUFICIENTES"]

UNIDADE_VAZAO = "m³/h"

# Escala única de gravidade (0 a 3), usada para ordenar resultados e nas regras de
# análise. Cada entidade do backend usa palavras diferentes (status do sensor,
# intensidade da chuva, severidade do alerta...), mas todas cabem nesta escala.
GRAVIDADE: dict[str, int] = {
    # 0 = normal
    "NORMAL": 0, "BAIXO": 0, "BAIXA": 0, "FRACA": 0, "FRACO": 0, "SEM_CHUVA": 0, "INFORMATIVO": 0, "LIVRE": 0,
    # 1 = atenção
    "ATENCAO": 1, "MEDIO": 1, "MEDIA": 1, "MODERADA": 1, "MODERADO": 1, "PARCIALMENTE_OBSTRUIDO": 1,
    # 2 = alerta
    "ALERTA": 2, "ALTO": 2, "ALTA": 2, "FORTE": 2, "OBSTRUIDO": 2, "ENTUPIDO": 2,
    # 3 = crítico
    "CRITICO": 3, "CRITICA": 3, "MUITO_FORTE": 3, "EXTREMA": 3, "EXTREMO": 3, "EMERGENCIA": 3,
}  # fmt: skip

# Palavras ignoradas ao comparar nomes de região ("Região Norte" encontra "Norte").
_PREFIXOS_DE_LOCAL = ("REGIAO_", "ZONA_", "BAIRRO_")


def normalizar(texto: Any) -> str:
    """Padroniza códigos: 'Atenção' -> 'ATENCAO', 'parcialmente obstruído' -> 'PARCIALMENTE_OBSTRUIDO'."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return "_".join(sem_acento.upper().replace("-", " ").split())


def gravidade(valor: str | None) -> int | None:
    """Posição de um status/nível na escala 0–3, ou None se o valor for desconhecido."""
    return None if valor is None else GRAVIDADE.get(normalizar(valor))


# Status que indicam alerta ou ocorrência finalizada. Qualquer outro (inclusive vazio) conta como ativo.
STATUS_ENCERRADOS = {
    "ENCERRADO", "ENCERRADA", "RESOLVIDO", "RESOLVIDA", "FINALIZADO", "FINALIZADA", "CONCLUIDO", "CONCLUIDA",
    "FECHADO", "FECHADA", "CANCELADO", "CANCELADA", "INATIVO", "INATIVA", "ARQUIVADO", "ARQUIVADA",
}  # fmt: skip


def esta_ativo(status: str | None) -> bool:
    """Alerta ativo / ocorrência aberta: tudo que não estiver em STATUS_ENCERRADOS."""
    return status is None or normalizar(status) not in STATUS_ENCERRADOS


def contem(texto: str | None, busca: str) -> bool:
    """Compara sem diferenciar maiúsculas e acentos: contem('Canal Norte', 'região norte') -> True."""
    if texto is None:
        return False
    termo = normalizar(busca)
    for prefixo in _PREFIXOS_DE_LOCAL:
        termo = termo.removeprefix(prefixo)
    return termo in normalizar(texto)


# =============================================================================
# 2. Entidades vindas do backend
# =============================================================================


def _codigo_ou_none(valor: Any) -> str | None:
    return None if valor is None or str(valor).strip() == "" else normalizar(valor)


def _texto_ou_none(valor: Any) -> str | None:
    return None if valor is None else str(valor)


# Códigos (status, níveis) chegam padronizados: "Crítico" vira "CRITICO".
Codigo = Annotated[str | None, BeforeValidator(_codigo_ou_none)]
Texto = Annotated[str | None, BeforeValidator(_texto_ou_none)]
Id = int | str | None


def _aceita(*nomes: str) -> Any:
    """Campo opcional que aceita qualquer um dos nomes informados no JSON do backend."""
    return Field(default=None, validation_alias=AliasChoices(*nomes))


def _saldo(entrada: float | None, saida: float | None) -> float | None:
    if entrada is None or saida is None:
        return None
    return round(entrada - saida, 2)


def _percentual(parte: float | None, total: float | None) -> float | None:
    if parte is None or not total:
        return None
    return round(parte / total * 100, 1)


class _Entidade(BaseModel):
    # Campos que o MCP não conhece são ignorados: a IA recebe sempre o mesmo formato.
    model_config = ConfigDict(extra="ignore")


class ResumoCidade(_Entidade):
    situacaoGeral: Codigo = _aceita("situacaoGeral", "situacao", "status")
    sensoresAtivos: int | None = None
    sensoresEmAlerta: int | None = None
    canaisEmAlerta: int | None = None
    barragensEmAlerta: int | None = None
    alertasAtivos: int | None = None
    ocorrenciasAbertas: int | None = None
    ultimaAtualizacao: Texto = _aceita("ultimaAtualizacao", "dataHora", "atualizadoEm")


class PrevisaoChuva(_Entidade):
    regiao: Texto = _aceita("regiao", "bairro", "local")
    chuvaPrevista: float | None = _aceita(
        "chuvaPrevista", "quantidadeChuva", "chuvaPrevistaMm", "precipitacao", "milimetros"
    )
    periodo: Texto = None
    dataHora: Texto = _aceita("dataHora", "horario", "data")
    intensidade: Codigo = None
    probabilidade: float | None = _aceita("probabilidade", "probabilidadeChuva")


class Sensor(_Entidade):
    id: Id = None
    codigo: Texto = _aceita("codigo", "identificador", "nome")
    localizacao: Texto = _aceita("localizacao", "local", "endereco")
    regiao: Texto = _aceita("regiao", "bairro", "zona")
    nivel: float | None = _aceita("nivel", "nivelAgua", "nivelAtual")
    capacidade: float | None = _aceita("capacidade", "capacidadeMaxima", "nivelMaximo")
    percentual: float | None = _aceita("percentual", "percentualOcupacao", "percentualCapacidade")
    vazaoEntrada: float | None = _aceita("vazaoEntrada", "entradaAgua", "entrada")
    vazaoSaida: float | None = _aceita("vazaoSaida", "saidaAgua", "saida")
    status: Codigo = _aceita("status", "situacao")
    ultimaAtualizacao: Texto = _aceita("ultimaAtualizacao", "dataHora", "atualizadoEm", "ultimaLeitura")

    @computed_field
    @property
    def saldoVazao(self) -> float | None:
        """Entrada menos saída: positivo significa que entra mais água do que sai."""
        return _saldo(self.vazaoEntrada, self.vazaoSaida)

    @model_validator(mode="after")
    def _completar_percentual(self) -> "Sensor":
        if self.percentual is None:
            self.percentual = _percentual(self.nivel, self.capacidade)
        return self


class LeituraSensor(_Entidade):
    dataHora: Texto = _aceita("dataHora", "horario", "timestamp", "data")
    nivel: float | None = None
    percentual: float | None = None


class Canal(_Entidade):
    id: Id = None
    nome: Texto = _aceita("nome", "codigo", "identificador")
    localizacao: Texto = _aceita("localizacao", "local", "endereco")
    regiao: Texto = _aceita("regiao", "bairro", "zona")
    nivel: float | None = _aceita("nivel", "nivelAgua", "nivelAtual")
    capacidade: float | None = _aceita("capacidade", "capacidadeMaxima", "nivelMaximo")
    percentual: float | None = _aceita("percentual", "percentualOcupacao", "percentualCapacidade")
    vazaoEntrada: float | None = _aceita("vazaoEntrada", "entradaAgua", "entrada")
    vazaoSaida: float | None = _aceita("vazaoSaida", "saidaAgua", "saida")
    status: Codigo = _aceita("status", "situacao")
    ultimaAtualizacao: Texto = _aceita("ultimaAtualizacao", "dataHora", "atualizadoEm")

    @computed_field
    @property
    def saldoVazao(self) -> float | None:
        """Entrada menos saída: positivo significa que entra mais água do que sai."""
        return _saldo(self.vazaoEntrada, self.vazaoSaida)

    @model_validator(mode="after")
    def _completar_percentual(self) -> "Canal":
        if self.percentual is None:
            self.percentual = _percentual(self.nivel, self.capacidade)
        return self


class Bueiro(_Entidade):
    id: Id = None
    codigo: Texto = _aceita("codigo", "identificador")
    localizacao: Texto = _aceita("localizacao", "local", "endereco")
    regiao: Texto = _aceita("regiao", "bairro", "zona")
    status: Codigo = _aceita("status", "situacao", "estado")
    nivelObstrucao: float | None = None
    ultimaAtualizacao: Texto = _aceita("ultimaAtualizacao", "ultimaManutencao", "ultimaInspecao", "dataHora")


class Barragem(_Entidade):
    id: Id = None
    nome: Texto = None
    localizacao: Texto = _aceita("localizacao", "local", "endereco")
    regiao: Texto = _aceita("regiao", "bairro", "zona")
    capacidade: float | None = _aceita("capacidade", "capacidadeMaxima")
    volumeAtual: float | None = _aceita("volumeAtual", "volume")
    percentual: float | None = _aceita("percentual", "percentualVolume", "percentualOcupacao")
    vazaoEntrada: float | None = _aceita("vazaoEntrada", "entrada")
    vazaoSaida: float | None = _aceita("vazaoSaida", "saida")
    nivel: float | None = _aceita("nivel", "nivelAgua", "nivelAtual")
    nivelRisco: Codigo = None
    status: Codigo = _aceita("status", "situacao")
    ultimaAtualizacao: Texto = _aceita("ultimaAtualizacao", "dataHora", "atualizadoEm")

    @computed_field
    @property
    def saldoVazao(self) -> float | None:
        """Entrada menos saída: positivo significa que entra mais água do que sai."""
        return _saldo(self.vazaoEntrada, self.vazaoSaida)

    @model_validator(mode="after")
    def _completar_percentual(self) -> "Barragem":
        if self.percentual is None:
            self.percentual = _percentual(self.volumeAtual, self.capacidade)
        return self


class AreaRisco(_Entidade):
    id: Id = None
    regiao: Texto = _aceita("regiao", "nome", "bairro")
    localizacao: Texto = _aceita("localizacao", "local", "endereco")
    populacaoEstimada: int | None = _aceita("populacaoEstimada", "populacao")
    nivelRisco: Codigo = _aceita("nivelRisco", "nivel", "risco", "classificacao")
    tipoRisco: Texto = None
    descricao: Texto = None
    situacaoAtual: Texto = _aceita("situacaoAtual", "situacao", "status")


class Alerta(_Entidade):
    id: Id = None
    tipo: Texto = None
    titulo: Texto = None
    mensagem: Texto = _aceita("mensagem", "descricao")
    severidade: Codigo = _aceita("severidade", "nivel", "gravidade")
    regiao: Texto = _aceita("regiao", "localizacao", "local")
    dataHora: Texto = _aceita("dataHora", "horario", "dataCriacao", "criadoEm")
    situacao: Codigo = _aceita("situacao", "status")


class Ocorrencia(_Entidade):
    id: Id = None
    tipo: Texto = None
    descricao: Texto = None
    localizacao: Texto = _aceita("localizacao", "endereco", "local")
    regiao: Texto = _aceita("regiao", "bairro")
    prioridade: Codigo = _aceita("prioridade", "nivel", "gravidade")
    dataHora: Texto = _aceita("dataHora", "horario", "dataAbertura", "criadoEm")
    status: Codigo = _aceita("status", "situacao")


@dataclass
class DadosCidade:
    """Dados já consultados e normalizados que alimentam a análise de risco."""

    previsoes: list[PrevisaoChuva] = field(default_factory=list)
    sensores: list[Sensor] = field(default_factory=list)
    canais: list[Canal] = field(default_factory=list)
    bueiros: list[Bueiro] = field(default_factory=list)
    barragens: list[Barragem] = field(default_factory=list)
    areas_risco: list[AreaRisco] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    fontes_consultadas: list[str] = field(default_factory=list)
    fontes_indisponiveis: list[str] = field(default_factory=list)


# =============================================================================
# 3. Resultados das análises
# =============================================================================


class AnaliseFluxo(BaseModel):
    vazaoEntrada: float | None
    vazaoSaida: float | None
    saldo: float | None
    unidade: str = UNIDADE_VAZAO
    resumo: str
    situacaoFluxo: SituacaoFluxo
    interpretacao: str
    observacao: str


class AnaliseTendencia(BaseModel):
    tendencia: Tendencia
    descricao: str
    leiturasAnalisadas: int
    primeiraLeitura: float | None = None
    ultimaLeitura: float | None = None
    variacao: float | None = None
    observacao: str = "Descreve o comportamento das leituras passadas; não é uma previsão."


class AnaliseRisco(BaseModel):
    situacao: StatusMonitoramento
    nivelConfianca: NivelConfianca
    principaisFatores: list[str]
    areasMaisAfetadas: list[str]
    recomendacao: str
    regiaoAnalisada: str | None
    pontuacao: int
    criterios: dict[str, int]
    escala: str
    fontesConsultadas: list[str]
    fontesIndisponiveis: list[str]
    observacao: str


# =============================================================================
# 4. Respostas
# =============================================================================


class ErroConsulta(Exception):
    """Falha ao obter os dados. Vira {"erro": ..., "detalhe": ...} na resposta da tool."""

    def __init__(self, erro: str, detalhe: str) -> None:
        super().__init__(f"{erro} {detalhe}")
        self.erro = erro
        self.detalhe = detalhe


def resposta_erro(erro: str, detalhe: str) -> dict[str, str]:
    return {"erro": erro, "detalhe": detalhe}


M = TypeVar("M", bound=BaseModel)


def validar(modelo: type[M], dados: Any) -> M:
    """Converte o JSON do backend no modelo do MCP, ou falha com uma mensagem compreensível."""
    try:
        return modelo.model_validate(dados)
    except ValidationError as exc:
        local = ".".join(str(parte) for parte in exc.errors()[0]["loc"]) or "registro"
        raise ErroConsulta(
            "O backend retornou dados em formato inesperado.",
            f"Campo '{local}' inválido em {modelo.__name__}.",
        ) from None


def validar_lista(modelo: type[M], itens: list[Any]) -> list[M]:
    return [validar(modelo, item) for item in itens]


def resposta_lista(chave: str, itens: list[BaseModel], **resumo: Any) -> dict[str, Any]:
    """Formato padrão das listas: total, informações de resumo e os itens."""
    return {"total": len(itens), **resumo, chave: [item.model_dump() for item in itens]}


def contar_por(valores: list[str | None]) -> dict[str, int]:
    """Quantidade por valor, ex.: {"NORMAL": 20, "ALERTA": 3, "SEM_INFORMACAO": 1}."""
    return dict(Counter(valor or "SEM_INFORMACAO" for valor in valores))


def ordenar_por_percentual(itens: list[M]) -> list[M]:
    """Do mais cheio para o mais vazio; itens sem leitura ficam no fim."""
    return sorted(itens, key=lambda item: (item.percentual is None, -(item.percentual or 0)))


def ordenar_por_gravidade(itens: list[M], campo: str) -> list[M]:
    """Do mais grave para o menos grave, segundo a escala GRAVIDADE."""
    return sorted(itens, key=lambda item: -(gravidade(getattr(item, campo)) or 0))
