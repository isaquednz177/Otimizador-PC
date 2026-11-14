# -*- coding: utf-8 -*-
"""Utilidades pequenas, sem nada de Windows."""

import os
from datetime import datetime

APP_DADOS = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "OtimizadorPC")
ARQUIVO_BACKUP = os.path.join(APP_DADOS, "backup_estado.json")
PASTA_LOGS = os.path.join(APP_DADOS, "logs")


def formatar_tamanho(n) -> str:
    """1536 -> '1,5 KB'. Vírgula decimal, como no Brasil."""
    if n is None:
        return "?"
    valor = float(n)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if abs(valor) < 1024 or unidade == "TB":
            if unidade == "B":
                return f"{int(valor)} B"
            return f"{valor:.1f} {unidade}".replace(".", ",")
        valor /= 1024
    return f"{valor:.1f} TB".replace(".", ",")


def agora_texto() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
