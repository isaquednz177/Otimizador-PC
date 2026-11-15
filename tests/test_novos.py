# -*- coding: utf-8 -*-
"""Desempenho, espaço em disco, tempo para ligar, tarefas e serviços de outros programas, cancelar."""
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime

from falso import BackupTemporario, SistemaFalso

from otimizador_pc import boot, espaco, inicializacao as ini, limpeza as lp
from otimizador_pc.controle import Cancelado, Controle
from otimizador_pc.processos import agrupar, exe_do_comando
from otimizador_pc.sistema import eh_servico_de_terceiro


def criar(caminho, tamanho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(b"x" * tamanho)


class TestProcessos(unittest.TestCase):
    def test_agrupa_por_exe_e_ordena_pela_memoria(self):
        brutos = [
            {"pid": 1, "exe": "chrome.exe", "memoria": 100, "cpu": 1.0, "sessao": 1},
            {"pid": 2, "exe": "Chrome.exe", "memoria": 300, "cpu": None, "sessao": 1},
            {"pid": 3, "exe": "steam.exe", "memoria": 250, "cpu": 2.5, "sessao": 1},
            {"pid": 4, "exe": "svchost.exe", "memoria": 50, "cpu": 0.0, "sessao": 0},
        ]
        g = agrupar(brutos, {"chrome.exe": "Google Chrome"})
        self.assertEqual([x.exe for x in g], ["chrome.exe", "steam.exe", "svchost.exe"])
        self.assertEqual((g[0].nome, g[0].memoria, g[0].qtd, g[0].cpu), ("Google Chrome", 400, 2, 1.0))
        self.assertTrue(g[0].pode_fechar)
        self.assertFalse(g[2].pode_fechar, "serviço da sessão 0 não ganha 'fechar'")

    def test_processos_do_windows_nunca_fecham(self):
        for exe in ("explorer.exe", "csrss.exe", "lsass.exe", "dwm.exe", "msmpeng.exe"):
            g = agrupar([{"pid": 9, "exe": exe, "memoria": 1, "sessao": 1}])[0]
            self.assertFalse(g.pode_fechar, exe)

    def test_exe_do_comando(self):
        self.assertEqual(exe_do_comando(r'"C:\Program Files (x86)\Steam\steam.exe" -silent'), "steam.exe")
        self.assertEqual(exe_do_comando(r"C:\Discord\Update.exe --processStart Discord.exe"), "update.exe")
        self.assertEqual(exe_do_comando("algo sem programa"), "")


class TestEspaco(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp(prefix="otim-espaco-")
        self.addCleanup(shutil.rmtree, self.raiz, True)
        criar(os.path.join(self.raiz, "jogos", "a", "grande.bin"), 3 << 20)
        criar(os.path.join(self.raiz, "jogos", "b", "medio.bin"), 2 << 20)
        criar(os.path.join(self.raiz, "fotos", "f.jpg"), 1500 << 10)
        criar(os.path.join(self.raiz, "pequena", "p.txt"), 10)
        criar(os.path.join(self.raiz, "solto.txt"), 100)

    def test_mede_e_guarda_as_pastas(self):
        m = espaco.varrer(self.raiz)
        raiz = m.pasta(self.raiz)
        total = (3 << 20) + (2 << 20) + (1500 << 10) + 10 + 100
        self.assertEqual(raiz.total, total)
        self.assertEqual(raiz.soltos, 100)
        self.assertEqual([os.path.basename(c) for c, _ in raiz.filhas], ["jogos", "fotos"])
        self.assertEqual(raiz.pequenas, 10)
        jogos = m.pasta(os.path.join(self.raiz, "jogos"))
        self.assertEqual([os.path.basename(c) for c, _ in jogos.filhas], ["a", "b"])
        self.assertEqual(os.path.basename(m.maiores[0][1]), "grande.bin")
        self.assertEqual(m.arquivos, 5)

    @unittest.skipUnless(os.name == "nt", "junção é do Windows")
    def test_juncao_nao_conta_duas_vezes(self):
        link = os.path.join(self.raiz, "atalho")
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, os.path.join(self.raiz, "jogos")], capture_output=True)
        if r.returncode != 0:
            self.skipTest("não deu para criar a junção")
        self.addCleanup(lambda: os.path.exists(link) and os.rmdir(link))
        m = espaco.varrer(self.raiz)
        self.assertEqual(m.pasta(self.raiz).total, (3 << 20) + (2 << 20) + (1500 << 10) + 110)

    def test_cancelar(self):
        ctl = Controle()
        ctl.parar()
        m = espaco.varrer(self.raiz, ctl)
        self.assertTrue(m.cancelado)

    def test_explicacoes(self):
        self.assertIn("memória virtual", espaco.explicar(r"C:\pagefile.sys"))
        self.assertIn("parece maior", espaco.explicar("C:\\Windows\\WinSxS\\"))
        self.assertEqual(espaco.explicar(r"C:\Jogos"), "")


