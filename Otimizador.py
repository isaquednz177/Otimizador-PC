# -*- coding: utf-8 -*-
"""
===============================================================================
 OTIMIZADOR PC  -  Limpeza e ajustes reversíveis do Windows 10/11
===============================================================================

 FILOSOFIA DE SEGURANÇA DESTE CÓDIGO (leia antes de alterar qualquer coisa):

 1. NADA é apagado fora de uma lista branca de pastas (Temp, Prefetch...).
    Antes de deletar, o caminho é normalizado e comparado com uma lista de
    pastas proibidas (C:\\, C:\\Windows, Arquivos de Programas, etc).

 2. NENHUM ajuste é aplicado sem antes salvar o valor original em um arquivo
    JSON (%APPDATA%\\OtimizadorPC\\backup_estado.json). A reversão simplesmente
    lê esse arquivo e devolve o valor antigo. Se o valor não existia no
    registro antes, a reversão APAGA a chave criada (volta ao padrão real).

 3. Serviços do Windows só podem ser tocados se estiverem em uma lista branca
    (SERVICOS_PERMITIDOS). Serviços de boot/kernel (Start 0 ou 1) são
    ignorados por segurança — desativar esses é o que quebra o Windows.

 4. Todo erro é capturado e escrito no log. O programa nunca "trava" o sistema
    por causa de um arquivo em uso: ele simplesmente pula o arquivo.

 Requisitos: Windows 10/11, Python 3.10+, customtkinter
 Execução: precisa de privilégio de Administrador (o programa se re-executa
 elevado automaticamente).
===============================================================================
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
from datetime import datetime

# winreg só existe no Windows. O try/except evita erro de import em outros SOs.
try:
    import winreg
except ImportError:
    winreg = None

import customtkinter as ctk
from tkinter import messagebox


# =============================================================================
# 1. CONSTANTES GERAIS
# =============================================================================

APP_NOME = "Otimizador PC"
APP_VERSAO = "1.0"

# Pasta onde guardamos o backup do estado original do Windows.
PASTA_DADOS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OtimizadorPC")
ARQUIVO_BACKUP = os.path.join(PASTA_DADOS, "backup_estado.json")

# Flag para rodar comandos (sc, powercfg, schtasks) sem piscar janela preta.
CREATE_NO_WINDOW = 0x08000000

# Em Windows 64 bits, se o .exe for 32 bits, o registro é "redirecionado".
# Esta flag força a leitura/escrita na visão real de 64 bits.
ACESSO_64 = getattr(winreg, "KEY_WOW64_64KEY", 0) if winreg else 0

# Mapa de nome curto -> handle da raiz do registro.
HIVES = {}
if winreg:
    HIVES = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }

# Lista branca: os ÚNICOS serviços que este programa tem permissão de mexer.
SERVICOS_PERMITIDOS = {"DiagTrack", "dmwappushservice", "WSearch", "SysMain"}

# Números de "Start" de serviço usados pelo Windows.
# 0 = boot | 1 = system | 2 = automático | 3 = manual | 4 = desativado
MAPA_START = {2: "auto", 3: "demand", 4: "disabled"}


# =============================================================================
# 2. UTILIDADES BÁSICAS
# =============================================================================

def eh_windows() -> bool:
    """Confere se estamos rodando no Windows."""
    return os.name == "nt" and winreg is not None


def eh_admin() -> bool:
    """Retorna True se o processo atual tem privilégio de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def reexecutar_como_admin() -> None:
    """
    Reabre o próprio programa pedindo elevação (aquele popup do UAC).
    Depois disso, o processo atual é encerrado — quem continua é o elevado.
    """
    try:
        if getattr(sys, "frozen", False):
            # Rodando como .exe compilado: o executável é o próprio sys.executable
            alvo = sys.executable
            args = " ".join(f'"{a}"' for a in sys.argv[1:])
        else:
            # Rodando como script .py: chamamos o python passando o script
            alvo = sys.executable
            args = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", alvo, args, None, 1)
    except Exception:
        pass
    sys.exit(0)


def rodar(comando: list) -> tuple:
    """
    Executa um comando externo sem abrir janela de console.
    Retorna (codigo_retorno, saida_texto). Nunca levanta exceção.
    """
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            shell=False,                 # shell=False evita injeção de comando
            creationflags=CREATE_NO_WINDOW,
            timeout=120,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return -1, str(e)


def formatar_tamanho(bytes_: int) -> str:
    """Converte bytes em texto legível (KB, MB, GB)."""
    unidades = ["B", "KB", "MB", "GB", "TB"]
    valor = float(bytes_)
    for u in unidades:
        if valor < 1024 or u == "TB":
            return f"{valor:.1f} {u}"
        valor /= 1024
    return f"{valor:.1f} TB"


