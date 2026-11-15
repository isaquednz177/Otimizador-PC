# -*- coding: utf-8 -*-
"""
Tradução dos números para quem não entende de computador.

Cada função recebe um número e devolve (nível, título curto, frase).
nível: "bom", "atencao" ou "ruim" (a tela escolhe a cor por ele).
"""

GB = 1 << 30


def memoria(pct):
    if pct is None:
        return "bom", "—", ""
    if pct >= 95:
        return "ruim", "cheia", "A memória acabou: o PC fica lento e os programas demoram para responder. Feche o que não está usando."
    if pct >= 85:
        return "atencao", "quase cheia", "Está quase sem espaço para abrir mais coisas. Se o PC estiver lento, feche alguns programas."
    if pct >= 70:
        return "bom", "bem usada", "Normal: o Windows aproveita a memória livre para deixar tudo mais rápido."
    return "bom", "tranquila", "Tem bastante espaço para abrir mais programas."


def processador(media):
    """`media` = média dos últimos minutos (um pico rápido é normal)."""
    if media is None:
        return "bom", "—", ""
    if media >= 75:
        return "ruim", "sobrecarregado", "Está trabalhando no limite há um tempo: tudo fica lento. Veja quem mais usa logo abaixo."
    if media >= 35:
        return "atencao", "ocupado", "Está trabalhando bastante. Normal durante jogos, vídeos ou instalações."
    return "bom", "folgado", "Está com folga: não é ele que deixa o PC lento agora."


def disco(livre, total):
    if not total:
        return "bom", "—", ""
    fracao = livre / total
    if fracao < 0.10 or livre < 10 * GB:
        return "ruim", "quase cheio", "Falta espaço: o Windows pode não conseguir se atualizar e tudo fica mais lento. Libere espaço."
    if fracao < 0.20:
        return "atencao", "enchendo", "Ainda dá, mas vale apagar o que não usa antes de encher."
    return "bom", "com espaço", "Tem espaço de sobra."


def ligar(segundos):
    if segundos is None:
        return "bom", "—", ""
    if segundos > 90:
        return "ruim", "lento", "Demora bastante para ligar. Desligar programas que abrem com o Windows costuma ajudar muito."
    if segundos > 45:
        return "atencao", "normal", "Um tempo comum. Dá para melhorar desligando programas que abrem sozinhos."
    return "bom", "rápido", "Liga rápido."


def resumo(mem_pct, cpu_media, livre, total) -> str:
    """Uma frase sobre o PC agora, começando pelo que mais pesa."""
    problemas = []
    n, _, _ = memoria(mem_pct)
    if n != "bom":
        problemas.append("a memória está " + ("cheia" if n == "ruim" else "quase cheia"))
    n, _, _ = processador(cpu_media)
    if n == "ruim":
        problemas.append("o processador está sobrecarregado")
    n, _, _ = disco(livre, total)
    if n != "bom":
        problemas.append("o disco está " + ("quase cheio" if n == "ruim" else "enchendo"))
    if not problemas:
        return "Seu PC está tranquilo agora."
    if len(problemas) == 1:
        return f"Seu PC pode estar lento agora: {problemas[0]}."
    return f"Seu PC pode estar lento agora: {', '.join(problemas[:-1])} e {problemas[-1]}."


# Termos que aparecem no programa, explicados em uma ou duas frases.
GLOSSARIO = [
    ("Memória (RAM)", "Onde ficam os programas que estão abertos. Quanto mais programas e abas, mais memória. "
                      "Quando ela enche, o PC fica lento. Não é o mesmo que o espaço no disco."),
    ("Processador (CPU)", "O \"cérebro\" do PC, que faz as contas. Quando ele trabalha no limite por muito tempo, "
                          "tudo demora para responder."),
    ("Disco (SSD ou HD)", "Onde ficam guardados os arquivos, fotos, jogos e o próprio Windows. SSD é o tipo moderno e "
                          "rápido; HD é o antigo, mais lento."),
    ("Programas que abrem com o Windows", "Programas que começam sozinhos quando o PC liga. Cada um deixa o PC "
                                          "demorar mais para ficar pronto e usa memória mesmo sem você abrir."),
    ("Serviço", "Um programa que roda escondido, sem janela (por exemplo, o que atualiza o navegador). "
                "Deixar em \"só quando precisa\" faz ele abrir apenas quando o programa dono pedir."),
    ("Tarefa automática", "Algo que o Windows roda sozinho em certos horários, como os atualizadores dos programas."),
    ("Cache", "Cópias guardadas para abrir mais rápido da próxima vez. Apagar libera espaço, e o programa refaz "
              "o que precisar."),
    ("Arquivos temporários", "Restos que os programas deixam enquanto trabalham. Na maioria das vezes, podem ser apagados."),
    ("Driver", "O programa que faz uma peça (placa de vídeo, som, Wi-Fi) funcionar no Windows. Driver novo costuma "
               "corrigir problemas e deixar jogos mais rápidos."),
    ("Ponto de restauração", "Uma \"foto\" das configurações do Windows. Se algo der errado, dá para voltar o "
                             "Windows para como estava naquela hora."),
    ("Administrador", "Permissão para mudar configurações do Windows. O programa pede quando abre; sem ela, ele só "
                      "consegue olhar."),
    ("Telemetria", "Informações de uso que o Windows manda para a Microsoft."),
    ("Plano de energia", "Diz ao PC se ele deve economizar energia ou correr mais. \"Alto desempenho\" corre mais e "
                         "gasta mais bateria."),
    ("Dual channel", "Quando há dois pentes de memória iguais, eles trabalham juntos e a memória fica bem mais rápida."),
]

GLOSSARIO_DICT = dict(GLOSSARIO)
