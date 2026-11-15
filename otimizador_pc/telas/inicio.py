# -*- coding: utf-8 -*-
"""Início: o estado do PC numa olhada e o que vale a pena fazer agora."""

import os

import customtkinter as ctk

from otimizador_pc import ajustes as aj
from otimizador_pc import boot, hardware, info, inicializacao as ini, limpeza, ponto
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina
from otimizador_pc.util import formatar_tamanho


class Inicio(Pagina):
    titulo = "Início"
    subtitulo = "Como o PC está agora e o que vale a pena fazer."

    def montar(self):
        self.botao_topo("atualizar", self.recarregar)
        grade = ctk.CTkFrame(self.corpo, fg_color="transparent")
        grade.pack(fill="x")
        for c in range(3):
            grade.grid_columnconfigure(c, weight=1, uniform="cartoes")
        self.c = {}
        especificacao = [
            ("memoria", "MEMÓRIA", "ver o que está pesando", "desempenho"),
            ("disco", "DISCO", "ver o que ocupa", "espaco"),
            ("boot", "TEMPO PARA LIGAR", "ver o histórico", "medicoes"),
            ("ajustes", "AJUSTES", "ver os ajustes", "ajustes"),
            ("inicio", "ABREM COM O WINDOWS", "ver a lista", "inicializacao"),
            ("lixeira", "LIXEIRA", "ir para a limpeza", "limpeza"),
        ]
        for i, (chave, nome, link, destino) in enumerate(especificacao):
            self.c[chave] = self._cartao(grade, i // 3, i % 3, nome, link, destino)

        rec = t.cartao(self.corpo)
        rec.pack(fill="both", expand=True, pady=(14, 0))
        cab = ctk.CTkFrame(rec, fg_color="transparent")
        cab.pack(fill="x", padx=18, pady=(14, 6))
        t.rotulo(cab, "RECOMENDAÇÕES", "titulo", 12, t.SUAVE).pack(side="left")
        self.lista_rec = t.rolavel(rec)
        self.lista_rec.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._timer = None

    def _cartao(self, pai, linha, coluna, nome, link, destino):
        c = t.cartao(pai, height=150)
        c.grid(row=linha, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 7, 0 if coluna == 2 else 7),
               pady=(0, 14))
        c.pack_propagate(False)
        t.rotulo(c, nome, "titulo", 11, t.SUAVE).pack(anchor="w", padx=18, pady=(14, 0))
        valor = t.rotulo(c, "—", "numero", 30)
        valor.pack(anchor="w", padx=18, pady=(2, 0))
        detalhe = t.rotulo(c, "", "corpo", 12, t.SUAVE)
        detalhe.pack(anchor="w", padx=18)
        b = t.barra(c, 0, largura=10)
        b.pack(fill="x", padx=18, pady=(8, 0))
        b.pack_forget()
        t.botao(c, link + "  ›", lambda: self.j.ir(destino), "fantasma", altura=24, anchor="w").pack(
            fill="x", padx=10, pady=(0, 8), side="bottom")
        return {"valor": valor, "detalhe": detalhe, "barra": b}

    def _definir(self, chave, valor, detalhe="", fracao=None, cor=None):
        c = self.c[chave]
        c["valor"].configure(text=valor, text_color=cor or t.TEXTO)
        c["detalhe"].configure(text=detalhe)
        if fracao is None:
            c["barra"].pack_forget()
        else:
            c["barra"].configure(progress_color=t.cor_do_uso(fracao))
            c["barra"].set(fracao)
            c["barra"].pack(fill="x", padx=18, pady=(8, 0))

    # ------------------------------------------------------------ dados
    def ao_mostrar(self):
        super().ao_mostrar()
        self.recarregar()
        self._agendar()

    def ao_esconder(self):
        super().ao_esconder()
        if self._timer:
            self.after_cancel(self._timer)
            self._timer = None

    def _agendar(self):
        self._memoria()
        if self.visivel:
            self._timer = self.after(3000, self._agendar)

    def _memoria(self):
        d = info.resumo()
        if d["ram_total"]:
            usado = d["ram_usada"] / d["ram_total"]
            self._definir("memoria", f"{d['ram_pct']}%",
                          f"{formatar_tamanho(d['ram_usada'])} de {formatar_tamanho(d['ram_total'])} em uso",
                          usado)
        if d["disco_total"]:
            usado = 1 - d["disco_livre"] / d["disco_total"]
            self._definir("disco", formatar_tamanho(d["disco_livre"]),
                          f"livres de {formatar_tamanho(d['disco_total'])} no {info.disco_do_sistema()[:2]}", usado)

    def recarregar(self):
        self._memoria()
        self.j.em_segundo_plano(self._coletar, self._mostrar)

    def _coletar(self):
        s, dados = self.s, self.j.backup.dados
        r = {"estados": {a.id: aj.estado_do_ajuste(a, s, dados) for a in aj.AJUSTES}}
        r["lixeira"] = s.lixeira_tamanho()
        r["protecao"] = ponto.protecao_ligada(s)
        programas = ini.listar(s)
        r["programas"] = sum(1 for p in programas if p.ativo)
        r["servicos"] = [x for x in ini.listar_servicos(s, self.j.backup) if x.automatico]
        r["removidos"] = list(dados.get("inicializacao_removida", {}).values())
        r["boot"], r["boot_erro"] = boot.ler(s, 10)
        r["info"] = info.resumo()
        r["downloads"] = limpeza.analisar_item(limpeza.ITENS_POR_ID["downloads_incompletos"], s)
        r["modo_jogo"] = bool(dados.get("modo_jogo", {}).get("ativo"))
        return r

    def _mostrar(self, r):
        estados = r["estados"]
        existentes = [e for e in estados.values() if e != "indisponivel"]
        aplicados = sum(1 for e in existentes if e == "aplicado")
        parciais = sum(1 for e in existentes if e == "parcial")
        self._definir("ajustes", f"{aplicados} de {len(existentes)}",
                      "aplicados" + (f" · {parciais} em parte" if parciais else ""))
        self._definir("inicio", str(r["programas"] + len(r["servicos"])),
                      f"{r['programas']} programa(s) · {len(r['servicos'])} serviço(s)")
        lix = r["lixeira"]
        if lix:
            self._definir("lixeira", formatar_tamanho(lix[1]), f"{lix[0]} item(ns)",
                          cor=t.ACENTO if lix[1] > 1 << 30 else None)
        if r["boot"]:
            ultimo = r["boot"][-1]
            ultimos = r["boot"][-5:]
            media = sum(b.total_ms for b in ultimos) / len(ultimos) / 1000
            self._definir("boot", f"{ultimo.total_ms / 1000:.0f} s",
                          f"última vez · média recente {media:.0f} s")
        else:
            self._definir("boot", "—", r["boot_erro"] or "")
        self._r = r
        self._recomendacoes()
        self.j.obter_hardware(self._com_hardware)

    def _com_hardware(self, rel):
        self._hw = rel
        self._recomendacoes()

    def _recomendacoes(self):
        r = getattr(self, "_r", None)
        if r is None:
            return
        for w in self.lista_rec.winfo_children():
            w.destroy()
        recs = []
        if r.get("modo_jogo"):
            recs.append(("aviso", "O modo jogo está ligado. Quando terminar de jogar, saia dele para voltar o "
                                  "plano de energia e reabrir os programas.", "ir para o modo jogo",
                         lambda: self.j.ir("modo_jogo")))
        rel = getattr(self, "_hw", None)
        if rel is not None:
            for tipo, texto, link in hardware.recomendacoes(rel):
                if link:
                    recs.append((tipo, texto, "abrir", lambda u=link: os.startfile(u)))
                else:
                    recs.append((tipo, texto, "ver hardware", lambda: self.j.ir("hardware")))
        d = r["info"]
        if d["ram_total"] and d["ram_pct"] >= 85:
            recs.append(("aviso", f"A memória está em {d['ram_pct']}%. O PC fica lento quando ela enche: "
                                  "veja o que está pesando e feche o que não está usando.",
                         "ver o que pesa", lambda: self.j.ir("desempenho")))
        if d["disco_total"] and d["disco_livre"] / d["disco_total"] < 0.15:
            recs.append(("aviso", "Menos de 15% do disco livre. O Windows precisa de espaço para atualizar.",
                         "ver o que ocupa", lambda: self.j.ir("espaco")))
        if r["removidos"]:
            nomes = ", ".join(x["nome"] for x in r["removidos"][:4])
            recs.append(("aviso", f"A versão antiga apagou {len(r['removidos'])} programa(s) da inicialização "
                                  f"({nomes}). O SecurityHealth é o ícone da Segurança do Windows.",
                         "restaurar", lambda: self.j.ir("inicializacao")))
        if r["protecao"] is False:
            recs.append(("aviso", "A Proteção do Sistema está desligada: o Windows não cria pontos de "
                                  "restauração. Ela é ligada na hora de aplicar ajustes, se você quiser.",
                         "ver ajustes", lambda: self.j.ir("ajustes")))
        if r["servicos"]:
            nomes = ", ".join(x.exibicao for x in r["servicos"][:3])
            recs.append(("info", f"{len(r['servicos'])} serviço(s) de outros programas abrem com o Windows "
                                 f"({nomes}...). Em manual, eles só abrem quando o programa precisa.",
                         "ver serviços", lambda: self.j.ir("inicializacao")))
        lix = r["lixeira"]
        if lix and lix[1] > 1 << 30:
            recs.append(("info", f"A Lixeira tem {formatar_tamanho(lix[1])}.", "ir para a limpeza",
                         lambda: self.j.ir("limpeza")))
        dl = r.get("downloads")
        if dl and dl.bytes > 200 << 20:
            recs.append(("info", f"{formatar_tamanho(dl.bytes)} em downloads que não terminaram, parados na pasta "
                                 "Downloads há mais de uma semana.", "ir para a limpeza",
                         lambda: self.j.ir("limpeza")))
        parciais = [a.nome for a in aj.AJUSTES if r["estados"].get(a.id) == "parcial"]
        if parciais:
            recs.append(("info", f"{len(parciais)} ajuste(s) estão só em parte (o Windows 11 tem opções novas "
                                 f"que a versão antiga não aplicava).", "ver ajustes", lambda: self.j.ir("ajustes")))
        if not recs:
            t.rotulo(self.lista_rec, "Nada urgente agora.", "corpo", 13, t.SUAVE).pack(anchor="w", padx=10, pady=8)
        for tipo, texto, acao, funcao in recs:
            linha = ctk.CTkFrame(self.lista_rec, fg_color="transparent")
            linha.pack(fill="x", padx=6, pady=4)
            linha.grid_columnconfigure(1, weight=1)
            cor = t.ACENTO if tipo == "aviso" else t.SUAVE
            t.icone(linha, "aviso" if tipo == "aviso" else "", 14, cor).grid(row=0, column=0, padx=(4, 12), sticky="n", pady=3)
            t.rotulo(linha, texto, "corpo", 13, wraplength=640).grid(row=0, column=1, sticky="w")
            t.botao(linha, acao, funcao, "secundario", altura=28).grid(row=0, column=2, padx=(12, 4))