# =============================================================================
# 3. CAMADA DE REGISTRO DO WINDOWS (ler / escrever / apagar)
# =============================================================================

def registro_ler(hive: str, caminho: str, nome: str):
    """
    Lê um valor do registro.
    Retorna (valor, tipo) se existir, ou None se a chave/valor não existir.
    """
    try:
        with winreg.OpenKey(HIVES[hive], caminho, 0, winreg.KEY_READ | ACESSO_64) as k:
            valor, tipo = winreg.QueryValueEx(k, nome)
            return valor, tipo
    except FileNotFoundError:
        return None
    except OSError:
        return None


def registro_escrever(hive: str, caminho: str, nome: str, tipo: int, valor) -> None:
    """Cria a chave (se preciso) e grava o valor. Levanta exceção em caso de erro."""
    with winreg.CreateKeyEx(HIVES[hive], caminho, 0, winreg.KEY_SET_VALUE | ACESSO_64) as k:
        winreg.SetValueEx(k, nome, 0, tipo, valor)


def registro_apagar_valor(hive: str, caminho: str, nome: str) -> None:
    """Apaga um valor. Se já não existir, não faz nada (não é erro)."""
    try:
        with winreg.OpenKey(HIVES[hive], caminho, 0, winreg.KEY_SET_VALUE | ACESSO_64) as k:
            winreg.DeleteValue(k, nome)
    except FileNotFoundError:
        pass
    except OSError:
        pass


# =============================================================================
# 4. CAMADA DE SERVIÇOS DO WINDOWS
# =============================================================================

def servico_ler_start(nome_servico: str):
    """
    Descobre o tipo de inicialização atual de um serviço lendo o registro.
    Retorna o número (0..4) ou None se o serviço não existir nesta máquina.
    """
    caminho = rf"SYSTEM\CurrentControlSet\Services\{nome_servico}"
    r = registro_ler("HKLM", caminho, "Start")
    return int(r[0]) if r else None


def servico_definir_start(nome_servico: str, start_num: int) -> tuple:
    """
    Altera o tipo de inicialização de um serviço usando o sc.exe.
    Só funciona para serviços da lista branca — dupla checagem de segurança.
    """
    if nome_servico not in SERVICOS_PERMITIDOS:
        return False, "serviço fora da lista permitida"
    if start_num not in MAPA_START:
        return False, f"tipo de início inválido ({start_num})"

    atual = servico_ler_start(nome_servico)
    if atual is None:
        return False, "serviço não existe neste Windows"
    # Serviços de boot/system NUNCA são tocados: é isso que corrompe o sistema.
    if atual <= 1:
        return False, "serviço crítico de boot — ignorado por segurança"

    codigo, saida = rodar(["sc", "config", nome_servico, "start=", MAPA_START[start_num]])
    if codigo != 0:
        return False, saida.strip()[:200]

    # Se estamos desativando, tentamos parar o serviço agora (erro aqui é normal
    # se ele já estiver parado, por isso ignoramos o retorno).
    if start_num == 4:
        rodar(["sc", "stop", nome_servico])
    return True, "ok"


# =============================================================================
# 5. TAREFAS AGENDADAS (schtasks)
# =============================================================================

def tarefa_definir(caminho_tarefa: str, ativar: bool) -> tuple:
    """Ativa ou desativa uma tarefa agendada do Windows."""
    acao = "/Enable" if ativar else "/Disable"
    codigo, saida = rodar(["schtasks", "/Change", "/TN", caminho_tarefa, acao])
    if codigo != 0:
        return False, saida.strip()[:200]
    return True, "ok"


# =============================================================================
# 6. BACKUP DE ESTADO (o coração da função de reversão)
# =============================================================================

def carregar_backup() -> dict:
    """Lê o JSON de backup. Se não existir ou estiver corrompido, começa vazio."""
    try:
        with open(ARQUIVO_BACKUP, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, dict) and "tweaks" in dados:
                return dados
    except Exception:
        pass
    return {"versao": APP_VERSAO, "tweaks": {}}


def salvar_backup(dados: dict) -> None:
    """Grava o JSON de backup em disco, criando a pasta se necessário."""
    os.makedirs(PASTA_DADOS, exist_ok=True)
    with open(ARQUIVO_BACKUP, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


# =============================================================================
# 7. DEFINIÇÃO DAS TAREFAS DE LIMPEZA
# =============================================================================

def pasta_temp_usuario() -> str:
    return os.environ.get("TEMP", "")


def pasta_temp_windows() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")


def pasta_prefetch() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch")


def pasta_cache_update() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                        "SoftwareDistribution", "Download")


