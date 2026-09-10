"""
Consulta livre: moeda + período escolhidos na hora, direto na PTAX, sem
precisar ter um item cadastrado. Pensada para uma tela interativa do
frontend (usuário escolhe moeda e intervalo de datas e vê o resultado na
hora), além do que o agendador já coleta para os itens cadastrados.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from src.infra import config
from src.api.schemas import CotacaoConsultaOut
from src.api.dependencias import logger_api
from src.coletores.ptax_cliente import buscar_boletins

router = APIRouter(prefix="/cotacoes", tags=["cotacoes"])


@router.get("", response_model=list[CotacaoConsultaOut])
def consultar_periodo(
    moeda: str = Query(..., min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"),
    data_inicio: date = Query(...),
    data_fim: date = Query(...),
):
    if data_inicio > data_fim:
        raise HTTPException(
            status_code=400, detail="data_inicio não pode ser depois de data_fim."
        )

    if (data_fim - data_inicio).days > config.JANELA_MAXIMA_CONSULTA_DIAS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Período maior que o limite de "
                f"{config.JANELA_MAXIMA_CONSULTA_DIAS} dias."
            ),
        )

    try:
        boletins = buscar_boletins(moeda.upper(), data_inicio, data_fim, logger_api)
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a PTAX: {erro}")

    fechamentos = [
        b for b in boletins
        if b.get("tipoBoletim") == config.API_TIPO_BOLETIM_FECHAMENTO
    ]

    return [
        CotacaoConsultaOut(
            data_cotacao=date.fromisoformat(
                b.get("dataHoraCotacao", "").split(" ")[0]
            ),
            valor_compra=float(b.get("cotacaoCompra", 0)),
            valor_venda=float(b.get("cotacaoVenda", 0)),
        )
        for b in fechamentos
    ]
