# 🛒 Marketplace de plugins — desenho

> Status: **ideia registrada, não implementada.** Este arquivo é o desenho para
> consulta futura.

## Por que é possível (e mais fácil do que parece)

O Shark Harness já foi construído na forma que um marketplace precisa:

| o que o marketplace exige | já existe? |
|---|---|
| unidade instalável isolada | ✅ plugin = 1 arquivo em `nh/plugins/` |
| descrição legível por máquina | ✅ docstring vira a descrição da ferramenta |
| contrato de entrada tipado | ✅ type hints viram JSON Schema sozinhos |
| classificação de perigo | ✅ `risk="safe/write/exec/danger"` por ferramenta |
| formulário na interface | ✅ a UI já gera o formulário do schema |
| registro de tudo que roda | ✅ `audit.log` append-only |

Ou seja: **o manifesto já existe, só está implícito no código.** Falta explicitá-lo.

## O que precisa ser construído

### 1. Manifesto explícito (`plugin.toml` ou cabeçalho no `.py`)
```toml
[plugin]
id          = "obras"
nome        = "Cálculo de Obras"
versao      = "1.2.0"
autor       = "jaivedpereira"
categoria   = "engenharia"
descricao   = "Concreto, aço CA-50, reboco, rampa e orçamento."
risco_max   = "safe"            # teto declarado: a guarda confere se confere
plataformas = ["linux", "windows", "android", "macos"]
requer      = ["ffmpeg"]        # binários externos -> degrada com mensagem clara
python      = ["psutil>=5.9"]   # opcional; sem isso a ferramenta some
tags        = ["construção", "engenharia", "nbr"]

[config]
unidade_padrao = { tipo = "select", opcoes = ["m", "cm"], padrao = "m" }
```

### 2. Duas pastas de plugins (correção importante)
Hoje o loader só olha `nh/plugins/` — **dentro do pacote**. Isso é um problema real:
um `git pull` ou reinstalação **apaga o que o usuário instalou**.

Correção: o loader passa a varrer duas pastas, com prioridade:

```
nh/plugins/                      # embutidos (vêm no pacote, sobem com o git pull)
~/.shark-harness/plugins/        # instalados pelo usuário (sobrevivem à atualização)
~/.shark-harness/plugins/<id>/   # plugin com vários arquivos + assets
```

E precisa aceitar **diretório** (`<id>/__init__.py`), não só arquivo `.py` solto —
senão plugin com template, asset ou tradução não cabe.

### 3. Ativar / desativar sem apagar
Uma lista em `config.json`: `plugins_desativados: ["media", "sensores"]`.
Isto é o coração do "customizável" — o usuário escolhe o que carrega, e a
interface + o agente só enxergam o que está ligado.

### 4. Comandos
```
nh plugin procurar <termo>     # busca no catálogo
nh plugin info <id>            # ferramentas, risco, dependências, autor
nh plugin instalar <id>        # baixa, confere o hash, valida e instala
nh plugin desativar <id>       # para de carregar (sem apagar)
nh plugin atualizar            # atualiza o que mudou
nh plugin remover <id>
nh plugin criar                # abre o fluxo da `fabrica` (gerar plugin seu)
```

### 5. Onde vive o catálogo
Um repositório `shark-harness-plugins` com um `index.json`, servido direto do
GitHub (raw). Sem servidor, sem custo, versionado por commit:

```json
[
  { "id": "obras", "versao": "1.2.0", "categoria": "engenharia",
    "autor": "jaivedpereira", "sha256": "9f2c…", "risco_max": "safe",
    "ferramentas": 6, "instalacoes": 0, "tags": ["construção"] }
]
```

## 🔐 A parte difícil é confiança, não código

Aqui vale ser honesto, sem enfeite: **plugin de terceiro roda com o mesmo poder que
você.** Não existe sandbox real dentro do mesmo processo Python — quem instala
código de estranho está rodando código de estranho, igual `pip install`.

O que dá para fazer de verdade, em ordem de força:

