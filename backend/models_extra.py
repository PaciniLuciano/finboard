from backend.database import Base
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from datetime import datetime

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
    calculado_em = Column(DateTime, default=datetime.now)
