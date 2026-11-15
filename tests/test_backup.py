# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest

from falso import SistemaFalso

from otimizador_pc import ajustes as aj
from otimizador_pc.backup import VERSAO, Backup

# Mesma forma do backup que a versão 1.1 grava (dados de exemplo).
V1 = {
    "versao": "1.0",
    "tweaks": {
        "telemetria": {
            "nome": "Desativar telemetria", "data": "25/08/2026 18:02",
            "registros": [
                {"hive": "HKLM", "caminho": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                 "nome": "AllowTelemetry", "existia": False, "valor": None, "tipo": None},
                {"hive": "HKLM", "caminho": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
                 "nome": "AllowTelemetry", "existia": True, "valor": 1, "tipo": 4},
            ],
            "servicos": [{"nome": "DiagTrack", "start": 2}, {"nome": "dmwappushservice", "start": 3}],
            "tarefas": [], "comando": False,
        },
        "tarefas_telemetria": {
            "nome": "tarefas", "data": "25/08/2026 18:02", "registros": [], "servicos": [],
            "tarefas": [r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"],
            "comando": False,
        },
        "hibernacao": {"nome": "hib", "data": "", "registros": [], "servicos": [], "tarefas": [],
                       "comando": True},
        "indexacao_busca": {"nome": "busca", "data": "", "registros": [],
                            "servicos": [{"nome": "WSearch", "start": 2}], "tarefas": [], "comando": False},
        "nada": {"nome": "vazio", "data": "", "registros": [], "servicos": [], "tarefas": [], "comando": False},
    },
    "inicializacao": {
        "HKLM:SecurityHealth": {"hive": "HKLM", "caminho": r"Software\Microsoft\Windows\CurrentVersion\Run",
                                "nome": "SecurityHealth", "valor": r"%windir%\system32\SecurityHealthSystray.exe",
                                "tipo": 2, "data": "31/08/2026 09:11"},
    },
}


def arquivo_com(conteudo) -> str:
    pasta = tempfile.mkdtemp(prefix="otim-teste-")
    caminho = os.path.join(pasta, "backup_estado.json")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo if isinstance(conteudo, str) else json.dumps(conteudo))
    return caminho


class TestMigracao(unittest.TestCase):
    def setUp(self):
        self.arquivo = arquivo_com(V1)
        self.b = Backup(self.arquivo)

    def test_converte_tudo(self):
        d = self.b.dados
        self.assertEqual(d["versao"], VERSAO)
        self.assertEqual(set(d["ajustes"]), {"telemetria", "tarefas_telemetria", "hibernacao", "indexacao_busca"})
        tel = d["ajustes"]["telemetria"]["passos"]
        self.assertEqual(len(tel), 4)
        self.assertEqual(tel["svc:DiagTrack"]["original"], {"start": 2, "atrasado": False, "rodando": True})
        self.assertEqual(tel["svc:dmwappushservice"]["original"]["rodando"], False)
        busca = d["ajustes"]["indexacao_busca"]["passos"]["svc:WSearch"]["original"]
        self.assertTrue(busca["atrasado"], "o Windows vem com o WSearch em início atrasado")
        self.assertEqual(d["ajustes"]["hibernacao"]["passos"]["hibernacao"]["original"], {"ligada": True})
        self.assertIn("HKLM:SecurityHealth", d["inicializacao_removida"])
        self.assertIsNotNone(self.b.aviso)

    def test_guarda_copia_e_regrava_no_formato_novo(self):
        pasta = os.path.dirname(self.arquivo)
        with open(os.path.join(pasta, "backup_estado.v1.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), V1)
        with open(self.arquivo, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["versao"], VERSAO)
        self.assertIsNone(Backup(self.arquivo).aviso)  # na segunda vez já está convertido

    def test_reverte_o_que_a_versao_1_fez(self):
        s = SistemaFalso()
        caminho_pol = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection"
        s.reg_escrever("HKLM", caminho_pol, "AllowTelemetry", 4, 0)
        s.reg_escrever("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 4, 0)
        s.servicos["DiagTrack"] = {"start": 4, "atrasado": False, "estado": "STOPPED"}
        s.servicos["dmwappushservice"] = {"start": 4, "atrasado": False, "estado": "STOPPED"}
        s.servicos["WSearch"] = {"start": 4, "atrasado": False, "estado": "STOPPED"}
        tarefa = r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"
        s.tarefas[tarefa] = False
        s.hibernacao = False

        for aid in list(self.b.dados["ajustes"]):
            self.assertTrue(aj.reverter_ajuste(aid, self.b, s, lambda *_: None), aid)

        self.assertEqual(s.reg_ler("HKLM", caminho_pol, "AllowTelemetry"), (1, 4))
        self.assertIsNone(s.reg_ler("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry"))
        self.assertEqual(s.servicos["DiagTrack"], {"start": 2, "atrasado": False, "estado": "RUNNING"})
        self.assertEqual(s.servicos["dmwappushservice"]["start"], 3)
        self.assertEqual(s.servicos["WSearch"]["start"], 2)
        self.assertTrue(s.servicos["WSearch"]["atrasado"])
        self.assertTrue(s.tarefas[tarefa])
        self.assertTrue(s.hibernacao)
        self.assertEqual(self.b.dados["ajustes"], {})


class TestArquivo(unittest.TestCase):
    def test_sem_arquivo_comeca_vazio(self):
        pasta = tempfile.mkdtemp(prefix="otim-teste-")
        b = Backup(os.path.join(pasta, "sub", "backup_estado.json"))
        self.assertEqual(b.dados["ajustes"], {})
        self.assertFalse(os.path.exists(b.arquivo))
        b.salvar()
        self.assertTrue(os.path.exists(b.arquivo))

    def test_corrompido_e_guardado_de_lado_e_nao_apagado(self):
        arquivo = arquivo_com('{"versao": 2, "ajustes": {"meio')
        b = Backup(arquivo)
        self.assertEqual(b.dados["ajustes"], {})
        self.assertIn("danificado", b.aviso)
        pasta = os.path.dirname(arquivo)
        guardados = [n for n in os.listdir(pasta) if n.startswith("backup_estado.corrompido-")]
        self.assertEqual(len(guardados), 1)
        with open(os.path.join(pasta, guardados[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"versao": 2, "ajustes": {"meio')

    def test_gravacao_nao_deixa_temporario(self):
        arquivo = arquivo_com({"versao": 2, "ajustes": {}, "inicializacao_removida": {}})
        b = Backup(arquivo)
        b.dados["ajustes"]["x"] = {"nome": "x", "data": "", "passos": {}}
        b.salvar()
        self.assertFalse(os.path.exists(arquivo + ".tmp"))
        with open(arquivo, encoding="utf-8") as f:
            self.assertIn("x", json.load(f)["ajustes"])


if __name__ == "__main__":
    unittest.main()
