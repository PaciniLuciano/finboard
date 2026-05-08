from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import criar_banco
from backend.scorer_job import iniciar_job

from backend.routers import (
    ativos, carteira, renda_fixa, mercado,
    watchlist, scoring, dividendos, importexport, config,
    premio_risco,
)

app = FastAPI(title="Finboard API", version="1.0.0")


@app.on_event("startup")
def startup():
    criar_banco()
    iniciar_job()
    print("✓ Finboard iniciado")


app.include_router(ativos.router)
app.include_router(carteira.router)
app.include_router(renda_fixa.router)
app.include_router(mercado.router)
app.include_router(watchlist.router)
app.include_router(scoring.router)
app.include_router(dividendos.router)
app.include_router(importexport.router)
app.include_router(config.router)
app.include_router(premio_risco.router)

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def home():
    return FileResponse("frontend/index.html")
