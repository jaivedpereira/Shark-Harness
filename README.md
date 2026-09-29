# 🦈 Shark Harness

Um **agente de tarefas** com arquitetura **tudo-é-plugin** — inspirado no
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness), mas em Python,
sem dependências obrigatórias e rodando igual no **PC**, no **Linux** e no **Termux**.

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

## 🦈 A interface

```bash
./run_web.sh                 # abre http://127.0.0.1:8787
nh web --port 9000           # porta custom
nh web --all                 # expõe na rede local (pede token, impresso no terminal)
nh web --risk safe           # interface só com ferramentas de leitura
```

Cinco telas:
- **Agente** — chat com o LLM; cada ferramenta chamada aparece como um cartão
  (🔧 nome + argumentos) e o resultado é clicável para expandir
- **Ferramentas** — os 29 cards com badge de risco; clicar abre um **formulário
  gerado do JSON Schema** e executa de verdade
- **Agendador** — criar/pausar/rodar/remover tarefas, com tradutor de cron
- **Auditoria** — tudo que foi executado, com segredos mascarados
- **Sistema** — RAM, disco, bateria, uptime do aparelho

Zero dependências: o servidor usa `http.server` da stdlib. Local por padrão; se
você expõe na rede (`--all`), ele exige um token gerado na hora.

---

## 🚀 Uso rápido (CLI)

```bash
nh                       # banner + ajuda
nh info                  # estado do harness + relatório do dispositivo
nh tools                 # lista as 29 ferramentas (com risco de cada uma)

nh do clock              # chama uma ferramenta direto, sem LLM
nh do run_shell --args '{"command": "ls -la ~"}'

nh audit                 # o que o harness executou (log de auditoria)
```

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

## 🧰 As 29 ferramentas

| plugin | ferramentas | risco |
|---|---|---|
| **shell** | `run_shell`, `which`, `env_get` | 🟠 exec |
| **code** | `run_python`, `run_node`, `check_syntax` | 🟠 exec |
| **files** | `read_file`, `list_dir`, `find_files`, `write_file`, `make_dir`, `delete_path` | 🟢→🔴 |
| **schedule** | `schedule_task`, `list_tasks`, `remove_task`, `pause_task`, `run_task_now`, `explain_cron` | 🟡/🟠 |
| **device** | `device_notify`, `device_screenshot`, `device_clipboard_ler`, `device_clipboard_escrever`, `device_abrir` | 🟡 |
| **sysinfo** | `sysinfo_report`, `disk_usage`, `clock` | 🟢 |
| **meta** | `list_tools`, `tool_help`, `audit_tail` | 🟢 |

Legenda: 🟢 só leitura · 🟡 escreve arquivo/tarefa · 🟠 executa comando · 🔴 apaga

**Gate de risco** — o que a IA/interface vê é limitado por `SHARK_MAX_RISK`:
```bash
SHARK_MAX_RISK=safe   nh serve   # só leitura: não escreve nem executa
SHARK_MAX_RISK=exec   nh serve   # default: escreve e executa, mas NÃO apaga
SHARK_MAX_RISK=danger nh serve   # libera delete_path (só se você confiar)
```

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
