from fastapi import APIRouter, HTTPException
from backend.data.brapi import buscar_cambio_usd_brl, buscar_ibovespa
from backend.data.cache import buscar_preco_com_cache as buscar_preco

router = APIRouter()


@router.get("/mercado/preco/{ticker}")
def preco_ativo(ticker: str, mercado: str = "BR"):
    return buscar_preco(ticker, mercado)


@router.get("/mercado/ibovespa")
def ibovespa():
    return buscar_ibovespa()


@router.get("/mercado/cambio")
def cambio():
    return {"usd_brl": buscar_cambio_usd_brl()}


@router.get("/history/{ticker}")
def historico_ativo(ticker: str, mercado: str = "BR", periodo: str = "1y"):
    from backend.data.history import buscar_historico
    try:
        return buscar_historico(ticker, mercado, periodo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
