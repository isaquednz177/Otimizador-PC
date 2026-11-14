# -*- coding: utf-8 -*-
"""
Janela do programa (customtkinter).

Regra desta tela: o trabalho pesado roda numa thread, e a thread NUNCA mexe
nos widgets. Ela manda pedidos por uma fila (`no_principal`), que a janela
atende a cada 80 ms. Perguntas no meio do trabalho usam `perguntar`, que
espera a resposta da janela.
"""

import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from otimizador_pc import APP_NOME, APP_VERSAO
from otimizador_pc import ajustes as aj
from otimizador_pc import inicializacao as ini
from otimizador_pc import info, limpeza, ponto
from otimizador_pc.backup import Backup
from otimizador_pc.registro import Registro
from otimizador_pc.sistema import Sistema
from otimizador_pc.util import ARQUIVO_BACKUP, PASTA_LOGS, formatar_tamanho

CINZA = ("gray40", "gray60")
CORES_ESTADO = {
    "aplicado": ("#2e7d32", "#7cc47f"),
    "parcial": ("#a15c00", "#e0a548"),
    "padrao": CINZA,
    "indisponivel": CINZA,
}
TEXTO_ESTADO = {
    "aplicado": "já aplicado",
    "parcial": "aplicado em parte",
    "padrao": "padrão do Windows",
    "indisponivel": "não existe neste PC",
}
RAIO = 4  # cantos quase retos