EVENTOS = """<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><EventID>100</EventID>
<TimeCreated SystemTime='2026-11-10T11:00:05.1234567Z'/></System><EventData>
<Data Name='BootTsVersion'>2</Data><Data Name='BootTime'>41000</Data><Data Name='MainPathBootTime'>30000</Data>
<Data Name='BootPostBootTime'>11000</Data></EventData></Event>
<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><EventID>100</EventID>
<TimeCreated SystemTime='2026-11-01T09:00:00.0000000Z'/></System><EventData>
<Data Name='BootTime'>62000</Data><Data Name='MainPathBootTime'>40000</Data><Data Name='BootPostBootTime'>22000</Data>
</EventData></Event>"""


class TestBoot(unittest.TestCase):
    def test_le_eventos_em_ordem(self):
        lista = boot.ler_eventos(EVENTOS)
        self.assertEqual([b.total_ms for b in lista], [62000, 41000])
        self.assertEqual(lista[1].principal_ms, 30000)
        self.assertLess(lista[0].quando, lista[1].quando)

    def test_comparar_precisa_de_dois_de_cada_lado(self):
        lista = [boot.Ligamento(datetime(2026, 1, d), s, 0, 0) for d, s in ((1, 60000), (2, 62000), (5, 40000), (6, 42000))]
        antes, depois, na, nd = boot.comparar(lista, datetime(2026, 1, 3))
        self.assertEqual((antes, depois, na, nd), (61000, 41000, 2, 2))
        self.assertIsNone(boot.comparar(lista, datetime(2026, 1, 6))[1])

    def test_datas_dos_ajustes(self):
        dados = {"ajustes": {"a": {"data": "25/08/2026 18:02"}, "b": {"data": ""}}}
        self.assertEqual(boot.datas_dos_ajustes(dados), [datetime(2026, 8, 25, 18, 2)])


TAREFA = """<?xml version="1.0" encoding="UTF-16"?>
<Task><RegistrationInfo><Author>Google LLC</Author></RegistrationInfo>
<Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger><CalendarTrigger/></Triggers>
<Settings><Enabled>true</Enabled></Settings>
<Actions><Exec><Command>C:\\Program Files (x86)\\Google\\Update\\GoogleUpdate.exe</Command><Arguments>/ua &amp; /x</Arguments></Exec></Actions></Task>"""


class TestTarefas(unittest.TestCase):
    def test_le_tarefa(self):
        tf = ini.ler_tarefa(TAREFA, r"\GoogleUpdateTaskMachineUA")
        self.assertEqual(tf.nome, "GoogleUpdateTaskMachineUA")
        self.assertTrue(tf.ativa)
        self.assertTrue(tf.atualizador)
        self.assertEqual(tf.quando, "ao entrar na conta, em horários marcados")
        self.assertTrue(tf.comando.endswith("/ua & /x"))

    def test_lista_so_as_que_nao_sao_do_windows(self):
        pasta = tempfile.mkdtemp(prefix="otim-tarefas-")
        self.addCleanup(shutil.rmtree, pasta, True)
        with open(os.path.join(pasta, "GoogleUpdate"), "wb") as f:
            f.write(TAREFA.encode("utf-16"))
        os.makedirs(os.path.join(pasta, "Microsoft", "Windows"))
        with open(os.path.join(pasta, "Microsoft", "Windows", "Interna"), "wb") as f:
            f.write(TAREFA.encode("utf-16"))
        os.makedirs(os.path.join(pasta, "Acer"))
        with open(os.path.join(pasta, "Acer", "Ajudante"), "w", encoding="utf-8") as f:
            f.write(TAREFA.replace("<Settings><Enabled>true", "<Settings><Enabled>false"))
        tarefas = {t.caminho: t for t in ini.listar_tarefas(pasta)}
        self.assertEqual(set(tarefas), {r"\GoogleUpdate", r"\Acer\Ajudante"})
        self.assertFalse(tarefas[r"\Acer\Ajudante"].ativa)


