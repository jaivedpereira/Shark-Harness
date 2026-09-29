# 🗺️ Roadmap de plugins do Shark Harness

> Antes de tudo: existe uma diferença entre **ferramenta nova** e **capacidade nova**.
> `git_status` é uma ferramenta. Um plugin que *escreve outros plugins* é capacidade.
> A seção **"Nível insano"** no fim deste arquivo é sobre o segundo tipo.

Hoje: **46 ferramentas em 11 plugins**. Como tudo é plugin, cada ideia abaixo é
literalmente **um arquivo novo** em `nh/plugins/` — nenhuma exige mexer no núcleo.

Regra que eu uso para priorizar: **resolve uma dor repetida?** Se sim, entra na fila
de cima. Se é só legal, vai para os absurdos (que também têm valor: testam o limite
da arquitetura).

---

## 🧠 NÍVEL INSANO — plugins que dão uma CAPACIDADE nova

Estes não adicionam ferramentas: mudam o que o harness **é**. Ordenados por
insanidade útil × viabilidade (do mais impressionante para o mais tranquilo).

### 1. `fabrica` — o harness que escreve os próprios plugins 👑
**O mais insano de todos, e é viável hoje.** O agente já tem `write_file`,
`run_python` e `check_syntax`; falta ele saber montar um plugin e recarregar.

```
fabrica_plugin   # descreve em português -> gera nh/plugins/x.py completo
testar_plugin    # roda a suite, confere docstring/type hints/risco
instalar_plugin  # valida e recarrega o registry a quente, sem reiniciar
plugins_criados  # lista o que ele mesmo criou
desfazer_plugin  # remove e restaura o registry anterior
```

Você pede no chat *"quero que ele saiba calcular juros compostos"* e ele **escreve
a ferramenta, testa e passa a usar**. O harness cresce sozinho — e o melhor: o
`sandbox_antes` (item 6) obriga isso a passar pela guarda antes de instalar.

### 2. `pipeline` — compor ferramentas em macros nomeadas
O salto de "tenho 46 ferramentas" para "tenho 46 ferramentas **encadeadas**".

```
fluxo_criar    # "backup completo" = zipar -> sha256 -> enviar telegram
fluxo_rodar    # roda o encadeamento, com condição e repetição por item
fluxo_listar · fluxo_agendar   # e o mesmo fluxo vira tarefa agendada
```

Um pipeline é um JSON com passos que reusam ferramentas existentes — dá para
combinar as 46 em centenas de rotinas sem escrever Python nenhuma vez.

### 3. `memoria` — o harness lembrar de você para sempre
Hoje ele esquece tudo entre execuções. Com isto, o que você fala uma vez vale
para sempre.

```
lembrar      # "meu wifi é X", "o deploy do Manganana é na Vercel"
recordar     # busca por assunto antes de agir
esquecer · memoria_listar
```

O gancho técnico: o agente **consulta a memória no início de toda tarefa** — é o
mesmo padrão que eu uso. Sem isso, você repete contexto toda vez.

### 4. `rotina_aprendida` — ler o próprio log e sugerir automação
O `audit.log` já registra tudo. Ninguém usa. Este plugin **usa**: acha padrão
repetido e propõe criar o job.

```
analisar_rotina   # "toda terça 14h você roda o mesmo backup — crio o job?"
sugerir_automacao # agrupa comandos parecidos e mede o tempo que você perde
```

Algoritmo clássico (frequência + similaridade + janela de tempo), sem LLM — dá
para fazer determinístico e barato. É automação que **se descobre sozinha**.

### 5. `visao` — entender uma imagem e agir
Você me manda print o tempo todo. O harness ainda não enxerga.

```
ler_imagem     # OCR: extrai o texto de um print ou foto
descrever      # resumo do que tem na tela (com modelo multimodal, se houver)
diagnosticar   # print de erro -> acha a causa e propõe a correção
comparar       # duas imagens: o que mudou
```

O fluxo que isso habilita: `device_screenshot` -> `ler_imagem` -> agente -> fix.
Você manda um print de erro no Telegram e ele responde com a correção.

