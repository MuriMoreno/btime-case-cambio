"""
Testes do fluxo de autenticação real: login e proteção das rotas por
token JWT. Ao contrário dos outros arquivos de teste (que usam a fixture
`client`, com autenticação "bypassada"), estes usam `client_real_auth`
porque aqui o próprio mecanismo de auth é o que está sendo testado.

Não existe endpoint público de cadastro (decisão: contas são criadas via
criar_usuario.py, uma ação administrativa) - os testes semeiam o usuário
direto no banco com a fixture `criar_usuario_teste`.
"""


def test_auth_registrar_nao_existe(client_real_auth):
    """Não deve haver cadastro público na API."""
    resposta = client_real_auth.post(
        "/auth/registrar", json={"email": "x@btime.com", "senha": "senha123"}
    )

    assert resposta.status_code == 404


def test_login_sucesso(client_real_auth, criar_usuario_teste):
    criar_usuario_teste("muri@btime.com", "senha123")

    resposta = client_real_auth.post(
        "/auth/login", json={"email": "muri@btime.com", "senha": "senha123"}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]


def test_login_senha_errada(client_real_auth, criar_usuario_teste):
    criar_usuario_teste("a@btime.com", "senha123")

    resposta = client_real_auth.post(
        "/auth/login", json={"email": "a@btime.com", "senha": "errada"}
    )

    assert resposta.status_code == 401


def test_login_email_inexistente(client_real_auth):
    resposta = client_real_auth.post(
        "/auth/login", json={"email": "naoexiste@btime.com", "senha": "senha123"}
    )

    assert resposta.status_code == 401


def test_rota_protegida_sem_token(client_real_auth):
    resposta = client_real_auth.get("/items")

    assert resposta.status_code == 401


def test_rota_protegida_com_token_invalido(client_real_auth):
    resposta = client_real_auth.get(
        "/items", headers={"Authorization": "Bearer token-invalido"}
    )

    assert resposta.status_code == 401


def test_rota_protegida_com_token_valido(client_real_auth, criar_usuario_teste):
    criar_usuario_teste("logado@btime.com", "senha123")
    login = client_real_auth.post(
        "/auth/login", json={"email": "logado@btime.com", "senha": "senha123"}
    )
    token = login.json()["access_token"]

    resposta = client_real_auth.get(
        "/items", headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
