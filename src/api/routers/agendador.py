"""
Expõe quando será a próxima coleta automática do agendador - alimenta o
relógio de contagem regressiva do frontend (mesmo cálculo já usado no aviso
de moeda duplicada em POST /items).
"""

from fastapi import APIRouter, Depends

from src.api import schemas
from src.api.dependencias import obter_usuario_atual
from src.agendador.scheduler import proxima_execucao, segundos_ate_proxima_execucao

router = APIRouter(
    prefix="/agendador", tags=["agendador"], dependencies=[Depends(obter_usuario_atual)]
)


@router.get("/proxima-coleta", response_model=schemas.ProximaColetaOut)
def obter_proxima_coleta():
    return schemas.ProximaColetaOut(
        proxima_coleta_em=proxima_execucao(),
        segundos_ate_proxima_coleta=segundos_ate_proxima_execucao(),
    )
