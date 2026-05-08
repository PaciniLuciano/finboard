from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from backend.database import get_db, RendaFixa

router = APIRouter()


class RendaFixaCreate(BaseModel):
    emissor: str
    tipo: str
    indexador: str
    taxa_pct: float
    vencimento: date
    valor_aplicado: float
    liquidez: str = "VENCIMENTO"


@router.post("/renda-fixa")
def cadastrar_rf(rf: RendaFixaCreate, db: Session = Depends(get_db)):
    novo = RendaFixa(
        emissor=rf.emissor,
        tipo=rf.tipo,
        indexador=rf.indexador,
        taxa_pct=rf.taxa_pct,
        vencimento=rf.vencimento,
        valor_aplicado=rf.valor_aplicado,
        liquidez=rf.liquidez,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"mensagem": f"{rf.tipo} {rf.emissor} cadastrado com sucesso", "id": novo.id}


@router.get("/renda-fixa")
def listar_rf(db: Session = Depends(get_db)):
    return db.query(RendaFixa).filter(RendaFixa.ativo == True).all()
