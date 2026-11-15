# -*- coding: utf-8 -*-
"""As páginas do programa, na ordem do menu: (chave, nome no menu, classe)."""

from otimizador_pc.telas.ajuda import Ajuda
from otimizador_pc.telas.ajustes import Ajustes
from otimizador_pc.telas.desempenho import Desempenho
from otimizador_pc.telas.desinstalar import Desinstalar
from otimizador_pc.telas.espaco import Espaco
from otimizador_pc.telas.hardware import Hardware
from otimizador_pc.telas.inicializacao import Inicializacao
from otimizador_pc.telas.inicio import Inicio
from otimizador_pc.telas.limpeza import Limpeza
from otimizador_pc.telas.medicoes import Medicoes
from otimizador_pc.telas.modo_jogo import ModoJogo
from otimizador_pc.telas.registro import RegistroPagina
from otimizador_pc.telas.reverter import Reverter

PAGINAS = [
    ("inicio", "Início", Inicio),
    ("desempenho", "Desempenho", Desempenho),
    ("modo_jogo", "Modo jogo", ModoJogo),
    ("limpeza", "Limpeza", Limpeza),
    ("espaco", "Espaço no disco", Espaco),
    ("desinstalar", "Desinstalar programas", Desinstalar),
    ("ajustes", "Ajustes do Windows", Ajustes),
    ("inicializacao", "Abrem com o Windows", Inicializacao),
    ("hardware", "Peças do PC", Hardware),
    ("medicoes", "Tempo para ligar", Medicoes),
    ("reverter", "Desfazer ajustes", Reverter),
    ("registro", "Histórico", RegistroPagina),
    ("ajuda", "Ajuda", Ajuda),
]
