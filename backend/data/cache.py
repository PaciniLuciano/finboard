import sqlite3
from datetime import datetime, timedelta
from backend.data.brapi import buscar_preco as buscar_preco_api

DB_PATH = "finboard.db"
TTL_MINUTOS = 15

def get_conn():
    return sqlite3.connect(DB_PATH)

def preco_em_cache(ticker: str) -> dict | None:
    """Verifica se há preço válido no cache (menos de 15 min)."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        limite = (datetime.now() - timedelta(minutes=TTL_MINUTOS)).isoformat()
        row = cursor.execute("""
            SELECT ticker, preco, variacao_dia, volume, moeda, fonte, atualizado_em
            FROM precos_cache
            WHERE ticker=? AND atualizado_em > ?
            ORDER BY atualizado_em DESC LIMIT 1
        """, (ticker, limite)).fetchone()
        conn.close()
        if row:
            return {
                "ticker": row[0],
                "preco": row[1],
                "variacao_dia": row[2],
                "volume": row[3],
                "moeda": row[4],
                "fonte": row[5] + "_cache",
                "atualizado_em": row[6],
                "cache": True
            }
        return None
    except:
        return None

def salvar_cache(ticker: str, dados: dict):
    """Salva preço no cache — UPSERT por ticker."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        values = (
            dados.get("preco"),
            dados.get("variacao_dia"),
            dados.get("volume"),
            dados.get("moeda", "BRL"),
            dados.get("fonte", "api"),
            now,
        )
        row = cursor.execute("SELECT id FROM precos_cache WHERE ticker=?", (ticker,)).fetchone()
        if row:
            cursor.execute("""
                UPDATE precos_cache
                SET preco=?, variacao_dia=?, volume=?, moeda=?, fonte=?, atualizado_em=?
                WHERE ticker=?
            """, (*values, ticker))
        else:
            cursor.execute("""
                INSERT INTO precos_cache (ticker, preco, variacao_dia, volume, moeda, fonte, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ticker, *values))
        conn.commit()
        conn.close()
    except:
        pass

def buscar_preco_com_cache(ticker: str, mercado: str = "BR") -> dict:
    """
    Busca preço com cache:
    1. Verifica cache (TTL 15 min)
    2. Se expirado ou inexistente, busca na API e salva
    """
    # Tenta cache primeiro
    cached = preco_em_cache(ticker)
    if cached:
        return cached

    # Cache miss — busca na API
    dados = buscar_preco_api(ticker, mercado)

    # Salva no cache se OK
    if "erro" not in dados and dados.get("preco"):
        salvar_cache(ticker, dados)

    return dados

def limpar_cache_antigo():
    """Remove entradas de cache com mais de 24 horas."""
    try:
        conn = get_conn()
        limite = (datetime.now() - timedelta(hours=24)).isoformat()
        conn.execute("DELETE FROM precos_cache WHERE atualizado_em < ?", (limite,))
        conn.commit()
        conn.close()
    except:
        pass

def invalidar_cache(ticker: str = None):
    """Invalida cache de um ticker ou de todos."""
    try:
        conn = get_conn()
        if ticker:
            conn.execute("DELETE FROM precos_cache WHERE ticker=?", (ticker,))
        else:
            conn.execute("DELETE FROM precos_cache")
        conn.commit()
        conn.close()
    except:
        pass




if __name__ == "__main__":
    print("Testando cache...\n")
    print("1a chamada:")
    r = buscar_preco_com_cache("PETR4")
    print(f"  PETR4: R$ " + str(r.get("preco")) + " - fonte: " + str(r.get("fonte")))
    print("\n2a chamada (cache):")
    r = buscar_preco_com_cache("PETR4")
    print(f"  Cache: " + str(r.get("cache", False)))
