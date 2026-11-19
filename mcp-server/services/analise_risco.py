"""Regras de análise do MCP: fluxo de água, tendência de leituras e risco da cidade.

* Sem IA: são regras fixas e explícitas, então os mesmos dados sempre geram o
  mesmo resultado (fácil de testar e de explicar).
* Sem acesso ao backend: recebe dados já consultados e normalizados pelas tools.
* Sem decisões operacionais: descreve a situação e aponta onde olhar; quem decide
  é a equipe da Defesa Civil.

As regras usam a escala de gravidade de models.schemas:
    0 = normal · 1 = atenção · 2 = alerta · 3 = crítico
"""

import dataclasses
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from models.schemas import (
    UNIDADE_VAZAO,
    AnaliseFluxo,
    AnaliseRisco,
    AnaliseTendencia,
    DadosCidade,
    NivelConfianca,
    StatusMonitoramento,
    contar_por,
    contem,
    esta_ativo,
    gravidade,
    normalizar,
)

# =============================================================================
# Fluxo de água (entrada x saída)
# =============================================================================

OBSERVACAO_FLUXO = (
    "Indicador descritivo: sozinho, não permite afirmar que haverá enchente. "
    "Considere também o nível, a previsão de chuva e os demais dados."
)


def analisar_fluxo(entrada: float | None, saida: float | None) -> AnaliseFluxo:
    """Compara a vazão de entrada com a de saída (saldo = entrada - saída)."""
    if entrada is None or saida is None:
        return AnaliseFluxo(
            vazaoEntrada=entrada,
            vazaoSaida=saida,
            saldo=None,
            resumo="Leitura de vazão indisponível.",
            situacaoFluxo="DADOS_INSUFICIENTES",
            interpretacao="Não foi possível obter a vazão de entrada e a de saída.",
            observacao=OBSERVACAO_FLUXO,
        )

    saldo = round(entrada - saida, 2)
    if saldo > 0:
        situacao = "ACUMULO_POTENCIAL"
        interpretacao = "A entrada de água está maior que a saída: existe acúmulo potencial de água."
    elif saldo < 0:
        situacao = "ESCOAMENTO"
        interpretacao = "A saída de água está maior que a entrada: sai mais água do que entra."
    else:
        situacao = "EQUILIBRIO"
        interpretacao = "A entrada e a saída de água estão equilibradas."

    sinal = "+" if saldo > 0 else ""
    return AnaliseFluxo(
        vazaoEntrada=entrada,
        vazaoSaida=saida,
        saldo=saldo,
        resumo=(
            f"Entrada: {_num(entrada)} {UNIDADE_VAZAO} | Saída: {_num(saida)} {UNIDADE_VAZAO} | "
            f"Saldo: {sinal}{_num(saldo)} {UNIDADE_VAZAO}"
        ),
        situacaoFluxo=situacao,
        interpretacao=interpretacao,
        observacao=OBSERVACAO_FLUXO,
    )


# =============================================================================
# Tendência de uma série de leituras
# =============================================================================

MINIMO_DE_LEITURAS = 3
# Variação estimada menor que 3% da média das leituras é tratada como estabilidade.
LIMIAR_ESTABILIDADE = 0.03


