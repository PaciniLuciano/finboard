import yfinance as yf
import requests
import os
import urllib3
from datetime import datetime
from dotenv import load_dotenv

# Desabilita avisos de conexão insegura (necessário ao usar verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
BRAPI_URL = "https://brapi.dev/api"

# ── BRAPI (ETFs BR) ───────────────────────────────────────

def buscar_preco_brapi(ticker: str) -> dict:
    """Busca preço via brapi.dev — usado para ETFs BR."""
    try:
        url = f"{BRAPI_URL}/quote/{ticker}?token={BRAPI_TOKEN}"
        # verify=False ignora erro de certificado SSL da rede corporativa
        response = requests.get(url, timeout=10, verify=False)
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

def buscar_preco_yfinance(ticker: str, mercado: str = "BR") -> dict:
    """Busca preço via yfinance."""
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        
        # Configura sessão para ignorar SSL no yfinance
        session = requests.Session()
        session.verify = False
        
        ativo = yf.Ticker(ticker_yf, session=session)
        info = ativo.info

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

def buscar_preco(ticker: str, mercado: str = "BR") -> dict:
    """
    Roteador inteligente:
    - ETFs BR → brapi
    - Ações, FIIs, ETFs EUA → yfinance
    """
    if mercado == "EUA":
        return buscar_preco_yfinance(ticker, mercado="EUA")

    if ticker in ETFs_BR:
        resultado = buscar_preco_brapi(ticker)
        if "erro" not in resultado:
            return resultado
        # fallback para yfinance se brapi falhar
        return buscar_preco_yfinance(ticker, mercado="BR")

    # Ações e FIIs → yfinance
    resultado = buscar_preco_yfinance(ticker, mercado="BR")
    if "erro" not in resultado:
        return resultado
    # fallback para brapi
    return buscar_preco_brapi(ticker)

def buscar_multiplos(tickers: list, mercado: str = "BR") -> list:
    """Busca preços de múltiplos tickers."""
    return [buscar_preco(t, mercado) for t in tickers]

def buscar_cambio_usd_brl() -> float:
    """Busca câmbio USD/BRL atual."""
    try:
        cambio = yf.Ticker("USDBRL=X")
        info = cambio.info
        return info.get("regularMarketPrice") or info.get("previousClose") or 0.0
    except:
        return 0.0

def buscar_ibovespa() -> dict:
    """Busca dados do Ibovespa."""
    try:
        ibov = yf.Ticker("^BVSP")
        info = ibov.info
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

if __name__ == "__main__":
    print("Testando fontes de dados...\n")

    print("=== AÇÕES (yfinance) ===")
    for ticker in ["PETR4", "VALE3", "ITUB4"]:
        r = buscar_preco(ticker)
        print(f"{ticker}: R$ {r.get('preco')} ({r.get('variacao_dia')}%) [{r.get('fonte')}]")

    print("\n=== FIIs (yfinance) ===")
    for ticker in ["HGLG11", "MXRF11"]:
        r = buscar_preco(ticker)
        print(f"{ticker}: R$ {r.get('preco')} ({r.get('variacao_dia')}%) [{r.get('fonte')}]")

    print("\n=== ETFs BR (brapi) ===")
    for ticker in ["BOVA11", "IVVB11"]:
        r = buscar_preco(ticker)
        print(f"{ticker}: R$ {r.get('preco')} ({r.get('variacao_dia')}%) [{r.get('fonte')}]")

    print("\n=== ETFs EUA (yfinance) ===")
    for ticker in ["VOO", "QQQ"]:
        r = buscar_preco(ticker, mercado="EUA")
        print(f"{ticker}: US$ {r.get('preco')} ({r.get('variacao_dia')}%) [{r.get('fonte')}]")

    print("\n=== CÂMBIO ===")
    print(f"USD/BRL: R$ {buscar_cambio_usd_brl()}")

    print("\n=== IBOVESPA ===")
    ibov = buscar_ibovespa()
    print(f"IBOV: {ibov.get('preco')} ({ibov.get('variacao_dia')}%)")
