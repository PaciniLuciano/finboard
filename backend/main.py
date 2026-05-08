from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import os
import io
import pandas as pd

from backend.database import get_db, criar_banco, Ativo, RendaFixa, PrecoCache, Watchlist, Dividendo
from backend.data.brapi import buscar_multiplos, buscar_cambio_usd_brl, buscar_ibovespa
from backend.data.cache import buscar_preco_com_cache as buscar_preco

app = FastAPI(title="Finboard API", version="1.0.0")

from backend.scorer_job import iniciar_job
from backend.models_extra import ScoreCache

@app.on_event("startup")
def startup():
    criar_banco()
    iniciar_job()
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
        if existente.ativo == False:
            # Reativa e atualiza
            existente.ativo = True
            existente.nome = ativo.nome
            existente.classe = ativo.classe
            existente.mercado = ativo.mercado
            existente.quantidade = ativo.quantidade
            existente.preco_medio = ativo.preco_medio
            existente.moeda = ativo.moeda
            existente.data_compra = ativo.data_compra
            db.commit()
            return {"mensagem": f"Ativo {ativo.ticker.upper()} reativado com sucesso", "id": existente.id}
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
        
        # Fallback para FUNDO_INVEST se não houver preço no cache
        if a.classe == "FUNDO_INVEST" and preco == 0:
            preco = a.preco_medio or 0

        variacao = preco_atual.get("variacao_dia") or 0
        qtd = a.quantidade or 0
        pm = a.preco_medio or 0
        
        valor_atual = preco * qtd
        valor_investido = pm * qtd
        retorno_pct = ((preco - pm) / pm * 100) if pm > 0 else 0

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

@app.patch("/ativos/{ticker}/preco")
def atualizar_preco_manual(ticker: str, preco_data: dict, db: Session = Depends(get_db)):
    """Atualiza o preço de um ativo manualmente (útil para fundos não listados)."""
    from backend.data.cache import salvar_cache
    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    
    novo_preco = preco_data.get("preco")
    if novo_preco is None:
        raise HTTPException(status_code=400, detail="Preço não informado")
    
    # Salva no cache para refletir na listagem imediatamente
    salvar_cache(ticker, {"preco": novo_preco, "fonte": "manual", "variacao_dia": 0})
    
    return {"mensagem": f"Preço de {ticker} atualizado para R$ {novo_preco}"}

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
        preco = preco_atual.get("preco") or a.preco_medio or 0
        if a.mercado == "EUA":
            preco = preco * (cambio or 1)

        qtd = a.quantidade or 0
        pm = a.preco_medio or 0

        valor_atual = preco * qtd
        valor_investido = pm * qtd
        if a.mercado == "EUA":
            valor_investido = valor_investido * (cambio or 1)

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

# ── EXPORTAR ─────────────────────────────────────────────

def _df_para_resposta(df: pd.DataFrame, nome: str, formato: str, extra_dfs: dict = None) -> StreamingResponse:
    if formato == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Carteira")
            if extra_dfs:
                for sheet_name, extra_df in extra_dfs.items():
                    extra_df.to_excel(writer, index=False, sheet_name=sheet_name)
        buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nome}.xlsx"})
    
    # CSV: Se houver extra_dfs, concatena para "exportar tudo" no mesmo arquivo
    if extra_dfs:
        combined_df = df.copy()
        for sheet_name, extra_df in extra_dfs.items():
            # Adiciona uma coluna para identificar a seção no CSV combinado
            extra_df_tagged = extra_df.copy()
            combined_df = pd.concat([combined_df, extra_df_tagged], ignore_index=True, sort=False)
        df = combined_df

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome}.csv"})

