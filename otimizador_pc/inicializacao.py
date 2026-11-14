# -*- coding: utf-8 -*-
"""
Programas que abrem junto com o Windows.

Usa o MESMO mecanismo do Gerenciador de Tarefas (aba Inicializar): uma marca
em ...\\Explorer\\StartupApproved. Nada é apagado; desligar e ligar é só
trocar a marca, e o que você fizer aqui aparece igual no Gerenciador de
Tarefas (e vice-versa).

A versão 1.1 APAGAVA o item da chave Run. Esses itens estão guardados no
backup ("inicializacao_removida") e podem ser restaurados por aqui.
"""

import os
import time
from dataclasses import dataclass

from otimizador_pc.sistema import REG_BINARY

APROVADO = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

# (fonte, hive, chave Run, subchave em StartupApproved, quem)
CHAVES_RUN = [
    ("run_usuario", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run", "só você"),
    ("run_todos", "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "Run", "todos os usuários"),
    ("run_todos32", "HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32",
     "todos os usuários"),
]


def pastas_inicializar():
    """(fonte, hive, pasta, subchave, quem) das pastas Inicializar."""
    saida = []
    if os.environ.get("APPDATA"):
        saida.append(("pasta_usuario", "HKCU", os.path.join(
            os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
            "StartupFolder", "só você"))
    saida.append(("pasta_todos", "HKLM", os.path.join(
        os.environ.get("ProgramData", r"C:\ProgramData"), "Microsoft", "Windows", "Start Menu",
        "Programs", "StartUp"), "StartupFolder", "todos os usuários"))
    return saida


@dataclass
class ItemInicio:
    fonte: str
    hive: str
    nome: str
    comando: str
    subchave: str
    quem: str
    ativo: bool

    @property
    def chave(self):
        return f"{self.fonte}:{self.nome}"


def ativo_pela_marca(marca) -> bool:
    """Sem marca = ligado. Primeiro byte par (02, 06) = ligado; ímpar (03, 07) = desligado."""
    if marca is None:
        return True
    valor = marca[0]
    if isinstance(valor, (bytes, bytearray)) and len(valor) > 0:
        return valor[0] % 2 == 0
    return True


def marca(ligar: bool, agora: float = None) -> bytes:
    """12 bytes como o Gerenciador de Tarefas grava (desligado leva a hora, em FILETIME)."""
    if ligar:
        return bytes([2]) + bytes(11)
    instante = time.time() if agora is None else agora
    filetime = int((instante + 11644473600) * 10_000_000)
    return bytes([3, 0, 0, 0]) + filetime.to_bytes(8, "little")


def listar(s) -> list:
    itens = []
    for fonte, hive, chave, sub, quem in CHAVES_RUN:
        for nome, valor, _tipo in s.reg_listar(hive, chave):
            if not nome:
                continue
            m = s.reg_ler(hive, f"{APROVADO}\\{sub}", nome)
            itens.append(ItemInicio(fonte, hive, nome, str(valor), sub, quem, ativo_pela_marca(m)))
    for fonte, hive, pasta, sub, quem in pastas_inicializar():
        for arquivo in s.listar_pasta(pasta):
            if arquivo.lower() == "desktop.ini":
                continue
            m = s.reg_ler(hive, f"{APROVADO}\\{sub}", arquivo)
            itens.append(ItemInicio(fonte, hive, arquivo, os.path.join(pasta, arquivo), sub, quem,
                                    ativo_pela_marca(m)))
    itens.sort(key=lambda i: i.nome.lower())
    return itens


def definir(s, item: ItemInicio, ligar: bool) -> tuple:
    try:
        s.reg_escrever(item.hive, f"{APROVADO}\\{item.subchave}", item.nome, REG_BINARY, marca(ligar))
    except PermissionError:
        return False, "sem permissão (abra como Administrador)"
    except OSError as e:
        return False, str(e)
    item.ativo = ligar
    return True, "ligado" if ligar else "desligado"


def restaurar_removido(s, backup, chave: str) -> tuple:
    """Põe de volta na chave Run um item que a versão 1.1 apagou."""
    removidos = backup.dados.get("inicializacao_removida", {})
    item = removidos.get(chave)
    if not item:
        return False, "não está mais no backup"
    try:
        s.reg_escrever(item["hive"], item["caminho"], item["nome"], item["tipo"], item["valor"])
    except PermissionError:
        return False, "sem permissão (abra como Administrador)"
    except OSError as e:
        return False, str(e)
    del removidos[chave]
    backup.salvar()
    return True, "restaurado"
