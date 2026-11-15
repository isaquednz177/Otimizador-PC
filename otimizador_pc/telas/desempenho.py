# -*- coding: utf-8 -*-
"""Desempenho: o que está gastando memória e processador agora."""

import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME, info, inicializacao as ini
from otimizador_pc import tema as t
from otimizador_pc.processos import Monitor, exe_do_comando
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

LINHAS = 24


class Desempenho(Pagina):
    titulo = "Desempenho"
    subtitulo = ("O que está gastando memória e processador agora, somando todos os processos de cada "
                 "programa. Atualiza a cada 3 segundos.")

    def montar(self):
        self.monitor = Monitor()
        self._lendo = False
        self._timer = None
        self.abre_com_windows = set()

        resumo = t.cartao(self.corpo)
        resumo.pack(fill="x")
        resumo.grid_columnconfigure((0, 1), weight=1, uniform="r")
        self.mem = self._medidor(resumo, 0, "Memória em uso")
        self.cpu = self._medidor(resumo, 1, "Processador")

        lista = t.cartao(self.corpo)
        lista.pack(fill="both", expand=True, pady=(14, 0))
        cab = ctk.CTkFrame(lista, fg_color="transparent")
        cab.pack(fill="x", padx=18, pady=(12, 4))
        cab.grid_columnconfigure(0, weight=1)
        # mesmas larguras das linhas: rótulo de 90 (memória), 70 + 8 (cpu), botão de 84 + 12
        for col, (texto, larg) in enumerate((("Programa", 0), ("Memória", 90), ("CPU", 70), ("", 84))):
            r = t.rotulo(cab, texto, "titulo", 11, t.FRACO, anchor="w" if col == 0 else "e", width=larg or 0)
            r.grid(row=0, column=col, sticky="w" if col == 0 else "e",
                   padx=(10, 8) if col == 0 else ((8, 8) if col == 2 else (4, 8) if col == 3 else 0))
        t.separador(lista).pack(fill="x", padx=18)
        self.area = t.rolavel(lista)
        self.area.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.linhas = [self._linha() for _ in range(LINHAS)]
        self.lbl_rodape = t.rotulo(lista, "", "corpo", 11, t.FRACO)
        self.lbl_rodape.pack(anchor="w", padx=18, pady=(0, 10))

    def _medidor(self, pai, coluna, nome):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.grid(row=0, column=coluna, sticky="ew", padx=18, pady=14)
        t.rotulo(f, nome, "titulo", 11, t.SUAVE).pack(anchor="w")
        linha = ctk.CTkFrame(f, fg_color="transparent")
        linha.pack(fill="x")
        valor = t.rotulo(linha, "—", "numero", 30)
        valor.pack(side="left")
        detalhe = t.rotulo(linha, "", "corpo", 12, t.SUAVE)
        detalhe.pack(side="left", padx=12, pady=(10, 0))
        b = t.barra(f, 0, largura=10)
        b.pack(fill="x", pady=(6, 0))
        return {"valor": valor, "detalhe": detalhe, "barra": b}

    def _linha(self):
        f = ctk.CTkFrame(self.area, fg_color="transparent", height=50)
        f.grid_columnconfigure(0, weight=1)
        nome = t.rotulo(f, "", "corpo_forte", 13)
        nome.grid(row=0, column=0, sticky="w", padx=(10, 8), pady=(6, 0))
        sub = t.rotulo(f, "", "corpo", 11, t.FRACO)
        sub.grid(row=1, column=0, sticky="w", padx=(10, 8), pady=(0, 6))
        mem = t.rotulo(f, "", "numero", 14, width=90, anchor="e")
        mem.grid(row=0, column=1, sticky="e")
        b = t.barra(f, 0, altura=3, largura=90)
        b.grid(row=1, column=1, sticky="e", padx=(0, 0))
        cpu = t.rotulo(f, "", "numero", 14, t.SUAVE, width=70, anchor="e")
        cpu.grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 8))
        fechar = t.botao(f, "fechar", None, "secundario", largura=84, altura=28)
        fechar.grid(row=0, column=3, rowspan=2, padx=(4, 8))
        return {"quadro": f, "nome": nome, "sub": sub, "mem": mem, "barra": b, "cpu": cpu, "fechar": fechar}

    # ------------------------------------------------------------ atualização
    def ao_mostrar(self):
        super().ao_mostrar()
        self.j.em_segundo_plano(self._ler_inicializacao, self._guardar_inicializacao)
        self._ciclo()

    def ao_esconder(self):
        super().ao_esconder()
        if self._timer:
            self.after_cancel(self._timer)
            self._timer = None

    def _ler_inicializacao(self):
        return {exe_do_comando(i.comando) for i in ini.listar(self.s) if i.ativo} - {""}

    def _guardar_inicializacao(self, exes):
        self.abre_com_windows = exes

    def _ciclo(self):
        if not self.visivel:
            return
        if not self._lendo:
            self._lendo = True
            threading.Thread(target=self._ler, daemon=True).start()
        self._timer = self.after(3000, self._ciclo)

    def _ler(self):
        try:
            grupos = self.monitor.ler(mostrar=LINHAS)
            dados = info.resumo()
            self.j.no_principal(self._mostrar, grupos, dados)
        except Exception as e:
            self.log(f"[erro] lendo processos: {e}")
        finally:
            self._lendo = False

    def _mostrar(self, grupos, d):
        if d["ram_total"]:
            fr = d["ram_usada"] / d["ram_total"]
            self.mem["valor"].configure(text=f"{d['ram_pct']}%")
            self.mem["detalhe"].configure(text=f"{formatar_tamanho(d['ram_usada'])} de {formatar_tamanho(d['ram_total'])}")
            self.mem["barra"].configure(progress_color=t.cor_do_uso(fr))
            self.mem["barra"].set(fr)
        cpu_total = sum(g.cpu or 0 for g in grupos)
        tem_cpu = any(g.cpu is not None for g in grupos)
        self.cpu["valor"].configure(text=f"{min(cpu_total, 100):.0f}%" if tem_cpu else "—")
        self.cpu["detalhe"].configure(text=f"{self.monitor.nucleos} núcleos lógicos")
        self.cpu["barra"].configure(progress_color=t.cor_do_uso(cpu_total / 100))
        self.cpu["barra"].set(min(cpu_total, 100) / 100)

        maior = max((g.memoria for g in grupos[:LINHAS]), default=1) or 1
        quantas = min(len(grupos), LINHAS)
        if quantas != getattr(self, "_quantas", -1):  # repõe na ordem certa
            for linha in self.linhas:
                linha["quadro"].pack_forget()
            for linha in self.linhas[:quantas]:
                linha["quadro"].pack(fill="x", pady=1)
            self._quantas = quantas
        for i, linha in enumerate(self.linhas[:quantas]):
            g = grupos[i]
            partes = [g.exe]
            if g.qtd > 1:
                partes.append(f"{g.qtd} processos")
            if g.exe in self.abre_com_windows:
                partes.append("abre com o Windows")
            if g.servico:
                partes.append("serviço ou parte do Windows")
            linha["nome"].configure(text=g.nome if len(g.nome) < 60 else g.nome[:57] + "...")
            linha["sub"].configure(text="  ·  ".join(partes),
                                   text_color=t.ACENTO if g.exe in self.abre_com_windows else t.FRACO)
            linha["mem"].configure(text=formatar_tamanho(g.memoria))
            linha["barra"].set(g.memoria / maior)
            linha["cpu"].configure(text="—" if g.cpu is None else f"{g.cpu:.1f}%".replace(".", ","),
                                   text_color=t.ACENTO if (g.cpu or 0) >= 15 else t.SUAVE)
            # o botão nunca sai da grade (senão as colunas da linha andam); só fica invisível
            if g.pode_fechar:
                linha["fechar"].configure(state="normal", text="fechar", fg_color=t.PAINEL2, border_width=1,
                                          command=lambda grupo=g: self._fechar(grupo))
            else:
                linha["fechar"].configure(state="disabled", text="", fg_color="transparent", border_width=0,
                                          command=None)
        total = sum(g.memoria for g in grupos)
        self.lbl_rodape.configure(text=f"{len(grupos)} programas abertos somam {formatar_tamanho(total)} de memória "
                                       "própria. O resto da memória em uso é do próprio Windows e de cache.")

    # ------------------------------------------------------------ fechar
    def _fechar(self, g):
        if not messagebox.askyesno(APP_NOME, f"Fechar {g.nome} ({g.qtd} processo(s))?\n\n"
                                             "É como clicar no X: o que não estiver salvo nele pode pedir para salvar."):
            return
        self.j.trabalhar(lambda ctl: self._tarefa_fechar(g), f"fechando {g.nome}", cancelavel=False)

    def _tarefa_fechar(self, g):
        self.s.encerrar(g.pids)
        time.sleep(2.5)
        # um Monitor só para conferir (o da tela é lido por outra thread)
        vivos = set(g.pids) & {pid for grupo in Monitor().ler(mostrar=0) for pid in grupo.pids}
        if not vivos:
            self.log(f"{g.nome} fechado.")
            return
        if self.j.perguntar(f"{g.nome} não fechou sozinho ({len(vivos)} processo(s) continuam).\n\n"
                            "Forçar o fechamento? O que não estiver salvo nele se perde.", aviso=True):
            ok, msg = self.s.encerrar(sorted(vivos), forcar=True)
            self.log(f"{g.nome}: {'fechado à força' if ok else 'não fechou: ' + msg}")
        else:
            self.log(f"{g.nome} continua aberto.")
