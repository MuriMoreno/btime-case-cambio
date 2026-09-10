"""
Configuração da conexão com o banco (SQLite via SQLAlchemy).

Um único engine/sessionmaker para o processo inteiro - usado tanto pela
dependência de sessão das rotas (uma sessão por requisição) quanto pelo
agendador (que abre a sua própria sessão fora do ciclo de requisição).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infra import config

# check_same_thread=False: necessário para SQLite quando o mesmo arquivo é
# acessado por threads diferentes (requisições da API e o job do agendador).
engine = create_engine(
    config.DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def criar_tabelas():
    """Cria as tabelas que ainda não existem. Idempotente."""
    from src.persistencia import modelos  # noqa: F401 - garante que os modelos foram registrados
    Base.metadata.create_all(bind=engine)
