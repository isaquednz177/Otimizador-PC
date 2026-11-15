# -*- coding: utf-8 -*-
"""A arte do visual (a moldura das volutas) está no projeto e vai para o .exe."""
import os
import unittest

ARTE = os.path.join(os.path.dirname(__file__), "..", "otimizador_pc", "arte")


class TestArte(unittest.TestCase):
    def test_moldura(self):
        with open(os.path.join(ARTE, "moldura.png"), "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_gerar_exe_leva_a_arte(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "gerar_exe.bat"), encoding="utf-8") as f:
            self.assertIn("otimizador_pc\\arte", f.read())

    def test_cores_do_tema(self):
        from otimizador_pc import tema as t

        def luz(cor):
            r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
            return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

        def contraste(a, b):
            la, lb = sorted((luz(a), luz(b)), reverse=True)
            return (la + 0.05) / (lb + 0.05)
        # texto e destaques legíveis sobre o fundo e os painéis (4,5:1 é o mínimo para texto)
        for cor in (t.TEXTO, t.SUAVE, t.ACENTO):
            for fundo in (t.FUNDO, t.PAINEL):
                self.assertGreaterEqual(contraste(cor, fundo), 4.5, f"{cor} sobre {fundo}")
        self.assertGreaterEqual(contraste(t.TEXTO, t.VINHO), 4.5, "texto do botão principal")


if __name__ == "__main__":
    unittest.main()
