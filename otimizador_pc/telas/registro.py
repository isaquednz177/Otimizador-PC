# -*- coding: utf-8 -*-
"""Registro: tudo o que o programa fez nesta sessão (também salvo em arquivo)."""

import os

import customtkinter as ctk

from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import PASTA_LOGS


class RegistroPagina(Pagina):
    titulo = "Histórico"
    subtitulo = "Tudo o que o programa fez desde que foi aberto, linha por linha. Útil se algo der errado: dá para mandar para alguém ajudar."

    def montar(self):
        self.botao_topo("abrir a pasta dos registros", lambda: self.s.abrir_no_explorador(PASTA_LOGS))
        self.caixa = ctk.CTkTextbox(self.corpo, corner_radius=t.RAIO, border_width=1, border_color=t.LINHA,
                                    fg_color=t.PAINEL, text_color=t.TEXTO, font=t.fonte("mono", 12),
                                    scrollbar_button_color=t.LINHA, wrap="word")
        self.caixa.pack(fill="both", expand=True)
        for linha in self.j.linhas_log:
            self.caixa.insert("end", linha + "\n")
        self.caixa.see("end")
        if self.log.arquivo:
            t.rotulo(self.corpo, f"arquivo desta sessão: {os.path.basename(self.log.arquivo)}", "corpo", 11,
                     t.FRACO).pack(anchor="w", pady=(8, 0))

    def acrescentar(self, linha):
        self.caixa.insert("end", linha + "\n")
        self.caixa.see("end")
