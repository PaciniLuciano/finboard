import yfinance as yf
from datetime import datetime

def calcular_valuation(ticker: str, classe: str = "ACAO", mercado: str = "BR") -> dict:
    """
    Calcula score de valuation para um ativo.
    Retorna score de 0 a 10.
    """
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        ativo = yf.Ticker(ticker_yf)
        info = ativo.info

        pontos = 0
        detalhes = {}
        max_pontos = 0

        # ── AÇÕES ─────────────────────────────────────────
        if classe == "ACAO":
            max_pontos = 10

            # P/L (0-3 pontos)
            pl = info.get("trailingPE") or info.get("forwardPE")
            if pl:
                detalhes["pl"] = round(pl, 2)
                if pl < 8:
                    pontos += 3
                elif pl < 12:
                    pontos += 2
                elif pl < 20:
                    pontos += 1

            # P/VP (0-2 pontos)
            pvp = info.get("priceToBook")
            if pvp:
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 1:
                    pontos += 2
                elif pvp < 2:
                    pontos += 1

            # Dividend Yield (0-2 pontos)
            dy = info.get("dividendYield")
            if dy:
                dy_pct = dy * 100
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 8:
                    pontos += 2
                elif dy_pct > 4:
                    pontos += 1

            # ROE (0-2 pontos)
            roe = info.get("returnOnEquity")
            if roe:
                roe_pct = roe * 100
                detalhes["roe"] = round(roe_pct, 2)
                if roe_pct > 20:
                    pontos += 2
                elif roe_pct > 10:
                    pontos += 1

            # Margem líquida (0-1 ponto)
            margem = info.get("profitMargins")
            if margem:
                margem_pct = margem * 100
                detalhes["margem_liquida"] = round(margem_pct, 2)
                if margem_pct > 10:
                    pontos += 1

        # ── FIIs ──────────────────────────────────────────
        elif classe == "FII":
            max_pontos = 8

            # P/VP (0-4 pontos) — métrica principal de FII
            pvp = info.get("priceToBook")
            if pvp:
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 0.85:
                    pontos += 4
                elif pvp < 0.95:
                    pontos += 3
                elif pvp < 1.05:
                    pontos += 2
                elif pvp < 1.15:
                    pontos += 1

            # Dividend Yield (0-4 pontos) — métrica principal de FII
            dy = info.get("dividendYield")
            if dy:
                dy_pct = dy * 100
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 10:
                    pontos += 4
                elif dy_pct > 8:
                    pontos += 3
                elif dy_pct > 6:
                    pontos += 2
                elif dy_pct > 4:
                    pontos += 1

        # ── ETFs ──────────────────────────────────────────
        elif classe in ["ETF_BR", "ETF_EUA"]:
            max_pontos = 6

            # P/L do índice (0-3 pontos)
            pl = info.get("trailingPE") or info.get("forwardPE")
            if pl:
                detalhes["pl"] = round(pl, 2)
                if pl < 15:
                    pontos += 3
                elif pl < 22:
                    pontos += 2
                elif pl < 30:
                    pontos += 1

            # DY (0-3 pontos)
            dy = info.get("dividendYield")
            if dy:
                dy_pct = dy * 100
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 3:
                    pontos += 3
                elif dy_pct > 1.5:
                    pontos += 2
                elif dy_pct > 0.5:
                    pontos += 1

        # Normaliza para 0-10
        if max_pontos == 0:
            score = 5.0
        else:
            score = round((pontos / max_pontos) * 10, 1)

        return {
            "ticker": ticker,
            "classe": classe,
            "score_valuation": score,
            "pontos_brutos": pontos,
            "max_pontos": max_pontos,
            "detalhes": detalhes,
            "calculado_em": datetime.now().isoformat()
        }

    except Exception as e:
        return {"ticker": ticker, "score_valuation": None, "erro": str(e)}


if __name__ == "__main__":
    print("Testando Score de Valuation...\n")

    testes = [
        ("PETR4", "ACAO", "BR"),
        ("VALE3", "ACAO", "BR"),
        ("ITUB4", "ACAO", "BR"),
        ("HGLG11", "FII", "BR"),
        ("MXRF11", "FII", "BR"),
    ]

    for ticker, classe, mercado in testes:
        r = calcular_valuation(ticker, classe, mercado)
        print(f"{ticker} ({classe}): Score {r.get('score_valuation')}")
        print(f"  Detalhes: {r.get('detalhes')}\n")
