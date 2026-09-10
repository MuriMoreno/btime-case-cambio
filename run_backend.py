"""
Ponto de entrada: sobe a API do monitor de cotações (FastAPI + Uvicorn).

Espelha run_scraping.py/run_api.py: garante o ambiente antes de rodar.

Executar:  python run_backend.py
Depois, abrir http://127.0.0.1:8000/docs para o Swagger.
"""

import uvicorn

from src.infra.ambiente import preparar_ambiente


def main():
    preparar_ambiente()
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
