import asyncio
import logging
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

BACEN_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

# Ajuste de score macro por setor — modificador somado ao score base da classe
AJUSTE_SETOR = {
    "BANCO": {"DEFENSIVO": 1.5, "NEUTRO": 0.5, "AGRESSIVO": -1.0},
    "SEGURO": {"DEFENSIVO": 1.0, "NEUTRO": 0.5, "AGRESSIVO": -0.5},
    "VAREJO": {"DEFENSIVO": -1.5, "NEUTRO": -0.5, "AGRESSIVO": 1.5},
    "CONSTRUTORA": {"DEFENSIVO": -1.5, "NEUTRO": -0.5, "AGRESSIVO": 1.5},
    "TECH": {"DEFENSIVO": -1.0, "NEUTRO": 0.0, "AGRESSIVO": 1.0},
    "COMMODITY": {"DEFENSIVO": 0.0, "NEUTRO": 0.5, "AGRESSIVO": 0.5},
    "FII_PAPEL": {"DEFENSIVO": 1.5, "NEUTRO": 0.5, "AGRESSIVO": -1.0},
}

TICKER_SETOR = {
    "ITUB": "BANCO",
    "BBDC": "BANCO",
    "SANB": "BANCO",
    "BBAS": "BANCO",
    "BPAC": "BANCO",
    "ABCB": "BANCO",
    "MGLU": "VAREJO",
    "VIIA": "VAREJO",
    "AMER": "VAREJO",
    "LREN": "VAREJO",
    "ALPA": "VAREJO",
    "SOMA": "VAREJO",
    "CYRE": "CONSTRUTORA",
    "MRVE": "CONSTRUTORA",
    "EZTC": "CONSTRUTORA",
    "DIRR": "CONSTRUTORA",
    "EVEN": "CONSTRUTORA",
    "LAVV": "CONSTRUTORA",
    "PETR": "COMMODITY",
    "VALE": "COMMODITY",
    "CSNA": "COMMODITY",
    "GGBR": "COMMODITY",
    "USIM": "COMMODITY",
    "BRAP": "COMMODITY",
    "BBSE": "SEGURO",
    "PSSA": "SEGURO",
    "EGIE": "SEGURO",
    "MXRF": "FII_PAPEL",
    "KNCR": "FII_PAPEL",
    "IRDM": "FII_PAPEL",
    "RECR": "FII_PAPEL",
    "BCFF": "FII_PAPEL",
}

SEGMENTO_PARA_AJUSTE = {
    "BANCO_FINANCEIRO": "BANCO",
    "SEGURO_FINANCEIRO": "SEGURO",
    "VAREJO_CONSUMO": "VAREJO",
    "CONSTRUCAO_IMOBILIARIA": "CONSTRUTORA",
    "TECNOLOGIA": "TECH",
    "PETROLEO_GAS": "COMMODITY",
    "MINERACAO_SIDERURGIA": "COMMODITY",
    "AGRO_ALIMENTOS": "COMMODITY",
    "PAPEL_CELULOSE": "COMMODITY",
    "FII_PAPEL": "FII_PAPEL",
}


def detectar_setor(ticker: str) -> str | None:
    # Prioridade: ativos_master (segmento enriquecido via yfinance)
    try:
        import sqlite3

        conn = sqlite3.connect("finboard.db")
        row = conn.execute(
            "SELECT segmento FROM ativos_master WHERE ticker=?", (ticker.upper(),)
        ).fetchone()
        conn.close()
        if row and row[0]:
            mapeado = SEGMENTO_PARA_AJUSTE.get(row[0])
            if mapeado:
                return mapeado
    except Exception:
        pass
    # Fallback: dicionario hardcoded (primeiros 4 caracteres)
    return TICKER_SETOR.get(ticker[:4].upper())


# Cache in-memory para dados macro — TTL 6h
_MACRO_TTL = 6 * 3600
_macro_cache: dict = {"resultado": None, "ts": 0.0}


def invalidar_cache_macro() -> None:
    _macro_cache["resultado"] = None
    _macro_cache["ts"] = 0.0


def _cache_macro_valido() -> bool:
    return (
        _macro_cache["resultado"] is not None
        and (time.monotonic() - _macro_cache["ts"]) < _MACRO_TTL
    )


async def buscar_selic() -> float:
    try:
        url = f"{BACEN_URL}.432/dados/ultimos/1?formato=json"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
            return float(data[0]["valor"])
    except Exception:
        return 13.75


async def buscar_ipca_12m() -> float:
    try:
        url = f"{BACEN_URL}.13522/dados/ultimos/1?formato=json"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
            return float(data[0]["valor"])
    except Exception:
        return 5.0


