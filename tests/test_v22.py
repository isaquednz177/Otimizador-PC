# -*- coding: utf-8 -*-
"""Hardware, modo jogo, aviso de versão nova, downloads incompletos e preferências."""
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import date

from falso import BackupTemporario, SistemaFalso

from otimizador_pc import atualizacao, hardware as hw, limpeza as lp, modo_jogo as mj
from otimizador_pc.ajustes import ALTO_DESEMPENHO
from otimizador_pc.config import Config
from otimizador_pc.processos import Grupo

# O que o notebook do Isaque respondeu (Acer Aspire, 1 pente de 8 GB DDR5 em 2 encaixes).
DADOS = {
    "pentes": [{"DeviceLocator": "Controller0-ChannelA-DIMM0", "Capacity": 8589934592, "Speed": 5600,
                "ConfiguredClockSpeed": 5200, "Manufacturer": "HANA Electronics", "PartNumber": "X",
                "SMBIOSMemoryType": 34, "FormFactor": 12}],
    "placa_memoria": [{"MemoryDevices": 2, "MaxCapacityEx": 67108864, "MaxCapacity": 67108864}],
    "cpu": {"Name": "13th Gen Intel(R) Core(TM) i3-1305U", "NumberOfCores": 5, "NumberOfLogicalProcessors": 6},
    "video": [{"Name": "Intel(R) UHD Graphics", "DriverVersion": "32.0.101.5768", "DriverDate": "2024-07-23",
               "PNPDeviceID": "PCI\\VEN_8086&DEV_A7A9"},
              {"Name": "Microsoft Basic Display Adapter", "DriverDate": "2006-06-21", "PNPDeviceID": "ROOT\\X"}],
    "discos": [{"DeviceId": "0", "FriendlyName": "NVMe SM2P41C8-256GC5", "MediaType": "SSD", "BusType": "NVMe",
                "HealthStatus": "Healthy", "Size": 256060514304}],
    "atualizacoes": [{"HotFixID": "KB5127936", "Data": "2026-10-29"}],
    "modelo": [{"Manufacturer": "Acer", "Model": "Aspire AG15-51P"}],
}

BATERIA = """<?xml version="1.0" encoding="utf-8"?>
<BatteryReport xmlns="http://schemas.microsoft.com/battery/2012"><Batteries><Battery>
<Id>AP23ABL</Id><DesignCapacity>52995</DesignCapacity><FullChargeCapacity>50676</FullChargeCapacity>
<CycleCount>81</CycleCount></Battery></Batteries></BatteryReport>"""


class TestHardware(unittest.TestCase):
    def setUp(self):
        self.r = hw.interpretar(DADOS, hoje=date(2026, 11, 14))

    def test_memoria(self):
        m = self.r.memoria
        self.assertEqual((m.total, len(m.pentes), m.encaixes, m.livres, m.tipo), (8 << 30, 1, 2, 1, "DDR5"))
        self.assertEqual(m.maximo, 64 << 30)
        self.assertEqual(m.pentes[0]["velocidade"], 5200)

    def test_lpddr_e_soldada_sem_encaixe_livre(self):
        dados = json.loads(json.dumps(DADOS))
        dados["pentes"][0]["SMBIOSMemoryType"] = 35
        self.assertEqual(hw.interpretar(dados).memoria.livres, 0)

    def test_video_ignora_adaptador_basico_e_calcula_idade(self):
        self.assertEqual(len(self.r.videos), 1)
        v = self.r.videos[0]
        self.assertEqual((v["fabricante"], v["dias"]), ("Intel", 844))
        self.assertTrue(v["site"].startswith("https://www.intel.com.br/"))

    def test_resto(self):
        self.assertEqual(self.r.modelo, "Acer Aspire AG15-51P")
        self.assertEqual(self.r.cpu, "13th Gen Intel(R) Core(TM) i3-1305U")
        self.assertEqual(self.r.discos[0]["saude"], "Healthy")
        self.assertEqual(self.r.ultima_atualizacao, date(2026, 10, 29))

    def test_bateria(self):
        b = hw.ler_bateria_xml(BATERIA)
        self.assertEqual((b["fabrica"], b["hoje"], b["ciclos"]), (52995, 50676, 81))
        self.assertAlmostEqual(b["saude"], 0.956, places=3)
        self.assertIsNone(hw.ler_bateria_xml("<BatteryReport/>"))
        self.assertIsNone(hw.ler_bateria_xml("não é xml"))

    def test_recomendacoes(self):
        textos = " ".join(t for _, t, _ in hw.recomendacoes(self.r, hoje=date(2026, 11, 14)))
        self.assertIn("segundo pente de 8 GB DDR5", textos)
        self.assertIn("driver de vídeo", textos)
        self.assertNotIn("última atualização", textos)  # 16 dias: tudo bem

    def test_reinicio_pendente(self):
        s = SistemaFalso()
        self.assertFalse(hw.reinicio_pendente(s))
        s.reg_subchaves = lambda hive, caminho: ["RebootRequired"] if caminho.endswith("Auto Update") else []
        self.assertTrue(hw.reinicio_pendente(s))


