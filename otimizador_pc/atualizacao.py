# -*- coding: utf-8 -*-
"""
Avisa quando sai versão nova: lê a última "Release" do repositório no GitHub.
Uma consulta por vez que o programa abre, sem mandar nada além do pedido.
Sem internet, ou se o GitHub não responder, simplesmente não avisa.
"""

import json
import re
import urllib.request

REPOSITORIO = "isaquednz177/Otimizador-PC"
API = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"


def versao(texto: str) -> tuple:
    """'v2.10.1' -> (2, 10, 1)."""
    return tuple(int(n) for n in re.findall(r"\d+", texto or "")[:3])


def tem_nova(atual: str, publicada: str) -> bool:
    return bool(versao(publicada)) and versao(publicada) > versao(atual)


def verificar(atual: str, timeout: float = 5):
    """(versão nova, link) ou None."""
    try:
        pedido = urllib.request.Request(API, headers={"User-Agent": "OtimizadorPC",
                                                      "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            dados = json.loads(resposta.read(200_000).decode("utf-8"))
    except Exception:
        return None
    tag = dados.get("tag_name") or ""
    link = dados.get("html_url") or f"https://github.com/{REPOSITORIO}/releases"
    if not link.startswith("https://github.com/"):
        return None
    return (tag.lstrip("vV"), link) if tem_nova(atual, tag) else None
