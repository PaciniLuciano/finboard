from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import os

from backend.database import get_db, criar_banco, Ativo, RendaFixa, PrecoCache
from backend.data.brapi import buscar_preco, buscar_multiplos, buscar_cambio_usd_brl, buscar_ibovespa

app = FastAPI(title="Finboard API", version="1.0.0")


@app.on_event("startup")
def startup():
    criar_banco()
    print("✓ Finboard iniciado")


class AtivoCreate(BaseModel):
    ticker: str
    nome: Optional[str] = None
    classe: str  # ACAO, FII, ETF_BR, ETF_EUA, TESOURO
    mercado: str = "BR"
    quantidade: float
    preco_medio: float
    moeda: str = "BRL"
    data_compra: Optional[date] = None

class RendaFixaCreate(BaseModel):
    emissor: str
    tipo: str  # CDB, LCI, LCA, LC
    indexador: str  # CDI, IPCA, PREFIXADO
    taxa_pct: float
    vencimento: date
    valor_aplicado: float
    liquidez: str = "VENCIMENTO"


@app.post("/ativos")
def cadastrar_ativo(ativo: AtivoCreate, db: Session = Depends(get_db)):
    existente = db.query(Ativo).filter(Ativo.ticker == ativo.ticker.upper()).first()
    if existente:
        raise HTTPException(status_code=400, detail=f"Ticker {ativo.ticker} já cadastrado")

    novo = Ativo(
        ticker=ativo.ticker.upper(),
        nome=ativo.nome,
        classe=ativo.classe,
        mercado=ativo.mercado,
        quantidade=ativo.quantidade,
        preco_medio=ativo.preco_medio,
        moeda=ativo.moeda,
        data_compra=ativo.data_compra
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"mensagem": f"Ativo {ativo.ticker.upper()} cadastrado com sucesso", "id": novo.id}

@app.get("/ativos")
def listar_ativos(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    resultado = []
    for a in ativos:
        preco_atual = buscar_preco(a.ticker, a.mercado)
        preco = preco_atual.get("preco") or 0
        variacao = preco_atual.get("variacao_dia") or 0
        valor_atual = preco * a.quantidade
        valor_investido = a.preco_medio * a.quantidade
        retorno_pct = ((preco - a.preco_medio) / a.preco_medio * 100) if a.preco_medio > 0 else 0

        resultado.append({
            "id": a.id,
            "ticker": a.ticker,
            "nome": a.nome,
            "classe": a.classe,
            "mercado": a.mercado,
            "quantidade": a.quantidade,
            "preco_medio": a.preco_medio,
            "preco_atual": preco,
            "variacao_dia": variacao,
            "valor_investido": round(valor_investido, 2),
            "valor_atual": round(valor_atual, 2),
            "retorno_pct": round(retorno_pct, 2),
            "retorno_rs": round(valor_atual - valor_investido, 2),
            "moeda": a.moeda
        })
    return resultado

@app.delete("/ativos/{ticker}")
def remover_ativo(ticker: str, db: Session = Depends(get_db)):
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker.upper()).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    ativo.ativo = False
    db.commit()
    return {"mensagem": f"Ativo {ticker.upper()} removido"}


@app.post("/renda-fixa")
def cadastrar_rf(rf: RendaFixaCreate, db: Session = Depends(get_db)):
    novo = RendaFixa(
        emissor=rf.emissor,
        tipo=rf.tipo,
        indexador=rf.indexador,
        taxa_pct=rf.taxa_pct,
        vencimento=rf.vencimento,
        valor_aplicado=rf.valor_aplicado,
        liquidez=rf.liquidez
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"mensagem": f"{rf.tipo} {rf.emissor} cadastrado com sucesso", "id": novo.id}

@app.get("/renda-fixa")
def listar_rf(db: Session = Depends(get_db)):
    itens = db.query(RendaFixa).filter(RendaFixa.ativo == True).all()
    return itens


@app.get("/mercado/preco/{ticker}")
def preco_ativo(ticker: str, mercado: str = "BR"):
    return buscar_preco(ticker, mercado)

@app.get("/mercado/ibovespa")
def ibovespa():
    return buscar_ibovespa()

@app.get("/mercado/cambio")
def cambio():
    return {"usd_brl": buscar_cambio_usd_brl()}


