"""Dependências compartilhadas das rotas."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.persistencia.database import SessionLocal
from src.persistencia import repositorio
from src.infra.logger import Logger
from src.auth.seguranca import decodificar_token, TokenInvalidoError

# Um logger compartilhado por todo o processo da API (rotas + agendador),
# igual ao padrão de run_scraping.py/run_api.py, só que de vida longa em vez
# de uma execução só.
logger_api = Logger("backend")

# auto_error=False: preferimos levantar o 401 nós mesmos (mensagem e status
# consistentes com o resto da API) em vez do 403 padrão que o HTTPBearer
# devolve quando não vem nenhum header Authorization.
_esquema_bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def obter_usuario_atual(
    credenciais: HTTPAuthorizationCredentials = Depends(_esquema_bearer),
    db: Session = Depends(get_db),
):
    """
    Dependência que protege uma rota: exige um Bearer token válido e
    devolve o Usuario correspondente. Aplicada no nível do router
    (dependencies=[Depends(obter_usuario_atual)]), não rota por rota.
    """
    if credenciais is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    try:
        payload = decodificar_token(credenciais.credentials)
    except TokenInvalidoError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    usuario = repositorio.obter_usuario(db, int(payload["sub"]))
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    return usuario
