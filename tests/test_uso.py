# -*- coding: utf-8 -*-
"""Contas das estatísticas de uso: processador, divisão da memória e histórico."""
import unittest

from otimizador_pc import info

GB = 1 << 30


class TestUso(unittest.TestCase):
    def test_processador(self):
        # (ocioso, kernel, usuário); o kernel já inclui o ocioso
        self.assertAlmostEqual(info.uso_do_processador((0, 0, 0), (75, 100, 0)), 25.0)
        self.assertAlmostEqual(info.uso_do_processador((10, 100, 50), (10, 150, 100)), 100.0)
        self.assertIsNone(info.uso_do_processador((5, 5, 5), (5, 5, 5)))

    def test_composicao(self):
        grupos = [("Chrome", 2 * GB), ("Code", GB), ("Discord", GB // 2), ("a", 100), ("b", 50)]
        partes = info.composicao_da_memoria(8 * GB, 6 * GB, grupos, destaques=3)
        nomes = [n for n, _, _ in partes]
        self.assertEqual(nomes, ["Chrome", "Code", "Discord", "outros programas", "Windows, drivers e cache", "livre"])
        valores = dict((n, v) for n, v, _ in partes)
        self.assertEqual(valores["outros programas"], 150)
        self.assertEqual(valores["livre"], 2 * GB)
        self.assertEqual(sum(v for n, v, _ in partes if n != "livre"), 6 * GB, "a soma bate com a memória usada")

    def test_composicao_quando_os_programas_passam_do_usado(self):
        # a memória privada pode somar mais que a "em uso" (parte está no arquivo de paginação)
        partes = info.composicao_da_memoria(8 * GB, 4 * GB, [("x", 5 * GB)])
        self.assertNotIn("Windows, drivers e cache", [n for n, _, _ in partes])
        self.assertEqual(dict((n, v) for n, v, _ in partes)["livre"], 3 * GB)

    def test_historico(self):
        h = info.Historico(tamanho=3)
        for m, c in ((50, 10), (60, None), (70, 30), (80, 40)):
            h.guardar(m, c)
        self.assertEqual(list(h.memoria), [60, 70, 80], "guarda só os últimos")
        self.assertEqual(list(h.processador), [10, 30, 40])
        self.assertEqual(info.Historico.pico_e_media(h.memoria), (80, 70))
        self.assertEqual(info.Historico.pico_e_media([]), (None, None))


if __name__ == "__main__":
    unittest.main()
