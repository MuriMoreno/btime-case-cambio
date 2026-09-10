"""
Hash de senha e emissão/verificação de token JWT.

Concentrado aqui para o resto do backend nunca lidar com senha em texto
puro nem com a mecânica de JWT diretamente - só chama hash_senha,
verificar_senha, criar_token e decodificar_token.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from src.infra import config


def hash_senha(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha, senha_hash):
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


class TokenInvalidoError(Exception):
    """Token ausente, malformado, assinatura inválida ou expirado."""
    pass


def criar_token(usuario_id, email):
    expira_em = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRACAO_HORAS)
    payload = {"sub": str(usuario_id), "email": email, "exp": expira_em}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decodificar_token(token):
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError as erro:
        raise TokenInvalidoError(str(erro))
