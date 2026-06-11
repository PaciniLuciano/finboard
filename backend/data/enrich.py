import asyncio
import re
from datetime import date

import yfinance as yf


def _norm_yf(s: str) -> str:
    """Normaliza string do yfinance para o padrao do mapeamento.
    yfinance retorna 'Banks - Regional', o mapeamento usa 'Banks—Regional'.
    """
    if not s:
        return ""
    return re.sub(r"\s*-\s*", "—", s.strip())


MAPEAMENTO_SEGMENTO = {
    # Financeiro
    ("Financial Services", "Banks—Regional"): "BANCO_FINANCEIRO",
    ("Financial Services", "Banks—Diversified"): "BANCO_FINANCEIRO",
    ("Financial Services", "Insurance—Diversified"): "SEGURO_FINANCEIRO",
    ("Financial Services", "Insurance—Life"): "SEGURO_FINANCEIRO",
    ("Financial Services", "Asset Management"): "GESTAO_FINANCEIRA",
    # Energia / Utilities
    ("Utilities", "Utilities—Regulated Electric"): "ENERGIA_UTILITIES",
    ("Utilities", "Utilities—Diversified"): "ENERGIA_UTILITIES",
    ("Utilities", "Utilities—Regulated Water"): "SANEAMENTO",
    # Petroleo e Gas
    ("Energy", "Oil & Gas Integrated"): "PETROLEO_GAS",
    ("Energy", "Oil & Gas E&P"): "PETROLEO_GAS",
    ("Energy", "Oil & Gas Refining & Marketing"): "PETROLEO_GAS",
    # Mineracao / Siderurgia
    ("Basic Materials", "Steel"): "MINERACAO_SIDERURGIA",
    ("Basic Materials", "Other Industrial Metals & Mining"): "MINERACAO_SIDERURGIA",
    ("Basic Materials", "Copper"): "MINERACAO_SIDERURGIA",
    # Agro / Alimentos
    ("Consumer Defensive", "Farm Products"): "AGRO_ALIMENTOS",
    ("Consumer Defensive", "Packaged Foods"): "AGRO_ALIMENTOS",
    ("Consumer Defensive", "Beverages—Non-Alcoholic"): "AGRO_ALIMENTOS",
    # Varejo / Consumo
    ("Consumer Cyclical", "Apparel Retail"): "VAREJO_CONSUMO",
    ("Consumer Cyclical", "Department Stores"): "VAREJO_CONSUMO",
    ("Consumer Cyclical", "Specialty Retail"): "VAREJO_CONSUMO",
    ("Consumer Cyclical", "Home Improvement Retail"): "VAREJO_CONSUMO",
    # Construcao
    ("Consumer Cyclical", "Residential Construction"): "CONSTRUCAO_IMOBILIARIA",
    ("Real Estate", "Real Estate—Development"): "CONSTRUCAO_IMOBILIARIA",
    # Saude
    ("Healthcare", "Medical Care Facilities"): "SAUDE",
    ("Healthcare", "Diagnostics & Research"): "SAUDE",
    ("Healthcare", "Drug Manufacturers—Specialty & Generic"): "SAUDE",
    # Tecnologia
    ("Technology", "Software—Application"): "TECNOLOGIA",
    ("Technology", "Software—Infrastructure"): "TECNOLOGIA",
    ("Technology", "Information Technology Services"): "TECNOLOGIA",
    # Telecom
    ("Communication Services", "Telecom Services"): "TELECOMUNICACAO",
    # Industria / Transporte
    ("Industrials", "Airlines"): "TRANSPORTE_LOGISTICA",
    ("Industrials", "Railroads"): "TRANSPORTE_LOGISTICA",
    ("Industrials", "Trucking"): "TRANSPORTE_LOGISTICA",
    ("Industrials", "Engineering & Construction"): "INDUSTRIA",
    # Papel / Celulose
    ("Basic Materials", "Paper & Paper Products"): "PAPEL_CELULOSE",
    ("Basic Materials", "Forest Products"): "PAPEL_CELULOSE",
    # FIIs
    ("Real Estate", "REIT—Industrial"): "FII_TIJOLO_LOGISTICA",
    ("Real Estate", "REIT—Office"): "FII_TIJOLO_LAJES",
    ("Real Estate", "REIT—Retail"): "FII_TIJOLO_SHOPPING",
    ("Real Estate", "REIT—Mortgage"): "FII_PAPEL",
    ("Real Estate", "REIT—Diversified"): "FII_HIBRIDO",
}

FALLBACK_SETOR = {
    "Financial Services": "FINANCEIRO",
    "Energy": "ENERGIA_UTILITIES",
    "Basic Materials": "COMMODITIES",
    "Consumer Cyclical": "VAREJO_CONSUMO",
    "Consumer Defensive": "CONSUMO_BASICO",
    "Healthcare": "SAUDE",
    "Technology": "TECNOLOGIA",
    "Communication Services": "TELECOMUNICACAO",
    "Industrials": "INDUSTRIA",
    "Utilities": "ENERGIA_UTILITIES",
    "Real Estate": "FII_OUTROS",
}

