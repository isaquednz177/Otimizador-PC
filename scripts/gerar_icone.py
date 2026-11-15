# -*- coding: utf-8 -*-
"""
Desenha o ícone do programa (otimizador_pc/arte/icone.ico) nas cores do tema:
fundo preto gótico, moldura marrom e um mostrador em vermelho-sangue com ponteiro.

Desenha grande (1024 px) e reduz para cada tamanho que o Windows usa, para ficar
nítido do 16 px da barra de título ao 256 px do Explorador.
Uso: python scripts/gerar_icone.py
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

DESTINO = os.path.join(os.path.dirname(__file__), "..", "otimizador_pc", "arte")
N = 1024

PRETO = (9, 6, 6)
PRETO2 = (27, 18, 13)
MARROM = (94, 61, 39)
MARROM_ESCURO = (52, 34, 22)
SANGUE = (138, 10, 18)
SANGUE_VIVO = (229, 71, 79)
CLARO = (238, 230, 220)


def desenhar() -> Image.Image:
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(N * 0.04)

    # fundo: quadrado de cantos quase retos, do preto para o marrom bem escuro
    fundo = Image.new("RGBA", (N, N))
    for y in range(N):
        t = y / N
        cor = tuple(int(PRETO[i] + (PRETO2[i] - PRETO[i]) * t) for i in range(3)) + (255,)
        ImageDraw.Draw(fundo).line([(0, y), (N, y)], fill=cor)
    mascara = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((m, m, N - m, N - m), radius=int(N * 0.06), fill=255)
    img.paste(fundo, (0, 0), mascara)

    # moldura marrom (dupla, como a do site)
    d.rounded_rectangle((m, m, N - m, N - m), radius=int(N * 0.06), outline=MARROM, width=int(N * 0.022))
    i2 = m + int(N * 0.05)
    d.rectangle((i2, i2, N - i2, N - i2), outline=MARROM_ESCURO, width=int(N * 0.008))

    # mostrador: arco de 270 graus, trilho marrom e 3/4 em vermelho-sangue
    c = N / 2
    r = N * 0.30
    largura = int(N * 0.085)
    caixa = (c - r, c - r + N * 0.04, c + r, c + r + N * 0.04)
    d.arc(caixa, start=135, end=405, fill=MARROM_ESCURO, width=largura)
    d.arc(caixa, start=135, end=330, fill=SANGUE, width=largura)
    d.arc(caixa, start=300, end=330, fill=SANGUE_VIVO, width=largura)

    # brilho fraco atrás do vermelho
    brilho = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(brilho).arc(caixa, start=135, end=330, fill=SANGUE_VIVO + (90,), width=largura + 30)
    img = Image.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(N * 0.02)), img)
    d = ImageDraw.Draw(img)

    # ponteiro apontando para a ponta do vermelho
    cy = c + N * 0.04
    angulo = math.radians(315)
    ponta = (c + math.cos(angulo) * r * 0.86, cy + math.sin(angulo) * r * 0.86)
    lado = math.radians(315 + 90)
    base = N * 0.035
    d.polygon([ponta,
               (c + math.cos(lado) * base, cy + math.sin(lado) * base),
               (c - math.cos(angulo) * N * 0.05, cy - math.sin(angulo) * N * 0.05),
               (c - math.cos(lado) * base, cy - math.sin(lado) * base)], fill=CLARO)
    eixo = N * 0.055
    d.ellipse((c - eixo, cy - eixo, c + eixo, cy + eixo), fill=SANGUE, outline=CLARO, width=int(N * 0.012))
    return img


def main():
    os.makedirs(DESTINO, exist_ok=True)
    grande = desenhar()
    tamanhos = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    destino = os.path.join(DESTINO, "icone.ico")
    grande.resize((256, 256), Image.LANCZOS).save(destino, sizes=[(s, s) for s in tamanhos])
    grande.resize((256, 256), Image.LANCZOS).save(os.path.join(DESTINO, "icone.png"))
    print("ok", destino)


if __name__ == "__main__":
    main()
