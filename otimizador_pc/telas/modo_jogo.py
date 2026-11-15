# -*- coding: utf-8 -*-
"""Modo jogo: fecha o que você escolher e liga o Alto desempenho; ao sair, volta tudo."""

import threading

import customtkinter as ctk

from otimizador_pc import ajustes as aj
from otimizador_pc import modo_jogo as mj
from otimizador_pc import tema as t
from otimizador_pc.processos import Monitor
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho


class ModoJogo(Pagina):
    titulo = "Modo jogo"
    subtitulo = ("Antes de jogar: fecha os programas que você marcar e liga o Alto desempenho. Ao sair, "
                 "volta o plano de energia de antes e reabre o que foi fechado.")

    def montar(self):
        self.pref = self.j.config.dados["modo_jogo"]
        self.botao_topo("atualizar a lista", self._ler)

        topo = t.cartao(self.corpo)
        topo.pack(fill="x")
        topo.grid_columnconfigure(0, weight=1)
        esq = ctk.CTkFrame(topo, fg_color="transparent")
        esq.grid(row=0, column=0, sticky="w", padx=18, pady=16)
        t.rotulo(esq, "ESTADO", "titulo", 11, t.SUAVE).pack(anchor="w")
        self.lbl_estado = t.rotulo(esq, "", "numero", 28)
        self.lbl_estado.pack(anchor="w")
        self.lbl_desde = t.rotulo(esq, "", "corpo", 12, t.FRACO)
        self.lbl_desde.pack(anchor="w")
        self.btn = self.j.registrar_botao(t.botao(topo, "", self._alternar, "principal", largura=200, altura=44,
                                                  font=t.fonte("titulo", 15)))
        self.btn.grid(row=0, column=1, padx=18)

        opcoes = ctk.CTkFrame(self.corpo, fg_color="transparent")
        opcoes.pack(fill="x", pady=(12, 6))
        self.var_desempenho = ctk.BooleanVar(value=self.pref.get("desempenho", True))
        self.var_reabrir = ctk.BooleanVar(value=self.pref.get("reabrir", True))
        t.caixa(opcoes, "ligar o Alto desempenho enquanto joga", self.var_desempenho,
                command=self._guardar).pack(side="left")
        t.caixa(opcoes, "reabrir os programas quando sair", self.var_reabrir,
                command=self._guardar).pack(side="left", padx=24)

        lista = t.cartao(self.corpo)
        lista.pack(fill="both", expand=True)
        t.rotulo(lista, "FECHAR AO ENTRAR NO MODO JOGO", "titulo", 11, t.SUAVE).pack(anchor="w", padx=18, pady=(14, 0))
        t.rotulo(lista, "Programas abertos agora. O que você marcar fica guardado para as próximas vezes.",
                 "corpo", 12, t.FRACO).pack(anchor="w", padx=18)
        self.area = t.rolavel(lista)
        self.area.pack(fill="both", expand=True, padx=8, pady=8)
        self.vars = {}

    def ao_mostrar(self):
        super().ao_mostrar()
        self._estado()
        self._ler()

    def _estado(self):
        ligado = mj.ativo(self.j.backup)
        desde = self.j.backup.dados.get("modo_jogo", {}).get("desde", "")
        self.lbl_estado.configure(text="LIGADO" if ligado else "DESLIGADO", text_color=t.ACENTO if ligado else t.SUAVE)
        self.lbl_desde.configure(text=f"desde {desde}" if ligado else "")
        self.btn.configure(text="sair do modo jogo" if ligado else "entrar no modo jogo")

    def _guardar(self):
        self.pref["desempenho"] = bool(self.var_desempenho.get())
        self.pref["reabrir"] = bool(self.var_reabrir.get())
        self.pref["fechar"] = sorted(exe for exe, var in self.vars.items() if var.get())
        self.j.config.salvar()

    def _ler(self):
        def ler():
            return Monitor().ler(mostrar=40)
        threading.Thread(target=lambda: self.j.no_principal(self._lista, ler()), daemon=True).start()

    def _lista(self, grupos):
        for w in self.area.winfo_children():
            w.destroy()
        marcados = set(self.pref.get("fechar", []))
        self.vars = {}
        vistos = set()
        for g in grupos:
            if not g.pode_fechar or g.exe in vistos:
                continue
            vistos.add(g.exe)
            self._item(g.exe, g.nome, f"{g.exe} · {formatar_tamanho(g.memoria)}", g.exe in marcados)
        for exe in sorted(marcados - vistos):  # marcados que não estão abertos agora
            self._item(exe, exe, "não está aberto agora", True)

    def _item(self, exe, nome, sub, marcado):
        var = ctk.BooleanVar(value=marcado)
        self.vars[exe] = var
        f = ctk.CTkFrame(self.area, fg_color="transparent")
        f.pack(fill="x", padx=8, pady=(6, 0))
        t.caixa(f, nome, var, command=self._guardar).pack(anchor="w")
        t.rotulo(f, sub, "corpo", 11, t.FRACO).pack(anchor="w", padx=(28, 0))

    def _alternar(self):
        if not self.j.precisa_admin():
            return
        self._guardar()
        if mj.ativo(self.j.backup):
            self.j.trabalhar(lambda ctl: mj.sair(self.s, self.j.backup, self.pref, self.log),
                             "saindo do modo jogo", cancelavel=False)
        else:
            energia_ja = aj.estado_do_ajuste(aj.AJUSTES_POR_ID["energia_desempenho"], self.s,
                                             self.j.backup.dados) == "aplicado"
            # mostrar=300: lê o caminho de cada programa, para poder reabrir depois
            self.j.trabalhar(lambda ctl: mj.entrar(self.s, self.j.backup, self.pref, Monitor().ler(mostrar=300),
                                                   self.log, energia_ja), "entrando no modo jogo", cancelavel=False)
        self.after(1500, self._depois)

    def _depois(self):
        if self.j.ocupado:
            self.after(500, self._depois)
            return
        self._estado()
        self._ler()
