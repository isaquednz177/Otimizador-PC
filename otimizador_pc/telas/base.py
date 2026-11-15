# -*- coding: utf-8 -*-
"""Base das páginas: o letreiro gótico no topo, os botões à direita e o corpo."""

import customtkinter as ctk

from otimizador_pc import tema as t


class Pagina(ctk.CTkFrame):
    titulo = ""
    subtitulo = ""

    def __init__(self, janela, pai):
        super().__init__(pai, fg_color=t.FUNDO, corner_radius=0)
        self.j = janela
        self.visivel = False
        self.grid_columnconfigure(0, weight=1)
        self.letreiro = t.Letreiro(self, self.titulo, self.subtitulo, tamanho=26)
        self.letreiro.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 14))
        # botões do topo, por cima do letreiro, à direita
        self.acoes = ctk.CTkFrame(self, fg_color=t.FUNDO, corner_radius=0, width=1, height=1)
        self.acoes.place(relx=1.0, x=-40, y=34, anchor="ne")
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self.corpo.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 18))
        self.grid_rowconfigure(1, weight=1)
        self.montar()
        self.acoes.lift()

    # para as páginas
    def montar(self):
        pass

    def ao_mostrar(self):
        self.visivel = True

    def ao_esconder(self):
        self.visivel = False

    def botao_topo(self, texto, comando, tipo="secundario", acao=False, largura=None):
        b = t.botao(self.acoes, texto, comando, tipo, largura=largura)
        b.pack(side="left", padx=(8, 0))
        if acao:
            self.j.registrar_botao(b)
        return b

    @property
    def s(self):
        return self.j.s

    @property
    def log(self):
        return self.j.log
