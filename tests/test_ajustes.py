# -*- coding: utf-8 -*-
import json
import unittest

from falso import BackupTemporario, SistemaFalso

from otimizador_pc import ajustes as aj
from otimizador_pc.ajustes import Ajuste, Registro, Servico, Tarefa

CAM = r"Software\Teste"


def nada(*_):
    pass


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.s = SistemaFalso()
        self.b = BackupTemporario()

    def test_aplica_e_reverte_valor_que_existia(self):
        self.s.reg_escrever("HKCU", CAM, "X", 4, 1)
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "X", 4, 0)])
        self.assertTrue(aj.aplicar_ajuste(a, self.b, self.s, nada))
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "X"), (0, 4))
        self.assertTrue(aj.reverter_ajuste("t", self.b, self.s, nada))
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "X"), (1, 4))
        self.assertNotIn("t", self.b.dados["ajustes"])

    def test_valor_que_nao_existia_e_apagado_ao_reverter(self):
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "Novo", 4, 1)])
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertIsNone(self.s.reg_ler("HKCU", CAM, "Novo"))

    def test_original_vai_para_o_disco_antes_da_mudanca(self):
        b = self.b
        s = self.s
        s.reg_escrever("HKCU", CAM, "X", 4, 7)
        original_escrever = s.reg_escrever
        visto = {}

        def escrever(hive, caminho, nome, tipo, valor):
            with open(b.arquivo, encoding="utf-8") as f:
                visto["disco"] = json.load(f)
            original_escrever(hive, caminho, nome, tipo, valor)
        s.reg_escrever = escrever

        aj.aplicar_ajuste(Ajuste("t", "teste", "", [Registro("HKCU", CAM, "X", 4, 0)]), b, s, nada)
        passos = visto["disco"]["ajustes"]["t"]["passos"]
        self.assertEqual(passos[f"reg:HKCU\\{CAM}\\X"]["original"], {"existia": True, "valor": 7, "tipo": 4})

    def test_reaplicar_nao_troca_o_original(self):
        self.s.reg_escrever("HKCU", CAM, "X", 4, 1)
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "X", 4, 0)])
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        aj.aplicar_ajuste(a, self.b, self.s, nada)  # agora o valor atual já é 0
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "X"), (1, 4))

    def test_reversao_que_falha_fica_guardada_para_tentar_de_novo(self):
        self.s.reg_escrever("HKCU", CAM, "X", 4, 1)
        self.s.reg_escrever("HKCU", CAM, "Y", 4, 1)
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "X", 4, 0), Registro("HKCU", CAM, "Y", 4, 0)])
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        self.s.falhar_reg.add("Y")
        self.assertFalse(aj.reverter_ajuste("t", self.b, self.s, nada))
        passos = self.b.dados["ajustes"]["t"]["passos"]
        self.assertEqual(list(passos), [f"reg:HKCU\\{CAM}\\Y"])  # o X voltou e saiu; o Y ficou
        self.s.falhar_reg.clear()
        self.assertTrue(aj.reverter_ajuste("t", self.b, self.s, nada))
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "Y"), (1, 4))

    def test_falha_ao_aplicar_nao_perde_o_original(self):
        self.s.reg_escrever("HKCU", CAM, "X", 4, 5)
        self.s.falhar_reg.add("X")
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "X", 4, 0)])
        self.assertFalse(aj.aplicar_ajuste(a, self.b, self.s, nada))
        self.s.falhar_reg.clear()
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "X"), (5, 4))

    def test_bytes_vao_e_voltam_do_json(self):
        self.s.reg_escrever("HKCU", CAM, "B", 3, b"\x01\x02")
        a = Ajuste("t", "teste", "", [Registro("HKCU", CAM, "B", 4, 0)])
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        recarregado = BackupTemporario.__new__(BackupTemporario)
        recarregado.salvamentos = 0
        from otimizador_pc.backup import Backup
        Backup.__init__(recarregado, self.b.arquivo)
        aj.reverter_ajuste("t", recarregado, self.s, nada)
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "B"), (b"\x01\x02", 3))

    def test_original_guardado_em_outro_ajuste_e_reaproveitado(self):
        self.s.reg_escrever("HKCU", CAM, "X", 4, 1)
        p = Registro("HKCU", CAM, "X", 4, 0)
        aj.aplicar_ajuste(Ajuste("velho", "velho", "", [p]), self.b, self.s, nada)
        aj.aplicar_ajuste(Ajuste("novo", "novo", "", [p]), self.b, self.s, nada)
        aj.reverter_ajuste("novo", self.b, self.s, nada)
        self.assertEqual(self.s.reg_ler("HKCU", CAM, "X"), (1, 4))


