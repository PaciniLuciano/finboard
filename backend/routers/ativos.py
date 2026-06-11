import asyncio
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.data.brapi import buscar_cambio_usd_brl
from backend.data.cache import buscar_preco_com_cache as buscar_preco
from backend.data.cache import salvar_cache
from backend.data.enrich import enrich_ticker, enriquecer_e_salvar
from backend.database import Ativo, AtivoMaster, get_db

router = APIRouter()


class AtivoCreate(BaseModel):
    ticker: str
    nome: str | None = None
    classe: str
    mercado: str = "BR"
    quantidade: float
    preco_medio: float
    moeda: str = "BRL"
    data_compra: date | None = None


class NovaCompra(BaseModel):
    ticker: str
    quantidade: float
    preco: float


class Venda(BaseModel):
    ticker: str
    quantidade: float
    preco: float


class AtivoUpdate(BaseModel):
    nome: str | None = None
    classe: str | None = None
    mercado: str | None = None
    quantidade: float | None = None
    preco_medio: float | None = None
    moeda: str | None = None
    data_compra: date | None = None


def _deve_enriquecer(ticker: str, db: Session) -> bool:
    """Retorna True se o ticker precisa ser enriquecido (inexistente ou > 30 dias)."""
    try:
        master = db.query(AtivoMaster).filter(AtivoMaster.ticker == ticker).first()
        if not master or not master.ultima_atualizacao:
            return True
        ultima = date.fromisoformat(master.ultima_atualizacao)
        return (date.today() - ultima).days > 30
    except Exception:
        return True


# ── MASTER DATA ───────────────────────────────────────────


@router.get("/ativos/master")
def listar_master(db: Session = Depends(get_db)):
    registros = db.query(AtivoMaster).all()
    return [
        {
            "ticker": r.ticker,
            "nome": r.nome,
            "classe": r.classe,
            "segmento": r.segmento,
            "setor_yf": r.setor_yf,
            "industria_yf": r.industria_yf,
            "pais": r.pais,
            "moeda": r.moeda,
            "market_cap": r.market_cap,
            "beta": r.beta,
            "data_cadastro": r.data_cadastro,
            "ultima_atualizacao": r.ultima_atualizacao,
        }
        for r in registros
    ]


@router.get("/ativos/master/{ticker}")
def get_master(ticker: str, db: Session = Depends(get_db)):
    master = db.query(AtivoMaster).filter(AtivoMaster.ticker == ticker.upper()).first()
    if not master:
        raise HTTPException(
            status_code=404, detail=f"Master data de {ticker.upper()} nao encontrado"
        )
    return {
        "ticker": master.ticker,
        "nome": master.nome,
        "classe": master.classe,
        "segmento": master.segmento,
        "setor_yf": master.setor_yf,
        "industria_yf": master.industria_yf,
        "pais": master.pais,
        "moeda": master.moeda,
        "descricao": master.descricao,
        "market_cap": master.market_cap,
        "beta": master.beta,
        "data_cadastro": master.data_cadastro,
        "ultima_atualizacao": master.ultima_atualizacao,
    }


@router.post("/ativos/master/{ticker}/atualizar")
async def atualizar_master(ticker: str, classe: str = "ACAO", db: Session = Depends(get_db)):
    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker).first()
    if ativo:
        classe = ativo.classe
    else:
        from backend.database import Watchlist

        wl = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
        if wl:
            classe = wl.classe

    dados = await enrich_ticker(ticker, classe)
    existente = db.query(AtivoMaster).filter(AtivoMaster.ticker == ticker).first()
    if existente:
        for k, v in dados.items():
            if k != "data_cadastro":
                setattr(existente, k, v)
    else:
        db.add(AtivoMaster(**dados))
    db.commit()
    return dados


# ── CARTEIRA ──────────────────────────────────────────────


