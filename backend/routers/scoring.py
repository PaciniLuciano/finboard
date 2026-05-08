from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db, Ativo, Watchlist
from backend.scoring.engine import calcular_score_final, calcular_scores_carteira
from backend.scoring.macro import calcular_regime_macro, invalidar_cache_macro
from backend.models_extra import ScoreCache

router = APIRouter()


@router.get("/scoring/{ticker}")
def score_ativo(ticker: str, classe: str = "ACAO", mercado: str = "BR"):
    return calcular_score_final(ticker, classe, mercado)


@router.get("/scoring/carteira/todos")
def score_carteira(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    lista = [{"ticker": a.ticker, "classe": a.classe, "mercado": a.mercado} for a in ativos]
    if not lista:
        return []
    return calcular_scores_carteira(lista)


@router.get("/macro/regime")
def regime_macro(forcar: bool = False):
    return calcular_regime_macro(forcar=forcar)


@router.post("/macro/invalidar-cache")
def invalidar_macro():
    invalidar_cache_macro()
    return {"mensagem": "Cache macro invalidado"}


@router.get("/radar")
def radar(origem: str = "carteira", forcar: bool = False, db: Session = Depends(get_db)):
    from backend.scorer_job import atualizar_scores

    cache = db.query(ScoreCache).filter(ScoreCache.origem == origem).all()
    if forcar or not cache:
        atualizar_scores()
        cache = db.query(ScoreCache).filter(ScoreCache.origem == origem).all()

    macro = calcular_regime_macro()
    ativos = [{
        "ticker": s.ticker,
        "classe": s.classe,
        "mercado": s.mercado,
        "score_final": s.score_final,
        "score_valuation": s.score_valuation,
        "score_momento": s.score_momento,
        "score_macro": s.score_macro,
        "regime_macro": s.regime_macro,
        "sinal": s.sinal,
        "calculado_em": s.calculado_em.isoformat() if s.calculado_em else None,
    } for s in sorted(cache, key=lambda x: x.score_final, reverse=True)]

    return {
        "regime": macro["regime"],
        "selic": macro["detalhes"]["selic_atual"],
        "ipca": macro["detalhes"]["ipca_12m"],
        "juro_real": macro["detalhes"]["juro_real"],
        "ativos": ativos,
    }


@router.get("/radar/watchlist")
def radar_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo == True).all()
    lista = [{"ticker": i.ticker, "classe": i.classe, "mercado": i.mercado} for i in items]
    if not lista:
        return {"regime": "NEUTRO", "ativos": [], "fonte": "watchlist"}
    macro = calcular_regime_macro()
    scores = calcular_scores_carteira(lista)
    return {
        "regime": macro["regime"],
        "selic": macro["detalhes"]["selic_atual"],
        "ipca": macro["detalhes"]["ipca_12m"],
        "juro_real": macro["detalhes"]["juro_real"],
        "ativos": scores,
        "fonte": "watchlist",
    }
