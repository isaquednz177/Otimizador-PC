# -*- coding: utf-8 -*-
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest

from falso import SistemaFalso

from otimizador_pc import limpeza as lp
from otimizador_pc.limpeza import Alvo, ItemLimpeza
from otimizador_pc.seguranca import caminho_e_seguro, pastas_proibidas

DIA = 24 * 3600


def criar(caminho, conteudo=b"x" * 10):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)
    return caminho


class Base(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp(prefix="otim-limpa-")
        self.pasta = os.path.join(self.raiz, "alvo")
        os.makedirs(self.pasta)
        self.addCleanup(shutil.rmtree, self.raiz, True)


class TestLimparAlvo(Base):
    def test_apaga_o_conteudo_e_deixa_a_pasta(self):
        criar(os.path.join(self.pasta, "a.tmp"))
        criar(os.path.join(self.pasta, "sub", "fundo", "b.tmp"), b"y" * 30)
        fora = criar(os.path.join(self.raiz, "fora.txt"))
        res = lp.limpar_alvo(Alvo(self.pasta))
        self.assertEqual((res.apagados, res.bytes, res.pulados), (2, 40, 0))
        self.assertTrue(os.path.isdir(self.pasta))
        self.assertEqual(os.listdir(self.pasta), [], "as subpastas vazias também saem")
        self.assertTrue(os.path.exists(fora))

    def test_arquivo_recente_fica(self):
        velho = criar(os.path.join(self.pasta, "velho.tmp"))
        novo = criar(os.path.join(self.pasta, "novo.tmp"))
        agora = time.time() + 30 * 3600            # finge que passaram 30 h
        os.utime(novo, (agora - 3600, agora - 3600))  # o "novo" foi mexido 1 h antes de "agora"
        res = lp.limpar_alvo(Alvo(self.pasta, idade_horas=24), agora=agora)
        self.assertEqual(res.apagados, 1)
        self.assertFalse(os.path.exists(velho))
        self.assertTrue(os.path.exists(novo))

    def test_analisar_mostra_o_mesmo_que_a_limpeza_apaga(self):
        for i in range(5):
            criar(os.path.join(self.pasta, f"s{i}", f"{i}.bin"), b"z" * (i + 1))
        analise = lp.analisar_alvo(Alvo(self.pasta))
        res = lp.limpar_alvo(Alvo(self.pasta))
        self.assertEqual((analise.apagados, analise.bytes), (res.apagados, res.bytes))
        self.assertEqual(analise.bytes, 15)

    def test_filtros(self):
        criar(os.path.join(self.pasta, "thumbcache_32.db"))
        criar(os.path.join(self.pasta, "iconcache_32.db"))
        criar(os.path.join(self.pasta, "thumbcache_32.txt"))
        criar(os.path.join(self.pasta, "sub", "thumbcache_99.db"))
        alvo = Alvo(self.pasta, prefixos=("thumbcache_",), extensoes=(".db",), recursivo=False)
        res = lp.limpar_alvo(alvo)
        self.assertEqual(res.apagados, 1)
        self.assertEqual(sorted(os.listdir(self.pasta)), ["iconcache_32.db", "sub", "thumbcache_32.txt"])

    def test_nomes_exatos(self):
        criar(os.path.join(self.pasta, "MEMORY.DMP"))
        criar(os.path.join(self.pasta, "outro.dmp"))
        res = lp.limpar_alvo(Alvo(self.pasta, nomes=("memory.dmp",), recursivo=False))
        self.assertEqual(res.apagados, 1)
        self.assertEqual(os.listdir(self.pasta), ["outro.dmp"])

    def test_somente_leitura_tambem_sai(self):
        arq = criar(os.path.join(self.pasta, "ro.tmp"))
        os.chmod(arq, stat.S_IREAD)
        self.assertEqual(lp.limpar_alvo(Alvo(self.pasta)).apagados, 1)

    @unittest.skipUnless(os.name == "nt", "arquivo travado só no Windows")
    def test_arquivo_em_uso_e_pulado(self):
        arq = criar(os.path.join(self.pasta, "aberto.tmp"))
        with open(arq, "rb"):
            res = lp.limpar_alvo(Alvo(self.pasta))
        self.assertEqual((res.apagados, res.pulados), (0, 1))
        self.assertTrue(os.path.exists(arq))

    @unittest.skipUnless(os.name == "nt", "junção é do Windows")
    def test_juncao_nunca_e_seguida(self):
        importante = os.path.join(self.raiz, "documentos")
        guardado = criar(os.path.join(importante, "tese.docx"))
        link = os.path.join(self.pasta, "atalho")
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, importante], capture_output=True)
        if r.returncode != 0:
            self.skipTest("não deu para criar a junção")
        criar(os.path.join(self.pasta, "lixo.tmp"))
        self.assertEqual(lp.analisar_alvo(Alvo(self.pasta)).apagados, 1)
        lp.limpar_alvo(Alvo(self.pasta))
        self.assertTrue(os.path.exists(guardado), "o arquivo do outro lado da junção tem que ficar")
        self.assertTrue(os.path.exists(link), "a junção em si também fica")
        os.rmdir(link)

    def test_pasta_que_nao_existe(self):
        res = lp.limpar_alvo(Alvo(os.path.join(self.raiz, "nao-existe")))
        self.assertEqual((res.apagados, res.bytes), (0, 0))


