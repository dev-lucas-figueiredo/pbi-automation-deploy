"""Ponto de entrada do pipeline de publicacao Power BI / Microsoft Fabric.

Chamado por run_deploy.bat via `python -m pbi_deploy.main` (executado a
partir da raiz do projeto, onde estao o .env e as pastas data/template/build).
Toda a logica vive nos demais modulos deste pacote; este arquivo so delega
para o orquestrador.
"""

from pbi_deploy.pipeline import run

if __name__ == "__main__":
    run()
