"""
Autenticação: login (emite um JWT).

Não existe cadastro público aqui de propósito. Numa API que vai pro
cliente, conceder acesso é uma ação administrativa - não uma tela que
qualquer pessoa alcança. Contas são criadas com criar_usuario.py, rodado
localmente por quem administra o sistema, não pela API.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api import schemas
from src.api.dependencias import get_db
from src.persistencia import repositorio
from src.auth.seguranca import verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = repositorio.obter_usuario_por_email(db, payload.email)
    if usuario is None or not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")

    return schemas.TokenOut(access_token=criar_token(usuario.id, usuario.email))
