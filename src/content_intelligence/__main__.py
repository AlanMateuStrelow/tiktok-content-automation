"""Ponto de entrada de modulo: `python -m content_intelligence ...`.

O comando instalado e `ci-system`, mas ele depende do diretorio de scripts do
Python estar no PATH -- coisa que no Windows costuma nao estar. Rodar pelo
modulo usa o mesmo Python que instalou o pacote e sempre funciona.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
