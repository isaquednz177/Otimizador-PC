# -*- coding: utf-8 -*-
"""As leituras da saída dos programas do Windows, em português e em inglês."""
import unittest

from otimizador_pc.ponto import protecao_ligada
from otimizador_pc.sistema import estado_do_sc, processos_do_tasklist, tarefa_ativa_do_xml
from otimizador_pc.util import formatar_tamanho

from falso import SistemaFalso

SC_PT = """
NOME_DO_SERVIÇO: WSearch
        TIPO               : 10  WIN32_OWN_PROCESS
        ESTADO              : 1  STOPPED
        CÓDIGO_DE_SAÍDA_DO_WIN32    : 1077  (0x435)
        PONTO_DE_VERIFICAÇÃO         : 0x0
"""
SC_EN = "SERVICE_NAME: wuauserv\n        TYPE               : 20  WIN32_SHARE_PROCESS\n        STATE              : 4  RUNNING\n"

XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task><Triggers><TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers>
<Settings><IdleSettings><StopOnIdleEnd>true</StopOnIdleEnd></IdleSettings>
<Enabled>false</Enabled><Hidden>true</Hidden></Settings></Task>"""


class TestLeituras(unittest.TestCase):
    def test_sc_em_portugues_e_ingles(self):
        self.assertEqual(estado_do_sc(SC_PT), "STOPPED")
        self.assertEqual(estado_do_sc(SC_EN), "RUNNING")
        self.assertIsNone(estado_do_sc("[SC] OpenService FALHA 1060"))

    def test_xml_da_tarefa(self):
        self.assertFalse(tarefa_ativa_do_xml(XML))
        self.assertTrue(tarefa_ativa_do_xml(XML.replace("<Enabled>false</Enabled>", "")))
        self.assertIsNone(tarefa_ativa_do_xml("ERRO: O sistema não pode encontrar o arquivo especificado."))

    def test_tasklist(self):
        saida = '"chrome.exe","1234","Console","1","120.000 K"\n"Steam.exe","99","Console","1","5 K"\n' \
                'INFORMAÇÕES: Nenhuma tarefa em execução\n'
        self.assertEqual(processos_do_tasklist(saida), {"chrome.exe", "steam.exe"})

    def test_tamanho(self):
        self.assertEqual(formatar_tamanho(0), "0 B")
        self.assertEqual(formatar_tamanho(1536), "1,5 KB")
        self.assertEqual(formatar_tamanho(3 * 1024 ** 3), "3,0 GB")
        self.assertEqual(formatar_tamanho(None), "?")

    def test_protecao_do_sistema(self):
        s = SistemaFalso()
        self.assertIsNone(protecao_ligada(s))
        caminho = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
        s.reg_escrever("HKLM", caminho, "RPSessionInterval", 4, 0)
        self.assertFalse(protecao_ligada(s))
        s.reg_escrever("HKLM", caminho, "RPSessionInterval", 4, 1)
        self.assertTrue(protecao_ligada(s))
        s.reg_escrever("HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore", "DisableSR", 4, 1)
        self.assertFalse(protecao_ligada(s))


if __name__ == "__main__":
    unittest.main()
