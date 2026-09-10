"""
Testes do fluxo de autenticação real: registro, login e proteção das
rotas por token JWT. Ao contrário dos outros arquivos de teste (que usam
a fixture `client`, com autenticação "bypassada"), estes usam
`client_real_auth` porque aqui o próprio mecanismo de auth é o que está
sendo testado.
"""


def test_registrar_e_logar(client_real_auth):
    resposta = client_real_auth.post(
        "/auth/registrar", json={"email": "muri@btime.com", "senha": "senha123"}
    )
    assert resposta.status_code == 201
    assert resposta.json()["email"] == "muri@btime.com"
    assert "senha" not in resposta.json() and "senha_hash" not in resposta.json()

    login = client_real_auth.post(
        "/auth/login", json={"email": "muri@btime.com", "senha": "senha123"}
    )
    assert login.status_code == 200
    corpo = login.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]


def test_registrar_email_duplicado(client_real_auth):
    payload = {"email": "duplicado@btime.com", "senha": "senha123"}
    client_real_auth.post("/auth/registrar", json=payload)

    resposta = client_real_auth.post("/auth/registrar", json=payload)

    assert resposta.status_code == 409


def test_registrar_email_invalido(client_real_auth):
    resposta = client_real_auth.post(
        "/auth/registrar", json={"email": "nao-e-email", "senha": "senha123"}
    )

    assert resposta.status_code == 400


def test_registrar_senha_curta(client_real_auth):
    resposta = client_real_auth.post(
        "/auth/registrar", json={"email": "curta@btime.com", "senha": "123"}
    )

    assert resposta.status_code == 400


def test_login_senha_errada(client_real_auth):
    client_real_auth.post(
        "/auth/registrar", json={"email": "a@btime.com", "senha": "senha123"}
    )

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


def test_rota_protegida_com_token_valido(client_real_auth):
    client_real_auth.post(
        "/auth/registrar", json={"email": "logado@btime.com", "senha": "senha123"}
    )
    login = client_real_auth.post(
        "/auth/login", json={"email": "logado@btime.com", "senha": "senha123"}
    )
    token = login.json()["access_token"]

    resposta = client_real_auth.get(
        "/items", headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 200
