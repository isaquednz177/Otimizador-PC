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

import html
import os
import re
import time
from dataclasses import dataclass

from otimizador_pc.sistema import REG_BINARY, eh_servico_de_terceiro, tarefa_ativa_do_xml

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


# ================================================================ tarefas agendadas
# Os programas também se escondem em tarefas agendadas (atualizadores do
# Chrome, Edge, Brave, Acer...). Mostramos as que NÃO são do Windows
# (fora da pasta \Microsoft\). Desligar é o mesmo que no Agendador de Tarefas.

GATILHOS = {
    "LogonTrigger": "ao entrar na conta",
    "BootTrigger": "ao ligar o PC",
    "CalendarTrigger": "em horários marcados",
    "TimeTrigger": "em horários marcados",
    "IdleTrigger": "com o PC parado",
    "EventTrigger": "quando algo acontece no Windows",
    "SessionStateChangeTrigger": "ao desbloquear ou conectar",
    "RegistrationTrigger": "ao ser criada",
}


@dataclass
class TarefaInicio:
    caminho: str
    nome: str
    autor: str
    comando: str
    gatilhos: list
    ativa: bool

    @property
    def atualizador(self):
        return "update" in self.caminho.lower() or "update" in self.comando.lower()

    @property
    def quando(self):
        textos = [GATILHOS.get(g, "") for g in self.gatilhos]
        textos = [t for i, t in enumerate(textos) if t and t not in textos[:i]]
        return ", ".join(textos) or "só quando chamada"


def ler_tarefa(xml: str, caminho: str):
    """TarefaInicio a partir do XML da tarefa (o arquivo em System32\\Tasks)."""
    ativa = tarefa_ativa_do_xml(xml)
    if ativa is None:
        return None
    gat = re.search(r"<Triggers>(.*?)</Triggers>", xml, re.S)
    gatilhos = re.findall(r"<(\w+Trigger)\b", gat.group(1)) if gat else []
    autor = re.search(r"<Author>([^<]*)</Author>", xml)
    cmd = re.search(r"<Command>([^<]*)</Command>", xml)
    args = re.search(r"<Arguments>([^<]*)</Arguments>", xml)
    comando = (cmd.group(1).strip() if cmd else "") + (" " + args.group(1).strip() if args else "")
    return TarefaInicio(caminho, caminho.rsplit("\\", 1)[-1], autor.group(1).strip() if autor else "",
                        html.unescape(comando.strip()), gatilhos, ativa)


def _texto_do_arquivo(dados: bytes) -> str:
    if dados.startswith(b"\xff\xfe") or dados.startswith(b"\xfe\xff"):
        return dados.decode("utf-16", errors="replace")
    if len(dados) > 1 and dados[1:2] == b"\x00":
        return dados.decode("utf-16-le", errors="replace")
    return dados.decode("utf-8-sig", errors="replace")


def listar_tarefas(pasta: str = None) -> list:
    pasta = pasta or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "Tasks")
    tarefas = []
    for raiz, dirs, arquivos in os.walk(pasta):
        if os.path.normcase(raiz) == os.path.normcase(pasta):
            dirs[:] = [d for d in dirs if d.lower() != "microsoft"]  # as do Windows ficam de fora
        for nome in arquivos:
            completo = os.path.join(raiz, nome)
            try:
                with open(completo, "rb") as f:
                    xml = _texto_do_arquivo(f.read(256 * 1024))
            except OSError:
                continue
            caminho = "\\" + os.path.relpath(completo, pasta)
            t = ler_tarefa(xml, caminho)
            if t:
                tarefas.append(t)
    tarefas.sort(key=lambda t: t.nome.lower())
    return tarefas


# ================================================================ serviços de outros programas
# Só troca entre "automático" e "manual". Manual = o serviço só abre quando o
# programa dele pede, que é o certo para MySQL, atualizadores etc. Nunca
# "desativado" (isso quebra o programa). Como estava fica no backup.

@dataclass
class ServicoInicio:
    nome: str
    exibicao: str
    caminho: str
    automatico: bool

    @property
    def atualizador(self):
        return "update" in self.nome.lower() or "update" in self.caminho.lower()


def listar_servicos(s, backup) -> list:
    mexidos = backup.dados.get("servicos_terceiros", {})
    saida = []
    for nome in s.reg_subchaves("HKLM", r"SYSTEM\CurrentControlSet\Services"):
        info = s.servico_info(nome)
        if not info or not eh_servico_de_terceiro(nome, info["tipo"], info["caminho"]):
            continue
        if info["start"] == 2 or (info["start"] == 3 and nome in mexidos):
            saida.append(ServicoInicio(nome, info["exibicao"], info["caminho"], info["start"] == 2))
    saida.sort(key=lambda x: x.exibicao.lower())
    return saida


def definir_servico(s, backup, item: ServicoInicio, ligar: bool) -> tuple:
    mexidos = backup.dados.setdefault("servicos_terceiros", {})
    if not ligar:
        info = s.servico_info(item.nome)
        if info is None:
            return False, "serviço não existe"
        if item.nome not in mexidos:
            mexidos[item.nome] = {"start": info["start"], "atrasado": info["atrasado"]}
            backup.salvar()  # como estava vai para o disco antes
        ok, msg = s.servico_terceiro_definir(item.nome, 3)
    else:
        original = mexidos.get(item.nome, {"start": 2, "atrasado": False})
        ok, msg = s.servico_terceiro_definir(item.nome, 2, bool(original.get("atrasado")))
        if ok:
            mexidos.pop(item.nome, None)
            backup.salvar()
    if ok:
        item.automatico = ligar
        return True, "abre com o Windows" if ligar else "só quando o programa pedir (manual)"
    return False, msg


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