@app.get("/exportar/carteira")
def exportar_carteira(formato: str = "csv", db: Session = Depends(get_db)):
    # Ativos Variáveis
    ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
    dados_ativos = [{
        "secao": "VARIÁVEL",
        "ticker/emissor": a.ticker,
        "nome": a.nome or "",
        "classe": a.classe,
        "mercado": a.mercado,
        "quantidade/valor": a.quantidade,
        "preco_medio/taxa": a.preco_medio,
        "moeda": a.moeda,
        "data_compra/vencimento": str(a.data_compra) if a.data_compra else "",
        "indexador": "",
        "liquidez": ""
    } for a in ativos]

    # Renda Fixa
    rfs = db.query(RendaFixa).filter(RendaFixa.ativo == True).all()
    dados_rf = [{
        "secao": "RENDA FIXA",
        "ticker/emissor": rf.emissor,
        "nome": rf.tipo,
        "classe": "RENDA_FIXA",
        "mercado": "BR",
        "quantidade/valor": rf.valor_aplicado,
        "preco_medio/taxa": rf.taxa_pct,
        "moeda": "BRL",
        "data_compra/vencimento": str(rf.vencimento) if rf.vencimento else "",
        "indexador": rf.indexador,
        "liquidez": rf.liquidez
    } for rf in rfs]

    df_carteira = pd.DataFrame(dados_ativos + dados_rf)

    # Dividendos
    divs = db.query(Dividendo).all()
    df_divs = pd.DataFrame([{
        "secao": "DIVIDENDOS",
        "ticker": d.ticker,
        "valor_por_cota": d.valor_por_cota,
        "quantidade_cotas": d.quantidade_cotas,
        "valor_total": d.valor_total,
        "data_pagamento": str(d.data_pagamento) if d.data_pagamento else "",
        "tipo": d.tipo
    } for d in divs])

    return _df_para_resposta(df_carteira, "finboard_export_completo", formato, extra_dfs={"Dividendos": df_divs})


@app.get("/exportar/watchlist")
def exportar_watchlist(formato: str = "csv", db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo == True).all()
    df = pd.DataFrame([{
        "ticker": i.ticker, "nome": i.nome or "",
        "classe": i.classe, "mercado": i.mercado,
    } for i in items])
    return _df_para_resposta(df, "watchlist", formato)

# ── IMPORTAR ─────────────────────────────────────────────

def _ler_arquivo(arquivo_bytes: bytes, nome: str) -> pd.DataFrame:
    if nome.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(arquivo_bytes))
    return pd.read_csv(io.BytesIO(arquivo_bytes))

def _str(val, default=""):
    if pd.isna(val): return default
    return str(val).strip()

