# -*- coding: utf-8 -*-
"""As páginas do programa, na ordem do menu: (chave, nome no menu, classe)."""

from otimizador_pc.telas.ajustes import Ajustes
from otimizador_pc.telas.desempenho import Desempenho
from otimizador_pc.telas.espaco import Espaco
from otimizador_pc.telas.inicializacao import Inicializacao
from otimizador_pc.telas.inicio import Inicio
from otimizador_pc.telas.limpeza import Limpeza
from otimizador_pc.telas.medicoes import Medicoes
from otimizador_pc.telas.registro import RegistroPagina
from otimizador_pc.telas.reverter import Reverter

PAGINAS = [
    ("inicio", "Início", Inicio),
    ("desempenho", "Desempenho", Desempenho),
    ("limpeza", "Limpeza", Limpeza),
    ("espaco", "Espaço em disco", Espaco),
    ("ajustes", "Ajustes", Ajustes),
    ("inicializacao", "Inicialização", Inicializacao),
    ("medicoes", "Tempo para ligar", Medicoes),
    ("reverter", "Reverter", Reverter),
    ("registro", "Registro", RegistroPagina),
]
