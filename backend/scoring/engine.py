from backend.scoring.momento import calcular_momento
from backend.scoring.valuation import calcular_valuation
from backend.scoring.macro import calcular_regime_macro, get_score_macro
from datetime import datetime

# Pesos padrão (configuráveis pelo usuário)
PESOS_PADRAO = {
    "valuation": 0.40,
    "momento": 0.30,
    "macro": 0.30
}

def calcular_score_final(ticker: str, classe: str = "ACAO", mercado: str = "BR", pesos: dict = None) -> dict:
    """
    Calcula o score final combinando Valuation + Momento + Macro.
    Score final de 0 a 10.
    """
    if pesos is None:
        pesos = PESOS_PADRAO

    print(f"  Calculando scores para {ticker}...")

    # Calcula os três scores
    s_valuation = calcular_valuation(ticker, classe, mercado)
    s_momento   = calcular_momento(ticker, mercado)
    s_macro     = get_score_macro(classe)

    v = s_valuation.get("score_valuation") or 5.0
    m = s_momento.get("score_momento") or 5.0
    mac = s_macro

    # Score final ponderado
    score_final = round(
        v   * pesos["valuation"] +
        m   * pesos["momento"]  +
        mac * pesos["macro"],
        1
    )

    # Regime macro atual
    macro_info = calcular_regime_macro()

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
    """
    Calcula score final para uma lista de ativos da carteira.
    ativos = [{"ticker": "PETR4", "classe": "ACAO", "mercado": "BR"}, ...]
    """
    resultados = []
    for ativo in ativos:
        score = calcular_score_final(
            ticker=ativo["ticker"],
            classe=ativo.get("classe", "ACAO"),
            mercado=ativo.get("mercado", "BR"),
            pesos=pesos
        )
        resultados.append(score)

    # Ordena por score final decrescente
    resultados.sort(key=lambda x: x["score_final"], reverse=True)
    return resultados

if __name__ == "__main__":
    print("Calculando Score Final — Motor Completo\n")
    print("=" * 50)

    ativos = [
        {"ticker": "PETR4",  "classe": "ACAO", "mercado": "BR"},
        {"ticker": "VALE3",  "classe": "ACAO", "mercado": "BR"},
        {"ticker": "ITUB4",  "classe": "ACAO", "mercado": "BR"},
        {"ticker": "HGLG11", "classe": "FII",  "mercado": "BR"},
        {"ticker": "MXRF11", "classe": "FII",  "mercado": "BR"},
    ]

    resultados = calcular_scores_carteira(ativos)

    print(f"\n{'TICKER':<10} {'CLASSE':<8} {'VALUATION':<12} {'MOMENTO':<10} {'MACRO':<8} {'FINAL':<8} {'REGIME'}")
    print("-" * 70)
    for r in resultados:
        print(f"{r['ticker']:<10} {r['classe']:<8} {r['score_valuation']:<12} {r['score_momento']:<10} {r['score_macro']:<8} {r['score_final']:<8} {r['regime_macro']}")