### 6. `sandbox_antes` — prever o estrago antes de fazer
Um harness que executa precisa saber o que vai acontecer **antes**.

```
simular        # roda o comando num ambiente descartável e mostra o efeito
prever_efeito  # "isto vai apagar 412 arquivos e 3,1 GB" — antes de perguntar
```

No PC, container descartável; no Termux, cópia do diretório alvo num tmpfs. É o
que transforma "espero que esteja certo" em "eu sei o que vai acontecer".

### 7. `cofre` — o LLM usa a senha sem nunca ver a senha
Arquitetura de segurança, não ferramenta.

```
cofre_guardar  # cifra um segredo com chave derivada da senha mestra
cofre_listar   # devolve só os NOMES, nunca os valores
cofre_usar     # injeta a credencial no comando, o modelo vê apenas {{cofre:x}}
```

Assim o modelo pode rodar `curl -H "token: {{cofre:github}}"` e o valor real
nunca entra no contexto dele — nem no log de auditoria (que já mascara segredos).

### 8. `guardiao` — auto-cura
Hoje o agendador roda tarefas. Com isto, ele **reage**.

```
proteger_servico  # vigia porta/processo e reinicia se cair
em_caso_de_falha  # gatilho: se X falhar -> roda Y -> me notifica
auto_recuperar    # retenta com espera crescente antes de desistir
```

Ex.: se o `nh web` morrer às 3h, ele reinicia, testa e só te incomoda se não
conseguir — em vez de descobrir de manhã que está tudo fora do ar.

### 9. `pc_remoto` — o celular comandando o PC
O harness roda nos dois; falta eles se falarem.

```
pc_conectar    # SSH do Termux para o Windows (ou o contrário)
pc_rodar       # manda a tarefa pesada para o PC e traz o resultado
pc_enviar · pc_puxar
```

O caso insano: *"compila o projeto no PC, zipa e me manda o arquivo aqui no
celular"* — você pede do ônibus e chega em casa pronto.

### 10. `agenda_viva` — o agendador que conhece a tua vida
O `schedule` atual só entende cron. Este entende contexto.

```
horario_livre   # sabe que qua/qui você está na escola das 5h35 às 19h30
agendar_inteligente  # "roda isso quando eu estiver em casa" -> escolhe o horário
modo_escola · modo_estudo
```

Ele já sabe que terça é treino A e sábado é treino C (está no JAI 2.0). Juntando,
o agendador deixa de ser um relógio e vira alguém que sabe quando você pode.

---

## 🥇 O que eu faria primeiro

### 1. `git` — versionamento (7 ferramentas)
O que mais falta hoje. Você usa GitHub em tudo, e o agente não sabe nada de git.

```
git_status · git_diff · git_log · git_commit · git_pull · git_push · git_branch
```

Valor: *"commita e sobe o que eu mexi hoje"* passa a funcionar de verdade. Risco:
`git_push` como `danger` (reescreve história remota se for `--force`).

### 2. `mensagens` — o agente falar com você (4 ferramentas)
Fecha o ciclo: hoje ele executa e espera você abrir o painel.

```
telegram_enviar · telegram_ler · email_enviar · resumo_do_dia
```

Valor: tarefa agendada de madrugada te manda o resultado no zap às 7h. O plugin
`schedule` já existe — só falta o canal de saída.

### 3. `vigia` — monitorar algo e avisar quando mudar (4 ferramentas)
Transforma o agendador em vigia de verdade (hoje ele só executa no horário, não
compara estado).

```
vigiar_url      # guarda URL + hash e avisa quando o conteúdo mudar
vigiar_preco    # extrai preço de uma página
vigiar_arquivo  # avisa se um arquivo for alterado
vigiar_listar
```

Valor: *"me avisa quando o ingresso baixar de 80"* / *"se o site do Manganana cair"*.
É a diferença entre automação e **mordomo**.

### 4. `obras` — cálculo de construção civil (6 ferramentas)
Você cursa Edificações. Este é o plugin com utilidade mais direta pra você.

