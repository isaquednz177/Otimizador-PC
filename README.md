# Otimizador PC

Limpeza e ajustes do Windows 10 e 11, **todos reversíveis**. Feito para uso pessoal.

## O que ele faz

**Limpeza**: "Analisar" mostra quanto cada item libera, sem apagar nada.
- Temporários do usuário e do Windows (os das últimas 24 h ficam, para não quebrar uma instalação em andamento)
- Relatórios de erro, despejos de tela azul e logs antigos do Windows
- Downloads do Windows Update (o serviço é pausado durante a limpeza e volta depois)
- Cache da Otimização de Entrega (apagado pelo próprio Windows)
- Cache do Chrome, Edge, Brave, Opera, Opera GX e Firefox: só o cache (senhas, histórico e abas ficam), e só com o navegador fechado
- Cache de shaders (DirectX, NVIDIA, AMD e Intel) e de miniaturas
- Limpeza de componentes do Windows (WinSxS, pelo DISM), Lixeira e DNS

**Otimização**: cada ajuste mostra se já está aplicado no seu PC.
- Telemetria, tarefas de telemetria, apps da Loja em segundo plano
- Sugestões e anúncios (Menu Iniciar, tela de bloqueio, Explorador, recomendações do Windows 11)
- Busca do Menu Iniciar sem Bing, Game DVR desligado
- Aceleração do mouse desligada (vale na hora)
- Plano de energia Alto desempenho (se o PC esconde esse plano, ele cria uma cópia e apaga ao reverter)
- Windows Search, SysMain e hibernação

**Inicialização**: liga e desliga os programas que abrem com o Windows, do mesmo jeito que o Gerenciador de Tarefas. Nada é apagado.

**Reverter**: volta cada ajuste para como estava antes.

## Segurança

- **O estado original é gravado no disco antes de cada mudança.** Se o programa fechar no meio, nada se perde.
- **Reverter volta ao que estava, e não ao "padrão":** uma tarefa que você já tinha desligado continua desligada; um serviço com início atrasado volta atrasado.
- Se uma reversão falhar, ela continua guardada para você tentar de novo.
- Antes de aplicar, ele cria um ponto de restauração **e confere se foi criado de verdade**. Se a Proteção do Sistema estiver desligada, ele oferece ligar.
- A limpeza só apaga dentro de uma lista fechada de pastas. Nunca apaga a pasta do Windows, Arquivos de Programas, a pasta do usuário, Documentos, Downloads etc., e nunca segue atalhos de pasta (junções).
- Os serviços só são mexidos se estiverem numa lista fechada. Serviços de inicialização do sistema nunca são tocados.
- O backup fica em `%APPDATA%\OtimizadorPC\backup_estado.json`, e o registro de cada sessão em `%APPDATA%\OtimizadorPC\logs`.

## Como abrir

Precisa do [Python](https://www.python.org/downloads/) 3.10 ou mais novo, com "Add python.exe to PATH" marcado.

1. Clique duas vezes no **`executar.bat`**. Na primeira vez ele instala o `customtkinter`.
2. Aceite o aviso do Windows (Administrador). Se recusar, o programa abre só para olhar.

### Gerar o .exe

Clique duas vezes no **`gerar_exe.bat`**. Ele roda os testes e só gera o `dist\OtimizadorPC.exe` se todos passarem.
O `.exe` não tem assinatura digital, então o Controle de Aplicativos Inteligente do Windows 11 pode bloqueá-lo. Nesse caso, use o `executar.bat`.

## Para quem mexe no código

```
python -m unittest discover -s tests
```

Os testes usam um Windows falso (`tests/falso.py`), então não mudam nada no PC.

| Arquivo | Papel |
|---|---|
| `otimizador_pc/sistema.py` | tudo o que fala com o Windows (lê só o que não muda com o idioma) |
| `otimizador_pc/ajustes.py` | os ajustes e o motor que guarda o original antes |
| `otimizador_pc/limpeza.py` | o que limpar, análise e limpeza |
| `otimizador_pc/seguranca.py` | pastas proibidas e atalhos de pasta |
| `otimizador_pc/backup.py` | o arquivo de backup e a conversão do formato da versão 1 |
| `otimizador_pc/ponto.py` | ponto de restauração conferido |
| `otimizador_pc/inicializacao.py` | programas que abrem com o Windows |
| `otimizador_pc/interface.py` | a janela |

**Ajuste novo:** acrescente em `AJUSTES` (`ajustes.py`). O teste reclama se o mesmo passo aparecer em dois ajustes.
**Item de limpeza novo:** acrescente em `ITENS` (`limpeza.py`), com as pastas como `Alvo`.

## Vindo da versão 1

Na primeira vez, o backup antigo é convertido sozinho, e uma cópia do original fica em `backup_estado.v1.json`. O que a versão 1 aplicou aparece na aba Reverter.
A versão 1.1 **apagava** os programas da inicialização. Eles aparecem na aba Inicialização com o botão "restaurar".

**Não use mais a versão antiga depois de abrir a 2.0.** Ela não entende o formato novo do backup e pode gravar por cima dele.
