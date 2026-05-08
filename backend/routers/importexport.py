import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db, Ativo, RendaFixa, Watchlist, Dividendo

router = APIRouter()


def _df_para_resposta(df: pd.DataFrame, nome: str, formato: str, extra_dfs: dict = None) -> StreamingResponse:
    if formato == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Carteira")
            if extra_dfs:
                for sheet_name, extra_df in extra_dfs.items():
                    extra_df.to_excel(writer, index=False, sheet_name=sheet_name)
        buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nome}.xlsx"})

    if extra_dfs:
        combined = df.copy()
        for _, extra_df in extra_dfs.items():
            combined = pd.concat([combined, extra_df], ignore_index=True, sort=False)
        df = combined
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome}.csv"})


def _ler_arquivo(arquivo_bytes: bytes, nome: str) -> pd.DataFrame:
    if nome.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(arquivo_bytes))
    return pd.read_csv(io.BytesIO(arquivo_bytes))


def _str(val, default=""):
    if pd.isna(val):
        return default
    return str(val).strip()


@router.get("/exportar/carteira")
def exportar_carteira(formato: str = "csv", db: Session = Depends(get_db)):
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
        "liquidez": "",
    } for a in ativos]

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
        "liquidez": rf.liquidez,
    } for rf in rfs]

    df_carteira = pd.DataFrame(dados_ativos + dados_rf)

    divs = db.query(Dividendo).all()
    df_divs = pd.DataFrame([{
        "secao": "DIVIDENDOS",
        "ticker": d.ticker,
        "valor_por_cota": d.valor_por_cota,
        "quantidade_cotas": d.quantidade_cotas,
        "valor_total": d.valor_total,
        "data_pagamento": str(d.data_pagamento) if d.data_pagamento else "",
        "tipo": d.tipo,
    } for d in divs])

    return _df_para_resposta(df_carteira, "finboard_export_completo", formato, extra_dfs={"Dividendos": df_divs})


@router.get("/exportar/watchlist")
def exportar_watchlist(formato: str = "csv", db: Session = Depends(get_db)):
    items = db.query(Watchlist).filter(Watchlist.ativo == True).all()
    df = pd.DataFrame([{
        "ticker": i.ticker, "nome": i.nome or "",
        "classe": i.classe, "mercado": i.mercado,
    } for i in items])
    return _df_para_resposta(df, "watchlist", formato)


@router.post("/importar/carteira")
async def importar_carteira(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    try:
        df = _ler_arquivo(conteudo, arquivo.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {e}")

    df.columns = df.columns.str.lower().str.strip()

    mapeamento = {
        "ticker/emissor": "ticker",
        "quantidade/valor": "quantidade",
        "preco_medio/taxa": "preco_medio",
        "data_compra/vencimento": "data_compra",
    }
    for col_nova, col_antiga in mapeamento.items():
        if col_nova in df.columns:
            if col_antiga in df.columns:
                df[col_antiga] = df[col_antiga].fillna(df[col_nova])
                df = df.drop(columns=[col_nova])
            else:
                df = df.rename(columns={col_nova: col_antiga})

    ausentes = {"ticker", "classe", "quantidade", "preco_medio"} - set(df.columns)
    if ausentes:
        raise HTTPException(status_code=400, detail=f"Colunas obrigatórias ausentes: {ausentes}")

    importados, atualizados, erros = 0, 0, []
    for _, row in df.iterrows():
        secao = _str(row.get("secao"), "VARIÁVEL").upper()

        if secao == "RENDA FIXA" or _str(row.get("classe")) == "RENDA_FIXA":
            emissor = _str(row.get("ticker"))
            if not emissor or emissor == "NAN":
                continue
            try:
                vencimento = None
                raw_venc = row.get("data_compra")
                if not pd.isna(raw_venc) and str(raw_venc).strip():
                    try:
                        vencimento = pd.to_datetime(raw_venc).date()
                    except Exception:
                        pass
                tipo = _str(row.get("nome"), "CDB")
                existente = db.query(RendaFixa).filter(
                    RendaFixa.emissor == emissor, RendaFixa.tipo == tipo
                ).first()
                if existente:
                    existente.ativo = True
                    existente.valor_aplicado = float(row["quantidade"])
                    existente.taxa_pct = float(row["preco_medio"])
                    existente.indexador = _str(row.get("indexador"), existente.indexador)
                    existente.liquidez = _str(row.get("liquidez"), existente.liquidez)
                    if vencimento:
                        existente.vencimento = vencimento
                    atualizados += 1
                else:
                    db.add(RendaFixa(
                        emissor=emissor,
                        tipo=tipo,
                        indexador=_str(row.get("indexador"), "CDI"),
                        taxa_pct=float(row["preco_medio"]),
                        vencimento=vencimento,
                        valor_aplicado=float(row["quantidade"]),
                        liquidez=_str(row.get("liquidez"), "VENCIMENTO"),
                    ))
                    importados += 1
            except Exception as e:
                erros.append(f"RF {emissor}: {e}")

        else:
            ticker = _str(row.get("ticker")).upper()
            if not ticker or ticker == "NAN":
                continue
            try:
                data_compra = None
                raw_data = row.get("data_compra")
                if not pd.isna(raw_data) and str(raw_data).strip():
                    try:
                        data_compra = pd.to_datetime(raw_data).date()
                    except Exception:
                        pass
                existente = db.query(Ativo).filter(Ativo.ticker == ticker).first()
                if existente:
                    existente.ativo = True
                    existente.quantidade  = float(row["quantidade"])
                    existente.preco_medio = float(row["preco_medio"])
                    existente.classe      = _str(row.get("classe"), existente.classe)
                    existente.mercado     = _str(row.get("mercado"), existente.mercado)
                    existente.nome        = _str(row.get("nome")) or existente.nome
                    if data_compra:
                        existente.data_compra = data_compra
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
                        data_compra=data_compra,
                    ))
                    importados += 1
            except Exception as e:
                erros.append(f"{ticker}: {e}")

    db.commit()
    return {"importados": importados, "atualizados": atualizados, "erros": erros}


@router.post("/importar/watchlist")
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
