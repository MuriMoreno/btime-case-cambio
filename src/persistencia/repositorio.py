"""
Repositório: única camada que sabe consultar/gravar Item e Coleta no banco.

As rotas da API e o agendador chamam essas funções em vez de montar queries
SQLAlchemy diretamente - mantém a forma de acessar os dados num lugar só.
"""

from src.persistencia.modelos import Item, Coleta


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