class TestServicosDeTerceiros(unittest.TestCase):
    def test_quem_e_de_terceiro(self):
        self.assertTrue(eh_servico_de_terceiro("MySQL80", 0x10, r'"C:\Program Files\MySQL\bin\mysqld.exe" MySQL80'))
        self.assertFalse(eh_servico_de_terceiro("WinDefend", 0x10, r"C:\ProgramData\x\MsMpEng.exe"))
        self.assertFalse(eh_servico_de_terceiro("MDCoreSvc", 0x10,
                                                r"C:\ProgramData\Microsoft\Windows Defender\Platform\x.exe"))
        self.assertFalse(eh_servico_de_terceiro("Spooler", 0x10, r"%SystemRoot%\System32\spoolsv.exe"))
        self.assertFalse(eh_servico_de_terceiro("algum", 0x1, r"C:\Program Files\x\driver.sys"), "driver")
        self.assertFalse(eh_servico_de_terceiro("vazio", 0x10, ""))

    def setUp(self):
        self.s = SistemaFalso()
        self.b = BackupTemporario()
        self.s.servicos = {
            "MySQL80": {"start": 2, "atrasado": True, "estado": "RUNNING",
                        "caminho": r"C:\Program Files\MySQL\mysqld.exe", "exibicao": "MySQL80"},
            "Spooler": {"start": 2, "atrasado": False, "estado": "RUNNING",
                        "caminho": r"C:\Windows\System32\spoolsv.exe"},
            "gupdatem": {"start": 3, "atrasado": False, "estado": "STOPPED",
                         "caminho": r"C:\Program Files (x86)\Google\Update\GoogleUpdate.exe"},
        }

    def test_lista_so_automaticos_de_terceiros(self):
        self.assertEqual([x.nome for x in ini.listar_servicos(self.s, self.b)], ["MySQL80"])

    def test_manual_e_volta_como_estava(self):
        mysql = ini.listar_servicos(self.s, self.b)[0]
        ok, _ = ini.definir_servico(self.s, self.b, mysql, False)
        self.assertTrue(ok)
        self.assertEqual(self.s.servicos["MySQL80"]["start"], 3)
        self.assertEqual(self.b.dados["servicos_terceiros"]["MySQL80"], {"start": 2, "atrasado": True})
        # continua na lista (agora manual) para poder voltar
        self.assertEqual([(x.nome, x.automatico) for x in ini.listar_servicos(self.s, self.b)], [("MySQL80", False)])
        ok, _ = ini.definir_servico(self.s, self.b, mysql, True)
        self.assertTrue(ok)
        self.assertEqual((self.s.servicos["MySQL80"]["start"], self.s.servicos["MySQL80"]["atrasado"]), (2, True))
        self.assertEqual(self.b.dados["servicos_terceiros"], {})


class TestCancelarLimpeza(unittest.TestCase):
    def test_cancelado_antes_nao_apaga_nada(self):
        pasta = tempfile.mkdtemp(prefix="otim-cancela-")
        self.addCleanup(shutil.rmtree, pasta, True)
        criar(os.path.join(pasta, "sub", "x.tmp"), 10)
        ctl = Controle()
        ctl.parar()
        with self.assertRaises(Cancelado):
            lp.limpar_alvo(lp.Alvo(pasta), ctl=ctl)
        self.assertTrue(os.path.exists(os.path.join(pasta, "sub", "x.tmp")))


if __name__ == "__main__":
    unittest.main()
