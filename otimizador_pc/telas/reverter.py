# -*- coding: utf-8 -*-
"""Reverter: volta os ajustes para como estavam antes."""

from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME
from otimizador_pc import ajustes as aj
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina


class Reverter(Pagina):
    titulo = "Reverter"
    subtitulo = ("Volta cada ajuste para como estava ANTES (não para o padrão de fábrica). "
                 "Se algo falhar, continua guardado aqui para tentar de novo.")

    def montar(self):
        self.j.registrar_botao(self.botao_topo("restaurar tudo", lambda: self.acao(tudo=True), "perigo"))
        self.j.registrar_botao(self.botao_topo("restaurar selecionados", self.acao, "principal"))
        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        self.area = t.rolavel(cartao)
        self.area.pack(fill="both", expand=True, padx=8, pady=8)
        self.vars = {}
        self.lbl_extra = t.rotulo(self.corpo, "", "corpo", 11, t.FRACO, wraplength=900)
        self.lbl_extra.pack(anchor="w", pady=(8, 0))

    def ao_mostrar(self):
        super().ao_mostrar()
        self.atualizar()

    def atualizar(self):
        for w in self.area.winfo_children():
            w.destroy()
        self.vars = {}
        dados = self.j.backup.dados
        aplicados = dados.get("ajustes", {})
        if not aplicados:
            t.rotulo(self.area, "Nenhum ajuste aplicado por este programa.", "corpo", 13, t.SUAVE).pack(
                anchor="w", padx=12, pady=12)
        for aid, reg in aplicados.items():
            var = ctk.BooleanVar(value=False)
            f = ctk.CTkFrame(self.area, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=(10, 0))
            nome = aj.AJUSTES_POR_ID[aid].nome if aid in aj.AJUSTES_POR_ID else reg.get("nome", aid)
            t.caixa(f, nome, var).pack(anchor="w")
            n = len(reg.get("passos", {}))
            t.rotulo(f, f"aplicado em {reg.get('data') or '?'}  ·  {n} mudança(s) guardada(s)", "corpo", 12,
                     t.FRACO).pack(anchor="w", padx=(28, 0))
            self.vars[aid] = var
        extra = len(dados.get("servicos_terceiros", {}))
        self.lbl_extra.configure(text=f"{extra} serviço(s) de outros programas estão em manual: eles voltam pela "
                                      "página Inicialização." if extra else "")

    def acao(self, tudo=False):
        ids = list(self.vars) if tudo else [a for a, v in self.vars.items() if v.get()]
        if not ids:
            messagebox.showinfo(APP_NOME, "Não há nada marcado para restaurar.")
            return
        if not self.j.precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"Voltar {len(ids)} ajuste(s) para como estavam antes?"):
            return
        self.j.trabalhar(lambda ctl: self._reverter(ctl, ids), "restaurando")

    def _reverter(self, ctl, ids):
        self.log("REVERSÃO")
        for n, aid in enumerate(ids):
            ctl.checar()
            nome = self.j.backup.dados["ajustes"].get(aid, {}).get("nome", aid)
            ctl.avisar(f"restaurando: {nome}", n / len(ids))
            self.log(f"> {nome}")
            aj.reverter_ajuste(aid, self.j.backup, self.s, self.log)
        self.log("Pronto. Reinicie o PC para tudo voltar de vez.")
        self.j.no_principal(self.atualizar)
        pagina = self.j.pagina("ajustes")
        if pagina:
            self.j.no_principal(pagina.conferir)
