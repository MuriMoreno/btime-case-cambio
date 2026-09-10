"""
Repositório: única camada que sabe consultar/gravar Item e Coleta no banco.

As rotas da API e o agendador chamam essas funções em vez de montar queries
SQLAlchemy diretamente - mantém a forma de acessar os dados num lugar só.
"""

from src.persistencia.modelos import Item, Coleta, Usuario


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
