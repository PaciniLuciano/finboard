import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime

def converter_numpy(obj):
    import numpy as np
    if isinstance(obj, dict):
        return {k: converter_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [converter_numpy(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    return obj

async def calcular_momento(ticker: str, mercado: str = "BR") -> dict:
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        
        loop = asyncio.get_event_loop()
        ativo = yf.Ticker(ticker_yf)
        
        # .history() involves I/O and processing, running in executor
        hist = await loop.run_in_executor(None, ativo.history, "1y")

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "score_momento": 5.0, "erro": "Historico insuficiente"}

        close = hist["Close"]
        mm20  = float(close.rolling(20).mean().iloc[-1])
        mm50  = float(close.rolling(50).mean().iloc[-1])
        mm200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        preco_atual = float(close.iloc[-1])

        delta = close.diff()
        ganho = delta.clip(lower=0).rolling(14).mean()
        perda = (-delta.clip(upper=0)).rolling(14).mean()
        rs = ganho / perda
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        retorno_6m = float((preco_atual / close.iloc[-126] - 1) * 100) if len(close) >= 126 else None
        retorno_12m = float((preco_atual / close.iloc[0] - 1) * 100)

        pontos = 0
        detalhes = {}

        if mm200:
            acima_mm200 = preco_atual > mm200
            detalhes["mm200"] = {"valor": round(mm200, 2), "preco_acima": bool(acima_mm200)}
            pontos += 3 if acima_mm200 else 0

        acima_mm50 = preco_atual > mm50
        detalhes["mm50"] = {"valor": round(mm50, 2), "preco_acima": bool(acima_mm50)}
        pontos += 2 if acima_mm50 else 0

        detalhes["rsi"] = round(rsi, 1)
        if rsi < 30:
            pontos += 2
        elif rsi <= 70:
            pontos += 1

        if retorno_6m is not None:
            detalhes["retorno_6m"] = round(retorno_6m, 2)
            if retorno_6m > 10:
                pontos += 2
            elif retorno_6m > 0:
                pontos += 1

        detalhes["retorno_12m"] = round(retorno_12m, 2)
        if retorno_12m > 0:
            pontos += 1

        score = round((pontos / 10) * 10, 1)

        return {
            "ticker": ticker,
            "score_momento": score,
            "pontos_brutos": pontos,
            "preco_atual": round(preco_atual, 2),
            "detalhes": detalhes,
            "calculado_em": datetime.now().isoformat()
        }

    except Exception as e:
        return {"ticker": ticker, "score_momento": 5.0, "erro": str(e)}