@app.get("/carteira/resumo")
def resumo_carteira(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    rfs = db.query(RendaFixa).filter(RendaFixa.ativo == True).all()
    cambio = buscar_cambio_usd_brl()

    total_investido = 0
    total_atual = 0
    por_classe = {}

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

        classe = a.classe
        if classe not in por_classe:
            por_classe[classe] = 0
        por_classe[classe] += valor_atual

    for rf in rfs:
        total_investido += rf.valor_aplicado
        total_atual += rf.valor_aplicado
        if "RF" not in por_classe:
            por_classe["RF"] = 0
        por_classe["RF"] += rf.valor_aplicado

    retorno_total = ((total_atual - total_investido) / total_investido * 100) if total_investido > 0 else 0

    return {
        "patrimonio_total": round(total_atual, 2),
        "total_investido": round(total_investido, 2),
        "retorno_total_pct": round(retorno_total, 2),
        "retorno_total_rs": round(total_atual - total_investido, 2),
        "por_classe": {k: round(v, 2) for k, v in por_classe.items()},
        "cambio_usd_brl": cambio
    }

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def home():
    return FileResponse("frontend/index.html")



from backend.scoring.engine import calcular_score_final, calcular_scores_carteira
from backend.scoring.macro import calcular_regime_macro

@app.get("/scoring/{ticker}")
def score_ativo(ticker: str, classe: str = "ACAO", mercado: str = "BR"):
    """Calcula score triplo para um ativo."""
    return calcular_score_final(ticker, classe, mercado)

@app.get("/scoring/carteira/todos")
def score_carteira(db: Session = Depends(get_db)):
    """Calcula score de todos os ativos da carteira."""
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    lista = [{"ticker": a.ticker, "classe": a.classe, "mercado": a.mercado} for a in ativos]
    if not lista:
        return []
    return calcular_scores_carteira(lista)

@app.get("/macro/regime")
def regime_macro():
    """Retorna regime macro atual."""
    return calcular_regime_macro()

@app.get("/radar")
def radar(db: Session = Depends(get_db)):
    """
    Radar de oportunidades — analisa ativos da carteira
    e retorna ordenados por score final.
    """
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    lista = [{"ticker": a.ticker, "classe": a.classe, "mercado": a.mercado} for a in ativos]
    if not lista:
        return {"regime": "NEUTRO", "ativos": []}
    
    macro = calcular_regime_macro()
    scores = calcular_scores_carteira(lista)
    
    return {
        "regime": macro["regime"],
        "selic": macro["detalhes"]["selic_atual"],
        "ipca": macro["detalhes"]["ipca_12m"],
        "juro_real": macro["detalhes"]["juro_real"],
        "ativos": scores
    }

# ROTAS CONFIGURACOES
from pydantic import BaseModel as BM
class ConfigInput(BM):
    selic_previsao_12m: float = None
    selic_pessimista: float = None
    selic_otimista: float = None
    fonte_selic: str = "manual"

@app.get("/configuracoes")
def get_configuracoes(db: Session = Depends(get_db)):
    from backend.database import Configuracao
    import json
    cfgs = db.query(Configuracao).all()
    resultado = {}
    for c in cfgs:
        try:
            resultado[c.chave] = json.loads(c.valor)
        except:
            resultado[c.chave] = c.valor
    return resultado

@app.post("/configuracoes")
def salvar_configuracoes(cfg: ConfigInput, db: Session = Depends(get_db)):
    from backend.database import Configuracao
    import json
    dados = {
        "selic_previsao_12m": cfg.selic_previsao_12m,
        "selic_pessimista": cfg.selic_pessimista,
        "selic_otimista": cfg.selic_otimista,
        "fonte_selic": cfg.fonte_selic
    }
    for chave, valor in dados.items():
        if valor is not None:
            existente = db.query(Configuracao).filter(Configuracao.chave == chave).first()
            if existente:
                existente.valor = json.dumps(valor)
            else:
                db.add(Configuracao(chave=chave, valor=json.dumps(valor)))
    db.commit()
    return {"mensagem": "Configuracoes salvas com sucesso"}

# ROTAS OPERACOES
class NovaCompra(BaseModel):
    ticker: str
    quantidade: float
    preco: float

class Venda(BaseModel):
    ticker: str
    quantidade: float
    preco: float

@app.post("/ativos/compra")
def registrar_compra(compra: NovaCompra, db: Session = Depends(get_db)):
    ticker = compra.ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()

    if not ativo:
        raise HTTPException(status_code=404, detail=f"Ativo {ticker} nao encontrado. Cadastre primeiro.")

    # Calcula novo preco medio ponderado
    custo_atual = ativo.quantidade * ativo.preco_medio
    custo_novo = compra.quantidade * compra.preco
    nova_quantidade = ativo.quantidade + compra.quantidade
    novo_preco_medio = (custo_atual + custo_novo) / nova_quantidade

    ativo.quantidade = nova_quantidade
    ativo.preco_medio = round(novo_preco_medio, 4)
    db.commit()

    return {
        "mensagem": f"Compra registrada — {ticker}",
        "quantidade_anterior": ativo.quantidade - compra.quantidade,
        "quantidade_nova": nova_quantidade,
        "preco_medio_anterior": round((custo_atual) / (ativo.quantidade - compra.quantidade), 2),
        "preco_medio_novo": round(novo_preco_medio, 2),
        "custo_total": round(custo_atual + custo_novo, 2)
    }

@app.post("/ativos/venda")
def registrar_venda(venda: Venda, db: Session = Depends(get_db)):
    ticker = venda.ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()

    if not ativo:
        raise HTTPException(status_code=404, detail=f"Ativo {ticker} nao encontrado.")

    if venda.quantidade > ativo.quantidade:
        raise HTTPException(status_code=400, detail=f"Quantidade insuficiente. Voce tem {ativo.quantidade} cotas.")

    lucro = (venda.preco - ativo.preco_medio) * venda.quantidade
    nova_quantidade = ativo.quantidade - venda.quantidade

    if nova_quantidade == 0:
        ativo.ativo = False
        mensagem = f"{ticker} totalmente vendido e removido da carteira"
    else:
        ativo.quantidade = nova_quantidade
        mensagem = f"Venda registrada — {ticker}"

    db.commit()

    return {
        "mensagem": mensagem,
        "quantidade_vendida": venda.quantidade,
        "quantidade_restante": nova_quantidade,
        "preco_medio": ativo.preco_medio,
        "preco_venda": venda.preco,
        "lucro_realizado": round(lucro, 2),
        "lucro_pct": round((venda.preco - ativo.preco_medio) / ativo.preco_medio * 100, 2)
    }
