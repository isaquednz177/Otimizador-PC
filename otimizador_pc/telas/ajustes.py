# -*- coding: utf-8 -*-
"""Ajustes do Windows: cada um mostra se já está aplicado. Tudo pode ser desfeito."""

from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME
from otimizador_pc import ajustes as aj
from otimizador_pc import ponto
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina

TEXTO = {"aplicado": "JÁ APLICADO", "parcial": "EM PARTE", "padrao": "PADRÃO DO WINDOWS",
         "indisponivel": "NÃO EXISTE AQUI", None: "conferindo..."}
COR = {"aplicado": t.OK, "parcial": t.ACENTO, "padrao": t.SUAVE, "indisponivel": t.FRACO, None: t.FRACO}


class Ajustes(Pagina):
    titulo = "Ajustes"
    subtitulo = ("Ajustes do Windows. Como estava antes fica guardado, e a página Reverter desfaz "
                 "qualquer um deles.")

    def montar(self):
        self.j.registrar_botao(self.botao_topo("conferir de novo", self.conferir))
        self.j.registrar_botao(self.botao_topo("aplicar selecionados", self.acao_aplicar, "principal"))
        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        area = t.rolavel(cartao)
        area.pack(fill="both", expand=True, padx=8, pady=8)
        self.linhas = {}
        for a in aj.AJUSTES:
            var = ctk.BooleanVar(value=False)
            f = ctk.CTkFrame(area, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=(10, 0))
            f.grid_columnconfigure(0, weight=1)
            caixa = t.caixa(f, a.nome, var)
            caixa.grid(row=0, column=0, sticky="w")
            estado = t.rotulo(f, TEXTO[None], "titulo", 11, COR[None], anchor="e")
            estado.grid(row=0, column=1, sticky="e", padx=8)
            t.rotulo(f, a.descricao, "corpo", 12, t.FRACO, wraplength=720).grid(
                row=1, column=0, columnspan=2, sticky="w", padx=(28, 0), pady=(2, 0))
            self.linhas[a.id] = (a, var, caixa, estado)

        rodape = ctk.CTkFrame(self.corpo, fg_color="transparent")
        rodape.pack(fill="x", pady=(10, 0))
        self.var_ponto = ctk.BooleanVar(value=True)
        t.caixa(rodape, "criar um ponto de restauração antes (recomendado)", self.var_ponto).pack(side="left")
        self._conferido = False

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
            messagebox.showinfo(APP_NOME, "Marque pelo menos um ajuste.")
            return
        if not self.j.precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"Aplicar {len(escolhidos)} ajuste(s)? Como estava antes fica "
                                             "guardado, e a página Reverter desfaz."):
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
                                "pela página Reverter. Continuar mesmo assim?", aviso=True)
