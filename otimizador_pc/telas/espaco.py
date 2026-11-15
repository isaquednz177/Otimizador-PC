# -*- coding: utf-8 -*-
"""Espaço em disco: o que ocupa o C: (ou outra pasta). Só mostra; nada é apagado aqui."""

import os
import shutil
from tkinter import filedialog

import customtkinter as ctk

from otimizador_pc import espaco, info
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

MAX_LINHAS = 40


class Espaco(Pagina):
    titulo = "Espaço em disco"
    subtitulo = ("O que ocupa o disco, pasta por pasta. Clique numa pasta para entrar nela. "
                 "Esta página só mostra: nada é apagado aqui.")

    def montar(self):
        self.mapa = None
        self.atual = None
        self.j.registrar_botao(self.botao_topo("outra pasta...", self._escolher))
        self.j.registrar_botao(self.botao_topo(f"medir o {info.disco_do_sistema()[:2]}",
                                               lambda: self._medir(info.disco_do_sistema()), "principal"))

        self.corpo.grid_columnconfigure(0, weight=3)
        self.corpo.grid_columnconfigure(1, weight=2)
        self.corpo.grid_rowconfigure(1, weight=1)

        nav = ctk.CTkFrame(self.corpo, fg_color="transparent")
        nav.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        nav.grid_columnconfigure(1, weight=1)
        self.btn_subir = t.botao(nav, t.ICONES["subir"], self._subir, "secundario", largura=36,
                                 font=t.fonte("icone", 13))
        self.btn_subir.grid(row=0, column=0, padx=(0, 10))
        self.lbl_caminho = t.rotulo(nav, "Clique em \"medir\" para começar.", "corpo", 13, t.SUAVE)
        self.lbl_caminho.grid(row=0, column=1, sticky="w")
        self.btn_abrir = t.botao(nav, "abrir no Explorador", self._abrir_atual, "fantasma")
        self.btn_abrir.grid(row=0, column=2)

        esq = t.cartao(self.corpo)
        esq.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        self.lbl_total = t.rotulo(esq, "", "titulo", 12, t.SUAVE)
        self.lbl_total.pack(anchor="w", padx=18, pady=(12, 4))
        self.lista = t.rolavel(esq)
        self.lista.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        dir_ = t.cartao(self.corpo)
        dir_.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        t.rotulo(dir_, "Maiores arquivos", "titulo", 12, t.SUAVE).pack(anchor="w", padx=18, pady=(12, 4))
        self.maiores = t.rolavel(dir_)
        self.maiores.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.lbl_nota = t.rotulo(self.corpo, "", "corpo", 11, t.FRACO, wraplength=900)
        self.lbl_nota.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------ medir
    def _escolher(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta para medir")
        if pasta:
            self._medir(os.path.normpath(pasta))

    def _medir(self, raiz):
        self.j.trabalhar(lambda ctl: self._tarefa(ctl, raiz), f"medindo {raiz}")

    def _tarefa(self, ctl, raiz):
        self.log(f"Medindo {raiz} (só leitura)...")
        mapa = espaco.varrer(raiz, ctl)
        self.log(f"Medição {'interrompida' if mapa.cancelado else 'pronta'}: "
                 f"{mapa.arquivos:,} arquivos.".replace(",", "."))
        self.j.no_principal(self._pronto, mapa)

    def _pronto(self, mapa):
        self.mapa = mapa
        self._mostrar(mapa.raiz)
        self._mostrar_maiores()
        nota = []
        if mapa.cancelado:
            nota.append("A medição foi cancelada: os números estão incompletos.")
        if mapa.sem_acesso:
            nota.append(f"{mapa.sem_acesso} pasta(s) o Windows não deixou abrir.")
        raiz = mapa.pasta(mapa.raiz)
        if raiz and os.path.splitdrive(mapa.raiz)[1].strip("\\/") == "":
            try:
                uso = shutil.disk_usage(mapa.raiz)
                fora = uso.used - raiz.total
                if fora > 1 << 30:
                    nota.append(f"{formatar_tamanho(fora)} do disco não puderam ser medidos (pontos de "
                                "restauração, arquivos do sistema e de outras contas).")
            except OSError:
                pass
        self.lbl_nota.configure(text="  ".join(nota))

    # ------------------------------------------------------------ navegar
    def _mostrar(self, caminho):
        pasta = self.mapa.pasta(caminho) if self.mapa else None
        if not pasta:
            return
        self.atual = pasta.caminho
        self.lbl_caminho.configure(text=pasta.caminho, text_color=t.TEXTO)
        self.lbl_total.configure(text=f"{formatar_tamanho(pasta.total)} nesta pasta")
        for w in self.lista.winfo_children():
            w.destroy()
        itens = list(pasta.filhas[:MAX_LINHAS])
        if pasta.soltos:
            itens.append(("__soltos__", pasta.soltos))
        if pasta.pequenas:
            itens.append(("__pequenas__", pasta.pequenas))
        itens.sort(key=lambda x: x[1], reverse=True)
        total = pasta.total or 1
        for caminho_filho, tamanho in itens:
            self._linha(caminho_filho, tamanho, total)
        no_raiz = os.path.normcase(os.path.normpath(pasta.caminho)) == os.path.normcase(
            os.path.normpath(self.mapa.raiz))
        self.btn_subir.configure(state="disabled" if no_raiz else "normal")

    def _linha(self, caminho, tamanho, total):
        especial = caminho.startswith("__")
        nome = {"__soltos__": "arquivos soltos nesta pasta",
                "__pequenas__": "pastas pequenas (menos de 1 MB cada)"}.get(caminho, os.path.basename(caminho))
        entra = not especial and self.mapa.pasta(caminho) is not None
        f = ctk.CTkFrame(self.lista, fg_color="transparent", cursor="hand2" if entra else "")
        f.pack(fill="x", pady=1)
        f.grid_columnconfigure(1, weight=1)
        t.icone(f, "pasta" if not especial else "", 14, t.ACENTO if entra else t.FRACO).grid(
            row=0, column=0, rowspan=2, padx=(10, 10))
        t.rotulo(f, nome, "corpo", 13, t.TEXTO if not especial else t.SUAVE).grid(row=0, column=1, sticky="w",
                                                                                pady=(6, 0))
        explicacao = "" if especial else espaco.explicar(caminho)
        fracao = tamanho / total
        b = t.barra(f, fracao, altura=3, largura=10)
        b.grid(row=1, column=1, sticky="ew", pady=(3, 6), padx=(0, 20))
        t.rotulo(f, formatar_tamanho(tamanho), "numero", 14, anchor="e", width=90).grid(row=0, column=2, sticky="e")
        t.rotulo(f, f"{fracao * 100:.0f}%", "numero", 11, t.FRACO, anchor="e", width=90).grid(
            row=1, column=2, sticky="e")
        if explicacao:
            t.rotulo(f, explicacao, "corpo", 11, t.ACENTO, wraplength=520).grid(row=2, column=1, sticky="w",
                                                                              pady=(0, 6))
        if entra:
            t.ao_clicar(f, lambda c=caminho: self._mostrar(c))

    def _subir(self):
        if self.atual and self.mapa:
            pai = os.path.dirname(self.atual.rstrip("\\/"))
            if pai and self.mapa.pasta(pai):
                self._mostrar(pai)

    def _abrir_atual(self):
        if self.atual:
            self.s.abrir_no_explorador(self.atual)

    def _mostrar_maiores(self):
        for w in self.maiores.winfo_children():
            w.destroy()
        for tamanho, caminho in self.mapa.maiores[:30]:
            f = ctk.CTkFrame(self.maiores, fg_color="transparent")
            f.pack(fill="x", pady=2)
            f.grid_columnconfigure(0, weight=1)
            nome = os.path.basename(caminho)
            t.rotulo(f, nome if len(nome) < 42 else nome[:39] + "...", "corpo", 12).grid(row=0, column=0, sticky="w",
                                                                                     padx=(10, 6))
            pasta = os.path.dirname(caminho)
            t.rotulo(f, pasta if len(pasta) < 52 else "..." + pasta[-49:], "corpo", 10, t.FRACO).grid(
                row=1, column=0, sticky="w", padx=(10, 6))
            t.rotulo(f, formatar_tamanho(tamanho), "numero", 13, anchor="e").grid(row=0, column=1, sticky="e")
            t.botao(f, "mostrar", lambda c=caminho: self.s.abrir_no_explorador(c, selecionar=True),
                    "fantasma", altura=22, largura=60).grid(row=1, column=1, sticky="e")
            explicacao = espaco.explicar(caminho)
            if explicacao:
                t.rotulo(f, explicacao, "corpo", 10, t.ACENTO, wraplength=300).grid(row=2, column=0, columnspan=2,
                                                                                  sticky="w", padx=(10, 6))
