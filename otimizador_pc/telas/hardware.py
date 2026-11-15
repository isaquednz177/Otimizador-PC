# -*- coding: utf-8 -*-
"""Hardware e atualizações: memória, discos, vídeo, bateria e Windows. Só mostra."""

import os

import customtkinter as ctk

from otimizador_pc import hardware as hw
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho

GB = 1 << 30
SAUDE = {"Healthy": ("saudável", t.OK), "Warning": ("com aviso", t.ACENTO), "Unhealthy": ("com problema", t.PERIGO)}


class Hardware(Pagina):
    titulo = "Peças do PC"
    subtitulo = ("Memória, discos, vídeo, bateria e atualizações. O que aqui faria o PC mais rápido "
                 "aparece em âmbar.")

    def montar(self):
        self.botao_topo("abrir o Windows Update", lambda: self._abrir("ms-settings:windowsupdate"), largura=200)
        self.botao_topo("ler de novo", lambda: self.j.obter_hardware(self._mostrar, novo=True))
        self.area = t.rolavel(self.corpo)
        self.area.pack(fill="both", expand=True)
        self.area.grid_columnconfigure((0, 1), weight=1, uniform="hw")
        self._mostrou = False
        t.rotulo(self.area, "lendo o hardware (leva uns 20 segundos)...", "corpo", 13, t.FRACO).grid(
            row=0, column=0, sticky="w", padx=4, pady=8)

    def ao_mostrar(self):
        super().ao_mostrar()
        if not self._mostrou:
            self.j.obter_hardware(self._mostrar)

    def _escala(self):
        try:
            return ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            return 1.0

    def _abrir(self, alvo):
        try:
            os.startfile(alvo)
        except OSError:
            pass

    # ------------------------------------------------------------ peças
    def _cartao(self, linha, coluna, titulo, colspan=1):
        c = t.cartao(self.area)
        c.grid(row=linha, column=coluna, columnspan=colspan, sticky="nsew",
               padx=(0 if coluna == 0 else 7, 0 if coluna + colspan >= 2 else 7), pady=(0, 14))
        t.rotulo(c, titulo, "titulo", 11, t.SUAVE).pack(anchor="w", padx=18, pady=(14, 0))
        return c

    def _grande(self, pai, texto, detalhe="", cor=None, tamanho=28):
        t.rotulo(pai, texto, "numero", tamanho, cor or t.TEXTO, wraplength=460).pack(anchor="w", padx=18)
        if detalhe:
            t.rotulo(pai, detalhe, "corpo", 12, t.SUAVE, wraplength=460).pack(anchor="w", padx=18)

    def _par(self, pai, rotulo, valor, cor=None):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=1)
        t.rotulo(f, rotulo, "corpo", 12, t.FRACO).pack(side="left")
        t.rotulo(f, valor, "corpo", 12, cor or t.TEXTO, anchor="e").pack(side="right")

    def _nota(self, pai, texto, cor=None, botao=None):
        f = ctk.CTkFrame(pai, fg_color=t.ACENTO_FUNDO if cor == t.ACENTO else "transparent", corner_radius=t.RAIO)
        f.pack(fill="x", padx=12, pady=(10, 0))
        rotulo = t.rotulo(f, texto, "corpo", 12, cor or t.SUAVE, wraplength=360)
        rotulo.pack(anchor="w", fill="x", padx=8, pady=6)
        # a quebra de linha acompanha a largura do cartão (senão o texto é cortado à direita)
        f.bind("<Configure>", lambda e, r=rotulo: r.configure(wraplength=max(200, int(e.width / self._escala()) - 24)))
        if botao:
            t.botao(f, botao[0], botao[1], "secundario", altura=28).pack(anchor="w", padx=8, pady=(0, 8))

    # ------------------------------------------------------------ desenho
    def _mostrar(self, r):
        self._mostrou = True
        for w in self.area.winfo_children():
            w.destroy()
        if r is None:
            t.rotulo(self.area, "Não deu para ler o hardware.", "corpo", 13, t.FRACO).grid(row=0, column=0, sticky="w")
            return
        recs = {texto: link for _, texto, link in hw.recomendacoes(r)}

        # memória
        m = r.memoria
        c = self._cartao(0, 0, "Memória (RAM)")
        self._grande(c, formatar_tamanho(m.total) if m.total else "—",
                     " · ".join(x for x in (m.tipo, f"{len(m.pentes)} pente(s)",
                                            f"{m.encaixes} encaixe(s)" if m.encaixes else "",
                                            f"aceita até {m.maximo // GB} GB" if m.maximo else "") if x))
        for p in m.pentes:
            self._par(c, p["local"] or "pente", f"{formatar_tamanho(p['tamanho'])} · {p['velocidade']} MHz"
                      + (f" · {p['fabricante']}" if p["fabricante"] else ""))
        for texto in recs:
            if "pente" in texto:
                self._nota(c, texto, t.ACENTO)
        ctk.CTkFrame(c, height=12, width=10, fg_color="transparent").pack(pady=(0, 3))  # sem cobrir a borda

        # vídeo e processador
        c = self._cartao(0, 1, "Processador e placa de vídeo")
        self._grande(c, r.cpu.replace("(R)", "").replace("(TM)", "") or "—", r.nucleos, tamanho=20)
        for v in r.videos:
            idade = f"{v['dias'] // 30} meses" if v["dias"] is not None else "?"
            velho = v["dias"] is not None and v["dias"] > 180
            self._par(c, v["nome"], f"driver de {v['data']:%m/%Y} ({idade})" if v["data"] else "driver sem data",
                      t.ACENTO if velho else None)
            if velho and v["site"]:
                self._nota(c, f"Driver {v['fabricante']} com mais de 6 meses: o novo costuma dar mais FPS.",
                           t.ACENTO, ("baixar no site da " + v["fabricante"], lambda u=v["site"]: self._abrir(u)))
        ctk.CTkFrame(c, height=12, width=10, fg_color="transparent").pack(pady=(0, 3))  # sem cobrir a borda

        # discos
        c = self._cartao(1, 0, "Disco (onde ficam os arquivos)")
        for d in r.discos:
            texto, cor = SAUDE.get(d["saude"], (d["saude"] or "?", t.SUAVE))
            t.rotulo(c, d["nome"], "corpo_forte", 13).pack(anchor="w", padx=18, pady=(8, 0))
            self._par(c, "tipo", f"{d['tipo']} · {d['barramento']} · {formatar_tamanho(d['tamanho'])}")
            self._par(c, "saúde", texto, cor)
            if d["desgaste"] is not None:
                self._par(c, "desgaste", f"{d['desgaste']}%", t.ACENTO if int(d["desgaste"]) >= 80 else None)
            if d["temperatura"]:
                self._par(c, "temperatura", f"{d['temperatura']} °C", t.ACENTO if int(d["temperatura"]) >= 70 else None)
            if d["horas"]:
                self._par(c, "horas ligado", f"{int(d['horas']):,}".replace(",", "."))
        if r.discos and all(d["desgaste"] is None for d in r.discos):
            self._nota(c, "Desgaste e temperatura só aparecem com permissão de Administrador.")
        ctk.CTkFrame(c, height=12, width=10, fg_color="transparent").pack(pady=(0, 3))  # sem cobrir a borda

        # bateria e Windows
        c = self._cartao(1, 1, "Bateria e Windows")
        if r.bateria:
            b = r.bateria
            self._par(c, "bateria", f"{b['saude'] * 100:.0f}% da carga de fábrica",
                      t.ACENTO if b["saude"] < 0.7 else t.OK)
            self._par(c, "capacidade", f"{b['hoje'] / 1000:.1f} de {b['fabrica'] / 1000:.1f} Wh".replace(".", ","))
            if b["ciclos"] is not None:
                self._par(c, "ciclos de carga", str(b["ciclos"]))
        else:
            self._par(c, "bateria", "não encontrada (computador de mesa?)")
        if r.ultima_atualizacao:
            self._par(c, "última atualização", f"{r.ultima_atualizacao:%d/%m/%Y} ({r.kb})")
        self._par(c, "reinício pendente", "sim" if r.reinicio_pendente else "não",
                  t.ACENTO if r.reinicio_pendente else None)
        if r.modelo:
            self._par(c, "modelo", r.modelo)
        ctk.CTkFrame(c, height=12, width=10, fg_color="transparent").pack(pady=(0, 3))  # sem cobrir a borda
