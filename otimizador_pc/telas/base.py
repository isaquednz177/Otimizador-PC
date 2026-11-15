# -*- coding: utf-8 -*-
"""Base das páginas: título, subtítulo e um lugar para os botões no topo."""

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
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 14))
        topo.grid_columnconfigure(0, weight=1)
        t.rotulo(topo, self.titulo, "titulo", 24).grid(row=0, column=0, sticky="w")
        if self.subtitulo:
            t.rotulo(topo, self.subtitulo, "corpo", 12, t.SUAVE, wraplength=820).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        # quadro dos botões do topo; sem tamanho próprio (vazio, o padrão seria 200 x 200)
        self.acoes = ctk.CTkFrame(topo, fg_color="transparent", width=1, height=1)
        self.acoes.grid(row=0, column=1, sticky="e")
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self.corpo.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 18))
        self.grid_rowconfigure(1, weight=1)
        self.montar()

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
