# -*- coding: utf-8 -*-
"""
Limpeza de arquivos.

Como funciona:
- Cada item tem ALVOS (pasta + filtros). Só se apaga o que está DENTRO deles,
  depois de passar pela trava de seguranca.caminho_e_seguro().
- "Analisar" usa exatamente a mesma busca da limpeza, só que sem apagar:
  o número mostrado é o que vai sair (menos o que estiver em uso).
- Temporários com menos de 24 h ficam: um instalador rodando agora usa o
  %TEMP%, e apagar no meio quebra a instalação.
- Atalhos de pasta (junções) nunca são seguidos nem apagados.
- O cache do Windows Update só é limpo com o Windows Update e o BITS
  parados, e eles voltam a rodar depois se estavam rodando.
- Cache de navegador só com o navegador fechado (senão ele é pulado).
"""

import glob
import os
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from otimizador_pc.controle import nulo
from otimizador_pc.seguranca import caminho_e_seguro, dentro_de, eh_link


@dataclass
class Alvo:
    pasta: str
    extensoes: tuple = ()      # só arquivos com estas extensões (".log")
    prefixos: tuple = ()       # só arquivos que começam assim ("thumbcache_")
    nomes: tuple = ()          # só estes nomes exatos ("MEMORY.DMP")
    idade_horas: float = 0     # só o que não foi mexido nas últimas N horas
    recursivo: bool = True     # entra nas subpastas
    apagar_pastas: bool = True # tira as subpastas que ficarem vazias
    # Só para pastas pessoais protegidas (Downloads): permite apagar ali, mas SÓ arquivos
    # com as extensões da lista, sem entrar em subpastas. Ver _excecao_protegida.
    pasta_pessoal: bool = False


@dataclass
class Resultado:
    apagados: int = 0
    bytes: int = 0
    pulados: int = 0
    nota: str = ""

    def somar(self, outro: "Resultado"):
        self.apagados += outro.apagados
        self.bytes += outro.bytes
        self.pulados += outro.pulados


@dataclass
class ItemLimpeza:
    id: str
    nome: str
    descricao: str
    alvos: Callable[[], list] = lambda: []
    padrao: bool = False
    confirmar: str = ""                     # pergunta antes (ex.: Lixeira)
    parar_servicos: tuple = ()              # para durante a limpeza
    fechar_processos: tuple = ()            # só limpa com estes fechados
    nome_processo: str = ""                 # nome amigável para o aviso
    libera_espaco: bool = True
    analisar_especial: Optional[Callable] = None   # (s) -> Resultado | None
    limpar_especial: Optional[Callable] = None     # (s, log) -> Resultado
    sempre_mostrar: bool = False

    def disponivel(self) -> bool:
        if self.sempre_mostrar or self.limpar_especial:
            return True
        return any(os.path.isdir(a.pasta) for a in self.alvos())


# ---------------------------------------------------------------- busca dos arquivos
def _combina(nome: str, alvo: Alvo) -> bool:
    baixo = nome.lower()
    if alvo.nomes and baixo not in {n.lower() for n in alvo.nomes}:
        return False
    if alvo.prefixos and not baixo.startswith(tuple(p.lower() for p in alvo.prefixos)):
        return False
    if alvo.extensoes and os.path.splitext(baixo)[1] not in {e.lower() for e in alvo.extensoes}:
        return False
    return True


def _recente(st, limite: float) -> bool:
    """True se foi criado ou mexido depois do limite."""
    criado = getattr(st, "st_birthtime", None) or st.st_ctime
    return max(st.st_mtime, criado) >= limite


def _excecao_protegida(alvo: Alvo) -> bool:
    """
    Exceções estreitas à lista de pastas protegidas, sempre SEM entrar em subpastas:
    - nomes exatos (ex.: C:\\Windows\\MEMORY.DMP);
    - pasta pessoal (Downloads) só com uma lista de extensões (downloads incompletos).
    A raiz do disco continua proibida.
    """
    if alvo.recursivo or not alvo.pasta:
        return False
    if not (alvo.nomes or (alvo.pasta_pessoal and alvo.extensoes)):
        return False
    p = os.path.normpath(os.path.abspath(alvo.pasta))
    if not os.path.splitdrive(p)[1].strip("\\/"):
        return False
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and not eh_link(st)


