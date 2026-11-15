# -*- coding: utf-8 -*-
"""
Hardware e atualizações: só leitura.

- Memória: quantos pentes, quantos encaixes, tipo (DDR4, DDR5...) e quanto a placa aceita.
  Um pente sozinho numa placa de dois encaixes é o caso mais comum de PC lento que
  um ajuste de software não resolve: um segundo pente igual dobra a memória e liga o
  "dual channel" (o vídeo integrado, que usa a RAM, ganha muito).
- Discos: saúde, desgaste, temperatura e horas ligado (as três últimas só com Administrador).
- Vídeo: idade do driver e o site oficial para baixar o novo.
- Bateria: capacidade de fábrica x capacidade de hoje (relatório do próprio Windows).
- Windows: última atualização instalada e reinício pendente.

A leitura leva uns 20 segundos (o Windows é lento para listar discos e atualizações).
"""

import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime

SCRIPT = r"""
$r = [ordered]@{}
try { $r.pentes = @(Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator, Capacity, Speed, ConfiguredClockSpeed, Manufacturer, PartNumber, SMBIOSMemoryType, FormFactor) } catch {}
try { $r.placa_memoria = @(Get-CimInstance Win32_PhysicalMemoryArray | Where-Object { $_.Use -eq 3 } | Select-Object MemoryDevices, MaxCapacityEx, MaxCapacity) } catch {}
try { $r.cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors) } catch {}
try { $r.video = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, @{n='DriverDate';e={ if ($_.DriverDate) { $_.DriverDate.ToString('yyyy-MM-dd') } }}, PNPDeviceID) } catch {}
try { $r.discos = @(Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType, HealthStatus, Size) } catch {}
try { $r.confiabilidade = @(Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction Stop | Select-Object DeviceId, Wear, Temperature, TemperatureMax, PowerOnHours) } catch {}
try { $r.atualizacoes = @(Get-CimInstance Win32_QuickFixEngineering | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending | Select-Object -First 1 HotFixID, @{n='Data';e={ $_.InstalledOn.ToString('yyyy-MM-dd') }}) } catch {}
try { $r.modelo = @(Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model) } catch {}
$r | ConvertTo-Json -Depth 4 -Compress
"""

TIPO_MEMORIA = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 29: "LPDDR3", 30: "LPDDR4",
                34: "DDR5", 35: "LPDDR5"}
FABRICANTE_VIDEO = {"8086": "Intel", "10DE": "NVIDIA", "1002": "AMD"}
SITE_DRIVER = {
    "Intel": "https://www.intel.com.br/content/www/br/pt/support/detect.html",
    "NVIDIA": "https://www.nvidia.com/pt-br/geforce/drivers/",
    "AMD": "https://www.amd.com/pt/support/download/drivers.html",
}
GB = 1 << 30


@dataclass
class Memoria:
    total: int = 0
    pentes: list = field(default_factory=list)   # [{"local", "tamanho", "velocidade", "fabricante"}]
    encaixes: int = 0
    livres: int = 0
    maximo: int = 0
    tipo: str = ""
    soldada: bool = False


@dataclass
class Relatorio:
    modelo: str = ""
    memoria: Memoria = field(default_factory=Memoria)
    cpu: str = ""
    nucleos: str = ""
    videos: list = field(default_factory=list)    # [{"nome", "fabricante", "driver", "data", "dias", "site"}]
    discos: list = field(default_factory=list)    # [{"nome", "tipo", "saude", "tamanho", "desgaste", "temperatura", "horas"}]
    bateria: dict = None                          # {"fabrica", "hoje", "saude", "ciclos"}
    ultima_atualizacao: date = None
    kb: str = ""
    reinicio_pendente: bool = False
    erro: str = ""


