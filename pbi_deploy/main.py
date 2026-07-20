"""Ponto de entrada do pipeline de publicacao Power BI / Microsoft Fabric.

Chamado pelos .bat via `python -m pbi_deploy.main <gestao|lideres>` (executado
a partir da raiz do projeto, onde estao o .env e as pastas data/template/build).
O modo (gestao ou lideres) vem como argumento de linha de comando. Toda a logica
vive nos demais modulos deste pacote; este arquivo so delega para o orquestrador.
"""

import sys

from pbi_deploy.pipeline import run

if __name__ == "__main__":
    modo = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None
    run(modo)
