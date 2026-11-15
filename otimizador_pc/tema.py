# -*- coding: utf-8 -*-
"""
A cara do programa: vermelho-sangue, preto gótico e marrom escuro.

- Fundo preto, painéis em marrom escuro, bordas e volutas em marrom, e o
  vermelho-sangue nos destaques, nas barras e no botão principal.
- Fontes normais do Windows (Segoe UI).
- Cartões com a moldura de volutas nos cantos.
- Fundo áspero de TV de tubo (linhas de varredura e granulado) atrás dos títulos,
  no lugar de degradê liso.
- Cantos quase retos; nenhum botão em pílula.
"""

import os
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

ARTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arte")

# ---------------------------------------------------------------- cores
FUNDO = "#090606"         # preto gótico
LATERAL = "#0C0807"
PAINEL = "#1B120D"        # marrom escuro
PAINEL2 = "#26190F"
LINHA = "#382519"
ORNATO = "#5E3D27"        # borda dos cartões e volutas (marrom)
TEXTO = "#EEE6DC"
SUAVE = "#B9A898"
FRACO = "#83705F"
ACENTO = "#E5474F"        # vermelho-sangue para texto e destaques (contraste 5:1 no preto, 4,7:1 no marrom)
ACENTO_CLARO = "#EE5A61"
ACENTO_FUNDO = "#2C0D0D"
NO_ACENTO = "#FFFFFF"
VINHO = "#8A0A12"         # vermelho-sangue escuro (botão principal)
VINHO_CLARO = "#A8101A"
OK = "#A3B57E"            # "já aplicado", saudável
PERIGO = "#E5474F"
PERIGO_FUNDO = "#300A0C"
LARANJA = "#C9732C"
NORMAL = "#8C6447"        # barras em uso normal (marrom claro)
NAV_ATIVO = "#2A1210"     # item do menu escolhido
NAV_HOVER = "#170E0B"
BARRA = "#5E3D27"         # barras dos gráficos
RAIO = 2

ICONES = {
    "inicio": "", "desempenho": "", "limpeza": "", "espaco": "",
    "ajustes": "", "inicializacao": "", "medicoes": "", "reverter": "",
    "registro": "", "modo_jogo": "", "hardware": "", "pasta": "",
    "subir": "", "atualizar": "", "fechar": "", "escudo": "", "aviso": "",
}

_familias = {}
_imagens = {}   # guarda as imagens (o Tk apaga imagem sem referência)


def preparar_fontes():
    """Chamar depois de criar a janela. Fontes normais do Windows."""
    existentes = set(tkfont.families())

    def primeira(*opcoes):
        for f in opcoes:
            if f in existentes:
                return f
        return opcoes[-1]
    _familias.update(
        gotico=primeira("Segoe UI Variable Display Semib", "Segoe UI Semibold", "Segoe UI"),  # títulos das páginas
        titulo=primeira("Segoe UI Semibold", "Segoe UI"),
        numero=primeira("Segoe UI Semibold", "Segoe UI"),
        corpo=primeira("Segoe UI Variable Text", "Segoe UI"),
        corpo_forte=primeira("Segoe UI Variable Text Semibold", "Segoe UI Semibold", "Segoe UI"),
        mono=primeira("Cascadia Mono", "Consolas"),
        icone=primeira("Segoe Fluent Icons", "Segoe MDL2 Assets", "Segoe UI Symbol"),
    )


_AJUSTE = {}


def familia(tipo):
    return _familias.get(tipo, "Segoe UI")


def fonte(tipo="corpo", tamanho=13):
    return ctk.CTkFont(family=familia(tipo), size=tamanho + _AJUSTE.get(tipo, 0))


def escala(widget) -> float:
    try:
        return ctk.ScalingTracker.get_widget_scaling(widget)
    except Exception:
        return 1.0