def analisar_tendencia(valores: list[float | None], grandeza: str = "nível do sensor") -> AnaliseTendencia:
    """Classifica uma série (da mais antiga para a mais recente) em aumento, redução ou estabilidade.

    Usa a inclinação da reta de mínimos quadrados, que sofre menos com uma leitura
    isolada fora do padrão do que comparar só a primeira com a última.
    """
    leituras = [float(valor) for valor in valores if valor is not None]
    if len(leituras) < MINIMO_DE_LEITURAS:
        return AnaliseTendencia(
            tendencia="DADOS_INSUFICIENTES",
            descricao=(
                "Dados insuficientes para avaliar a tendência "
                f"(são necessárias ao menos {MINIMO_DE_LEITURAS} leituras)."
            ),
            leiturasAnalisadas=len(leituras),
        )

    variacao_estimada = _inclinacao(leituras) * (len(leituras) - 1)
    limiar = LIMIAR_ESTABILIDADE * fmean(abs(valor) for valor in leituras)
    if abs(variacao_estimada) <= limiar:
        tendencia, texto = "ESTABILIDADE", "estabilidade"
    elif variacao_estimada > 0:
        tendencia, texto = "AUMENTO", "tendência de aumento"
    else:
        tendencia, texto = "REDUCAO", "tendência de redução"

    return AnaliseTendencia(
        tendencia=tendencia,
        descricao=f"O {grandeza} apresentou {texto} nas últimas leituras.",
        leiturasAnalisadas=len(leituras),
        primeiraLeitura=leituras[0],
        ultimaLeitura=leituras[-1],
        variacao=round(leituras[-1] - leituras[0], 2),
    )


def _inclinacao(valores: list[float]) -> float:
    """Quanto o valor muda, em média, de uma leitura para a seguinte."""
    media_x = (len(valores) - 1) / 2
    media_y = fmean(valores)
    numerador = sum((x - media_x) * (y - media_y) for x, y in enumerate(valores))
    denominador = sum((x - media_x) ** 2 for x in range(len(valores)))
    return numerador / denominador


# =============================================================================
# Resumo da cidade (quando o backend não tem a rota /api/dashboard/resumo)
# =============================================================================

_SITUACAO_POR_GRAVIDADE: dict[int, StatusMonitoramento] = {0: "NORMAL", 1: "ATENCAO", 2: "ALERTA", 3: "CRITICO"}


def resumir_cidade(
    sensores: list[Any], canais: list[Any], barragens: list[Any], alertas: list[Any], ocorrencias: list[Any]
) -> dict[str, Any]:
    """Monta o resumo a partir das listas do backend. A situação geral é a do item mais grave."""
    def em_alerta(itens: list[Any]) -> int:
        return sum(1 for item in itens if _gravidade_medidor(item) >= 2)

    medidores = [*sensores, *canais, *barragens]
    pior = max((_gravidade_medidor(item) for item in medidores), default=0)
    return {
        "situacaoGeral": _SITUACAO_POR_GRAVIDADE[pior],
        "sensoresAtivos": sum(1 for s in sensores if s.percentual is not None or s.nivel is not None),
        "sensoresEmAlerta": em_alerta(sensores),
        "canaisEmAlerta": em_alerta(canais),
        "barragensEmAlerta": em_alerta(barragens),
        "alertasAtivos": sum(1 for a in alertas if esta_ativo(a.situacao)),
        "ocorrenciasAbertas": sum(1 for o in ocorrencias if esta_ativo(o.status)),
        "ultimaAtualizacao": None,
        "fonte": "Calculado pelo MCP a partir das listas do backend (o backend não tem /api/dashboard/resumo).",
    }


# =============================================================================
# Risco da cidade (combina todas as fontes)
# =============================================================================

# Ocupação (% da capacidade) -> gravidade, para sensores, canais e barragens.
LIMITES_DE_OCUPACAO = ((90, 3), (80, 2), (70, 1))
# Entrada maior que a saída só vira fator a partir desta ocupação (ou com status fora do normal).
OCUPACAO_MINIMA_PARA_FLUXO = 70

# Pontuação total -> situação.
FAIXAS_DE_SITUACAO: tuple[tuple[int, StatusMonitoramento], ...] = (
    (8, "CRITICO"),
    (4, "ALERTA"),
    (1, "ATENCAO"),
    (0, "NORMAL"),
)
ESCALA = (
    "0 = NORMAL · 1 a 3 = ATENÇÃO · 4 a 7 = ALERTA · 8 ou mais = CRÍTICO. "
    "Um indicador crítico eleva a situação para, no mínimo, ALERTA."
)

