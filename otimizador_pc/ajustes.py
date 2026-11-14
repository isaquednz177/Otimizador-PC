# -*- coding: utf-8 -*-
"""
Ajustes do Windows, todos reversíveis.

Cada ajuste é uma lista de PASSOS. Cada passo sabe:
  capturar(s)            -> como está agora (None = não existe neste Windows)
  aplicar(s, guardado)   -> faz a mudança
  reverter(s, original)  -> volta ao que estava
  ja_aplicado(s)         -> True/False/None (None = não existe neste Windows)

Regras do motor (aplicar_ajuste / reverter_ajuste):
1. O estado original de cada passo é GRAVADO NO DISCO antes da mudança.
   Se o programa fechar no meio, o original não se perde.
2. Se o passo já tem original guardado (de outra vez, ou de outro ajuste),
   ele é reaproveitado: nunca guardamos o valor já otimizado como "original".
3. Na reversão, só sai do backup o passo que voltou de verdade. Se algo
   falhar, ele continua lá para tentar de novo.
4. A reversão usa só o que está no backup (classe + parâmetros), então
   funciona até para passos que saíram desta lista em versões novas.
"""

from dataclasses import dataclass, field

from otimizador_pc.sistema import REG_DWORD, SERVICOS_CONFIGURAVEIS
from otimizador_pc.util import agora_texto

# Plano de energia "Alto desempenho" do Windows (o GUID é o mesmo em todo PC).
ALTO_DESEMPENHO = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


# ---------------------------------------------------------------- valores no JSON
def _para_json(valor):
    if isinstance(valor, (bytes, bytearray)):
        return {"hex": bytes(valor).hex()}
    return valor


def _de_json(valor):
    if isinstance(valor, dict) and "hex" in valor:
        return bytes.fromhex(valor["hex"])
    return valor


# ---------------------------------------------------------------- passos
class Registro:
    classe = "registro"

    def __init__(self, hive, caminho, nome, tipo, valor):
        self.hive, self.caminho, self.nome, self.tipo, self.valor = hive, caminho, nome, tipo, valor

    @property
    def chave(self):
        return f"reg:{self.hive}\\{self.caminho}\\{self.nome}"

    def params(self):
        return {"hive": self.hive, "caminho": self.caminho, "nome": self.nome,
                "tipo": self.tipo, "valor": _para_json(self.valor)}

    def descrever(self):
        return f"{self.hive}\\{self.caminho}\\{self.nome}"

    def capturar(self, s):
        atual = s.reg_ler(self.hive, self.caminho, self.nome)
        if atual is None:
            return {"existia": False, "valor": None, "tipo": None}
        return {"existia": True, "valor": _para_json(atual[0]), "tipo": atual[1]}

    def aplicar(self, s, guardado):
        s.reg_escrever(self.hive, self.caminho, self.nome, self.tipo, self.valor)
        return True, f"{self.nome} = {self.valor}"

    def reverter(self, s, original, guardado):
        if original.get("existia"):
            s.reg_escrever(self.hive, self.caminho, self.nome, original["tipo"],
                           _de_json(original["valor"]))
            return True, f"{self.nome} voltou a {original['valor']}"
        s.reg_apagar(self.hive, self.caminho, self.nome)
        return True, f"{self.nome} apagado (não existia antes)"

    def ja_aplicado(self, s, guardado=None):
        atual = s.reg_ler(self.hive, self.caminho, self.nome)
        return atual is not None and atual[0] == _de_json(self.valor)


class Servico:
    classe = "servico"

    def __init__(self, nome):
        if nome not in SERVICOS_CONFIGURAVEIS:
            raise ValueError(f"serviço fora da lista permitida: {nome}")
        self.nome = nome

    @property
    def chave(self):
        return f"svc:{self.nome}"

    def params(self):
        return {"nome": self.nome}

    def descrever(self):
        return f"serviço {self.nome}"

    def capturar(self, s):
        cfg = s.servico_config(self.nome)
        if cfg is None:
            return None
        return {"start": cfg["start"], "atrasado": cfg["atrasado"],
                "rodando": s.servico_estado(self.nome) == "RUNNING"}

    def aplicar(self, s, guardado):
        ok, msg = s.servico_definir(self.nome, 4)
        if not ok:
            return False, msg
        parou = s.servico_parar(self.nome)
        return True, "desativado" + ("" if parou else " (para de vez depois de reiniciar)")

    def reverter(self, s, original, guardado):
        start = int(original["start"])
        if start == 4:
            return True, "já estava desativado antes"
        ok, msg = s.servico_definir(self.nome, start, bool(original.get("atrasado")))
        if not ok:
            return False, msg
        if original.get("rodando"):
            s.servico_iniciar(self.nome)
        return True, msg

    def ja_aplicado(self, s, guardado=None):
        cfg = s.servico_config(self.nome)
        return None if cfg is None else cfg["start"] == 4


