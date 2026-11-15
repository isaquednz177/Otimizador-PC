# -*- coding: utf-8 -*-
"""RAM, processador e espaço no disco do sistema, só leitura."""

import ctypes
import os
import shutil
from collections import deque
from ctypes import wintypes


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def disco_do_sistema() -> str:
    return os.environ.get("SystemDrive", "C:") + "\\"


def espaco_livre():
    try:
        return shutil.disk_usage(disco_do_sistema()).free
    except OSError:
        return None


def resumo() -> dict:
    """RAM e disco (zeros se falhar). `comprometida`/`limite`: memória prometida aos programas
    (RAM + arquivo de paginação); quando chega no limite, o Windows começa a fechar coisas."""
    dados = {"ram_total": 0, "ram_usada": 0, "ram_pct": 0, "comprometida": 0, "limite": 0,
             "disco_total": 0, "disco_livre": 0}
    try:
        m = _MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            dados.update(ram_total=m.ullTotalPhys, ram_usada=m.ullTotalPhys - m.ullAvailPhys,
                         ram_pct=int(m.dwMemoryLoad),
                         comprometida=m.ullTotalPageFile - m.ullAvailPageFile, limite=m.ullTotalPageFile)
    except Exception:
        pass
    try:
        uso = shutil.disk_usage(disco_do_sistema())
        dados.update(disco_total=uso.total, disco_livre=uso.free)
    except OSError:
        pass
    return dados


def uso_do_processador(antes: tuple, depois: tuple):
    """% do processador entre duas leituras (ocioso, kernel, usuário). O kernel inclui o ocioso."""
    ocioso = depois[0] - antes[0]
    total = (depois[1] - antes[1]) + (depois[2] - antes[2])
    if total <= 0:
        return None
    return max(0.0, min(100.0, (total - ocioso) / total * 100))


class Processador:
    """Uso total do processador, como o Gerenciador de Tarefas (GetSystemTimes)."""

    def __init__(self):
        self._antes = self._tempos()

    @staticmethod
    def _tempos():
        ocioso, kernel, usuario = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        try:
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(ocioso), ctypes.byref(kernel),
                                                         ctypes.byref(usuario)):
                return None
        except Exception:
            return None

        def n(ft):
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        return n(ocioso), n(kernel), n(usuario)

    def ler(self):
        agora = self._tempos()
        if agora is None or self._antes is None:
            self._antes = agora
            return None
        pct = uso_do_processador(self._antes, agora)
        self._antes = agora
        return pct


class Historico:
    """As últimas leituras de memória e processador (uma a cada 2 s: 90 = 3 minutos)."""

    def __init__(self, tamanho: int = 90):
        self.memoria = deque(maxlen=tamanho)
        self.processador = deque(maxlen=tamanho)

    def guardar(self, memoria_pct, processador_pct):
        if memoria_pct is not None:
            self.memoria.append(float(memoria_pct))
        if processador_pct is not None:
            self.processador.append(float(processador_pct))

    @staticmethod
    def pico_e_media(valores):
        valores = list(valores)
        if not valores:
            return None, None
        return max(valores), sum(valores) / len(valores)


def composicao_da_memoria(total: int, usada: int, grupos: list, destaques: int = 6) -> list:
    """
    Divide a memória: os `destaques` programas que mais usam, os outros programas,
    o que é do Windows (drivers, sistema e cache) e o livre.
    grupos: [(nome, bytes)] em ordem decrescente. Devolve [(nome, bytes, tipo)].
    """
    partes = []
    soma = 0
    for nome, tam in grupos[:destaques]:
        partes.append((nome, tam, "programa"))
        soma += tam
    outros = sum(t for _, t in grupos[destaques:])
    if outros > 0:
        partes.append(("outros programas", outros, "outros"))
        soma += outros
    windows = max(0, usada - soma)
    if windows > 0:
        partes.append(("Windows, drivers e cache", windows, "windows"))
    livre = max(0, total - max(usada, soma))
    partes.append(("livre", livre, "livre"))
    return partes
