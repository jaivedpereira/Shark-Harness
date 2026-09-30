# 🦈 Shark Harness

Um **agente de tarefas** com arquitetura **tudo-é-plugin** — inspirado no
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness), mas em Python,
sem dependências obrigatórias e rodando igual no **PC**, no **Linux** e no **Termux**.

## 🙏 Créditos de design

O [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (MIT, *"Everything is a
Plugin"*) é a referência declarada deste projeto. Dele vieram **adaptadas ao tema do Shark**
(azul e preto) as seguintes peças — o código é nosso, em JS/CSS puro, mas a **linguagem
visual** e as ideias são deles:

| o que foi aproveitado | de onde (MIT) |
|---|---|
| **Paleta completa + tokens em três camadas** (`design-platform.css`, 382 variáveis, valores reais) | `packages/client/ui-theme/src/styles/` |
| Escala de raio (4/8/12/16/20/28), movimento (`--ds-ease-in-out`) e pilha de fontes (`--dsw-font-family*`) | `ui-theme/src/styles/base.css` |
| **Barra de rolagem temática de 5px + o portão `@supports not selector(::-webkit-scrollbar)`** | `ui-theme/src/styles/scrollbar.css` |
| Anel de foco de 2px, suprimido no clique de mouse | `ui-theme/src/styles/focus.css` |
| Nomes de token `--dsw-alias-*` / `--ds-*` mantidos iguais aos deles, de propósito | idem |
| **Pílula** de 24px, com anel interno (e não borda) no estado ativo | `Pill.module.css` |
| **Seletor segmentado** com indicador deslizante calculado só por CSS | `SegmentedControl.module.css` |
| **Linha de disclosure**: caixa de 16px, cor que sobe no hover | `DisclosureRow.module.css` |
| **Texto com brilho** varrendo em diagonal (`mask-image` a 105°) | `TextShimmer.module.css` |
| **Indicador de conexão** com borda em `color-mix` do próprio rótulo | `ConnectionIndicator.module.css` |
| **Medidor de contexto** e **navegador de turnos** | `ContextMeter` / `TurnNavigator` |
| **Tecla Enter** configurável (enviar ou quebrar linha) | `EnterBehaviorRow.module.css` |


Ele **programa** (escreve e roda código), **mexe no dispositivo** (shell, arquivos,
notificação, clipboard, screenshot) e **executa tarefas agendadas** sozinho, no
horário que você definir.

O mesmo registry de ferramentas alimenta **quatro frentes**:

| frente | comando | serve para |
|---|---|---|
| 🦈 **Interface web** | `nh web` | painel azul/preto com o tubarão: chat, ferramentas, agenda, auditoria |
| 🔌 **MCP** (stdio) | `nh serve` | Claude Code, Cursor, OpenCode/LunaCode usarem as ferramentas |
| 💻 **CLI** | `nh do`, `nh tools`, `nh cron` | operar na mão, sem LLM |
| 🤖 **Agente** | `nh run "..."` | o LLM decide quais ferramentas chamar e executa |

---

## ⚡ Instalação

### 🪟 Windows (PowerShell — recomendado)
1. Instale o **Python 3** de https://www.python.org/downloads/ — na primeira tela
   **marque “Add python.exe to PATH”**.
2. Abra a pasta do projeto, clique com o botão direito em um espaço vazio →
   **“Abrir no Terminal”** (ou shift+clique direito → “Abrir janela do PowerShell aqui”).
3. Rode:
```powershell
.\install.ps1
```
Se aparecer erro de política de execução, rode antes:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Depois disso use os atalhos `.bat` (não precisa mexer em PATH):
```bat
nh.bat info                  :: estado do harness + relatório do PC
nh.bat tools                 :: lista as 29 ferramentas
nh.bat run "checa o sistema"  :: agente
run_web.bat                  :: 🦈 interface no navegador (localhost:8787)
run_scheduler.bat            :: liga o agendador em segundo plano
run_scheduler.bat stop       :: para o agendador
```

> **Chave do LLM no Windows:** o próprio Python lê o arquivo `.env` (o
> `install.ps1` já cria um a partir do `.env.example`). Abra o `.env` no Bloco de
> Notas, cole a chave em `SHARK_LLM_KEY=` e salve. Vale para a CLI, a interface e
> o agente. O `.env` está no `.gitignore` — nunca vai pro Git.

### 🐧 Linux / macOS
```bash
./install.sh              # núcleo + CLI + interface web
./install.sh --with-mcp    # adiciona o servidor MCP
./run_web.sh               # interface
./run_scheduler.sh start   # agendador em segundo plano
```
> Se você baixou o **.zip** (e não o .tar.gz ou um clone do Git), o ZIP não guarda
> a permissão de execução — use `bash install.sh` em vez de `./install.sh`.

### 📱 Termux (Android)
```bash
pkg install python && pkg install termux-api
pip install -e .        # NÃO instale mcp[cli] — veja o aviso abaixo
nh info
```
> ⚠️ **No Termux não instale `mcp[cli]`** — ele puxa `rpds-py`, que exige Rust e não
> compila em `aarch64-linux-android`. O núcleo, a CLI, a interface web e o agente
> funcionam sem o SDK. Para controle completo do Android instale também o app
> **Termux:API** pela loja.

---

## 🔄 Como atualizar

Atualizar é **baixar o código novo e rodar de novo** — sua chave, seu catálogo de modelos
e suas sessões ficam em `~/.shark-harness/`, **fora** do projeto, então nada disso se perde.
Plugins que você instalou pelo marketplace também sobrevivem (ficam em
`~/.shark-harness/plugins/`).

### 🪟 Windows (PowerShell)

Primeiro confirme que o Git está instalado:
```powershell
git --version
```
Se reclamar que não existe, instale com:
```powershell
winget install Git.Git
```
(depois **feche e abra o terminal de novo**, para o comando `git` aparecer)

Com o Git OK, entre na pasta e baixe a atualização:
```powershell
cd $HOME\Shark-Harness
```
```powershell
git pull
```
E rode — o `run_web.bat` cuida do caminho do Python pra você:
```powershell
.\run_web.bat
```

> **Não precisa reinstalar.** O projeto é instalado em modo "editável" (`pip install -e .`),
> então o que o `git pull` baixou já vale na próxima vez que você roda.

> ⚠️ **Se você baixou o ZIP e não clonou com Git**, o `git pull` vai dizer
> *"not a git repository"*. Aí tem duas saídas: baixar o ZIP de novo (e reinstalar), ou —
> melhor — clonar uma vez com Git e nunca mais se preocupar:
> ```powershell
> cd $HOME
> ```
> ```powershell
> git clone https://github.com/jaivedpereira/Shark-Harness.git
> ```
> ```powershell
> cd Shark-Harness
> ```
> ```powershell
> .\install.ps1
> ```
> (se der erro de política de execução: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)

### 📱 Termux / 🐧 Linux

```bash
cd ~/Shark-Harness
```
```bash
git pull
```
```bash
./.venv/bin/nh web
```

### Se o `git pull` reclamar de arquivo modificado

Acontece quando algum arquivo do projeto foi editado à mão. Descarte as mudanças locais
e baixe de novo:
```bash
git checkout .
```
```bash
git pull
```

### Se a porta estiver ocupada

O harness avisa sozinho e **sobe numa porta livre automaticamente**. Se você quiser aquela
porta de volta, pare a janela antiga:
```bash
pkill -f "Shark-Harness"
```
> Aquela janela antiga está rodando o **código de antes** do `git pull` — por isso o certo
> é parar e subir de novo, não só recarregar a página.

---

## 🦈 A interface

```bash
./run_web.sh                 # abre http://127.0.0.1:8787
nh web --port 9000           # porta custom
nh web --all                 # expõe na rede local (pede token, impresso no terminal)
nh web --risk safe           # interface só com ferramentas de leitura
```

Seis telas:
- **Agente** — chat com o LLM; cada ferramenta chamada aparece como um cartão
  (→ nome + argumentos) e o resultado é clicável para expandir
- **Ferramentas** — os 29 cards com etiqueta de risco; clicar abre um **formulário
  gerado do JSON Schema** e executa de verdade
- **Agendador** — criar/pausar/rodar/remover tarefas, com tradutor de cron
- **Auditoria** — tudo que foi executado, com segredos mascarados
- **Sistema** — RAM, disco, bateria, uptime do aparelho
- **Configurações** — ligar a IA sem mexer em arquivo (ver abaixo)

### 🔑 Configurar a IA pela interface (sem editar arquivo)

Na aba **Configurações** você escolhe o provedor, cola a chave e clica em **Salvar**.
O **Testar conexão** faz uma chamada real ao provedor e diz exatamente o que está
errado (chave inválida, sem saldo, modelo inexistente, rate-limit).

Provedores já cadastrados (a URL é preenchida sozinha):

| provedor | chave grátis? | observação |
|---|---|---|
| **OpenRouter** | ✅ tem modelos `:free` | default; o link "pegar chave" abre a página certa |
| **Groq** | ✅ tier gratuito | bem rápido |
| **DeepSeek** | ❌ exige saldo | ótimo em código |
| **OpenCode Zen** | ⚠️ | os `:free` só funcionam dentro do próprio OpenCode |
| **Ollama** | ✅ **100% local** | não precisa de chave — rode `ollama pull llama3.2` |
| **Personalizado** | — | qualquer endpoint OpenAI-compatível |

O que é salvo vai para `~/.shark-harness/config.json` (permissão `600`, só o seu
usuário lê). **A chave nunca volta inteira para a tela** — a interface mostra apenas
o começo e o fim (`sk-or-…8469`). Você também pode usar a variável de ambiente
`SHARK_LLM_KEY`, que tem prioridade sobre o arquivo.

Zero dependências: o servidor usa `http.server` da stdlib. Local por padrão; se
você expõe na rede (`--all`), ele exige um token gerado na hora.

### 📱 Foi feito para o celular também

A interface é **mobile-first de verdade**: no celular a barra lateral desaparece e
entram

- **barra de navegação embaixo** com 6 abas (ícone + rótulo), no lugar certo para o polegar
- **barra de cima** com o logo e o indicador de status da IA
- **alvos de toque** de 42px+ e campos com fonte 16px (o iOS não dá zoom ao digitar)
- **modal em tela cheia** para ler a saída das ferramentas
- **log de auditoria em cartões** (tabela no celular é sofrimento)
- respeito ao **notch e à barra de gestos** (`safe-area-inset`)

E dá para **instalar como app**: o servidor entrega um `manifest.webmanifest`, então
no Chrome/Android aparece "Adicionar à tela inicial" — abre em tela cheia, sem barra
de navegador, com o ícone do emblema. No Termux, rode `termux-wake-lock` antes do
`nh web` para o Android não matar o processo.

O **campo de digitar fica preso** na parte de baixo, logo acima da barra de navegação:
a conversa rola por trás dele, sem levar o campo junto.

## 🧠 Catálogo de modelos — vários modelos, cada um no seu endpoint

O harness nasceu com **um** modelo. Agora você cadastra quantos quiser, cada um com o seu
**endpoint** e o seu **nível** — e troca no topo do chat com um toque.

### 🌐 16 provedores prontos — e ele **busca a lista real de modelos**

Em vez de decorar nomes de modelo, escolha o provedor e clique em **🔍 buscar modelos**:
o harness pergunta ao endpoint (`/v1/models`) quais modelos existem e mostra a lista para
você escolher, com filtro. No OpenRouter isso são **mais de 400 modelos** (e ele diz quantos
são grátis). Ao clicar num modelo, o **nível já vem sugerido** pelo nome
(`:free`/`mini` → ⚡ rápido, `70b`/`pro`/`coder` → 🧠 potente).

| tipo | provedores |
|---|---|
| ☁️ **nuvem** | OpenRouter · Groq · DeepSeek · Mistral · Google Gemini · Cerebras · Together · Fireworks · xAI (Grok) · OpenAI · Anthropic · OpenCode Zen |
| 🏠 **local, sem chave** | Ollama · LM Studio · llama.cpp server |
| 🔧 | Personalizado (qualquer endpoint OpenAI-compatível) |

Cada provedor já vem com a dica, o tipo e o **link direto para pegar a chave**.
E o harness **reconhece o provedor pela URL** — inclusive separando Ollama (11434),
LM Studio (1234) e llama.cpp (8080), que vivem todos em `localhost`.

> 💡 Se a listagem falhar, a mensagem diz o porquê em português: *"a chave foi recusada —
> confira se ela é desse provedor"*, *"esse provedor não expõe lista de modelos"*,
> *"rate-limit ao pedir a lista"*.

| nível | para quê |
|---|---|
| ⚡ **Rápido** | respostas curtas e baratas, o dia a dia |
| ⚖️ **Equilibrado** | o padrão: qualidade boa com velocidade razoável |
| 🧠 **Potente** | raciocínio forte para tarefa difícil (mais lento e mais caro) |

Cada item guarda: apelido, endpoint, nome do modelo, **chave própria (opcional)** e uma nota.

**O nível não é enfeite — é a ordem das reservas.** Se o modelo escolhido falhar, o agente
tenta sozinho os outros: primeiro os do **mesmo nível** (troca justa), depois os **mais
potentes** (se algo tem que dar conta, que seja o forte). Dá para misturar provedores no
mesmo catálogo — OpenRouter, Groq, DeepSeek e um Ollama local convivem na mesma lista.

### 🔬 Teste de qualidade (o mais útil daqui)

Cada modelo tem um botão **testar**: ele roda 3 perguntas simples e mede **acerto** e
**velocidade**. Pega o que realmente atrapalha:

| o que aparece | o que significa |
|---|---|
| `vazou o raciocínio em vez de responder` | o modelo despeja o "thinking process" em inglês |
| `responder vazio` | devolve resposta vazia (acontece muito em modelo grátis) |
| `HTTP 404 — saiu do plano grátis` | o modelo não existe mais nesse provedor |
| `HTTP 429 — rate-limit` | estourou a cota (no OpenRouter grátis é diária) |
| `média 106s` | certo, mas lento demais para usar |

O teste tem teto de tempo (**~100s**): passou disso, ele já reprova por lentidão e nem faz
as perguntas que faltam. Gasta ~180 tokens no total.

```bash
nh modelo listar                  # o catálogo, com o que está em uso
nh modelo add --apelido "Groq rápido" --nivel 1 \
    --url https://api.groq.com/openai/v1/chat/completions \
    --modelo llama-3.3-70b-versatile
nh modelo usar <id>               # escolhe o do chat (sem id = volta ao global)
nh modelo testar <id>             # o teste de qualidade, no terminal
nh modelo remover <id>
```

O catálogo fica no `config.json`, então sobrevive a atualização. **A chave nunca volta
inteira para a tela** — o máximo que aparece é `sk-or-…8469`. Salvar um modelo sem informar
chave **não apaga** a que já estava lá.

---

## 📂 Sessões — trabalhar numa pasta de projeto

Sessão é o modo "Claude Code": você aponta uma **pasta** e o agente trabalha *dentro dela*.

- **todas as ferramentas passam a enxergar aquela pasta** — `write_file`, `read_file`,
  `grep_files` e os comandos rodam ali, não no workspace padrão
- o agente recebe um **resumo do projeto** antes de responder (arquivos do topo, ramo do
  git, começo do README) — então ele já sabe com o que está lidando
- a **conversa fica salva por pasta** (últimas 60 mensagens), então amanhã ele lembra do
  que vocês fizeram naquele projeto

Na interface: **Agente** tem a barra no topo (`📂`) para escolher a sessão, e a aba
**Sessões** cria/gerencia. Apagar uma sessão **não toca na pasta do projeto**.

```bash
# por dentro: a sessão grava aqui
~/.shark-harness/sessions.json
```

---

### 📊 Uso do modelo (tokens e custo)

Cada execução do agente é registrada em `~/.shark-harness/usage.jsonl` (uma linha JSON,
local, nunca enviada para fora). Isso alimenta:

- **Sistema → Uso do modelo** na interface: totais de hoje / 7 dias / período, gráfico
  dos últimos 14 dias e quebra por modelo, com **custo estimado em dólar**
- `nh uso [dias]` no terminal
- a ferramenta `uso_do_modelo`, que o próprio agente pode chamar — pergunte
  *"quanto eu já gastei hoje?"* e ele responde com os números reais

O custo é uma **estimativa** por uma tabela de preço por 1M de tokens (modelo `:free`
entra como zero); modelo sem preço conhecido aparece como `—` em vez de um número
inventado. Quem manda é a fatura do provedor.

### 🎛️ Barra de baixo ajustável

Em **Configurações → Aparência** dá para escolher o tamanho da barra de navegação no
celular: **Normal** (ícone + rótulo), **Compacta** (menor, barra de 52px) ou **Mínima**
(só ícones, barra de 42px). O campo de digitar acompanha, e a preferência fica salva
no navegador daquele aparelho.

---

## 🚀 Uso rápido (CLI)

```bash
nh                       # banner + ajuda
nh doctor                # 🩺 diagnóstico: testa escrita de arquivo e diz o que corrigir
nh info                  # estado do harness + relatório do dispositivo
nh tools                 # lista as 46 ferramentas (com risco de cada uma)

nh do clock              # chama uma ferramenta direto, sem LLM
nh do run_shell --args '{"command": "ls -la ~"}'
nh do cep --args '{"cep_numero": "01001000"}'
nh do clima --args '{"cidade": "São Paulo"}'
nh do port_check --args '{"porta": 8787}'
nh do zipar --args '{"origem": "~/.shark-harness"}'

nh audit                 # o que o harness executou (log de auditoria)
nh uso                   # uso do modelo: tokens consumidos e custo estimado
nh uso 7                 # janela de 7 dias · `nh uso --limpar` apaga o histórico
```

> 💡 **Comece pelo `nh doctor`.** Ele testa criação de arquivo de verdade, checa as
> pastas, a chave da IA, o termux-api e o log — e devolve a dica de correção de cada
> problema. É a resposta para "não consigo criar arquivo".

### 🤖 Com o agente (LLM)
```bash
export SHARK_LLM_KEY="sk-or-..."
nh run "checa o sistema e cria um backup do workspace em ~/bkp.tgz"
nh run "cria um script python que soma 1..100 e roda ele"
```
O agente imprime cada ferramenta que chamou (`🔧 [1] sysinfo_report(...)`) e a
saída real, então você audita tudo que ele fez.

> **Endpoint já testado funcionando:** OpenRouter com modelos `:free`
> (default: `nvidia/nemotron-3.5-lightning:free`).
> O `opencode.ai/zen` tem os modelos grátis travados ("free tier can only be used
> from within OpenCode") e os pagos exigem saldo. Alternativas: Groq, DeepSeek ou
> **Ollama local** (`http://localhost:11434/v1/chat/completions`, offline e grátis).

### ⏰ Tarefas agendadas
```bash
nh cron explain --cron "0 7 * * 1-5"                 # traduz o cron pra PT-BR
nh cron add --name backup --cron "0 3 * * *" --cmd "tar -czf ~/bkp.tgz ~/shark-workspace"
nh cron add --name saude  --cron "*/30 * * * *" --tool sysinfo_report
nh cron list
nh cron run --id backup        # executa agora, pra testar
nh cron pause --id backup
nh cron rm --id backup

./run_scheduler.sh start       # liga o agendador em segundo plano
./run_scheduler.sh status
./run_scheduler.sh logs
```

### 🔌 Ligar num cliente MCP
```bash
claude mcp add shark-harness -- python -m nh serve
nh serve --list        # confere o que está exposto
nh serve --selftest    # handshake + tools/list + tools/call, por stdio real
```
```json
{ "mcp": { "shark-harness": { "type": "stdio", "command": "python",
  "args": ["-m", "nh", "serve"], "enabled": true } } }
```

---

## 🧰 As 46 ferramentas

> O harness vem com **11 plugins embutidos (46 ferramentas)**. O resto você instala
> pelo **marketplace** — veja a seção seguinte.

| plugin | ferramentas | risco |
|---|---|---|
| **shell** | `run_shell`, `which`, `env_get` | 🟠 exec |
| **code** | `run_python`, `run_node`, `check_syntax` | 🟠 exec |
| **files** | `read_file`, `list_dir`, `find_files`, `grep_files`, `write_file`, `make_dir`, `delete_path` | 🟢→🔴 |
| **net** | `http_get`, `http_post`, `baixar_arquivo`, `port_check`, `ip_publico`, `cep`, `clima` | 🟢/🟡 |
| **archive** | `zipar`, `deszipar`, `sha256`, `tamanho_arquivos` | 🟢/🟡 |
| **proc** | `processos`, `meus_processos`, `matar_processo` | 🟢/🔴 |
| **schedule** | `schedule_task`, `list_tasks`, `remove_task`, `pause_task`, `run_task_now`, `explain_cron` | 🟡/🟠 |
| **device** | `device_notify`, `device_screenshot`, `device_clipboard_ler`, `device_clipboard_escrever`, `device_abrir` | 🟡 |
| **doctor** | `diagnostico`, `testar_escrita` | 🟢/🟡 |
| **sysinfo** | `sysinfo_report`, `disk_usage`, `clock` | 🟢 |
| **meta** | `list_tools`, `tool_help`, `audit_tail` | 🟢 |

Legenda: 🟢 só leitura · 🟡 escreve arquivo/tarefa · 🟠 executa comando · 🔴 apaga

**Gate de risco** — o que a IA/interface vê é limitado por `SHARK_MAX_RISK`:
```bash
SHARK_MAX_RISK=safe   nh serve   # só leitura: não escreve nem executa
SHARK_MAX_RISK=exec   nh serve   # default: escreve e executa, mas NÃO apaga
SHARK_MAX_RISK=danger nh serve   # libera delete_path (só se você confiar)
```

**Rodadas do agente** — cada ferramenta que ele usa gasta uma rodada. A última é
sempre reservada para ele **escrever a resposta**, então nunca termina de mãos vazias:
```bash
SHARK_MAX_ROUNDS=14  nh run "..."   # default
SHARK_MAX_ROUNDS=25  nh run "..."   # tarefa longa de depuração (testar/corrigir/testar)
```
Também dá para ajustar na interface, em **Configurações → Rodadas por tarefa**.

Se um pedido for grande demais, ele resolve a parte principal, entrega o que
conseguiu e diz o que ficou pendente — aí você pede para continuar de onde parou.

---

## 🛒 Marketplace de plugins

O harness vem com o essencial; o resto você instala quando precisar. Tudo roda pelos
mesmos três caminhos (interface, CLI e agente).

```bash
nh plugin catalogo            # o que existe para instalar
nh plugin procurar pdf        # busca por termo
nh plugin info obras          # ficha completa (risco, ferramentas, dependências)
nh plugin instalar obras      # baixa, confere o hash e instala
nh plugin listar              # tudo que está carregado + origem
nh plugin desativar media     # desliga sem apagar
nh plugin ativar media        # liga de volta
nh plugin remover obras       # apaga o que você instalou
nh plugin kits                # conjuntos por perfil
nh plugin kit essencial       # instala o kit inteiro
```

Na interface: **Ferramentas → Loja** (catálogo e kits) e **Ferramentas → Plugins**
(liga/desliga cada um com um interruptor).

### Onde os plugins instalados ficam (e por que isso importa)

```
nh/plugins/                   # embutidos — vêm no pacote, atualizam com `git pull`
~/.shark-harness/plugins/     # instalados por você — SOBREVIVEM ao `git pull`
```

Antes só existia a primeira pasta, então atualizar o pacote **apagaria** o que você
instalou. Agora o loader varre as duas, e um plugin pode ser um `.py` solto ou uma
pasta com `__init__.py` (para quando precisa de template ou asset junto).

### Confiança, sem enfeite

Plugin de terceiro **roda com o mesmo poder que você** — não existe sandbox de
verdade dentro do mesmo processo Python, igual `pip install`. O que o instalador
garante:

| trava | o que impede |
|---|---|
| **sha256 fixado** no catálogo | alguém trocar o arquivo depois de publicado |
| **risco conferido no código (AST)** | plugin dizer "sou só leitura" e importar `subprocess` |
| **confirmação explícita** para risco `exec`/`danger` | instalar sem saber que executa comando |
| **catálogo curado** | plugin malicioso entrar na lista |

Se o risco declarado não bater com o código, a instalação **aborta** e nada é gravado.
Leia o código antes de confiar — é uma pasta com um arquivo `.py`, abre no editor.

---

## 🛡️ Segurança (leia)

Este harness executa comandos de verdade. As travas:

1. **Deny-list de comandos destrutivos** — `rm -rf /`, `mkfs`, `dd` no disco,
   `curl | sh`, fork bomb, `shutdown`, apagar histórico e force-push em `main` são
   **bloqueados**, e não dá pra desligar por flag.
2. **Deny-list de caminhos** — não escreve em `/etc`, `/boot`, `/dev`, nem em
   vetores de persistência automática (`~/.bashrc`, `authorized_keys`, chaves SSH).
   Isso impede que algo (ou um modelo alucinando) se instale pra rodar no boot.
3. **Gate de risco** — `delete_path` fica fora do que a IA vê por padrão.
4. **Log de auditoria append-only** — `~/.shark-harness/audit.log`, com timestamp,
   status e argumentos (segredos mascarados). Veja com `nh audit` ou na interface.
5. **Timeout obrigatório** em todo comando/código.
6. **Interface presa no localhost** por padrão; expor na rede exige token.

⚠️ **Isto NÃO é uma sandbox.** Um comando fora da deny-list que você autorize pode
causar dano. Como diz o aviso do próprio DeepSeek Harness: rode com o mínimo de
privilégios, mantenha backup e não use como única barreira para código não confiável.
Em máquina compartilhada, prefira container/VM.

**O que ele NÃO faz de propósito:** esconder rastro, persistência silenciosa,
capturar tela/clipboard sem você pedir, ou enviar dados para fora. As ações são
locais e auditáveis.

---

## 📁 Estrutura

```
shark-harness/
├── install.sh / install.ps1   # instaladores (Linux/macOS · Windows)
├── nh.bat / run_web.bat / run_scheduler.bat   # atalhos para Windows
├── run_web.sh / run_scheduler.sh              # atalhos para Linux/macOS
├── nh/
│   ├── core.py        # registry + descoberta de plugins + schema do docstring
│   ├── guard.py       # deny-lists, auditoria, níveis de risco
│   ├── scheduler.py   # cron parser, jobs.json, daemon
│   ├── agent.py       # loop de tool-calling (urllib, zero deps)
│   ├── cli.py         # a CLI `nh`
│   ├── mcp_server.py  # servidor MCP stdio (SDK opcional)
│   ├── web.py         # interface web (http.server da stdlib)
│   ├── paths.py       # ~/.shark-harness, workspace, .env, plataforma
│   ├── webui/         # index.html · style.css · app.js (tema azul/preto + tubarão)
│   └── plugins/       # shell, code, files, schedule, device, sysinfo, meta
└── tests/
    ├── test_core.py        # registry, guarda, execução, cron (40+ asserts)
    ├── test_mcp_stdio.py   # handshake + tools/list + tools/call por stdio real
    └── test_agent_live.py  # agente com LLM real (escolhe um modelo grátis)
```

**Criar um plugin novo** — crie `nh/plugins/meu.py`:
```python
from ..core import Registry

def meu_comando(entrada: str, vezes: int = 1) -> str:
    """Faz algo útil no dispositivo.

    Args:
        entrada: o que processar.
        vezes: quantas vezes repetir.
    """
    return "resultado real"

def register(reg: Registry) -> None:
    reg.add(meu_comando, risk="safe", plugin="meu")
```
O núcleo descobre sozinho: o **docstring vira a descrição** e os **type hints viram
o JSON Schema** — e as quatro frentes (web, MCP, CLI, agente) pegam automaticamente.

---

## ✅ Verificação (o que foi testado de verdade)

```bash
python3 tests/test_core.py                # registry, guarda, cron, jobs
.venv/bin/python tests/test_mcp_stdio.py  # MCP: handshake, 28 tools, tools/call
.venv/bin/python -m nh serve --selftest   # selftest rápido do MCP
SHARK_LLM_KEY=... python3 tests/test_agent_live.py   # agente com LLM real
```

Resultados obtidos nesta máquina:
- 29 ferramentas · 7 plugins carregados
- **7/7** comandos destrutivos bloqueados · **5/5** comandos legítimos liberados
- escrita em `~/.bashrc` bloqueada pela guarda
- tarefa agendada criada, disparada **sozinha pelo daemon** 2x e histórico gravado
- **agente real** chamou `sysinfo_report`, leu os dados e respondeu certo
- MCP: 28 ferramentas expostas, `delete_path` fora, `rm -rf /` barrado dentro do MCP
- interface web: `/api/state`, `/api/tool`, `/api/cron` e `/api/agent` testados
  (agente rodando pela UI com passos ao vivo)

---

## 📜 Licença
MIT. Use por sua conta e risco — ver seção de segurança.
