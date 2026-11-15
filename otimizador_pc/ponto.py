# -*- coding: utf-8 -*-
"""
Ponto de restauração do Windows, conferido de verdade.

Problemas da versão 1 que isto resolve:
- O Windows só cria UM ponto a cada 24 h. Nesse caso o Checkpoint-Computer
  dá só um aviso, sai com "sucesso", e o programa dizia "criado" sem ter
  criado nada. Agora: a trava das 24 h é tirada durante a criação (e volta
  como estava), e contamos os pontos antes e depois.
- Com a Proteção do Sistema desligada, o programa só mandava abrir o Painel
  de Controle. Agora ele percebe e oferece ligar.
"""

import os

from otimizador_pc.sistema import REG_DWORD

CHAVE_SR = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
FREQUENCIA = "SystemRestorePointCreationFrequency"

SCRIPT_CRIAR = (
    "$antes = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "try { Checkpoint-Computer -Description 'Otimizador PC' -RestorePointType MODIFY_SETTINGS "
    "-ErrorAction Stop -WarningAction SilentlyContinue } "
    "catch { Write-Output $_.Exception.Message; exit 4 }; "
    "$depois = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "if ($depois -gt $antes) { exit 0 } else { exit 3 }"
)


def protecao_ligada(s):
    """True/False pela chave do Windows; None se não deu para saber."""
    politica = s.reg_ler("HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore", "DisableSR")
    if politica and int(politica[0]) == 1:
        return False
    r = s.reg_ler("HKLM", CHAVE_SR, "RPSessionInterval")
    if r is None:
        return None
    return int(r[0]) != 0


def ligar_protecao(s) -> tuple:
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    codigo, saida = s.powershell(f"Enable-ComputerRestore -Drive '{drive}' -ErrorAction Stop", timeout=120)
    return (True, "ok") if codigo == 0 else (False, saida.strip()[:300])


def criar_ponto(s, log=print) -> str:
    """'ok', 'desligada' (Proteção do Sistema desligada) ou 'falhou'."""
    if protecao_ligada(s) is False:
        return "desligada"

    log("Criando ponto de restauração (pode levar 1 ou 2 minutos)...")
    antes = s.reg_ler("HKLM", CHAVE_SR, FREQUENCIA)
    mexeu = False
    try:
        s.reg_escrever("HKLM", CHAVE_SR, FREQUENCIA, REG_DWORD, 0)
        mexeu = True
    except OSError:
        pass  # sem isso, pode cair na trava das 24 h; a contagem abaixo percebe

    try:
        codigo, saida = s.powershell(SCRIPT_CRIAR, timeout=900)
    finally:
        if mexeu:
            try:
                if antes is None:
                    s.reg_apagar("HKLM", CHAVE_SR, FREQUENCIA)
                else:
                    s.reg_escrever("HKLM", CHAVE_SR, FREQUENCIA, antes[1], antes[0])
            except OSError:
                pass

    if codigo == 0:
        log("Ponto de restauração criado e conferido.")
        return "ok"
    texto = (saida or "").lower()
    if "disabled" in texto or "desativad" in texto or "desabilitad" in texto:
        return "desligada"
    if codigo == 3:
        log("O Windows não criou o ponto de restauração (a contagem não mudou).")
    else:
        log(f"Não deu para criar o ponto de restauração: {saida.strip()[:200]}")
    return "falhou"