@router.post("/ativos")
def cadastrar_ativo(
    ativo: AtivoCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    ticker = ativo.ticker.upper()
    existente = db.query(Ativo).filter(Ativo.ticker == ticker).first()
    if existente:
        if not existente.ativo:
            existente.ativo = True
            existente.nome = ativo.nome
            existente.classe = ativo.classe
            existente.mercado = ativo.mercado
            existente.quantidade = ativo.quantidade
            existente.preco_medio = ativo.preco_medio
            existente.moeda = ativo.moeda
            existente.data_compra = ativo.data_compra
            db.commit()
            if _deve_enriquecer(ticker, db):
                background_tasks.add_task(enriquecer_e_salvar, ticker, ativo.classe)
            return {"mensagem": f"Ativo {ticker} reativado com sucesso", "id": existente.id}
        raise HTTPException(status_code=400, detail=f"Ticker {ticker} ja cadastrado")

    novo = Ativo(
        ticker=ticker,
        nome=ativo.nome,
        classe=ativo.classe,
        mercado=ativo.mercado,
        quantidade=ativo.quantidade,
        preco_medio=ativo.preco_medio,
        moeda=ativo.moeda,
        data_compra=ativo.data_compra,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    if _deve_enriquecer(ticker, db):
        background_tasks.add_task(enriquecer_e_salvar, ticker, ativo.classe)

    return {"mensagem": f"Ativo {ticker} cadastrado com sucesso", "id": novo.id}


@router.get("/ativos")
async def listar_ativos(db: Session = Depends(get_db)):
    ativos = db.query(Ativo).filter(Ativo.ativo).all()
    cambio = await buscar_cambio_usd_brl() or 5.0

    async def get_ativo_info(a):
        preco_atual = await buscar_preco(a.ticker, a.mercado)
        preco_usd = preco_atual.get("preco") or 0
        if a.classe == "FUNDO_INVEST" and preco_usd == 0:
            preco_usd = a.preco_medio or 0
        variacao = preco_atual.get("variacao_dia") or 0
        qtd = a.quantidade or 0
        pm = a.preco_medio or 0

        em_dolar = (a.moeda == "USD") or (a.mercado == "EUA")

        preco_atual_brl = preco_usd * cambio if a.mercado == "EUA" else preco_usd
        pm_brl = pm * cambio if em_dolar else pm

        valor_investido = pm_brl * qtd
        valor_atual = preco_atual_brl * qtd
        retorno_pct = ((preco_usd - pm) / pm * 100) if pm > 0 else 0

        return {
            "id": a.id,
            "ticker": a.ticker,
            "nome": a.nome,
            "classe": a.classe,
            "mercado": a.mercado,
            "quantidade": a.quantidade,
            "preco_medio": round(pm_brl, 2),
            "preco_atual": round(preco_atual_brl, 2),
            "variacao_dia": variacao,
            "valor_investido": round(valor_investido, 2),
            "valor_atual": round(valor_atual, 2),
            "retorno_pct": round(retorno_pct, 2),
            "retorno_rs": round(valor_atual - valor_investido, 2),
            "moeda": a.moeda,
            "cambio": round(cambio, 4) if em_dolar else None,
        }

    tasks = [get_ativo_info(a) for a in ativos]
    return await asyncio.gather(*tasks)


@router.patch("/ativos/{ticker}/preco")
def atualizar_preco_manual(ticker: str, preco_data: dict, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo nao encontrado")
    novo_preco = preco_data.get("preco")
    if novo_preco is None:
        raise HTTPException(status_code=400, detail="Preco nao informado")
    salvar_cache(ticker, {"preco": novo_preco, "fonte": "manual", "variacao_dia": 0})
    return {"mensagem": f"Preco de {ticker} atualizado para R$ {novo_preco}"}


@router.put("/ativos/{ticker}")
def editar_ativo(ticker: str, dados: AtivoUpdate, db: Session = Depends(get_db)):
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker.upper(), Ativo.ativo).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo nao encontrado")

    if dados.nome is not None:
        ativo.nome = dados.nome
    if dados.classe is not None:
        ativo.classe = dados.classe
    if dados.mercado is not None:
        ativo.mercado = dados.mercado
    if dados.quantidade is not None:
        ativo.quantidade = dados.quantidade
    if dados.preco_medio is not None:
        ativo.preco_medio = dados.preco_medio
    if dados.moeda is not None:
        ativo.moeda = dados.moeda
    if dados.data_compra is not None:
        ativo.data_compra = dados.data_compra

    db.commit()
    db.refresh(ativo)
    return {"mensagem": f"Ativo {ticker.upper()} atualizado", "id": ativo.id}


@router.delete("/ativos/{ticker}")
def remover_ativo(ticker: str, db: Session = Depends(get_db)):
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker.upper()).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo nao encontrado")
    ativo.ativo = False
    db.commit()
    return {"mensagem": f"Ativo {ticker.upper()} removido"}


@router.post("/ativos/compra")
def registrar_compra(compra: NovaCompra, db: Session = Depends(get_db)):
    ticker = compra.ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo).first()
    if not ativo:
        raise HTTPException(
            status_code=404, detail=f"Ativo {ticker} nao encontrado. Cadastre primeiro."
        )

    custo_atual = ativo.quantidade * ativo.preco_medio
    custo_novo = compra.quantidade * compra.preco
    nova_quantidade = ativo.quantidade + compra.quantidade
    novo_preco_medio = (custo_atual + custo_novo) / nova_quantidade

    qtd_anterior = ativo.quantidade
    pm_anterior = round(custo_atual / qtd_anterior, 2)

    ativo.quantidade = nova_quantidade
    ativo.preco_medio = round(novo_preco_medio, 4)
    db.commit()

    return {
        "mensagem": f"Compra registrada — {ticker}",
        "quantidade_anterior": qtd_anterior,
        "quantidade_nova": nova_quantidade,
        "preco_medio_anterior": pm_anterior,
        "preco_medio_novo": round(novo_preco_medio, 2),
        "custo_total": round(custo_atual + custo_novo, 2),
    }


@router.post("/ativos/venda")
def registrar_venda(venda: Venda, db: Session = Depends(get_db)):
    ticker = venda.ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo).first()
    if not ativo:
        raise HTTPException(status_code=404, detail=f"Ativo {ticker} nao encontrado.")

    if venda.quantidade > ativo.quantidade:
        raise HTTPException(
            status_code=400, detail=f"Quantidade insuficiente. Voce tem {ativo.quantidade} cotas."
        )

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
        "lucro_pct": round((venda.preco - ativo.preco_medio) / ativo.preco_medio * 100, 2),
    }