class TestSeguranca(Base):
    def test_pastas_proibidas(self):
        amb = {"SystemRoot": self.raiz, "SystemDrive": "C:", "USERPROFILE": self.pasta}
        self.assertFalse(caminho_e_seguro(self.raiz, amb))
        self.assertFalse(caminho_e_seguro(self.pasta, amb))
        os.makedirs(os.path.join(self.pasta, "Documents"))
        self.assertFalse(caminho_e_seguro(os.path.join(self.pasta, "Documents"), amb))
        os.makedirs(os.path.join(self.raiz, "Temp"))
        self.assertTrue(caminho_e_seguro(os.path.join(self.raiz, "Temp"), amb))
        self.assertFalse(caminho_e_seguro("C:\\", amb))
        self.assertFalse(caminho_e_seguro(os.path.join(self.raiz, "nao-existe"), amb))
        self.assertFalse(caminho_e_seguro("", amb))

    def test_lista_tem_as_pastas_do_sistema(self):
        p = pastas_proibidas({"SystemRoot": r"C:\Windows", "SystemDrive": "C:", "USERPROFILE": r"C:\Users\x"})
        for pasta in (r"c:\\", r"c:\windows", r"c:\windows\system32", r"c:\users\x", r"c:\users\x\desktop"):
            self.assertIn(os.path.normcase(os.path.normpath(pasta)), p)

    def test_alvo_em_pasta_protegida_so_com_nome_exato(self):
        criar(os.path.join(self.pasta, "MEMORY.DMP"))
        criar(os.path.join(self.pasta, "importante.txt"))
        antigo = os.environ.get("SystemRoot")
        os.environ["SystemRoot"] = self.pasta  # finge que a pasta é o C:\Windows
        try:
            self.assertEqual(lp.analisar_alvo(Alvo(self.pasta)).apagados, 0)
            self.assertEqual(lp.analisar_alvo(Alvo(self.pasta, nomes=("MEMORY.DMP",), recursivo=False)).apagados, 1)
            self.assertEqual(lp.analisar_alvo(Alvo(self.pasta, nomes=("MEMORY.DMP",))).apagados, 0)
        finally:
            if antigo is None:
                os.environ.pop("SystemRoot")
            else:
                os.environ["SystemRoot"] = antigo


class TestItens(Base):
    def item(self, **kw):
        return ItemLimpeza("t", "t", "", lambda: [Alvo(self.pasta)], **kw)

    def test_navegador_aberto_e_pulado(self):
        criar(os.path.join(self.pasta, "cache.bin"))
        s = SistemaFalso()
        s.abertos = {"chrome.exe"}
        res = lp.limpar_item(self.item(fechar_processos=("chrome.exe",), nome_processo="o Chrome"), s)
        self.assertIn("feche o Chrome", res.nota)
        self.assertEqual(len(os.listdir(self.pasta)), 1)
        s.abertos = set()
        self.assertEqual(lp.limpar_item(self.item(fechar_processos=("chrome.exe",)), s).apagados, 1)

    def test_windows_update_para_e_volta_so_se_estava_rodando(self):
        criar(os.path.join(self.pasta, "pacote.cab"))
        s = SistemaFalso()
        s.servicos["wuauserv"] = {"start": 3, "atrasado": False, "estado": "RUNNING"}
        s.servicos["BITS"] = {"start": 3, "atrasado": False, "estado": "STOPPED"}
        res = lp.limpar_item(self.item(parar_servicos=("wuauserv", "BITS")), s)
        self.assertEqual(res.apagados, 1)
        self.assertEqual(s.servicos["wuauserv"]["estado"], "RUNNING")
        self.assertEqual(s.servicos["BITS"]["estado"], "STOPPED")
        self.assertIn(("iniciar", "wuauserv"), s.comandos)
        self.assertNotIn(("iniciar", "BITS"), s.comandos)

    def test_ids_unicos_e_todo_item_tem_descricao(self):
        ids = [i.id for i in lp.ITENS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in lp.ITENS:
            self.assertTrue(i.descricao, i.id)

    def test_temporarios_guardam_as_ultimas_24h(self):
        for a in lp.alvos_temp_usuario() + lp.alvos_temp_windows():
            self.assertGreaterEqual(a.idade_horas, 24)

    def test_prefetch_saiu(self):
        self.assertNotIn("prefetch", lp.ITENS_POR_ID)

    def test_caches_de_navegador_nao_tocam_em_senhas_nem_historico(self):
        perfil = os.path.join(self.pasta, "Default")
        criar(os.path.join(perfil, "Preferences"))
        alvos = lp._alvos_chromium(self.pasta)
        nomes = {os.path.basename(a.pasta) for a in alvos}
        self.assertIn("Cache", nomes)
        for proibido in ("Login Data", "History", "Cookies", "Bookmarks", "Local Storage", "Sessions"):
            self.assertNotIn(proibido, nomes)


if __name__ == "__main__":
    unittest.main()
