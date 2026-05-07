import threading, time, json
from datetime import datetime
from backend.database import get_db, Ativo, Watchlist
from backend.models_extra import ScoreCache
from backend.scoring.engine import calcular_scores_carteira
from sqlalchemy import text

INTERVALO = 30 * 60  # 30 minutos

def calcular_sinal(score):
    if score >= 7: return "Forte"
    if score >= 5.5: return "Neutro"
    return "Fraco"

def atualizar_scores():
    print(f"[ScoreJob] Iniciando calculo: {datetime.now()}")
    db = next(get_db())
    try:
        # Carteira
        ativos = db.query(Ativo).filter(Ativo.ativo == True).all()
        lista = [{"ticker": a.ticker, "classe": a.classe, "mercado": a.mercado} for a in ativos]
        
        # Watchlist
        wl = db.query(Watchlist).filter(Watchlist.ativo == True).all()
        lista_wl = [{"ticker": r.ticker, "classe": r.classe, "mercado": r.mercado} for r in wl]

        for origem, lista_ativos in [("carteira", lista), ("watchlist", lista_wl)]:
            if not lista_ativos:
                continue
            scores = calcular_scores_carteira(lista_ativos)
            # Apaga cache anterior dessa origem
            db.execute(text(f"DELETE FROM scores_cache WHERE origem='{origem}'"))
            for s in scores:
                db.add(ScoreCache(
                    ticker=s["ticker"],
                    origem=origem,
                    classe=s["classe"],
                    mercado=s["mercado"],
                    score_final=s["score_final"],
                    score_valuation=s["score_valuation"],
                    score_momento=s["score_momento"],
                    score_macro=s["score_macro"],
                    regime_macro=s["regime_macro"],
                    sinal=calcular_sinal(s["score_final"]),
                    detalhes=json.dumps(s.get("detalhes_momento", {})),
                    calculado_em=datetime.now()
                ))
            db.commit()
            print(f"[ScoreJob] {origem}: {len(scores)} ativos salvos")
    except Exception as e:
        print(f"[ScoreJob] Erro: {e}")
    finally:
        db.close()

def iniciar_job():
    def loop():
        while True:
            atualizar_scores()
            time.sleep(INTERVALO)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("[ScoreJob] Job iniciado — intervalo 30min")
