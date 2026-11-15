# -*- coding: utf-8 -*-
"""
Travas de segurança da limpeza.

1. Só se limpa DENTRO de pastas da lista do limpeza.py, e nunca uma destas
   pastas em si (C:\\, Windows, System32, Arquivos de Programas, a pasta do
   usuário, Área de Trabalho, Documentos, Downloads...).
2. Atalhos de pasta (junções e links simbólicos) nunca são seguidos nem
   apagados: uma junção dentro do %TEMP% pode apontar para os seus Documentos.
"""

import os
import stat

FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _normal(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def pastas_proibidas(ambiente=None) -> set:
    amb = os.environ if ambiente is None else ambiente
    sistema = amb.get("SystemRoot", r"C:\Windows")
    perfil = amb.get("USERPROFILE", "")
    lista = {
        amb.get("SystemDrive", "C:") + "\\",
        sistema,
        os.path.join(sistema, "System32"),
        os.path.join(sistema, "SysWOW64"),
        os.path.join(sistema, "WinSxS"),
        amb.get("ProgramFiles", r"C:\Program Files"),
        amb.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        amb.get("ProgramData", r"C:\ProgramData"),
        amb.get("APPDATA", ""),
        amb.get("LOCALAPPDATA", ""),
        perfil,
    }
    if perfil:
        for sub in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive"):
            lista.add(os.path.join(perfil, sub))
    return {_normal(p) for p in lista if p}


def eh_link(st) -> bool:
    """True para link simbólico, junção ou qualquer ponto de nova análise."""
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def caminho_e_seguro(pasta: str, ambiente=None) -> bool:
    """
    True só se a pasta existe, é uma pasta de verdade (não um atalho), não está
    na lista proibida e não é a raiz de um disco.
    """
    if not pasta:
        return False
    p = _normal(pasta)
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if eh_link(st) or not stat.S_ISDIR(st.st_mode):
        return False
    if not os.path.splitdrive(p)[1].strip("\\/"):
        return False
    return p not in pastas_proibidas(ambiente)


def dentro_de(caminho: str, pasta: str) -> bool:
    """True se `caminho` fica dentro de `pasta` (e não é a própria pasta)."""
    c, p = _normal(caminho), _normal(pasta)
    return c != p and c.startswith(p.rstrip("\\/") + os.sep)
