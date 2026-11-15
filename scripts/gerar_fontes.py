# -*- coding: utf-8 -*-
"""
Gera as fontes do app (otimizador_pc/arte/*.ttf) a partir das do site MFG (.woff2).

O Windows não lê .woff2, e as fontes variáveis (Grenze, Grenze Gotisch) nem sempre
funcionam bem no Tk. Aqui elas viram fontes fixas, cada peso com um nome de família.
Precisa de: pip install fonttools brotli

Uso: python scripts/gerar_fontes.py CAMINHO\\DO\\mfg\\assets\\fontes
Licença das fontes: SIL Open Font License (otimizador_pc/arte/OFL.txt).
"""

import os
import sys

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

DESTINO = os.path.join(os.path.dirname(__file__), "..", "otimizador_pc", "arte")

# (arquivo de origem, peso ou None, nome da família, arquivo de saída)
FONTES = [
    ("unifrakturcook-latin.woff2", None, "UnifrakturCook", "UnifrakturCook.ttf"),
    ("grenze-gotisch-latin.woff2", 500, "Grenze Gotisch", "GrenzeGotisch.ttf"),
    ("grenze-latin.woff2", 400, "Grenze", "Grenze.ttf"),
    ("grenze-latin.woff2", 600, "Grenze SemiBold", "GrenzeSemiBold.ttf"),
]


def renomear(fonte: TTFont, familia: str):
    nomes = fonte["name"]
    for rec in list(nomes.names):
        if rec.nameID in (16, 17, 25):
            nomes.removeNames(nameID=rec.nameID)
    pos = familia.replace(" ", "") + "-Regular"
    for nid, valor in ((1, familia), (2, "Regular"), (4, familia), (6, pos)):
        nomes.setName(valor, nid, 3, 1, 0x409)
        nomes.setName(valor, nid, 1, 0, 0)


def main(origem: str):
    os.makedirs(DESTINO, exist_ok=True)
    for arquivo, peso, familia, saida in FONTES:
        f = TTFont(os.path.join(origem, arquivo))
        f.flavor = None
        if peso is not None and "fvar" in f:
            f = instancer.instantiateVariableFont(f, {"wght": peso})
            f["OS/2"].usWeightClass = 400  # cada peso é uma família própria, sempre "Regular"
        if peso is not None:
            renomear(f, familia)
        f.save(os.path.join(DESTINO, saida))
        print("ok", saida)


if __name__ == "__main__":
    main(sys.argv[1])
