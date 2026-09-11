"""
Schemas Pydantic: formato de entrada/saída dos endpoints.

Validação básica de formato (tipos, regex) fica aqui - o que exige uma
chamada externa (a moeda existe mesmo na PTAX?) é responsabilidade das
rotas, que chamam o coletor.
"""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    variacao_percentual: float | None = None

    model_config = ConfigDict(from_attributes=True)


class CotacaoConsultaOut(BaseModel):
    data_cotacao: date
    valor_compra: float
    valor_venda: float


class MoedaOut(BaseModel):
    codigo: str
    nome: str


class ProximaColetaOut(BaseModel):
    proxima_coleta_em: datetime | None = None
    segundos_ate_proxima_coleta: int | None = None


class VariacaoMoedaOut(BaseModel):
    codigo: str
    valor_inicial: float
    valor_atual: float
    variacao_percentual: float


class ResumoDashboardOut(BaseModel):
    total_itens: int
    itens_com_alerta: int
    total_conversoes: int


class VolatilidadeMoedaOut(BaseModel):
    codigo: str
    maior_variacao_diaria_percentual: float
    data_ocorrencia: date


class VariacaoDiaSemanaOut(BaseModel):
    dia_semana: str
    variacao_media_percentual: float
    amostras: int


class DashboardMercadoOut(BaseModel):
    volatilidade: list[VolatilidadeMoedaOut]
    variacao_por_dia_semana: list[VariacaoDiaSemanaOut]


class ParConversaoOut(BaseModel):
    moeda_origem: str
    moeda_destino: str
    quantidade: int
    percentual: float


class ResumoConversoesOut(BaseModel):
    total: int
    pares: list[ParConversaoOut]


_CODIGO_MOEDA_REGEX = re.compile(r"^[A-Za-z]{3}$")


class ConversaoCreate(BaseModel):
    moeda_origem: str = Field(..., min_length=3, max_length=3)
    moeda_destino: str = Field(..., min_length=3, max_length=3)
    valor: float = Field(..., gt=0)

    @field_validator("moeda_origem", "moeda_destino")
    @classmethod
    def moeda_maiuscula_e_alfabetica(cls, valor):
        if not _CODIGO_MOEDA_REGEX.match(valor):
            raise ValueError("codigo de moeda deve ter 3 letras (ex: 'USD', 'BRL')")
        return valor.upper()


class ConversaoOut(BaseModel):
    id: int
    moeda_origem: str
    moeda_destino: str
    valor_origem: float
    valor_destino: float
    taxa_aplicada: float
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


def _validar_email(valor):
    if not _EMAIL_REGEX.match(valor):
        raise ValueError("e-mail inválido")
    return valor.strip().lower()


class LoginRequest(BaseModel):
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def email_valido(cls, valor):
        return _validar_email(valor)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
