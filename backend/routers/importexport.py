import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db, Ativo, Watchlist

router = APIRouter()


def _df_para_resposta(df: pd.DataFrame, nome: str, formato: str) -> StreamingResponse:
    if formato == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nome}.xlsx"})
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
    df = pd.DataFrame([{
        "ticker": a.ticker, "nome": a.nome or "", "classe": a.classe,
        "mercado": a.mercado, "quantidade": a.quantidade,
        "preco_medio": a.preco_medio, "moeda": a.moeda,
        "data_compra": str(a.data_compra) if a.data_compra else "",
    } for a in ativos])
    return _df_para_resposta(df, "carteira", formato)


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
    ausentes = {"ticker", "classe", "quantidade", "preco_medio"} - set(df.columns)
    if ausentes:
        raise HTTPException(status_code=400, detail=f"Colunas obrigatórias ausentes: {ausentes}")

    importados, atualizados, erros = 0, 0, []
    for _, row in df.iterrows():
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
