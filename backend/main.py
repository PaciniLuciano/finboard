import logging

import backend.ssl_patch  # noqa: F401 — must be first, patches curl_cffi before yfinance loads

logging.basicConfig(level=logging.DEBUG)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import criar_banco
from backend.routers import (
    ativos,
    carteira,
    config,
    dividendos,
    importexport,
    mercado,
    premio_risco,
    renda_fixa,
    scoring,
    watchlist,
)
from backend.scorer_job import iniciar_job

app = FastAPI(title="Finboard API", version="1.0.0")


@app.on_event("startup")
def startup():
    # Forçar nível DEBUG nos loggers da app APÓS o uvicorn configurar os handlers
    import logging as _logging

    _logging.getLogger("backend").setLevel(_logging.DEBUG)
    criar_banco()
    iniciar_job()
    print("[OK] Finboard iniciado")


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
