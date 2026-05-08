import time
import requests
import yfinance as yf

_CACHE_TTL = 30 * 60
_cache: dict = {}

# Prêmio mínimo exigido acima do CDI por classe de ativo
PREMIO_MINIMO = {
    "ACAO":         8.5,
    "FII":          3.0,
    "ETF_BR":       5.0,
    "ETF_EUA":      8.0,
    "TESOURO":      0.0,
    "FUNDO_INVEST": None,
}


def calcular_premio(ticker: str, classe: str, mercado: str, cdi: float) -> dict:
    chave = (ticker.upper(), classe, mercado)
    cached = _cache.get(chave)
    if cached and (time.monotonic() - cached["ts"]) < _CACHE_TTL:
        return {**cached["data"], "cache": True}

    resultado = _calcular(ticker, classe, mercado, cdi)
    _cache[chave] = {"data": resultado, "ts": time.monotonic()}
    return resultado


def _calcular(ticker: str, classe: str, mercado: str, cdi: float) -> dict:
    base = {"ticker": ticker, "classe": classe, "cache": False}

    premio_minimo = PREMIO_MINIMO.get(classe)
    if premio_minimo is None:
        return {**base, "yield_esperado": None, "sinal": "N/A",
                "detalhes": {}, "yield_tipo": None}

    try:
        session = requests.Session()
        session.verify = False
        ticker_yf = f"{ticker.upper()}.SA" if mercado == "BR" else ticker.upper()
        info = yf.Ticker(ticker_yf, session=session).info

        pe_raw = info.get("trailingPE") or info.get("forwardPE")
        dy_raw = info.get("dividendYield") or 0
        pe  = float(pe_raw) if pe_raw else None
        dy  = round(float(dy_raw) * 100, 2) if dy_raw else 0

        yield_esperado: float | None = None
        yield_tipo: str | None = None

        if classe == "FII":
            if dy > 0:
                yield_esperado, yield_tipo = dy, "dividendo"
            elif pe and pe > 0:
                yield_esperado, yield_tipo = round((1 / pe) * 100, 2), "lucro"
        else:
            if pe and pe > 0:
                yield_esperado, yield_tipo = round((1 / pe) * 100, 2), "lucro"
            elif dy > 0:
                yield_esperado, yield_tipo = dy, "dividendo"

        if yield_esperado is None:
            return {**base, "yield_esperado": None, "sinal": "SEM_DADO",
                    "yield_tipo": None, "detalhes": {"pe": pe, "dy": dy}}

        benchmark   = round(cdi + premio_minimo, 2)
        premio_cdi  = round(yield_esperado - cdi, 2)
        gap         = round(yield_esperado - benchmark, 2)

        if yield_esperado >= benchmark:
            sinal = "ATRATIVO"
        elif yield_esperado >= cdi:
            sinal = "NEUTRO"
        else:
            sinal = "ABAIXO_CDI"

        return {
            **base,
            "yield_esperado": yield_esperado,
            "yield_tipo": yield_tipo,
            "cdi": round(cdi, 2),
            "benchmark": benchmark,
            "premio_minimo": premio_minimo,
            "premio_cdi": premio_cdi,
            "gap": gap,
            "sinal": sinal,
            "detalhes": {"pe": round(pe, 2) if pe else None, "dy": dy},
        }

    except Exception as e:
        return {**base, "yield_esperado": None, "sinal": "ERRO",
                "yield_tipo": None, "detalhes": {}, "erro": str(e)}
