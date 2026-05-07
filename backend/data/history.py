import yfinance as yf
import time

_HISTORY_TTL = 30 * 60  # 30 minutos — dados intraday suficiente
_cache: dict = {}        # chave: (ticker_yf, periodo)

def buscar_historico(ticker: str, mercado: str = "BR", periodo: str = "1y") -> dict:
    ticker_yf = f"{ticker.upper()}.SA" if mercado == "BR" else ticker.upper()
    chave = (ticker_yf, periodo)

    cached = _cache.get(chave)
    if cached and (time.monotonic() - cached["ts"]) < _HISTORY_TTL:
        return {**cached["data"], "cache": True}

    hist = yf.Ticker(ticker_yf).history(period=periodo)
    if hist.empty:
        raise ValueError(f"Sem dados para {ticker}")

    candles = []
    volumes = []
    for data, row in hist.iterrows():
        d = str(data)[:10]
        candles.append({
            "time": d,
            "open":  round(float(row["Open"]),  2),
            "high":  round(float(row["High"]),  2),
            "low":   round(float(row["Low"]),   2),
            "close": round(float(row["Close"]), 2),
        })
        volumes.append({"time": d, "value": int(row["Volume"])})

    resultado = {
        "ticker": ticker.upper(),
        "mercado": mercado,
        "periodo": periodo,
        "candles": candles,
        "volumes": volumes,
        "cache": False,
    }
    _cache[chave] = {"data": resultado, "ts": time.monotonic()}
    return resultado