def _pastas_proibidas() -> set:
    """Monta a lista de pastas que JAMAIS podem ser limpas."""
    sistema = os.environ.get("SystemRoot", r"C:\Windows")
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    proibidas = {
        drive,
        sistema,
        os.path.join(sistema, "System32"),
        os.path.join(sistema, "SysWOW64"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        os.environ.get("USERPROFILE", ""),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    }
    return {os.path.normcase(os.path.normpath(p)) for p in proibidas if p}


def caminho_e_seguro(pasta: str) -> bool:
    """
    Trava de segurança: só devolve True se a pasta existir, não for uma pasta
    proibida e não for a raiz de um disco.
    """
    if not pasta:
        return False
    p = os.path.normcase(os.path.normpath(os.path.abspath(pasta)))
    if not os.path.isdir(p):
        return False
    if p in _pastas_proibidas():
        return False
    # Rejeita raiz de disco (ex: "C:\") — precisa ter pelo menos uma subpasta.
    if len(os.path.splitdrive(p)[1].strip("\\/")) == 0:
        return False
    return True


def limpar_pasta(pasta: str, so_extensoes=None, log=print) -> tuple:
    """
    Apaga o CONTEÚDO de uma pasta (nunca a pasta em si).
    - so_extensoes: se informado (ex: ['.pf']), apaga apenas esses tipos.
    - Arquivos em uso pelo Windows simplesmente são pulados.
    Retorna (qtd_apagados, bytes_liberados, qtd_pulados).
    """
    if not caminho_e_seguro(pasta):
        log(f"   [ignorado] Caminho não permitido ou inexistente: {pasta}")
        return 0, 0, 0

    apagados = liberados = pulados = 0
    try:
        entradas = list(os.scandir(pasta))
    except Exception as e:
        log(f"   [erro] Não foi possível ler {pasta}: {e}")
        return 0, 0, 0

    for item in entradas:
        try:
            if item.is_file() or item.is_symlink():
                if so_extensoes and os.path.splitext(item.name)[1].lower() not in so_extensoes:
                    continue
                tamanho = item.stat().st_size
                os.chmod(item.path, 0o777)   # remove atributo somente-leitura
                os.remove(item.path)
                apagados += 1
                liberados += tamanho
            elif item.is_dir():
                if so_extensoes:             # se filtramos por extensão, não mexe em pastas
                    continue
                tamanho = 0
                for raiz, _, arquivos in os.walk(item.path):
                    for a in arquivos:
                        try:
                            tamanho += os.path.getsize(os.path.join(raiz, a))
                        except Exception:
                            pass
                import shutil
                shutil.rmtree(item.path, ignore_errors=False)
                apagados += 1
                liberados += tamanho
        except Exception:
            # Arquivo aberto/em uso ou protegido: pula sem drama.
            pulados += 1
    return apagados, liberados, pulados


def esvaziar_lixeira(log=print) -> bool:
    """
    Esvazia a Lixeira de todas as unidades usando a API oficial do Windows
    (SHEmptyRecycleBinW), sem confirmação, sem som e sem barra de progresso.
    """
    SHERB_NOCONFIRMATION = 0x01
    SHERB_NOPROGRESSUI = 0x02
    SHERB_NOSOUND = 0x04
    try:
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        )
        # 0 = sucesso | 0x8000FFFF = já estava vazia (também é sucesso pra nós)
        if res in (0, -2147418113, 0x8000FFFF):
            log("   Lixeira esvaziada.")
            return True
        log(f"   Lixeira retornou código {res} (pode já estar vazia).")
        return True
    except Exception as e:
        log(f"   [erro] Lixeira: {e}")
        return False


def limpar_dns(log=print) -> bool:
    """Limpa o cache de DNS — resolve lentidão/erro de sites, 100% seguro."""
    codigo, saida = rodar(["ipconfig", "/flushdns"])
    log("   Cache DNS limpo." if codigo == 0 else f"   [erro] DNS: {saida[:120]}")
    return codigo == 0


