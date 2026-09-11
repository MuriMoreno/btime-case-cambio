"""
Repositório: única camada que sabe consultar/gravar Item e Coleta no banco.

As rotas da API e o agendador chamam essas funções em vez de montar queries
SQLAlchemy diretamente - mantém a forma de acessar os dados num lugar só.
"""

from sqlalchemy import func

from src.persistencia.modelos import Item, Coleta, Usuario, Conversao


def criar_item(db, nome, moeda):
    item = Item(nome=nome, moeda=moeda)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def listar_itens(db):
    return db.query(Item).order_by(Item.id).all()


def obter_item(db, item_id):
    return db.query(Item).filter(Item.id == item_id).first()


def obter_item_por_moeda(db, moeda):
    return db.query(Item).filter(Item.moeda == moeda).first()


def criar_coleta(db, item_id, data_cotacao, valor_compra, valor_venda):
    coleta = Coleta(
        item_id=item_id,
        data_cotacao=data_cotacao,
        valor_compra=valor_compra,
        valor_venda=valor_venda,
    )
    db.add(coleta)
    db.commit()
    db.refresh(coleta)
    return coleta


def obter_ultima_coleta(db, item_id):
    return (
        db.query(Coleta)
        .filter(Coleta.item_id == item_id)
        .order_by(Coleta.coletado_em.desc())
        .first()
    )


def listar_historico(db, item_id):
    return (
        db.query(Coleta)
        .filter(Coleta.item_id == item_id)
        .order_by(Coleta.data_cotacao.asc(), Coleta.coletado_em.asc())
        .all()
    )


def obter_duas_ultimas_coletas(db, item_id):
    """
    As 2 coletas mais recentes (mais nova primeiro). Usado pra calcular a
    variação percentual entre a última coleta e a anterior - a base do
    selo de alerta de subida/queda brusca no frontend.
    """
    return (
        db.query(Coleta)
        .filter(Coleta.item_id == item_id)
        .order_by(Coleta.coletado_em.desc())
        .limit(2)
        .all()
    )


def calcular_variacao_percentual(db, item_id):
    """
    Variação % da cotação de compra entre a coleta mais recente e a
    anterior. None se o item ainda não tem 2 coletas pra comparar. Usada
    tanto por GET /items (selo de alerta) quanto por GET /dashboard/resumo
    (contagem de itens com alerta ativo).
    """
    duas_ultimas = obter_duas_ultimas_coletas(db, item_id)
    if len(duas_ultimas) < 2:
        return None

    atual, anterior = duas_ultimas[0].valor_compra, duas_ultimas[1].valor_compra
    if not anterior:
        return None
    return ((atual - anterior) / anterior) * 100


def obter_usuario_por_email(db, email):
    return db.query(Usuario).filter(Usuario.email == email).first()


def obter_usuario(db, usuario_id):
    return db.query(Usuario).filter(Usuario.id == usuario_id).first()


def criar_usuario(db, email, senha_hash):
    usuario = Usuario(email=email, senha_hash=senha_hash)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def criar_conversao(
    db, usuario_id, moeda_origem, moeda_destino, valor_origem, valor_destino, taxa_aplicada
):
    conversao = Conversao(
        usuario_id=usuario_id,
        moeda_origem=moeda_origem,
        moeda_destino=moeda_destino,
        valor_origem=valor_origem,
        valor_destino=valor_destino,
        taxa_aplicada=taxa_aplicada,
    )
    db.add(conversao)
    db.commit()
    db.refresh(conversao)
    return conversao


def listar_conversoes(db, usuario_id, limite=50):
    return (
        db.query(Conversao)
        .filter(Conversao.usuario_id == usuario_id)
        .order_by(Conversao.criado_em.desc())
        .limit(limite)
        .all()
    )


def contar_conversoes(db, usuario_id):
    return db.query(Conversao).filter(Conversao.usuario_id == usuario_id).count()


def contar_pares_conversao(db, usuario_id):
    """
    Quantas vezes cada par (moeda_origem -> moeda_destino) foi convertido
    pelo usuário, do mais frequente pro menos frequente - base do card
    "moeda mais convertida" do dashboard.
    """
    return (
        db.query(
            Conversao.moeda_origem,
            Conversao.moeda_destino,
            func.count(Conversao.id).label("quantidade"),
        )
        .filter(Conversao.usuario_id == usuario_id)
        .group_by(Conversao.moeda_origem, Conversao.moeda_destino)
        .order_by(func.count(Conversao.id).desc())
        .all()
    )
