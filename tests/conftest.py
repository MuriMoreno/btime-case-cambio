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
from src.persistencia import modelos  # noqa: F401 - registra Item/Coleta no Base
from src.api.main import app
from src.api.dependencias import get_db


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
    return TestClient(app)
