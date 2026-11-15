# -*- coding: utf-8 -*-
"""
Tudo o que conversa com o Windows passa por aqui (registro, serviços, tarefas
agendadas, plano de energia, hibernação, mouse, lixeira, processos).

O resto do programa recebe um objeto `Sistema` e nunca chama o Windows
direto. Assim os testes trocam o `Sistema` por um falso (tests/falso.py) e
conferem as regras sem mexer no PC de verdade.

Regra de ouro desta camada: nada de ler texto traduzido. O Windows em
português escreve "ESTADO", "TIPO_DE_INÍCIO"... Lemos só o que não muda com
o idioma: números do registro, GUIDs, o <Enabled> do XML das tarefas e os
nomes de estado do sc.exe (RUNNING, STOPPED), que ficam sempre em inglês.
"""

import ctypes
import csv
import io
import os
import re
import subprocess
import time

try:
    import winreg
except ImportError:  # fora do Windows (só para os testes importarem o módulo)
    winreg = None

# Tipos de valor do registro (iguais aos do winreg, definidos aqui para o
# módulo funcionar mesmo sem ele).
REG_SZ = 1
REG_EXPAND_SZ = 2
REG_BINARY = 3
REG_DWORD = 4
REG_MULTI_SZ = 7
REG_QWORD = 11

CREATE_NO_WINDOW = 0x08000000

# Os únicos serviços cujo tipo de início este programa pode mudar.
SERVICOS_CONFIGURAVEIS = frozenset({"DiagTrack", "dmwappushservice", "WSearch", "SysMain"})
# Os únicos que ele pode parar e ligar de novo (o Windows Update e o BITS são
# parados só durante a limpeza do cache do Windows Update, e voltam depois).
SERVICOS_PARAVEIS = SERVICOS_CONFIGURAVEIS | {"wuauserv", "BITS"}

# Start do serviço: 0 boot | 1 sistema | 2 automático | 3 manual | 4 desativado
NOME_START = {2: "auto", 3: "demand", 4: "disabled"}

GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
ESTADO_SC_RE = re.compile(
    r":\s*\d+\s+(STOPPED|START_PENDING|STOP_PENDING|RUNNING|CONTINUE_PENDING|PAUSE_PENDING|PAUSED)\b"
)


def _decodificar(dados: bytes) -> str:
    """Programas de console escrevem na página de código OEM (cp850 no Brasil)."""
    if not dados:
        return ""
    for cod in ("utf-8", "oem", "cp850"):
        try:
            return dados.decode(cod)
        except (UnicodeDecodeError, LookupError):
            continue
    return dados.decode("latin-1", errors="replace")


def estado_do_sc(saida: str):
    """Tira o estado (RUNNING, STOPPED...) da saída do `sc query`, em qualquer idioma."""
    m = ESTADO_SC_RE.search(saida or "")
    return m.group(1) if m else None


def tarefa_ativa_do_xml(xml: str):
    """
    Lê se a tarefa está ligada pelo XML do `schtasks /Query /XML`.
    O <Enabled> que vale é o de <Settings> (os gatilhos têm o deles).
    Sem <Enabled> em <Settings>, o padrão do Windows é ligada.
    """
    m = re.search(r"<Settings>(.*?)</Settings>", xml or "", re.S)
    if not m:
        return None
    bloco = re.sub(r"<IdleSettings>.*?</IdleSettings>", "", m.group(1), flags=re.S)
    e = re.search(r"<Enabled>\s*(true|false)\s*</Enabled>", bloco, re.I)
    return True if not e else e.group(1).lower() == "true"


SERVICOS_PROTEGIDOS = frozenset({
    "windefend", "mdcoresvc", "wdnissvc", "sense", "securityhealthservice", "wscsvc", "mpssvc",
    "sgrmbroker", "webthreatdefsvc", "webthreatdefusersvc",
})


def eh_servico_de_terceiro(nome: str, tipo: int, caminho: str) -> bool:
    """
    True para serviço de OUTRO programa (Steam, MySQL, atualizadores...).
    Fora: drivers, tudo dentro da pasta do Windows, o antivírus do Windows
    e a lista de proteção.
    """
    if not (int(tipo or 0) & 0x30):  # 0x10/0x20 = serviço Win32; o resto é driver
        return False
    if (nome or "").lower() in SERVICOS_PROTEGIDOS:
        return False
    c = (caminho or "").lower().replace("/", "\\")
    if not c.strip():
        return False
    proibidos = ("\\windows\\", "%systemroot%", "systemroot\\", "\\windows defender",
                 "\\microsoft\\windows defender", "system32\\")
    return not any(p in c for p in proibidos)


