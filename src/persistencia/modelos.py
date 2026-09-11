"""
Modelos ORM (SQLAlchemy) do monitor de itens.

Item: algo que o usuário cadastrou para monitorar (uma moeda contra o Real).
Coleta: uma leitura no tempo - o valor da moeda naquele instante, com a data
do boletim PTAX e o momento em que o backend coletou.
Usuario: quem acessa o sistema - senha nunca fica em texto puro, só o hash.
Conversao: um cálculo de conversão entre duas moedas feito pelo usuário,
guardado como histórico (não move dinheiro nenhum, é só o registro do
cálculo pra aparecer na tela de conversão).
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


class Conversao(Base):
    __tablename__ = "conversoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    moeda_origem = Column(String, nullable=False)
    moeda_destino = Column(String, nullable=False)
    valor_origem = Column(Float, nullable=False)
    valor_destino = Column(Float, nullable=False)
    taxa_aplicada = Column(Float, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
