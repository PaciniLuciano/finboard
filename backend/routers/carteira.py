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
    cambio = buscar_cambio_usd_brl() or 5.0

    t_investido = 0.0
    t_atual = 0.0
    por_classe: dict = {}

    for a in ativos:
        p_atual = buscar_preco(a.ticker, a.mercado).get("preco") or a.preco_medio or 0
        qtd = a.quantidade or 0
        pm = a.preco_medio or 0
        v_invest = pm * qtd
        v_atual = p_atual * qtd
        if a.mercado == "EUA":
            v_invest *= cambio
            v_atual *= cambio
        t_investido += v_invest
        t_atual += v_atual
        classe = a.classe or "OUTROS"
        por_classe[classe] = por_classe.get(classe, 0) + v_atual

    for rf in rfs:
        valor = rf.valor_aplicado or 0
        t_investido += valor
        t_atual += valor
        por_classe["RENDA_FIXA"] = por_classe.get("RENDA_FIXA", 0) + valor

    return {
        "patrimonio_total": round(t_atual, 2),
        "total_investido": round(t_investido, 2),
        "lucro_prejuizo": round(t_atual - t_investido, 2),
        "retorno_pct": round((t_atual / t_investido - 1) * 100, 2) if t_investido > 0 else 0,
        "por_classe": {k: round(v, 2) for k, v in por_classe.items()},
        "cambio_usd_brl": round(cambio, 4),
    }
