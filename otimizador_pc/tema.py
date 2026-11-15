# -*- coding: utf-8 -*-
"""
A cara do programa: cores, fontes e as peças da tela.

Escuro quente com acento âmbar, como um painel de instrumentos. Cantos
quase retos (nada de botão em pílula), linhas finas em vez de sombra,
Bahnschrift nos títulos e números, Segoe UI no texto e os ícones do
próprio Windows (Segoe Fluent Icons; no Windows 10, Segoe MDL2 Assets).
"""

import tkinter.font as tkfont

import customtkinter as ctk

FUNDO = "#0F1113"
LATERAL = "#131619"
PAINEL = "#191C20"
PAINEL2 = "#21252B"
LINHA = "#2B3037"
TEXTO = "#ECE7DD"
SUAVE = "#A29F97"
FRACO = "#6F6D67"
ACENTO = "#E3A33B"
ACENTO_CLARO = "#F0B858"
ACENTO_FUNDO = "#2E2412"
NO_ACENTO = "#17110A"
OK = "#86C98A"
PERIGO = "#E5776B"
PERIGO_FUNDO = "#3D1C19"
RAIO = 3

ICONES = {
    "inicio": "", "desempenho": "", "limpeza": "", "espaco": "",
    "ajustes": "", "inicializacao": "", "medicoes": "", "reverter": "",
    "registro": "", "modo_jogo": "", "hardware": "", "pasta": "", "subir": "", "atualizar": "",
    "fechar": "", "escudo": "", "aviso": "",
}

_familias = {}


def preparar_fontes():
    """Escolhe as fontes que existem neste Windows (chamar depois de criar a janela)."""
    existentes = set(tkfont.families())

    def primeira(*opcoes):
        for f in opcoes:
            if f in existentes:
                return f
        return opcoes[-1]
    _familias.update(
        titulo=primeira("Bahnschrift SemiBold", "Bahnschrift", "Segoe UI Semibold", "Segoe UI"),
        numero=primeira("Bahnschrift", "Segoe UI"),
        corpo=primeira("Segoe UI Variable Text", "Segoe UI"),
        corpo_forte=primeira("Segoe UI Variable Text Semibold", "Segoe UI Semibold", "Segoe UI"),
        mono=primeira("Cascadia Mono", "Consolas"),
        icone=primeira("Segoe Fluent Icons", "Segoe MDL2 Assets", "Segoe UI Symbol"),
    )


def fonte(tipo="corpo", tamanho=13):
    return ctk.CTkFont(family=_familias.get(tipo, "Segoe UI"), size=tamanho)


# ---------------------------------------------------------------- peças
def rotulo(pai, texto="", tipo="corpo", tamanho=13, cor=TEXTO, **kw):
    kw.setdefault("anchor", "w")
    kw.setdefault("justify", "left")
    return ctk.CTkLabel(pai, text=texto, font=fonte(tipo, tamanho), text_color=cor, **kw)


def icone(pai, nome, tamanho=16, cor=SUAVE, **kw):
    return ctk.CTkLabel(pai, text=ICONES.get(nome, nome), font=fonte("icone", tamanho), text_color=cor, **kw)


def botao(pai, texto, comando, tipo="secundario", largura=None, altura=32, **kw):
    estilos = {
        "principal": dict(fg_color=ACENTO, hover_color=ACENTO_CLARO, text_color=NO_ACENTO,
                          border_width=0, font=fonte("corpo_forte", 13)),
        "secundario": dict(fg_color=PAINEL2, hover_color=LINHA, text_color=TEXTO,
                           border_width=1, border_color=LINHA, font=fonte("corpo", 13)),
        "perigo": dict(fg_color=PERIGO_FUNDO, hover_color="#5A2622", text_color=PERIGO,
                       border_width=1, border_color="#5A2622", font=fonte("corpo", 13)),
        "fantasma": dict(fg_color="transparent", hover_color=PAINEL2, text_color=SUAVE,
                         border_width=0, font=fonte("corpo", 12)),
    }
    opcoes = dict(estilos[tipo], corner_radius=RAIO, height=altura, text_color_disabled=FRACO)
    if largura:
        opcoes["width"] = largura
    opcoes.update(kw)
    return ctk.CTkButton(pai, text=texto, command=comando, **opcoes)


def cartao(pai, **kw):
    kw.setdefault("fg_color", PAINEL)
    return ctk.CTkFrame(pai, corner_radius=RAIO, border_width=1, border_color=LINHA, **kw)


def barra(pai, valor=0.0, cor=ACENTO, altura=6, largura=200):
    b = ctk.CTkProgressBar(pai, height=altura, width=largura, corner_radius=0, border_width=0,
                           fg_color=LINHA, progress_color=cor)
    b.set(max(0.0, min(1.0, valor)))
    return b


def caixa(pai, texto, variavel, **kw):
    return ctk.CTkCheckBox(pai, text=texto, variable=variavel, corner_radius=2, border_width=2,
                           checkbox_width=18, checkbox_height=18, fg_color=ACENTO, hover_color=ACENTO_CLARO,
                           border_color=FRACO, checkmark_color=NO_ACENTO, text_color=TEXTO,
                           font=fonte("corpo", 13), **kw)


def rolavel(pai, **kw):
    kw.setdefault("fg_color", "transparent")
    return ctk.CTkScrollableFrame(pai, corner_radius=0, scrollbar_button_color=LINHA,
                                  scrollbar_button_hover_color=FRACO, **kw)


def separador(pai):
    return ctk.CTkFrame(pai, height=1, fg_color=LINHA, corner_radius=0)


class Alternador(ctk.CTkButton):
    """Botão quadrado de dois estados (ligado/desligado), no lugar da chave em pílula."""

    def __init__(self, pai, ligado: bool, comando, textos=("LIGADO", "DESLIGADO"), largura=104):
        self._textos = textos
        self._ao_clicar = comando
        super().__init__(pai, text="", width=largura, height=28, corner_radius=RAIO, border_width=1,
                         font=fonte("titulo", 11), command=self._clique)
        self.definir(ligado)

    def definir(self, ligado: bool):
        self.ligado = bool(ligado)
        if self.ligado:
            self.configure(text=self._textos[0], fg_color=ACENTO_FUNDO, hover_color="#3A2E17",
                           border_color=ACENTO, text_color=ACENTO)
        else:
            self.configure(text=self._textos[1], fg_color=PAINEL2, hover_color=LINHA,
                           border_color=LINHA, text_color=FRACO)

    def _clique(self):
        self._ao_clicar(self, not self.ligado)


def ao_clicar(widget, funcao):
    """Liga o clique num quadro e em tudo dentro dele."""
    widget.bind("<Button-1>", lambda e: funcao())
    for filho in widget.winfo_children():
        ao_clicar(filho, funcao)


def cor_do_uso(fracao: float) -> str:
    if fracao >= 0.9:
        return PERIGO
    if fracao >= 0.75:
        return ACENTO
    return OK
