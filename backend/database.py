from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./finboard.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── TABELAS ──────────────────────────────────────────────

class Ativo(Base):
    __tablename__ = "ativos"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    nome = Column(String)
    classe = Column(String)  # ACAO, FII, ETF_BR, ETF_EUA, TESOURO
    mercado = Column(String)  # BR, EUA
    quantidade = Column(Float, default=0)
    preco_medio = Column(Float, default=0)
    moeda = Column(String, default="BRL")
    data_compra = Column(Date, nullable=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)

class RendaFixa(Base):
    __tablename__ = "renda_fixa"
    id = Column(Integer, primary_key=True, index=True)
    emissor = Column(String, nullable=False)
    tipo = Column(String)  # CDB, LCI, LCA, LC
    indexador = Column(String)  # CDI, IPCA, PREFIXADO
    taxa_pct = Column(Float)
    vencimento = Column(Date)
    valor_aplicado = Column(Float)
    liquidez = Column(String)  # DIARIA, VENCIMENTO
    fgc = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)

class PrecoCache(Base):
    __tablename__ = "precos_cache"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    preco = Column(Float)
    variacao_dia = Column(Float)
    variacao_mes = Column(Float)
    volume = Column(Float, nullable=True)
    moeda = Column(String, default="BRL")
    fonte = Column(String)
    atualizado_em = Column(DateTime, default=datetime.now)

class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    score_valuation = Column(Float, nullable=True)
    score_momento = Column(Float, nullable=True)
    score_macro = Column(Float, nullable=True)
    score_final = Column(Float, nullable=True)
    regime_macro = Column(String, nullable=True)
    calculado_em = Column(DateTime, default=datetime.now)

class Alerta(Base):
    __tablename__ = "alertas"
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String)
    ticker = Column(String, nullable=True)
    mensagem = Column(Text)
    prioridade = Column(String, default="MEDIA")
    lido = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.now)

class Configuracao(Base):
    __tablename__ = "configuracoes"
    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String, unique=True)
    valor = Column(Text)
    atualizado_em = Column(DateTime, default=datetime.now)

class HistoricoAgente(Base):
    __tablename__ = "historico_agente"
    id = Column(Integer, primary_key=True, index=True)
    pergunta = Column(Text)
    resposta = Column(Text)
    criado_em = Column(DateTime, default=datetime.now)

# ── CRIAR TABELAS ────────────────────────────────────────

def criar_banco():
    Base.metadata.create_all(bind=engine)
    print("✓ Banco de dados criado com sucesso")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    criar_banco()
