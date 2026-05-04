import yfinance as yf
import pandas as pd
from datetime import datetime

def calcular_momento(ticker: str, mercado: str = "BR") -> dict:
    """
    Calcula score de momento técnico para um ativo.
    Retorna score de 0 a 10.
    """
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        ativo = yf.Ticker(ticker_yf)

        # Busca histórico de 1 ano
        hist = ativo.history(period="1y")

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "score_momento": None, "erro": "Histórico insuficiente"}

        close = hist["Close"]

        # ── MÉDIAS MÓVEIS ─────────────────────────────────
        mm20  = close.rolling(20).mean().iloc[-1]
        mm50  = close.rolling(50).mean().iloc[-1]
        mm200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        preco_atual = close.iloc[-1]

        # ── RSI 14 DIAS ───────────────────────────────────
        delta = close.diff()
        ganho = delta.clip(lower=0).rolling(14).mean()
        perda = (-delta.clip(upper=0)).rolling(14).mean()
        rs = ganho / perda
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # ── MOMENTUM 6M e 12M ─────────────────────────────
        if len(close) >= 126:
            retorno_6m = (preco_atual / close.iloc[-126] - 1) * 100
        else:
            retorno_6m = None

        retorno_12m = (preco_atual / close.iloc[0] - 1) * 100

        # ── SCORING ───────────────────────────────────────
        pontos = 0
        detalhes = {}

        # MM200 (0-3 pontos)
        if mm200:
            acima_mm200 = preco_atual > mm200
            detalhes["mm200"] = {
                "valor": round(mm200, 2),
                "preco_acima": acima_mm200
            }
            pontos += 3 if acima_mm200 else 0

        # MM50 (0-2 pontos)
        acima_mm50 = preco_atual > mm50
        detalhes["mm50"] = {
            "valor": round(mm50, 2),
            "preco_acima": acima_mm50
        }
        pontos += 2 if acima_mm50 else 0

        # RSI como filtro de extremo (0-2 pontos)
        detalhes["rsi"] = round(rsi, 1)
        if rsi < 30:
            pontos += 2  # sobrevendido — oportunidade
        elif rsi < 50:
            pontos += 1  # neutro-baixo
        elif rsi <= 70:
            pontos += 1  # neutro-alto
        else:
            pontos += 0  # sobrecomprado — cuidado

        # Momentum 6M (0-2 pontos)
        if retorno_6m is not None:
            detalhes["retorno_6m"] = round(retorno_6m, 2)
            if retorno_6m > 10:
                pontos += 2
            elif retorno_6m > 0:
                pontos += 1

        # Momentum 12M (0-1 ponto)
        detalhes["retorno_12m"] = round(retorno_12m, 2)
        if retorno_12m > 0:
            pontos += 1

        # Normaliza para 0-10
        max_pontos = 10
        score = round((pontos / max_pontos) * 10, 1)

        return {
            "ticker": ticker,
            "score_momento": score,
            "pontos_brutos": pontos,
            "preco_atual": round(preco_atual, 2),
            "detalhes": detalhes,
            "calculado_em": datetime.now().isoformat()
        }

    except Exception as e:
        return {"ticker": ticker, "score_momento": None, "erro": str(e)}


if __name__ == "__main__":
    print("Testando Score de Momento...\n")
    for ticker in ["PETR4", "VALE3", "HGLG11"]:
        r = calcular_momento(ticker)
        print(f"{ticker}: Score {r.get('score_momento')} | RSI {r.get('detalhes', {}).get('rsi')} | 12m {r.get('detalhes', {}).get('retorno_12m')}%")
        print(f"  Detalhes: {r.get('detalhes')}\n")
