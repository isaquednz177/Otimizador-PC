# -*- coding: utf-8 -*-
"""Desinstalar e caçar sobras: o que entra na lista, o comando e, principalmente, o que NUNCA é apagado."""
import os
import shutil
import tempfile
import unittest

from otimizador_pc import desinstalar as d
from otimizador_pc.sistema import REG_DWORD, REG_SZ

from falso import SistemaFalso

U64 = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
U32 = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"


def instalar(s, hive, raiz, sub, **valores):
    for nome, valor in valores.items():
        tipo = REG_DWORD if isinstance(valor, int) else REG_SZ
        s.reg_escrever(hive, f"{raiz}\\{sub}", nome, tipo, valor)


class TestNomes(unittest.TestCase):
    def test_chave_sem_versao_nem_arquitetura(self):
        self.assertEqual(d.chave_de("7-Zip 23.01 (x64)"), "7zip")
        self.assertEqual(d.chave_de("Foobar Editor 2.1.3"), "foobareditor")
        self.assertEqual(d.chave_de("Discord"), "discord")

    def test_editor_sem_sufixo(self):
        self.assertEqual(d.chave_do_editor("Valve Corporation"), "valve")
        self.assertEqual(d.chave_do_editor("Acme, Inc."), "acme")
        self.assertEqual(d.chave_do_editor("Igor Pavlov"), "igorpavlov")

    def test_nomes_genericos_nao_valem(self):
        self.assertFalse(d.chave_valida("update"))
        self.assertFalse(d.chave_valida("abc"))
        self.assertTrue(d.chave_valida("foobareditor"))


class TestLista(unittest.TestCase):
    def test_filtra_e_le_os_campos(self):
        s = SistemaFalso()
        instalar(s, "HKLM", U64, "Foobar", DisplayName="Foobar Editor 2.1", DisplayVersion="2.1",
                 Publisher="Acme Inc", UninstallString=r'"C:\Program Files\Foobar\unins000.exe"',
                 EstimatedSize=2048, InstallDate="20260315")
        instalar(s, "HKLM", U64, "Escondido", DisplayName="Peça do sistema", UninstallString="x.exe",
                 SystemComponent=1)
        instalar(s, "HKLM", U64, "Atualizacao", DisplayName="Atualização", UninstallString="x.exe",
                 ParentKeyName="Office")
        instalar(s, "HKLM", U64, "SemDesinstalador", DisplayName="Sem desinstalador")
        instalar(s, "HKLM", U32, "{11111111-2222-3333-4444-555555555555}", DisplayName="Coisa MSI",
                 UninstallString="MsiExec.exe /I{11111111-2222-3333-4444-555555555555}", WindowsInstaller=1)
        instalar(s, "HKCU", U64, "Foobar", DisplayName="Foobar Editor 2.1", DisplayVersion="2.1",
                 UninstallString="dup.exe")   # repetido: some
        lista = d.listar(s)
        self.assertEqual([p.nome for p in lista], ["Coisa MSI", "Foobar Editor 2.1"])
        foo = lista[1]
        self.assertEqual(foo.tamanho, 2048 * 1024)
        self.assertEqual(foo.data, "15/03/2026")
        self.assertEqual(foo.editor, "Acme Inc")
        self.assertTrue(lista[0].msi)

    def test_msi_vira_desinstalar_pelo_caminho_completo(self):
        p = d.Programa("HKLM", U64 + r"\{11111111-2222-3333-4444-555555555555}", "Coisa",
                       desinstalar="MsiExec.exe /I{11111111-2222-3333-4444-555555555555}", msi=True)
        self.assertEqual(d.comando(p, {"SystemRoot": r"C:\Windows"}),
                         r'"C:\Windows\System32\msiexec.exe" /x {11111111-2222-3333-4444-555555555555}')

    def test_variaveis_do_caminho_sao_trocadas(self):
        p = d.Programa("HKCU", U64 + r"\App", "App", desinstalar=r'"%LOCALAPPDATA%\App\Update.exe" --uninstall')
        self.assertEqual(d.comando(p, {"LOCALAPPDATA": r"C:\U\AppData\Local"}),
                         r'"C:\U\AppData\Local\App\Update.exe" --uninstall')
        self.assertEqual(d.executavel(r'"C:\A B\u.exe" /S'), r"C:\A B\u.exe")
        self.assertEqual(d.executavel(r"C:\A B\u.exe /S"), r"C:\A B\u.exe")


