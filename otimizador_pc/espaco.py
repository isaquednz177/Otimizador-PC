# -*- coding: utf-8 -*-
"""
O que ocupa o disco. Só mede e mostra: nada aqui apaga arquivos.

- Junções e links de pasta não são seguidos (senão a mesma pasta contaria duas vezes).
- Arquivos do OneDrive que estão só na nuvem contam 0 (não ocupam o disco).
- Guarda o tamanho de toda pasta com 1 MB ou mais, para navegar sem medir de novo.
"""

import heapq
import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from otimizador_pc.controle import Cancelado, nulo

REPARSE = 0x400
SO_NA_NUVEM = 0x400000 | 0x40000 | 0x1000  # RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE
LINKS_DE_PASTA = {0xA0000003, 0xA000000C}  # junção (mount point) e link simbólico

EXPLICACOES = {
    "pagefile.sys": "memória virtual do Windows (o Windows cuida do tamanho)",
    "hiberfil.sys": "arquivo da hibernação (some se desligar a hibernação)",
    "swapfile.sys": "memória virtual dos apps da Loja",
    "winsxs": "componentes do Windows; parece maior do que é (muitos arquivos são o mesmo arquivo)",
    "system volume information": "pontos de restauração (o Windows não deixa abrir)",
    "$recycle.bin": "Lixeira",
    "windows.old": "Windows anterior; o próprio Windows apaga depois de uns dias, ou pela Limpeza de Disco",
    "softwaredistribution": "atualizações do Windows (a aba Limpeza cuida dos downloads)",
    "installer": "instaladores de programas; não apague à mão",
    "node_modules": "dependências de projetos JavaScript; apagar e rodar npm install refaz",
    "steamapps": "jogos da Steam",
    ".ollama": "modelos de IA do Ollama; apague os que não usa pelo próprio Ollama (ollama list e ollama rm NOME)",
    "blobs": "partes dos modelos de IA; apague pelo programa que os baixou, não à mão",
    ".cargo": "pacotes do Rust; a pasta registry é cache e pode ser limpa com cargo-cache",
    ".rustup": "instalação do Rust (cada versão instalada ocupa espaço; rustup toolchain list)",
    ".vscode": "extensões do VS Code (desinstale as que não usa pelo próprio VS Code)",
    ".cache": "caches de vários programas de desenvolvimento",
    ".npm": "cache do npm; npm cache clean --force libera",
    "npm-cache": "cache do npm; npm cache clean --force libera",
    ".nuget": "pacotes do .NET; dotnet nuget locals all --clear libera",
    ".gradle": "cache do Gradle (Android e Java)",
    ".android": "emulador e ferramentas do Android",
    ".docker": "configurações do Docker (as imagens ficam no disco virtual do WSL)",
    "appdata": "configurações e dados dos programas; não apague à mão",
    "temp": "temporários (a página Limpeza cuida)",
    "downloads": "seus downloads: costuma juntar instaladores que não servem mais",
    "onedrive": "arquivos do OneDrive baixados no PC (os que estão só na nuvem não contam)",
    "packages": "dados dos apps da Microsoft Store",
    "crashdumps": "despejos de programas que travaram (a página Limpeza cuida)",
    "pip": "cache do pip; pip cache purge libera",
    "program files (x86)": "programas de 32 bits",
    "program files": "programas instalados; desinstale pelo Windows, não apagando a pasta",
    "programdata": "dados compartilhados dos programas; não apague à mão",
    "epic games": "jogos da Epic",
    "riot games": "jogos da Riot",
}


@dataclass
class Pasta:
    caminho: str
    total: int = 0
    soltos: int = 0          # arquivos direto nesta pasta
    filhas: list = field(default_factory=list)  # [(caminho, total)] das subpastas com 1 MB ou mais
    pequenas: int = 0        # soma das subpastas menores que 1 MB


@dataclass
class Mapa:
    raiz: str
    pastas: dict = field(default_factory=dict)   # caminho normalizado -> Pasta
    maiores: list = field(default_factory=list)  # [(tamanho, caminho)] do maior para o menor
    arquivos: int = 0
    sem_acesso: int = 0
    cancelado: bool = False

    def pasta(self, caminho: str):
        return self.pastas.get(_chave(caminho))


def _chave(caminho: str) -> str:
    return os.path.normcase(os.path.normpath(caminho))


def explicar(caminho: str) -> str:
    return EXPLICACOES.get(os.path.basename(caminho.rstrip("\\/")).lower(), "")