def _percorrer(alvo: Alvo, agora: float, ctl=None):
    """Devolve (arquivos, pastas): arquivos = [(caminho, tamanho)] que podem sair."""
    if not (caminho_e_seguro(alvo.pasta) or _excecao_protegida(alvo)):
        return [], []
    ctl = ctl or nulo()
    limite = agora - alvo.idade_horas * 3600
    raiz = os.path.normcase(os.path.abspath(alvo.pasta)).rstrip("\\/") + os.sep
    # Primeiro nível aqui; cada subpasta de cima numa thread (listar pastas
    # espera o disco, e o Windows atende vários pedidos ao mesmo tempo).
    arquivos, pastas, subpastas = _varrer(alvo, raiz, [alvo.pasta], limite, ctl, so_um_nivel=True)
    if subpastas:
        with ThreadPoolExecutor(max_workers=min(8, len(subpastas))) as pool:
            for a, p, _ in pool.map(lambda d: _varrer(alvo, raiz, [d], limite, ctl), subpastas):
                arquivos += a
                pastas += p
    return arquivos, pastas


def _varrer(alvo: Alvo, raiz: str, pilha: list, limite: float, ctl, so_um_nivel: bool = False):
    """Varre as pastas da pilha. `raiz` é a pasta do alvo normalizada, com a barra no fim."""
    arquivos, pastas, subpastas = [], [], []
    while pilha:
        ctl.checar()
        atual = pilha.pop()
        try:
            entradas = list(os.scandir(atual))
        except OSError:
            continue
        for e in entradas:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if eh_link(st):
                continue  # junção ou link: nem segue, nem apaga
            if stat.S_ISDIR(st.st_mode):
                if alvo.recursivo:
                    (subpastas if so_um_nivel else pilha).append(e.path)
                    pastas.append((e.path, st))
                continue
            if not _combina(e.name, alvo):
                continue
            if alvo.idade_horas and _recente(st, limite):
                continue
            if not os.path.normcase(e.path).startswith(raiz):
                continue  # nunca deveria acontecer; é a última trava
            arquivos.append((e.path, st.st_size))
    return arquivos, pastas, subpastas


def analisar_alvo(alvo: Alvo, agora: float = None, ctl=None) -> Resultado:
    arquivos, _ = _percorrer(alvo, time.time() if agora is None else agora, ctl)
    return Resultado(apagados=len(arquivos), bytes=sum(t for _, t in arquivos))


def limpar_alvo(alvo: Alvo, agora: float = None, ctl=None) -> Resultado:
    """Apaga o que a análise acharia. Cancelando no meio, para e devolve o que já saiu."""
    agora = time.time() if agora is None else agora
    res = Resultado()
    arquivos, pastas = _percorrer(alvo, agora, ctl)
    for caminho, tamanho in arquivos:
        if ctl and ctl.parado():
            res.nota = "cancelado no meio"
            return res
        try:
            try:
                os.chmod(caminho, stat.S_IWRITE)  # tira o "somente leitura"
            except OSError:
                pass
            os.remove(caminho)
            res.apagados += 1
            res.bytes += tamanho
        except OSError:
            res.pulados += 1  # em uso ou protegido: fica

    if alvo.apagar_pastas and not (alvo.extensoes or alvo.prefixos or alvo.nomes):
        limite = agora - alvo.idade_horas * 3600
        # das mais fundas para as de cima; rmdir só tira pasta vazia
        for caminho, st in sorted(pastas, key=lambda p: p[0].count(os.sep), reverse=True):
            if alvo.idade_horas and _recente(st, limite):
                continue
            if dentro_de(caminho, alvo.pasta):
                try:
                    os.rmdir(caminho)
                except OSError:
                    pass
    return res


# ---------------------------------------------------------------- pastas
def _env(nome, padrao=""):
    return os.environ.get(nome, padrao)


def _win(*partes):
    return os.path.join(_env("SystemRoot", r"C:\Windows"), *partes)


def _local(*partes):
    return os.path.join(_env("LOCALAPPDATA"), *partes) if _env("LOCALAPPDATA") else ""


def _locallow(*partes):
    return os.path.join(_env("USERPROFILE"), "AppData", "LocalLow", *partes) if _env("USERPROFILE") else ""


def _roaming(*partes):
    return os.path.join(_env("APPDATA"), *partes) if _env("APPDATA") else ""


def _programdata(*partes):
    return os.path.join(_env("ProgramData", r"C:\ProgramData"), *partes)


def _sem_repetir(alvos):
    vistos, saida = set(), []
    for a in alvos:
        if not a.pasta:
            continue
        chave = os.path.normcase(os.path.normpath(a.pasta))
        if chave not in vistos:
            vistos.add(chave)
            saida.append(a)
    return saida


def alvos_temp_usuario():
    return _sem_repetir([Alvo(_env("TEMP"), idade_horas=24), Alvo(_local("Temp"), idade_horas=24)])


def alvos_temp_windows():
    return [Alvo(_win("Temp"), idade_horas=24)]