```
concreto_volume   # viga/laje/pilar em m3 -> cimento, areia, brita, água
peso_aco          # bitola CA-50 x comprimento -> kg (tabela NBR 7480)
reboco_material   # area de parede -> sacos de argamassa
rampa_inclinacao  # altura x comprimento -> %
orcamento_insumos # lista de itens x preco -> total
verificar_nbr     # checagens de traço e dimensão mínima
```

Tabela de aço que entra no plugin (kg/m): 6.3→0.245 · 8→0.395 · 10→0.617 ·
12.5→0.963 · 16→1.578 · 20→2.466 · 25→3.853 · 32→6.313

### 5. `media` — imagem, áudio e vídeo (6 ferramentas)
Depende de ffmpeg (opcional, degrada com mensagem clara).

```
extrair_audio    # mp4/mkv -> mp3
comprimir_video  # reduz tamanho mantendo qualidade aceitável
redimensionar_imagem · converter_imagem   # webp/png/jpg + otimizar
gerar_thumbnail  # capa a partir de um frame
info_midia       # duração, resolução, bitrate
```

Valor: cortar áudio de vídeo, otimizar asset pra web (Manganana), capa de vídeo.

---

## 🥈 Fila do meio

### 6. `pdf` — o que você mais me pede
```
pdf_de_markdown · pdf_juntar · pdf_dividir · pdf_extrair_texto · pdf_para_png
```
Hoje eu gero PDF na mão (como o catálogo). Com isso o agente faz sozinho.

### 7. `notas` — memória durável em markdown
```
nota_salvar · nota_buscar · nota_listar · nota_apagar
```
Um caderno que o agente consulta. Diferente do meu log de auditoria (que é
histórico técnico) — isto é conhecimento seu: endereço, receita, senha do wifi,
decisão de projeto.

### 8. `planilhas` — CSV, JSON e Excel
```
csv_consultar   # filtra/ordena/agrupa sem abrir Excel
csv_para_json · json_consultar  # navega JSON por caminho
xlsx_ler · xlsx_escrever
```
Valor: planilha de orçamento de obra, controle de gasto, nota de escola.

### 9. `backup` — rotina com retenção
```
backup_criar · backup_restaurar · backup_listar · backup_limpar_antigos
```
O `archive` compacta, mas não gerencia: isto mantém os últimos N e apaga o resto.
Combina com o agendador: backup diário às 3h, guarda 7 dias.

### 10. `sensores` — só no celular (Termux:API)
```
bateria_detalhada · localizacao · enviar_sms · tirar_foto · falar (TTS) · sensor_luz
```
Aqui mora o lado "celular como sensor": *"tira uma foto e me descreve"*,
*"onde eu deixei o carro"*, *"lê em voz alta o resumo"*.

### 11. `monitor` — vigia o próprio aparelho
```
ligar_alerta   # RAM/disco/bateria acima do limite -> notifica
```
Diferente do `vigia` (que olha a internet), este olha a máquina.

---

## 🥉 Arquiteturais (mais trabalho, mais poder)

### 12. `mcp_cliente` — o harness consumindo outros MCPs
Hoje ele **é** servidor MCP. Com isto ele vira **cliente**: puxa as ferramentas de
um MCP externo (GitHub, Notion, banco de dados) e registra como se fossem plugins
nativos. Multiplica as ferramentas sem escrever nenhuma.

### 13. `sync` — celular ↔ PC
```
sync_enviar · sync_puxar   # rsync por SSH entre o Termux e o Windows
```
Valor: você começa a anotar no celular e termina no PC sem mandar arquivo no zap.

### 14. `ia_local` — modelo offline
Um plugin que fala com `llama.cpp` no PC: quando não tiver internet (ou a chave
vencer), o agente continua funcionando com modelo local. Também serve para tarefas
simples sem gastar cota.

### 15. `rotina` — liga com o teu JAI 2.0
```
xp_registrar · xp_relatorio · sequencia (streak) · habito_marcar
```
Você já tem treino A/B/C, handbook e XP no sistema JAI 2.0. Isto deixaria o próprio
harness registrar: *"fiz o treino B"* → soma XP, atualiza a sequência e te manda o
relatório das 21h sem depender do cron externo.

