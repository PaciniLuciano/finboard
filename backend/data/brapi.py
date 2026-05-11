import yfinance as yf
import httpx
import os
import urllib3
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Desabilita avisos de conexão insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
BRAPI_URL = "https://brapi.dev/api"

# ── BRAPI (ETFs BR) ───────────────────────────────────────

async def buscar_preco_brapi(ticker: str) -> dict:
    """Busca preço via brapi.dev — usado para ETFs BR."""
    try:
        url = f"{BRAPI_URL}/quote/{ticker}?token={BRAPI_TOKEN}"
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, timeout=10)
            data = response.json()

        if "results" not in data or not data["results"]:
            return {"erro": f"Ticker {ticker} não encontrado no brapi"}

        r = data["results"][0]
        return {
            "ticker": ticker,
            "preco": r.get("regularMarketPrice"),
            "variacao_dia": round(r.get("regularMarketChangePercent", 0), 2),
            "volume": r.get("regularMarketVolume"),
            "nome": r.get("longName") or r.get("shortName"),
            "moeda": "BRL",
            "fonte": "brapi",
            "atualizado_em": datetime.now().isoformat()
        }
    except Exception as e:
        return {"erro": str(e), "ticker": ticker}

# ── YFINANCE (Ações, FIIs, ETFs EUA) ─────────────────────

async def buscar_preco_yfinance(ticker: str, mercado: str = "BR") -> dict:
    """Busca preço via yfinance."""
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        
        loop = asyncio.get_event_loop()
        ativo = yf.Ticker(ticker_yf)
        
        # yfinance doesn't have an async API for info, running in executor
        info = await loop.run_in_executor(None, getattr, ativo, "info")

        preco = (
            info.get("regularMarketPrice") or
            info.get("currentPrice") or
            info.get("previousClose")
        )

        variacao = info.get("regularMarketChangePercent", 0)

        return {
            "ticker": ticker,
            "preco": preco,
            "variacao_dia": round(variacao, 2) if variacao else 0,
            "volume": info.get("regularMarketVolume"),
            "nome": info.get("longName") or info.get("shortName"),
            "moeda": "BRL" if mercado == "BR" else "USD",
            "fonte": "yfinance",
            "atualizado_em": datetime.now().isoformat()
        }
    except Exception as e:
        return {"erro": str(e), "ticker": ticker}

# ── ROTEADOR PRINCIPAL ────────────────────────────────────

ETFs_BR = ["BOVA11", "IVVB11", "SMAL11", "HASH11", "XFIX11",
           "DIVO11", "ECOO11", "FIND11", "GOLD11", "MATB11"]

async def buscar_preco(ticker: str, mercado: str = "BR") -> dict:
    """
    Roteador inteligente:
    - ETFs BR → brapi
    - Ações, FIIs, ETFs EUA → yfinance
    """
    if mercado == "EUA":
        return await buscar_preco_yfinance(ticker, mercado="EUA")

    if ticker in ETFs_BR:
        resultado = await buscar_preco_brapi(ticker)
        if "erro" not in resultado:
            return resultado
        # fallback para yfinance se brapi falhar
        return await buscar_preco_yfinance(ticker, mercado="BR")

    # Ações e FIIs → yfinance
    resultado = await buscar_preco_yfinance(ticker, mercado="BR")
    if "erro" not in resultado:
        return resultado
    # fallback para brapi
    return await buscar_preco_brapi(ticker)

async def buscar_multiplos(tickers: list, mercado: str = "BR") -> list:
    """Busca preços de múltiplos tickers em paralelo."""
    tasks = [buscar_preco(t, mercado) for t in tickers]
    return await asyncio.gather(*tasks)

async def buscar_cambio_usd_brl() -> float:
    """Busca câmbio USD/BRL atual."""
    try:
        loop = asyncio.get_event_loop()
        cambio = yf.Ticker("USDBRL=X")
        info = await loop.run_in_executor(None, getattr, cambio, "info")
        return info.get("regularMarketPrice") or info.get("previousClose") or 0.0
    except:
        return 0.0

async def buscar_ibovespa() -> dict:
    """Busca dados do Ibovespa."""
    try:
        loop = asyncio.get_event_loop()
        ibov = yf.Ticker("^BVSP")
        info = await loop.run_in_executor(None, getattr, ibov, "info")
        return {
            "ticker": "IBOV",
            "preco": info.get("regularMarketPrice") or info.get("previousClose") or 0.0,
            "variacao_dia": round(info.get("regularMarketChangePercent", 0), 2),
            "fonte": "yfinance",
            "atualizado_em": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "ticker": "IBOV",
            "preco": 0.0,
            "variacao_dia": 0.0,
            "erro": str(e),
            "atualizado_em": datetime.now().isoformat()
        }