class Tarefa:
    classe = "tarefa"

    def __init__(self, caminho):
        self.caminho = caminho

    @property
    def chave(self):
        return f"task:{self.caminho}"

    def params(self):
        return {"caminho": self.caminho}

    def descrever(self):
        return "tarefa " + self.caminho.rsplit("\\", 1)[-1]

    def capturar(self, s):
        ativa = s.tarefa_ativa(self.caminho)
        return None if ativa is None else {"ativa": ativa}

    def aplicar(self, s, guardado):
        return s.tarefa_definir(self.caminho, False)

    def reverter(self, s, original, guardado):
        if not original.get("ativa"):
            return True, "já estava desligada antes"
        return s.tarefa_definir(self.caminho, True)

    def ja_aplicado(self, s, guardado=None):
        ativa = s.tarefa_ativa(self.caminho)
        return None if ativa is None else not ativa


class Hibernacao:
    classe = "hibernacao"
    chave = "hibernacao"

    def params(self):
        return {}

    def descrever(self):
        return "hibernação"

    def capturar(self, s):
        ligada = s.hibernacao_ligada()
        return {"ligada": True if ligada is None else bool(ligada)}

    def aplicar(self, s, guardado):
        return s.hibernacao_definir(False)

    def reverter(self, s, original, guardado):
        if not original.get("ligada"):
            return True, "já estava desligada antes"
        return s.hibernacao_definir(True)

    def ja_aplicado(self, s, guardado=None):
        return s.hibernacao_ligada() is False


class PlanoEnergia:
    """Troca para o 'Alto desempenho'. Se o PC esconde esse plano, cria uma cópia dele."""
    classe = "energia"
    chave = "energia"

    def params(self):
        return {}

    def descrever(self):
        return "plano de energia"

    def capturar(self, s):
        guid = s.plano_ativo()
        return None if guid is None else {"guid": guid}

    def aplicar(self, s, guardado):
        planos = s.planos()
        alvo = None
        if ALTO_DESEMPENHO in planos:
            alvo = ALTO_DESEMPENHO
        elif guardado.get("criado") in planos:
            alvo = guardado["criado"]
        else:
            alvo = s.plano_duplicar(ALTO_DESEMPENHO)
            if not alvo:
                return False, "este PC não tem o plano Alto desempenho"
            guardado["criado"] = alvo  # para apagar a cópia ao reverter
        ok, msg = s.plano_ativar(alvo)
        return ok, ("Alto desempenho ativado" if ok else msg)

    def reverter(self, s, original, guardado):
        ok, msg = s.plano_ativar(original["guid"])
        if not ok:
            return False, msg
        criado = (guardado or {}).get("criado")
        if criado and criado != original["guid"]:
            s.plano_apagar(criado)
        return True, "plano de antes reativado"

    def ja_aplicado(self, s, guardado=None):
        ativo = s.plano_ativo()
        if ativo is None:
            return None
        return ativo == ALTO_DESEMPENHO or ativo == (guardado or {}).get("criado")


class Mouse:
    """Desliga o 'Aumentar precisão do ponteiro' (aceleração). Vale na hora."""
    classe = "mouse"
    chave = "mouse"

    def params(self):
        return {}

    def descrever(self):
        return "precisão do ponteiro"

    def capturar(self, s):
        vals = s.mouse_ler()
        return None if vals is None else {"valores": list(vals)}

    def aplicar(self, s, guardado):
        return s.mouse_definir([0, 0, 0])

    def reverter(self, s, original, guardado):
        return s.mouse_definir(original["valores"])

    def ja_aplicado(self, s, guardado=None):
        vals = s.mouse_ler()
        return None if vals is None else vals[2] == 0


CLASSES = {c.classe: c for c in (Registro, Servico, Tarefa, Hibernacao, PlanoEnergia, Mouse)}


