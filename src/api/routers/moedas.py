"""
Lista as moedas que a PTAX aceita - alimenta o seletor de moeda do
frontend no cadastro de item, em vez do usuário digitar um código de cabeça.
"""

from fastapi import APIRouter, HTTPException

from src.api.schemas import MoedaOut
from src.api.dependencias import logger_api
from src.coletores.ptax_cliente import listar_moedas

router = APIRouter(prefix="/moedas", tags=["moedas"])


@router.get("", response_model=list[MoedaOut])
def listar():
    try:
        moedas = listar_moedas(logger_api)
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a PTAX: {erro}")

    return [
        MoedaOut(codigo=m.get("simbolo", ""), nome=m.get("nomeFormatado", ""))
        for m in moedas
    ]