# ---------------------------------------------------------------- imagens
def _moldura():
    """Os 4 cantos com volutas, recortados da moldura do site e pintados na cor ORNATO."""
    if "cantos" in _imagens:
        return _imagens["cantos"]
    try:
        from PIL import Image
        img = Image.open(os.path.join(ARTE, "moldura.png")).convert("RGBA")
        r, g, b = (int(ORNATO[i:i + 2], 16) for i in (1, 3, 5))
        alfa = img.getchannel("A")
        img = Image.new("RGBA", img.size, (r, g, b, 255))
        img.putalpha(alfa)
        n = 40  # o PNG tem 120 px (o dobro de 60): cada canto ocupa 40 x 40
        w, h = img.size
        cantos = {
            "nw": img.crop((0, 0, n, n)), "ne": img.crop((w - n, 0, w, n)),
            "sw": img.crop((0, h - n, n, h)), "se": img.crop((w - n, h - n, w, h)),
        }
        _imagens["cantos"] = {k: ctk.CTkImage(v, size=(20, 20)) for k, v in cantos.items()}
    except Exception:
        _imagens["cantos"] = None
    return _imagens["cantos"]


def textura_crt(largura: int, altura: int, base: str = FUNDO):
    """Fundo de TV de tubo: granulado fino e linhas de varredura (uma imagem PIL)."""
    from PIL import Image, ImageDraw
    r, g, b = (int(base[i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new("RGB", (largura, altura), (r, g, b))
    ruido = Image.effect_noise((largura, altura), 40).convert("L")
    quente = Image.merge("RGB", (ruido, ruido.point(lambda v: int(v * 0.8)), ruido.point(lambda v: int(v * 0.7))))
    img = Image.blend(img, quente, 0.07)
    desenho = ImageDraw.Draw(img, "RGBA")
    for y in range(0, altura, 3):
        desenho.line([(0, y), (largura, y)], fill=(0, 0, 0, 70))
    # brilho fraco de tela ligada no meio
    brilho = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(brilho).ellipse((-largura * 0.2, -altura * 1.2, largura * 0.9, altura * 1.6), fill=26)
    claro = Image.new("RGB", (largura, altura), (110, 12, 16))
    img = Image.composite(claro, img, brilho.point(lambda v: v // 2))
    return img


# ---------------------------------------------------------------- peças
def rotulo(pai, texto="", tipo="corpo", tamanho=13, cor=TEXTO, **kw):
    kw.setdefault("anchor", "w")
    kw.setdefault("justify", "left")
    return ctk.CTkLabel(pai, text=texto, font=fonte(tipo, tamanho), text_color=cor, **kw)


def icone(pai, nome, tamanho=16, cor=SUAVE, **kw):
    return ctk.CTkLabel(pai, text=ICONES.get(nome, nome), font=fonte("icone", tamanho), text_color=cor, **kw)


def botao(pai, texto, comando, tipo="secundario", largura=None, altura=32, **kw):
    estilos = {
        # vinho com friso dourado, como o botão principal do site
        "principal": dict(fg_color=VINHO, hover_color=VINHO_CLARO, text_color=TEXTO,
                          border_width=1, border_color=ACENTO, font=fonte("titulo", 13)),
        "secundario": dict(fg_color=PAINEL2, hover_color="#302014", text_color=TEXTO,
                           border_width=1, border_color=ORNATO, font=fonte("corpo", 13)),
        "perigo": dict(fg_color=PERIGO_FUNDO, hover_color="#4A1012", text_color=PERIGO,
                       border_width=1, border_color="#6A1418", font=fonte("corpo", 13)),
        "fantasma": dict(fg_color="transparent", hover_color=PAINEL2, text_color=SUAVE,
                         border_width=0, font=fonte("corpo", 12)),
    }
    opcoes = dict(estilos[tipo], corner_radius=RAIO, height=altura, text_color_disabled=FRACO)
    if largura:
        opcoes["width"] = largura
    opcoes.update(kw)
    return ctk.CTkButton(pai, text=texto, command=comando, **opcoes)


def cartao(pai, ornado=True, **kw):
    """Painel com borda de ouro velho e as volutas do site nos quatro cantos."""
    kw.setdefault("fg_color", PAINEL)
    c = ctk.CTkFrame(pai, corner_radius=0, border_width=1, border_color=ORNATO, **kw)
    cantos = _moldura() if ornado else None
    if cantos:
        rotulos = []
        for chave, (relx, rely, ancora) in {"nw": (0, 0, "nw"), "ne": (1, 0, "ne"),
                                            "sw": (0, 1, "sw"), "se": (1, 1, "se")}.items():
            r = ctk.CTkLabel(c, text="", image=cantos[chave], fg_color="transparent", width=20, height=20)
            r.place(relx=relx, rely=rely, anchor=ancora)
            rotulos.append(r)
        # depois que o conteúdo do cartão for montado, os cantos sobem para a frente
        c.after_idle(lambda: [r.lift() for r in rotulos if r.winfo_exists()])
    return c


def barra(pai, valor=0.0, cor=ACENTO, altura=6, largura=200):
    b = ctk.CTkProgressBar(pai, height=altura, width=largura, corner_radius=0, border_width=0,
                           fg_color="#21160F", progress_color=cor)
    b.set(max(0.0, min(1.0, valor)))
    return b


def caixa(pai, texto, variavel, **kw):
    return ctk.CTkCheckBox(pai, text=texto, variable=variavel, corner_radius=0, border_width=1,
                           checkbox_width=17, checkbox_height=17, fg_color=VINHO, hover_color=VINHO_CLARO,
                           border_color=ORNATO, checkmark_color=TEXTO, text_color=TEXTO,
                           font=fonte("corpo", 13), **kw)


def rolavel(pai, **kw):
    kw.setdefault("fg_color", "transparent")
    return ctk.CTkScrollableFrame(pai, corner_radius=0, scrollbar_button_color=LINHA,
                                  scrollbar_button_hover_color=ORNATO, **kw)


def separador(pai):
    return ctk.CTkFrame(pai, height=1, fg_color=LINHA, corner_radius=0)


class Alternador(ctk.CTkButton):
    """Botão quadrado de dois estados (ligado/desligado), no lugar da chave em pílula."""

    def __init__(self, pai, ligado: bool, comando, textos=("ligado", "desligado"), largura=108):
        self._textos = textos
        self._ao_clicar = comando
        super().__init__(pai, text="", width=largura, height=28, corner_radius=RAIO, border_width=1,
                         font=fonte("titulo", 12), command=self._clique)
        self.definir(ligado)

    def definir(self, ligado: bool):
        self.ligado = bool(ligado)
        if self.ligado:
            self.configure(text=self._textos[0], fg_color=ACENTO_FUNDO, hover_color="#3A1212",
                           border_color=ACENTO, text_color=ACENTO)
        else:
            self.configure(text=self._textos[1], fg_color=PAINEL2, hover_color="#302014",
                           border_color=LINHA, text_color=FRACO)

    def _clique(self):
        self._ao_clicar(self, not self.ligado)


class Letreiro(tk.Canvas):
    """
    Faixa com o fundo de TV de tubo e um texto em fraktur por cima, com um filete
    dourado embaixo. Usada no título das páginas e no nome do programa.
    """

    def __init__(self, pai, titulo, subtitulo="", tamanho=30, altura=None, cor=TEXTO):
        self._esc = escala(pai)
        self._altura = int((altura or (tamanho * 2.4 + (26 if subtitulo else 0))) * self._esc)
        super().__init__(pai, height=self._altura, bg=FUNDO, highlightthickness=0, bd=0)
        self.titulo, self.subtitulo, self.tamanho, self.cor = titulo, subtitulo, tamanho, cor
        self._foto = None
        self.bind("<Configure>", lambda e: self._desenhar())

    def _desenhar(self):
        from PIL import ImageTk
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        self.delete("all")
        self._foto = ImageTk.PhotoImage(textura_crt(w, h))
        self.create_image(0, 0, image=self._foto, anchor="nw")
        e = self._esc
        x = int(14 * e)
        tam = int(self.tamanho * e)
        y = int(self.tamanho * 1.1 * e)
        fam = familia("gotico")
        # sombra vinho e depois o texto: o "brilho" do letreiro
        self.create_text(x + 2, y + 2, text=self.titulo, anchor="w", fill="#000000", font=(fam, -tam))
        self.create_text(x, y, text=self.titulo, anchor="w", fill=self.cor, font=(fam, -tam))
        largura_titulo = tkfont.Font(family=fam, size=-tam).measure(self.titulo)
        yl = int(y + tam * 0.72)
        self.create_line(x, yl, x + largura_titulo, yl, fill=ACENTO, width=1)
        self.create_polygon(x + largura_titulo + 2, yl, x + largura_titulo + 8, yl - 4,
                            x + largura_titulo + 14, yl, x + largura_titulo + 8, yl + 4, fill=ACENTO, outline="")
        self.create_line(x + largura_titulo + 18, yl, w - x, yl, fill=ORNATO, width=1)
        fim = yl + int(10 * e)
        if self.subtitulo:
            # o subtítulo não passa por baixo dos botões do topo (que ficam à direita, na linha do título)
            self.create_text(x, yl + int(8 * e), text=self.subtitulo, anchor="nw", fill=SUAVE,
                             font=(familia("corpo"), -int(14 * e)), width=w - 2 * x, tags="sub")
            caixa = self.bbox("sub")
            if caixa:
                fim = caixa[3] + int(12 * e)
        if abs(fim - h) > 2:  # a altura acompanha o texto (que quebra conforme a largura)
            self.configure(height=fim)


def ao_clicar(widget, funcao):
    """Liga o clique num quadro e em tudo dentro dele."""
    widget.bind("<Button-1>", lambda e: funcao())
    for filho in widget.winfo_children():
        ao_clicar(filho, funcao)


def cor_do_uso(fracao: float) -> str:
    if fracao >= 0.9:
        return ACENTO
    if fracao >= 0.75:
        return LARANJA
    return NORMAL


# ---------------------------------------------------------------- gráficos (desenhados à mão)
class _Tela(tk.Canvas):
    """Canvas que redesenha quando muda de tamanho e conhece a escala da tela."""

    def __init__(self, pai, largura, altura, fundo=PAINEL):
        self.e = escala(pai)
        super().__init__(pai, width=int(largura * self.e), height=int(altura * self.e), bg=fundo,
                         highlightthickness=0, bd=0)
        self.bind("<Configure>", lambda ev: self.desenhar())

    def px(self, v):
        return int(v * self.e)

    def letra(self, tipo, tamanho):
        return (familia(tipo), -self.px(tamanho))

    def desenhar(self):
        pass


class Anel(_Tela):
    """Medidor em arco de 270 graus (como o ícone): trilho marrom e a parte usada colorida."""

    def __init__(self, pai, tamanho=124, fundo=PAINEL):
        self.fracao, self.valor, self.legenda = 0.0, "—", ""
        super().__init__(pai, tamanho, tamanho, fundo)

    def definir(self, fracao, valor, legenda=""):
        self.fracao = max(0.0, min(1.0, fracao or 0.0))
        self.valor, self.legenda = valor, legenda
        self.desenhar()

    def desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        lado = min(w, h)
        if lado < 20:
            return
        grossura = max(6, lado * 0.09)
        m = grossura / 2 + 2
        caixa = ((w - lado) / 2 + m, (h - lado) / 2 + m, (w + lado) / 2 - m, (h + lado) / 2 - m)
        self.create_arc(caixa, start=225, extent=-270, style="arc", outline=LINHA, width=grossura)
        if self.fracao > 0:
            self.create_arc(caixa, start=225, extent=-270 * self.fracao, style="arc",
                            outline=cor_do_uso(self.fracao), width=grossura)
        cx, cy = w / 2, h / 2
        self.create_text(cx, cy - lado * 0.04, text=self.valor, fill=TEXTO,
                         font=(familia("numero"), -int(lado * 0.24)))
        if self.legenda:
            self.create_text(cx, cy + lado * 0.2, text=self.legenda, fill=SUAVE,
                             font=(familia("corpo"), -int(lado * 0.095)))


class Grafico(_Tela):
    """Histórico em área (0 a 100%): linhas de 25 em 25, a curva e o ponto de agora."""

    def __init__(self, pai, largura=300, altura=70, fundo=PAINEL, segundos=180):
        self.valores, self.segundos = [], segundos
        super().__init__(pai, largura, altura, fundo)

    def definir(self, valores):
        self.valores = list(valores)
        self.desenhar()

    def desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 30 or h < 20:
            return
        esq, base, topo = self.px(28), h - self.px(14), self.px(4)
        alt = base - topo
        for pct in (0, 50, 100):
            y = base - alt * pct / 100
            self.create_line(esq, y, w, y, fill=LINHA, dash=(1, 3) if pct else ())
            self.create_text(esq - self.px(4), y, text=f"{pct}%", anchor="e", fill=FRACO, font=self.letra("corpo", 9))
        self.create_text(esq, h, text=f"{self.segundos // 60} min atrás", anchor="sw", fill=FRACO,
                         font=self.letra("corpo", 9))
        self.create_text(w, h, text="agora", anchor="se", fill=FRACO, font=self.letra("corpo", 9))
        v = self.valores
        if len(v) < 2:
            return
        total = max(len(v), 2)
        passo = (w - esq - self.px(4)) / (total - 1)
        pontos = [(esq + i * passo, base - alt * min(max(x, 0), 100) / 100) for i, x in enumerate(v)]
        cor = cor_do_uso(v[-1] / 100)
        area = [(pontos[0][0], base)] + pontos + [(pontos[-1][0], base)]
        self.create_polygon([c for p in area for c in p], fill=ACENTO_FUNDO, outline="")
        self.create_line([c for p in pontos for c in p], fill=cor, width=max(1, self.px(1.6)), smooth=True)
        x, y = pontos[-1]
        r = self.px(3)
        self.create_oval(x - r, y - r, x + r, y + r, fill=cor, outline=PAINEL)


CORES_PARTES = ["#E5474F", "#B3121B", "#8A0A12", "#C9732C", "#8C6447", "#6E4A32"]


class Composicao(_Tela):
    """Barra dividida em partes coloridas, com a legenda embaixo (nome e tamanho)."""

    def __init__(self, pai, largura=600, altura=96, fundo=PAINEL):
        self.partes, self.formatar = [], str
        super().__init__(pai, largura, altura, fundo)

    def definir(self, partes, formatar):
        """partes: [(nome, valor, tipo)], tipo "programa", "outros", "windows" ou "livre"."""
        self.partes, self.formatar = partes, formatar
        self.desenhar()

    def _cor(self, i, tipo):
        return {"outros": "#4A3020", "windows": "#33221A", "livre": LINHA}.get(tipo, CORES_PARTES[i % len(CORES_PARTES)])

    def desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        total = sum(v for _, v, _ in self.partes)
        if w < 50 or not total:
            return
        alt_barra = self.px(18)
        x = 0
        for i, (nome, valor, tipo) in enumerate(self.partes):
            largura = w * valor / total
            if largura >= 1:
                self.create_rectangle(x, 0, x + largura - (self.px(2) if largura > 4 else 0), alt_barra,
                                      fill=self._cor(i, tipo), outline="")
            x += largura
        # legenda em colunas
        y, x = alt_barra + self.px(12), 0
        coluna = max(self.px(190), w / 5 if w > self.px(1100) else w / 4)
        for i, (nome, valor, tipo) in enumerate(self.partes):
            if x + coluna > w + 1:
                x, y = 0, y + self.px(22)
            q = self.px(10)
            self.create_rectangle(x, y, x + q, y + q, fill=self._cor(i, tipo), outline="")
            texto = nome if len(nome) <= 24 else nome[:22] + "…"
            self.create_text(x + q + self.px(6), y + q / 2, text=texto, anchor="w", fill=SUAVE if tipo != "programa" else TEXTO,
                             font=self.letra("corpo", 11))
            self.create_text(x + coluna - self.px(14), y + q / 2, text=self.formatar(valor), anchor="e", fill=SUAVE,
                             font=self.letra("numero", 11))
            x += coluna
        necessario = y + self.px(22)
        if abs(necessario - h) > 2:
            self.configure(height=necessario)
