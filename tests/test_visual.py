# -*- coding: utf-8 -*-
"""As fontes e a moldura do visual gótico estão no projeto (e vão para o .exe)."""
import os
import unittest

ARTE = os.path.join(os.path.dirname(__file__), "..", "otimizador_pc", "arte")


class TestArte(unittest.TestCase):
    def test_fontes_sao_ttf_de_verdade(self):
        for nome in ("UnifrakturCook.ttf", "GrenzeGotisch.ttf", "Grenze.ttf", "GrenzeSemiBold.ttf"):
            caminho = os.path.join(ARTE, nome)
            self.assertTrue(os.path.isfile(caminho), nome)
            with open(caminho, "rb") as f:
                self.assertEqual(f.read(4), b"\x00\x01\x00\x00", f"{nome} não é TrueType (o Windows não lê woff2)")

    def test_licenca_das_fontes(self):
        with open(os.path.join(ARTE, "OFL.txt"), encoding="utf-8") as f:
            self.assertIn("SIL OPEN FONT LICENSE", f.read().upper())

    def test_moldura(self):
        with open(os.path.join(ARTE, "moldura.png"), "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_gerar_exe_leva_a_arte(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "gerar_exe.bat"), encoding="utf-8") as f:
            self.assertIn("otimizador_pc\\arte", f.read())


if __name__ == "__main__":
    unittest.main()