@app.post("/importar/carteira")
async def importar_carteira(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    try:
        df = _ler_arquivo(conteudo, arquivo.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {e}")

    df.columns = df.columns.str.lower().str.strip()
    
    # Mapeamento de sinônimos para suportar o novo formato de exportação
    mapeamento = {
        "ticker/emissor": "ticker",
        "quantidade/valor": "quantidade",
        "preco_medio/taxa": "preco_medio",
        "data_compra/vencimento": "data_compra",
        "tipo_registro": "secao"
    }
    
    # Mescla colunas sinônimas se ambas existirem (evita erro de Series ambígua)
    for col_nova, col_antiga in mapeamento.items():
        if col_nova in df.columns:
            if col_antiga in df.columns:
                df[col_antiga] = df[col_antiga].fillna(df[col_nova])
                df = df.drop(columns=[col_nova])
            else:
                df = df.rename(columns={col_nova: col_antiga})

    obrigatorios = {"ticker", "classe", "quantidade", "preco_medio"}
    ausentes = obrigatorios - set(df.columns)
    if ausentes:
        raise HTTPException(status_code=400, detail=f"Colunas obrigatórias ausentes: {ausentes}")

    importados, atualizados, erros = 0, 0, []
    for _, row in df.iterrows():
        secao = _str(row.get("secao"), "VARIÁVEL").upper()
        
        # Lógica para VARIÁVEL (Ativos)
        if secao == "VARIÁVEL" or row.get("classe") != "RENDA_FIXA":
            ticker = _str(row.get("ticker")).upper()
            if not ticker or ticker == "NAN": continue
            try:
                data_compra = None
                raw_data = row.get("data_compra")
                if not pd.isna(raw_data) and str(raw_data).strip():
                    try: data_compra = pd.to_datetime(raw_data).date()
                    except: pass

                existente = db.query(Ativo).filter(Ativo.ticker == ticker).first()
                if existente:
                    existente.ativo = True
                    existente.quantidade  = float(row["quantidade"])
                    existente.preco_medio = float(row["preco_medio"])
                    existente.classe      = _str(row.get("classe"), existente.classe)
                    existente.mercado     = _str(row.get("mercado"), existente.mercado)
                    existente.nome        = _str(row.get("nome")) or existente.nome
                    if data_compra: existente.data_compra = data_compra
                    atualizados += 1
                else:
                    db.add(Ativo(
                        ticker=ticker,
                        nome=_str(row.get("nome")) or None,
                        classe=_str(row.get("classe"), "ACAO"),
                        mercado=_str(row.get("mercado"), "BR"),
                        quantidade=float(row["quantidade"]),
                        preco_medio=float(row["preco_medio"]),
                        moeda=_str(row.get("moeda"), "BRL"),
                        data_compra=data_compra
                    ))
                    importados += 1
            except Exception as e:
                erros.append(f"{ticker}: {e}")

        # Lógica para RENDA FIXA
        elif secao == "RENDA FIXA" or row.get("classe") == "RENDA_FIXA":
            emissor = _str(row.get("ticker")) # no rename virou ticker
            if not emissor or emissor == "NAN": continue
            try:
                vencimento = None
                raw_venc = row.get("data_compra") # no rename virou data_compra
                if not pd.isna(raw_venc) and str(raw_venc).strip():
                    try: vencimento = pd.to_datetime(raw_venc).date()
                    except: pass

                # Procura RF existente pelo emissor e tipo para evitar duplicidade
                tipo = _str(row.get("nome"), "CDB")
                existente = db.query(RendaFixa).filter(RendaFixa.emissor == emissor, RendaFixa.tipo == tipo).first()
                
                if existente:
                    existente.ativo = True
                    existente.valor_aplicado = float(row["quantidade"])
                    existente.taxa_pct = float(row["preco_medio"])
                    existente.indexador = _str(row.get("indexador"), existente.indexador)
                    existente.liquidez = _str(row.get("liquidez"), existente.liquidez)
                    if vencimento: existente.vencimento = vencimento
                    atualizados += 1
                else:
                    db.add(RendaFixa(
                        emissor=emissor,
                        tipo=tipo,
                        indexador=_str(row.get("indexador"), "CDI"),
                        taxa_pct=float(row["preco_medio"]),
                        vencimento=vencimento,
                        valor_aplicado=float(row["quantidade"]),
                        liquidez=_str(row.get("liquidez"), "VENCIMENTO")
                    ))
                    importados += 1
            except Exception as e:
                erros.append(f"RF {emissor}: {e}")

    db.commit()
    return {"importados": importados, "atualizados": atualizados, "erros": erros}


@app.post("/importar/watchlist")
async def importar_watchlist(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    try:
        df = _ler_arquivo(conteudo, arquivo.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {e}")

    df.columns = df.columns.str.lower().str.strip()
    if "ticker" not in df.columns:
        raise HTTPException(status_code=400, detail="Coluna 'ticker' obrigatória")

    importados, atualizados, erros = 0, 0, []
    for _, row in df.iterrows():
        ticker = _str(row.get("ticker")).upper()
        if not ticker or ticker == "NAN":
            continue
        try:
            existente = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
            if existente:
                existente.ativo   = True
                existente.classe  = _str(row.get("classe"), existente.classe or "ACAO")
                existente.mercado = _str(row.get("mercado"), existente.mercado or "BR")
                existente.nome    = _str(row.get("nome")) or existente.nome
                atualizados += 1
            else:
                db.add(Watchlist(
                    ticker=ticker,
                    nome=_str(row.get("nome")) or None,
                    classe=_str(row.get("classe"), "ACAO"),
                    mercado=_str(row.get("mercado"), "BR"),
                ))
                importados += 1
        except Exception as e:
            erros.append(f"{ticker}: {e}")

    db.commit()
    return {"importados": importados, "atualizados": atualizados, "erros": erros}

@app.get("/history/{ticker}")
def historico_ativo(ticker: str, mercado: str = "BR", periodo: str = "1y"):
    from backend.data.history import buscar_historico
    try:
        return buscar_historico(ticker, mercado, periodo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def home():
    return FileResponse("frontend/index.html")



from backend.scoring.engine import calcular_score_final, calcular_scores_carteira
from backend.scoring.macro import calcular_regime_macro, invalidar_cache_macro

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
def regime_macro(forcar: bool = False):
    """Retorna regime macro atual. Cache de 6h; use ?forcar=true para atualizar."""
    return calcular_regime_macro(forcar=forcar)

@app.post("/macro/invalidar-cache")
def invalidar_macro():
    """Força atualização do cache macro na próxima chamada."""
    invalidar_cache_macro()
    return {"mensagem": "Cache macro invalidado"}

@app.get("/radar")
def radar(origem: str = "carteira", forcar: bool = False, db: Session = Depends(get_db)):
    from backend.scorer_job import atualizar_scores
    from backend.scoring.macro import calcular_regime_macro

    # Se forcar=true ou cache vazio, recalcula agora
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
        "calculado_em": s.calculado_em.isoformat() if s.calculado_em else None
    } for s in sorted(cache, key=lambda x: x.score_final, reverse=True)]

    return {
        "regime": macro["regime"],
        "selic": macro["detalhes"]["selic_atual"],
        "ipca": macro["detalhes"]["ipca_12m"],
        "juro_real": macro["detalhes"]["juro_real"],
        "ativos": ativos
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

# ROTAS WATCHLIST

class WatchlistCreate(BaseModel):
    ticker: str
    nome: Optional[str] = None
    classe: str = "ACAO"
    mercado: str = "BR"

@app.get("/watchlist")
def listar_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo == True).all()
    return [{"id": i.id, "ticker": i.ticker, "nome": i.nome, "classe": i.classe, "mercado": i.mercado} for i in items]

@app.post("/watchlist")
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

@app.delete("/watchlist/{ticker}")
def remover_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.query(Watchlist).filter(Watchlist.ticker == ticker.upper()).first()
    if item:
        item.ativo = False
        db.commit()
    return {"mensagem": f"{ticker.upper()} removido da watchlist"}

@app.get("/radar/watchlist")
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
        "fonte": "watchlist"
    }

# ROTAS DIVIDENDOS
class DividendoCreate(BaseModel):
    ticker: str
    valor_por_cota: float
    quantidade_cotas: float
    data_pagamento: date
    tipo: str = "PROVENTO"

@app.post("/dividendos")
def registrar_dividendo(div: DividendoCreate, db: Session = Depends(get_db)):
    ticker = div.ticker.upper()
    valor_total = div.valor_por_cota * div.quantidade_cotas
    db.add(Dividendo(
        ticker=ticker,
        valor_por_cota=div.valor_por_cota,
        quantidade_cotas=div.quantidade_cotas,
        valor_total=valor_total,
        data_pagamento=div.data_pagamento,
        tipo=div.tipo
    ))
    db.commit()
    return {"mensagem": f"Dividendo de {ticker} registrado", "valor_total": round(valor_total, 2)}

@app.get("/dividendos/{ticker}")
def listar_dividendos(ticker: str, db: Session = Depends(get_db)):
    from sqlalchemy import desc
    items = db.query(Dividendo).filter(Dividendo.ticker == ticker.upper()).order_by(desc(Dividendo.data_pagamento)).all()
    return [{"id": i.id, "ticker": i.ticker, "valor_por_cota": i.valor_por_cota, "quantidade_cotas": i.quantidade_cotas,
             "valor_total": i.valor_total, "data_pagamento": str(i.data_pagamento), "tipo": i.tipo} for i in items]

@app.get("/dividendos")
def listar_todos_dividendos(db: Session = Depends(get_db)):
    from sqlalchemy import desc
    items = db.query(Dividendo).order_by(desc(Dividendo.data_pagamento)).all()
    return [{"id": i.id, "ticker": i.ticker, "valor_por_cota": i.valor_por_cota, "quantidade_cotas": i.quantidade_cotas,
             "valor_total": i.valor_total, "data_pagamento": str(i.data_pagamento), "tipo": i.tipo} for i in items]

@app.get("/retorno-total/{ticker}")
def retorno_total(ticker: str, db: Session = Depends(get_db)):
    """Retorna retorno completo: valorização + dividendos recebidos."""
    from sqlalchemy import text
    ticker = ticker.upper()

    # Busca ativo
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")

    # Busca dividendos
    from sqlalchemy import func
    result = db.query(func.sum(Dividendo.valor_total), func.count(Dividendo.id)).filter(Dividendo.ticker == ticker).one()
    total_dividendos = result[0] or 0
    qtd_proventos = result[1] or 0

    # Preço atual
    preco_atual = buscar_preco(ativo.ticker, ativo.mercado)
    preco = preco_atual.get("preco") or ativo.preco_medio

    valor_atual = preco * ativo.quantidade
    valor_investido = ativo.preco_medio * ativo.quantidade

    retorno_cota = valor_atual - valor_investido
    retorno_cota_pct = (retorno_cota / valor_investido * 100) if valor_investido > 0 else 0

    dy_pct = (total_dividendos / valor_investido * 100) if valor_investido > 0 else 0

    retorno_total_rs = retorno_cota + total_dividendos
    retorno_total_pct = retorno_cota_pct + dy_pct

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
        "retorno_total_rs": round(retorno_total_rs, 2),
        "retorno_total_pct": round(retorno_total_pct, 2),
        "qtd_proventos": qtd_proventos
    }

# IMPORTACAO AUTOMATICA DE DIVIDENDOS
@app.post("/dividendos/importar/{ticker}")
def importar_dividendos(ticker: str, db: Session = Depends(get_db)):
    """Importa automaticamente dividendos via yfinance desde a data de compra."""
    import yfinance as yf
    from datetime import date as date_type

    ticker = ticker.upper()
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker, Ativo.ativo == True).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado na carteira")

    try:
        ticker_yf = f"{ticker}.SA" if ativo.mercado == "BR" else ticker
        yf_ativo = yf.Ticker(ticker_yf)
        divs = yf_ativo.dividends

        if divs.empty:
            return {"mensagem": "Nenhum dividendo encontrado", "importados": 0}

        if ativo.data_compra:
            divs = divs[divs.index >= str(ativo.data_compra)]

        importados = 0
        ignorados = 0

        for data, valor in divs.items():
            data_str = str(data)[:10]  # YYYY-MM-DD
            data_obj = date_type.fromisoformat(data_str)

            existente = db.query(Dividendo).filter(
                Dividendo.ticker == ticker,
                Dividendo.data_pagamento == data_obj
            ).first()

            if existente:
                ignorados += 1
                continue

            valor_total = float(valor) * ativo.quantidade
            db.add(Dividendo(
                ticker=ticker,
                valor_por_cota=float(valor),
                quantidade_cotas=ativo.quantidade,
                valor_total=valor_total,
                data_pagamento=data_obj,
                tipo="AUTO"
            ))
            importados += 1

        db.commit()
        return {
            "mensagem": f"{ticker} — {importados} proventos importados",
            "importados": importados,
            "ignorados": ignorados,
            "quantidade_cotas": ativo.quantidade
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dividendos/importar-todos")
def importar_todos_dividendos(db: Session = Depends(get_db)):
    """Importa dividendos de todos os ativos da carteira."""
    import yfinance as yf
    from datetime import date as date_type

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
                data_obj = date_type.fromisoformat(str(data)[:10])
                existente = db.query(Dividendo).filter(
                    Dividendo.ticker == ativo.ticker,
                    Dividendo.data_pagamento == data_obj
                ).first()
                if existente:
                    continue
                valor_total = float(valor) * ativo.quantidade
                db.add(Dividendo(
                    ticker=ativo.ticker,
                    valor_por_cota=float(valor),
                    quantidade_cotas=ativo.quantidade,
                    valor_total=valor_total,
                    data_pagamento=data_obj,
                    tipo="AUTO"
                ))
                importados += 1
            db.commit()
            if importados > 0:
                resultados.append({"ticker": ativo.ticker, "importados": importados})
        except:
            continue
    return {"mensagem": "Importação concluída", "resultados": resultados}
