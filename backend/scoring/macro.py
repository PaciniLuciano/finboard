import asyncio
import httpx
from datetime import datetime, timedelta
import time

BACEN_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

# Cache in-memory para dados macro — TTL 6h
_MACRO_TTL = 6 * 3600
_macro_cache: dict = {"resultado": None, "ts": 0.0}

def invalidar_cache_macro() -> None:
    _macro_cache["resultado"] = None
    _macro_cache["ts"] = 0.0

def _cache_macro_valido() -> bool:
    return (
        _macro_cache["resultado"] is not None
        and (time.monotonic() - _macro_cache["ts"]) < _MACRO_TTL
    )

async def buscar_selic() -> float:
    try:
        url = f"{BACEN_URL}.432/dados/ultimos/1?formato=json"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
            return float(data[0]["valor"])
    except:
        return 13.75

async def buscar_ipca_12m() -> float:
    try:
        url = f"{BACEN_URL}.13522/dados/ultimos/1?formato=json"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
            return float(data[0]["valor"])
    except:
        return 5.0

async def buscar_focus_selic() -> float | None:
    try:
        url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativaMercadoAnuais"
        params = {
            "$filter": "Indicador eq 'Selic' and DataReferencia eq '2026'",
            "$orderby": "Data desc",
            "$top": 1,
            "$format": "json",
            "$select": "Indicador,Data,Mediana,DataReferencia"
        }
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, timeout=10)
            data = r.json()
            if data.get("value"):
                return float(data["value"][0]["Mediana"])
        return None
    except:
        return None

async def calcular_regime_macro(forcar: bool = False) -> dict:
    if not forcar and _cache_macro_valido():
        return {**_macro_cache["resultado"], "cache": True}

    # Parallelize macro fetches
    selic_task = buscar_selic()
    ipca_task = buscar_ipca_12m()
    focus_task = buscar_focus_selic()
    
    selic, ipca, selic_esperada = await asyncio.gather(selic_task, ipca_task, focus_task)

    detalhes = {
        "selic_atual": selic,
        "ipca_12m": ipca,
        "juro_real": round(selic - ipca, 2),
        "focus_selic_esperada": selic_esperada
    }

    pontos_regime = 0

    if selic > 13:
        pontos_regime -= 2
    elif selic > 11:
        pontos_regime -= 1
    elif selic < 9:
        pontos_regime += 2
    else:
        pontos_regime += 1

    if selic_esperada:
        variacao = selic_esperada - selic
        if variacao < -1.5:
            pontos_regime += 2
        elif variacao < -0.5:
            pontos_regime += 1
        elif variacao > 0.5:
            pontos_regime -= 1

    if ipca < 4:
        pontos_regime += 1
    elif ipca > 6:
        pontos_regime -= 1

    if pontos_regime >= 2:
        regime = "AGRESSIVO"
    elif pontos_regime <= -1:
        regime = "DEFENSIVO"
    else:
        regime = "NEUTRO"

    if regime == "DEFENSIVO":
        scores = {
            "ACAO": 4.0, "FII_PAPEL": 8.5, "FII_TIJOLO": 4.0,
            "ETF_BR": 4.5, "ETF_EUA": 6.0,
            "TESOURO_IPCA": 9.0, "TESOURO_SELIC": 8.0, "CDB": 8.5,
        }
    elif regime == "NEUTRO":
        scores = {
            "ACAO": 6.0, "FII_PAPEL": 7.0, "FII_TIJOLO": 6.0,
            "ETF_BR": 6.0, "ETF_EUA": 6.5,
            "TESOURO_IPCA": 7.5, "TESOURO_SELIC": 6.5, "CDB": 7.0,
        }
    else:
        scores = {
            "ACAO": 8.5, "FII_PAPEL": 5.5, "FII_TIJOLO": 8.5,
            "ETF_BR": 8.0, "ETF_EUA": 7.5,
            "TESOURO_IPCA": 6.0, "TESOURO_SELIC": 4.5, "CDB": 5.0,
        }

    resultado = {
        "regime": regime,
        "pontos_regime": pontos_regime,
        "detalhes": detalhes,
        "scores_por_classe": scores,
        "calculado_em": datetime.now().isoformat(),
        "cache": False
    }
    _macro_cache["resultado"] = resultado
    _macro_cache["ts"] = time.monotonic()
    return resultado

async def get_score_macro(classe: str, macro_info: dict = None) -> float:
    if macro_info is None:
        macro_info = await calcular_regime_macro()
    scores = macro_info.get("scores_por_classe", {})
    mapa = {
        "ACAO": "ACAO", "FII": "FII_TIJOLO",
        "ETF_BR": "ETF_BR", "ETF_EUA": "ETF_EUA",
        "TESOURO": "TESOURO_IPCA", "CDB": "CDB",
    }
    return scores.get(mapa.get(classe, "ACAO"), 5.0)
