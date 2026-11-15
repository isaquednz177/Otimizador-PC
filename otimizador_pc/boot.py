# -*- coding: utf-8 -*-
"""
Quanto tempo o PC leva para ligar, pelo registro do próprio Windows
(Diagnostics-Performance, evento 100). Precisa de Administrador.

BootTime = do ligar até a área de trabalho ficar pronta para usar.
MainPathBootTime = até aparecer a área de trabalho.
Com a Inicialização Rápida ligada, o "desligar" é uma hibernação e esses
ligamentos não entram no registro; só os ligamentos completos e reinícios.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

LOG = "Microsoft-Windows-Diagnostics-Performance/Operational"


@dataclass
class Ligamento:
    quando: datetime        # hora local
    total_ms: int           # pronto para usar
    principal_ms: int       # até a área de trabalho
    depois_ms: int          # da área de trabalho até ficar pronto


def ler_eventos(xml: str) -> list:
    """Lê a saída do `wevtutil qe ... /f:xml`. Devolve do mais antigo para o mais novo."""
    saida = []
    for ev in re.findall(r"<Event\b.*?</Event>", xml or "", re.S):
        quando = re.search(r"<TimeCreated\s+SystemTime=['\"]([^'\"]+)['\"]", ev)
        dados = dict(re.findall(r"<Data Name=['\"](\w+)['\"]>([^<]*)</Data>", ev))
        if not quando or "BootTime" not in dados:
            continue
        texto = quando.group(1)
        m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", texto)
        if not m:
            continue
        utc = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        try:
            saida.append(Ligamento(
                quando=utc.astimezone().replace(tzinfo=None),
                total_ms=int(dados["BootTime"]),
                principal_ms=int(dados.get("MainPathBootTime") or 0),
                depois_ms=int(dados.get("BootPostBootTime") or 0),
            ))
        except ValueError:
            continue
    saida.sort(key=lambda l: l.quando)
    return saida


def ler(s, quantos: int = 40):
    """(lista, erro). erro = texto para a tela, ou None."""
    codigo, saida = s.rodar(["wevtutil", "qe", LOG, "/q:*[System[(EventID=100)]]",
                             f"/c:{quantos}", "/rd:true", "/f:xml"], timeout=60)
    if codigo != 0:
        if "negado" in saida.lower() or "denied" in saida.lower():
            return [], "precisa de Administrador para ler"
        return [], "o Windows não entregou o registro de inicializações"
    lista = ler_eventos(saida)
    if not lista:
        return [], "ainda não há ligamentos completos registrados"
    return lista, None


def datas_dos_ajustes(dados_backup: dict) -> list:
    """Datas em que ajustes foram aplicados (para marcar no gráfico)."""
    datas = []
    for reg in (dados_backup or {}).get("ajustes", {}).values():
        try:
            datas.append(datetime.strptime(reg.get("data", ""), "%d/%m/%Y %H:%M"))
        except ValueError:
            pass
    return sorted(set(datas))


def comparar(lista: list, marco: datetime):
    """Média antes e depois de uma data. None em cada lado com menos de 2 ligamentos."""
    antes = [l.total_ms for l in lista if l.quando < marco]
    depois = [l.total_ms for l in lista if l.quando >= marco]

    def media(v):
        return sum(v) / len(v) if len(v) >= 2 else None
    return media(antes), media(depois), len(antes), len(depois)
