# -*- coding: utf-8 -*-
import unittest

from falso import BackupTemporario, SistemaFalso

from otimizador_pc import inicializacao as ini

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


class TestMarca(unittest.TestCase):
    def test_marca_igual_a_do_gerenciador_de_tarefas(self):
        self.assertEqual(ini.marca(True), bytes([2]) + bytes(11))
        desligado = ini.marca(False, agora=0)
        self.assertEqual(len(desligado), 12)
        self.assertEqual(desligado[:4], bytes([3, 0, 0, 0]))
        self.assertEqual(int.from_bytes(desligado[4:], "little"), 11644473600 * 10_000_000)

    def test_leitura_da_marca(self):
        self.assertTrue(ini.ativo_pela_marca(None))
        self.assertTrue(ini.ativo_pela_marca((bytes([2]) + bytes(11), 3)))
        self.assertTrue(ini.ativo_pela_marca((bytes([6]) + bytes(11), 3)))
        self.assertFalse(ini.ativo_pela_marca((bytes([3]) + bytes(11), 3)))
        self.assertFalse(ini.ativo_pela_marca((bytes([7]) + bytes(11), 3)))


class TestLista(unittest.TestCase):
    def setUp(self):
        self.s = SistemaFalso()
        self.s.reg_escrever("HKCU", RUN, "Steam", 1, r'"C:\Steam\steam.exe" -silent')
        self.s.reg_escrever("HKCU", RUN, "Discord", 1, r"C:\Discord\Update.exe")
        self.s.reg_escrever("HKCU", ini.APROVADO + r"\Run", "Steam", 3, ini.marca(False))

    def test_lista_com_estado(self):
        itens = {i.nome: i for i in ini.listar(self.s)}
        self.assertFalse(itens["Steam"].ativo)
        self.assertTrue(itens["Discord"].ativo)

    def test_desligar_nao_apaga_o_programa_da_lista(self):
        discord = next(i for i in ini.listar(self.s) if i.nome == "Discord")
        ok, _ = ini.definir(self.s, discord, False)
        self.assertTrue(ok)
        self.assertIsNotNone(self.s.reg_ler("HKCU", RUN, "Discord"))
        self.assertFalse(next(i for i in ini.listar(self.s) if i.nome == "Discord").ativo)
        ini.definir(self.s, discord, True)
        self.assertTrue(next(i for i in ini.listar(self.s) if i.nome == "Discord").ativo)

    def test_pasta_inicializar_ignora_desktop_ini(self):
        pasta = ini.pastas_inicializar()[0][2]
        self.s.pastas[pasta] = ["desktop.ini", "Spotify.lnk"]
        nomes = [i.nome for i in ini.listar(self.s)]
        self.assertIn("Spotify.lnk", nomes)
        self.assertNotIn("desktop.ini", nomes)


class TestRemovidosPelaVersaoAntiga(unittest.TestCase):
    def test_restaurar(self):
        s = SistemaFalso()
        b = BackupTemporario()
        b.dados["inicializacao_removida"]["HKLM:SecurityHealth"] = {
            "hive": "HKLM", "caminho": RUN, "nome": "SecurityHealth",
            "valor": r"%windir%\system32\SecurityHealthSystray.exe", "tipo": 2, "data": ""}
        ok, _ = ini.restaurar_removido(s, b, "HKLM:SecurityHealth")
        self.assertTrue(ok)
        self.assertEqual(s.reg_ler("HKLM", RUN, "SecurityHealth"),
                         (r"%windir%\system32\SecurityHealthSystray.exe", 2))
        self.assertEqual(b.dados["inicializacao_removida"], {})

    def test_falha_mantem_no_backup(self):
        s = SistemaFalso()
        s.falhar_reg.add("X")
        b = BackupTemporario()
        b.dados["inicializacao_removida"]["HKCU:X"] = {"hive": "HKCU", "caminho": RUN, "nome": "X",
                                                       "valor": "x.exe", "tipo": 1}
        ok, _ = ini.restaurar_removido(s, b, "HKCU:X")
        self.assertFalse(ok)
        self.assertIn("HKCU:X", b.dados["inicializacao_removida"])


if __name__ == "__main__":
    unittest.main()
