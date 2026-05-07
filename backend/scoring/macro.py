import requests
from datetime import datetime

BACEN_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

def buscar_selic() -> float:
    """Busca taxa Selic meta atual (% ao ano)."""
    try:
        # Série 432 = Selic meta definida pelo Copom (% a.a.)
        url = f"{BACEN_URL}.432/dados/ultimos/1?formato=json"
        r = requests.get(url, timeout=10)
        data = r.json()
        return float(data[0]["valor"])
    except:
        return 13.75

def buscar_ipca_12m() -> float:
    """Busca IPCA acumulado 12 meses."""
    try:
        # Série 13522 = IPCA acumulado 12 meses
        url = f"{BACEN_URL}.13522/dados/ultimos/1?formato=json"
        r = requests.get(url, timeout=10)
        data = r.json()
        return float(data[0]["valor"])
    except:
        return 5.0

def buscar_focus_selic() -> float | None:
    """Busca expectativa de Selic do Focus para fim do ano."""
    try:
        url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativaMercadoAnuais"
        params = {
            "$filter": "Indicador eq 'Selic' and DataReferencia eq '2026'",
            "$orderby": "Data desc",
            "$top": 1,
            "$format": "json",
            "$select": "Indicador,Data,Mediana,DataReferencia"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("value"):
            return float(data["value"][0]["Mediana"])
        return None
    except:
        return None

def calcular_regime_macro() -> dict:
    selic = buscar_selic()
    ipca = buscar_ipca_12m()
    selic_esperada = buscar_focus_selic()

    detalhes = {
        "selic_atual": selic,
        "ipca_12m": ipca,
        "juro_real": round(selic - ipca, 2),
        "focus_selic_esperada": selic_esperada
    }

    pontos_regime = 0

    # Selic alta = defensivo
    if selic > 13:
        pontos_regime -= 2
    elif selic > 11:
        pontos_regime -= 1
    elif selic < 9:
        pontos_regime += 2
    else:
        pontos_regime += 1

    # Focus: queda esperada = antecipa ciclo positivo
    if selic_esperada:
        variacao = selic_esperada - selic
        if variacao < -1.5:
            pontos_regime += 2
        elif variacao < -0.5:
            pontos_regime += 1
        elif variacao > 0.5:
            pontos_regime -= 1

    # IPCA
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

    return {
        "regime": regime,
        "pontos_regime": pontos_regime,
        "detalhes": detalhes,
        "scores_por_classe": scores,
        "calculado_em": datetime.now().isoformat()
    }

def get_score_macro(classe: str, macro_info: dict = None) -> float:
    if macro_info is None:
        macro_info = calcular_regime_macro()
    scores = macro_info.get("scores_por_classe", {})
    mapa = {
        "ACAO": "ACAO", "FII": "FII_TIJOLO",
        "ETF_BR": "ETF_BR", "ETF_EUA": "ETF_EUA",
        "TESOURO": "TESOURO_IPCA", "CDB": "CDB",
    }
    return scores.get(mapa.get(classe, "ACAO"), 5.0)

if __name__ == "__main__":
    print("Testando Score Macro...\n")
    macro = calcular_regime_macro()
    print(f"Regime:              {macro['regime']}")
    print(f"Selic atual:         {macro['detalhes']['selic_atual']}% a.a.")
    print(f"IPCA 12m:            {macro['detalhes']['ipca_12m']}%")
    print(f"Juro Real:           {macro['detalhes']['juro_real']}%")
    print(f"Focus Selic 2026:    {macro['detalhes']['focus_selic_esperada']}%")
    print(f"\nScores por classe:")
    for classe, score in macro['scores_por_classe'].items():
        print(f"  {classe}: {score}")
