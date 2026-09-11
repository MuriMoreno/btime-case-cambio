"""
Testes dos endpoints principais: cadastro/listagem de itens, última
cotação, histórico, coleta manual e consulta livre por período.

A coleta na PTAX é sempre mockada (monkeypatch) - os testes nunca fazem
requisição real de rede, então rodam rápido e de forma determinística.
"""

from datetime import date

import pytest

import src.api.routers.itens as itens_router
import src.api.routers.cotacoes as cotacoes_router
import src.api.routers.moedas as moedas_router
import src.api.routers.conversoes as conversoes_router
import src.api.routers.agendador as agendador_router
from src.coletores.coletor_item import CotacaoAtual, CotacaoIndisponivelError


def _mockar_cotacao(monkeypatch, valor_compra=5.10, valor_venda=5.12, data_cotacao=None):
    resultado = CotacaoAtual(
        data_cotacao=data_cotacao or date(2026, 9, 9),
        valor_compra=valor_compra,
        valor_venda=valor_venda,
    )
    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", lambda moeda, logger: resultado)
    return resultado


def _criar_item(client, monkeypatch, moeda="USD"):
    _mockar_cotacao(monkeypatch)
    resposta = client.post("/items", json={"nome": "Dólar Americano", "moeda": moeda})
    assert resposta.status_code == 201
    return resposta.json()


# -- POST /items -------------------------------------------------------------

def test_criar_item_sucesso(client, monkeypatch):
    _mockar_cotacao(monkeypatch, valor_compra=5.10, valor_venda=5.12)

    resposta = client.post("/items", json={"nome": "Dólar", "moeda": "usd"})

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["moeda"] == "USD"  # normalizado para maiúsculo
    assert corpo["ultima_coleta"]["valor_compra"] == 5.10


def test_criar_item_moeda_invalida(client, monkeypatch):
    def levantar(moeda, logger):
        raise CotacaoIndisponivelError("moeda nao encontrada na PTAX")

    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", levantar)

    resposta = client.post("/items", json={"nome": "Inexistente", "moeda": "zzz"})

    assert resposta.status_code == 400


def test_criar_item_moeda_duplicada(client, monkeypatch):
    _mockar_cotacao(monkeypatch)
    primeiro = client.post("/items", json={"nome": "Dólar Americano", "moeda": "usd"})
    assert primeiro.status_code == 201
    id_existente = primeiro.json()["id"]

    resposta = client.post("/items", json={"nome": "Dólar de novo", "moeda": "usd"})

    assert resposta.status_code == 409
    detalhe = resposta.json()["detail"]
    assert detalhe["item_id"] == id_existente
    assert detalhe["moeda"] == "USD"
    assert detalhe["nome"] == "Dólar Americano"
    assert "segundos_ate_proxima_coleta" in detalhe

    # não deve ter criado um segundo item
    lista = client.get("/items").json()
    assert len(lista) == 1


def test_criar_item_fonte_fora_do_ar(client, monkeypatch):
    def falhar(moeda, logger):
        raise RuntimeError("PTAX indisponivel")

    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", falhar)

    resposta = client.post("/items", json={"nome": "Euro", "moeda": "eur"})

    assert resposta.status_code == 502


def test_criar_item_payload_invalido(client):
    resposta = client.post("/items", json={"nome": "", "moeda": "US"})

    assert resposta.status_code == 400


# -- GET /items ---------------------------------------------------------------

def test_listar_itens_vazio(client):
    resposta = client.get("/items")

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_listar_itens_com_ultima_coleta(client, monkeypatch):
    item = _criar_item(client, monkeypatch)

    resposta = client.get("/items")

    assert resposta.status_code == 200
    itens = resposta.json()
    assert len(itens) == 1
    assert itens[0]["id"] == item["id"]
    assert itens[0]["ultima_coleta"] is not None


# -- GET /items/{id}/latest ----------------------------------------------------

def test_latest_item_inexistente(client):
    resposta = client.get("/items/999/latest")

    assert resposta.status_code == 404


def test_latest_com_coleta(client, monkeypatch):
    item = _criar_item(client, monkeypatch)

    resposta = client.get(f"/items/{item['id']}/latest")

    assert resposta.status_code == 200
    assert resposta.json()["item_id"] == item["id"]


