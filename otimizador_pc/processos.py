# -*- coding: utf-8 -*-
"""
O que está pesando agora: memória e processador por programa.

Uma única chamada ao Windows (NtQuerySystemInformation) traz todos os
processos com o "conjunto de trabalho privado", que é o MESMO número da
coluna Memória do Gerenciador de Tarefas. O uso do processador sai da
diferença de tempo entre duas leituras.

Processos com o mesmo .exe viram um grupo só (as 30 abas do Chrome
aparecem como "Google Chrome").
"""

import ctypes
import os
import re
import time
from ctypes import wintypes
from dataclasses import dataclass, field

# Processos do Windows que nunca ganham o botão "fechar".
PROTEGIDOS = frozenset({
    "", "idle", "system", "registry", "secure system", "memory compression", "memcompression",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "lsaiso.exe",
    "svchost.exe", "dwm.exe", "fontdrvhost.exe", "explorer.exe", "sihost.exe", "ctfmon.exe",
    "audiodg.exe", "spoolsv.exe", "wudfhost.exe", "conhost.exe", "runtimebroker.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe", "taskhostw.exe",
    "dllhost.exe", "smartscreen.exe", "msmpeng.exe", "nissrv.exe", "mpdefendercoreservice.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe", "lockapp.exe", "userinit.exe",
    "applicationframehost.exe", "systemsettings.exe", "taskmgr.exe", "wmiprvse.exe",
    "searchindexer.exe", "sgrmbroker.exe", "lsm.exe", "csrss", "vmmem", "vmmemws",
})


@dataclass
class Grupo:
    exe: str
    nome: str
    pids: list = field(default_factory=list)
    memoria: int = 0
    cpu: float = None          # % do processador inteiro; None na primeira leitura
    caminho: str = ""
    servico: bool = True       # True se todos rodam na sessão 0 (serviços)

    @property
    def qtd(self):
        return len(self.pids)

    @property
    def pode_fechar(self):
        return not self.servico and self.exe not in PROTEGIDOS


def agrupar(processos: list, nomes=None) -> list:
    """
    processos: dicts {pid, exe, memoria, cpu, sessao, caminho}.
    Devolve grupos ordenados pela memória (maior primeiro).
    """
    nomes = nomes or {}
    grupos = {}
    for p in processos:
        exe = (p.get("exe") or "").lower()
        g = grupos.get(exe)
        if g is None:
            g = grupos[exe] = Grupo(exe=exe, nome=nomes.get(exe) or p.get("exe") or "Sistema")
        g.pids.append(p["pid"])
        g.memoria += p.get("memoria") or 0
        if p.get("cpu") is not None:
            g.cpu = (g.cpu or 0.0) + p["cpu"]
        if p.get("sessao", 0) != 0:
            g.servico = False
        if not g.caminho and p.get("caminho"):
            g.caminho = p["caminho"]
    return sorted(grupos.values(), key=lambda g: g.memoria, reverse=True)


def exe_do_comando(comando: str) -> str:
    """'"C:\\Steam\\steam.exe" -silent' -> 'steam.exe'."""
    m = re.search(r"([^\\/\"]+?\.exe)\b", comando or "", re.I)
    return m.group(1).lower() if m else ""


# ---------------------------------------------------------------- Windows
class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]


class _SPI(ctypes.Structure):
    """SYSTEM_PROCESS_INFORMATION (só o começo, que é o que usamos)."""
    _fields_ = [
        ("NextEntryOffset", ctypes.c_ulong), ("NumberOfThreads", ctypes.c_ulong),
        ("WorkingSetPrivateSize", ctypes.c_longlong), ("HardFaultCount", ctypes.c_ulong),
        ("NumberOfThreadsHighWatermark", ctypes.c_ulong), ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong), ("UserTime", ctypes.c_longlong), ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UNICODE_STRING), ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_void_p), ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", ctypes.c_ulong), ("SessionId", ctypes.c_ulong),
    ]


