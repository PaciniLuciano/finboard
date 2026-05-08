from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db, Watchlist

router = APIRouter()


class WatchlistCreate(BaseModel):
    ticker: str
    nome: Optional[str] = None
    classe: str = "ACAO"
    mercado: str = "BR"


@router.get("/watchlist")
def listar_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo == True).all()
    return [{"id": i.id, "ticker": i.ticker, "nome": i.nome, "classe": i.classe, "mercado": i.mercado} for i in items]


@router.post("/watchlist")
def adicionar_watchlist(item: WatchlistCreate, db: Session = Depends(get_db)):
    ticker = item.ticker.upper()
    existente = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
    if existente:
        if existente.ativo:
            raise HTTPException(status_code=400, detail=f"{ticker} ja esta na watchlist")
        existente.ativo = True
        existente.nome = item.nome
        existente.classe = item.classe
        existente.mercado = item.mercado
        db.commit()
        return {"mensagem": f"{ticker} reativado na watchlist"}
    db.add(Watchlist(ticker=ticker, nome=item.nome, classe=item.classe, mercado=item.mercado))
    db.commit()
    return {"mensagem": f"{ticker} adicionado a watchlist"}


@router.delete("/watchlist/{ticker}")
def remover_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.query(Watchlist).filter(Watchlist.ticker == ticker.upper()).first()
    if item:
        item.ativo = False
        db.commit()
    return {"mensagem": f"{ticker.upper()} removido da watchlist"}
