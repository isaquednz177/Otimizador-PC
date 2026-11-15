# -*- coding: utf-8 -*-
"""Um Windows de mentira, guardado em dicionários, para os testes."""

import os
import tempfile

from otimizador_pc.backup import Backup


class SistemaFalso:
    def __init__(self):
        self.reg = {}            # (hive, caminho.lower(), nome) -> (valor, tipo)
        self.servicos = {}       # nome -> {"start", "atrasado", "estado"}
        self.tarefas = {}        # caminho -> bool
        self.hibernacao = True
        self.plano = "381b4222-f694-41f0-9685-ff5bb260df2e"
        self.lista_planos = ["381b4222-f694-41f0-9685-ff5bb260df2e"]
        self.mouse = [6, 10, 1]
        self.abertos = set()
        self.pastas = {}
        self.comandos = []
        self.falhar_reg = set()  # nomes de valor que dão PermissionError ao gravar
        self.falhar_servico = set()
        self._novo = 0

    # registro
    def _k(self, hive, caminho, nome):
        return hive, caminho.lower(), nome

    def reg_ler(self, hive, caminho, nome):
        return self.reg.get(self._k(hive, caminho, nome))

    def reg_escrever(self, hive, caminho, nome, tipo, valor):
        if nome in self.falhar_reg:
            raise PermissionError("negado")
        self.reg[self._k(hive, caminho, nome)] = (valor, tipo)

    def reg_apagar(self, hive, caminho, nome):
        if nome in self.falhar_reg:
            raise PermissionError("negado")
        self.reg.pop(self._k(hive, caminho, nome), None)

    def reg_listar(self, hive, caminho):
        return [(n, v, t) for (h, c, n), (v, t) in self.reg.items() if h == hive and c == caminho.lower()]

    # serviços
    def servico_config(self, nome):
        s = self.servicos.get(nome)
        return None if s is None else {"start": s["start"], "atrasado": s["atrasado"]}

    def servico_estado(self, nome):
        s = self.servicos.get(nome)
        return None if s is None else s["estado"]

    def servico_definir(self, nome, start, atrasado=False):
        if nome in self.falhar_servico:
            return False, "negado"
        s = self.servicos[nome]
        if s["start"] <= 1:
            return False, "crítico"
        s["start"], s["atrasado"] = start, (start == 2 and atrasado)
        return True, "ok"

    def servico_parar(self, nome, espera=30):
        if nome in self.servicos:
            self.servicos[nome]["estado"] = "STOPPED"
        self.comandos.append(("parar", nome))
        return True

    def servico_iniciar(self, nome):
        if nome in self.servicos:
            self.servicos[nome]["estado"] = "RUNNING"
        self.comandos.append(("iniciar", nome))
        return True

    # tarefas
    def tarefa_ativa(self, caminho):
        return self.tarefas.get(caminho)

    def tarefa_definir(self, caminho, ativar):
        self.tarefas[caminho] = ativar
        return True, "ok"

    # energia
    def plano_ativo(self):
        return self.plano

    def planos(self):
        return list(self.lista_planos)

    def plano_ativar(self, guid):
        if guid not in self.lista_planos:
            return False, "não existe"
        self.plano = guid
        return True, "ok"

    def plano_duplicar(self, guid):
        self._novo += 1
        novo = f"00000000-0000-0000-0000-{self._novo:012d}"
        self.lista_planos.append(novo)
        return novo

    def plano_apagar(self, guid):
        self.lista_planos.remove(guid)
        return True

    # hibernação e mouse
    def hibernacao_ligada(self):
        return self.hibernacao

    def hibernacao_definir(self, ligar):
        self.hibernacao = ligar
        return True, "ok"

    def mouse_ler(self):
        return list(self.mouse)

    def mouse_definir(self, valores):
        self.mouse = list(valores)
        return True, "ok"

    # serviços de outros programas (usa os mesmos dados de self.servicos, com tipo/caminho)
    def reg_subchaves(self, hive, caminho):
        return list(self.servicos) if caminho.lower().endswith("services") else []

    def servico_info(self, nome):
        s = self.servicos.get(nome)
        if s is None:
            return None
        return {"start": s["start"], "atrasado": s["atrasado"], "tipo": s.get("tipo", 0x10),
                "caminho": s.get("caminho", ""), "exibicao": s.get("exibicao", nome)}

    def servico_terceiro_definir(self, nome, start, atrasado=False):
        from otimizador_pc.sistema import eh_servico_de_terceiro
        info = self.servico_info(nome)
        if info is None or not eh_servico_de_terceiro(nome, info["tipo"], info["caminho"]):
            return False, "não"
        self.servicos[nome]["start"] = start
        self.servicos[nome]["atrasado"] = start == 2 and atrasado
        return True, "ok"

    def encerrar(self, pids, forcar=False):
        self.comandos.append(("encerrar", tuple(pids), forcar))
        return True, ""

    # outros
    def processos(self):
        return set(self.abertos)

    def listar_pasta(self, pasta):
        return list(self.pastas.get(pasta, []))

    def rodar(self, comando, timeout=120):
        self.comandos.append(tuple(comando))
        return 0, ""

    def powershell(self, script, timeout=120):
        self.comandos.append(("powershell", script))
        return 0, ""


class BackupTemporario(Backup):
    """Backup num arquivo dentro de uma pasta temporária, que conta quantas vezes salvou."""

    def __init__(self):
        self.pasta = tempfile.mkdtemp(prefix="otim-teste-")
        self.salvamentos = 0
        super().__init__(os.path.join(self.pasta, "backup_estado.json"))

    def salvar(self):
        self.salvamentos += 1
        super().salvar()
