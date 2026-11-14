# -*- coding: utf-8 -*-
"""RAM e espaço no disco do sistema, só leitura."""

import ctypes
import os
import shutil


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
    """{"ram_total", "ram_usada", "ram_pct", "disco_total", "disco_livre"} (zeros se falhar)."""
    dados = {"ram_total": 0, "ram_usada": 0, "ram_pct": 0, "disco_total": 0, "disco_livre": 0}
    try:
        m = _MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            dados.update(ram_total=m.ullTotalPhys, ram_usada=m.ullTotalPhys - m.ullAvailPhys,
                         ram_pct=int(m.dwMemoryLoad))
    except Exception:
        pass
    try:
        uso = shutil.disk_usage(disco_do_sistema())
        dados.update(disco_total=uso.total, disco_livre=uso.free)
    except OSError:
        pass
    return dados