# Lista das opções que aparecem na aba Limpeza.
# Cada item: (id, rótulo, descrição, função_executora)
TAREFAS_LIMPEZA = [
    ("temp_user", "Arquivos temporários do usuário (%temp%)",
     "Conteúdo de AppData\\Local\\Temp. Seguro: são arquivos descartáveis.",
     lambda log: limpar_pasta(pasta_temp_usuario(), None, log)),

    ("temp_win", "Arquivos temporários do Windows (C:\\Windows\\Temp)",
     "Temporários criados por instaladores e pelo próprio sistema.",
     lambda log: limpar_pasta(pasta_temp_windows(), None, log)),

    ("prefetch", "Prefetch (C:\\Windows\\Prefetch)",
     "Apaga apenas arquivos .pf. O Windows recria conforme você usa os programas.",
     lambda log: limpar_pasta(pasta_prefetch(), [".pf"], log)),

    ("cache_update", "Cache do Windows Update",
     "Instaladores já aplicados que ficam ocupando espaço.",
     lambda log: limpar_pasta(pasta_cache_update(), None, log)),

    ("lixeira", "Esvaziar a Lixeira",
     "ATENÇÃO: arquivos na Lixeira não podem ser recuperados depois.",
     lambda log: (1 if esvaziar_lixeira(log) else 0, 0, 0)),

    ("dns", "Limpar cache de DNS",
     "Renova o cache de endereços de sites. Não apaga arquivos.",
     lambda log: (1 if limpar_dns(log) else 0, 0, 0)),
]


# =============================================================================
# 8. DEFINIÇÃO DOS AJUSTES (TWEAKS) — TUDO REVERSÍVEL
# =============================================================================
# Estrutura de cada tweak:
#   id            -> chave usada no arquivo de backup
#   nome          -> texto do checkbox
#   descricao     -> explicação curta mostrada abaixo do checkbox
#   registros     -> lista de (hive, caminho, nome, tipo, valor_otimizado)
#   servicos      -> lista de nomes de serviço a desativar (Start = 4)
#   tarefas       -> lista de tarefas agendadas a desativar
#   comando       -> (aplicar, reverter) para ajustes que não são de registro
# =============================================================================

DWORD = winreg.REG_DWORD if winreg else 4

TWEAKS = [
    {
        "id": "telemetria",
        "nome": "Desativar telemetria e coleta de dados",
        "descricao": "Bloqueia o envio de dados de uso e desativa os serviços DiagTrack e dmwappushservice.",
        "registros": [
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", DWORD, 0),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection", "AllowTelemetry", DWORD, 0),
        ],
        "servicos": ["DiagTrack", "dmwappushservice"],
        "tarefas": [],
    },
    {
        "id": "tarefas_telemetria",
        "nome": "Desativar tarefas agendadas de telemetria",
        "descricao": "Desliga o Compatibility Appraiser e o programa de melhoria da experiência (CEIP).",
        "registros": [],
        "servicos": [],
        "tarefas": [
            r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
            r"\Microsoft\Windows\Application Experience\ProgramDataUpdater",
            r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
            r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
        ],
    },
    {
        "id": "apps_segundo_plano",
        "nome": "Desativar aplicativos em segundo plano",
        "descricao": "Impede que apps da Microsoft Store fiquem rodando escondidos consumindo RAM e CPU.",
        "registros": [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", DWORD, 1),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", DWORD, 0),
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", DWORD, 2),
        ],
        "servicos": [],
        "tarefas": [],
    },
    {
        "id": "sugestoes_anuncios",
        "nome": "Desativar sugestões, dicas e anúncios do sistema",
        "descricao": "Remove propaganda do menu Iniciar, da tela de bloqueio e o ID de publicidade.",
        "registros": [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SystemPaneSuggestionsEnabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SilentInstalledAppsEnabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338388Enabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338389Enabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-353694Enabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "RotatingLockScreenOverlayEnabled", DWORD, 0),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", DWORD, 0),
        ],
        "servicos": [],
        "tarefas": [],
    },
    {
        "id": "cortana_busca_web",
        "nome": "Desativar Cortana e busca na web do menu Iniciar",
        "descricao": "A busca passa a procurar só no seu PC, ficando bem mais rápida.",
        "registros": [
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", DWORD, 0),
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "DisableWebSearch", DWORD, 1),
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "ConnectedSearchUseWeb", DWORD, 0),
        ],
        "servicos": [],
        "tarefas": [],
    },
    {
        "id": "game_dvr",
        "nome": "Desativar Game DVR / gravação em segundo plano",
        "descricao": "Recomendado para jogos: remove a gravação automática da Xbox Game Bar.",
        "registros": [
            ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", DWORD, 0),
            ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", DWORD, 0),
        ],
        "servicos": [],
        "tarefas": [],
    },
    {
        "id": "indexacao_busca",
        "nome": "Desativar indexação de arquivos (Windows Search)",
        "descricao": "Alivia o HD, mas a busca por arquivos fica mais lenta. Reversível.",
        "registros": [],
        "servicos": ["WSearch"],
        "tarefas": [],
    },
    {
        "id": "sysmain",
        "nome": "Desativar SysMain (antigo Superfetch)",
        "descricao": "Útil em PCs com HD antigo e uso de disco em 100%. Em SSD, o ganho é pequeno.",
        "registros": [],
        "servicos": ["SysMain"],
        "tarefas": [],
    },
    {
        "id": "hibernacao",
        "nome": "Desativar hibernação (libera vários GB em C:)",
        "descricao": "Apaga o hiberfil.sys. Isso também desliga a Inicialização Rápida.",
        "registros": [],
        "servicos": [],
        "tarefas": [],
        "comando": (["powercfg", "/hibernate", "off"], ["powercfg", "/hibernate", "on"]),
    },
]


