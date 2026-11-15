# -*- coding: utf-8 -*-
"""
O arquivo que guarda como o Windows estava antes de cada ajuste.

Formato 2:
{
  "versao": 2,
  "ajustes": {
    "<id do ajuste>": {
      "nome": "...", "data": "dd/mm/aaaa hh:mm",
      "passos": {
        "<chave do passo>": {"classe": "registro", "params": {...}, "original": {...}}
      }
    }
  },
  "inicializacao_removida": { ... itens que a versão 1.1 APAGOU do registro ... }
}

Cuidados:
- Gravação atômica: escreve num arquivo temporário e troca de uma vez. Se o
  PC desligar no meio, fica o arquivo antigo inteiro, nunca um pela metade.
- Arquivo corrompido NÃO é sobrescrito: ele é renomeado para
  backup_estado.corrompido-<data>.json e o programa avisa.
- O formato da versão 1 (o do GitHub e o da 1.1) é convertido na primeira
  abertura, e uma cópia do original fica em backup_estado.v1.json.
"""

import json
import os
from datetime import datetime

VERSAO = 2

# Como o Windows vem de fábrica: usado só para converter backups da versão 1,
# que não guardavam o "início atrasado".
ATRASADO_PADRAO = {"WSearch": True}


def vazio() -> dict:
    return {"versao": VERSAO, "ajustes": {}, "inicializacao_removida": {}, "servicos_terceiros": {}}


def migrar_v1(antigo: dict) -> dict:
    """Converte o backup da versão 1/1.1 para o formato 2, sem perder nada."""
    novo = vazio()
    for tid, t in (antigo.get("tweaks") or {}).items():
        passos = {}
        for r in t.get("registros") or []:
            chave = f"reg:{r['hive']}\\{r['caminho']}\\{r['nome']}"
            passos[chave] = {
                "classe": "registro",
                "params": {"hive": r["hive"], "caminho": r["caminho"], "nome": r["nome"],
                           "tipo": r.get("tipo") or 4, "valor": None},
                "original": {"existia": bool(r.get("existia")), "valor": r.get("valor"),
                             "tipo": r.get("tipo")},
            }
        for s in t.get("servicos") or []:
            start = int(s["start"])
            passos[f"svc:{s['nome']}"] = {
                "classe": "servico",
                "params": {"nome": s["nome"]},
                "original": {"start": start,
                             "atrasado": start == 2 and ATRASADO_PADRAO.get(s["nome"], False),
                             # a versão 1 não guardava se estava rodando; automático quase sempre está
                             "rodando": start == 2},
            }
        # A versão 1 só guardava as tarefas que ELA desligou (estavam ligadas).
        for tarefa in t.get("tarefas") or []:
            passos[f"task:{tarefa}"] = {
                "classe": "tarefa", "params": {"caminho": tarefa}, "original": {"ativa": True},
            }
        if t.get("comando"):  # só a hibernação usava "comando"
            passos["hibernacao"] = {"classe": "hibernacao", "params": {}, "original": {"ligada": True}}
        if passos:
            novo["ajustes"][tid] = {"nome": t.get("nome", tid), "data": t.get("data", ""),
                                    "passos": passos}
    for chave, item in (antigo.get("inicializacao") or {}).items():
        novo["inicializacao_removida"][chave] = item
    return novo


def _valido_v2(dados) -> bool:
    return (isinstance(dados, dict) and dados.get("versao") == VERSAO
            and isinstance(dados.get("ajustes"), dict))


class Backup:
    """Carrega e grava o arquivo. `aviso` diz ao usuário se algo foi recuperado."""

    def __init__(self, arquivo: str):
        self.arquivo = arquivo
        self.aviso = None
        self.dados = self._carregar()

    def _carregar(self) -> dict:
        if not os.path.exists(self.arquivo):
            return vazio()
        try:
            with open(self.arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError):
            dados = None

        if _valido_v2(dados):
            dados.setdefault("inicializacao_removida", {})
            return dados

        if isinstance(dados, dict) and isinstance(dados.get("tweaks"), dict):
            copia = os.path.join(os.path.dirname(self.arquivo), "backup_estado.v1.json")
            if not os.path.exists(copia):
                self._gravar_bruto(copia, dados)
            novo = migrar_v1(dados)
            self._gravar_bruto(self.arquivo, novo)
            self.aviso = ("O backup da versão antiga foi convertido para o formato novo "
                          f"(cópia do original em {copia}).")
            return novo

        # Corrompido ou desconhecido: guarda de lado em vez de apagar.
        marca = datetime.now().strftime("%Y%m%d-%H%M%S")
        destino = os.path.join(os.path.dirname(self.arquivo), f"backup_estado.corrompido-{marca}.json")
        try:
            os.replace(self.arquivo, destino)
            self.aviso = (f"O arquivo de backup estava danificado e foi guardado em {destino}. "
                          "Os ajustes de antes não podem ser desfeitos por aqui; use o ponto de "
                          "restauração do Windows se precisar.")
        except OSError:
            self.aviso = "O arquivo de backup estava danificado e não pôde ser movido."
        return vazio()

    @staticmethod
    def _gravar_bruto(caminho: str, dados: dict) -> None:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        temporario = caminho + ".tmp"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporario, caminho)

    def salvar(self) -> None:
        self._gravar_bruto(self.arquivo, self.dados)
