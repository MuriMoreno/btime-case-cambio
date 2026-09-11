"""
Conversão de moedas: calcula quanto um valor numa moeda vale em outra,
usando a cotação PTAX mais recente de cada uma como ponte via Real (BRL).
Cada conversão feita fica registrada como histórico do usuário - não é uma
transação financeira real, só o cálculo.

Taxa usada: média entre compra e venda da cotação mais recente. Um
conversor didático não precisa (nem deveria) escolher entre a ponta de
compra ou venda do banco - a média evita favorecer uma direção.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api import schemas
from src.api.dependencias import get_db, logger_api, obter_usuario_atual
from src.persistencia import repositorio
from src.coletores.coletor_item import buscar_cotacao_atual, CotacaoIndisponivelError

router = APIRouter(
    prefix="/conversoes", tags=["conversoes"], dependencies=[Depends(obter_usuario_atual)]
)

MOEDA_BASE = "BRL"


def _taxa_em_reais(moeda):
    """1 unidade de 'moeda' vale quantos reais, pela cotação mais recente (média compra/venda). BRL = 1.0."""
    if moeda == MOEDA_BASE:
        return 1.0

    cotacao = buscar_cotacao_atual(moeda, logger_api)
    return (cotacao.valor_compra + cotacao.valor_venda) / 2


@router.post("", response_model=schemas.ConversaoOut, status_code=201)
def converter(
    payload: schemas.ConversaoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(obter_usuario_atual),
):
    try:
        taxa_origem = _taxa_em_reais(payload.moeda_origem)
        taxa_destino = _taxa_em_reais(payload.moeda_destino)
    except CotacaoIndisponivelError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a PTAX: {erro}")

    taxa_aplicada = taxa_origem / taxa_destino
    valor_destino = payload.valor * taxa_aplicada

    conversao = repositorio.criar_conversao(
        db,
        usuario_id=usuario.id,
        moeda_origem=payload.moeda_origem,
        moeda_destino=payload.moeda_destino,
        valor_origem=payload.valor,
        valor_destino=valor_destino,
        taxa_aplicada=taxa_aplicada,
    )
    return conversao


@router.get("", response_model=list[schemas.ConversaoOut])
def historico(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    return repositorio.listar_conversoes(db, usuario.id)
