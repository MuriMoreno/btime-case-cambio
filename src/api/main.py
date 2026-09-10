"""
Ponto de montagem da API FastAPI: cria as tabelas, sobe o agendador no
lifespan, registra os routers e os dois handlers de erro globais.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infra.ambiente import preparar_ambiente
from src.persistencia.database import criar_tabelas
from src.agendador.scheduler import iniciar_agendador, parar_agendador
from src.api.dependencias import logger_api
from src.api.routers import itens, cotacoes, moedas, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    preparar_ambiente(logger_api)
    criar_tabelas()
    iniciar_agendador()
    yield
    parar_agendador()


app = FastAPI(
    title="btime - Monitor de Cotações",
    description=(
        "Monitora cotações PTAX do Banco Central ao longo do tempo: "
        "cadastro de itens (moedas), coleta automática/manual e consulta "
        "livre por período."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(itens.router)
app.include_router(cotacoes.router)
app.include_router(moedas.router)

# Frontend roda numa origem diferente (arquivo estático servido à parte, ou
# futuramente Lovable) - liberado para qualquer origem por ser um projeto
# de ambientação local. Num deploy real, restringir a origem exata.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def payload_invalido(request: Request, exc: RequestValidationError):
    # O desafio pede 400 para payload invalido; o FastAPI usa 422 por
    # padrao, entao sobrescrevemos so o status, mantendo o detalhe dos erros.
    # jsonable_encoder (em vez de passar exc.errors() cru pro JSONResponse):
    # quando um field_validator levanta ValueError (ex: e-mail invalido), o
    # Pydantic guarda a excecao crua em ctx.error - json.dumps direto quebra
    # nisso; jsonable_encoder sabe converter pra string.
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"detail": exc.errors()}),
    )


@app.exception_handler(Exception)
async def excecao_nao_tratada(request: Request, exc: Exception):
    logger_api.excecao(f"Excecao inesperada em {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno inesperado."},
    )