class TestModoJogo(unittest.TestCase):
    def setUp(self):
        self.s = SistemaFalso()
        self.b = BackupTemporario()
        self.pasta = tempfile.mkdtemp(prefix="otim-jogo-")
        self.addCleanup(shutil.rmtree, self.pasta, True)
        self.discord = os.path.join(self.pasta, "Discord.exe")
        open(self.discord, "w").close()
        self.grupos = [
            Grupo("discord.exe", "Discord", [10, 11], 300, None, self.discord, servico=False),
            Grupo("chrome.exe", "Chrome", [20], 900, None, "", servico=False),
            Grupo("explorer.exe", "Explorer", [30], 90, None, "", servico=False),
        ]
        self.pref = {"fechar": ["discord.exe", "explorer.exe"], "desempenho": True, "reabrir": True}

    def test_entra_e_sai_voltando_tudo(self):
        antes = self.s.plano
        self.assertTrue(mj.entrar(self.s, self.b, self.pref, self.grupos, lambda *_: None))
        self.assertTrue(mj.ativo(self.b))
        self.assertIn(("encerrar", (10, 11), False), self.s.comandos)
        self.assertFalse(any(c[0] == "encerrar" and 30 in c[1] for c in self.s.comandos if c[0] == "encerrar"),
                         "o Explorer nunca é fechado")
        self.assertNotEqual(self.s.plano, antes)
        abertos = []
        self.assertTrue(mj.sair(self.s, self.b, self.pref, lambda *_: None, abrir=lambda c: abertos.append(c) or True))
        self.assertEqual(self.s.plano, antes)
        self.assertEqual(abertos, [self.discord])
        self.assertFalse(mj.ativo(self.b))
        self.assertEqual(len(self.s.lista_planos), 1, "a cópia do Alto desempenho foi apagada")

    def test_estado_vai_para_o_disco(self):
        mj.entrar(self.s, self.b, self.pref, self.grupos, lambda *_: None)
        with open(self.b.arquivo, encoding="utf-8") as f:
            salvo = json.load(f)["modo_jogo"]
        self.assertTrue(salvo["ativo"])
        self.assertEqual(salvo["fechados"][0]["exe"], "discord.exe")
        self.assertIn("guid", salvo["energia"]["original"])

    def test_nao_mexe_no_plano_se_o_ajuste_ja_esta_aplicado(self):
        self.s.lista_planos.append(ALTO_DESEMPENHO)
        self.s.plano = ALTO_DESEMPENHO
        mj.entrar(self.s, self.b, self.pref, [], lambda *_: None, energia_ja_aplicada=True)
        mj.sair(self.s, self.b, self.pref, lambda *_: None, abrir=lambda c: True)
        self.assertEqual(self.s.plano, ALTO_DESEMPENHO)

    def test_sem_reabrir(self):
        mj.entrar(self.s, self.b, self.pref, self.grupos, lambda *_: None)
        abertos = []
        mj.sair(self.s, self.b, dict(self.pref, reabrir=False), lambda *_: None, abrir=lambda c: abertos.append(c))
        self.assertEqual(abertos, [])


