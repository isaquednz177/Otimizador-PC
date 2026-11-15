# -*- coding: utf-8 -*-
"""
Modo jogo: antes de jogar, fecha os programas que você escolheu e liga o Alto
desempenho; ao sair, volta o plano de energia de antes e reabre os programas.

O estado fica no backup ("modo_jogo") ANTES de cada mudança: se o PC desligar
no meio, na próxima vez o programa avisa e "sair do modo jogo" desfaz.
Os programas reabertos passam pelo Explorador, para NÃO abrirem como
Administrador (o otimizador roda como Administrador).
"""

import os
import subprocess

from otimizador_pc.ajustes import PlanoEnergia
from otimizador_pc.util import agora_texto


def ativo(backup) -> bool:
    return bool(backup.dados.get("modo_jogo", {}).get("ativo"))


def _abrir_como_usuario(caminho: str) -> bool:
    try:
        subprocess.Popen(["explorer.exe", caminho])
        return True
    except OSError:
        return False


def entrar(s, backup, preferencias: dict, grupos: list, log=print, energia_ja_aplicada=False) -> bool:
    """grupos = leitura atual dos processos (processos.Monitor().ler())."""
    if ativo(backup):
        log("O modo jogo já está ligado.")
        return False
    estado = {"ativo": True, "desde": agora_texto(), "energia": None, "fechados": []}
    backup.dados["modo_jogo"] = estado
    backup.salvar()

    if preferencias.get("desempenho") and not energia_ja_aplicada:
        plano = PlanoEnergia()
        original = plano.capturar(s)
        if original:
            guardado = {"original": original}
            estado["energia"] = guardado
            backup.salvar()  # o plano de antes vai para o disco antes de trocar
            ok, msg = plano.aplicar(s, guardado)
            backup.salvar()
            log(f"   {'OK ' if ok else '[erro]'} plano de energia: {msg}")

    escolhidos = {e.lower() for e in preferencias.get("fechar", [])}
    for g in grupos:
        if g.exe in escolhidos and g.pode_fechar:
            ok, _ = s.encerrar(g.pids)
            estado["fechados"].append({"exe": g.exe, "nome": g.nome, "caminho": g.caminho})
            backup.salvar()
            log(f"   {'OK ' if ok else '[erro]'} fechando {g.nome}")
    log("Modo jogo ligado. Bom jogo!")
    return True


def sair(s, backup, preferencias: dict, log=print, abrir=_abrir_como_usuario) -> bool:
    estado = backup.dados.get("modo_jogo")
    if not estado:
        log("O modo jogo não está ligado.")
        return False
    tudo_ok = True
    energia = estado.get("energia")
    if energia:
        ok, msg = PlanoEnergia().reverter(s, energia["original"], energia)
        tudo_ok = tudo_ok and ok
        log(f"   {'OK ' if ok else '[erro]'} plano de energia: {msg}")
    if preferencias.get("reabrir", True):
        for f in estado.get("fechados", []):
            caminho = f.get("caminho") or ""
            if caminho and os.path.exists(caminho):
                log(f"   {'OK ' if abrir(caminho) else '[erro]'} reabrindo {f.get('nome') or f.get('exe')}")
    estado["fechados"] = []  # já reabertos: não reabrir de novo se precisar tentar sair outra vez
    if tudo_ok:
        backup.dados.pop("modo_jogo", None)
    backup.salvar()  # se o plano não voltou, o estado fica para tentar de novo
    log("Modo jogo desligado." if tudo_ok else "O plano de energia não voltou; tente sair de novo.")
    return tudo_ok