def processos_do_tasklist(saida: str) -> set:
    """Nomes dos processos (em minúsculas) a partir do `tasklist /FO CSV /NH`."""
    nomes = set()
    for linha in csv.reader(io.StringIO(saida or "")):
        if linha and linha[0].lower().endswith(".exe"):
            nomes.add(linha[0].lower())
    return nomes


class Sistema:
    """O Windows de verdade."""

    def __init__(self):
        if winreg:
            self._hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
            # Força a visão de 64 bits do registro mesmo se o Python for 32 bits.
            self._v64 = getattr(winreg, "KEY_WOW64_64KEY", 0)
        else:
            self._hives, self._v64 = {}, 0

    # ------------------------------------------------------------ comandos
    def rodar(self, comando: list, timeout: int = 120) -> tuple:
        """Roda um programa sem abrir janela. Devolve (código, saída). Nunca levanta erro."""
        try:
            proc = subprocess.run(
                comando, capture_output=True, shell=False,
                creationflags=CREATE_NO_WINDOW, timeout=timeout,
            )
            return proc.returncode, _decodificar(proc.stdout) + _decodificar(proc.stderr)
        except subprocess.TimeoutExpired:
            return -1, f"passou de {timeout} s sem terminar"
        except Exception as e:  # programa não existe, etc.
            return -1, str(e)

    def powershell(self, script: str, timeout: int = 120) -> tuple:
        return self.rodar(["powershell", "-NoProfile", "-NonInteractive",
                           "-ExecutionPolicy", "Bypass", "-Command", script], timeout)

    # ------------------------------------------------------------ registro
    def reg_ler(self, hive: str, caminho: str, nome: str):
        """(valor, tipo), ou None se a chave ou o valor não existem."""
        try:
            with winreg.OpenKey(self._hives[hive], caminho, 0, winreg.KEY_READ | self._v64) as k:
                return winreg.QueryValueEx(k, nome)
        except OSError:
            return None

    def reg_escrever(self, hive: str, caminho: str, nome: str, tipo: int, valor) -> None:
        """Cria a chave se preciso e grava. Levanta PermissionError/OSError se falhar."""
        with winreg.CreateKeyEx(self._hives[hive], caminho, 0, winreg.KEY_SET_VALUE | self._v64) as k:
            winreg.SetValueEx(k, nome, 0, tipo, valor)

    def reg_apagar(self, hive: str, caminho: str, nome: str) -> None:
        """Apaga um valor. Se já não existe, tudo bem. Falta de permissão levanta erro."""
        try:
            with winreg.OpenKey(self._hives[hive], caminho, 0, winreg.KEY_SET_VALUE | self._v64) as k:
                winreg.DeleteValue(k, nome)
        except FileNotFoundError:
            pass

    def reg_listar(self, hive: str, caminho: str) -> list:
        """[(nome, valor, tipo)] de uma chave; lista vazia se ela não existe."""
        itens = []
        try:
            with winreg.OpenKey(self._hives[hive], caminho, 0, winreg.KEY_READ | self._v64) as k:
                i = 0
                while True:
                    try:
                        itens.append(winreg.EnumValue(k, i))
                    except OSError:
                        break
                    i += 1
        except OSError:
            pass
        return itens

    def reg_subchaves(self, hive: str, caminho: str) -> list:
        nomes = []
        try:
            with winreg.OpenKey(self._hives[hive], caminho, 0, winreg.KEY_READ | self._v64) as k:
                i = 0
                while True:
                    try:
                        nomes.append(winreg.EnumKey(k, i))
                    except OSError:
                        break
                    i += 1
        except OSError:
            pass
        return nomes

    # ------------------------------------------------------------ serviços
    def servico_info(self, nome: str):
        """{"start", "atrasado", "tipo", "caminho", "exibicao"} lidos do registro, ou None."""
        chave = rf"SYSTEM\CurrentControlSet\Services\{nome}"
        cfg = self.servico_config(nome)
        if cfg is None:
            return None
        tipo = self.reg_ler("HKLM", chave, "Type")
        caminho = self.reg_ler("HKLM", chave, "ImagePath")
        exibicao = self.reg_ler("HKLM", chave, "DisplayName")
        nome_tela = exibicao[0] if exibicao and not str(exibicao[0]).startswith("@") else nome
        return dict(cfg, tipo=int(tipo[0]) if tipo else 0,
                    caminho=str(caminho[0]) if caminho else "", exibicao=str(nome_tela))

    def servico_terceiro_definir(self, nome: str, start: int, atrasado: bool = False) -> tuple:
        """Automático (2) ou manual (3) para serviço de outro programa. Nunca desativa."""
        info = self.servico_info(nome)
        if info is None:
            return False, "serviço não existe"
        if not eh_servico_de_terceiro(nome, info["tipo"], info["caminho"]):
            return False, "serviço do Windows: não mexo"
        if start not in (2, 3) or info["start"] not in (2, 3):
            return False, "só troco entre automático e manual"
        tipo = "delayed-auto" if (start == 2 and atrasado) else NOME_START[start]
        codigo, saida = self.rodar(["sc", "config", nome, "start=", tipo], timeout=60)
        return (True, "ok") if codigo == 0 else (False, saida.strip()[:200])

    def servico_config(self, nome: str):
        """{"start": 0..4, "atrasado": bool}, ou None se o serviço não existe."""
        chave = rf"SYSTEM\CurrentControlSet\Services\{nome}"
        start = self.reg_ler("HKLM", chave, "Start")
        if start is None:
            return None
        atrasado = self.reg_ler("HKLM", chave, "DelayedAutostart")
        return {"start": int(start[0]), "atrasado": bool(atrasado and int(atrasado[0]) == 1)}

    def servico_estado(self, nome: str):
        """"RUNNING", "STOPPED"... ou None se não deu para saber."""
        _, saida = self.rodar(["sc", "query", nome], timeout=30)
        return estado_do_sc(saida)

    def servico_definir(self, nome: str, start: int, atrasado: bool = False) -> tuple:
        if nome not in SERVICOS_CONFIGURAVEIS:
            return False, "serviço fora da lista permitida"
        if start not in NOME_START:
            return False, f"tipo de início inválido ({start})"
        cfg = self.servico_config(nome)
        if cfg is None:
            return False, "serviço não existe neste Windows"
        if cfg["start"] <= 1:
            return False, "serviço de inicialização do sistema: não mexo"
        tipo = "delayed-auto" if (start == 2 and atrasado) else NOME_START[start]
        codigo, saida = self.rodar(["sc", "config", nome, "start=", tipo], timeout=60)
        if codigo != 0:
            return False, saida.strip()[:200]
        return True, f"início = {tipo}"

    def servico_parar(self, nome: str, espera: int = 30) -> bool:
        if nome not in SERVICOS_PARAVEIS:
            return False
        if self.servico_estado(nome) in (None, "STOPPED"):
            return True
        self.rodar(["sc", "stop", nome], timeout=30)
        limite = time.monotonic() + espera
        while time.monotonic() < limite:
            if self.servico_estado(nome) == "STOPPED":
                return True
            time.sleep(0.5)
        return False

    def servico_iniciar(self, nome: str) -> bool:
        if nome not in SERVICOS_PARAVEIS:
            return False
        if self.servico_estado(nome) == "RUNNING":
            return True
        codigo, _ = self.rodar(["sc", "start", nome], timeout=30)
        return codigo == 0

    # ------------------------------------------------------------ tarefas agendadas
    def tarefa_ativa(self, caminho: str):
        """True/False, ou None se a tarefa não existe neste Windows."""
        codigo, saida = self.rodar(["schtasks", "/Query", "/TN", caminho, "/XML"], timeout=30)
        if codigo != 0:
            return None
        return tarefa_ativa_do_xml(saida)

    def tarefa_definir(self, caminho: str, ativar: bool) -> tuple:
        codigo, saida = self.rodar(
            ["schtasks", "/Change", "/TN", caminho, "/Enable" if ativar else "/Disable"], timeout=30)
        return (True, "ok") if codigo == 0 else (False, saida.strip()[:200])

    # ------------------------------------------------------------ energia
    def plano_ativo(self):
        _, saida = self.rodar(["powercfg", "/getactivescheme"], timeout=30)
        m = GUID_RE.search(saida)
        return m.group(0).lower() if m else None

    def planos(self) -> list:
        _, saida = self.rodar(["powercfg", "/list"], timeout=30)
        return [g.lower() for g in GUID_RE.findall(saida)]

    def plano_ativar(self, guid: str) -> tuple:
        codigo, saida = self.rodar(["powercfg", "/setactive", guid], timeout=30)
        return (True, "ok") if codigo == 0 else (False, saida.strip()[:200])

    def plano_duplicar(self, guid: str):
        """Cria uma cópia de um plano escondido e devolve o GUID novo."""
        codigo, saida = self.rodar(["powercfg", "/duplicatescheme", guid], timeout=30)
        if codigo != 0:
            return None
        novos = [g.lower() for g in GUID_RE.findall(saida) if g.lower() != guid.lower()]
        return novos[0] if novos else None

    def plano_apagar(self, guid: str) -> bool:
        codigo, _ = self.rodar(["powercfg", "/delete", guid], timeout=30)
        return codigo == 0

    # ------------------------------------------------------------ hibernação
    def hibernacao_ligada(self):
        r = self.reg_ler("HKLM", r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled")
        if r is not None:
            return int(r[0]) == 1
        drive = os.environ.get("SystemDrive", "C:") + "\\"
        return os.path.exists(os.path.join(drive, "hiberfil.sys"))

    def hibernacao_definir(self, ligar: bool) -> tuple:
        codigo, saida = self.rodar(["powercfg", "/hibernate", "on" if ligar else "off"], timeout=60)
        return (True, "ok") if codigo == 0 else (False, saida.strip()[:200])

    # ------------------------------------------------------------ mouse
    def mouse_ler(self):
        """[limite1, limite2, aceleração] do 'Aumentar precisão do ponteiro'."""
        vals = (ctypes.c_int * 3)()
        if ctypes.windll.user32.SystemParametersInfoW(0x0003, 0, vals, 0):  # SPI_GETMOUSE
            return [vals[0], vals[1], vals[2]]
        return None

    def mouse_definir(self, valores: list) -> tuple:
        vals = (ctypes.c_int * 3)(*[int(v) for v in valores])
        # SPI_SETMOUSE, gravando no perfil (1) e avisando os programas (2): vale na hora.
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0004, 0, vals, 0x01 | 0x02)
        return (True, "ok") if ok else (False, "o Windows recusou a mudança do mouse")

    # ------------------------------------------------------------ lixeira
    def lixeira_tamanho(self):
        """(itens, bytes) da Lixeira de todos os discos, ou None."""
        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_longlong),
                        ("i64NumItems", ctypes.c_longlong)]
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        try:
            if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
                return int(info.i64NumItems), int(info.i64Size)
        except Exception:
            pass
        return None

    def lixeira_esvaziar(self) -> tuple:
        # sem confirmação (1), sem barra (2), sem som (4)
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x01 | 0x02 | 0x04)
        res &= 0xFFFFFFFF
        if res in (0, 0x8000FFFF):  # 0x8000FFFF = já estava vazia
            return True, "ok"
        return False, f"o Windows respondeu 0x{res:08X}"

    # ------------------------------------------------------------ processos e pastas
    def processos(self) -> set:
        _, saida = self.rodar(["tasklist", "/FO", "CSV", "/NH"], timeout=30)
        return processos_do_tasklist(saida)

    def encerrar(self, pids: list, forcar: bool = False) -> tuple:
        """Fecha processos. Sem `forcar`, pede para fechar (como clicar no X)."""
        cmd = ["taskkill"]
        for pid in pids[:200]:
            cmd += ["/PID", str(int(pid))]
        cmd.append("/T")
        if forcar:
            cmd.append("/F")
        codigo, saida = self.rodar(cmd, timeout=30)
        return codigo == 0, saida.strip()[:200]

    def abrir_no_explorador(self, caminho: str, selecionar: bool = False) -> None:
        try:
            if selecionar:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(caminho)])
            else:
                os.startfile(os.path.normpath(caminho))
        except OSError:
            pass

    def listar_pasta(self, pasta: str) -> list:
        try:
            return [e.name for e in os.scandir(pasta) if e.is_file(follow_symlinks=False)]
        except OSError:
            return []
