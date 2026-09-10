"""
Modelos ORM (SQLAlchemy) do monitor de itens.

Item: algo que o usuário cadastrou para monitorar (uma moeda contra o Real).
Coleta: uma leitura no tempo - o valor da moeda naquele instante, com a data
do boletim PTAX e o momento em que o backend coletou.
Usuario: quem acessa o sistema - senha nunca fica em texto puro, só o hash.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.persistencia.database import Base


class Item(Base):
    __tablename__ = "itens"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    moeda = Column(String, nullable=False, index=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    coletas = relationship(
        "Coleta", back_populates="item", cascade="all, delete-orphan"
    )


class Coleta(Base):
    __tablename__ = "coletas"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("itens.id"), nullable=False, index=True)
    data_cotacao = Column(Date, nullable=False)
    valor_compra = Column(Float, nullable=False)
    valor_venda = Column(Float, nullable=False)
    coletado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    item = relationship("Item", back_populates="coletas")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    senha_hash = Column(String, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
