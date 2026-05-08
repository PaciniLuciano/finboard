from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db, Ativo, RendaFixa
from backend.data.brapi import buscar_cambio_usd_brl
from backend.data.cache import buscar_preco_com_cache as buscar_preco

router = APIRouter()


@router.get("/carteira/resumo")
def resumo_carteira(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    rfs = db.query(RendaFixa).filter(RendaFixa.ativo == True).all()
    cambio = buscar_cambio_usd_brl()

    total_investido = 0
    total_atual = 0
    por_classe: dict = {}

    for a in ativos:
        preco_atual = buscar_preco(a.ticker, a.mercado)
        preco = preco_atual.get("preco") or a.preco_medio
        if a.mercado == "EUA":
            preco = preco * cambio

        valor_atual = preco * a.quantidade
        valor_investido = a.preco_medio * a.quantidade
        if a.mercado == "EUA":
            valor_investido = valor_investido * cambio

        total_investido += valor_investido
        total_atual += valor_atual
        por_classe[a.classe] = por_classe.get(a.classe, 0) + valor_atual

    for rf in rfs:
        total_investido += rf.valor_aplicado
        total_atual += rf.valor_aplicado
        por_classe["RF"] = por_classe.get("RF", 0) + rf.valor_aplicado

    retorno_total = ((total_atual - total_investido) / total_investido * 100) if total_investido > 0 else 0

    return {
        "patrimonio_total": round(total_atual, 2),
        "total_investido": round(total_investido, 2),
        "retorno_total_pct": round(retorno_total, 2),
        "retorno_total_rs": round(total_atual - total_investido, 2),
        "por_classe": {k: round(v, 2) for k, v in por_classe.items()},
        "cambio_usd_brl": cambio,
    }
