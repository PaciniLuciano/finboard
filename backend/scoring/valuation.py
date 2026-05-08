import yfinance as yf
from datetime import datetime
from backend.scoring.utils import normalizar_dy

def calcular_valuation(ticker: str, classe: str = "ACAO", mercado: str = "BR") -> dict:
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker
        ativo = yf.Ticker(ticker_yf)
        info = ativo.info

        pontos = 0
        detalhes = {}
        max_pontos = 10

        if classe == "ACAO":
            pl = info.get("trailingPE") or info.get("forwardPE")
            if pl:
                pl = float(pl)
                detalhes["pl"] = round(pl, 2)
                if pl < 8: pontos += 3
                elif pl < 12: pontos += 2
                elif pl < 20: pontos += 1

            pvp = info.get("priceToBook")
            if pvp:
                pvp = float(pvp)
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 1: pontos += 2
                elif pvp < 2: pontos += 1

            dy = info.get("dividendYield")
            if dy:
                dy_pct = normalizar_dy(dy)
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 8: pontos += 2
                elif dy_pct > 4: pontos += 1

            roe = info.get("returnOnEquity")
            if roe:
                roe_pct = float(roe) * 100
                detalhes["roe"] = round(roe_pct, 2)
                if roe_pct > 20: pontos += 2
                elif roe_pct > 10: pontos += 1

            margem = info.get("profitMargins")
            if margem:
                detalhes["margem_liquida"] = round(float(margem) * 100, 2)
                if float(margem) * 100 > 10: pontos += 1

        elif classe == "FII":
            max_pontos = 8
            pvp = info.get("priceToBook")
            if pvp:
                pvp = float(pvp)
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 0.85: pontos += 4
                elif pvp < 0.95: pontos += 3
                elif pvp < 1.05: pontos += 2
                elif pvp < 1.15: pontos += 1

            dy = info.get("dividendYield")
            if dy:
                dy_pct = normalizar_dy(dy)
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 10: pontos += 4
                elif dy_pct > 8: pontos += 3
                elif dy_pct > 6: pontos += 2
                elif dy_pct > 4: pontos += 1

        elif classe in ["ETF_BR", "ETF_EUA"]:
            max_pontos = 6
            pl = info.get("trailingPE")
            if pl:
                pl = float(pl)
                detalhes["pl"] = round(pl, 2)
                if pl < 15: pontos += 3
                elif pl < 22: pontos += 2
                elif pl < 30: pontos += 1

            dy = info.get("dividendYield")
            if dy:
                dy_pct = normalizar_dy(dy)
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 3: pontos += 3
                elif dy_pct > 1.5: pontos += 2
                elif dy_pct > 0.5: pontos += 1

        score = round((pontos / max_pontos) * 10, 1) if max_pontos > 0 else 5.0

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
        return {"ticker": ticker, "score_valuation": 5.0, "erro": str(e)}