---

## 🤪 Os absurdos (tecnicamente viáveis, socialmente questionáveis)

Estes existem para testar os limites da arquitetura — e porque dá vontade.

### Nível 1 — só bobagem
| plugin | o que faz |
|---|---|
| `carinho` | a cada job concluído solta um "boa, chefe" aleatório. Confete no terminal. |
| `ansiedade` | tarefa agendada às 3h03 que pergunta *"e se der errado?"* e não faz mais nada. |
| `drama` | envia toda saída por um tradutor de novela mexicana antes de mostrar. |
| `mascote` | um tubarão ASCII que reage ao teu comando — morre de vergonha no `rm`, comemora no `git push`. |
| `gato` | ignora completamente o pedido e devolve um gato aleatório de API pública. Só isso. |

### Nível 2 — sabotagem carinhosa
| plugin | o que faz |
|---|---|
| `burocracia` | força 3 formulários, um carimbo e 1 a 3 dias úteis antes de executar qualquer coisa. O oposto exato de automação. |
| `plot_twist` | 10% de chance de o job agendado rodar **ao contrário** e depois pedir desculpa. |
| `alarme_maluco` | a notificação chega 47 minutos depois, com o texto de outra tarefa. |
| `ex` | responde toda solicitação com *"não vou responder isso"* e loga sua tentativa. |
| `gaslight` | afirma com segurança que executou, e no log de auditoria mostra que não. |

### Nível 3 — o limite do razoável
| plugin | o que faz |
|---|---|
| `tinder_de_arquivos` | swipe (ou `y`/`n`) para decidir o que apagar. Tem placar no fim. |
| `leilao` | para rodar uma tarefa, você tem que vencer um leilão contra um bot que sempre dá lance 1 real acima. |
| `auditoria_inversa` | registra tudo que **você** fez e te cobra explicações no fim do dia. |
| `karma` | cada comando destrutivo aumenta um contador eterno que só aparece no `nh info`. |
| `demo` | atrasa tudo em 300ms e adiciona "…" para parecer que está pensando mais do que pensa. |
| `sindicato` | as ferramentas entram em greve aleatória: *"run_shell não trabalha depois das 18h"*. |
| `advogado` | antes de qualquer escrita, exige um termo de consentimento de 4 parágrafos que você não pode ler até o fim. |

---

## ⛔ Onde eu não vou

Algumas ideias aparecem em toda conversa sobre agente autônomo — e a resposta é não,
não por frescura, mas porque são **malware**. Se eu construir, quem perde é você:

- **persistência silenciosa** — se reinstalar no boot escondido. O `guard` já bloqueia
  escrita em `~/.bashrc` e `authorized_keys` justamente por isso.
- **esconder rastro no log** — todo o valor do harness é a auditoria ser confiável.
- **capturar tela/teclado/senha sem pedido** — print e clipboard só quando você manda.
- **mineração de cripto / usar tua máquina de graça** — queima a bateria e a vida do
  aparelho, e em muitos países é crime.
- **exfiltração de dados** — mandar arquivo pra fora sem você pedir.
- **atacar terceiros** — DDoS, força bruta, spam, varredura de rede alheia.

O caminho divertido e legítimo para esse tipo de desafio é **CTF** e **pentest no
próprio app** — atacar o Shark Harness para achar falha nele é ótimo exercício e não
prejudica ninguém. Inclusive seria um plugin válido: `autoteste` (tenta furar a
própria guarda com uma lista de truques e mostra o que passou).

---

## Ordem sugerida de execução

1. `git` → destrava teu fluxo de código inteiro
2. `mensagens` → o agente passa a te alcançar sem você abrir o painel
3. `vigia` → transforma agendador em mordomo
4. `obras` → utilidade direta pro teu curso
5. `media` → o que mais dói no dia a dia com vídeo e imagem

Depois disso, um absurdo por vez — de preferência o `mascote`, porque ele dá
personalidade ao projeto.