def _ler_todos() -> list:
    """[(pid, exe, memória privada, tempo de CPU em 100 ns, sessão)]"""
    ntdll = ctypes.WinDLL("ntdll")
    tamanho = 1 << 20
    while True:
        buf = ctypes.create_string_buffer(tamanho)
        preciso = ctypes.c_ulong(0)
        status = ntdll.NtQuerySystemInformation(5, buf, tamanho, ctypes.byref(preciso)) & 0xFFFFFFFF
        if status == 0xC0000004:  # buffer pequeno: tenta com folga
            tamanho = max(preciso.value, tamanho) + (256 << 10)
            continue
        if status != 0:
            return []
        break
    saida, pos = [], 0
    base = ctypes.addressof(buf)
    while True:
        spi = _SPI.from_address(base + pos)
        nome = ""
        if spi.ImageName.Buffer and spi.ImageName.Length:
            nome = ctypes.wstring_at(spi.ImageName.Buffer, spi.ImageName.Length // 2)
        pid = spi.UniqueProcessId or 0
        saida.append((pid, nome, spi.WorkingSetPrivateSize, spi.UserTime + spi.KernelTime, spi.SessionId))
        if not spi.NextEntryOffset:
            break
        pos += spi.NextEntryOffset
    return saida


_DLL = {}


def _kernel32():
    if "k32" not in _DLL:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        _DLL["k32"] = k32
    return _DLL["k32"]


def _caminho_do_pid(pid: int) -> str:
    k32 = _kernel32()
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(wintypes.HANDLE(h), 0, buf, ctypes.byref(n)):
            return buf.value
        return ""
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))


def _descricao(caminho: str) -> str:
    """A 'Descrição do arquivo' do .exe (ex.: 'Google Chrome')."""
    try:
        ver = _DLL.get("ver") or _DLL.setdefault("ver", ctypes.WinDLL("version"))
        tam = ver.GetFileVersionInfoSizeW(caminho, None)
        if not tam:
            return ""
        dados = ctypes.create_string_buffer(tam)
        if not ver.GetFileVersionInfoW(caminho, 0, tam, dados):
            return ""
        ptr, n = ctypes.c_void_p(), ctypes.c_uint()
        if not ver.VerQueryValueW(dados, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(n)) or n.value < 4:
            return ""
        idioma = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ushort))
        for ling, pagina in ((idioma[0], idioma[1]), (0x0409, 0x04B0), (0x0416, 0x04B0)):
            chave = f"\\StringFileInfo\\{ling:04x}{pagina:04x}\\FileDescription"
            if ver.VerQueryValueW(dados, chave, ctypes.byref(ptr), ctypes.byref(n)) and n.value > 1:
                texto = ctypes.wstring_at(ptr, n.value - 1).strip()
                if texto:
                    return texto
    except Exception:
        pass
    return ""


class Monitor:
    """Lê os processos várias vezes; da segunda leitura em diante já tem o % de processador."""

    def __init__(self):
        self._anterior = {}      # pid -> (tempo de CPU, instante)
        self._caminhos = {}      # pid -> caminho
        self._nomes = {}         # exe -> descrição
        self.nucleos = os.cpu_count() or 1
        self.meu_exe = os.path.basename(_caminho_do_pid(os.getpid()) or "").lower()

    def ler(self, mostrar: int = 30) -> list:
        """Grupos ordenados pela memória. Nome amigável e caminho só para os `mostrar` primeiros."""
        agora = time.monotonic()
        atual, lista = {}, []
        for pid, exe, mem, tempo, sessao in _ler_todos():
            if not pid:
                continue  # o "Ocioso" não é programa
            atual[pid] = (tempo, agora)
            cpu = None
            if pid in self._anterior:
                t0, i0 = self._anterior[pid]
                passou = agora - i0
                if passou > 0:
                    cpu = max(0.0, (tempo - t0) / 1e7 / passou / self.nucleos * 100)
            lista.append({"pid": pid, "exe": exe, "memoria": mem, "cpu": cpu, "sessao": sessao,
                          "caminho": self._caminhos.get(pid, "")})
        self._anterior = atual
        self._caminhos = {p: c for p, c in self._caminhos.items() if p in atual}  # esquece os que fecharam

        grupos = agrupar(lista, self._nomes)
        for g in grupos[:mostrar]:
            if not g.caminho:
                for pid in g.pids[:3]:
                    if pid not in self._caminhos:
                        self._caminhos[pid] = _caminho_do_pid(pid)
                    if self._caminhos[pid]:
                        g.caminho = self._caminhos[pid]
                        break
            if g.exe not in self._nomes:
                self._nomes[g.exe] = _descricao(g.caminho) if g.caminho else ""
            g.nome = self._nomes[g.exe] or g.nome
        for g in grupos:
            if g.exe == self.meu_exe:
                g.servico = True  # nunca oferecer fechar o próprio otimizador
        return grupos
