"""
Rotas dos itens monitorados: cadastro, listagem, última cotação, histórico
e coleta manual.

Erros de negócio (item inexistente, moeda inválida, falha na fonte) são
tratados com HTTPException diretamente aqui - não há uma classe de erro de
domínio + handler genérico para isso, porque cada rota já sabe exatamente
qual status cada situação merece (ex: moeda vazia é 400 na criação, mas é
502 numa coleta manual de um item que já existe e é válido).

Regra de unicidade: só existe um item por moeda. Tentar cadastrar uma
moeda já monitorada não cria um segundo item - devolve 409 com os dados
do item existente e quanto tempo falta para a próxima coleta automática,
para o frontend oferecer "coletar agora mesmo assim" em vez de duplicar.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api import schemas
from src.api.dependencias import get_db, logger_api, obter_usuario_atual
from src.persistencia import repositorio
from src.coletores.coletor_item import buscar_cotacao_atual, CotacaoIndisponivelError
from src.agendador.scheduler import segundos_ate_proxima_execucao

router = APIRouter(
    prefix="/items", tags=["items"], dependencies=[Depends(obter_usuario_atual)]
)


def _detalhe_moeda_duplicada(item):
    segundos = segundos_ate_proxima_execucao()

    return {
        "mensagem": f"A moeda {item.moeda} já está cadastrada.",
        "item_id": item.id,
        "nome": item.nome,
        "moeda": item.moeda,
        "segundos_ate_proxima_coleta": segundos,
    }


def _montar_item_out(db: Session, item) -> schemas.ItemOut:
    ultima = repositorio.obter_ultima_coleta(db, item.id)
    return schemas.ItemOut(
        id=item.id,
        nome=item.nome,
        moeda=item.moeda,
        criado_em=item.criado_em,
        ultima_coleta=ultima,
        variacao_percentual=repositorio.calcular_variacao_percentual(db, item.id),
    )


@router.post("", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
def cadastrar_item(payload: schemas.ItemCreate, db: Session = Depends(get_db)):
    existente = repositorio.obter_item_por_moeda(db, payload.moeda)
    if existente is not None:
        raise HTTPException(status_code=409, detail=_detalhe_moeda_duplicada(existente))

    try:
        resultado = buscar_cotacao_atual(payload.moeda, logger_api)
    except CotacaoIndisponivelError as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a PTAX: {erro}")

    item = repositorio.criar_item(db, nome=payload.nome, moeda=payload.moeda)
    repositorio.criar_coleta(
        db,
        item_id=item.id,
        data_cotacao=resultado.data_cotacao,
        valor_compra=resultado.valor_compra,
        valor_venda=resultado.valor_venda,
    )
    return _montar_item_out(db, item)


@router.get("", response_model=list[schemas.ItemOut])
def listar_itens(db: Session = Depends(get_db)):
    itens = repositorio.listar_itens(db)
    return [_montar_item_out(db, item) for item in itens]


@router.get("/{item_id}/latest", response_model=schemas.ColetaOut)
def obter_ultima_cotacao(item_id: int, db: Session = Depends(get_db)):
    item = repositorio.obter_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    ultima = repositorio.obter_ultima_coleta(db, item_id)
    if ultima is None:
        raise HTTPException(
            status_code=404, detail="Nenhuma coleta registrada para este item ainda."
        )
    return ultima


@router.get("/{item_id}/history", response_model=list[schemas.ColetaOut])
def obter_historico(item_id: int, db: Session = Depends(get_db)):
    item = repositorio.obter_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    return repositorio.listar_historico(db, item_id)


@router.post(
    "/{item_id}/collect",
    response_model=schemas.ColetaOut,
    status_code=status.HTTP_201_CREATED,
)
def coletar_agora(item_id: int, db: Session = Depends(get_db)):
    item = repositorio.obter_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    try:
        resultado = buscar_cotacao_atual(item.moeda, logger_api)
    except CotacaoIndisponivelError as erro:
        raise HTTPException(status_code=502, detail=str(erro))
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a PTAX: {erro}")

    return repositorio.criar_coleta(
        db,
        item_id=item.id,
        data_cotacao=resultado.data_cotacao,
        valor_compra=resultado.valor_compra,
        valor_venda=resultado.valor_venda,
    )