class Janela(ctk.CTk):

    def __init__(self, admin: bool):
        super().__init__()
        self.admin = admin
        self.title(f"{APP_NOME} {APP_VERSAO}")
        self.geometry("1000x760")
        self.minsize(880, 640)

        self.s = Sistema()
        self.log = Registro(PASTA_LOGS)
        self.backup = Backup(ARQUIVO_BACKUP)
        self._fila_ui = queue.Queue()
        self.ocupado = False
        self.botoes_acao = []

        self._cabecalho()
        self.abas = ctk.CTkTabview(self, corner_radius=RAIO)
        self.abas.pack(fill="both", expand=True, padx=12, pady=(6, 0))
        for nome in ("Limpeza", "Otimização", "Inicialização", "Reverter"):
            self.abas.add(nome)
        self._aba_limpeza(self.abas.tab("Limpeza"))
        self._aba_otimizacao(self.abas.tab("Otimização"))
        self._aba_inicializacao(self.abas.tab("Inicialização"))
        self._aba_reverter(self.abas.tab("Reverter"))
        self._caixa_log()

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(80, self._bombear)

        self.log(f"{APP_NOME} {APP_VERSAO} aberto.")
        if self.backup.aviso:
            self.log("AVISO: " + self.backup.aviso)
        if not admin:
            self.log("Sem privilégio de Administrador: dá para analisar e ver o estado, "
                     "mas limpar o sistema, aplicar e reverter vão falhar. Abra de novo e aceite o aviso do Windows.")
        self.atualizar_cabecalho()
        self.atualizar_inicializacao()
        self.atualizar_reverter()
        self.trabalhar(self._tarefa_estados, silencioso=True)

    # ================================================================ estrutura
    def _cabecalho(self):
        topo = ctk.CTkFrame(self, corner_radius=0)
        topo.pack(fill="x")
        ctk.CTkLabel(topo, text=APP_NOME, font=ctk.CTkFont(size=22, weight="bold")).pack(
            side="left", padx=16, pady=12)
        self.lbl_admin = ctk.CTkLabel(
            topo, text="Administrador" if self.admin else "Sem Administrador",
            text_color=("#2e7d32", "#7cc47f") if self.admin else ("#c62828", "#ef6b6b"))
        self.lbl_admin.pack(side="right", padx=16)
        self.lbl_ram = ctk.CTkLabel(topo, text="", text_color=CINZA)
        self.lbl_ram.pack(side="right", padx=10)
        self.lbl_disco = ctk.CTkLabel(topo, text="", text_color=CINZA)
        self.lbl_disco.pack(side="right", padx=10)

    def _caixa_log(self):
        quadro = ctk.CTkFrame(self, corner_radius=RAIO)
        quadro.pack(fill="x", padx=12, pady=12)
        barra = ctk.CTkFrame(quadro, fg_color="transparent")
        barra.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(barra, text="Registro de atividades", font=ctk.CTkFont(weight="bold")).pack(side="left")
        if self.log.arquivo:
            ctk.CTkLabel(barra, text=f"também salvo em {self.log.arquivo}", text_color=CINZA,
                         font=ctk.CTkFont(size=11)).pack(side="right")
        self.caixa_log = ctk.CTkTextbox(quadro, height=110, corner_radius=RAIO,
                                        font=ctk.CTkFont(family="Consolas", size=12))
        self.caixa_log.pack(fill="x", padx=10, pady=8)

    def _botao(self, pai, texto, comando, acao=True, **kw):
        b = ctk.CTkButton(pai, text=texto, command=comando, corner_radius=RAIO, **kw)
        if acao:
            self.botoes_acao.append(b)
        return b

    def _linha(self, pai, titulo, descricao, variavel=None, direita=""):
        """Uma opção: caixa de marcar (ou só título), texto à direita e a explicação embaixo."""
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(fill="x", padx=6, pady=(8, 0))
        f.grid_columnconfigure(0, weight=1)
        if variavel is not None:
            caixa = ctk.CTkCheckBox(f, text=titulo, variable=variavel, corner_radius=RAIO,
                                    font=ctk.CTkFont(size=13))
        else:
            caixa = ctk.CTkLabel(f, text=titulo, font=ctk.CTkFont(size=13))
        caixa.grid(row=0, column=0, sticky="w")
        lado = ctk.CTkLabel(f, text=direita, text_color=CINZA, anchor="e")
        lado.grid(row=0, column=1, sticky="e", padx=(8, 4))
        if descricao:
            ctk.CTkLabel(f, text=descricao, text_color=CINZA, font=ctk.CTkFont(size=11),
                         wraplength=760, justify="left", anchor="w").grid(
                row=1, column=0, columnspan=2, sticky="w", padx=(28, 0))
        return f, caixa, lado

    # ================================================================ fila e threads
    def _bombear(self):
        try:
            while True:
                linha = self.log.fila.get_nowait()
                self.caixa_log.insert("end", linha + "\n")
                self.caixa_log.see("end")
        except queue.Empty:
            pass
        try:
            while True:
                funcao, args = self._fila_ui.get_nowait()
                try:
                    funcao(*args)
                except Exception as e:  # um erro de tela não pode parar a fila
                    self.log(f"[erro na tela] {e}")
        except queue.Empty:
            pass
        self.after(80, self._bombear)

    def no_principal(self, funcao, *args):
        self._fila_ui.put((funcao, args))

    def perguntar(self, titulo, texto, aviso=False) -> bool:
        """Chamada de dentro da thread: mostra a pergunta na janela e espera."""
        pronto, caixa = threading.Event(), {}

        def mostrar():
            caixa["r"] = (messagebox.askyesno(titulo, texto, icon="warning") if aviso
                          else messagebox.askyesno(titulo, texto))
            pronto.set()
        self.no_principal(mostrar)
        pronto.wait()
        return caixa.get("r", False)

    def trabalhar(self, funcao, silencioso=False):
        if self.ocupado:
            if not silencioso:
                messagebox.showinfo(APP_NOME, "Espere a tarefa atual terminar.")
            return
        self.ocupado = True
        self._travar(True)

        def alvo():
            try:
                funcao()
            except Exception as e:
                self.log(f"[ERRO INESPERADO] {type(e).__name__}: {e}")
            finally:
                self.no_principal(self._terminou)
        threading.Thread(target=alvo, daemon=True).start()

    def _terminou(self):
        self.ocupado = False
        self._travar(False)
        self.atualizar_cabecalho()

    def _travar(self, travado):
        for b in self.botoes_acao:
            try:
                b.configure(state="disabled" if travado else "normal")
            except Exception:
                pass

    def _fechar(self):
        if self.ocupado and not messagebox.askyesno(
                APP_NOME, "Uma tarefa está em andamento. O que já foi feito está salvo no backup, "
                          "mas a tarefa vai parar no meio. Fechar mesmo assim?", icon="warning"):
            return
        self.destroy()

    def atualizar_cabecalho(self):
        d = info.resumo()
        if d["disco_total"]:
            self.lbl_disco.configure(text=f"{info.disco_do_sistema()[:2]} {formatar_tamanho(d['disco_livre'])} livres "
                                          f"de {formatar_tamanho(d['disco_total'])}")
        if d["ram_total"]:
            self.lbl_ram.configure(text=f"RAM {d['ram_pct']}% em uso ({formatar_tamanho(d['ram_total'])})")

    def _precisa_admin(self) -> bool:
        if self.admin:
            return True
        messagebox.showwarning(APP_NOME, "Isto precisa de Administrador. Feche o programa, abra de novo "
                                         "e aceite o aviso do Windows.")
        return False

    # ================================================================ aba Limpeza
    def _aba_limpeza(self, pai):
        lista = ctk.CTkScrollableFrame(pai, corner_radius=RAIO,
                                       label_text="Marque o que apagar. \"Analisar\" mostra o tamanho sem apagar nada.")
        lista.pack(fill="both", expand=True, padx=4, pady=4)
        self.limpeza = {}  # id -> (item, var, rótulo do tamanho)
        self.tamanhos = {}
        for item in limpeza.ITENS:
            if not item.disponivel():
                continue
            var = ctk.BooleanVar(value=item.padrao)
            var.trace_add("write", lambda *_: self._somar_selecao())
            direita = "não libera espaço" if not item.libera_espaco else ""
            _, _, lado = self._linha(lista, item.nome, item.descricao, var, direita)
            self.limpeza[item.id] = (item, var, lado)

        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(2, 4))
        self._botao(barra, "Analisar", lambda: self.trabalhar(self._tarefa_analisar), width=110).pack(side="left", padx=4)
        self._botao(barra, "Só os recomendados", self._marcar_recomendados, acao=False, width=150,
                    fg_color="gray30").pack(side="left", padx=4)
        self._botao(barra, "Desmarcar tudo", lambda: self._marcar(False), acao=False, width=120,
                    fg_color="gray30").pack(side="left", padx=4)
        self.lbl_total = ctk.CTkLabel(barra, text="", text_color=CINZA)
        self.lbl_total.pack(side="left", padx=12)
        self._botao(barra, "Limpar selecionados", self.acao_limpar, width=170).pack(side="right", padx=4)

    def _marcar(self, valor):
        for _, var, _ in self.limpeza.values():
            var.set(valor)

    def _marcar_recomendados(self):
        for item, var, _ in self.limpeza.values():
            var.set(item.padrao)

    def _somar_selecao(self):
        total, desconhecido = 0, False
        for iid, (item, var, _) in self.limpeza.items():
            if var.get() and item.libera_espaco:
                if iid in self.tamanhos and self.tamanhos[iid] is not None:
                    total += self.tamanhos[iid]
                else:
                    desconhecido = True
        if not self.tamanhos:
            self.lbl_total.configure(text="")
            return
        texto = f"Selecionado: {formatar_tamanho(total)}"
        self.lbl_total.configure(text=texto + (" + itens sem estimativa" if desconhecido else ""))

    def _mostrar_tamanho(self, iid, res):
        item, _, lado = self.limpeza[iid]
        if not item.libera_espaco:
            return
        if res is None:
            texto = "sem estimativa"
            self.tamanhos[iid] = None
        else:
            texto = formatar_tamanho(res.bytes) if res.apagados else "vazio"
            self.tamanhos[iid] = res.bytes
        lado.configure(text=texto)
        self._somar_selecao()

    def _tarefa_analisar(self):
        self.log("Analisando (nada é apagado)...")
        total = 0
        for iid, (item, _, lado) in self.limpeza.items():
            if not item.libera_espaco:
                continue
            self.no_principal(lambda rotulo=lado: rotulo.configure(text="analisando..."))
            try:
                res = limpeza.analisar_item(item, self.s)
            except Exception as e:
                self.log(f"   [erro] {item.nome}: {e}")
                res = None
            self.no_principal(self._mostrar_tamanho, iid, res)
            if res:
                total += res.bytes
        self.log(f"Análise pronta: {formatar_tamanho(total)} no total (sem contar os itens sem estimativa).")

    def acao_limpar(self):
        escolhidos = [item for item, var, _ in self.limpeza.values() if var.get()]
        if not escolhidos:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um item.")
            return
        for item in escolhidos:
            if item.confirmar and not messagebox.askyesno(APP_NOME, item.confirmar, icon="warning"):
                return
        if any(i.id == "componentes" for i in escolhidos) and not messagebox.askyesno(
                APP_NOME, "A limpeza de componentes do Windows demora de 5 a 30 minutos. Continuar?"):
            return
        precisa = [i for i in escolhidos if i.id not in ("temp_user", "navegador_chrome", "navegador_edge",
                                                          "navegador_brave", "navegador_opera",
                                                          "navegador_operagx", "navegador_firefox",
                                                          "shaders", "miniaturas", "lixeira", "dns")]
        if precisa and not self._precisa_admin():
            return
        self.trabalhar(lambda: self._tarefa_limpar(escolhidos))

    def _tarefa_limpar(self, escolhidos):
        self.log("=" * 60)
        self.log("LIMPEZA")
        livre_antes = info.espaco_livre()
        soma = 0
        for item in escolhidos:
            self.log(f"> {item.nome}")
            try:
                res = limpeza.limpar_item(item, self.s, self.log)
            except Exception as e:
                self.log(f"   [erro] {e}")
                continue
            if res.nota:
                self.log(f"   {res.nota}")
            if item.libera_espaco and (res.apagados or res.pulados):
                self.log(f"   {res.apagados} arquivo(s), {formatar_tamanho(res.bytes)} liberados"
                         + (f"; {res.pulados} em uso ficaram" if res.pulados else ""))
            soma += res.bytes
            self.no_principal(self._marcar_limpo, item.id)
        livre_depois = info.espaco_livre()
        self.log("-" * 60)
        self.log(f"Somando os arquivos apagados: {formatar_tamanho(soma)}.")
        if livre_antes is not None and livre_depois is not None:
            self.log(f"Espaço livre no disco: antes {formatar_tamanho(livre_antes)}, agora "
                     f"{formatar_tamanho(livre_depois)} ({formatar_tamanho(livre_depois - livre_antes)} a mais).")
        self.log("=" * 60)

    def _marcar_limpo(self, iid):
        item, _, lado = self.limpeza[iid]
        if item.libera_espaco:
            lado.configure(text="limpo")
            self.tamanhos.pop(iid, None)
            self._somar_selecao()

    # ================================================================ aba Otimização
    def _aba_otimizacao(self, pai):
        lista = ctk.CTkScrollableFrame(pai, corner_radius=RAIO,
                                       label_text="Marque o que aplicar. Tudo pode ser desfeito na aba Reverter.")
        lista.pack(fill="both", expand=True, padx=4, pady=4)
        self.otim = {}  # id -> (ajuste, var, caixa, rótulo do estado)
        for a in aj.AJUSTES:
            var = ctk.BooleanVar(value=False)
            _, caixa, lado = self._linha(lista, a.nome, a.descricao, var, "conferindo...")
            self.otim[a.id] = (a, var, caixa, lado)

        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(2, 4))
        self._botao(barra, "Conferir estado", lambda: self.trabalhar(self._tarefa_estados), width=130,
                    fg_color="gray30").pack(side="left", padx=4)
        self.var_ponto = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(barra, text="Criar ponto de restauração antes", variable=self.var_ponto,
                        corner_radius=RAIO).pack(side="left", padx=14)
        self._botao(barra, "Aplicar selecionados", self.acao_otimizar, width=170).pack(side="right", padx=4)

    def _tarefa_estados(self):
        for aid, (a, _, _, _) in self.otim.items():
            estado = aj.estado_do_ajuste(a, self.s, self.backup.dados)
            self.no_principal(self._mostrar_estado, aid, estado)

    def _mostrar_estado(self, aid, estado):
        _, var, caixa, lado = self.otim[aid]
        lado.configure(text=TEXTO_ESTADO[estado], text_color=CORES_ESTADO[estado])
        if estado == "indisponivel":
            var.set(False)
            caixa.configure(state="disabled")
        else:
            caixa.configure(state="normal")

    def acao_otimizar(self):
        escolhidos = [a for a, var, _, _ in self.otim.values() if var.get()]
        if not escolhidos:
            messagebox.showinfo(APP_NOME, "Marque pelo menos um ajuste.")
            return
        if not self._precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"Aplicar {len(escolhidos)} ajuste(s)? Como estava antes fica "
                                             "guardado, e a aba Reverter desfaz."):
            return
        com_ponto = self.var_ponto.get()
        self.trabalhar(lambda: self._tarefa_otimizar(escolhidos, com_ponto))

    def _tarefa_otimizar(self, escolhidos, com_ponto):
        self.log("=" * 60)
        self.log("OTIMIZAÇÃO")
        if com_ponto and not self._garantir_ponto():
            self.log("Cancelado: nada foi mudado.")
            return
        for a in escolhidos:
            self.log(f"> {a.nome}")
            aj.aplicar_ajuste(a, self.backup, self.s, self.log)
        self.log("-" * 60)
        self.log("Pronto. Alguns ajustes só valem depois de reiniciar o PC.")
        self.log("=" * 60)
        self.no_principal(self.atualizar_reverter)
        self._tarefa_estados()

    def _garantir_ponto(self) -> bool:
        r = ponto.criar_ponto(self.s, self.log)
        if r == "desligada":
            if self.perguntar(APP_NOME, "A Proteção do Sistema está desligada neste PC, então o Windows não "
                                        "cria pontos de restauração.\n\nLigar agora no disco do sistema? "
                                        "Ela usa uma parte pequena do disco para guardar os pontos."):
                ok, msg = ponto.ligar_protecao(self.s)
                self.log("Proteção do Sistema ligada." if ok else f"Não deu para ligar: {msg}")
                if ok:
                    r = ponto.criar_ponto(self.s, self.log)
        if r == "ok":
            return True
        return self.perguntar(APP_NOME, "Não foi criado um ponto de restauração.\n\nOs ajustes ainda podem ser "
                                        "desfeitos pela aba Reverter. Continuar mesmo assim?", aviso=True)

    # ================================================================ aba Inicialização
    def _aba_inicializacao(self, pai):
        self.lista_ini = ctk.CTkScrollableFrame(
            pai, corner_radius=RAIO,
            label_text="Programas que abrem com o Windows. Desligar não apaga nada (igual ao Gerenciador de Tarefas).")
        self.lista_ini.pack(fill="both", expand=True, padx=4, pady=4)
        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(2, 4))
        self._botao(barra, "Atualizar lista", self.atualizar_inicializacao, width=130,
                    fg_color="gray30").pack(side="left", padx=4)
        self.lbl_ini = ctk.CTkLabel(barra, text="", text_color=CINZA)
        self.lbl_ini.pack(side="left", padx=12)

    def atualizar_inicializacao(self):
        for w in self.lista_ini.winfo_children():
            w.destroy()
        removidos = self.backup.dados.get("inicializacao_removida", {})
        if removidos:
            ctk.CTkLabel(self.lista_ini, text="Apagados pela versão antiga do programa (podem voltar):",
                         font=ctk.CTkFont(size=13, weight="bold"), text_color=("#a15c00", "#e0a548")).pack(
                anchor="w", padx=6, pady=(6, 0))
            for chave, item in removidos.items():
                f, _, _ = self._linha(self.lista_ini, item["nome"], str(item.get("valor", "")))
                self._botao(f, "restaurar", lambda c=chave: self._restaurar_removido(c), width=90,
                            fg_color="gray30").grid(row=0, column=1, sticky="e")
            ctk.CTkLabel(self.lista_ini, text="Na inicialização agora:", font=ctk.CTkFont(size=13, weight="bold")).pack(
                anchor="w", padx=6, pady=(14, 0))

        itens = ini.listar(self.s)
        if not itens:
            ctk.CTkLabel(self.lista_ini, text="Nenhum programa na inicialização.", text_color=CINZA).pack(
                anchor="w", padx=8, pady=10)
        for item in itens:
            f = ctk.CTkFrame(self.lista_ini, fg_color="transparent")
            f.pack(fill="x", padx=6, pady=(8, 0))
            var = ctk.BooleanVar(value=item.ativo)
            chave = ctk.CTkSwitch(f, text=item.nome, variable=var, font=ctk.CTkFont(size=13))
            chave.configure(command=lambda i=item, v=var: self._alternar(i, v))
            chave.pack(anchor="w")
            comando = item.comando if len(item.comando) < 120 else item.comando[:117] + "..."
            ctk.CTkLabel(f, text=f"{item.quem} · {comando}", text_color=CINZA, font=ctk.CTkFont(size=11),
                         wraplength=760, justify="left", anchor="w").pack(anchor="w", padx=(46, 0))
        ligados = sum(1 for i in itens if i.ativo)
        self.lbl_ini.configure(text=f"{ligados} de {len(itens)} ligados")

    def _alternar(self, item, var):
        ligar = bool(var.get())
        if item.hive == "HKLM" and not self.admin:
            var.set(not ligar)
            self._precisa_admin()
            return
        ok, msg = ini.definir(self.s, item, ligar)
        if not ok:
            var.set(not ligar)
        self.log(f"Inicialização · {item.nome}: {msg}")
        if ok:
            # redesenha depois: o botão não pode ser destruído dentro do próprio clique
            self.after(50, self.atualizar_inicializacao)

    def _restaurar_removido(self, chave):
        item = self.backup.dados.get("inicializacao_removida", {}).get(chave)
        if item and item.get("hive") == "HKLM" and not self._precisa_admin():
            return
        ok, msg = ini.restaurar_removido(self.s, self.backup, chave)
        self.log(f"Inicialização · {item['nome'] if item else chave}: {msg}")
        self.after(50, self.atualizar_inicializacao)

    # ================================================================ aba Reverter
    def _aba_reverter(self, pai):
        self.lista_rev = ctk.CTkScrollableFrame(
            pai, corner_radius=RAIO, label_text="Ajustes aplicados por este programa. Marque para voltar como estava.")
        self.lista_rev.pack(fill="both", expand=True, padx=4, pady=4)
        self.rev = {}
        barra = ctk.CTkFrame(pai, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(2, 4))
        self._botao(barra, "Restaurar tudo", lambda: self.acao_reverter(tudo=True), width=140,
                    fg_color="#7f1d1d", hover_color="#991b1b").pack(side="right", padx=4)
        self._botao(barra, "Restaurar selecionados", self.acao_reverter, width=190,
                    fg_color="#8a4b08", hover_color="#6f3c06").pack(side="right", padx=4)

    def atualizar_reverter(self):
        for w in self.lista_rev.winfo_children():
            w.destroy()
        self.rev = {}
        aplicados = self.backup.dados.get("ajustes", {})
        if not aplicados:
            ctk.CTkLabel(self.lista_rev, text="Nenhum ajuste aplicado por este programa.", text_color=CINZA).pack(
                anchor="w", padx=8, pady=12)
            return
        for aid, reg in aplicados.items():
            var = ctk.BooleanVar(value=False)
            n = len(reg.get("passos", {}))
            self._linha(self.lista_rev, reg.get("nome", aid),
                        f"aplicado em {reg.get('data') or '?'} · {n} mudança(s) guardada(s)", var)
            self.rev[aid] = var

    def acao_reverter(self, tudo=False):
        ids = list(self.rev) if tudo else [aid for aid, v in self.rev.items() if v.get()]
        if not ids:
            messagebox.showinfo(APP_NOME, "Não há nada marcado para restaurar.")
            return
        if not self._precisa_admin():
            return
        if not messagebox.askyesno(APP_NOME, f"Voltar {len(ids)} ajuste(s) para como estavam antes?"):
            return
        self.trabalhar(lambda: self._tarefa_reverter(ids))

    def _tarefa_reverter(self, ids):
        self.log("=" * 60)
        self.log("REVERSÃO")
        for aid in ids:
            nome = self.backup.dados["ajustes"].get(aid, {}).get("nome", aid)
            self.log(f"> {nome}")
            aj.reverter_ajuste(aid, self.backup, self.s, self.log)
        self.log("-" * 60)
        self.log("Pronto. Reinicie o PC para tudo voltar de vez.")
        self.log("=" * 60)
        self.no_principal(self.atualizar_reverter)
        self._tarefa_estados()


def abrir(admin: bool):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    Janela(admin).mainloop()
