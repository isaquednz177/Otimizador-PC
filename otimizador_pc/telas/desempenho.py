# -*- coding: utf-8 -*-
"""
Desempenho: memória e processador agora e nos últimos 3 minutos, quem está usando a
memória, e a lista dos programas que mais pesam.
"""

import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME, info, inicializacao as ini
from otimizador_pc import explicar as ex
from otimizador_pc import tema as t
from otimizador_pc.processos import Monitor, exe_do_comando
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

LINHAS = 24


def _pct(v):
    return f"{v:.0f}%" if v is not None else "—"


class Desempenho(Pagina):
    titulo = "Desempenho"
    subtitulo = ("Mostra se o PC está pesado agora e por quê. As duas coisas que mais deixam o PC lento são "
                 "a memória cheia e o processador sobrecarregado; embaixo, os programas que mais gastam.")

    def montar(self):
        self.monitor = Monitor()
        self._lendo = False
        self._timer = None
        self._quantas = -1
        self.abre_com_windows = set()
        self.grupos = []

        c = self.corpo
        c.grid_columnconfigure((0, 1), weight=1, uniform="medidores")
        c.grid_rowconfigure(2, weight=1)
        self.mem = self._medidor(0, "Memória (RAM)", ex.GLOSSARIO_DICT["Memória (RAM)"])
        self.cpu = self._medidor(1, "Processador (CPU)", ex.GLOSSARIO_DICT["Processador (CPU)"])

        quem = t.cartao(c)
        quem.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        cab = ctk.CTkFrame(quem, fg_color="transparent")
        cab.pack(fill="x", padx=20, pady=(12, 6))
        t.rotulo(cab, "Quem está usando a memória", "titulo", 13, t.TEXTO).pack(side="left")
        t.ajuda(cab, "Cada cor é um programa aberto. \"Windows, drivers e cache\" é o que o próprio Windows usa para "
                     "funcionar e para abrir as coisas mais rápido (ele devolve essa parte quando outro programa "
                     "precisa). \"Livre\" é o que sobra.").pack(side="left", padx=8)
        self.lbl_quem = t.rotulo(cab, "", "corpo", 11, t.FRACO)
        self.lbl_quem.pack(side="right")
        self.composicao = t.Composicao(quem, altura=60)
        self.composicao.pack(fill="x", padx=20, pady=(0, 12))

        lista = t.cartao(c)
        lista.grid(row=2, column=0, columnspan=2, sticky="nsew")
        cab = ctk.CTkFrame(lista, fg_color="transparent")
        cab.pack(fill="x", padx=20, pady=(12, 2))
        cab.grid_columnconfigure(1, weight=1)
        for col, (texto, larg, lado) in enumerate((("#", 26, "w"), ("Programa", 0, "w"), ("Memória", 150, "e"),
                                                     ("Processador", 120, "e"), ("", 92, "e"))):
            cab.grid_columnconfigure(col, minsize=int(larg * t.escala(cab)))
            t.rotulo(cab, texto, "titulo", 11, t.FRACO, anchor=lado).grid(row=0, column=col, sticky=lado, padx=4)
        t.separador(lista).pack(fill="x", padx=20)
        self.area = t.rolavel(lista)
        self.area.pack(fill="both", expand=True, padx=10, pady=(2, 4))
        self.linhas = [self._linha(i) for i in range(LINHAS)]
        self.lbl_rodape = t.rotulo(lista, "", "corpo", 11, t.FRACO)
        self.lbl_rodape.pack(anchor="w", padx=20, pady=(0, 12))

    # ------------------------------------------------------------ peças
    def _medidor(self, coluna, nome, explicacao):
        card = t.cartao(self.corpo)
        card.grid(row=0, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 6, 6 if coluna == 0 else 0),
                  pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        anel = t.Anel(card, tamanho=96)
        anel.grid(row=0, column=0, rowspan=4, padx=(18, 14), pady=(14, 4), sticky="n")
        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.grid(row=0, column=1, sticky="w", pady=(16, 0))
        t.rotulo(topo, nome, "titulo", 14).pack(side="left")
        t.ajuda(topo, explicacao).pack(side="left", padx=8)
        # 1: o veredito em palavras, 2: o detalhe, 3: os últimos 3 minutos
        linhas = [t.rotulo(card, "", "corpo_forte", 12), t.texto_longo(card, "", "corpo", 12, t.SUAVE),
                  t.rotulo(card, "", "corpo", 11, t.FRACO)]
        for i, r in enumerate(linhas, start=1):
            r.grid(row=i, column=1, sticky="ew", padx=(0, 22))
        grafico = t.Grafico(card, altura=50)
        # longe das volutas dos cantos de baixo
        grafico.grid(row=4, column=0, columnspan=2, sticky="ew", padx=(18, 28), pady=(4, 22))
        return {"anel": anel, "linhas": linhas, "grafico": grafico}

    def _linha(self, i):
        f = ctk.CTkFrame(self.area, fg_color="transparent")
        e = t.escala(f)
        f.grid_columnconfigure(1, weight=1)
        for col, larg in ((0, 26), (2, 150), (3, 120), (4, 92)):
            f.grid_columnconfigure(col, minsize=int(larg * e))
        t.rotulo(f, str(i + 1), "numero", 12, t.FRACO).grid(row=0, column=0, rowspan=2, sticky="w", padx=(10, 0))
        nome = t.rotulo(f, "", "corpo_forte", 13)
        nome.grid(row=0, column=1, sticky="w", pady=(7, 0))
        sub = t.rotulo(f, "", "corpo", 11, t.FRACO)
        sub.grid(row=1, column=1, sticky="w", pady=(0, 7))
        mem = t.rotulo(f, "", "numero", 13, anchor="e")
        mem.grid(row=0, column=2, sticky="e", padx=4, pady=(7, 0))
        bmem = t.barra(f, 0, altura=4, largura=130)
        bmem.grid(row=1, column=2, sticky="e", padx=4)
        cpu = t.rotulo(f, "", "numero", 13, t.SUAVE, anchor="e")
        cpu.grid(row=0, column=3, sticky="e", padx=4, pady=(7, 0))
        bcpu = t.barra(f, 0, altura=4, largura=90)
        bcpu.grid(row=1, column=3, sticky="e", padx=4)
        fechar = t.botao(f, "fechar", None, "secundario", largura=80, altura=28)
        fechar.grid(row=0, column=4, rowspan=2, sticky="e", padx=(4, 6))
        t.separador(f).grid(row=2, column=0, columnspan=5, sticky="ew")
        return {"quadro": f, "nome": nome, "sub": sub, "mem": mem, "bmem": bmem, "cpu": cpu, "bcpu": bcpu,
                "fechar": fechar}

    # ------------------------------------------------------------ medidores (a cada 2 s, pela janela)
    def ao_amostrar(self, d):
        h = self.j.historico
        if d.get("ram_total"):
            fr = d["ram_usada"] / d["ram_total"]
            nivel, curto, frase = ex.memoria(d["ram_pct"])
            self.mem["anel"].definir(fr, f"{d['ram_pct']}%", curto)
            pico, media = h.pico_e_media(h.memoria)
            l1, l2, l3 = self.mem["linhas"]
            l1.configure(text=f"{curto.capitalize()}: usando {formatar_tamanho(d['ram_usada'])} de "
                              f"{formatar_tamanho(d['ram_total'])}", text_color=t.COR_NIVEL[nivel])
            l2.configure(text=frase)
            l3.configure(text=f"Nos últimos 3 minutos: no máximo {_pct(pico)}, em média {_pct(media)}.")
            self.mem["grafico"].definir(h.memoria)
        cpu = d.get("cpu")
        pico, media = h.pico_e_media(h.processador)
        nivel, curto, frase = ex.processador(media)
        if cpu is not None:
            self.cpu["anel"].definir(cpu / 100, f"{cpu:.0f}%", curto)
        l1, l2, l3 = self.cpu["linhas"]
        topo = max((g for g in self.grupos if g.cpu is not None), key=lambda g: g.cpu, default=None)
        quem = f" (quem mais usa: {topo.nome})" if topo and topo.cpu >= 5 else ""
        l1.configure(text=f"{curto.capitalize()}{quem}", text_color=t.COR_NIVEL[nivel])
        l2.configure(text=frase)
        l3.configure(text=f"Nos últimos 3 minutos: no máximo {_pct(pico)}, em média {_pct(media)}.")
        self.cpu["grafico"].definir(h.processador)

    # ------------------------------------------------------------ lista (a cada 3 s)
    def ao_mostrar(self):
        super().ao_mostrar()
        self.ao_amostrar(self.j.amostra)
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
            self.j.no_principal(self._mostrar, grupos, info.resumo())
        except Exception as e:
            self.log(f"[erro] lendo processos: {e}")
        finally:
            self._lendo = False

    def _mostrar(self, grupos, d):
        self.grupos = grupos
        if d["ram_total"]:
            partes = info.composicao_da_memoria(d["ram_total"], d["ram_usada"],
                                                [(g.nome, g.memoria) for g in grupos])
            self.composicao.definir(partes, formatar_tamanho)
            windows = next((v for n, v, tp in partes if tp == "windows"), 0)
            self.lbl_quem.configure(text=f"{len(grupos)} programas abertos  ·  {formatar_tamanho(windows)} do próprio Windows")

        maior = max((g.memoria for g in grupos[:LINHAS]), default=1) or 1
        quantas = min(len(grupos), LINHAS)
        if quantas != self._quantas:  # repõe na ordem certa
            for linha in self.linhas:
                linha["quadro"].pack_forget()
            for linha in self.linhas[:quantas]:
                linha["quadro"].pack(fill="x")
            self._quantas = quantas
        for i, linha in enumerate(self.linhas[:quantas]):
            g = grupos[i]
            partes = [g.exe]
            if g.qtd > 1:
                partes.append(f"aberto em {g.qtd} partes")
            if g.exe in self.abre_com_windows:
                partes.append("abre com o Windows")
            if g.servico:
                partes.append("parte do Windows")
            linha["nome"].configure(text=g.nome if len(g.nome) < 56 else g.nome[:53] + "...")
            linha["sub"].configure(text="  ·  ".join(partes),
                                   text_color=t.ACENTO if g.exe in self.abre_com_windows else t.FRACO)
            linha["mem"].configure(text=formatar_tamanho(g.memoria))
            linha["bmem"].configure(progress_color=t.ACENTO if i < 3 else t.NORMAL)
            linha["bmem"].set(g.memoria / maior)
            cpu = g.cpu or 0
            linha["cpu"].configure(text="—" if g.cpu is None else f"{cpu:.1f}%".replace(".", ","),
                                   text_color=t.ACENTO if cpu >= 15 else t.SUAVE)
            linha["bcpu"].configure(progress_color=t.cor_do_uso(cpu / 100))
            linha["bcpu"].set(min(cpu, 100) / 100)
            # o botão nunca sai da grade (senão as colunas andam); só fica invisível
            if g.pode_fechar:
                linha["fechar"].configure(state="normal", text="fechar", fg_color=t.PAINEL2, border_width=1,
                                          command=lambda grupo=g: self._fechar(grupo))
            else:
                linha["fechar"].configure(state="disabled", text="", fg_color="transparent", border_width=0,
                                          command=None)
        total = sum(g.memoria for g in grupos)
        self.lbl_rodape.configure(text=f"Os programas abertos somam {formatar_tamanho(total)}. Memória de cada um = "
                                       "o mesmo número do Gerenciador de Tarefas.")

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
