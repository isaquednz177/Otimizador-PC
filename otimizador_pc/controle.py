# -*- coding: utf-8 -*-
"""
Cancelar e mostrar progresso de tarefas longas.

A tarefa recebe um `Controle` e chama `checar()` de vez em quando: se a
pessoa clicou em "cancelar", sai uma exceção `Cancelado` e a tarefa para
no próximo ponto seguro (nunca no meio de uma gravação).
"""

import threading


class Cancelado(Exception):
    pass


class Controle:
    def __init__(self, progresso=None):
        self._parar = threading.Event()
        self.progresso = progresso  # função (texto, fração 0..1 ou None)

    def parar(self):
        self._parar.set()

    def parado(self) -> bool:
        return self._parar.is_set()

    def checar(self):
        if self._parar.is_set():
            raise Cancelado()

    def avisar(self, texto: str, fracao=None):
        if self.progresso:
            self.progresso(texto, fracao)


def nulo() -> Controle:
    """Um controle que nunca cancela (para chamadas sem tela)."""
    return Controle()