# -- GET /items/{id}/history ----------------------------------------------------

def test_history_item_inexistente(client):
    resposta = client.get("/items/999/history")

    assert resposta.status_code == 404


def test_history_com_coleta(client, monkeypatch):
    item = _criar_item(client, monkeypatch)

    resposta = client.get(f"/items/{item['id']}/history")

    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


# -- POST /items/{id}/collect ----------------------------------------------------

def test_collect_sucesso(client, monkeypatch):
    item = _criar_item(client, monkeypatch)
    _mockar_cotacao(monkeypatch, valor_compra=5.20, valor_venda=5.22, data_cotacao=date(2026, 9, 10))

    resposta = client.post(f"/items/{item['id']}/collect")

    assert resposta.status_code == 201
    assert resposta.json()["valor_compra"] == 5.20


def test_variacao_percentual_null_com_uma_coleta(client, monkeypatch):
    item = _criar_item(client, monkeypatch)

    lista = client.get("/items").json()

    assert lista[0]["variacao_percentual"] is None


def test_variacao_percentual_calculada_apos_segunda_coleta(client, monkeypatch):
    item = _criar_item(client, monkeypatch)  # compra=5.10
    _mockar_cotacao(monkeypatch, valor_compra=5.61, valor_venda=5.63, data_cotacao=date(2026, 9, 10))

    client.post(f"/items/{item['id']}/collect")
    lista = client.get("/items").json()

    # (5.61 - 5.10) / 5.10 * 100 = 10.0
    assert lista[0]["variacao_percentual"] == pytest.approx(10.0)


def test_collect_falha_da_fonte(client, monkeypatch):
    item = _criar_item(client, monkeypatch)

    def falhar(moeda, logger):
        raise RuntimeError("PTAX fora do ar")

    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", falhar)

    resposta = client.post(f"/items/{item['id']}/collect")

    assert resposta.status_code == 502


def test_collect_item_inexistente(client):
    resposta = client.post("/items/999/collect")

    assert resposta.status_code == 404


# -- GET /cotacoes (consulta livre) ----------------------------------------------

def test_consulta_livre_sucesso(client, monkeypatch):
    boletins = [
        {
            "tipoBoletim": "Fechamento",
            "dataHoraCotacao": "2026-09-09 13:00:00.0",
            "cotacaoCompra": 5.10,
            "cotacaoVenda": 5.12,
        }
    ]
    monkeypatch.setattr(
        cotacoes_router, "buscar_boletins", lambda moeda, di, df, logger: boletins
    )

    resposta = client.get(
        "/cotacoes",
        params={"moeda": "EUR", "data_inicio": "2026-09-01", "data_fim": "2026-09-10"},
    )

    assert resposta.status_code == 200
    assert len(resposta.json()) == 1
    assert resposta.json()[0]["valor_compra"] == 5.10


