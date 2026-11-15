# -*- coding: utf-8 -*-
"""
Desinstalar programas e caçar o que eles deixam para trás (como o Revo Uninstaller).

1. A lista vem das chaves "Uninstall" do registro (64 e 32 bits, do PC e do usuário),
   as mesmas que o "Adicionar ou remover programas" do Windows lê.
2. Quem desinstala é o desinstalador do PRÓPRIO programa. O sistema espera ele e
   todos os processos que ele abrir terminarem.
3. Depois, procuramos as sobras: pastas com o nome do programa em lugares conhecidos
   (Arquivos de Programas, AppData, ProgramData, Menu Iniciar) e chaves em Software
   no registro. Só entra o que tem o nome do programa (ou do fabricante, quando nenhum
   outro programa dele continua instalado). Nada da Microsoft entra.
4. Só se apaga o que a pessoa marcar. Pastas vão para a Lixeira (dá para voltar) e cada
   chave do registro é exportada para um arquivo .reg antes (dois cliques nele põem de volta).
"""

import os
import re
from dataclasses import dataclass, field

from otimizador_pc import seguranca
from otimizador_pc.util import APP_DADOS

PASTA_COPIAS = os.path.join(APP_DADOS, "desinstalados")

RAIZES_UNINSTALL = [
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

# Nomes que aparecem em muitos programas: nunca servem para achar sobra.
GENERICOS = frozenset({
    "app", "apps", "program", "programs", "programa", "software", "update", "updater", "updates",
    "common", "commonfiles", "shared", "data", "cache", "temp", "tmp", "tools", "tool", "driver",
    "drivers", "setup", "installer", "install", "launcher", "client", "service", "services", "system",
    "windows", "microsoft", "user", "users", "default", "config", "settings", "plugins", "games",
    "game", "steam", "steamapps", "packages", "package", "runtime", "help", "documents", "desktop",
    "startmenu", "programfiles", "programdata", "appdata", "local", "roaming", "locallow", "google",
    "intel", "nvidia", "amd", "realtek", "classes", "policies", "wow6432node", "clients",
    "python", "java", "browser", "steamapps", "common", "library", "libraries", "assets", "bin",
})

# Chaves de Software que nunca se apagam, nem por engano.
CHAVES_PROTEGIDAS = frozenset({
    "microsoft", "windows", "classes", "policies", "wow6432node", "clients", "registeredapplications",
    "intel", "odbc", "khronos", "partner", "description", "setup", "secure", "wow6432",
})

EDITORES_PROTEGIDOS = ("microsoft", "windows")

_SUFIXOS_EDITOR = re.compile(
    r"[,.]?\s*\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|gmbh|ag|s\.?a|"
    r"s\.?r\.?l|b\.?v|oy|ab|pty|plc|software|technologies|technology|games|studios?|group|"
    r"international|ltda|me|eireli)\b\.?", re.I)
_VERSAO = re.compile(r"\s+(v(ersion)?\s*)?\d+([.,]\d+)+.*$|\s+\d{4}\b.*$", re.I)
_ARQUITETURA = re.compile(r"\s*[\(\[]?\s*(x64|x86|64[- ]?bits?|32[- ]?bits?|amd64|arm64)\s*[\)\]]?", re.I)
_GUID = re.compile(r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}")

# Programas que outros programas precisam (aviso antes de desinstalar).
_COMPARTILHADOS = re.compile(
    r"visual c\+\+|redistributable|\.net|directx|vcredist|runtime|webview2|java\(tm\)|java \d|"
    r"driver|chipset|physx|openal|xna|vulkan|microsoft edge|windows sdk|sdk", re.I)


def chave_de(texto: str) -> str:
    """'7-Zip 23.01 (x64)' -> '7zip'. Só letras e números, minúsculas, sem versão e sem arquitetura."""
    t = _ARQUITETURA.sub(" ", texto or "")
    t = _VERSAO.sub("", t.strip())
    return re.sub(r"[^0-9a-z]", "", t.lower())


def chave_do_editor(editor: str) -> str:
    """'Valve Corporation' -> 'valve'; 'Mozilla' -> 'mozilla'."""
    t = editor or ""
    for _ in range(3):
        t = _SUFIXOS_EDITOR.sub("", t).strip(" ,.")
    return re.sub(r"[^0-9a-z]", "", t.lower())


def chave_valida(k: str) -> bool:
    return len(k) >= 4 and k not in GENERICOS


@dataclass
class Programa:
    hive: str
    chave: str              # caminho da chave Uninstall dele
    nome: str
    versao: str = ""
    editor: str = ""
    pasta: str = ""         # InstallLocation
    desinstalar: str = ""   # UninstallString
    silencioso: str = ""    # QuietUninstallString
    tamanho: int = 0        # bytes (o registro guarda em KB)
    data: str = ""          # "dd/mm/aaaa"
    msi: bool = False

    @property
    def id(self) -> str:
        return f"{self.hive}\\{self.chave}"

    @property
    def compartilhado(self) -> bool:
        """Runtime, driver ou biblioteca que outros programas usam."""
        return bool(_COMPARTILHADOS.search(self.nome))

    @property
    def da_microsoft(self) -> bool:
        e = (self.editor or "").lower()
        return any(p in e for p in EDITORES_PROTEGIDOS)

    @property
    def chaves(self) -> set:
        k = chave_de(self.nome)
        return {k} if chave_valida(k) else set()


def _valor(s, hive, chave, nome, padrao=""):
    r = s.reg_ler(hive, chave, nome)
    if r is None or r[0] is None:
        return padrao
    return r[0]


def _data(texto) -> str:
    t = str(texto or "")
    if re.fullmatch(r"\d{8}", t):
        return f"{t[6:8]}/{t[4:6]}/{t[0:4]}"
    return ""


def listar(s) -> list:
    """Programas instalados, sem atualizações do Windows nem componentes escondidos."""
    vistos, programas = set(), []
    for hive, raiz in RAIZES_UNINSTALL:
        for sub in s.reg_subchaves(hive, raiz):
            chave = f"{raiz}\\{sub}"
            nome = str(_valor(s, hive, chave, "DisplayName")).strip()
            desinstalar = str(_valor(s, hive, chave, "UninstallString")).strip()
            if not nome or not desinstalar:
                continue
            if int(_valor(s, hive, chave, "SystemComponent", 0) or 0) == 1:
                continue
            if _valor(s, hive, chave, "ParentKeyName") or \
                    str(_valor(s, hive, chave, "ReleaseType")).lower() in ("update", "hotfix", "security update"):
                continue
            if re.match(r"(?i)^(security )?update for |\(kb\d+\)", nome):
                continue
            versao = str(_valor(s, hive, chave, "DisplayVersion")).strip()
            marca = (nome.lower(), versao)
            if marca in vistos:
                continue
            vistos.add(marca)
            try:
                tamanho = int(_valor(s, hive, chave, "EstimatedSize", 0) or 0) * 1024
            except (TypeError, ValueError):
                tamanho = 0
            msi = int(_valor(s, hive, chave, "WindowsInstaller", 0) or 0) == 1 or \
                "msiexec" in desinstalar.lower()
            programas.append(Programa(
                hive=hive, chave=chave, nome=nome, versao=versao,
                editor=str(_valor(s, hive, chave, "Publisher")).strip(),
                pasta=str(_valor(s, hive, chave, "InstallLocation")).strip().strip('"'),
                desinstalar=desinstalar,
                silencioso=str(_valor(s, hive, chave, "QuietUninstallString")).strip(),
                tamanho=tamanho, data=_data(_valor(s, hive, chave, "InstallDate")), msi=msi,
                ))
    programas.sort(key=lambda p: p.nome.lower())
    return programas


def comando(p: Programa, ambiente=None) -> str:
    """
    A linha de comando do desinstalador. Para MSI, sempre `msiexec /x {GUID}` pelo caminho
    completo: muita entrada vem com /I, que abre o "modificar" em vez de desinstalar.
    """
    amb = os.environ if ambiente is None else ambiente
    texto = p.desinstalar.strip()
    if p.msi or re.search(r"(?i)\bmsiexec(\.exe)?\b", texto):
        g = _GUID.search(texto) or _GUID.search(p.chave)
        if g:
            msiexec = os.path.join(amb.get("SystemRoot", r"C:\Windows"), "System32", "msiexec.exe")
            return f'"{msiexec}" /x {g.group(0)}'
    return re.sub(r"%([^%]+)%", lambda m: amb.get(m.group(1), m.group(0)), texto)


def executavel(cmd: str) -> str:
    """O programa que a linha de comando abre (o que está entre aspas, ou até o .exe)."""
    c = (cmd or "").strip()
    if c.startswith('"'):
        return c[1:].split('"', 1)[0]
    m = re.match(r"(?i)^(.+?\.exe)\b", c)
    return m.group(1) if m else c.split(" ")[0]


def desinstalador_existe(p: Programa, ambiente=None) -> bool:
    cmd = comando(p, ambiente)
    exe = executavel(cmd)
    if os.path.basename(exe).lower() == "msiexec.exe":
        return True
    return os.path.isfile(exe)


# ======================================================================= sobras
@dataclass
class Sobra:
    tipo: str          # "pasta" | "registro"
    caminho: str       # pasta, ou "HKCU\SOFTWARE\Fulano"
    motivo: str
    forte: bool = True  # bate com o nome exato (vem marcada)
    tamanho: int = 0
    hive: str = ""
    chave: str = ""

    @property
    def id(self) -> str:
        return f"{self.tipo}:{self.caminho.lower()}"


def raizes_de_pastas(ambiente=None) -> list:
    amb = os.environ if ambiente is None else ambiente
    raizes = []
    for nome in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData", "APPDATA", "LOCALAPPDATA"):
        if amb.get(nome):
            raizes.append(amb[nome])
    local, perfil = amb.get("LOCALAPPDATA", ""), amb.get("USERPROFILE", "")
    if local:
        raizes.append(os.path.join(local, "Programs"))
    if perfil:
        raizes.append(os.path.join(perfil, "AppData", "LocalLow"))
    menu = os.path.join("Microsoft", "Windows", "Start Menu", "Programs")
    for nome in ("APPDATA", "ProgramData"):
        if amb.get(nome):
            raizes.append(os.path.join(amb[nome], menu))
    unicas, vistas = [], set()
    for r in raizes:
        n = os.path.normcase(os.path.normpath(r))
        if n not in vistas:
            vistas.add(n)
            unicas.append(r)
    return unicas


def _filhas(pasta: str) -> list:
    try:
        return [e for e in os.scandir(pasta) if e.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def _tamanho(pasta: str, limite: int = 20000) -> int:
    total, vistos, pilha = 0, 0, [pasta]
    while pilha and vistos < limite:
        atual = pilha.pop()
        try:
            for e in os.scandir(atual):
                vistos += 1
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if seguranca.eh_link(st):
                    continue
                if e.is_dir(follow_symlinks=False):
                    pilha.append(e.path)
                else:
                    total += st.st_size
        except OSError:
            continue
    return total


def _normal(p: str) -> str:
    return os.path.normcase(os.path.normpath(p)).rstrip("\\/")


def _de_outro(caminho: str, outros_locais: list) -> bool:
    """True se a pasta é (ou guarda, ou fica dentro de) a pasta de outro programa instalado."""
    c = _normal(caminho)
    for o in outros_locais:
        if c == o or o.startswith(c + os.sep) or c.startswith(o + os.sep):
            return True
    return False


def procurar(p: Programa, instalados: list, s, ambiente=None, ainda_instalado: bool = False) -> list:
    """
    As sobras de `p`. `instalados` é a lista de programas que CONTINUAM instalados
    (sem o próprio `p`): o que é deles nunca entra.
    """
    if p.da_microsoft:
        return _sobra_da_entrada(p, s, ainda_instalado)
    outros = [o for o in instalados if o.id != p.id]
    outras_chaves = set().union(*[o.chaves for o in outros]) if outros else set()
    outros_locais = [_normal(o.pasta) for o in outros if o.pasta and len(_normal(o.pasta)) > 3]
    if ainda_instalado and p.pasta:   # desinstalação cancelada: a pasta dele continua em uso
        outros_locais.append(_normal(p.pasta))
    chaves = p.chaves - outras_chaves
    editor = chave_do_editor(p.editor)
    editor_ok = chave_valida(editor) and editor not in CHAVES_PROTEGIDAS
    # sem o nome do fabricante no começo: "mozillafirefox" -> "firefox" (só dentro da pasta dele)
    curtas = set(chaves)
    if editor_ok:
        for k in chaves:
            if k.startswith(editor) and chave_valida(k[len(editor):]):
                curtas.add(k[len(editor):])
        curtas -= outras_chaves
    editor_sozinho = editor_ok and not any(chave_do_editor(o.editor) == editor for o in outros)

    sobras, vistas = [], set()

    def pasta(caminho, motivo, forte=True):
        n = _normal(caminho)
        if n in vistas or not seguranca.caminho_e_seguro(caminho, ambiente) or _de_outro(caminho, outros_locais):
            return
        if "\\microsoft\\" in n.lower() and "start menu" not in n.lower():
            return
        vistas.add(n)
        sobras.append(Sobra("pasta", caminho, motivo, forte, _tamanho(caminho)))

    if not chaves and not editor_sozinho:
        return _sobra_da_entrada(p, s, ainda_instalado)

    # a pasta onde ele foi instalado, se sobrou e tem o nome dele (um registro mal feito pode
    # apontar para uma pasta de todo mundo, como a steamapps\common: sem o nome, não entra)
    if p.pasta and os.path.isdir(p.pasta) and not ainda_instalado:
        nome_pasta = chave_de(os.path.basename(_normal(p.pasta)))
        if nome_pasta in curtas:
            pasta(p.pasta, "a pasta onde ele foi instalado")
        elif editor_sozinho and nome_pasta == editor:
            pasta(p.pasta, "a pasta onde ele foi instalado (com o nome do fabricante)", forte=False)

    for raiz in raizes_de_pastas(ambiente):
        for e in _filhas(raiz):
            k = chave_de(e.name)
            if k in chaves:
                pasta(e.path, "tem o nome do programa")
            elif editor_ok and k == editor:
                dentro = _filhas(e.path)
                achou = [d for d in dentro if chave_de(d.name) in curtas]
                for d in achou:
                    pasta(d.path, "pasta do programa dentro da pasta do fabricante")
                if editor_sozinho and (len(achou) == len(dentro)):
                    try:
                        arquivos = [x for x in os.scandir(e.path) if not x.is_dir(follow_symlinks=False)]
                    except OSError:
                        arquivos = ["?"]
                    if not arquivos:
                        pasta(e.path, "pasta do fabricante (nenhum outro programa dele está instalado)", forte=False)

    sobras += _sobras_do_registro(s, chaves, curtas, editor if editor_ok else "", editor_sozinho)
    if not ainda_instalado:
        sobras += _sobra_da_entrada(p, s, False)
    return sobras


def _sobra_da_entrada(p, s, ainda_instalado):
    """A entrada do "Adicionar ou remover programas", quando o desinstalador a deixou para trás."""
    if ainda_instalado or not s.reg_chave_existe(p.hive, p.chave):
        return []
    return [Sobra("registro", f"{p.hive}\\{p.chave}", "o registro de que ele está instalado ficou para trás",
                  True, hive=p.hive, chave=p.chave)]


def _sobras_do_registro(s, chaves, curtas, editor, editor_sozinho) -> list:
    achadas = []
    bases = [("HKCU", "SOFTWARE"), ("HKLM", "SOFTWARE"), ("HKLM", r"SOFTWARE\WOW6432Node"),
             ("HKCU", r"SOFTWARE\WOW6432Node")]
    for hive, base in bases:
        for sub in s.reg_subchaves(hive, base):
            k = chave_de(sub)
            if sub.lower() in CHAVES_PROTEGIDAS:
                continue
            caminho = f"{base}\\{sub}"
            if k in chaves:
                achadas.append(Sobra("registro", f"{hive}\\{caminho}", "tem o nome do programa", True,
                                     hive=hive, chave=caminho))
            elif editor and k == editor:
                dentro = s.reg_subchaves(hive, caminho)
                achou = [d for d in dentro if chave_de(d) in curtas and d.lower() not in CHAVES_PROTEGIDAS]
                for d in achou:
                    achadas.append(Sobra("registro", f"{hive}\\{caminho}\\{d}",
                                         "chave do programa dentro da chave do fabricante", True,
                                         hive=hive, chave=f"{caminho}\\{d}"))
                if editor_sozinho and achou and len(achou) == len(dentro):
                    achadas.append(Sobra("registro", f"{hive}\\{caminho}",
                                         "chave do fabricante (nenhum outro programa dele está instalado)", False,
                                         hive=hive, chave=caminho))
    return achadas


def nome_do_arquivo(texto: str) -> str:
    return (re.sub(r"[^0-9A-Za-z._-]+", "-", texto).strip("-") or "programa")[:60]


def apagar(s, sobras: list, nome_programa: str, log=print, ambiente=None, pasta_copias: str = None) -> tuple:
    """
    Apaga as sobras escolhidas. Pastas vão para a Lixeira; chaves do registro são
    exportadas antes para um .reg. Devolve (quantas apagou, quantas falharam).
    """
    from datetime import datetime
    destino = pasta_copias or PASTA_COPIAS
    feitas = falhas = 0
    # a chave de dentro antes da de fora não importa (reg delete apaga a árvore), mas
    # exportar a de fora depois da de dentro sumir perderia a cópia: ordena de fora para dentro.
    for sb in sorted(sobras, key=lambda x: (x.tipo, len(x.caminho))):
        if sb.tipo == "pasta":
            if not seguranca.caminho_e_seguro(sb.caminho, ambiente):
                log(f"  [pulado] {sb.caminho}: não é uma pasta que eu possa apagar")
                falhas += 1
                continue
            ok, msg = s.para_lixeira(sb.caminho)
            log(f"  {'[lixeira]' if ok else '[falhou]'} {sb.caminho}" + ("" if ok else f": {msg}"))
        else:
            topo = sb.chave.split("\\")[-1].lower()
            if topo in CHAVES_PROTEGIDAS or sb.chave.strip("\\").lower() in ("software", r"software\wow6432node"):
                log(f"  [pulado] {sb.caminho}: chave protegida")
                falhas += 1
                continue
            if not s.reg_chave_existe(sb.hive, sb.chave):
                continue   # já saiu junto com a chave de fora
            os.makedirs(destino, exist_ok=True)
            arquivo = os.path.join(destino, f"{datetime.now():%Y%m%d-%H%M%S}-{nome_do_arquivo(nome_programa)}-"
                                              f"{nome_do_arquivo(sb.chave.split(chr(92))[-1])}.reg")
            ok, msg = s.reg_exportar(sb.hive, sb.chave, arquivo)
            if not ok:
                log(f"  [falhou] {sb.caminho}: não deu para guardar a cópia antes ({msg}); não apaguei")
                falhas += 1
                continue
            ok, msg = s.reg_apagar_chave(sb.hive, sb.chave)
            log(f"  {'[apagada]' if ok else '[falhou]'} {sb.caminho}" + ("" if ok else f": {msg}"))
        feitas += ok
        falhas += not ok
    return feitas, falhas
