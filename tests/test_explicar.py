# -*- coding: utf-8 -*-
"""As frases para leigos saem certas para cada faixa de número."""
import unittest

from otimizador_pc import explicar as ex

GB = 1 << 30


class TestExplicar(unittest.TestCase):
    def test_memoria(self):
        self.assertEqual(ex.memoria(50)[:2], ("bom", "tranquila"))
        self.assertEqual(ex.memoria(80)[:2], ("bom", "bem usada"))
        self.assertEqual(ex.memoria(90)[:2], ("atencao", "quase cheia"))
        self.assertEqual(ex.memoria(97)[:2], ("ruim", "cheia"))

    def test_processador_olha_a_media(self):
        self.assertEqual(ex.processador(10)[0], "bom")
        self.assertEqual(ex.processador(50)[0], "atencao")
        self.assertEqual(ex.processador(80)[0], "ruim")

    def test_disco(self):
        self.assertEqual(ex.disco(80 * GB, 237 * GB)[0], "bom")
        self.assertEqual(ex.disco(40 * GB, 237 * GB)[0], "atencao")
        self.assertEqual(ex.disco(8 * GB, 237 * GB)[0], "ruim")
        self.assertEqual(ex.disco(0, 0)[0], "bom")

    def test_ligar(self):
        self.assertEqual(ex.ligar(30)[1], "rápido")
        self.assertEqual(ex.ligar(60)[1], "normal")
        self.assertEqual(ex.ligar(120)[1], "lento")

    def test_resumo(self):
        self.assertEqual(ex.resumo(50, 10, 100 * GB, 237 * GB), "Seu PC está tranquilo agora.")
        self.assertEqual(ex.resumo(96, 10, 100 * GB, 237 * GB), "Seu PC pode estar lento agora: a memória está cheia.")
        self.assertEqual(ex.resumo(96, 80, 5 * GB, 237 * GB),
                         "Seu PC pode estar lento agora: a memória está cheia, o processador está sobrecarregado "
                         "e o disco está quase cheio.")

    def test_glossario_sem_termos_repetidos(self):
        termos = [t for t, _ in ex.GLOSSARIO]
        self.assertEqual(len(termos), len(set(termos)))
        for termo, texto in ex.GLOSSARIO:
            self.assertTrue(texto.endswith("."), termo)


if __name__ == "__main__":
    unittest.main()