def _lista(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _data(texto):
    try:
        return datetime.strptime(str(texto)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def interpretar(dados: dict, hoje: date = None) -> Relatorio:
    hoje = hoje or date.today()
    r = Relatorio()
    modelo = _lista(dados.get("modelo"))
    if modelo:
        r.modelo = f"{modelo[0].get('Manufacturer') or ''} {modelo[0].get('Model') or ''}".strip()

    m = r.memoria
    for p in _lista(dados.get("pentes")):
        tamanho = int(p.get("Capacity") or 0)
        m.total += tamanho
        m.pentes.append({"local": (p.get("DeviceLocator") or "").strip(), "tamanho": tamanho,
                         "velocidade": int(p.get("ConfiguredClockSpeed") or p.get("Speed") or 0),
                         "fabricante": (p.get("Manufacturer") or "").strip()})
        tipo = TIPO_MEMORIA.get(int(p.get("SMBIOSMemoryType") or 0), "")
        m.tipo = m.tipo or tipo
        if tipo.startswith("LP"):
            m.soldada = True  # LPDDR é sempre soldada na placa
    placas = _lista(dados.get("placa_memoria"))
    if placas:
        m.encaixes = sum(int(p.get("MemoryDevices") or 0) for p in placas)
        kb = max(int(p.get("MaxCapacityEx") or p.get("MaxCapacity") or 0) for p in placas)
        m.maximo = kb * 1024
    m.livres = max(0, m.encaixes - len(m.pentes)) if not m.soldada else 0

    cpus = _lista(dados.get("cpu"))
    if cpus:
        c = cpus[0]
        r.cpu = re.sub(r"\s+", " ", c.get("Name") or "").strip()
        r.nucleos = f"{c.get('NumberOfCores')} núcleos, {c.get('NumberOfLogicalProcessors')} threads"

    for v in _lista(dados.get("video")):
        nome = v.get("Name") or ""
        if "basic" in nome.lower() or "virtual" in nome.lower() or "remote" in nome.lower():
            continue
        ven = re.search(r"VEN_([0-9A-Fa-f]{4})", v.get("PNPDeviceID") or "")
        fab = FABRICANTE_VIDEO.get(ven.group(1).upper(), "") if ven else ""
        d = _data(v.get("DriverDate"))
        r.videos.append({"nome": nome, "fabricante": fab, "driver": v.get("DriverVersion") or "",
                         "data": d, "dias": (hoje - d).days if d else None, "site": SITE_DRIVER.get(fab, "")})

    conf = {str(c.get("DeviceId")): c for c in _lista(dados.get("confiabilidade"))}
    for d in _lista(dados.get("discos")):
        c = conf.get(str(d.get("DeviceId")), {})
        r.discos.append({
            "nome": (d.get("FriendlyName") or "").strip(),
            "tipo": d.get("MediaType") or "", "barramento": d.get("BusType") or "",
            "saude": d.get("HealthStatus") or "", "tamanho": int(d.get("Size") or 0),
            "desgaste": c.get("Wear"), "temperatura": c.get("Temperature") or None,
            "horas": c.get("PowerOnHours"),
        })

    atual = _lista(dados.get("atualizacoes"))
    if atual:
        r.ultima_atualizacao = _data(atual[0].get("Data"))
        r.kb = atual[0].get("HotFixID") or ""
    return r


def ler_bateria_xml(texto: str):
    """{"fabrica", "hoje", "saude" (0..1), "ciclos"} do `powercfg /batteryreport /xml`, ou None."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return None
    for el in raiz.iter():
        if el.tag.split("}")[-1] != "Battery":
            continue
        valores = {filho.tag.split("}")[-1]: (filho.text or "").strip() for filho in el}
        try:
            fabrica = int(valores.get("DesignCapacity") or 0)
            hoje = int(valores.get("FullChargeCapacity") or 0)
        except ValueError:
            continue
        if fabrica > 0 and hoje > 0:
            ciclos = valores.get("CycleCount")
            return {"fabrica": fabrica, "hoje": hoje, "saude": min(hoje / fabrica, 1.0),
                    "ciclos": int(ciclos) if ciclos and ciclos.isdigit() else None}
    return None


def reinicio_pendente(s) -> bool:
    """Só as marcas do Windows Update e do instalador de componentes (as mais confiáveis)."""
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion"
    return ("RebootRequired" in s.reg_subchaves("HKLM", base + r"\WindowsUpdate\Auto Update")
            or "RebootPending" in s.reg_subchaves("HKLM", base + r"\Component Based Servicing"))


def ler(s, ctl=None) -> Relatorio:
    codigo, saida = s.powershell(SCRIPT, timeout=120)
    try:
        dados = json.loads(saida[saida.find("{"):]) if "{" in saida else {}
    except ValueError:
        dados = {}
    r = interpretar(dados)
    if not dados:
        r.erro = "o Windows não respondeu à consulta de hardware"
    if ctl:
        ctl.checar()
    arquivo = os.path.join(tempfile.gettempdir(), "otimizador-bateria.xml")
    codigo, _ = s.rodar(["powercfg", "/batteryreport", "/xml", "/output", arquivo], timeout=60)
    if codigo == 0 and os.path.exists(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8", errors="replace") as f:
                r.bateria = ler_bateria_xml(f.read())
        finally:
            try:
                os.remove(arquivo)
            except OSError:
                pass
    r.reinicio_pendente = reinicio_pendente(s)
    return r


def recomendacoes(r: Relatorio, hoje: date = None) -> list:
    """[(tipo "aviso"/"info", texto, link ou "")]"""
    hoje = hoje or date.today()
    recs = []
    m = r.memoria
    if m.total and m.total <= 8 * GB and m.livres > 0:
        tamanho = m.pentes[0]["tamanho"] // GB if m.pentes else 8
        recs.append(("aviso",
                     f"Só {m.total // GB} GB de memória e {m.livres} encaixe livre. Um segundo pente de "
                     f"{tamanho} GB {m.tipo} igual ao seu dobra a memória e faz os dois trabalharem juntos (dual channel), o que também "
                     "acelera muito o vídeo integrado. É a melhoria que mais faria diferença neste PC. "
                     "(Confira o encaixe livre no manual: em alguns notebooks parte da memória é soldada.)", ""))
    for v in r.videos:
        if v["dias"] is not None and v["dias"] > 180:
            recs.append(("aviso" if v["dias"] > 365 else "info",
                         f"O driver de vídeo ({v['nome']}) é de {v['data']:%m/%Y}, há {v['dias'] // 30} meses. "
                         "Driver novo costuma dar mais FPS e corrigir travamentos em jogos.", v["site"]))
    for d in r.discos:
        if d["saude"] and d["saude"] not in ("Healthy", "Saudável"):
            recs.append(("aviso", f"O Windows diz que o disco {d['nome']} não está saudável ({d['saude']}). "
                                  "Faça cópia dos seus arquivos.", ""))
        if d["desgaste"] is not None and int(d["desgaste"]) >= 80:
            recs.append(("aviso", f"O SSD {d['nome']} está com {d['desgaste']}% de desgaste.", ""))
    if r.bateria and r.bateria["saude"] < 0.7:
        recs.append(("info", f"A bateria segura {r.bateria['saude'] * 100:.0f}% da carga de fábrica.", ""))
    if r.reinicio_pendente:
        recs.append(("aviso", "O Windows está esperando reiniciar para terminar uma atualização.", ""))
    if r.ultima_atualizacao and (hoje - r.ultima_atualizacao).days > 60:
        recs.append(("info", f"A última atualização do Windows foi em {r.ultima_atualizacao:%d/%m/%Y}.",
                     "ms-settings:windowsupdate"))
    return recs