MAXIMO_DE_FATORES = 8
MAXIMO_DE_AREAS = 5

RECOMENDACOES: dict[str, str] = {
    "NORMAL": "Manter o monitoramento de rotina.",
    "ATENCAO": "Acompanhar com mais frequência os indicadores destacados e confirmar as leituras, se necessário.",
    "ALERTA": (
        "Monitorar as regiões destacadas e verificar as áreas de risco próximas "
        "aos canais, sensores e bueiros indicados."
    ),
    "CRITICO": (
        "Levar esta análise imediatamente à equipe responsável da Defesa Civil, "
        "que avaliará as medidas cabíveis."
    ),
}

OBSERVACAO_RISCO = (
    "Análise automática baseada em regras fixas, para apoiar a tomada de decisão. "
    "Não é uma previsão determinística e não substitui a avaliação dos responsáveis da Defesa Civil; "
    "não constitui ordem de evacuação nem decisão operacional."
)

_ROTULOS = {
    "ATENCAO": "ATENÇÃO",
    "CRITICO": "CRÍTICO",
    "CRITICA": "CRÍTICA",
    "MEDIO": "MÉDIO",
    "MEDIA": "MÉDIA",
    "OBSTRUIDO": "OBSTRUÍDO",
    "PARCIALMENTE_OBSTRUIDO": "PARCIALMENTE OBSTRUÍDO",
    "SEM_INFORMACAO": "SEM INFORMAÇÃO",
}


@dataclass
class _Fator:
    gravidade: int
    texto: str


def avaliar_risco(dados: DadosCidade, regiao: str | None = None) -> AnaliseRisco:
    """Combina chuva, sensores, canais, barragens, bueiros, alertas e áreas de risco.

    Cada critério recebe uma nota (o item mais grave daquele tipo). A soma das notas
    define a situação. Se `regiao` for informada, só entram os dados daquela região.
    """
    if regiao:
        dados = _filtrar_por_regiao(dados, regiao)

    fatores: list[_Fator] = []
    criterios = {
        "chuva": _avaliar_chuva(dados, fatores),
        "sensores": _avaliar_medidores("Sensor", dados.sensores, fatores),
        "canais": _avaliar_medidores("Canal", dados.canais, fatores),
        "barragens": _avaliar_medidores("Barragem", dados.barragens, fatores),
        "bueiros": _avaliar_bueiros(dados, fatores),
        "alertas": _avaliar_alertas(dados, fatores),
        "fluxo": _avaliar_fluxo(dados, fatores),
    }
    regioes = _pontuar_regioes(dados)
    criterios["vulnerabilidade"] = _avaliar_vulnerabilidade(dados, regioes, fatores)

    pontuacao = sum(criterios.values())
    situacao = _situacao(pontuacao, maior_nota=max(criterios.values()))

    observacao = OBSERVACAO_RISCO
    if dados.fontes_indisponiveis:
        observacao += f" Fontes indisponíveis nesta análise: {', '.join(dados.fontes_indisponiveis)}."

    return AnaliseRisco(
        situacao=situacao,
        nivelConfianca=_confianca(dados),
        principaisFatores=_listar_fatores(fatores),
        areasMaisAfetadas=_areas_mais_afetadas(regioes),
        recomendacao=_recomendacao(situacao, criterios, dados),
        regiaoAnalisada=regiao,
        pontuacao=pontuacao,
        criterios=criterios,
        escala=ESCALA,
        fontesConsultadas=dados.fontes_consultadas,
        fontesIndisponiveis=dados.fontes_indisponiveis,
        observacao=observacao,
    )


# ---------------------------------------------------------------- critérios


