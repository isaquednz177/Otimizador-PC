# -*- coding: utf-8 -*-
"""
A janela: menu lateral, páginas e barra de status.

Regra desta tela: o trabalho pesado roda numa thread, e a thread NUNCA mexe
nos widgets. Ela manda pedidos por uma fila (`no_principal`), que a janela
atende a cada 60 ms. Perguntas no meio do trabalho usam `perguntar`, que
espera a resposta da janela.

- `trabalhar(funcao, titulo)`: tarefa que muda o sistema; uma por vez, com
  barra de progresso e botão de cancelar. `funcao` recebe um Controle.
- `em_segundo_plano(funcao, depois)`: leitura rápida (não trava os botões).
"""

import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME, APP_VERSAO, info
from otimizador_pc import tema as t
from otimizador_pc.backup import Backup
from otimizador_pc.controle import Cancelado, Controle
from otimizador_pc.registro import Registro
from otimizador_pc.sistema import Sistema
from otimizador_pc.telas import PAGINAS
from otimizador_pc.util import ARQUIVO_BACKUP, PASTA_LOGS, formatar_tamanho


class Janela(ctk.CTk):

    def __init__(self, admin: bool):
        super().__init__(fg_color=t.FUNDO)
        t.preparar_fontes()
        self.admin = admin
        self.title(f"{APP_NOME} {APP_VERSAO}")
        self.geometry("1180x780")
        self.minsize(1000, 660)

        self.s = Sistema()
        self.log = Registro(PASTA_LOGS)
        self.backup = Backup(ARQUIVO_BACKUP)
        self._fila_ui = queue.Queue()
        self.ocupado = False
        self.ctl = None
        self.botoes_acao = []
        self.linhas_log = []
        self.paginas, self.nav = {}, {}
        self.atual = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._lateral()
        self.conteudo = ctk.CTkFrame(self, fg_color=t.FUNDO, corner_radius=0)
        self.conteudo.grid(row=0, column=1, sticky="nsew")
        self.conteudo.grid_columnconfigure(0, weight=1)
        self.conteudo.grid_rowconfigure(0, weight=1)
        self._barra_status()

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(60, self._bombear)

        self.log(f"{APP_NOME} {APP_VERSAO} aberto.")
        if self.backup.aviso:
            self.log("AVISO: " + self.backup.aviso)
        if not admin:
            self.log("Sem Administrador: dá para ver e analisar, mas não para mudar o sistema.")
        self.atualizar_lateral()
        self.ir("inicio")

    # ================================================================ estrutura
    def _lateral(self):
        lado = ctk.CTkFrame(self, fg_color=t.LATERAL, corner_radius=0, width=228)
        lado.grid(row=0, column=0, rowspan=2, sticky="nsw")
        lado.grid_propagate(False)
        lado.grid_columnconfigure(0, weight=1)

        marca = ctk.CTkFrame(lado, fg_color="transparent")
        marca.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 18))
        t.rotulo(marca, "OTIMIZADOR", "titulo", 20, t.TEXTO).pack(anchor="w")
        linha = ctk.CTkFrame(marca, fg_color="transparent")
        linha.pack(anchor="w", fill="x")
        ctk.CTkFrame(linha, fg_color=t.ACENTO, width=22, height=3, corner_radius=0).pack(side="left", pady=(2, 0))
        t.rotulo(linha, f"  PC  ·  {APP_VERSAO}", "numero", 11, t.SUAVE).pack(side="left")

        for i, (chave, nome, _) in enumerate(PAGINAS, start=1):
            self.nav[chave] = self._item_nav(lado, i, chave, nome)

        lado.grid_rowconfigure(len(PAGINAS) + 1, weight=1)
        rodape = ctk.CTkFrame(lado, fg_color="transparent")
        rodape.grid(row=len(PAGINAS) + 2, column=0, sticky="ew", padx=20, pady=18)
        self.lbl_disco = t.rotulo(rodape, "", "corpo", 11, t.SUAVE)
        self.lbl_disco.pack(anchor="w")
        self.barra_disco = t.barra(rodape, 0, largura=186, altura=4)
        self.barra_disco.pack(anchor="w", pady=(4, 10))
        cor = t.OK if self.admin else t.PERIGO
        linha = ctk.CTkFrame(rodape, fg_color="transparent")
        linha.pack(anchor="w")
        t.icone(linha, "escudo", 13, cor).pack(side="left")
        t.rotulo(linha, "  Administrador" if self.admin else "  Sem Administrador", "corpo", 11, cor).pack(side="left")

    def _item_nav(self, pai, linha, chave, nome):
        f = ctk.CTkFrame(pai, fg_color="transparent", corner_radius=0, height=40, cursor="hand2")
        f.grid(row=linha, column=0, sticky="ew", padx=(0, 10))
        f.grid_propagate(False)
        marca = ctk.CTkFrame(f, fg_color="transparent", width=3, corner_radius=0)
        marca.place(x=0, y=6, relheight=0.7)
        ic = t.icone(f, chave, 15, t.FRACO)
        ic.place(x=22, rely=0.5, anchor="w")
        tx = t.rotulo(f, nome, "corpo", 13, t.SUAVE)
        tx.place(x=52, rely=0.5, anchor="w")
        item = {"quadro": f, "marca": marca, "icone": ic, "texto": tx}

        def entrar(_):
            if self.atual != chave:
                f.configure(fg_color=t.PAINEL)

        def sair(_):
            if self.atual != chave:
                f.configure(fg_color="transparent")
        for w in (f, ic, tx):
            w.bind("<Button-1>", lambda e: self.ir(chave))
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", sair)
        return item

    def _barra_status(self):
        barra = ctk.CTkFrame(self, fg_color=t.LATERAL, corner_radius=0, height=38)
        barra.grid(row=1, column=1, sticky="ew")
        barra.grid_propagate(False)
        barra.grid_columnconfigure(0, weight=1)
        self.lbl_status = t.rotulo(barra, "", "corpo", 11, t.SUAVE)
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=18, pady=9)
        self.progresso = t.barra(barra, 0, largura=220, altura=4)
        self.btn_cancelar = t.botao(barra, "cancelar", self.cancelar, "fantasma", largura=80, altura=26)

    # ================================================================ navegação
    def ir(self, chave):
        if chave not in self.paginas:
            classe = dict((c, cls) for c, _, cls in PAGINAS)[chave]
            pagina = classe(self, self.conteudo)
            pagina.grid(row=0, column=0, sticky="nsew")
            self.paginas[chave] = pagina
        if self.atual and self.atual in self.paginas:
            self.paginas[self.atual].ao_esconder()
            n = self.nav[self.atual]
            n["quadro"].configure(fg_color="transparent")
            n["marca"].configure(fg_color="transparent")
            n["icone"].configure(text_color=t.FRACO)
            n["texto"].configure(text_color=t.SUAVE)
        self.atual = chave
        n = self.nav[chave]
        n["quadro"].configure(fg_color=t.PAINEL)
        n["marca"].configure(fg_color=t.ACENTO)
        n["icone"].configure(text_color=t.ACENTO)
        n["texto"].configure(text_color=t.TEXTO)
        self.paginas[chave].tkraise()
        self.paginas[chave].ao_mostrar()

    def pagina(self, chave):
        return self.paginas.get(chave)

    def atualizar_lateral(self):
        d = info.resumo()
        if d["disco_total"]:
            usado = 1 - d["disco_livre"] / d["disco_total"]
            self.lbl_disco.configure(text=f"{info.disco_do_sistema()[:2]}  {formatar_tamanho(d['disco_livre'])} livres")
            self.barra_disco.configure(progress_color=t.cor_do_uso(usado))
            self.barra_disco.set(usado)

    # ================================================================ fila e threads
    def _bombear(self):
        try:
            while True:
                linha = self.log.fila.get_nowait()
                self.linhas_log.append(linha)
                self.lbl_status.configure(text=linha[11:] if len(linha) > 11 else linha)
                reg = self.paginas.get("registro")
                if reg:
                    reg.acrescentar(linha)
        except queue.Empty:
            pass
        try:
            while True:
                funcao, args = self._fila_ui.get_nowait()
                try:
                    funcao(*args)
                except Exception as e:  # um erro de tela não pode parar a fila
                    self.log(f"[erro na tela] {type(e).__name__}: {e}")
        except queue.Empty:
            pass
        self.after(60, self._bombear)

    def no_principal(self, funcao, *args):
        self._fila_ui.put((funcao, args))

    def perguntar(self, texto, aviso=False) -> bool:
        """Chamada de dentro da thread: mostra a pergunta na janela e espera."""
        pronto, caixa = threading.Event(), {}

        def mostrar():
            caixa["r"] = messagebox.askyesno(APP_NOME, texto, icon="warning" if aviso else "question")
            pronto.set()
        self.no_principal(mostrar)
        pronto.wait()
        return caixa.get("r", False)

    def em_segundo_plano(self, funcao, depois=None):
        def alvo():
            try:
                r = funcao()
            except Exception as e:
                self.log(f"[erro] {type(e).__name__}: {e}")
                return
            if depois:
                self.no_principal(depois, r)
        threading.Thread(target=alvo, daemon=True).start()

    def trabalhar(self, funcao, titulo="trabalhando", cancelavel=True, silencioso=False) -> bool:
        if self.ocupado:
            if not silencioso:
                messagebox.showinfo(APP_NOME, "Espere a tarefa atual terminar (ou cancele).")
            return False
        self.ocupado = True
        self.ctl = Controle(progresso=lambda texto, fr: self.no_principal(self._progresso, texto, fr))
        self._travar(True)
        self._mostrar_progresso(titulo, cancelavel)

        def alvo():
            try:
                funcao(self.ctl)
            except Cancelado:
                self.log("Cancelado. O que já tinha sido feito ficou feito (e guardado no backup).")
            except Exception as e:
                self.log(f"[ERRO INESPERADO] {type(e).__name__}: {e}")
            finally:
                self.no_principal(self._terminou)
        threading.Thread(target=alvo, daemon=True).start()
        return True

    def cancelar(self):
        if self.ctl:
            self.ctl.parar()
            self.btn_cancelar.configure(state="disabled", text="cancelando...")

    def _mostrar_progresso(self, titulo, cancelavel):
        self.lbl_status.configure(text=titulo + "...")
        self.progresso.configure(mode="indeterminate")
        self.progresso.grid(row=0, column=1, padx=10)
        self.progresso.start()
        if cancelavel:
            self.btn_cancelar.configure(state="normal", text="cancelar")
            self.btn_cancelar.grid(row=0, column=2, padx=(0, 12))

    def _progresso(self, texto, fracao):
        if texto:
            self.lbl_status.configure(text=texto if len(texto) < 110 else texto[:107] + "...")
        if fracao is not None:
            if self.progresso.cget("mode") != "determinate":
                self.progresso.stop()
                self.progresso.configure(mode="determinate")
            self.progresso.set(max(0.0, min(1.0, fracao)))

    def _terminou(self):
        self.ocupado = False
        self.ctl = None
        self.progresso.stop()
        self.progresso.grid_forget()
        self.btn_cancelar.grid_forget()
        self._travar(False)
        self.atualizar_lateral()
        if self.linhas_log:
            self.lbl_status.configure(text=self.linhas_log[-1][11:])

    def registrar_botao(self, b):
        self.botoes_acao.append(b)
        return b

    def _travar(self, travado):
        for b in self.botoes_acao:
            try:
                b.configure(state="disabled" if travado else "normal")
            except Exception:
                pass

    def precisa_admin(self) -> bool:
        if self.admin:
            return True
        messagebox.showwarning(APP_NOME, "Isto precisa de Administrador. Feche o programa, abra de novo "
                                         "e responda Sim no aviso do Windows.")
        return False

    def _fechar(self):
        if self.ocupado and not messagebox.askyesno(
                APP_NOME, "Uma tarefa está em andamento. O que já foi feito está salvo no backup, "
                          "mas a tarefa vai parar no meio. Fechar mesmo assim?", icon="warning"):
            return
        self.destroy()


def abrir(admin: bool):
    ctk.set_appearance_mode("dark")
    Janela(admin).mainloop()
