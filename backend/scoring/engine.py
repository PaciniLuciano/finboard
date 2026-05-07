from backend.scoring.momento import calcular_momento
from backend.scoring.valuation import calcular_valuation
from backend.scoring.macro import calcular_regime_macro, get_score_macro
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

PESOS_PADRAO = {
    "valuation": 0.40,
    "momento": 0.30,
    "macro": 0.30
}

def calcular_score_final(ticker: str, classe: str = "ACAO", mercado: str = "BR", pesos: dict = None, macro_info: dict = None) -> dict:
    if pesos is None:
        pesos = PESOS_PADRAO

    print(f"  Calculando scores para {ticker}...")

    if macro_info is None:
        macro_info = calcular_regime_macro()

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_val = ex.submit(calcular_valuation, ticker, classe, mercado)
        fut_mom = ex.submit(calcular_momento, ticker, mercado)
        s_valuation = fut_val.result()
        s_momento   = fut_mom.result()

    s_macro = get_score_macro(classe, macro_info)

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

def calcular_scores_carteira(ativos: list, pesos: dict = None) -> list:
    if not ativos:
        return []

    # Macro calculado UMA vez para todos os tickers
    macro_info = calcular_regime_macro()

    resultados = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futuros = {
            ex.submit(
                calcular_score_final,
                ativo["ticker"],
                ativo.get("classe", "ACAO"),
                ativo.get("mercado", "BR"),
                pesos,
                macro_info
            ): ativo for ativo in ativos
        }
        for fut in as_completed(futuros):
            try:
                resultados.append(fut.result())
            except Exception as e:
                ativo = futuros[fut]
                print(f"Erro em {ativo['ticker']}: {e}")

    resultados.sort(key=lambda x: x["score_final"], reverse=True)
    return resultados
