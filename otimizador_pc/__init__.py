# -*- coding: utf-8 -*-
"""
Otimizador PC: limpeza e ajustes reversíveis do Windows 10 e 11.

Mapa:
  sistema.py        tudo o que fala com o Windows (registro, serviços, tarefas...)
  seguranca.py      travas da limpeza (pastas proibidas, atalhos de pasta)
  limpeza.py        o que limpar, análise e limpeza
  ajustes.py        ajustes reversíveis e o motor que guarda o original antes
  backup.py         o arquivo com o estado original (e a conversão da versão 1)
  ponto.py          ponto de restauração conferido de verdade
  inicializacao.py  programas que abrem com o Windows
  info.py           RAM e disco
  registro.py       registro de atividades (tela + arquivo)
  interface.py      a janela
"""

APP_NOME = "Otimizador PC"
APP_VERSAO = "2.0"
