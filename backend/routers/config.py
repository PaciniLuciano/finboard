import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db, Configuracao

router = APIRouter()


class ConfigInput(BaseModel):
    selic_previsao_12m: Optional[float] = None
    selic_pessimista: Optional[float] = None
    selic_otimista: Optional[float] = None
    fonte_selic: str = "manual"


@router.get("/configuracoes")
def get_configuracoes(db: Session = Depends(get_db)):
    cfgs = db.query(Configuracao).all()
    resultado = {}
    for c in cfgs:
        try:
            resultado[c.chave] = json.loads(c.valor)
        except Exception:
            resultado[c.chave] = c.valor
    return resultado


@router.post("/configuracoes")
def salvar_configuracoes(cfg: ConfigInput, db: Session = Depends(get_db)):
    dados = {
        "selic_previsao_12m": cfg.selic_previsao_12m,
        "selic_pessimista": cfg.selic_pessimista,
        "selic_otimista": cfg.selic_otimista,
        "fonte_selic": cfg.fonte_selic,
    }
    for chave, valor in dados.items():
        if valor is not None:
            existente = db.query(Configuracao).filter(Configuracao.chave == chave).first()
            if existente:
                existente.valor = json.dumps(valor)
            else:
                db.add(Configuracao(chave=chave, valor=json.dumps(valor)))
    db.commit()
    return {"mensagem": "Configuracoes salvas com sucesso"}
