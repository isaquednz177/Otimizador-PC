# -*- coding: utf-8 -*-
"""
Registro de atividades: vai para a tela e para um arquivo por sessão em
%APPDATA%\\OtimizadorPC\\logs (ficam os 30 mais novos).

Pode ser chamado de qualquer thread: a tela lê as linhas de uma fila.
"""

import glob
import os
import queue
import threading
from datetime import datetime


class Registro:
    MANTER = 30

    def __init__(self, pasta: str):
        self.fila = queue.Queue()
        self._trava = threading.Lock()
        self.arquivo = None
        try:
            os.makedirs(pasta, exist_ok=True)
            self.arquivo = os.path.join(pasta, datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".log")
            antigos = sorted(glob.glob(os.path.join(pasta, "*.log")))
            for velho in antigos[:-self.MANTER]:
                try:
                    os.remove(velho)
                except OSError:
                    pass
        except OSError:
            self.arquivo = None

    def __call__(self, texto: str) -> None:
        linha = f"[{datetime.now().strftime('%H:%M:%S')}] {texto}"
        self.fila.put(linha)
        if self.arquivo:
            with self._trava:
                try:
                    with open(self.arquivo, "a", encoding="utf-8") as f:
                        f.write(linha + "\n")
                except OSError:
                    pass
