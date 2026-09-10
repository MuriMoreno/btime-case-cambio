"""
Autenticação: cadastro de usuário e login (emite um JWT).

Fica de fora da proteção por token (óbvio: sem token ainda não tem como
autenticar). O cadastro é aberto porque este projeto roda só localmente,
de ambientação - numa API exposta de verdade, isso teria outro controle
(convite, confirmação de e-mail, ou simplesmente removido depois de criar
a própria conta).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api import schemas
from src.api.dependencias import get_db
from src.persistencia import repositorio
from src.auth.seguranca import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registrar", response_model=schemas.UsuarioOut, status_code=201)
def registrar(payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if repositorio.obter_usuario_por_email(db, payload.email) is not None:
        raise HTTPException(status_code=409, detail="Já existe uma conta com esse e-mail.")

    return repositorio.criar_usuario(
        db, email=payload.email, senha_hash=hash_senha(payload.senha)
    )


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = repositorio.obter_usuario_por_email(db, payload.email)
    if usuario is None or not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")

    return schemas.TokenOut(access_token=criar_token(usuario.id, usuario.email))
