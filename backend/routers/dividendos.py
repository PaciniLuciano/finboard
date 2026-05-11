from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel
from datetime import date
import yfinance as yf

from backend.database import get_db, Ativo, Dividendo
from backend.data.cache import buscar_preco_com_cache as buscar_preco

router = APIRouter()


class DividendoCreate(BaseModel):
    ticker: str
    valor_por_cota: float
    quantidade_cotas: float
    data_pagamento: date
    tipo: str = "PROVENTO"


@router.post("/dividendos")
def registrar_dividendo(div: DividendoCreate, db: Session = Depends(get_db)):
    ticker = div.ticker.upper()
    valor_total = div.valor_por_cota * div.quantidade_cotas
    db.add(Dividendo(
        ticker=ticker,
        valor_por_cota=div.valor_por_cota,
        quantidade_cotas=div.quantidade_cotas,
        valor_total=valor_total,
        data_pagamento=div.data_pagamento,
        tipo=div.tipo,
    ))
    db.commit()
    return {"mensagem": f"Dividendo de {ticker} registrado", "valor_total": round(valor_total, 2)}


@router.get("/dividendos/{ticker}")
def listar_dividendos(ticker: str, db: Session = Depends(get_db)):
    items = db.query(Dividendo).filter(Dividendo.ticker == ticker.upper()).order_by(desc(Dividendo.data_pagamento)).all()
    return [{"id": i.id, "ticker": i.ticker, "valor_por_cota": i.valor_por_cota,
             "quantidade_cotas": i.quantidade_cotas, "valor_total": i.valor_total,
             "data_pagamento": str(i.data_pagamento), "tipo": i.tipo} for i in items]


@router.get("/dividendos")
def listar_todos_dividendos(db: Session = Depends(get_db)):
    items = db.query(Dividendo).order_by(desc(Dividendo.data_pagamento)).all()
    return [{"id": i.id, "ticker": i.ticker, "valor_por_cota": i.valor_por_cota,
             "quantidade_cotas": i.quantidade_cotas, "valor_total": i.valor_total,
             "data_pagamento": str(i.data_pagamento), "tipo": i.tipo} for i in items]


@router.get("/retorno-total/{ticker}")
async def retorno_total(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")

    result = db.query(func.sum(Dividendo.valor_total), func.count(Dividendo.id)).filter(Dividendo.ticker == ticker).one()
    total_dividendos = result[0] or 0
    qtd_proventos = result[1] or 0

    preco_atual = await buscar_preco(ativo.ticker, ativo.mercado)
    preco = preco_atual.get("preco") or ativo.preco_medio

    valor_atual = preco * ativo.quantidade
    valor_investido = ativo.preco_medio * ativo.quantidade
    retorno_cota = valor_atual - valor_investido
    retorno_cota_pct = (retorno_cota / valor_investido * 100) if valor_investido > 0 else 0
    dy_pct = (total_dividendos / valor_investido * 100) if valor_investido > 0 else 0

    return {
        "ticker": ticker,
        "quantidade": ativo.quantidade,
        "preco_medio": ativo.preco_medio,
        "preco_atual": preco,
        "valor_investido": round(valor_investido, 2),
        "valor_atual": round(valor_atual, 2),
        "retorno_cota_rs": round(retorno_cota, 2),
        "retorno_cota_pct": round(retorno_cota_pct, 2),
        "total_dividendos": round(total_dividendos, 2),
        "dy_recebido_pct": round(dy_pct, 2),
        "retorno_total_rs": round(retorno_cota + total_dividendos, 2),
        "retorno_total_pct": round(retorno_cota_pct + dy_pct, 2),
        "qtd_proventos": qtd_proventos,
    }


@router.post("/dividendos/importar/{ticker}")
def importar_dividendos(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado na carteira")

    try:
        ticker_yf = f"{ticker}.SA" if ativo.mercado == "BR" else ticker
        divs = yf.Ticker(ticker_yf).dividends
        if divs.empty:
            return {"mensagem": "Nenhum dividendo encontrado", "importados": 0}

        if ativo.data_compra:
            divs = divs[divs.index >= str(ativo.data_compra)]

        importados, ignorados = 0, 0
        for data, valor in divs.items():
            data_obj = date.fromisoformat(str(data)[:10])
            existente = db.query(Dividendo).filter(
                Dividendo.ticker == ticker,
                Dividendo.data_pagamento == data_obj,
            ).first()
            if existente:
                ignorados += 1
                continue
            db.add(Dividendo(
                ticker=ticker,
                valor_por_cota=float(valor),
                quantidade_cotas=ativo.quantidade,
                valor_total=float(valor) * ativo.quantidade,
                data_pagamento=data_obj,
                tipo="AUTO",
            ))
            importados += 1

        db.commit()
        return {
            "mensagem": f"{ticker} — {importados} proventos importados",
            "importados": importados,
            "ignorados": ignorados,
            "quantidade_cotas": ativo.quantidade,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dividendos/importar-todos")
def importar_todos_dividendos(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    resultados = []
    for ativo in ativos:
        try:
            ticker_yf = f"{ativo.ticker}.SA" if ativo.mercado == "BR" else ativo.ticker
            divs = yf.Ticker(ticker_yf).dividends
            if divs.empty:
                continue
            if ativo.data_compra:
                divs = divs[divs.index >= str(ativo.data_compra)]
            importados = 0
            for data, valor in divs.items():
                data_obj = date.fromisoformat(str(data)[:10])
                existente = db.query(Dividendo).filter(
                    Dividendo.ticker == ativo.ticker,
                    Dividendo.data_pagamento == data_obj,
                ).first()
                if existente:
                    continue
                db.add(Dividendo(
                    ticker=ativo.ticker,
                    valor_por_cota=float(valor),
                    quantidade_cotas=ativo.quantidade,
                    valor_total=float(valor) * ativo.quantidade,
                    data_pagamento=data_obj,
                    tipo="AUTO",
                ))
                importados += 1
            db.commit()
            if importados > 0:
                resultados.append({"ticker": ativo.ticker, "importados": importados})
        except Exception:
            continue
    return {"mensagem": "Importação concluída", "resultados": resultados}
