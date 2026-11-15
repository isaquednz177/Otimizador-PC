# -*- coding: utf-8 -*-
"""Desinstalar programas e apagar o que eles deixam para trás (como o Revo Uninstaller)."""

import os
from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME
from otimizador_pc import desinstalar as d
from otimizador_pc import ponto
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

ORDENS = [("nome", "nome"), ("tamanho", "maiores"), ("data", "mais novos")]


def _data_ordem(p):
    if not p.data:
        return ""
    dia, mes, ano = p.data.split("/")
    return ano + mes + dia


class Desinstalar(Pagina):
    titulo = "Desinstalar programas"
    subtitulo = ("Tira um programa do PC de verdade. Primeiro roda o desinstalador do próprio programa; depois "
                 "procura as pastas e os registros que ele esqueceu e mostra tudo antes de apagar.")

    def montar(self):
        self.botao_topo("atualizar", self.atualizar)
        barra = ctk.CTkFrame(self.corpo, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 10))
        self.busca = ctk.CTkEntry(barra, width=280, height=32, corner_radius=t.RAIO, border_width=1,
                                  border_color=t.ORNATO, fg_color=t.PAINEL2, text_color=t.TEXTO,
                                  placeholder_text="procurar um programa...", placeholder_text_color=t.FRACO,
                                  font=t.fonte("corpo", 13))
        self.busca.pack(side="left")
        self.busca.bind("<KeyRelease>", lambda e: self._agendar())
        self.ordem = "nome"
        self.botoes_ordem = {}
        t.rotulo(barra, "ordem:", "corpo", 12, t.FRACO).pack(side="left", padx=(18, 6))
        for chave, texto in ORDENS:
            b = t.botao(barra, texto, lambda c=chave: self._ordenar(c), "fantasma", largura=90, altura=30)
            b.pack(side="left", padx=(0, 2))
            self.botoes_ordem[chave] = b
        self.lbl_total = t.rotulo(barra, "", "corpo", 12, t.FRACO)
        self.lbl_total.pack(side="right")

        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        self.area = t.rolavel(cartao)
        self.area.pack(fill="both", expand=True, padx=8, pady=8)
        self.programas, self._carregado, self._espera = [], False, None
        self._marcar_ordem()

    def ao_mostrar(self):
        super().ao_mostrar()
        if not self._carregado:
            self.atualizar()

    # ------------------------------------------------------------ lista
    def atualizar(self):
        self._carregado = True
        self._limpar()
        t.rotulo(self.area, "lendo os programas instalados...", "corpo", 13, t.FRACO).pack(anchor="w", padx=12, pady=12)
        self.j.em_segundo_plano(lambda: d.listar(self.s), self._chegou)

    def _chegou(self, programas):
        self.programas = programas
        self._desenhar()

    def _limpar(self):
        for w in self.area.winfo_children():
            w.destroy()

    def _agendar(self):
        if self._espera:
            self.after_cancel(self._espera)
        self._espera = self.after(250, self._desenhar)

    def _ordenar(self, chave):
        self.ordem = chave
        self._marcar_ordem()
        self._desenhar()

    def _marcar_ordem(self):
        for chave, b in self.botoes_ordem.items():
            ativo = chave == self.ordem
            b.configure(fg_color=t.NAV_ATIVO if ativo else "transparent", text_color=t.TEXTO if ativo else t.SUAVE)

    def _desenhar(self):
        self._espera = None
        self._limpar()
        termo = self.busca.get().strip().lower()
        lista = [p for p in self.programas if not termo or termo in p.nome.lower() or termo in p.editor.lower()]
        if self.ordem == "tamanho":
            lista.sort(key=lambda p: -p.tamanho)
        elif self.ordem == "data":
            lista.sort(key=_data_ordem, reverse=True)
        total = sum(p.tamanho for p in self.programas)
        self.lbl_total.configure(text=f"{len(self.programas)} programas  ·  {formatar_tamanho(total)} no total")
        if not lista:
            t.rotulo(self.area, "Nenhum programa com esse nome." if termo else "Nenhum programa encontrado.",
                     "corpo", 13, t.FRACO).pack(anchor="w", padx=12, pady=12)
            return
        for p in lista:
            self._linha(p)

    def _linha(self, p):
        f = ctk.CTkFrame(self.area, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(10, 0))
        f.grid_columnconfigure(0, weight=1)
        t.rotulo(f, p.nome, "corpo_forte", 13).grid(row=0, column=0, sticky="w")
        partes = [p.editor if p.editor and p.editor != "None" else "fabricante desconhecido"]
        if p.versao:
            partes.append(f"versão {p.versao}")
        if p.tamanho:
            partes.append(formatar_tamanho(p.tamanho))
        if p.data:
            partes.append(f"instalado em {p.data}")
        t.rotulo(f, "  ·  ".join(partes), "corpo", 11, t.FRACO).grid(row=1, column=0, sticky="w")
        aviso = ""
        if p.compartilhado:
            aviso = "outros programas podem precisar dele: só desinstale se tiver certeza"
        elif p.da_microsoft:
            aviso = "é da Microsoft: o Windows ou outros programas podem usar"
        if aviso:
            t.rotulo(f, aviso, "corpo", 11, t.LARANJA).grid(row=2, column=0, sticky="w")
        existe = d.desinstalador_existe(p)
        texto, acao = ("desinstalar", lambda: self._desinstalar(p)) if existe else \
            ("remover restos", lambda: self._restos(p))
        b = t.botao(f, texto, acao, "perigo" if existe else "secundario", largura=130, altura=28)
        b.grid(row=0, column=1, rowspan=2, sticky="e")
        if not existe:
            t.Dica(b, "O desinstalador deste programa já foi apagado. Eu procuro o que ficou para trás "
                      "e mostro antes de apagar.")
        t.separador(self.area).pack(fill="x", padx=10, pady=(10, 0))

    # ------------------------------------------------------------ desinstalar
    def _desinstalar(self, p):
        if not self.j.precisa_admin():
            return
        texto = (f"Desinstalar \"{p.nome}\"?\n\n"
                 "1. O desinstalador do próprio programa vai abrir: siga os passos dele.\n"
                 "2. Quando ele terminar, eu procuro o que ficou para trás e mostro antes de apagar qualquer coisa.")
        if p.compartilhado:
            texto += "\n\nAtenção: outros programas podem precisar deste. Se algum parar de abrir, instale de novo."
        if not messagebox.askyesno(APP_NOME, texto, icon="warning" if p.compartilhado else "question"):
            return
        self.j.trabalhar(lambda ctl: self._rodar(ctl, p), f"desinstalando {p.nome}")

    def _restos(self, p):
        if not self.j.precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"O desinstalador de \"{p.nome}\" não existe mais: ele já foi apagado, "
                                             "mas o programa ficou na lista.\n\nProcurar o que sobrou dele?"):
            return
        self.j.trabalhar(lambda ctl: self._procurar(ctl, p, ainda=False), "procurando o que sobrou")

    def _rodar(self, ctl, p):
        self.log(f"DESINSTALAR · {p.nome}")
        if ponto.protecao_ligada(self.s):
            ctl.avisar("criando um ponto de restauração antes")
            ponto.criar_ponto(self.s, self.log)
        else:
            self.log("Sem ponto de restauração: a Proteção do Sistema está desligada (dá para ligar em Ajustes do Windows).")
        cmd = d.comando(p)
        ctl.avisar(f"esperando o desinstalador do {p.nome} terminar")
        self.log(f"Abrindo o desinstalador: {cmd}")
        codigo, erro = self.s.rodar_desinstalador(cmd, ctl)
        if erro:
            self.log(f"Não deu para abrir o desinstalador: {erro}")
            self.j.no_principal(messagebox.showerror, APP_NOME, f"Não deu para abrir o desinstalador:\n{erro}")
            return
        self.log(f"O desinstalador terminou (código {codigo}).")
        instalados = d.listar(self.s)
        ainda = any(x.id == p.id for x in instalados) and d.desinstalador_existe(p)
        if ainda and not self.j.perguntar(
                f"\"{p.nome}\" ainda aparece como instalado. Talvez a desinstalação foi cancelada, ou ela "
                "termina só depois de reiniciar o PC.\n\nProcurar mesmo assim o que sobrou? Nesse caso eu não "
                "mexo na pasta onde ele está instalado."):
            self.j.no_principal(self.atualizar)
            return
        self._procurar(ctl, p, ainda, instalados)

    def _procurar(self, ctl, p, ainda, instalados=None):
        ctl.avisar("procurando o que ficou para trás")
        instalados = instalados if instalados is not None else d.listar(self.s)
        outros = [x for x in instalados if x.id != p.id]
        sobras = d.procurar(p, outros, self.s, ainda_instalado=ainda)
        self.log(f"Sobras encontradas: {len(sobras)}")
        self.j.no_principal(self.atualizar)
        self.j.no_principal(self._mostrar_sobras, p, sobras)

    # ------------------------------------------------------------ sobras
    def _mostrar_sobras(self, p, sobras):
        if not sobras:
            messagebox.showinfo(APP_NOME, f"Pronto: não sobrou nada de \"{p.nome}\".")
            return
        JanelaSobras(self, p, sobras, self._apagar)

    def _apagar(self, p, escolhidas):
        if not escolhidas:
            return
        def trabalho(ctl):
            ctl.avisar(f"apagando o que sobrou de {p.nome}")
            self.log(f"APAGAR SOBRAS · {p.nome}")
            feitas, falhas = d.apagar(self.s, escolhidas, p.nome, self.log)
            msg = f"Apaguei {feitas} de {len(escolhidas)} sobras de \"{p.nome}\"."
            if any(x.tipo == "pasta" for x in escolhidas):
                msg += "\n\nAs pastas estão na Lixeira: dá para restaurar de lá."
            if any(x.tipo == "registro" for x in escolhidas):
                msg += f"\n\nA cópia do registro ficou em:\n{d.PASTA_COPIAS}\n(dois cliques no arquivo .reg põem de volta)"
            if falhas:
                msg += f"\n\n{falhas} não deram para apagar (veja o Histórico)."
            self.log(msg.split("\n")[0])
            self.j.no_principal(messagebox.showinfo, APP_NOME, msg)
            self.j.no_principal(self.atualizar)
        self.j.trabalhar(trabalho, "apagando sobras")


