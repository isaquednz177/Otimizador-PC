# -*- coding: utf-8 -*-
"""Preferências da pessoa (ex.: o que fechar no modo jogo), num JSON em %APPDATA%\\OtimizadorPC."""

import json
import os

from otimizador_pc.backup import Backup
from otimizador_pc.util import APP_DADOS

ARQUIVO = os.path.join(APP_DADOS, "config.json")

PADRAO = {"modo_jogo": {"fechar": [], "desempenho": True, "reabrir": True}}


class Config:
    def __init__(self, arquivo: str = ARQUIVO):
        self.arquivo = arquivo
        self.dados = json.loads(json.dumps(PADRAO))
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                lido = json.load(f)
            if isinstance(lido, dict):
                for chave, valor in lido.items():
                    if isinstance(valor, dict) and isinstance(self.dados.get(chave), dict):
                        self.dados[chave].update(valor)
                    else:
                        self.dados[chave] = valor
        except (OSError, ValueError):
            pass

    def salvar(self):
        Backup._gravar_bruto(self.arquivo, self.dados)