def aplicar_tweak(tweak: dict, backup: dict, log=print) -> bool:
    """
    Aplica um ajuste SALVANDO ANTES o estado original no dicionário de backup.
    Se o mesmo tweak já foi aplicado antes, o backup antigo é preservado
    (senão salvaríamos o valor já otimizado como se fosse o original).
    """
    tid = tweak["id"]
    ja_tem_backup = tid in backup["tweaks"]

    estado = backup["tweaks"].get(tid, {
        "nome": tweak["nome"],
        "data": "",
        "registros": [],
        "servicos": [],
        "tarefas": [],
        "comando": False,
    })
    estado["nome"] = tweak["nome"]
    estado["data"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --- Registro -----------------------------------------------------------
    for hive, caminho, nome, tipo, valor_novo in tweak.get("registros", []):
        try:
            if not ja_tem_backup:
                atual = registro_ler(hive, caminho, nome)
                estado["registros"].append({
                    "hive": hive,
                    "caminho": caminho,
                    "nome": nome,
                    "existia": atual is not None,
                    "valor": atual[0] if atual else None,
                    "tipo": atual[1] if atual else None,
                })
            registro_escrever(hive, caminho, nome, tipo, valor_novo)
            log(f"   OK  {hive}\\{caminho} -> {nome} = {valor_novo}")
        except PermissionError:
            log(f"   [erro] Sem permissão para {hive}\\{caminho} (rode como Administrador)")
        except Exception as e:
            log(f"   [erro] {hive}\\{caminho}\\{nome}: {e}")

    # --- Serviços -----------------------------------------------------------
    for svc in tweak.get("servicos", []):
        atual = servico_ler_start(svc)
        if atual is None:
            log(f"   [pulado] Serviço {svc} não existe nesta versão do Windows.")
            continue
        if not ja_tem_backup:
            estado["servicos"].append({"nome": svc, "start": atual})
        ok, msg = servico_definir_start(svc, 4)
        log(f"   {'OK ' if ok else '[erro]'} Serviço {svc}: {msg}")

    # --- Tarefas agendadas --------------------------------------------------
    for tarefa in tweak.get("tarefas", []):
        ok, msg = tarefa_definir(tarefa, ativar=False)
        if ok and not ja_tem_backup:
            estado["tarefas"].append(tarefa)
        log(f"   {'OK ' if ok else '[pulado]'} Tarefa {tarefa.split(chr(92))[-1]}")

    # --- Comando externo ----------------------------------------------------
    if "comando" in tweak:
        aplicar_cmd, _ = tweak["comando"]
        codigo, saida = rodar(aplicar_cmd)
        if codigo == 0:
            estado["comando"] = True
            log(f"   OK  Comando executado: {' '.join(aplicar_cmd)}")
        else:
            log(f"   [erro] {' '.join(aplicar_cmd)}: {saida[:150]}")

    backup["tweaks"][tid] = estado
    return True


def reverter_tweak(tid: str, backup: dict, log=print) -> bool:
    """
    Desfaz um ajuste usando exclusivamente o que foi salvo no backup.
    Valor que não existia antes é APAGADO (volta ao comportamento padrão).
    """
    estado = backup["tweaks"].get(tid)
    if not estado:
        log(f"   [aviso] Nenhum backup encontrado para '{tid}'.")
        return False

    tweak = next((t for t in TWEAKS if t["id"] == tid), None)

    # --- Registro -----------------------------------------------------------
    for r in estado.get("registros", []):
        try:
            if r["existia"]:
                registro_escrever(r["hive"], r["caminho"], r["nome"], r["tipo"], r["valor"])
                log(f"   OK  Restaurado {r['nome']} = {r['valor']}")
            else:
                registro_apagar_valor(r["hive"], r["caminho"], r["nome"])
                log(f"   OK  Removido {r['nome']} (não existia antes)")
        except Exception as e:
            log(f"   [erro] Ao restaurar {r['nome']}: {e}")

    # --- Serviços -----------------------------------------------------------
    for s in estado.get("servicos", []):
        ok, msg = servico_definir_start(s["nome"], s["start"])
        log(f"   {'OK ' if ok else '[erro]'} Serviço {s['nome']} -> {MAPA_START.get(s['start'], s['start'])}")

    # --- Tarefas ------------------------------------------------------------
    for tarefa in estado.get("tarefas", []):
        ok, msg = tarefa_definir(tarefa, ativar=True)
        log(f"   {'OK ' if ok else '[erro]'} Tarefa reativada: {tarefa.split(chr(92))[-1]}")

    # --- Comando ------------------------------------------------------------
    if estado.get("comando") and tweak and "comando" in tweak:
        _, reverter_cmd = tweak["comando"]
        codigo, saida = rodar(reverter_cmd)
        log(f"   {'OK ' if codigo == 0 else '[erro]'} Comando de reversão: {' '.join(reverter_cmd)}")

    # Só removemos o registro de backup depois de tudo processado.
    backup["tweaks"].pop(tid, None)
    return True


def criar_ponto_restauracao(log=print) -> bool:
    """
    Cria um Ponto de Restauração do Sistema via PowerShell.
    Pode falhar se a Proteção do Sistema estiver desligada — nesse caso apenas
    avisamos, sem impedir o resto do programa.
    """
    log("Criando ponto de restauração do sistema (pode demorar ~1 min)...")
    codigo, saida = rodar([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "Checkpoint-Computer -Description 'Otimizador PC' -RestorePointType 'MODIFY_SETTINGS'"
    ])
    if codigo == 0:
        log("Ponto de restauração criado com sucesso.\n")
        return True
    log("Não foi possível criar o ponto de restauração. "
        "Ative a Proteção do Sistema em: Painel de Controle > Sistema > "
        "Proteção do Sistema.\n")
    return False


# =============================================================================
# 9. INTERFACE GRÁFICA
# =============================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Janela(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NOME} v{APP_VERSAO}")
        self.geometry("960x700")
        self.minsize(860, 620)

        self.backup = carregar_backup()
        self.vars_limpeza = {}    # id -> BooleanVar
        self.vars_tweaks = {}     # id -> BooleanVar
        self.vars_reversao = {}   # id -> BooleanVar
        self.rodando = False      # trava para não executar duas tarefas juntas

        self._montar_cabecalho()
        self._montar_abas()
        self._montar_log()

        self.log(f"{APP_NOME} iniciado.")
        self.log(f"Backup do estado original: {ARQUIVO_BACKUP}")
        if not eh_admin():
            self.log("AVISO: sem privilégio de Administrador. Vários ajustes vão falhar.")

    # ---------------------------------------------------------------- layout
    def _montar_cabecalho(self):
        topo = ctk.CTkFrame(self, corner_radius=0)
        topo.pack(fill="x")
        ctk.CTkLabel(topo, text=APP_NOME,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=16, pady=12)
        status = "Administrador" if eh_admin() else "Sem privilégio de Administrador"
        ctk.CTkLabel(topo, text=status, text_color=("#2e7d32" if eh_admin() else "#c62828"),
                     font=ctk.CTkFont(size=12)).pack(side="right", padx=16)

    def _montar_abas(self):
        self.abas = ctk.CTkTabview(self, height=380)
        self.abas.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.abas.add("Limpeza")
        self.abas.add("Otimização")
        self.abas.add("Reverter")

        self._aba_limpeza(self.abas.tab("Limpeza"))
        self._aba_otimizacao(self.abas.tab("Otimização"))
        self._aba_reversao(self.abas.tab("Reverter"))

    def _aba_limpeza(self, pai):
        lista = ctk.CTkScrollableFrame(pai, label_text="Marque o que deseja apagar")
        lista.pack(fill="both", expand=True, padx=6, pady=6)

        for tid, rotulo, descricao, _ in TAREFAS_LIMPEZA:
            var = ctk.BooleanVar(value=(tid in ("temp_user", "temp_win")))
            self.vars_limpeza[tid] = var
            ctk.CTkCheckBox(lista, text=rotulo, variable=var,
                            font=ctk.CTkFont(size=13)).pack(anchor="w", padx=8, pady=(10, 0))
            ctk.CTkLabel(lista, text=descricao, font=ctk.CTkFont(size=11),
                         text_color="gray60", wraplength=780,
                         justify="left").pack(anchor="w", padx=34)

        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(barra, text="Marcar tudo", width=110,
                      command=lambda: self._marcar(self.vars_limpeza, True)).pack(side="left", padx=4)
        ctk.CTkButton(barra, text="Desmarcar tudo", width=120, fg_color="gray30",
                      command=lambda: self._marcar(self.vars_limpeza, False)).pack(side="left", padx=4)
        self.btn_limpar = ctk.CTkButton(barra, text="Executar limpeza", width=170,
                                        command=self.acao_limpar)
        self.btn_limpar.pack(side="right", padx=4)

    def _aba_otimizacao(self, pai):
        lista = ctk.CTkScrollableFrame(pai, label_text="Marque o que deseja desativar")
        lista.pack(fill="both", expand=True, padx=6, pady=6)

        for tweak in TWEAKS:
            var = ctk.BooleanVar(value=False)
            self.vars_tweaks[tweak["id"]] = var
            ctk.CTkCheckBox(lista, text=tweak["nome"], variable=var,
                            font=ctk.CTkFont(size=13)).pack(anchor="w", padx=8, pady=(10, 0))
            ctk.CTkLabel(lista, text=tweak["descricao"], font=ctk.CTkFont(size=11),
                         text_color="gray60", wraplength=780,
                         justify="left").pack(anchor="w", padx=34)

        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(barra, text="Marcar tudo", width=110,
                      command=lambda: self._marcar(self.vars_tweaks, True)).pack(side="left", padx=4)
        ctk.CTkButton(barra, text="Desmarcar tudo", width=120, fg_color="gray30",
                      command=lambda: self._marcar(self.vars_tweaks, False)).pack(side="left", padx=4)

        self.var_ponto = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(barra, text="Criar ponto de restauração antes",
                        variable=self.var_ponto,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=16)

        self.btn_otimizar = ctk.CTkButton(barra, text="Aplicar otimizações", width=180,
                                          command=self.acao_otimizar)
        self.btn_otimizar.pack(side="right", padx=4)

    def _aba_reversao(self, pai):
        self.frame_reversao = ctk.CTkScrollableFrame(
            pai, label_text="Ajustes aplicados — marque para restaurar ao padrão do Windows")
        self.frame_reversao.pack(fill="both", expand=True, padx=6, pady=6)

        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(barra, text="Atualizar lista", width=130, fg_color="gray30",
                      command=self.atualizar_reversao).pack(side="left", padx=4)
        self.btn_reverter = ctk.CTkButton(barra, text="Restaurar selecionados", width=190,
                                          fg_color="#b45309", hover_color="#92400e",
                                          command=self.acao_reverter)
        self.btn_reverter.pack(side="right", padx=4)
        ctk.CTkButton(barra, text="Restaurar tudo", width=140, fg_color="#7f1d1d",
                      hover_color="#991b1b",
                      command=self.acao_reverter_tudo).pack(side="right", padx=4)

        self.atualizar_reversao()

    def _montar_log(self):
        quadro = ctk.CTkFrame(self)
        quadro.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(quadro, text="Registro de atividades",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.caixa_log = ctk.CTkTextbox(quadro, height=170, font=ctk.CTkFont(family="Consolas", size=12))
        self.caixa_log.pack(fill="both", expand=True, padx=10, pady=8)

    # ------------------------------------------------------------- auxiliares
    def _marcar(self, dicionario, valor):
        for v in dicionario.values():
            v.set(valor)

    def log(self, texto: str):
        """Escreve no log. Pode ser chamado de qualquer thread com segurança."""
        self.after(0, self._escrever_log, texto)

    def _escrever_log(self, texto: str):
        hora = datetime.now().strftime("%H:%M:%S")
        self.caixa_log.insert("end", f"[{hora}] {texto}\n")
        self.caixa_log.see("end")

    def _travar_botoes(self, travado: bool):
        estado = "disabled" if travado else "normal"
        for b in (self.btn_limpar, self.btn_otimizar, self.btn_reverter):
            b.configure(state=estado)

    def _executar_em_thread(self, funcao):
        """
        Roda a tarefa pesada em uma thread separada para a janela não congelar.
        A trava self.rodando impede duas execuções simultâneas.
        """
        if self.rodando:
            messagebox.showinfo(APP_NOME, "Aguarde a tarefa atual terminar.")
            return
        self.rodando = True
        self._travar_botoes(True)

        def alvo():
            try:
                funcao()
            except Exception as e:
                self.log(f"[ERRO INESPERADO] {e}")
            finally:
                self.rodando = False
                self.after(0, self._travar_botoes, False)

        threading.Thread(target=alvo, daemon=True).start()

    def atualizar_reversao(self):
        """Redesenha a aba Reverter lendo o arquivo de backup."""
        for w in self.frame_reversao.winfo_children():
            w.destroy()
        self.vars_reversao.clear()

        self.backup = carregar_backup()
        aplicados = self.backup.get("tweaks", {})

        if not aplicados:
            ctk.CTkLabel(self.frame_reversao,
                         text="Nenhum ajuste aplicado por este programa até agora.",
                         text_color="gray60").pack(anchor="w", padx=10, pady=14)
            return

        for tid, estado in aplicados.items():
            var = ctk.BooleanVar(value=False)
            self.vars_reversao[tid] = var
            ctk.CTkCheckBox(self.frame_reversao, text=estado.get("nome", tid),
                            variable=var, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=8, pady=(10, 0))
            ctk.CTkLabel(self.frame_reversao,
                         text=f"Aplicado em {estado.get('data', '?')}",
                         font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=34)

    # ------------------------------------------------------------------ ações
    def acao_limpar(self):
        selecionados = [t for t in TAREFAS_LIMPEZA if self.vars_limpeza[t[0]].get()]
        if not selecionados:
            messagebox.showinfo(APP_NOME, "Marque pelo menos uma opção de limpeza.")
            return
        if any(t[0] == "lixeira" for t in selecionados):
            if not messagebox.askyesno(
                    APP_NOME,
                    "A Lixeira será esvaziada e os arquivos não poderão ser recuperados.\n\nContinuar?"):
                return

        def tarefa():
            self.log("=" * 60)
            self.log("LIMPEZA INICIADA")
            total_arquivos = total_bytes = total_pulados = 0
            for tid, rotulo, _, funcao in selecionados:
                self.log(f"> {rotulo}")
                arq, bts, pul = funcao(self.log)
                total_arquivos += arq
                total_bytes += bts
                total_pulados += pul
                if tid not in ("lixeira", "dns"):
                    self.log(f"   {arq} itens apagados | {formatar_tamanho(bts)} liberados | "
                             f"{pul} em uso (pulados)")
            self.log("-" * 60)
            self.log(f"CONCLUÍDO: {total_arquivos} itens removidos, "
                     f"{formatar_tamanho(total_bytes)} de espaço liberado.")
            self.log("=" * 60)

        self._executar_em_thread(tarefa)

    def acao_otimizar(self):
        selecionados = [t for t in TWEAKS if self.vars_tweaks[t["id"]].get()]
        if not selecionados:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um ajuste.")
            return
        if not eh_admin():
            messagebox.showwarning(
                APP_NOME, "Feche e abra o programa como Administrador para aplicar os ajustes.")
            return
        if not messagebox.askyesno(
                APP_NOME,
                f"{len(selecionados)} ajuste(s) serão aplicados.\n"
                "O estado atual será salvo e pode ser revertido na aba Reverter.\n\nContinuar?"):
            return

        criar_ponto = self.var_ponto.get()

        def tarefa():
            self.log("=" * 60)
            self.log("OTIMIZAÇÃO INICIADA")
            if criar_ponto:
                criar_ponto_restauracao(self.log)
            for tweak in selecionados:
                self.log(f"> {tweak['nome']}")
                aplicar_tweak(tweak, self.backup, self.log)
            salvar_backup(self.backup)
            self.log("-" * 60)
            self.log("CONCLUÍDO. Reinicie o PC para que tudo tenha efeito.")
            self.log("=" * 60)
            self.after(0, self.atualizar_reversao)

        self._executar_em_thread(tarefa)

    def acao_reverter(self):
        ids = [tid for tid, var in self.vars_reversao.items() if var.get()]
        if not ids:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um ajuste para restaurar.")
            return
        self._reverter_ids(ids)

    def acao_reverter_tudo(self):
        ids = list(self.backup.get("tweaks", {}).keys())
        if not ids:
            messagebox.showinfo(APP_NOME, "Não há nada para restaurar.")
            return
        self._reverter_ids(ids)

    def _reverter_ids(self, ids):
        if not eh_admin():
            messagebox.showwarning(
                APP_NOME, "Feche e abra o programa como Administrador para restaurar os ajustes.")
            return
        if not messagebox.askyesno(
                APP_NOME, f"Restaurar {len(ids)} ajuste(s) para o padrão do Windows?"):
            return

        def tarefa():
            self.log("=" * 60)
            self.log("REVERSÃO INICIADA")
            for tid in ids:
                nome = self.backup["tweaks"].get(tid, {}).get("nome", tid)
                self.log(f"> {nome}")
                reverter_tweak(tid, self.backup, self.log)
            salvar_backup(self.backup)
            self.log("-" * 60)
            self.log("CONCLUÍDO. Reinicie o PC para finalizar a restauração.")
            self.log("=" * 60)
            self.after(0, self.atualizar_reversao)

        self._executar_em_thread(tarefa)


# =============================================================================
# 10. PONTO DE ENTRADA
# =============================================================================

def main():
    if not eh_windows():
        print("Este programa só funciona no Windows.")
        return

    # Se não estiver elevado, pede elevação e reabre. O "--sem-admin" permite
    # abrir mesmo sem UAC (útil para testar a interface).
    if not eh_admin() and "--sem-admin" not in sys.argv:
        reexecutar_como_admin()
        return

    app = Janela()
    app.mainloop()


if __name__ == "__main__":
    main()
