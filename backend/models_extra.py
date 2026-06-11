from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from backend.database import Base


class ScoreCache(Base):
    __tablename__ = "scores_cache"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    origem = Column(String)
    classe = Column(String)
    mercado = Column(String)
    score_final = Column(Float)
    score_valuation = Column(Float)
    score_momento = Column(Float)
    score_macro = Column(Float)
    regime_macro = Column(String)
    sinal = Column(String)
    detalhes = Column(Text)
    earnings_yield = Column(Float)
    spread_selic = Column(Float)
    roic_estimado = Column(Float)
    sinal_oportunidade = Column(String)
    selic_usada = Column(Float)
    calculado_em = Column(DateTime, default=datetime.now)