def alvos_update():
    return [Alvo(_win("SoftwareDistribution", "Download"))]


def alvos_relatorios():
    return [Alvo(_programdata("Microsoft", "Windows", "WER", p)) for p in ("ReportArchive", "ReportQueue", "Temp")] + \
           [Alvo(_local("Microsoft", "Windows", "WER", p)) for p in ("ReportArchive", "ReportQueue")] + \
           [Alvo(_local("CrashDumps"))]


def alvos_dumps():
    return [Alvo(_win("Minidump")),
            Alvo(_env("SystemRoot", r"C:\Windows"), nomes=("MEMORY.DMP",), recursivo=False),
            Alvo(_win("LiveKernelReports"), extensoes=(".dmp",))]


def alvos_miniaturas():
    return [Alvo(_local("Microsoft", "Windows", "Explorer"), prefixos=("thumbcache_",),
                 extensoes=(".db",), recursivo=False)]


def pasta_downloads() -> str:
    """A pasta Downloads de verdade (a pessoa pode ter mudado de lugar)."""
    try:
        import ctypes
        import uuid
        guid = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")  # FOLDERID_Downloads
        bufer = ctypes.c_wchar_p()
        id_bytes = (ctypes.c_byte * 16).from_buffer_copy(guid.bytes_le)
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(id_bytes), 0, None, ctypes.byref(bufer)) == 0:
            caminho = bufer.value
            ctypes.windll.ole32.CoTaskMemFree(bufer)
            if caminho:
                return caminho
    except Exception:
        pass
    return os.path.join(_env("USERPROFILE"), "Downloads") if _env("USERPROFILE") else ""


EXT_INCOMPLETOS = (".crdownload", ".part", ".partial", ".download", ".opdownload", ".tmp")


def alvos_downloads():
    """Downloads que nunca terminaram, com mais de 7 dias. Só esses tipos, só na pasta de cima."""
    return [Alvo(pasta_downloads(), extensoes=EXT_INCOMPLETOS, idade_horas=24 * 7, recursivo=False,
                 apagar_pastas=False, pasta_pessoal=True)]


def alvos_logs():
    return [Alvo(_win("Logs", "CBS"), extensoes=(".log", ".cab"), idade_horas=24 * 7, recursivo=False),
            Alvo(_win("Logs", "DISM"), extensoes=(".log",), idade_horas=24 * 7, recursivo=False)]


def alvos_shaders():
    return [Alvo(p) for p in (
        _local("D3DSCache"),
        _local("NVIDIA", "DXCache"), _local("NVIDIA", "GLCache"),
        _locallow("NVIDIA", "PerDriverVersion", "DXCache"),
        _local("AMD", "DxCache"), _local("AMD", "DxcCache"), _local("AMD", "GLCache"), _local("AMD", "VkCache"),
        _locallow("Intel", "ShaderCache"),
    ) if p]


CACHES_CHROMIUM = ("Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache")
CACHES_RAIZ_CHROMIUM = ("ShaderCache", "GrShaderCache", "GraphiteDawnCache")


def _alvos_chromium(dados_usuario: str):
    """Caches de cada perfil de um navegador Chromium (Chrome, Edge, Brave). Nada de senhas ou histórico."""
    if not dados_usuario or not os.path.isdir(dados_usuario):
        return []
    alvos = [Alvo(os.path.join(dados_usuario, c)) for c in CACHES_RAIZ_CHROMIUM]
    try:
        for e in os.scandir(dados_usuario):
            if e.is_dir(follow_symlinks=False) and os.path.isfile(os.path.join(e.path, "Preferences")):
                alvos += [Alvo(os.path.join(e.path, c)) for c in CACHES_CHROMIUM]
    except OSError:
        pass
    return alvos


def _alvos_opera(nome: str):
    alvos = []
    for base in (_local("Opera Software", nome), _roaming("Opera Software", nome)):
        if base:
            alvos += [Alvo(os.path.join(base, c)) for c in CACHES_CHROMIUM]
    return alvos


def _alvos_firefox():
    base = _local("Mozilla", "Firefox", "Profiles")
    if not base:
        return []
    return [Alvo(os.path.join(p, c)) for p in glob.glob(os.path.join(base, "*"))
            for c in ("cache2", "startupCache")]


# ---------------------------------------------------------------- itens especiais
def _analisar_lixeira(s):
    r = s.lixeira_tamanho()
    return None if r is None else Resultado(apagados=r[0], bytes=r[1])