def _avaliar_chuva(dados: DadosCidade, fatores: list[_Fator]) -> int:
    nota = 0
    for previsao in dados.previsoes:
        g = gravidade(previsao.intensidade) or 0
        if g == 0:
            continue
        nota = max(nota, g)
        texto = f"Previsão de chuva {_rotulo(previsao.intensidade).lower()}"
        if previsao.regiao:
            texto += f" para {previsao.regiao}"
        detalhes = []
        if previsao.chuvaPrevista is not None:
            detalhes.append(f"{_num(previsao.chuvaPrevista)} mm")
        if previsao.periodo:
            detalhes.append(f"em {previsao.periodo}")
        if detalhes:
            texto += f" ({' '.join(detalhes)})"
        fatores.append(_Fator(g, texto))
    return nota


def _avaliar_medidores(tipo: str, itens: list[Any], fatores: list[_Fator]) -> int:
    """Sensores, canais e barragens: vale o pior entre o status e a ocupação."""
    nota = 0
    for item in itens:
        g = _gravidade_medidor(item)
        if g == 0:
            continue
        nota = max(nota, g)
        texto = _identificar(tipo, item)
        if item.percentual is not None:
            texto += f" com {_num(item.percentual)}% da capacidade"
        if item.status:
            texto += f" (status {_rotulo(item.status)})"
        fatores.append(_Fator(g, texto))
    return nota


def _avaliar_bueiros(dados: DadosCidade, fatores: list[_Fator]) -> int:
    """Bueiros contam no máximo como ALERTA: um bueiro obstruído, sozinho, não torna a situação crítica."""
    nota = 0
    por_status: dict[str, list[Any]] = {}
    for bueiro in dados.bueiros:
        if _gravidade_bueiro(bueiro) > 0:
            por_status.setdefault(bueiro.status, []).append(bueiro)

    for status, bueiros in por_status.items():
        g = _gravidade_bueiro(bueiros[0])
        nota = max(nota, g)
        locais = [b.localizacao or b.codigo or f"#{b.id}" for b in bueiros]
        lista = ", ".join(locais[:3]) + (f" e mais {len(locais) - 3}" if len(locais) > 3 else "")
        fatores.append(_Fator(g, f"{len(bueiros)} bueiro(s) com status {_rotulo(status)}: {lista}"))
    return nota


def _avaliar_alertas(dados: DadosCidade, fatores: list[_Fator]) -> int:
    if not dados.alertas:
        return 0
    nota = max(_gravidade_alerta(alerta) for alerta in dados.alertas)
    contagem = contar_por([alerta.severidade for alerta in dados.alertas])
    detalhes = ", ".join(f"{quantidade} {_rotulo(severidade)}" for severidade, quantidade in contagem.items())
    fatores.append(_Fator(nota, f"{len(dados.alertas)} alerta(s) ativo(s) ({detalhes})"))
    return nota


def _avaliar_fluxo(dados: DadosCidade, fatores: list[_Fator]) -> int:
    """+1 ponto se algum canal ou barragem já cheio recebe mais água do que escoa."""
    nota = 0
    pontos = [("Canal", canal) for canal in dados.canais] + [("Barragem", barragem) for barragem in dados.barragens]
    for tipo, item in pontos:
        saldo = item.saldoVazao
        if saldo is None or saldo <= 0:
            continue
        cheio = (item.percentual or 0) >= OCUPACAO_MINIMA_PARA_FLUXO or (gravidade(item.status) or 0) >= 1
        if not cheio:
            continue
        nota = 1
        fatores.append(
            _Fator(1, f"{_identificar(tipo, item)}: entrada de água superior à saída (+{_num(saldo)} {UNIDADE_VAZAO})")
        )
    return nota


