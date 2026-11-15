# -*- coding: utf-8 -*-
"""Tempo para ligar: o histórico do próprio Windows, para ver se os ajustes ajudaram."""

import tkinter as tk

import customtkinter as ctk

from otimizador_pc import boot
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina


class Medicoes(Pagina):
    titulo = "Tempo para ligar"
    subtitulo = ("Quanto o PC levou para ficar pronto em cada vez que ligou, pelo registro do próprio "
                 "Windows. A linha tracejada marca quando ajustes foram aplicados.")

    def montar(self):
        self.botao_topo("atualizar", self.atualizar)
        self.lista = []
        self.marcos = []

        numeros = t.cartao(self.corpo)
        numeros.pack(fill="x")
        self.num = {}
        for i, (chave, nome) in enumerate((("ultimo", "Última vez"), ("media", "Média"),
                                            ("melhor", "Mais rápido"), ("comparacao", "Antes e depois dos ajustes"))):
            numeros.grid_columnconfigure(i, weight=2 if chave == "comparacao" else 1)
            f = ctk.CTkFrame(numeros, fg_color="transparent")
            f.grid(row=0, column=i, sticky="w", padx=18, pady=14)
            t.rotulo(f, nome, "titulo", 11, t.SUAVE).pack(anchor="w")
            v = t.rotulo(f, "—", "numero", 26)
            v.pack(anchor="w")
            d = t.rotulo(f, "", "corpo", 11, t.FRACO)
            d.pack(anchor="w")
            self.num[chave] = (v, d)

        grafico = t.cartao(self.corpo)
        grafico.pack(fill="both", expand=True, pady=(14, 0))
        self.canvas = tk.Canvas(grafico, bg=t.PAINEL, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda e: self._desenhar())
        self.lbl_nota = t.rotulo(self.corpo, "", "corpo", 11, t.FRACO, wraplength=900)
        self.lbl_nota.pack(anchor="w", pady=(8, 0))
        self._carregado = False

    def ao_mostrar(self):
        super().ao_mostrar()
        if not self._carregado:
            self.atualizar()

    def atualizar(self):
        self._carregado = True
        self.j.em_segundo_plano(lambda: boot.ler(self.s, 40), self._mostrar)

    def _mostrar(self, resultado):
        lista, erro = resultado
        self.lista = lista
        self.marcos = boot.datas_dos_ajustes(self.j.backup.dados)
        nota = ("Com a Inicialização Rápida ligada, ligar depois de \"Desligar\" não entra aqui (é uma "
                "hibernação); reiniciar entra. Os números variam com atualizações do Windows e com o que "
                "abre junto: compare médias, não uma vez só.")
        if erro:
            self.num["ultimo"][0].configure(text="—")
            self.num["ultimo"][1].configure(text=erro)
            self.lbl_nota.configure(text=nota)
            self._desenhar()
            return
        seg = [b.total_ms / 1000 for b in lista]
        self.num["ultimo"][0].configure(text=f"{seg[-1]:.0f} s")
        self.num["ultimo"][1].configure(text=lista[-1].quando.strftime("%d/%m %H:%M"))
        self.num["media"][0].configure(text=f"{sum(seg) / len(seg):.0f} s")
        self.num["media"][1].configure(text=f"das últimas {len(seg)} vezes")
        self.num["melhor"][0].configure(text=f"{min(seg):.0f} s")
        self.num["melhor"][1].configure(text=lista[seg.index(min(seg))].quando.strftime("%d/%m"))

        v, d = self.num["comparacao"]
        if self.marcos:
            marco = self.marcos[-1]
            antes, depois, na, nd = boot.comparar(lista, marco)
            if antes and depois:
                diferenca = (depois - antes) / 1000
                v.configure(text=f"{antes / 1000:.0f} s → {depois / 1000:.0f} s",
                            text_color=t.OK if diferenca < 0 else t.ACENTO)
                d.configure(text=f"média antes e depois de {marco:%d/%m} ({na} e {nd} vezes)")
            else:
                v.configure(text="poucos dados", text_color=t.SUAVE)
                d.configure(text=f"precisa de 2 vezes antes e 2 depois de {marco:%d/%m} (tem {na} e {nd})")
        else:
            v.configure(text="—", text_color=t.SUAVE)
            d.configure(text="nenhum ajuste aplicado ainda")
        self.lbl_nota.configure(text=nota)
        self._desenhar()

    # ------------------------------------------------------------ gráfico
    def _desenhar(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:
            return
        if not self.lista:
            c.create_text(w / 2, h / 2, text="sem dados para mostrar", fill=t.FRACO, font=(t.fonte("corpo", 12).cget("family"), 12))
            return
        esq, dir_, topo, base = 46, 12, 18, 34
        largura, altura = w - esq - dir_, h - topo - base
        seg = [b.total_ms / 1000 for b in self.lista]
        maximo = max(seg) * 1.15 or 1
        familia = t.fonte("numero", 10).cget("family")

        # linhas de grade
        passo = 10 if maximo <= 80 else 30 if maximo <= 240 else 60
        valor = 0
        while valor <= maximo:
            y = topo + altura - valor / maximo * altura
            c.create_line(esq, y, w - dir_, y, fill=t.LINHA)
            c.create_text(esq - 8, y, text=f"{valor:.0f} s", anchor="e", fill=t.FRACO, font=(familia, 9))
            valor += passo

        n = len(seg)
        vao = largura / n
        barra = max(3, min(28, vao * 0.62))
        media = sum(seg) / n
        for i, (b, s) in enumerate(zip(self.lista, seg)):
            x = esq + vao * i + vao / 2
            y = topo + altura - s / maximo * altura
            cor = t.ACENTO if i == n - 1 else t.BARRA
            c.create_rectangle(x - barra / 2, y, x + barra / 2, topo + altura, fill=cor, width=0)
            if n <= 16 or i % max(1, n // 10) == 0 or i == n - 1:
                c.create_text(x, topo + altura + 14, text=b.quando.strftime("%d/%m"), fill=t.FRACO, font=(familia, 9))

        ym = topo + altura - media / maximo * altura
        c.create_line(esq, ym, w - dir_, ym, fill=t.SUAVE, dash=(2, 3))
        c.create_text(w - dir_, ym - 8, text=f"média {media:.0f} s", anchor="e", fill=t.SUAVE, font=(familia, 9))

        for marco in self.marcos:
            antes = [i for i, b in enumerate(self.lista) if b.quando < marco]
            if not antes or len(antes) == n:
                continue
            x = esq + vao * (antes[-1] + 1)
            c.create_line(x, topo - 6, x, topo + altura, fill=t.VINHO_CLARO, dash=(4, 3), width=2)
            c.create_text(x + 6, topo, text=f"ajustes {marco:%d/%m}", anchor="w", fill=t.PERIGO, font=(familia, 10))