def test_consulta_livre_periodo_sem_boletim(client, monkeypatch):
    monkeypatch.setattr(
        cotacoes_router, "buscar_boletins", lambda moeda, di, df, logger: []
    )

    resposta = client.get(
        "/cotacoes",
        params={"moeda": "EUR", "data_inicio": "2026-09-01", "data_fim": "2026-09-10"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_consulta_livre_periodo_invertido(client):
    resposta = client.get(
        "/cotacoes",
        params={"moeda": "EUR", "data_inicio": "2026-09-10", "data_fim": "2026-09-01"},
    )

    assert resposta.status_code == 400


def test_consulta_livre_falha_da_fonte(client, monkeypatch):
    def falhar(moeda, di, df, logger):
        raise RuntimeError("PTAX fora do ar")

    monkeypatch.setattr(cotacoes_router, "buscar_boletins", falhar)

    resposta = client.get(
        "/cotacoes",
        params={"moeda": "EUR", "data_inicio": "2026-09-01", "data_fim": "2026-09-10"},
    )

    assert resposta.status_code == 502


# -- GET /moedas ------------------------------------------------------------

def test_listar_moedas_sucesso(client, monkeypatch):
    moedas_cruas = [
        {"simbolo": "USD", "nomeFormatado": "Dólar dos Estados Unidos"},
        {"simbolo": "EUR", "nomeFormatado": "Euro"},
    ]
    monkeypatch.setattr(moedas_router, "listar_moedas", lambda logger: moedas_cruas)

    resposta = client.get("/moedas")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo == [
        {"codigo": "USD", "nome": "Dólar dos Estados Unidos"},
        {"codigo": "EUR", "nome": "Euro"},
    ]


def test_listar_moedas_falha_da_fonte(client, monkeypatch):
    def falhar(logger):
        raise RuntimeError("PTAX fora do ar")

    monkeypatch.setattr(moedas_router, "listar_moedas", falhar)

    resposta = client.get("/moedas")

    assert resposta.status_code == 502


# -- POST/GET /conversoes ------------------------------------------------------

def _mockar_taxa(monkeypatch, valor_compra=5.00, valor_venda=5.10):
    resultado = CotacaoAtual(
        data_cotacao=date(2026, 9, 9), valor_compra=valor_compra, valor_venda=valor_venda
    )
    monkeypatch.setattr(
        conversoes_router, "buscar_cotacao_atual", lambda moeda, logger: resultado
    )
    return resultado


def test_converter_moeda_estrangeira_para_brl(client, monkeypatch):
    _mockar_taxa(monkeypatch, valor_compra=5.00, valor_venda=5.10)  # média = 5.05

    resposta = client.post(
        "/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 100}
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["moeda_origem"] == "USD"
    assert corpo["moeda_destino"] == "BRL"
    assert corpo["valor_destino"] == pytest.approx(505.0)
    assert corpo["taxa_aplicada"] == pytest.approx(5.05)


def test_converter_entre_duas_moedas_estrangeiras(client, monkeypatch):
    chamadas = {"USD": 5.00, "EUR": 6.00}

    def taxa_por_moeda(moeda, logger):
        valor = chamadas[moeda]
        return CotacaoAtual(data_cotacao=date(2026, 9, 9), valor_compra=valor, valor_venda=valor)

    monkeypatch.setattr(conversoes_router, "buscar_cotacao_atual", taxa_por_moeda)

    resposta = client.post(
        "/conversoes", json={"moeda_origem": "EUR", "moeda_destino": "USD", "valor": 10}
    )

    assert resposta.status_code == 201
    # 10 EUR * 6.00 = 60 BRL; 60 BRL / 5.00 = 12 USD
    assert resposta.json()["valor_destino"] == pytest.approx(12.0)


def test_converter_moeda_invalida(client, monkeypatch):
    def levantar(moeda, logger):
        raise CotacaoIndisponivelError("moeda nao encontrada na PTAX")

    monkeypatch.setattr(conversoes_router, "buscar_cotacao_atual", levantar)

    resposta = client.post(
        "/conversoes", json={"moeda_origem": "zzz", "moeda_destino": "brl", "valor": 10}
    )

    assert resposta.status_code == 400


def test_converter_fonte_fora_do_ar(client, monkeypatch):
    def falhar(moeda, logger):
        raise RuntimeError("PTAX fora do ar")

    monkeypatch.setattr(conversoes_router, "buscar_cotacao_atual", falhar)

    resposta = client.post(
        "/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 10}
    )

    assert resposta.status_code == 502


def test_listar_historico_conversoes(client, monkeypatch):
    _mockar_taxa(monkeypatch)
    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 100})
    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 50})

    resposta = client.get("/conversoes")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 2
    assert corpo[0]["valor_origem"] == 50  # mais recente primeiro


# -- GET /agendador/proxima-coleta ---------------------------------------------

def test_proxima_coleta_com_agendador_rodando(client, monkeypatch):
    from datetime import datetime, timezone

    daqui_a_pouco = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setattr(agendador_router, "proxima_execucao", lambda: daqui_a_pouco)
    monkeypatch.setattr(agendador_router, "segundos_ate_proxima_execucao", lambda: 123)

    resposta = client.get("/agendador/proxima-coleta")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["segundos_ate_proxima_coleta"] == 123
    assert corpo["proxima_coleta_em"] is not None


def test_proxima_coleta_sem_agendador(client, monkeypatch):
    monkeypatch.setattr(agendador_router, "proxima_execucao", lambda: None)
    monkeypatch.setattr(agendador_router, "segundos_ate_proxima_execucao", lambda: None)

    resposta = client.get("/agendador/proxima-coleta")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["segundos_ate_proxima_coleta"] is None
    assert corpo["proxima_coleta_em"] is None
