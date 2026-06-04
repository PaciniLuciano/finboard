import asyncio
import logging
from backend.scoring.momento import calcular_momento
from backend.scoring.valuation import calcular_valuation
from backend.scoring.macro import calcular_regime_macro, get_score_macro
from datetime import datetime

logger = logging.getLogger(__name__)

PESOS_PADRAO = {
    "valuation": 0.40,
    "momento": 0.30,
    "macro": 0.30
}

async def calcular_score_final(ticker: str, classe: str = "ACAO", mercado: str = "BR", pesos: dict = None, macro_info: dict = None) -> dict:
    if pesos is None:
        pesos = PESOS_PADRAO

    logger.info("Calculando scores para %s", ticker)

    if macro_info is None:
        macro_info = await calcular_regime_macro()

    s_valuation, s_momento = await asyncio.gather(
        calcular_valuation(ticker, classe, mercado),
        calcular_momento(ticker, mercado)
    )

    s_macro = await get_score_macro(classe, macro_info, ticker=ticker)

    v = s_valuation.get("score_valuation")
    v = v if v is not None else 5.0
    m = s_momento.get("score_momento")
    m = m if m is not None else 5.0
    mac = s_macro

    score_final = round(
        v   * pesos["valuation"] +
        m   * pesos["momento"]  +
        mac * pesos["macro"],
        1
    )

    return {
        "ticker": ticker,
        "classe": classe,
        "mercado": mercado,
        "score_final": score_final,
        "score_valuation": v,
        "score_momento": m,
        "score_macro": mac,
        "regime_macro": macro_info["regime"],
        "pesos": pesos,
        "detalhes_valuation": s_valuation.get("detalhes", {}),
        "detalhes_momento": s_momento.get("detalhes", {}),
        "detalhes_macro": macro_info["detalhes"],
        "calculado_em": datetime.now().isoformat()
    }

async def calcular_scores_carteira(ativos: list, pesos: dict = None) -> list:
    if not ativos:
        return []

    macro_info = await calcular_regime_macro()

    sem = asyncio.Semaphore(8)

    async def sem_task(ativo):
        async with sem:
            return await calcular_score_final(
                ativo["ticker"],
                ativo.get("classe", "ACAO"),
                ativo.get("mercado", "BR"),
                pesos,
                macro_info
            )

    resultados_raw = await asyncio.gather(
        *[sem_task(a) for a in ativos], return_exceptions=True
    )

    resultados = []
    for i, res in enumerate(resultados_raw):
        if isinstance(res, Exception):
            logger.error("Erro em %s: %s", ativos[i]["ticker"], res)
        else:
            resultados.append(res)

    resultados.sort(key=lambda x: x["score_final"], reverse=True)
    return resultados