FII_SEGMENTO_MANUAL = {
    "KNCR": "FII_PAPEL",
    "KNIP": "FII_PAPEL",
    "MXRF": "FII_PAPEL",
    "CPTS": "FII_PAPEL",
    "HCTR": "FII_PAPEL",
    "IRDM": "FII_PAPEL",
    "VGIR": "FII_PAPEL",
    "RBRR": "FII_PAPEL",
    "BBPO": "FII_PAPEL",
    "HGLG": "FII_TIJOLO_LOGISTICA",
    "BTLG": "FII_TIJOLO_LOGISTICA",
    "VILG": "FII_TIJOLO_LOGISTICA",
    "XPLG": "FII_TIJOLO_LOGISTICA",
    "LVBI": "FII_TIJOLO_LOGISTICA",
    "GZIT": "FII_TIJOLO_LOGISTICA",
    "BRCO": "FII_TIJOLO_LAJES",
    "BRCR": "FII_TIJOLO_LAJES",
    "PVBI": "FII_TIJOLO_LAJES",
    "RBRP": "FII_TIJOLO_LAJES",
    "HGRE": "FII_TIJOLO_LAJES",
    "JSRE": "FII_TIJOLO_LAJES",
    "HGBS": "FII_TIJOLO_SHOPPING",
    "XPML": "FII_TIJOLO_SHOPPING",
    "VISC": "FII_TIJOLO_SHOPPING",
    "MALL": "FII_TIJOLO_SHOPPING",
    "HFOF": "FII_HIBRIDO",
    "BCFF": "FII_HIBRIDO",
    "RBRF": "FII_HIBRIDO",
    "KFOF": "FII_HIBRIDO",
    "RURA": "FII_AGRO",
    "BTRA": "FII_AGRO",
}


async def enrich_ticker(ticker: str, classe: str) -> dict:
    today = date.today().isoformat()
    base = {
        "ticker": ticker,
        "nome": "N/D",
        "classe": classe,
        "segmento": "OUTROS",
        "setor_yf": "N/D",
        "industria_yf": "N/D",
        "pais": "N/D",
        "moeda": "N/D",
        "descricao": "N/D",
        "market_cap": None,
        "beta": None,
        "data_cadastro": today,
        "ultima_atualizacao": today,
    }

    try:
        ticker_yf = f"{ticker}.SA" if classe in ("ACAO", "FII", "ETF_BR") else ticker
        info = await asyncio.to_thread(lambda: yf.Ticker(ticker_yf).info)

        setor = info.get("sector") or ""
        industria = info.get("industry") or ""

        # Normaliza para comparacao com o mapeamento (yfinance usa hifen simples, mapeamento usa em-dash)
        setor_std = _norm_yf(setor)
        industria_std = _norm_yf(industria)

        if classe == "ETF_BR":
            segmento = "ETF_BR"
        elif classe == "ETF_EUA":
            segmento = "ETF_EUA"
        elif classe == "FII" and ticker in FII_SEGMENTO_MANUAL:
            segmento = FII_SEGMENTO_MANUAL[ticker]
        else:
            segmento = (
                MAPEAMENTO_SEGMENTO.get((setor_std, industria_std))
                or MAPEAMENTO_SEGMENTO.get((setor, industria))
                or FALLBACK_SETOR.get(setor)
                or "OUTROS"
            )

        pais = "BR" if classe in ("ACAO", "FII", "ETF_BR") else (info.get("country") or "N/D")
        moeda = info.get("currency") or ("BRL" if classe in ("ACAO", "FII", "ETF_BR") else "USD")
        descricao = info.get("longBusinessSummary") or "N/D"

        return {
            **base,
            "nome": info.get("longName") or info.get("shortName") or "N/D",
            "segmento": segmento,
            "setor_yf": setor or "N/D",
            "industria_yf": industria or "N/D",
            "pais": pais,
            "moeda": moeda,
            "descricao": descricao[:1000] if descricao != "N/D" else "N/D",
            "market_cap": info.get("marketCap"),
            "beta": info.get("beta"),
            "ultima_atualizacao": today,
        }

    except Exception as e:
        print(f"[Enrich] Falha ao buscar dados de {ticker}: {e}")
        return base


async def enriquecer_e_salvar(ticker: str, classe: str):
    """Enriquece via yfinance e faz upsert em ativos_master. Nunca levanta excecao."""
    try:
        dados = await enrich_ticker(ticker, classe)
        from backend.database import AtivoMaster, get_db

        db = next(get_db())
        try:
            existente = db.query(AtivoMaster).filter(AtivoMaster.ticker == ticker).first()
            if existente:
                for k, v in dados.items():
                    if k != "data_cadastro":
                        setattr(existente, k, v)
            else:
                db.add(AtivoMaster(**dados))
            db.commit()
            print(f"[Enrich] [OK] {ticker} — segmento: {dados.get('segmento')}")
        finally:
            db.close()
    except Exception as e:
        print(f"[Enrich] Erro ao salvar master de {ticker}: {e}")