class TestOutrosPassos(unittest.TestCase):
    def setUp(self):
        self.s = SistemaFalso()
        self.b = BackupTemporario()

    def test_servico_volta_com_inicio_atrasado_e_rodando(self):
        self.s.servicos["WSearch"] = {"start": 2, "atrasado": True, "estado": "RUNNING"}
        aj.aplicar_ajuste(Ajuste("t", "t", "", [Servico("WSearch")]), self.b, self.s, nada)
        self.assertEqual(self.s.servicos["WSearch"]["start"], 4)
        self.assertEqual(self.s.servicos["WSearch"]["estado"], "STOPPED")
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.servicos["WSearch"], {"start": 2, "atrasado": True, "estado": "RUNNING"})

    def test_servico_que_ja_estava_desativado_continua_assim(self):
        self.s.servicos["SysMain"] = {"start": 4, "atrasado": False, "estado": "STOPPED"}
        aj.aplicar_ajuste(Ajuste("t", "t", "", [Servico("SysMain")]), self.b, self.s, nada)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.servicos["SysMain"]["start"], 4)
        self.assertNotIn(("iniciar", "SysMain"), self.s.comandos)

    def test_servico_que_nao_existe_e_pulado(self):
        a = Ajuste("t", "t", "", [Servico("dmwappushservice")])
        self.assertTrue(aj.aplicar_ajuste(a, self.b, self.s, nada))
        self.assertNotIn("t", self.b.dados["ajustes"])
        self.assertEqual(aj.estado_do_ajuste(a, self.s), "indisponivel")

    def test_servico_fora_da_lista_e_recusado(self):
        with self.assertRaises(ValueError):
            Servico("Winmgmt")

    def test_tarefa_desligada_antes_nao_e_religada(self):
        self.s.tarefas = {r"\A": True, r"\B": False}
        a = Ajuste("t", "t", "", [Tarefa(r"\A"), Tarefa(r"\B"), Tarefa(r"\NaoExiste")])
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        self.assertEqual(self.s.tarefas, {r"\A": False, r"\B": False})
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.tarefas, {r"\A": True, r"\B": False})

    def test_hibernacao_desligada_antes_nao_e_religada(self):
        self.s.hibernacao = False
        aj.aplicar_ajuste(Ajuste("t", "t", "", [aj.Hibernacao()]), self.b, self.s, nada)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertFalse(self.s.hibernacao)

    def test_hibernacao_ligada_volta_ligada(self):
        aj.aplicar_ajuste(Ajuste("t", "t", "", [aj.Hibernacao()]), self.b, self.s, nada)
        self.assertFalse(self.s.hibernacao)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertTrue(self.s.hibernacao)

    def test_plano_escondido_e_criado_e_apagado_ao_reverter(self):
        antes = self.s.plano
        aj.aplicar_ajuste(Ajuste("t", "t", "", [aj.PlanoEnergia()]), self.b, self.s, nada)
        criado = self.b.dados["ajustes"]["t"]["passos"]["energia"]["criado"]
        self.assertEqual(self.s.plano, criado)
        # reaplicar usa a mesma cópia, não cria outra
        aj.aplicar_ajuste(Ajuste("t", "t", "", [aj.PlanoEnergia()]), self.b, self.s, nada)
        self.assertEqual(len(self.s.lista_planos), 2)
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.plano, antes)
        self.assertNotIn(criado, self.s.lista_planos)

    def test_plano_alto_desempenho_existente_e_usado(self):
        self.s.lista_planos.append(aj.ALTO_DESEMPENHO)
        aj.aplicar_ajuste(Ajuste("t", "t", "", [aj.PlanoEnergia()]), self.b, self.s, nada)
        self.assertEqual(self.s.plano, aj.ALTO_DESEMPENHO)
        self.assertEqual(len(self.s.lista_planos), 2)

    def test_mouse(self):
        a = Ajuste("t", "t", "", [aj.Mouse()])
        self.assertEqual(aj.estado_do_ajuste(a, self.s), "padrao")
        aj.aplicar_ajuste(a, self.b, self.s, nada)
        self.assertEqual(self.s.mouse, [0, 0, 0])
        self.assertEqual(aj.estado_do_ajuste(a, self.s), "aplicado")
        aj.reverter_ajuste("t", self.b, self.s, nada)
        self.assertEqual(self.s.mouse, [6, 10, 1])


class TestLista(unittest.TestCase):
    def test_ids_e_chaves_unicos(self):
        ids = [a.id for a in aj.AJUSTES]
        self.assertEqual(len(ids), len(set(ids)))
        chaves = [p.chave for a in aj.AJUSTES for p in a.passos]
        self.assertEqual(len(chaves), len(set(chaves)), "um passo em dois ajustes estragaria o original")

    def test_ids_da_versao_1_continuam(self):
        for aid in ("telemetria", "tarefas_telemetria", "apps_segundo_plano", "sugestoes_anuncios",
                    "cortana_busca_web", "game_dvr", "indexacao_busca", "sysmain", "hibernacao"):
            self.assertIn(aid, aj.AJUSTES_POR_ID)

    def test_todo_passo_pode_ser_remontado_do_backup(self):
        for a in aj.AJUSTES:
            for p in a.passos:
                remontado = aj.montar_passo(p.classe, json.loads(json.dumps(p.params())))
                self.assertEqual(remontado.chave, p.chave)

    def test_estado_parcial(self):
        s = SistemaFalso()
        s.reg_escrever("HKCU", CAM, "X", 4, 0)
        a = Ajuste("t", "t", "", [Registro("HKCU", CAM, "X", 4, 0), Registro("HKCU", CAM, "Y", 4, 0)])
        self.assertEqual(aj.estado_do_ajuste(a, s), "parcial")


if __name__ == "__main__":
    unittest.main()
