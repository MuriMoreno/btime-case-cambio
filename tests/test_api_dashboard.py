"""
Testes do dashboard: ranking de maiores altas/baixas entre o recorte de
moedas configurado e o resumo (itens monitorados, alertas ativos,
conversões feitas). A consulta na PTAX é sempre mockada.
"""

from datetime import date

import pytest

import src.api.routers.dashboard as dashboard_router
import src.api.routers.itens as itens_router
from src.coletores.coletor_item import CotacaoAtual
from src.infra import config


def _boletim(data_iso, cotacao_compra):
    return {
        "tipoBoletim": "Fechamento",
        "dataHoraCotacao": f"{data_iso} 13:00:00.0",
        "cotacaoCompra": cotacao_compra,
        "cotacaoVenda": cotacao_compra + 0.01,
    }


# -- GET /dashboard/ranking-variacao -------------------------------------------

def test_ranking_variacao_ordena_da_maior_alta_para_a_maior_baixa(client, monkeypatch):
    boletins_por_moeda = {
        "USD": [_boletim("2026-06-01", 5.00), _boletim("2026-09-01", 5.50)],  # +10%
        "EUR": [_boletim("2026-06-01", 6.00), _boletim("2026-09-01", 5.40)],  # -10%
    }

    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        return boletins_por_moeda.get(moeda, [])

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/ranking-variacao")

    assert resposta.status_code == 200
    corpo = resposta.json()
    codigos = [item["codigo"] for item in corpo]
    assert codigos.index("USD") < codigos.index("EUR")  # USD (alta) antes de EUR (baixa)

    usd = next(item for item in corpo if item["codigo"] == "USD")
    assert usd["variacao_percentual"] == pytest.approx(10.0)


def test_ranking_variacao_ignora_moeda_com_menos_de_dois_boletins(client, monkeypatch):
    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        return [_boletim("2026-09-01", 5.00)] if moeda == "USD" else []

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/ranking-variacao")

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_ranking_variacao_ignora_moeda_que_falha_na_ptax(client, monkeypatch):
    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        if moeda == "USD":
            raise RuntimeError("PTAX fora do ar")
        return [_boletim("2026-06-01", 6.00), _boletim("2026-09-01", 6.60)]

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/ranking-variacao")

    assert resposta.status_code == 200
    codigos = [item["codigo"] for item in resposta.json()]
    assert "USD" not in codigos
    assert len(codigos) == len(config.MOEDAS_DASHBOARD_RANKING) - 1


def test_ranking_variacao_aceita_parametro_dias(client, monkeypatch):
    chamadas = []

    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        chamadas.append((data_inicio, data_fim))
        return []

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/ranking-variacao", params={"dias": 30})

    assert resposta.status_code == 200
    assert all((df - di).days == 30 for di, df in chamadas)


# -- GET /dashboard/resumo ------------------------------------------------------

def test_resumo_sem_itens_nem_conversoes(client):
    resposta = client.get("/dashboard/resumo")

    assert resposta.status_code == 200
    assert resposta.json() == {"total_itens": 0, "itens_com_alerta": 0, "total_conversoes": 0}


def test_resumo_conta_itens_com_alerta_ativo(client, monkeypatch):
    resultado_inicial = CotacaoAtual(data_cotacao=date(2026, 9, 1), valor_compra=5.00, valor_venda=5.02)
    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", lambda moeda, logger: resultado_inicial)
    item = client.post("/items", json={"nome": "Dólar", "moeda": "usd"}).json()

    # segunda coleta com alta de 10% - acima do limiar padrão de 2%
    resultado_alta = CotacaoAtual(data_cotacao=date(2026, 9, 2), valor_compra=5.50, valor_venda=5.52)
    monkeypatch.setattr(itens_router, "buscar_cotacao_atual", lambda moeda, logger: resultado_alta)
    client.post(f"/items/{item['id']}/collect")

    resposta = client.get("/dashboard/resumo")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total_itens"] == 1
    assert corpo["itens_com_alerta"] == 1


def test_resumo_conta_conversoes_do_usuario(client, monkeypatch):
    resultado = CotacaoAtual(data_cotacao=date(2026, 9, 1), valor_compra=5.00, valor_venda=5.10)
    import src.api.routers.conversoes as conversoes_router

    monkeypatch.setattr(conversoes_router, "buscar_cotacao_atual", lambda moeda, logger: resultado)
    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 100})
    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 50})

    resposta = client.get("/dashboard/resumo")

    assert resposta.status_code == 200
    assert resposta.json()["total_conversoes"] == 2


