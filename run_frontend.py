"""
Ponto de entrada: sobe o frontend estático (HTML/CSS/JS puro, sem build)
num servidor local simples, para poder ser aberto no navegador com fetch()
funcionando (abrir o index.html direto como arquivo:// quebra o CORS).

Executar:  python run_frontend.py
Depois, abrir http://127.0.0.1:5500 (o backend precisa estar rodando em
paralelo - ver run_backend.py - a URL dele fica em frontend/config.js).
"""

import functools
import http.server
from pathlib import Path

PASTA_FRONTEND = Path(__file__).resolve().parent / "frontend"
PORTA = 5500


def main():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(PASTA_FRONTEND)
    )
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORTA), handler) as servidor:
        print(f"Frontend em http://127.0.0.1:{PORTA}")
        servidor.serve_forever()


if __name__ == "__main__":
    main()
