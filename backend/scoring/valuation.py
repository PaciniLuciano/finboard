import asyncio
from datetime import datetime

import yfinance as yf

from backend.scoring.utils import normalizar_dy


def obter_selic_cache() -> float | None:
    """Reutiliza o cache de dados macro para obter Selic atual."""
    try:
        from backend.scoring.macro import _macro_cache

        resultado = _macro_cache.get("resultado")
        if resultado:
            return resultado.get("detalhes", {}).get("selic_atual")
    except Exception:
        pass
    return None


async def calcular_valuation(
    ticker: str,
    classe: str = "ACAO",
    mercado: str = "BR",
    setor: str | None = None,
    selic_atual: float | None = None,
) -> dict:
    try:
        ticker_yf = f"{ticker}.SA" if mercado == "BR" else ticker

        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, lambda: yf.Ticker(ticker_yf).info)

        pontos = 0
        detalhes = {}
        max_pontos = 10

        earnings_yield = None
        spread_selic = None
        roic_estimado = None
        selic_usada = None

        if classe == "ACAO":
            max_pontos = 14
            # Prioridade: parâmetro do engine → cache macro → fallback conservador
            selic = selic_atual if selic_atual is not None else (obter_selic_cache() or 13.75)
            selic_usada = selic

            pl = info.get("trailingPE") or info.get("forwardPE")
            if pl:
                pl = float(pl)
                detalhes["pl"] = round(pl, 2)
                if pl > 0:
                    ey = (1 / pl) * 100
                    spread = ey - selic
                    earnings_yield = round(ey, 2)
                    spread_selic = round(spread, 2)

                    if spread > 8:
                        pontos += 4
                    elif spread > 5:
                        pontos += 3
                    elif spread > 2:
                        pontos += 2
                    elif spread > 0:
                        pontos += 1

            pvp = info.get("priceToBook")
            if pvp:
                pvp = float(pvp)
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 1:
                    pontos += 2
                elif pvp < 2:
                    pontos += 1

            dy = info.get("dividendYield")
            if dy:
                dy_pct = normalizar_dy(dy)
                detalhes["dy"] = round(dy_pct, 2)
                # DY > 15% provavelmente é distorção, não pontua no máximo
                if 6 < dy_pct <= 15:
                    pontos += 2
                elif 3 < dy_pct <= 6:
                    pontos += 1
                elif dy_pct > 15:
                    pontos += 1

            roe = info.get("returnOnEquity")
            if roe:
                roe_pct = float(roe) * 100
                detalhes["roe"] = round(roe_pct, 2)
                if roe_pct > 20:
                    pontos += 2
                elif roe_pct > 10:
                    pontos += 1

            margem = info.get("profitMargins")
            if margem:
                detalhes["margem_liquida"] = round(float(margem) * 100, 2)
                if float(margem) * 100 > 10:
                    pontos += 1

            # ROIC estimado — bancos usam ROE como proxy (operatingIncome não aplicável)
            if setor == "BANCO":
                roe_raw = info.get("returnOnEquity")
                if roe_raw:
                    roe_proxy = float(roe_raw) * 100
                    roic_estimado = round(roe_proxy, 1)
                    detalhes["roic_estimado"] = roic_estimado
                    if roe_proxy > 20:
                        pontos += 3
                    elif roe_proxy > 15:
                        pontos += 2
                    elif roe_proxy > 10:
                        pontos += 1
            else:
                # Taxa de imposto estimada Brasil: 34%
                operating_income = info.get("operatingIncome") or 0
                total_debt = info.get("totalDebt") or 0
                stockholder_equity = info.get("totalStockholderEquity") or 0
                capital_investido = stockholder_equity + total_debt

                if capital_investido > 0 and operating_income > 0:
                    roic = (operating_income * (1 - 0.34)) / capital_investido * 100
                    roic_estimado = round(roic, 1)
                    detalhes["roic_estimado"] = roic_estimado
                    if roic > 20:
                        pontos += 3
                    elif roic > 15:
                        pontos += 2
                    elif roic > 10:
                        pontos += 1

        elif classe == "FII":
            max_pontos = 8
            pvp = info.get("priceToBook")
            if pvp:
                pvp = float(pvp)
                detalhes["pvp"] = round(pvp, 2)
                if pvp < 0.85:
                    pontos += 4
                elif pvp < 0.95:
                    pontos += 3
                elif pvp < 1.05:
                    pontos += 2
                elif pvp < 1.15:
                    pontos += 1

            # DY via histórico real — auto_adjust=False evita NaN em FIIs com dividendos mensais
            dy_pct = 0.0
            try:
                hist_fii = await loop.run_in_executor(
                    None,
                    lambda: yf.Ticker(ticker_yf).history(period="1y", auto_adjust=False),
                )
                if not hist_fii.empty:
                    divs = float(hist_fii["Dividends"].sum())
                    closes = hist_fii["Close"].dropna()
                    preco = float(closes.iloc[-1]) if not closes.empty else 0.0
                    if divs > 0 and preco > 0:
                        dy_pct = round((divs / preco) * 100, 2)
            except Exception:
                pass

            # Fallback para info["dividendYield"] se histórico retornou zero
            if dy_pct == 0.0:
                raw_dy = info.get("dividendYield")
                if raw_dy:
                    dy_pct = normalizar_dy(raw_dy)

            if dy_pct > 0:
                detalhes["dy"] = dy_pct
                if dy_pct > 10:
                    pontos += 4
                elif dy_pct > 8:
                    pontos += 3
                elif dy_pct > 6:
                    pontos += 2
                elif dy_pct > 4:
                    pontos += 1

        elif classe in ["ETF_BR", "ETF_EUA"]:
            max_pontos = 6
            pl = info.get("trailingPE")
            if pl:
                pl = float(pl)
                detalhes["pl"] = round(pl, 2)
                if pl < 15:
                    pontos += 3
                elif pl < 22:
                    pontos += 2
                elif pl < 30:
                    pontos += 1

            dy = info.get("dividendYield")
            if dy:
                dy_pct = normalizar_dy(dy)
                detalhes["dy"] = round(dy_pct, 2)
                if dy_pct > 3:
                    pontos += 3
                elif dy_pct > 1.5:
                    pontos += 2
                elif dy_pct > 0.5:
                    pontos += 1

        score = round((pontos / max_pontos) * 10, 1) if max_pontos > 0 else 5.0

        return {
            "ticker": ticker,
            "classe": classe,
            "score_valuation": score,
            "pontos_brutos": pontos,
            "max_pontos": max_pontos,
            "detalhes": detalhes,
            "earnings_yield": earnings_yield,
            "spread_selic": spread_selic,
            "roic_estimado": roic_estimado,
            "selic_usada": selic_usada,
            "calculado_em": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"ticker": ticker, "score_valuation": 5.0, "erro": str(e)}