def _limpar_lixeira(s, log):
    antes = s.lixeira_tamanho() or (0, 0)
    ok, msg = s.lixeira_esvaziar()
    if not ok:
        return Resultado(nota=f"não esvaziou: {msg}")
    return Resultado(apagados=antes[0], bytes=antes[1])


def _limpar_dns(s, log):
    codigo, saida = s.rodar(["ipconfig", "/flushdns"])
    return Resultado(nota="cache de DNS renovado" if codigo == 0 else f"falhou: {saida.strip()[:120]}")


PASTA_ENTREGA = os.path.join(_env("SystemRoot", r"C:\Windows"), "ServiceProfiles", "NetworkService",
                             "AppData", "Local", "Microsoft", "Windows", "DeliveryOptimization", "Cache")


def _analisar_entrega(s):
    if not os.path.isdir(PASTA_ENTREGA):
        return None
    total = qtd = 0
    for raiz, _, nomes in os.walk(PASTA_ENTREGA):
        for n in nomes:
            try:
                total += os.path.getsize(os.path.join(raiz, n))
                qtd += 1
            except OSError:
                pass
    return Resultado(apagados=qtd, bytes=total)


def _limpar_entrega(s, log):
    antes = _analisar_entrega(s)
    codigo, saida = s.powershell("Delete-DeliveryOptimizationCache -Force -ErrorAction Stop", timeout=300)
    if codigo != 0:
        return Resultado(nota=f"o Windows não deixou: {saida.strip()[:150]}")
    depois = _analisar_entrega(s)
    if antes and depois:
        return Resultado(apagados=max(antes.apagados - depois.apagados, 0),
                         bytes=max(antes.bytes - depois.bytes, 0))
    return Resultado(nota="cache apagado pelo Windows")


def _limpar_componentes(s, log):
    log("   O DISM está trabalhando. Isso leva de 5 a 30 minutos; não feche o programa.")
    codigo, saida = s.rodar(["dism", "/Online", "/Cleanup-Image", "/StartComponentCleanup"], timeout=3600)
    if codigo == 0:
        return Resultado(nota="componentes antigos removidos")
    return Resultado(nota=f"o DISM terminou com erro {codigo}: {saida.strip()[-200:]}")


