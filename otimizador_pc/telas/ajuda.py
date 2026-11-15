# -*- coding: utf-8 -*-
"""Ajuda: como usar em 3 passos, o que as etiquetas querem dizer, o que o programa nunca faz e o glossário."""

import customtkinter as ctk

from otimizador_pc import explicar as ex
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina

PASSOS = [
    ("Olhe o Início", "A frase de cima diz como o PC está agora, e \"O que vale a pena fazer\" lista o que ajudaria. "
                      "Cada recomendação tem um botão que leva direto para o lugar certo."),
    ("Faça uma limpeza", "Na página Limpeza, clique em \"ver quanto libera\" (não apaga nada) e depois em \"limpar o "
                         "que está marcado\". O que já vem marcado é seguro."),
    ("Escolha alguns ajustes", "Em Ajustes do Windows, marque os que têm a etiqueta \"seguro\" e clique em \"fazer o "
                               "que está marcado\". Se não gostar de algum, a página \"Desfazer ajustes\" volta "
                               "exatamente como estava."),
]

NUNCA = [
    "Apagar seus arquivos pessoais (fotos, documentos, músicas, jogos).",
    "Mexer em peças importantes do Windows ou no antivírus.",
    "Fazer um ajuste sem antes guardar como estava (tudo pode ser desfeito).",
    "Mandar informações suas para algum lugar.",
]


class Ajuda(Pagina):
    titulo = "Ajuda"
    subtitulo = "Para quem não entende de computador: como usar, o que é seguro e o que cada palavra quer dizer."

    def montar(self):
        area = t.rolavel(self.corpo)
        area.pack(fill="both", expand=True)
        area.grid_columnconfigure((0, 1), weight=1, uniform="ajuda")

        c = self._cartao(area, 0, 0, "Como usar em 3 passos", colspan=2)
        linha = ctk.CTkFrame(c, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=(4, 18))
        for i, (titulo, texto) in enumerate(PASSOS):
            linha.grid_columnconfigure(i, weight=1, uniform="passos")
            f = ctk.CTkFrame(linha, fg_color=t.PAINEL2, corner_radius=0)
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 2 else 6))
            t.rotulo(f, str(i + 1), "numero", 30, t.ACENTO).pack(anchor="w", padx=14, pady=(10, 0))
            t.rotulo(f, titulo, "titulo", 14).pack(anchor="w", padx=14)
            t.texto_longo(f, texto, "corpo", 12, t.SUAVE).pack(fill="x", padx=14, pady=(4, 14))

        c = self._cartao(area, 1, 0, "O que as etiquetas querem dizer")
        for nivel in ("seguro", "cuidado", "avancado"):
            texto, cor, explicacao = t.NIVEIS[nivel]
            f = ctk.CTkFrame(c, fg_color="transparent")
            f.pack(fill="x", padx=18, pady=(6, 0))
            t.rotulo(f, texto, "titulo", 13, cor).pack(anchor="w")
            t.texto_longo(f, explicacao, "corpo", 12, t.SUAVE).pack(fill="x")
        ctk.CTkFrame(c, height=14, width=10, fg_color="transparent").pack(pady=(0, 3))

        c = self._cartao(area, 1, 1, "O que este programa nunca faz")
        for texto in NUNCA:
            f = ctk.CTkFrame(c, fg_color="transparent")
            f.pack(fill="x", padx=18, pady=(6, 0))
            t.rotulo(f, "✖", "corpo", 12, t.ACENTO).pack(side="left", anchor="n", padx=(0, 10))
            t.texto_longo(f, texto, "corpo", 12, t.TEXTO).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(c, height=14, width=10, fg_color="transparent").pack(pady=(0, 3))

        c = self._cartao(area, 2, 0, "O que cada palavra quer dizer", colspan=2)
        grade = ctk.CTkFrame(c, fg_color="transparent")
        grade.pack(fill="x", padx=18, pady=(4, 16))
        grade.grid_columnconfigure((0, 1), weight=1, uniform="glossario")
        for i, (termo, texto) in enumerate(ex.GLOSSARIO):
            f = ctk.CTkFrame(grade, fg_color="transparent")
            f.grid(row=i // 2, column=i % 2, sticky="new", padx=(0, 16), pady=(6, 4))
            t.rotulo(f, termo, "titulo", 13, t.TEXTO).pack(anchor="w")
            t.texto_longo(f, texto, "corpo", 12, t.SUAVE).pack(fill="x")

    def _cartao(self, pai, linha, coluna, titulo, colspan=1):
        c = t.cartao(pai)
        c.grid(row=linha, column=coluna, columnspan=colspan, sticky="nsew",
               padx=(0 if coluna == 0 else 7, 0 if coluna + colspan >= 2 else 7), pady=(0, 14))
        t.rotulo(c, titulo, "titulo", 15, t.TEXTO).pack(anchor="w", padx=18, pady=(16, 6))
        return c
