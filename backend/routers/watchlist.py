from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.data.enrich import enriquecer_e_salvar
from backend.database import AtivoMaster, Watchlist, get_db

router = APIRouter()


class WatchlistCreate(BaseModel):
    ticker: str
    nome: str | None = None
    classe: str = "ACAO"
    mercado: str = "BR"


def _deve_enriquecer(ticker: str, db: Session) -> bool:
    try:
        master = db.query(AtivoMaster).filter(AtivoMaster.ticker == ticker).first()
        if not master or not master.ultima_atualizacao:
            return True
        ultima = date.fromisoformat(master.ultima_atualizacao)
        return (date.today() - ultima).days > 30
    except Exception:
        return True


@router.get("/watchlist")
def listar_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo).all()
    return [
        {"id": i.id, "ticker": i.ticker, "nome": i.nome, "classe": i.classe, "mercado": i.mercado}
        for i in items
    ]


@router.post("/watchlist")
def adicionar_watchlist(
    item: WatchlistCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
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
        if _deve_enriquecer(ticker, db):
            background_tasks.add_task(enriquecer_e_salvar, ticker, item.classe)
        return {"mensagem": f"{ticker} reativado na watchlist"}

    db.add(Watchlist(ticker=ticker, nome=item.nome, classe=item.classe, mercado=item.mercado))
    db.commit()

    if _deve_enriquecer(ticker, db):
        background_tasks.add_task(enriquecer_e_salvar, ticker, item.classe)

    return {"mensagem": f"{ticker} adicionado a watchlist"}


@router.delete("/watchlist/{ticker}")
def remover_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.query(Watchlist).filter(Watchlist.ticker == ticker.upper()).first()
    if item:
        item.ativo = False
        db.commit()
    return {"mensagem": f"{ticker.upper()} removido da watchlist"}