# -- GET /dashboard/mercado (volatilidade + variação por dia da semana) -------

def test_mercado_encontra_maior_variacao_diaria(client, monkeypatch):
    # USD: maior salto é 08->09 (+20%); demais moedas do recorte ficam vazias.
    boletins_usd = [
        _boletim("2026-09-07", 5.00),  # segunda-feira
        _boletim("2026-09-08", 5.10),  # terça-feira: +2%
        _boletim("2026-09-09", 6.12),  # quarta-feira: +20% (maior variação)
    ]

    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        return boletins_usd if moeda == "USD" else []

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/mercado")

    assert resposta.status_code == 200
    corpo = resposta.json()

    assert len(corpo["volatilidade"]) == 1
    usd = corpo["volatilidade"][0]
    assert usd["codigo"] == "USD"
    assert usd["maior_variacao_diaria_percentual"] == pytest.approx(20.0)
    assert usd["data_ocorrencia"] == "2026-09-09"


def test_mercado_agrega_variacao_por_dia_da_semana(client, monkeypatch):
    # Cadeia de fechamentos consecutivos: 07->08 (terça, +2%), 08->14
    # (segunda, 0%) e 14->15 (terça, -1.96...%) - duas amostras caem na
    # terça-feira, pra confirmar que a média é entre as duas.
    boletins_usd = [
        _boletim("2026-09-07", 5.00),
        _boletim("2026-09-08", 5.10),  # terça: +2%
        _boletim("2026-09-14", 5.10),  # segunda: 0%
        _boletim("2026-09-15", 5.00),  # terça: -1.96...%
    ]

    def falso_buscar_boletins(moeda, data_inicio, data_fim, logger):
        return boletins_usd if moeda == "USD" else []

    monkeypatch.setattr(dashboard_router, "buscar_boletins", falso_buscar_boletins)

    resposta = client.get("/dashboard/mercado")

    assert resposta.status_code == 200
    por_dia = {d["dia_semana"]: d for d in resposta.json()["variacao_por_dia_semana"]}

    assert por_dia["Terça-feira"]["amostras"] == 2
    assert por_dia["Terça-feira"]["variacao_media_percentual"] == pytest.approx(1.98, abs=0.05)
    assert por_dia["Segunda-feira"]["amostras"] == 1
    assert por_dia["Segunda-feira"]["variacao_media_percentual"] == pytest.approx(0.0, abs=0.01)


def test_mercado_ignora_moeda_sem_boletins_suficientes(client, monkeypatch):
    monkeypatch.setattr(dashboard_router, "buscar_boletins", lambda moeda, di, df, logger: [])

    resposta = client.get("/dashboard/mercado")

    assert resposta.status_code == 200
    assert resposta.json() == {"volatilidade": [], "variacao_por_dia_semana": []}


# -- GET /dashboard/conversoes-resumo -------------------------------------------

def test_conversoes_resumo_sem_conversoes(client):
    resposta = client.get("/dashboard/conversoes-resumo")

    assert resposta.status_code == 200
    assert resposta.json() == {"total": 0, "pares": []}


def test_conversoes_resumo_agrupa_por_par_e_calcula_percentual(client, monkeypatch):
    import src.api.routers.conversoes as conversoes_router

    resultado = CotacaoAtual(data_cotacao=date(2026, 9, 1), valor_compra=5.00, valor_venda=5.10)
    monkeypatch.setattr(conversoes_router, "buscar_cotacao_atual", lambda moeda, logger: resultado)

    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 100})
    client.post("/conversoes", json={"moeda_origem": "usd", "moeda_destino": "brl", "valor": 50})
    client.post("/conversoes", json={"moeda_origem": "eur", "moeda_destino": "brl", "valor": 10})

    resposta = client.get("/dashboard/conversoes-resumo")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 3

    par_principal = corpo["pares"][0]
    assert par_principal["moeda_origem"] == "USD"
    assert par_principal["moeda_destino"] == "BRL"
    assert par_principal["quantidade"] == 2
    assert par_principal["percentual"] == pytest.approx(66.666, abs=0.01)
