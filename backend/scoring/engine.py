import asyncio
from backend.scoring.momento import calcular_momento
from backend.scoring.valuation import calcular_valuation
from backend.scoring.macro import calcular_regime_macro, get_score_macro
from datetime import datetime

PESOS_PADRAO = {
    "valuation": 0.40,
    "momento": 0.30,
    "macro": 0.30
}

async def calcular_score_final(ticker: str, classe: str = "ACAO", mercado: str = "BR", pesos: dict = None, macro_info: dict = None) -> dict:
    if pesos is None:
        pesos = PESOS_PADRAO

    print(f"  Calculando scores para {ticker}...")

    if macro_info is None:
        macro_info = await calcular_regime_macro()

    # Parallelize valuation and moment calculations
    val_task = calcular_valuation(ticker, classe, mercado)
    mom_task = calcular_momento(ticker, mercado)
    
    s_valuation, s_momento = await asyncio.gather(val_task, mom_task)

    s_macro = await get_score_macro(classe, macro_info)

    v   = s_valuation.get("score_valuation") or 5.0
    m   = s_momento.get("score_momento") or 5.0
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

    # Macro calculado UMA vez para todos os tickers
    macro_info = await calcular_regime_macro()

    # Calculate all scores in parallel
    tasks = [
        calcular_score_final(
            ativo["ticker"],
            ativo.get("classe", "ACAO"),
            ativo.get("mercado", "BR"),
            pesos,
            macro_info
        ) for ativo in ativos
    ]
    
    # We can use a semaphore if we want to limit concurrency
    # sem = asyncio.Semaphore(10)
    # async def sem_task(task):
    #     async with sem:
    #         return await task
    # resultados = await asyncio.gather(*[sem_task(t) for t in tasks], return_exceptions=True)
    
    resultados_raw = await asyncio.gather(*tasks, return_exceptions=True)
    
    resultados = []
    for i, res in enumerate(resultados_raw):
        if isinstance(res, Exception):
            print(f"Erro em {ativos[i]['ticker']}: {res}")
        else:
            resultados.append(res)

    resultados.sort(key=lambda x: x["score_final"], reverse=True)
    return resultados