| medida | protege de | custo |
|---|---|---|
| **índice curado** (só entra o que eu reviso) | plugin malicioso | tempo de revisão |
| **hash fixado** por versão (`sha256`) | troca de conteúdo depois | baixo |
| **risco declarado E conferido** — plugin que diz `safe` e importa `subprocess` é rejeitado na instalação | mentira no manifesto | baixo, dá para checar com `ast` |
| **mostrar o código antes de instalar** + confirmação explícita para `exec`/`danger` | instalação no escuro | baixo |
| **subprocesso isolado** com API por RPC: o plugin não recebe o poder do harness, só pede ferramentas | quase tudo | alto, mas é a resposta certa |

**Mesmo nível do problema:** a `fabrica` gerando plugin sozinha. Ela precisa passar
pelo mesmo portão — gerar, `check_syntax`, conferir o risco real, **pedir sua
confirmação** e só então instalar. Plugin auto-gerado nunca entra sozinho.

## 🎛️ Como o usuário escolhe (o ponto de UX)

Loja com 200 itens e sem curadoria é pior que 40 bons. Estratégia em camadas:

1. **Kits por perfil** (recomendado, é o que 90% vai usar)
   - *Kit Dev* · *Kit Celular/Termux* · *Kit Mídia* · *Kit Obras* · *Kit Estudo*
   - *Kit Vida* (notas, hábitos, finanças, calendário)
   - um clique instala o kit inteiro, já testado junto
2. **Categorias** — para quem quer navegar
3. **Modo avançado** — escolhe plugin por plugin, vê as ferramentas antes de instalar
4. **Modo desligado** — instala só o núcleo (os 11 de hoje) e pronto

E o encaixe com a `fabrica`: **marketplace = baixar o que outros fizeram;
fabrica = criar o teu.** As duas metades do mesmo sistema — e o que você criar
na `fabrica` pode ser publicado para virar item do marketplace.

## 📊 Quantos plugins teria

| área | plugins possíveis | exemplos |
|---|---|---|
| Sistema e dev | ~18 | git, docker, ssh, serviços, env, backup, sync |
| Rede e web | ~16 | dns, ssl, uptime, webhook, scraping, túnel, deploy |
| Mídia | ~14 | ffmpeg, imagem, ocr, pdf, docx, xlsx, tts, download |
| Dados | ~12 | csv, json, sqlite, postgres, redis, gráficos, etl |
| Android / Termux | ~14 | sensores, sms, câmera, localização, wifi, bluetooth |
| Comunicação | ~10 | telegram, email, discord, rss, slack, sms |
| Automação e IA | ~12 | pipeline, vigia, eventos, ia_local, embeddings, visão |
| Estudo e trabalho | ~10 | notas, SRS, calendário, tarefas, planilhas |
| Casa e vida | ~12 | casa inteligente, finanças, clima, câmbio, treino |
| Engenharia / obras | ~8 | concreto, aço, elétrica, hidráulica, orçamento, unidades |
| Segurança | ~8 | cofre, gpg, senhas, autoteste, scan, hardening |
| Jogos e diversão | ~6 | emulação, saves, servidor, dados de jogos |
| **total curado** | **~140** | |

Somando os 11 atuais: **~150 plugins curados**, algo entre **600 e 1.000 ferramentas**.

Três leituras desse número:

- **Curado:** 120–180. É até onde dá para revisar de verdade e manter funcionando.
- **Útil de verdade:** 40–60. Acima disso, o usuário não sabe o que escolher — daí
  a necessidade dos **kits**. O valor não está em ter 200, está em ter os 40 certos
  por perfil.
- **Nicho / long tail:** ilimitado. Só o `fabrica` responde isso, e aí o marketplace
  deixa de ser catálogo e vira **lugar de compartilhar o que cada um criou**.

## Ordem de implementação sugerida

1. **Duas pastas + ativar/desativar** — resolve o `git pull` apagar plugin e já
   entrega a customização (é o maior ganho pelo menor esforço)
2. **Manifesto explícito** + `nh plugin info`
3. **Índice `index.json` + `nh plugin instalar`** com hash
4. **Kit como pacote** (lista de ids instalados de uma vez)
5. **Aba do marketplace na interface** (a UI já sabe desenhar formulário de schema)
6. **Assinatura / subprocesso isolado** — quando tiver plugin de terceiro de verdade