def _avaliar_vulnerabilidade(dados: DadosCidade, regioes: dict[str, list[Any]], fatores: list[_Fator]) -> int:
    """+1 ponto se uma área de risco ALTO/CRÍTICO fica numa região com indicadores em alerta."""
    nota = 0
    for area in dados.areas_risco:
        g = gravidade(area.nivelRisco) or 0
        if g < 2 or not area.regiao:
            continue
        regiao = _encontrar_regiao(regioes, area.regiao)
        if regiao is None or regiao[1] < 2:
            continue
        regiao[1] += g  # a vulnerabilidade da área sobe a região no ranking de áreas afetadas
        nota = 1
        texto = f"Área de risco {_rotulo(area.nivelRisco)} em {area.regiao}"
        if area.populacaoEstimada:
            texto += f" (população estimada: {_milhar(area.populacaoEstimada)})"
        fatores.append(_Fator(g, texto + " com indicadores em alerta"))
    return nota


# ---------------------------------------------------------------- regiões


def _pontuar_regioes(dados: DadosCidade) -> dict[str, list[Any]]:
    """Soma a gravidade dos indicadores por região: {chave: [nome para exibir, pontos]}."""
    regioes: dict[str, list[Any]] = {}
    # Regiões que o sistema já conhece (áreas de risco e previsão de chuva): um endereço como
    # "Av. Beira Rio, 180 - Norte" é reconhecido como a região "Norte" em vez de virar uma região nova.
    conhecidas = [nome for nome in (*(a.regiao for a in dados.areas_risco), *(p.regiao for p in dados.previsoes)) if nome]

    def regiao_de(*campos: str | None) -> str | None:
        texto = next((campo for campo in campos if campo), None)
        if not texto:
            return None
        return next((nome for nome in conhecidas if contem(texto, nome)), texto)

    def somar(nome: str | None, pontos: int) -> None:
        if not nome or pontos <= 0:
            return
        regiao = regioes.setdefault(_chave_regiao(nome), [nome, 0])
        regiao[1] += pontos

    for previsao in dados.previsoes:
        somar(previsao.regiao, gravidade(previsao.intensidade) or 0)
    for item in [*dados.sensores, *dados.canais, *dados.barragens]:
        somar(regiao_de(item.regiao, item.localizacao), _gravidade_medidor(item))
    for bueiro in dados.bueiros:
        somar(regiao_de(bueiro.regiao, bueiro.localizacao), _gravidade_bueiro(bueiro))
    for alerta in dados.alertas:
        somar(regiao_de(alerta.regiao), _gravidade_alerta(alerta))
    return regioes


def _encontrar_regiao(regioes: dict[str, list[Any]], nome: str) -> list[Any] | None:
    chave = _chave_regiao(nome)
    if chave in regioes:
        return regioes[chave]
    for outra, regiao in regioes.items():
        if chave in outra or outra in chave:
            return regiao
    return None


def _areas_mais_afetadas(regioes: dict[str, list[Any]]) -> list[str]:
    afetadas = sorted((r for r in regioes.values() if r[1] >= 2), key=lambda r: -r[1])
    return [nome for nome, _ in afetadas[:MAXIMO_DE_AREAS]]


def _chave_regiao(nome: str) -> str:
    chave = normalizar(nome)
    for prefixo in ("REGIAO_", "ZONA_", "BAIRRO_"):
        chave = chave.removeprefix(prefixo)
    return chave


def _filtrar_por_regiao(dados: DadosCidade, regiao: str) -> DadosCidade:
    def pertence(item: Any) -> bool:
        return any(contem(getattr(item, campo, None), regiao) for campo in ("regiao", "localizacao", "nome"))

    return dataclasses.replace(
        dados,
        # Previsão sem região vale para a cidade toda.
        previsoes=[p for p in dados.previsoes if p.regiao is None or contem(p.regiao, regiao)],
        sensores=[s for s in dados.sensores if pertence(s)],
        canais=[c for c in dados.canais if pertence(c)],
        bueiros=[b for b in dados.bueiros if pertence(b)],
        barragens=[b for b in dados.barragens if pertence(b)],
        areas_risco=[a for a in dados.areas_risco if contem(a.regiao, regiao)],
        alertas=[a for a in dados.alertas if pertence(a)],
    )


