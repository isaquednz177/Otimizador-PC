# -*- coding: utf-8 -*-
"""Inicialização: programas, serviços e tarefas de outros programas que abrem com o Windows."""

import os

import customtkinter as ctk

from otimizador_pc import inicializacao as ini
from otimizador_pc import tema as t
from otimizador_pc.telas.base import Pagina


def _curto(texto, n=110):
    return texto if len(texto) <= n else texto[: n - 3] + "..."


class Inicializacao(Pagina):
    titulo = "Abrem com o Windows"
    subtitulo = ("Programas que começam sozinhos quando o PC liga. Cada um deixa o PC mais demorado para ficar "
                 "pronto e gasta memória. Desligar não apaga nada: o programa continua instalado e você abre "
                 "quando quiser.")

    def montar(self):
        self.botao_topo("atualizar", self.atualizar)
        cartao = t.cartao(self.corpo)
        cartao.pack(fill="both", expand=True)
        self.area = t.rolavel(cartao)
        self.area.pack(fill="both", expand=True, padx=8, pady=8)
        self._carregado = False

    def ao_mostrar(self):
        super().ao_mostrar()
        if not self._carregado:
            self.atualizar()

    def atualizar(self):
        self._carregado = True
        for w in self.area.winfo_children():
            w.destroy()
        t.rotulo(self.area, "lendo...", "corpo", 13, t.FRACO).pack(anchor="w", padx=12, pady=12)
        self.j.em_segundo_plano(self._ler, self._mostrar)

    def _ler(self):
        s = self.s
        tarefas, erro_tarefas = [], None
        if self.j.admin:
            tarefas = ini.listar_tarefas()
        else:
            erro_tarefas = "Para ver esta lista, abra o programa com permissão de Administrador."
        return {"programas": ini.listar(s), "servicos": ini.listar_servicos(s, self.j.backup),
                "tarefas": tarefas, "erro_tarefas": erro_tarefas,
                "removidos": dict(self.j.backup.dados.get("inicializacao_removida", {}))}

    # ------------------------------------------------------------ desenho
    def _secao(self, titulo, texto):
        f = ctk.CTkFrame(self.area, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(18, 4))
        t.rotulo(f, titulo, "titulo", 13, t.ACENTO).pack(anchor="w")
        if texto:
            t.rotulo(f, texto, "corpo", 12, t.FRACO, wraplength=760).pack(anchor="w", pady=(2, 0))
        t.separador(self.area).pack(fill="x", padx=10, pady=(4, 0))

    def _linha(self, nome, sub, aviso=""):
        f = ctk.CTkFrame(self.area, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(8, 0))
        f.grid_columnconfigure(0, weight=1)
        t.rotulo(f, nome, "corpo_forte", 13).grid(row=0, column=0, sticky="w")
        t.rotulo(f, sub, "corpo", 11, t.FRACO, wraplength=700).grid(row=1, column=0, sticky="w")
        if aviso:
            t.rotulo(f, aviso, "corpo", 11, t.ACENTO, wraplength=700).grid(row=2, column=0, sticky="w")
        return f

    def _mostrar(self, d):
        for w in self.area.winfo_children():
            w.destroy()

        if d["removidos"]:
            self._secao("Apagados pela versão antiga deste programa",
                        "A versão antiga apagava esses programas da lista em vez de só desligar. "
                        "\"Restaurar\" põe de volta como era.")
            for chave, item in d["removidos"].items():
                f = self._linha(item["nome"], _curto(str(item.get("valor", ""))),
                                "é o ícone da Segurança do Windows: vale restaurar" if item["nome"] == "SecurityHealth" else "")
                t.botao(f, "restaurar", lambda c=chave: self._restaurar(c), "secundario", largura=104,
                        altura=28).grid(row=0, column=1, rowspan=2, sticky="e")

        ligados = sum(1 for p in d["programas"] if p.ativo)
        self._secao(f"Programas  ·  {ligados} de {len(d['programas'])} abrem sozinhos", "Desligue o que você não precisa logo que liga o PC (Steam, Discord, Spotify...). Você ainda pode abrir cada um quando quiser.")
        if not d["programas"]:
            t.rotulo(self.area, "Nenhum.", "corpo", 12, t.FRACO).pack(anchor="w", padx=12, pady=6)
        for p in d["programas"]:
            f = self._linha(p.nome, f"{p.quem}  ·  {_curto(p.comando)}")
            t.Alternador(f, p.ativo, lambda b, ligar, item=p: self._programa(b, item, ligar)).grid(
                row=0, column=1, rowspan=2, sticky="e")

        auto = sum(1 for x in d["servicos"] if x.automatico)
        self._secao(f"Programas que rodam escondidos (serviços)  ·  {auto} ligam sozinhos",
                    "Partes de programas que rodam sem janela (como atualizadores). Em \"só quando precisa\", "
                    "eles não ligam com o Windows: o programa dono chama quando precisar. Os do Windows e do "
                    "antivírus não aparecem aqui, para não estragar nada.")
        if not d["servicos"]:
            t.rotulo(self.area, "Nenhum.", "corpo", 12, t.FRACO).pack(anchor="w", padx=12, pady=6)
        for x in d["servicos"]:
            aviso = "é um atualizador: o programa continua se atualizando quando você abrir ele" if x.atualizador else ""
            f = self._linha(x.exibicao, f"{x.nome}  ·  {_curto(x.caminho.strip(chr(34)))}", aviso)
            t.Alternador(f, x.automatico, lambda b, ligar, item=x: self._servico(b, item, ligar),
                         textos=("liga sozinho", "só quando precisa"), largura=150).grid(row=0, column=1, rowspan=2, sticky="e")

        self._secao(f"Tarefas automáticas de outros programas  ·  {len(d['tarefas'])}",
                    "Coisas que o Windows roda sozinho em certos horários para outros programas (quase sempre "
                    "atualizadores). As do próprio Windows não aparecem aqui.")
        if d["erro_tarefas"]:
            t.rotulo(self.area, d["erro_tarefas"], "corpo", 12, t.FRACO).pack(anchor="w", padx=12, pady=6)
        elif not d["tarefas"]:
            t.rotulo(self.area, "Nenhuma.", "corpo", 12, t.FRACO).pack(anchor="w", padx=12, pady=6)
        for tf in d["tarefas"]:
            aviso = "é um atualizador: desligado, o programa só se atualiza quando você abrir ele" if tf.atualizador else ""
            exe = os.path.basename(tf.comando.split('"')[1] if tf.comando.startswith('"') else tf.comando.split(" ")[0])
            f = self._linha(tf.nome, f"{tf.quando}  ·  {exe or 'sem programa'}" + (f"  ·  {tf.autor}" if tf.autor else ""),
                            aviso)
            t.Alternador(f, tf.ativa, lambda b, ligar, item=tf: self._tarefa(b, item, ligar)).grid(
                row=0, column=1, rowspan=2, sticky="e")

    # ------------------------------------------------------------ ações
    def _programa(self, botao, item, ligar):
        if item.hive == "HKLM" and not self.j.precisa_admin():
            return
        ok, msg = ini.definir(self.s, item, ligar)
        if ok:
            botao.definir(ligar)
        self.log(f"Inicialização · {item.nome}: {msg}")

    def _servico(self, botao, item, ligar):
        if not self.j.precisa_admin():
            return
        ok, msg = ini.definir_servico(self.s, self.j.backup, item, ligar)
        if ok:
            botao.definir(ligar)
        self.log(f"Serviço · {item.exibicao}: {msg}")

    def _tarefa(self, botao, item, ligar):
        if not self.j.precisa_admin():
            return
        ok, msg = self.s.tarefa_definir(item.caminho, ligar)
        if ok:
            item.ativa = ligar
            botao.definir(ligar)
        self.log(f"Tarefa · {item.nome}: {'ligada' if ligar else 'desligada'}" if ok else f"Tarefa · {item.nome}: {msg}")

    def _restaurar(self, chave):
        item = self.j.backup.dados.get("inicializacao_removida", {}).get(chave)
        if item and item.get("hive") == "HKLM" and not self.j.precisa_admin():
            return
        ok, msg = ini.restaurar_removido(self.s, self.j.backup, chave)
        self.log(f"Inicialização · {item['nome'] if item else chave}: {msg}")
        self.after(50, self.atualizar)
