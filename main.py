# -*- coding: utf-8 -*-
"""
Abre o Otimizador PC.

Sem Administrador, ele pede (o aviso do Windows). Se você recusar, ele abre
mesmo assim, só para olhar: dá para analisar, mas não para mudar o sistema.
`--sem-admin` abre direto sem pedir (útil para testar a tela).
"""

import ctypes
import os
import subprocess
import sys


def eh_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def pedir_admin() -> bool:
    """Reabre o programa como Administrador. True se o Windows aceitou."""
    if getattr(sys, "frozen", False):
        alvo, args = sys.executable, sys.argv[1:]
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        alvo = pythonw if os.path.exists(pythonw) else sys.executable
        args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
    try:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", alvo, subprocess.list2cmdline(args), None, 1)
        return r > 32  # abaixo de 32 = erro ou recusado
    except Exception:
        return False


def main():
    if os.name != "nt":
        print("O Otimizador PC só funciona no Windows.")
        return
    admin = eh_admin()
    if not admin and "--sem-admin" not in sys.argv and pedir_admin():
        return  # quem continua é a cópia com Administrador
    try:
        # um "nome de app" próprio: a barra de tarefas mostra o ícone do Otimizador, e não o do Python
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Billy.OtimizadorPC")
    except Exception:
        pass
    from otimizador_pc.interface import abrir
    abrir(admin)


if __name__ == "__main__":
    main()
