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
  inicializacao.py  programas, serviços e tarefas que abrem com o Windows
  processos.py      o que está gastando memória e processador
  hardware.py       memória, discos, vídeo, bateria e atualizações (só lê)
  modo_jogo.py      fecha o escolhido e liga o Alto desempenho; ao sair, volta tudo
  atualizacao.py    avisa quando sai versão nova no GitHub
  config.py         preferências da pessoa
  espaco.py         o que ocupa o disco (só mede)
  boot.py           tempo para ligar, pelo registro do Windows
  controle.py       cancelar e progresso das tarefas longas
  info.py           RAM e disco
  registro.py       registro de atividades (tela + arquivo)
  tema.py           cores, fontes e peças da tela
  interface.py      a janela (menu lateral, barra de status)
  telas/            uma página por arquivo
"""

APP_NOME = "Otimizador PC"
APP_VERSAO = "2.2"