def montar_passo(classe: str, params: dict):
    cls = CLASSES[classe]
    if cls is Registro:
        return Registro(params["hive"], params["caminho"], params["nome"], params.get("tipo"),
                        _de_json(params.get("valor")))
    return cls(**params)


# ---------------------------------------------------------------- lista de ajustes
@dataclass
class Ajuste:
    id: str
    nome: str
    descricao: str
    passos: list = field(default_factory=list)


def _reg(hive, caminho, nome, valor, tipo=REG_DWORD):
    return Registro(hive, caminho, nome, tipo, valor)


CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
AVANCADO = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"

AJUSTES = [
    Ajuste("telemetria", "Reduzir a telemetria (coleta de dados)",
           "Desliga os serviços DiagTrack e dmwappushservice e pede o nível mínimo de dados. "
           "No Windows Home e Pro o mínimo aceito é o \"necessário\"; desligar de vez só existe "
           "no Enterprise e no Education.",
           [_reg("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 0),
            _reg("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection", "AllowTelemetry", 0),
            Servico("DiagTrack"), Servico("dmwappushservice")]),

    Ajuste("tarefas_telemetria", "Desligar tarefas agendadas de telemetria",
           "Compatibility Appraiser e o programa de melhoria da experiência (CEIP). "
           "As que não existem no seu Windows são puladas.",
           [Tarefa(r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser"),
            Tarefa(r"\Microsoft\Windows\Application Experience\ProgramDataUpdater"),
            Tarefa(r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"),
            Tarefa(r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip")]),

    Ajuste("apps_segundo_plano", "Impedir apps da Loja em segundo plano",
           "Apps da Microsoft Store param de rodar escondidos. Notificações de alguns apps "
           "(Mail, Agenda, WhatsApp da Loja) podem atrasar.",
           [_reg("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", 1),
            _reg("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", 0),
            _reg("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", 2)]),

    Ajuste("sugestoes_anuncios", "Tirar sugestões, dicas e anúncios",
           "Menu Iniciar, tela de bloqueio, Explorador de Arquivos, \"Bem-vindo\" depois das "
           "atualizações, apps instalados sozinhos e o ID de publicidade.",
           [_reg("HKCU", CDM, "SystemPaneSuggestionsEnabled", 0),
            _reg("HKCU", CDM, "SilentInstalledAppsEnabled", 0),
            _reg("HKCU", CDM, "SoftLandingEnabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-310093Enabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-338388Enabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-338389Enabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-338393Enabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-353694Enabled", 0),
            _reg("HKCU", CDM, "SubscribedContent-353696Enabled", 0),
            _reg("HKCU", CDM, "RotatingLockScreenOverlayEnabled", 0),
            _reg("HKCU", AVANCADO, "ShowSyncProviderNotifications", 0),
            _reg("HKCU", AVANCADO, "Start_IrisRecommendations", 0),
            _reg("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0)]),

    # O id antigo fica para o backup da versão 1 continuar casando.
    Ajuste("cortana_busca_web", "Busca do menu Iniciar só no PC (sem Bing)",
           "A busca deixa de mandar o que você digita para a internet e de mostrar resultados "
           "do Bing. Vale depois de reiniciar ou de sair e entrar na conta.",
           [_reg("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1),
            _reg("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", 0),
            _reg("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "DisableWebSearch", 1),
            _reg("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "ConnectedSearchUseWeb", 0)]),

    Ajuste("game_dvr", "Desligar a gravação em segundo plano (Game DVR)",
           "A Xbox Game Bar para de gravar os últimos minutos de jogo o tempo todo, o que "
           "custa FPS. O atalho Win+G continua abrindo a barra.",
           [_reg("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0),
            _reg("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0),
            _reg("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 0)]),

    Ajuste("mouse_precisao", "Desligar a aceleração do mouse",
           "Desmarca \"Aumentar precisão do ponteiro\": o cursor anda sempre a mesma distância "
           "para o mesmo movimento. Bom para mirar em jogos. Vale na hora.",
           [Mouse()]),

    Ajuste("energia_desempenho", "Plano de energia Alto desempenho",
           "O processador não reduz tanto a velocidade. Em notebook, gasta mais bateria e "
           "esquenta mais; ao reverter, volta o plano que você usava.",
           [PlanoEnergia()]),

    Ajuste("indexacao_busca", "Desligar a indexação de arquivos (Windows Search)",
           "Alivia o disco em PCs com HD. A busca de arquivos fica bem mais lenta, e a do "
           "Outlook pode parar.",
           [Servico("WSearch")]),

    Ajuste("sysmain", "Desligar o SysMain (antigo Superfetch)",
           "Ajuda quando o HD fica em 100%. Em SSD o ganho é pequeno e os programas podem "
           "abrir um pouco mais devagar.",
           [Servico("SysMain")]),

    Ajuste("hibernacao", "Desligar a hibernação (libera espaço no C:)",
           "Apaga o hiberfil.sys, que ocupa vários GB. Também desliga a Inicialização Rápida, "
           "então o PC pode ligar alguns segundos mais devagar.",
           [Hibernacao()]),
]

AJUSTES_POR_ID = {a.id: a for a in AJUSTES}


# ---------------------------------------------------------------- motor
def _achar_guardado(dados: dict, chave: str):
    for reg in dados["ajustes"].values():
        if chave in reg.get("passos", {}):
            return reg["passos"][chave]
    return None


def aplicar_ajuste(ajuste: Ajuste, backup, s, log=print) -> bool:
    """Aplica um ajuste. Devolve True se todos os passos que existem deram certo."""
    dados = backup.dados
    reg = dados["ajustes"].setdefault(ajuste.id, {"nome": ajuste.nome, "data": "", "passos": {}})
    reg["nome"], reg["data"] = ajuste.nome, agora_texto()
    tudo_ok = True

    for passo in ajuste.passos:
        guardado = reg["passos"].get(passo.chave)
        if guardado is None:
            outro = _achar_guardado(dados, passo.chave)
            if outro is not None:
                guardado = dict(outro)  # o original de verdade já está em outro ajuste
            else:
                try:
                    original = passo.capturar(s)
                except Exception as e:
                    log(f"   [erro] {passo.descrever()}: não deu para ler como está ({e})")
                    tudo_ok = False
                    continue
                if original is None:
                    log(f"   [pulado] {passo.descrever()}: não existe neste Windows")
                    continue
                guardado = {"classe": passo.classe, "params": passo.params(), "original": original}
            reg["passos"][passo.chave] = guardado
            backup.salvar()  # o original vai para o disco ANTES da mudança

        try:
            ok, msg = passo.aplicar(s, guardado)
        except PermissionError:
            ok, msg = False, "sem permissão (abra como Administrador)"
        except Exception as e:
            ok, msg = False, str(e)
        backup.salvar()
        tudo_ok = tudo_ok and ok
        log(f"   {'OK ' if ok else '[erro]'} {passo.descrever()}: {msg}")

    if not reg["passos"]:
        dados["ajustes"].pop(ajuste.id, None)
        backup.salvar()
    return tudo_ok


def reverter_ajuste(aid: str, backup, s, log=print) -> bool:
    """Desfaz um ajuste. Devolve True se tudo voltou (e ele saiu do backup)."""
    dados = backup.dados
    reg = dados["ajustes"].get(aid)
    if not reg:
        log(f"   [aviso] nada guardado para '{aid}'")
        return False

    for chave in reversed(list(reg["passos"].keys())):
        g = reg["passos"][chave]
        try:
            passo = montar_passo(g["classe"], g["params"])
            ok, msg = passo.reverter(s, g["original"], g)
            nome = passo.descrever()
        except PermissionError:
            ok, msg, nome = False, "sem permissão (abra como Administrador)", chave
        except Exception as e:
            ok, msg, nome = False, str(e), chave
        if ok:
            del reg["passos"][chave]
            backup.salvar()
        log(f"   {'OK ' if ok else '[erro]'} {nome}: {msg}")

    if reg["passos"]:
        log(f"   {len(reg['passos'])} mudança(s) não voltaram; continuam guardadas para tentar de novo.")
        return False
    del dados["ajustes"][aid]
    backup.salvar()
    return True


def estado_do_ajuste(ajuste: Ajuste, s, dados=None) -> str:
    """'aplicado', 'parcial', 'padrao' ou 'indisponivel' (nada dele existe neste PC)."""
    guardados = {} if dados is None else dados.get("ajustes", {}).get(ajuste.id, {}).get("passos", {})
    resultados = []
    for passo in ajuste.passos:
        try:
            r = passo.ja_aplicado(s, guardados.get(passo.chave))
        except Exception:
            r = None
        if r is not None:
            resultados.append(r)
    if not resultados:
        return "indisponivel"
    if all(resultados):
        return "aplicado"
    return "parcial" if any(resultados) else "padrao"