class TestVersaoNova(unittest.TestCase):
    def test_comparar(self):
        self.assertTrue(atualizacao.tem_nova("2.2", "v2.3"))
        self.assertTrue(atualizacao.tem_nova("2.2", "v2.10"))
        self.assertFalse(atualizacao.tem_nova("2.2", "v2.2"))
        self.assertFalse(atualizacao.tem_nova("2.2", "v2.1.9"))
        self.assertFalse(atualizacao.tem_nova("2.2", "sem-numero"))


class TestDownloadsIncompletos(unittest.TestCase):
    def test_so_os_tipos_da_lista_e_sem_entrar_em_subpastas(self):
        perfil = tempfile.mkdtemp(prefix="otim-perfil-")
        self.addCleanup(shutil.rmtree, perfil, True)
        downloads = os.path.join(perfil, "Downloads")
        os.makedirs(os.path.join(downloads, "jogos"))
        agora = time.time() + 30 * 24 * 3600  # finge que passaram 30 dias desde a criação
        for nome in ("filme.mp4.crdownload", "abc.tmp", "foto.jpg", "instalador.exe"):
            with open(os.path.join(downloads, nome), "wb") as f:
                f.write(b"x" * 100)
        with open(os.path.join(downloads, "jogos", "x.tmp"), "wb") as f:
            f.write(b"x")
        novo = os.path.join(downloads, "novo.part")
        with open(novo, "wb") as f:
            f.write(b"x")
        os.utime(novo, (agora - 3600, agora - 3600))  # mexido 1 h antes de "agora": recente

        antigo = os.environ.get("USERPROFILE")
        os.environ["USERPROFILE"] = perfil  # a pasta Downloads fica protegida, como no PC de verdade
        try:
            alvo = lp.Alvo(downloads, extensoes=lp.EXT_INCOMPLETOS, idade_horas=24 * 7, recursivo=False,
                           apagar_pastas=False, pasta_pessoal=True)
            res = lp.limpar_alvo(alvo, agora=agora)
            self.assertEqual(res.apagados, 2)
            self.assertEqual(sorted(os.listdir(downloads)), ["foto.jpg", "instalador.exe", "jogos", "novo.part"])
            self.assertTrue(os.path.exists(os.path.join(downloads, "jogos", "x.tmp")))
            # sem a marca de pasta pessoal, a pasta protegida não é tocada
            sem_marca = lp.Alvo(downloads, extensoes=(".part",), recursivo=False)
            self.assertEqual(lp.analisar_alvo(sem_marca, agora=agora).apagados, 0)
            # com a marca mas recursivo, também não
            recursivo = lp.Alvo(downloads, extensoes=(".tmp",), pasta_pessoal=True)
            self.assertEqual(lp.analisar_alvo(recursivo, agora=agora).apagados, 0)
        finally:
            os.environ["USERPROFILE"] = antigo


class TestConfig(unittest.TestCase):
    def test_padrao_e_mistura_com_o_salvo(self):
        pasta = tempfile.mkdtemp(prefix="otim-cfg-")
        self.addCleanup(shutil.rmtree, pasta, True)
        arquivo = os.path.join(pasta, "config.json")
        c = Config(arquivo)
        self.assertEqual(c.dados["modo_jogo"]["fechar"], [])
        c.dados["modo_jogo"]["fechar"] = ["discord.exe"]
        c.salvar()
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump({"modo_jogo": {"fechar": ["steam.exe"]}}, f)
        c2 = Config(arquivo)
        self.assertEqual(c2.dados["modo_jogo"]["fechar"], ["steam.exe"])
        self.assertTrue(c2.dados["modo_jogo"]["reabrir"], "o que não estava salvo vem do padrão")


if __name__ == "__main__":
    unittest.main()