async def buscar_focus_selic() -> float | None:
    ano_atual = datetime.now().year
    base = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
    for ano in [ano_atual + 1, ano_atual]:
        try:
            # $ deve ser literal na URL — httpx codifica $ como %24 no dict de params,
            # o que o servidor Bacen/Olinda rejeita com HTTP 400
            url = (
                f"{base}?$filter=Indicador eq 'Selic' and DataReferencia eq '{ano}'"
                f"&$orderby=Data desc&$top=1&$format=json"
                f"&$select=Indicador,Data,Mediana,DataReferencia"
            )
            async with httpx.AsyncClient(verify=False, timeout=15, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    logger.error("Focus Selic %s: HTTP %s", ano, r.status_code)
                    continue
                data = r.json()
                if data.get("value"):
                    valor = float(data["value"][0]["Mediana"])
                    logger.info("Focus Selic %s: %.2f%%", ano, valor)
                    return valor
            logger.info("Focus Selic %s: resposta vazia, tentando ano anterior", ano)
        except Exception as e:
            logger.error("Erro ao buscar Focus Selic %s: %s", ano, e)
    return None


async def calcular_regime_macro(forcar: bool = False) -> dict:
    if not forcar and _cache_macro_valido():
        return {**_macro_cache["resultado"], "cache": True}

    selic, ipca, selic_esperada = await asyncio.gather(
        buscar_selic(), buscar_ipca_12m(), buscar_focus_selic()
    )

    detalhes = {
        "selic_atual": selic,
        "ipca_12m": ipca,
        "juro_real": round(selic - ipca, 2),
        "focus_selic_esperada": selic_esperada,
    }

    pontos_regime = 0

    if selic > 13:
        pontos_regime -= 2
    elif selic > 11:
        pontos_regime -= 1
    elif selic < 9:
        pontos_regime += 2
    else:
        pontos_regime += 1

    if selic_esperada:
        variacao = selic_esperada - selic
        if variacao < -1.5:
            pontos_regime += 2
        elif variacao < -0.5:
            pontos_regime += 1
        elif variacao > 0.5:
            pontos_regime -= 1

    if ipca < 4:
        pontos_regime += 1
    elif ipca > 6:
        pontos_regime -= 1

    if pontos_regime >= 2:
        regime = "AGRESSIVO"
    elif pontos_regime <= -1:
        regime = "DEFENSIVO"
    else:
        regime = "NEUTRO"

    if regime == "DEFENSIVO":
        scores = {
            "ACAO": 4.0,
            "FII_PAPEL": 8.5,
            "FII_TIJOLO": 4.0,
            "ETF_BR": 4.5,
            "ETF_EUA": 6.0,
            "TESOURO_IPCA": 9.0,
            "TESOURO_SELIC": 8.0,
            "CDB": 8.5,
        }
    elif regime == "NEUTRO":
        scores = {
            "ACAO": 6.0,
            "FII_PAPEL": 7.0,
            "FII_TIJOLO": 6.0,
            "ETF_BR": 6.0,
            "ETF_EUA": 6.5,
            "TESOURO_IPCA": 7.5,
            "TESOURO_SELIC": 6.5,
            "CDB": 7.0,
        }
    else:
        scores = {
            "ACAO": 8.5,
            "FII_PAPEL": 5.5,
            "FII_TIJOLO": 8.5,
            "ETF_BR": 8.0,
            "ETF_EUA": 7.5,
            "TESOURO_IPCA": 6.0,
            "TESOURO_SELIC": 4.5,
            "CDB": 5.0,
        }

    resultado = {
        "regime": regime,
        "pontos_regime": pontos_regime,
        "detalhes": detalhes,
        "scores_por_classe": scores,
        "calculado_em": datetime.now().isoformat(),
        "cache": False,
    }
    _macro_cache["resultado"] = resultado
    _macro_cache["ts"] = time.monotonic()
    return resultado


async def get_score_macro(classe: str, macro_info: dict = None, ticker: str = "") -> float:
    if macro_info is None:
        macro_info = await calcular_regime_macro()
    scores = macro_info.get("scores_por_classe", {})
    regime = macro_info.get("regime", "NEUTRO")
    mapa = {
        "ACAO": "ACAO",
        "FII": "FII_TIJOLO",
        "ETF_BR": "ETF_BR",
        "ETF_EUA": "ETF_EUA",
        "TESOURO": "TESOURO_IPCA",
        "CDB": "CDB",
    }
    score_base = scores.get(mapa.get(classe, "ACAO"), 5.0)

    setor = detectar_setor(ticker) if ticker else None
    if setor and setor in AJUSTE_SETOR:
        ajuste = AJUSTE_SETOR[setor].get(regime, 0.0)
        score_base = round(min(10.0, max(0.0, score_base + ajuste)), 1)

    return score_base
