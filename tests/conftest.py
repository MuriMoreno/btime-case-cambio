"""
Fixtures compartilhadas dos testes da API.

Cada teste ganha um banco SQLite isolado (arquivo temporário) via
override da dependência get_db - nunca toca no banco real
(dados/monitor.db) nem depende de execuções anteriores.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.persistencia.database import Base
from src.persistencia import modelos  # noqa: F401 - registra Item/Coleta/Usuario no Base
from src.api.main import app
from src.api.dependencias import get_db, obter_usuario_atual


class _UsuarioFalso:
    id = 1
    email = "teste@btime.com"


def _usuario_falso():
    return _UsuarioFalso()


@pytest.fixture()
def db_session(tmp_path):
    caminho = tmp_path / "teste.db"
    engine = create_engine(
        f"sqlite:///{caminho}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def sobrescrever_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = sobrescrever_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """
    Cliente com autenticação "bypassada" (injeta um usuário fake) - usado
    pelos testes de regra de negócio (itens, cotações, moedas), que não são
    sobre autenticação em si. Os testes do fluxo de auth de verdade usam
    `client_real_auth`.
    """
    app.dependency_overrides[obter_usuario_atual] = _usuario_falso
    yield TestClient(app)
    app.dependency_overrides.pop(obter_usuario_atual, None)


@pytest.fixture()
def client_real_auth(db_session):
    """Cliente sem bypass - exercita o fluxo real de registro/login/token."""
    return TestClient(app)
