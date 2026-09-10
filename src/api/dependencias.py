"""Dependências compartilhadas das rotas."""

from src.persistencia.database import SessionLocal
from src.infra.logger import Logger

# Um logger compartilhado por todo o processo da API (rotas + agendador),
# igual ao padrão de run_scraping.py/run_api.py, só que de vida longa em vez
# de uma execução só.
logger_api = Logger("backend")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