class JanelaSobras(ctk.CTkToplevel):
    """A lista do que sobrou, para marcar o que apagar."""

    def __init__(self, pagina, programa, sobras, ao_apagar):
        super().__init__(pagina.j, fg_color=t.FUNDO)
        self.programa, self.ao_apagar = programa, ao_apagar
        self.title(f"O que sobrou de {programa.nome}")
        self.geometry("860x580")
        self.minsize(640, 420)
        self.transient(pagina.j)
        icone = os.path.join(t.ARTE, "icone.ico")
        if os.path.exists(icone):
            self.after(250, lambda: self.iconbitmap(icone))   # o customtkinter troca o ícone logo depois de abrir
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        t.rotulo(self, f"Sobrou isto de \"{programa.nome}\"", "titulo", 17).grid(
            row=0, column=0, sticky="w", padx=22, pady=(18, 2))
        t.texto_longo(self, "Marque o que apagar. O que já vem marcado tem o nome do programa. Confira com "
                            "atenção o que está desmarcado. As pastas vão para a Lixeira, e o registro ganha uma "
                            "cópia antes (um arquivo .reg).", "corpo", 12, t.SUAVE).grid(
            row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        cartao = t.cartao(self, ornado=False)
        cartao.grid(row=2, column=0, sticky="nsew", padx=22)
        area = t.rolavel(cartao)
        area.pack(fill="both", expand=True, padx=6, pady=6)
        self.vars = []
        pastas = [x for x in sobras if x.tipo == "pasta"]
        chaves = [x for x in sobras if x.tipo == "registro"]
        if pastas:
            total = sum(x.tamanho for x in pastas)
            self._secao(area, f"Pastas  ·  {formatar_tamanho(total)}")
            for x in pastas:
                self._item(area, x, f"{x.motivo}  ·  {formatar_tamanho(x.tamanho)}")
        if chaves:
            self._secao(area, "Registro do Windows")
            for x in chaves:
                self._item(area, x, x.motivo)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.grid(row=3, column=0, sticky="ew", padx=22, pady=14)
        t.botao(rodape, "marcar tudo", lambda: [v.set(True) for v, _ in self.vars], "fantasma", largura=110).pack(side="left")
        t.botao(rodape, "desmarcar tudo", lambda: [v.set(False) for v, _ in self.vars], "fantasma", largura=120).pack(side="left")
        t.botao(rodape, "apagar o que está marcado", self._apagar, "principal", largura=220).pack(side="right")
        t.botao(rodape, "não apagar nada", self.destroy, "secundario", largura=140).pack(side="right", padx=(0, 8))
        self.after(150, self._focar)

    def _focar(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def _secao(self, pai, texto):
        t.rotulo(pai, texto, "titulo", 13, t.ACENTO).pack(anchor="w", padx=10, pady=(12, 2))
        t.separador(pai).pack(fill="x", padx=10, pady=(0, 4))

    def _item(self, pai, sobra, detalhe):
        var = ctk.BooleanVar(value=sobra.forte)
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(6, 0))
        t.caixa(f, sobra.caminho, var).pack(anchor="w")
        cor = t.FRACO if sobra.forte else t.LARANJA
        t.rotulo(f, detalhe + ("" if sobra.forte else "  ·  confira antes"), "corpo", 11, cor).pack(
            anchor="w", padx=(28, 0))
        self.vars.append((var, sobra))

    def _apagar(self):
        escolhidas = [s for v, s in self.vars if v.get()]
        if not escolhidas:
            messagebox.showinfo(APP_NOME, "Nada marcado.", parent=self)
            return
        if not messagebox.askyesno(APP_NOME, f"Apagar {len(escolhidas)} item(ns)?\n\nAs pastas vão para a Lixeira "
                                             "e o registro ganha uma cópia antes.", parent=self):
            return
        self.grab_release()
        self.destroy()
        self.ao_apagar(self.programa, escolhidas)