class TestSobras(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="otim-sobras-")
        self.amb = {}
        for nome, sub in (("ProgramFiles", "PF"), ("ProgramFiles(x86)", "PF86"), ("ProgramData", "PD"),
                          ("USERPROFILE", "U"), ("APPDATA", r"U\AppData\Roaming"),
                          ("LOCALAPPDATA", r"U\AppData\Local"), ("SystemRoot", "Win")):
            self.amb[nome] = os.path.join(self.base, sub)
            os.makedirs(self.amb[nome], exist_ok=True)
        self.amb["SystemDrive"] = "Z:"
        self.s = SistemaFalso()
        self.foo = d.Programa("HKLM", U64 + r"\Foobar", "Foobar Editor 2.1", editor="Acme Inc",
                              pasta=self.p("ProgramFiles", "Foobar Editor"))
        self.outro = d.Programa("HKLM", U64 + r"\Other", "Other Tool", editor="Acme Inc",
                                pasta=self.p("ProgramFiles", "Other Tool"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def p(self, raiz, *partes, criar=True):
        caminho = os.path.join(self.amb[raiz], *partes)
        if criar:
            os.makedirs(caminho, exist_ok=True)
            with open(os.path.join(caminho, "x.dat"), "wb") as f:
                f.write(b"1234")
        return caminho

    def caminhos(self, sobras, tipo):
        return {os.path.normcase(x.caminho) if tipo == "pasta" else x.caminho.lower()
                for x in sobras if x.tipo == tipo}

    def test_acha_as_pastas_do_programa_e_poupa_as_dos_outros(self):
        instalada = self.foo.pasta
        appdata = self.p("APPDATA", "Acme", "FoobarEditor")
        local = self.p("LOCALAPPDATA", "Foobar Editor")
        dos_outros = self.p("APPDATA", "Acme", "Other Tool")
        generica = self.p("LOCALAPPDATA", "Common")
        outro_programa = self.outro.pasta
        sobras = d.procurar(self.foo, [self.outro], self.s, self.amb)
        achadas = self.caminhos(sobras, "pasta")
        for c in (instalada, appdata, local):
            self.assertIn(os.path.normcase(c), achadas)
        for c in (dos_outros, generica, outro_programa, os.path.join(self.amb["APPDATA"], "Acme")):
            self.assertNotIn(os.path.normcase(c), achadas)

    def test_pasta_do_fabricante_so_quando_ele_nao_tem_outro_programa(self):
        self.p("APPDATA", "Acme", "Foobar Editor")
        os.remove(os.path.join(self.amb["APPDATA"], "Acme", "Foobar Editor", "x.dat"))
        sozinho = self.caminhos(d.procurar(self.foo, [], self.s, self.amb), "pasta")
        self.assertIn(os.path.normcase(os.path.join(self.amb["APPDATA"], "Acme")), sozinho)
        com_outro = self.caminhos(d.procurar(self.foo, [self.outro], self.s, self.amb), "pasta")
        self.assertNotIn(os.path.normcase(os.path.join(self.amb["APPDATA"], "Acme")), com_outro)

    def test_nunca_as_pastas_raiz_nem_a_pasta_instalada_estranha(self):
        estranho = d.Programa("HKLM", U64 + r"\X", "Foobar Editor", pasta=self.amb["USERPROFILE"])
        achadas = self.caminhos(d.procurar(estranho, [], self.s, self.amb), "pasta")
        for raiz in [v for k, v in self.amb.items() if k != "SystemDrive"]:
            self.assertNotIn(os.path.normcase(raiz), achadas)

    def test_pasta_instalada_sem_o_nome_do_programa_nao_entra(self):
        comum = self.p("ProgramFiles(x86)", "Steam", "steamapps", "common")
        jogo = d.Programa("HKLM", U64 + r"\Jogo", "Jogo Legal", editor="Estudio", pasta=comum)
        self.assertNotIn(os.path.normcase(comum), self.caminhos(d.procurar(jogo, [], self.s, self.amb), "pasta"))
        py = d.Programa("HKCU", U64 + r"\Py", "Python 3.11.9 (64-bit)", editor="Python Software Foundation")
        self.p("LOCALAPPDATA", "Python")
        self.assertEqual(self.caminhos(d.procurar(py, [], self.s, self.amb), "pasta"), set())

    def test_registro_do_programa_sim_e_do_windows_nunca(self):
        self.s.chaves |= {("HKCU", r"software\acme\foobar editor"), ("HKCU", r"software\acme\other tool"),
                          ("HKLM", r"software\foobareditor"), ("HKCU", r"software\microsoft\foobar editor"),
                          ("HKLM", r"software\wow6432node\foobar editor")}
        achadas = self.caminhos(d.procurar(self.foo, [self.outro], self.s, self.amb), "registro")
        self.assertEqual(achadas, {r"hkcu\software\acme\foobar editor", r"hklm\software\foobareditor",
                                   r"hklm\software\wow6432node\foobar editor"})

    def test_entrada_que_sobrou_e_programa_da_microsoft(self):
        self.s.chaves.add(("HKLM", (U64 + r"\Foobar").lower()))
        sobras = d.procurar(self.foo, [], self.s, self.amb)
        self.assertIn(("HKLM\\" + U64 + r"\Foobar").lower(), self.caminhos(sobras, "registro"))
        ms = d.Programa("HKLM", U64 + r"\Foobar", "Foobar Editor", editor="Microsoft Corporation")
        self.p("APPDATA", "Foobar Editor")
        self.assertEqual([x.tipo for x in d.procurar(ms, [], self.s, self.amb)], ["registro"])

    def test_enquanto_instalado_nao_oferece_a_entrada_nem_a_pasta(self):
        self.s.chaves.add(("HKLM", (U64 + r"\Foobar").lower()))
        sobras = d.procurar(self.foo, [], self.s, self.amb, ainda_instalado=True)
        self.assertFalse(any("uninstall" in x.caminho.lower() for x in sobras))
        self.assertNotIn(os.path.normcase(self.foo.pasta), self.caminhos(sobras, "pasta"))

    def test_apagar_manda_para_a_lixeira_e_exporta_o_registro_antes(self):
        pasta = self.p("LOCALAPPDATA", "Foobar Editor")
        self.s.chaves.add(("HKCU", r"software\foobar editor"))
        sobras = [d.Sobra("pasta", pasta, "x"),
                  d.Sobra("pasta", self.amb["APPDATA"], "raiz: não pode"),
                  d.Sobra("registro", r"HKCU\software\foobar editor", "x", hive="HKCU", chave=r"software\foobar editor"),
                  d.Sobra("registro", r"HKCU\software\microsoft", "x", hive="HKCU", chave=r"software\microsoft")]
        copias = os.path.join(self.base, "copias")
        feitas, falhas = d.apagar(self.s, sobras, "Foobar Editor", log=lambda *_: None,
                                  ambiente=self.amb, pasta_copias=copias)
        self.assertEqual((feitas, falhas), (2, 2))
        self.assertEqual(self.s.lixeira, [pasta])
        self.assertTrue(os.path.isdir(self.amb["APPDATA"]))
        self.assertEqual(len(self.s.exportadas), 1)
        self.assertTrue(os.path.isfile(self.s.exportadas[0][2]))
        self.assertFalse(self.s.reg_chave_existe("HKCU", r"software\foobar editor"))
        self.assertNotIn(("reg_apagar", "HKCU", r"software\microsoft"), self.s.comandos)


if __name__ == "__main__":
    unittest.main()