# ---------------------------------------------------------------- resultado


def _situacao(pontuacao: int, maior_nota: int) -> StatusMonitoramento:
    situacao: StatusMonitoramento = "NORMAL"
    for minimo, faixa in FAIXAS_DE_SITUACAO:
        if pontuacao >= minimo:
            situacao = faixa
            break
    if maior_nota >= 3 and situacao in ("NORMAL", "ATENCAO"):
        situacao = "ALERTA"
    return situacao


def _confianca(dados: DadosCidade) -> NivelConfianca:
    """Mede a completude dos dados usados, não a probabilidade de enchente."""
    indisponiveis = set(dados.fontes_indisponiveis)
    medidores = [*dados.sensores, *dados.canais, *dados.barragens]
    if len(indisponiveis) >= 3 or {"sensores", "canais"} <= indisponiveis or not medidores:
        return "BAIXO"
    sem_leitura = sum(1 for item in medidores if item.percentual is None and item.nivel is None)
    if indisponiveis or sem_leitura / len(medidores) > 0.2:
        return "MEDIO"
    return "ALTO"


def _listar_fatores(fatores: list[_Fator]) -> list[str]:
    if not fatores:
        return ["Nenhum indicador fora da normalidade nos dados consultados."]
    ordenados = sorted(fatores, key=lambda fator: -fator.gravidade)
    textos = [fator.texto for fator in ordenados[:MAXIMO_DE_FATORES]]
    if len(ordenados) > MAXIMO_DE_FATORES:
        textos.append(f"Mais {len(ordenados) - MAXIMO_DE_FATORES} fator(es) de menor gravidade.")
    return textos


def _recomendacao(situacao: str, criterios: dict[str, int], dados: DadosCidade) -> str:
    partes = [RECOMENDACOES[situacao]]
    if criterios["bueiros"] > 0:
        partes.append("Verificar a desobstrução dos bueiros indicados.")
    if criterios["fluxo"] > 0:
        partes.append("Acompanhar a vazão dos pontos em que a entrada de água supera a saída.")
    if dados.fontes_indisponiveis:
        partes.append("Confirmar os dados das fontes indisponíveis antes de concluir a avaliação.")
    return " ".join(partes)


# ---------------------------------------------------------------- auxiliares


def _gravidade_medidor(item: Any) -> int:
    return max(gravidade(item.status) or 0, _gravidade_ocupacao(item.percentual))


def _gravidade_ocupacao(percentual: float | None) -> int:
    if percentual is None:
        return 0
    for limite, g in LIMITES_DE_OCUPACAO:
        if percentual >= limite:
            return g
    return 0


def _gravidade_bueiro(bueiro: Any) -> int:
    return min(gravidade(bueiro.status) or 0, 2)


def _gravidade_alerta(alerta: Any) -> int:
    # Um alerta ativo de severidade desconhecida conta pelo menos como ATENÇÃO.
    return gravidade(alerta.severidade) or 1


def _identificar(tipo: str, item: Any) -> str:
    nome = getattr(item, "nome", None) or getattr(item, "codigo", None)
    if not nome:
        nome = f"#{item.id}" if item.id is not None else "sem identificação"
    texto = nome if normalizar(nome).startswith(normalizar(tipo)) else f"{tipo} {nome}"
    if item.localizacao and not contem(texto, item.localizacao):
        texto += f" ({item.localizacao})"
    return texto


def _rotulo(codigo: str | None) -> str:
    if not codigo:
        return "SEM INFORMAÇÃO"
    return _ROTULOS.get(codigo, codigo.replace("_", " "))


def _num(valor: float) -> str:
    """920.0 -> '920'; 87.456 -> '87.46'."""
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def _milhar(valor: int) -> str:
    """12000 -> '12.000'."""
    return f"{valor:,}".replace(",", ".")
