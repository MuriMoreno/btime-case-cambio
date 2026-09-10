"""
Schemas Pydantic: formato de entrada/saída dos endpoints.

Validação básica de formato (tipos, regex) fica aqui - o que exige uma
chamada externa (a moeda existe mesmo na PTAX?) é responsabilidade das
rotas, que chamam o coletor.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    moeda: str = Field(..., min_length=3, max_length=3)

    @field_validator("moeda")
    @classmethod
    def moeda_maiuscula_e_alfabetica(cls, valor):
        if not valor.isalpha():
            raise ValueError("moeda deve conter apenas letras (ex: 'USD')")
        return valor.upper()


class ColetaOut(BaseModel):
    id: int
    item_id: int
    data_cotacao: date
    valor_compra: float
    valor_venda: float
    coletado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemOut(BaseModel):
    id: int
    nome: str
    moeda: str
    criado_em: datetime
    ultima_coleta: ColetaOut | None = None

    model_config = ConfigDict(from_attributes=True)


class CotacaoConsultaOut(BaseModel):
    data_cotacao: date
    valor_compra: float
    valor_venda: float


class MoedaOut(BaseModel):
    codigo: str
    nome: str
