from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db, Ativo, RendaFixa
from backend.scoring.macro import calcular_regime_macro
from backend.scoring.premio_risco import calcular_premio

router = APIRouter()

_ORDEM_SINAL = {"ATRATIVO": 0, "NEUTRO": 1, "ABAIXO_CDI": 2,
                "SEM_DADO": 3, "N/A": 4, "ERRO": 5}


@router.get("/premio-risco")
def premio_risco(db: Session = Depends(get_db)):
    macro  = calcular_regime_macro()
    selic  = macro["detalhes"]["selic_atual"]
    ipca   = macro["detalhes"]["ipca_12m"]
    cdi    = round(selic - 0.1, 2)

    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(calcular_premio, a.ticker, a.classe, a.mercado, cdi)
            for a in ativos
        ]
        resultados = [f.result() for f in futures]

    # Renda Fixa — yield calculado diretamente da taxa cadastrada
    for rf in db.query(RendaFixa).filter(RendaFixa.ativo == True).all():
        if rf.indexador == "CDI":
            yield_ef = round(rf.taxa_pct / 100 * cdi, 2)
            yield_tipo = f"CDI × {rf.taxa_pct}%"
        elif rf.indexador == "IPCA":
            yield_ef = round(rf.taxa_pct + ipca, 2)
            yield_tipo = f"IPCA + {rf.taxa_pct}%"
        else:
            yield_ef = rf.taxa_pct
            yield_tipo = "prefixado"

        premio_cdi = round(yield_ef - cdi, 2)
        resultados.append({
            "ticker": rf.emissor,
            "classe": f"RF·{rf.tipo}",
            "yield_esperado": yield_ef,
            "yield_tipo": yield_tipo,
            "cdi": cdi,
            "benchmark": cdi,
            "premio_minimo": 0,
            "premio_cdi": premio_cdi,
            "gap": premio_cdi,
            "sinal": "ATRATIVO" if premio_cdi > 0 else "ABAIXO_CDI",
            "detalhes": {
                "taxa_pct": rf.taxa_pct,
                "indexador": rf.indexador,
                "vencimento": str(rf.vencimento),
            },
            "cache": False,
        })

    resultados.sort(
        key=lambda x: (_ORDEM_SINAL.get(x["sinal"], 9), -(x.get("gap") or -99))
    )

    resumo = {
        "atrativos":  sum(1 for r in resultados if r["sinal"] == "ATRATIVO"),
        "neutros":    sum(1 for r in resultados if r["sinal"] == "NEUTRO"),
        "abaixo_cdi": sum(1 for r in resultados if r["sinal"] == "ABAIXO_CDI"),
        "sem_dado":   sum(1 for r in resultados if r["sinal"] in ("SEM_DADO", "ERRO")),
    }

    return {
        "selic": selic,
        "cdi":   cdi,
        "ipca":  ipca,
        "ativos": resultados,
        "resumo": resumo,
    }
