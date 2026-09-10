"""
Cria uma conta de acesso ao backend, fora do fluxo de login.

Não existe cadastro público na API de propósito: conceder acesso é uma
ação administrativa, feita por quem tem a máquina/o banco em mãos - não
uma tela que qualquer pessoa alcança. É assim que um sistema que vai pro
cliente deveria funcionar (nos projetos reais da btime, isso seria criar
o usuário direto no Supabase; aqui, este script faz o equivalente no
SQLite local).

Executar:  python criar_usuario.py <email> <senha>
"""

import sys

from src.persistencia.database import SessionLocal, criar_tabelas
from src.persistencia import repositorio
from src.auth.seguranca import hash_senha


def main():
    if len(sys.argv) != 3:
        print("Uso: python criar_usuario.py <email> <senha>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    senha = sys.argv[2]

    criar_tabelas()
    db = SessionLocal()
    try:
        if repositorio.obter_usuario_por_email(db, email) is not None:
            print(f"Já existe uma conta com o e-mail {email}.")
            sys.exit(1)

        usuario = repositorio.criar_usuario(db, email=email, senha_hash=hash_senha(senha))
        print(f"Conta criada: id={usuario.id} email={usuario.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
