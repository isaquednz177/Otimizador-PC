# -*- coding: utf-8 -*-
"""Ajustes do Windows: cada um mostra se já está aplicado. Tudo pode ser desfeito."""

from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME
from otimizador_pc import ajustes as aj
from otimizador_pc import ponto
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina

TEXTO = {"aplicado": "já está feito", "parcial": "feito em parte", "padrao": "ainda não feito",
         "indisponivel": "não existe neste PC", None: "conferindo..."}
COR = {"aplicado": t.OK, "parcial": t.LARANJA, "padrao": t.SUAVE, "indisponivel": t.FRACO, None: t.FRACO}


class Ajustes(Pagina):
    titulo = "Ajustes do Windows"
    subtitulo = ("Mudanças nas configurações do Windows para deixar o PC mais leve e com menos propaganda. "
                 "Como estava antes fica guardado: a página \"Desfazer ajustes\" volta qualquer um deles.")

    def montar(self):
        self.j.registrar_botao(self.botao_topo("conferir de novo", self.conferir))
        self.j.registrar_botao(self.botao_topo("fazer o que está marcado", self.acao_aplicar, "principal", largura=230))
        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        area = t.rolavel(cartao)
        area.pack(fill="both", expand=True, padx=8, pady=8)
        self.linhas = {}
        for a in [a for a in aj.AJUSTES if a.nivel != "avancado"]:
            self._linha(area, a)
        avancados = [a for a in aj.AJUSTES if a.nivel == "avancado"]
        if avancados:
            recolhivel = t.Recolhivel(area, len(avancados))
            for a in avancados:
                self._linha(recolhivel.corpo, a)

        rodape = ctk.CTkFrame(self.corpo, fg_color="transparent")
        rodape.pack(fill="x", pady=(10, 0))
        self.var_ponto = ctk.BooleanVar(value=True)
        t.caixa(rodape, "criar um ponto de restauração antes (recomendado)", self.var_ponto).pack(side="left")
        t.ajuda(rodape, "Uma \"foto\" das configurações do Windows tirada antes de mudar qualquer coisa. Se algo der "
                        "errado, dá para voltar o Windows para como estava (Painel de Controle › Recuperação).").pack(
            side="left", padx=8)
        self._conferido = False

    def _linha(self, pai, a):
        var = ctk.BooleanVar(value=False)
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(fill="x", padx=8, pady=(10, 0))
        f.grid_columnconfigure(0, weight=1)
        nome, caixa = t.nome_com_etiqueta(f, a.nome, var, a.nivel)
        nome.grid(row=0, column=0, sticky="w")
        estado = t.rotulo(f, TEXTO[None], "titulo", 12, COR[None], anchor="e")
        estado.grid(row=0, column=1, sticky="e", padx=8)
        t.texto_longo(f, a.descricao, "corpo", 12, t.FRACO).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=(28, 0), pady=(2, 0))
        self.linhas[a.id] = (a, var, caixa, estado)

    def ao_mostrar(self):
        super().ao_mostrar()
        if not self._conferido:
            self.conferir()

    def conferir(self):
        self._conferido = True
        for a, _, _, estado in self.linhas.values():
            estado.configure(text=TEXTO[None], text_color=COR[None])
        self.j.em_segundo_plano(
            lambda: {a.id: aj.estado_do_ajuste(a, self.s, self.j.backup.dados) for a in aj.AJUSTES},
            self._mostrar)

    def _mostrar(self, estados):
        for aid, e in estados.items():
            _, var, caixa, estado = self.linhas[aid]
            estado.configure(text=TEXTO[e], text_color=COR[e])
            if e == "indisponivel":
                var.set(False)
                caixa.configure(state="disabled")
            else:
                caixa.configure(state="normal")

    # ------------------------------------------------------------ aplicar
    def acao_aplicar(self):
        escolhidos = [a for a, var, _, _ in self.linhas.values() if var.get()]
        if not escolhidos:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um ajuste na lista.")
            return
        if not self.j.precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"Aplicar {len(escolhidos)} ajuste(s)? Como estava antes fica "
                                             "guardado, e a página \"Desfazer ajustes\" volta atrás."):
            return
        com_ponto = self.var_ponto.get()
        self.j.trabalhar(lambda ctl: self._aplicar(ctl, escolhidos, com_ponto), "aplicando ajustes")

    def _aplicar(self, ctl, escolhidos, com_ponto):
        self.log("AJUSTES")
        if com_ponto:
            ctl.avisar("criando ponto de restauração")
            if not self._garantir_ponto():
                self.log("Cancelado: nada foi mudado.")
                return
        for n, a in enumerate(escolhidos):
            ctl.checar()  # cancelar só entre um ajuste e outro, nunca no meio
            ctl.avisar(f"aplicando: {a.nome}", n / len(escolhidos))
            self.log(f"> {a.nome}")
            aj.aplicar_ajuste(a, self.j.backup, self.s, self.log)
        self.log("Pronto. Alguns ajustes só valem depois de reiniciar o PC.")
        self.j.no_principal(self.conferir)
        reverter = self.j.pagina("reverter")
        if reverter:
            self.j.no_principal(reverter.atualizar)

    def _garantir_ponto(self) -> bool:
        r = ponto.criar_ponto(self.s, self.log)
        if r == "desligada":
            if self.j.perguntar("A Proteção do Sistema está desligada neste PC, então o Windows não cria "
                                "pontos de restauração.\n\nLigar agora no disco do sistema? Ela usa uma parte "
                                "pequena do disco para guardar os pontos."):
                ok, msg = ponto.ligar_protecao(self.s)
                self.log("Proteção do Sistema ligada." if ok else f"Não deu para ligar: {msg}")
                if ok:
                    r = ponto.criar_ponto(self.s, self.log)
        if r == "ok":
            return True
        return self.j.perguntar("Não foi criado um ponto de restauração.\n\nOs ajustes ainda podem ser desfeitos "
                                "pela página \"Desfazer ajustes\". Continuar mesmo assim?", aviso=True)
