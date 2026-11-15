# -*- coding: utf-8 -*-
"""Limpeza: analisar sem apagar, depois limpar o que foi marcado."""

from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME, info, limpeza
from otimizador_pc import tema as t
from otimizador_pc.controle import Cancelado
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

SEM_ADMIN = {"temp_user", "navegador_chrome", "navegador_edge", "navegador_brave", "navegador_opera",
             "navegador_operagx", "navegador_firefox", "shaders", "miniaturas", "lixeira", "dns"}


class Limpeza(Pagina):
    titulo = "Limpeza"
    subtitulo = "\"Analisar\" mostra quanto cada item libera, sem apagar nada. Arquivos em uso ficam."

    def montar(self):
        self.j.registrar_botao(self.botao_topo("analisar", self.acao_analisar))
        self.j.registrar_botao(self.botao_topo("limpar selecionados", self.acao_limpar, "principal"))

        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        area = t.rolavel(cartao)
        area.pack(fill="both", expand=True, padx=8, pady=8)
        self.itens = {}
        self.tamanhos = {}
        for item in limpeza.ITENS:
            if not item.disponivel():
                continue
            var = ctk.BooleanVar(value=item.padrao)
            var.trace_add("write", lambda *_: self._somar())
            f = ctk.CTkFrame(area, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=(10, 0))
            f.grid_columnconfigure(0, weight=1)
            t.caixa(f, item.nome, var).grid(row=0, column=0, sticky="w")
            lado = t.rotulo(f, "" if item.libera_espaco else "não libera espaço", "numero", 14, t.SUAVE,
                            anchor="e")
            lado.grid(row=0, column=1, sticky="e", padx=8)
            t.rotulo(f, item.descricao, "corpo", 12, t.FRACO, wraplength=720).grid(
                row=1, column=0, columnspan=2, sticky="w", padx=(28, 0), pady=(2, 0))
            self.itens[item.id] = (item, var, lado)

        rodape = ctk.CTkFrame(self.corpo, fg_color="transparent")
        rodape.pack(fill="x", pady=(10, 0))
        t.botao(rodape, "só os recomendados", self._recomendados, "fantasma").pack(side="left")
        t.botao(rodape, "desmarcar tudo", lambda: self._marcar(False), "fantasma").pack(side="left", padx=6)
        self.lbl_total = t.rotulo(rodape, "", "numero", 15, t.TEXTO)
        self.lbl_total.pack(side="right", padx=4)

    def _marcar(self, valor):
        for _, var, _ in self.itens.values():
            var.set(valor)

    def _recomendados(self):
        for item, var, _ in self.itens.values():
            var.set(item.padrao)

    def _somar(self):
        if not self.tamanhos:
            self.lbl_total.configure(text="")
            return
        total, sem = 0, False
        for iid, (item, var, _) in self.itens.items():
            if var.get() and item.libera_espaco:
                if self.tamanhos.get(iid) is None:
                    sem = True
                else:
                    total += self.tamanhos[iid]
        self.lbl_total.configure(text=f"selecionado: {formatar_tamanho(total)}" + (" +" if sem else ""))

    def _mostrar_tamanho(self, iid, res):
        item, _, lado = self.itens[iid]
        if res is None:
            self.tamanhos[iid] = None
            lado.configure(text="sem estimativa", text_color=t.FRACO)
        else:
            self.tamanhos[iid] = res.bytes
            grande = res.bytes >= 500 << 20
            lado.configure(text=formatar_tamanho(res.bytes) if res.apagados else "vazio",
                           text_color=t.ACENTO if grande else (t.TEXTO if res.apagados else t.FRACO))
        self._somar()

    # ------------------------------------------------------------ analisar
    def acao_analisar(self):
        self.j.trabalhar(self._analisar, "analisando")

    def _analisar(self, ctl):
        itens = [(iid, it) for iid, (it, _, _) in self.itens.items() if it.libera_espaco]
        total = 0
        for n, (iid, item) in enumerate(itens):
            ctl.checar()
            ctl.avisar(f"analisando: {item.nome}", n / len(itens))
            lado = self.itens[iid][2]
            self.j.no_principal(lambda r=lado: r.configure(text="analisando...", text_color=t.FRACO))
            try:
                res = limpeza.analisar_item(item, self.s, ctl)
            except Cancelado:
                raise
            except Exception as e:
                self.log(f"   [erro] {item.nome}: {e}")
                res = None
            self.j.no_principal(self._mostrar_tamanho, iid, res)
            total += res.bytes if res else 0
        self.log(f"Análise pronta: {formatar_tamanho(total)} no total (fora os itens sem estimativa).")

    # ------------------------------------------------------------ limpar
    def acao_limpar(self):
        escolhidos = [it for it, var, _ in self.itens.values() if var.get()]
        if not escolhidos:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um item.")
            return
        for it in escolhidos:
            if it.confirmar and not messagebox.askyesno(APP_NOME, it.confirmar, icon="warning"):
                return
        if any(i.id == "componentes" for i in escolhidos) and not messagebox.askyesno(
                APP_NOME, "A limpeza de componentes do Windows demora de 5 a 30 minutos e não pode ser "
                          "interrompida no meio. Continuar?"):
            return
        if any(i.id not in SEM_ADMIN for i in escolhidos) and not self.j.precisa_admin():
            return
        self.j.trabalhar(lambda ctl: self._limpar(ctl, escolhidos), "limpando")

    def _limpar(self, ctl, escolhidos):
        self.log("LIMPEZA")
        livre_antes = info.espaco_livre()
        soma = 0
        try:
            for n, item in enumerate(escolhidos):
                ctl.checar()
                ctl.avisar(f"limpando: {item.nome}", n / len(escolhidos))
                self.log(f"> {item.nome}")
                try:
                    res = limpeza.limpar_item(item, self.s, self.log, ctl)
                except Cancelado:
                    raise
                except Exception as e:
                    self.log(f"   [erro] {e}")
                    continue
                if res.nota:
                    self.log(f"   {res.nota}")
                if item.libera_espaco and (res.apagados or res.pulados):
                    self.log(f"   {res.apagados} arquivo(s), {formatar_tamanho(res.bytes)}"
                             + (f"; {res.pulados} em uso ficaram" if res.pulados else ""))
                soma += res.bytes
                self.j.no_principal(self._limpo, item.id)
        finally:
            livre_depois = info.espaco_livre()
            if livre_antes is not None and livre_depois is not None:
                self.log(f"Pronto: {formatar_tamanho(soma)} apagados. Espaço livre: "
                         f"{formatar_tamanho(livre_antes)} → {formatar_tamanho(livre_depois)}.")

    def _limpo(self, iid):
        item, _, lado = self.itens[iid]
        if item.libera_espaco:
            lado.configure(text="limpo", text_color=t.OK)
            self.tamanhos.pop(iid, None)
            self._somar()