class _Contexto:
    def __init__(self, ctl, minimo, n_maiores):
        self.ctl, self.minimo, self.n_maiores = ctl, minimo, n_maiores
        self.trava = threading.Lock()
        self.pastas, self.maiores = {}, []
        self.arquivos = self.sem_acesso = 0
        self._desde_aviso = 0

    def arquivo(self, tamanho, caminho, local):
        local["arquivos"] += 1
        heap = local["maiores"]
        if len(heap) < self.n_maiores:
            heapq.heappush(heap, (tamanho, caminho))
        elif tamanho > heap[0][0]:
            heapq.heapreplace(heap, (tamanho, caminho))


def _medir(caminho, ctx: _Contexto, local) -> int:
    ctx.ctl.checar()
    try:
        entradas = list(os.scandir(caminho))
    except OSError:
        local["sem_acesso"] += 1
        return 0
    total = soltos = pequenas = 0
    filhas = []
    for e in entradas:
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        atrib = getattr(st, "st_file_attributes", 0)
        if stat.S_ISLNK(st.st_mode):
            continue
        if stat.S_ISDIR(st.st_mode):
            if atrib & REPARSE and getattr(st, "st_reparse_tag", 0) in LINKS_DE_PASTA:
                continue
            t = _medir(e.path, ctx, local)
            total += t
            if t >= ctx.minimo:
                filhas.append((e.path, t))
            else:
                pequenas += t
            continue
        tamanho = 0 if atrib & SO_NA_NUVEM else st.st_size
        total += tamanho
        soltos += tamanho
        ctx.arquivo(tamanho, e.path, local)
    if total >= ctx.minimo:
        filhas.sort(key=lambda f: f[1], reverse=True)
        local["pastas"][_chave(caminho)] = Pasta(caminho, total, soltos, filhas, pequenas)
    local["desde_aviso"] += 1
    if local["desde_aviso"] >= 400:
        local["desde_aviso"] = 0
        with ctx.trava:
            ctx.ctl.avisar(f"medindo... {caminho}")
    return total


def _novo_local():
    return {"pastas": {}, "maiores": [], "arquivos": 0, "sem_acesso": 0, "desde_aviso": 0}


def varrer(raiz: str, ctl=None, minimo: int = 1 << 20, n_maiores: int = 40) -> Mapa:
    """Mede `raiz` inteira. Cancelando, devolve o que já mediu com `cancelado=True`."""
    ctl = ctl or nulo()
    ctx = _Contexto(ctl, minimo, n_maiores)
    mapa = Mapa(raiz)
    raiz_local = _novo_local()
    try:
        entradas = list(os.scandir(raiz))
    except OSError:
        mapa.sem_acesso = 1
        return mapa

    subpastas, total, soltos = [], 0, 0
    for e in entradas:
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        atrib = getattr(st, "st_file_attributes", 0)
        if stat.S_ISLNK(st.st_mode):
            continue
        if stat.S_ISDIR(st.st_mode):
            if not (atrib & REPARSE and getattr(st, "st_reparse_tag", 0) in LINKS_DE_PASTA):
                subpastas.append(e.path)
            continue
        tamanho = 0 if atrib & SO_NA_NUVEM else st.st_size
        total += tamanho
        soltos += tamanho
        ctx.arquivo(tamanho, e.path, raiz_local)

    def medir_uma(caminho):
        local = _novo_local()
        try:
            t = _medir(caminho, ctx, local)
        except Cancelado:
            local["cancelado"] = True
            t = None
        return caminho, t, local

    filhas, pequenas, locais = [], 0, [raiz_local]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for caminho, t, local in pool.map(medir_uma, subpastas):
            locais.append(local)
            if local.get("cancelado"):
                mapa.cancelado = True
                continue
            total += t
            if t >= minimo:
                filhas.append((caminho, t))
            else:
                pequenas += t

    for local in locais:
        mapa.pastas.update(local["pastas"])
        mapa.arquivos += local["arquivos"]
        mapa.sem_acesso += local["sem_acesso"]
        for item in local["maiores"]:
            if len(ctx.maiores) < n_maiores:
                heapq.heappush(ctx.maiores, item)
            elif item[0] > ctx.maiores[0][0]:
                heapq.heapreplace(ctx.maiores, item)
    filhas.sort(key=lambda f: f[1], reverse=True)
    mapa.pastas[_chave(raiz)] = Pasta(raiz, total, soltos, filhas, pequenas)
    mapa.maiores = sorted(ctx.maiores, reverse=True)
    return mapa
