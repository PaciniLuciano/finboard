import asyncio
import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


async def calcular_momento(ticker: str, mercado: str = "BR") -> dict:
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker

        loop = asyncio.get_running_loop()
        # auto_adjust=False evita NaN em FIIs BR com dividendos mensais:
        # o ajuste de preço falha para esses ativos e propaga NaN em todo o histórico
        hist = await loop.run_in_executor(
            None, lambda: yf.Ticker(ticker_yf).history(period="1y", auto_adjust=False)
        )

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "score_momento": 5.0, "erro": "Historico insuficiente"}

        close = hist["Close"]

        if close.isna().all():
            return {
                "ticker": ticker,
                "score_momento": 5.0,
                "erro": "Close todo NaN — ativo sem dados de preco",
            }

        # Preenche eventuais NaN isolados com forward-fill antes dos cálculos
        close = close.ffill().dropna()

        if len(close) < 50:
            return {
                "ticker": ticker,
                "score_momento": 5.0,
                "erro": "Historico insuficiente apos limpeza",
            }

        preco_atual = float(close.iloc[-1])

        mm50_raw = close.rolling(50).mean().iloc[-1]
        mm200_raw = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        mm50 = float(mm50_raw) if (mm50_raw is not None and not pd.isna(mm50_raw)) else None
        mm200 = float(mm200_raw) if (mm200_raw is not None and not pd.isna(mm200_raw)) else None

        delta = close.diff()
        ganho = delta.clip(lower=0).rolling(14).mean()
        perda = (-delta.clip(upper=0)).rolling(14).mean()
        # perda=0 → RSI=100; ganho=0 e perda=0 → NaN tratado como neutro (50)
        rs = ganho / perda.replace(0, float("nan"))
        rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
        rsi = 50.0 if pd.isna(rsi_val) else float(rsi_val)

        retorno_6m_raw = (preco_atual / close.iloc[-126] - 1) * 100 if len(close) >= 126 else None
        retorno_12m_raw = (preco_atual / close.iloc[0] - 1) * 100

        retorno_6m = (
            float(retorno_6m_raw)
            if (retorno_6m_raw is not None and not pd.isna(retorno_6m_raw))
            else None
        )
        retorno_12m = float(retorno_12m_raw) if not pd.isna(retorno_12m_raw) else None

        pontos = 0
        detalhes: dict = {}

        if mm200 is not None:
            acima_mm200 = preco_atual > mm200
            detalhes["mm200"] = {"valor": round(mm200, 2), "preco_acima": bool(acima_mm200)}
            pontos += 3 if acima_mm200 else 0

        if mm50 is not None:
            acima_mm50 = preco_atual > mm50
            detalhes["mm50"] = {"valor": round(mm50, 2), "preco_acima": bool(acima_mm50)}
            pontos += 2 if acima_mm50 else 0

        detalhes["rsi"] = round(rsi, 1)
        if 40 <= rsi <= 65:
            pontos += 2  # zona ideal: tendência saudável sem sobrecompra
        elif 30 <= rsi < 40 or 65 < rsi <= 70:
            pontos += 1  # aceitável
        # rsi < 30 (faca caindo) ou > 70 (sobrecomprado): +0

        if retorno_6m is not None:
            detalhes["retorno_6m"] = round(retorno_6m, 2)
            if retorno_6m > 10:
                pontos += 2
            elif retorno_6m > 0:
                pontos += 1

        if retorno_12m is not None:
            detalhes["retorno_12m"] = round(retorno_12m, 2)
            if retorno_12m > 0:
                pontos += 1

        # max_pontos dinâmico: sem MM200 o máximo atingível é 7, não 10
        max_pontos = 10 if mm200 is not None else 7
        score = round((pontos / max_pontos) * 10, 1)

        logger.debug(
            "MOMENTO DEBUG %s — pontos=%s/%s mm200=%s mm50=%s rsi=%.1f retorno_6m=%s retorno_12m=%s len_hist=%s",
            ticker,
            pontos,
            max_pontos,
            round(mm200, 2) if mm200 is not None else None,
            round(mm50, 2) if mm50 is not None else None,
            rsi,
            round(retorno_6m, 2) if retorno_6m is not None else None,
            round(retorno_12m, 2) if retorno_12m is not None else None,
            len(close),
        )

        return {
            "ticker": ticker,
            "score_momento": score,
            "pontos_brutos": pontos,
            "max_pontos": max_pontos,
            "preco_atual": round(preco_atual, 2),
            "detalhes": detalhes,
            "calculado_em": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"ticker": ticker, "score_momento": 5.0, "erro": str(e)}