# ---------------------------------------------------------------- lista
ITENS = [
    ItemLimpeza("temp_user", "Temporários do usuário (%TEMP%)",
                "Arquivos descartáveis de programas e instaladores. Os das últimas 24 h ficam, "
                "para não quebrar uma instalação em andamento.",
                alvos_temp_usuario, padrao=True),
    ItemLimpeza("temp_win", "Temporários do Windows (C:\\Windows\\Temp)",
                "Restos de atualizações e instaladores do sistema. Também guarda os das últimas 24 h.",
                alvos_temp_windows, padrao=True),
    ItemLimpeza("relatorios_erro", "Relatórios de erro antigos",
                "Relatórios de travamentos que o Windows já mandou ou desistiu de mandar.",
                alvos_relatorios, padrao=True),
    ItemLimpeza("cache_update", "Downloads do Windows Update",
                "Instaladores de atualizações já baixados. O Windows Update é pausado durante a "
                "limpeza e volta sozinho; uma atualização pendente pode ser baixada de novo.",
                alvos_update, parar_servicos=("wuauserv", "BITS")),
    ItemLimpeza("entrega_otimizada", "Cache da Otimização de Entrega",
                "Pedaços de atualizações que o Windows guarda para mandar a outros PCs. "
                "Apagado pelo próprio Windows.",
                analisar_especial=_analisar_entrega, limpar_especial=_limpar_entrega),
    ItemLimpeza("navegador_chrome", "Cache do Google Chrome",
                "Só o cache de páginas e imagens: senhas, histórico e abas ficam. Feche o Chrome antes.",
                lambda: _alvos_chromium(_local("Google", "Chrome", "User Data")),
                fechar_processos=("chrome.exe",), nome_processo="o Chrome"),
    ItemLimpeza("navegador_edge", "Cache do Microsoft Edge",
                "Só o cache: senhas, histórico e abas ficam. O Edge costuma ficar aberto escondido; "
                "se for pulado, desligue \"Aumento de inicialização\" nas configurações dele.",
                lambda: _alvos_chromium(_local("Microsoft", "Edge", "User Data")),
                fechar_processos=("msedge.exe",), nome_processo="o Edge"),
    ItemLimpeza("navegador_brave", "Cache do Brave",
                "Só o cache: senhas, histórico e abas ficam. Feche o Brave antes.",
                lambda: _alvos_chromium(_local("BraveSoftware", "Brave-Browser", "User Data")),
                fechar_processos=("brave.exe",), nome_processo="o Brave"),
    ItemLimpeza("navegador_operagx", "Cache do Opera GX",
                "Só o cache: senhas, histórico e abas ficam. Feche o Opera GX antes.",
                lambda: _alvos_opera("Opera GX Stable"),
                fechar_processos=("opera.exe",), nome_processo="o Opera GX"),
    ItemLimpeza("navegador_opera", "Cache do Opera",
                "Só o cache: senhas, histórico e abas ficam. Feche o Opera antes.",
                lambda: _alvos_opera("Opera Stable"),
                fechar_processos=("opera.exe",), nome_processo="o Opera"),
    ItemLimpeza("navegador_firefox", "Cache do Firefox",
                "Só o cache: senhas, histórico e abas ficam. Feche o Firefox antes.",
                _alvos_firefox, fechar_processos=("firefox.exe",), nome_processo="o Firefox"),
    ItemLimpeza("shaders", "Cache de shaders (DirectX, NVIDIA, AMD, Intel)",
                "Resolve gráfico bugado depois de atualizar o driver. Atenção: os jogos podem dar "
                "umas travadinhas nas primeiras partidas enquanto refazem o cache.",
                alvos_shaders),
    ItemLimpeza("miniaturas", "Cache de miniaturas do Explorador",
                "As miniaturas de fotos e vídeos são refeitas quando você abre as pastas.",
                alvos_miniaturas),
    ItemLimpeza("dumps", "Despejos de memória de telas azuis",
                "MEMORY.DMP e minidumps. Só apague se não precisa investigar uma tela azul.",
                alvos_dumps),
    ItemLimpeza("logs_windows", "Logs antigos do Windows (CBS e DISM)",
                "Registros de instalação de atualizações com mais de 7 dias.",
                alvos_logs),
    ItemLimpeza("downloads_incompletos", "Downloads que não terminaram",
                "Arquivos .crdownload, .part e .tmp na pasta Downloads, parados há mais de 7 dias "
                "(restos de downloads que falharam). Só esses tipos e só na pasta Downloads, sem entrar "
                "nas subpastas; seus arquivos normais não são tocados.",
                alvos_downloads),
    ItemLimpeza("componentes", "Limpeza de componentes do Windows (WinSxS)",
                "Remove versões antigas de arquivos do sistema substituídas por atualizações. O Windows "
                "faz isso sozinho depois de 30 dias; aqui é na hora. Demora de 5 a 30 minutos e, "
                "depois, atualizações antigas não podem ser desinstaladas.",
                limpar_especial=_limpar_componentes),
    ItemLimpeza("lixeira", "Esvaziar a Lixeira",
                "Atenção: o que estiver na Lixeira não volta mais.",
                analisar_especial=_analisar_lixeira, limpar_especial=_limpar_lixeira,
                confirmar="A Lixeira será esvaziada e os arquivos não poderão ser recuperados. Continuar?"),
    ItemLimpeza("dns", "Renovar o cache de DNS",
                "Resolve site que não abre depois de mudar de rede ou de DNS. Não libera espaço.",
                libera_espaco=False, limpar_especial=_limpar_dns),
]

ITENS_POR_ID = {i.id: i for i in ITENS}


# ---------------------------------------------------------------- execução
def analisar_item(item: ItemLimpeza, s, ctl=None):
    """Resultado com o que sairia, ou None quando não dá para estimar."""
    if item.analisar_especial:
        return item.analisar_especial(s)
    if item.limpar_especial:
        return None
    total = Resultado()
    for alvo in item.alvos():
        total.somar(analisar_alvo(alvo, ctl=ctl))
    return total


def limpar_item(item: ItemLimpeza, s, log=print, ctl=None) -> Resultado:
    """Limpa um item. Cancelar levanta Cancelado entre pastas, ou para no meio dos arquivos."""
    if item.fechar_processos:
        abertos = s.processos() & set(item.fechar_processos)
        if abertos:
            return Resultado(nota=f"pulado: feche {item.nome_processo} e tente de novo")

    if item.limpar_especial:
        return item.limpar_especial(s, log)

    religar = []
    for nome in item.parar_servicos:
        estava = s.servico_estado(nome) == "RUNNING"
        if not s.servico_parar(nome):
            for n in religar:
                s.servico_iniciar(n)
            return Resultado(nota=f"pulado: o serviço {nome} não parou")
        if estava:
            religar.append(nome)
    try:
        total = Resultado()
        for alvo in item.alvos():
            parcial = limpar_alvo(alvo, ctl=ctl)
            total.somar(parcial)
            if parcial.nota:
                total.nota = parcial.nota
                break
        return total
    finally:
        for nome in religar:
            s.servico_iniciar(nome)
