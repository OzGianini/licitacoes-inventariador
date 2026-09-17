# ESTADO_ATUAL.md — Inventariador

Documento de **estado vigente**, não histórico de ciclos. Toda afirmação é sustentada por leitura do working tree. Regenerado ao final de cada rodada, **por medição** — nunca por memória nem por cópia de documento antigo.

**Este ledger nasceu na D1.** Antes da D1, `C:\licitacoes\inventariador` não existia. A prova de inexistência está em `_rodada_inventariador\gate0\prova_inexistencia_ledger.txt`, com o erro real do sistema de arquivos (`FileNotFoundError: [Errno 2] [WinError 2]`).

**Estado após a D3, REGULARIZADA em 2026-09-14** — ver **D3.6**. A D1 e a D2 continuam registradas como foram escritas, e o **bloqueio original da D3 não foi apagado**: ele está em D3.6, com a autorização do Oz ao lado.

**As duas auditorias independentes convergiram sobre a D2**, e é essa convergência que abriu a D3. Os dois achados que a D2 deixou de fora **de propósito** foram tratados aqui; o terceiro — os 8 downloads que gravaram não-zip — **continua fora**, porque é frente do Módulo 1.

**Atalhos:** decisões vigentes em §6 · o que a auditoria bloqueou em §6.0 · onde o trabalho parou em §7 · o que esta rodada NÃO fez em §8.

---

## 1. O que esta frente é

O **Inventariador** responde: *dado um edital que a cadeia já conhece, quais arquivos existem AGORA para ele*. Nem mais, nem menos. Ver `CLAUDE.md` §2 para o que ele deliberadamente **não** faz — em especial: **não guarda fila**.

---

## 2. Os arquivos desta casa

| arquivo | papel |
|---|---|
| `CLAUDE.md` | instruções permanentes da frente |
| `ESTADO_ATUAL.md` | este arquivo — estado e ledger próprios |
| `ESTADO_ATUAL.md.sha256` | sidecar da identidade criptográfica deste arquivo |
| `config.py` | os caminhos, num lugar só; nenhum resolvido no import |
| `convencao_edital.py` | cópia deliberada da lógica provada do `modulo2/utils.py` |
| `agenda.py` | leitura somente-leitura da Agenda, por nome de cabeçalho |
| `inventario.py` | o inventário: estado, arquivos, achados, ordem determinística |
| `diff_inventario.py` | reinventário e diff |
| `inventariador.py` | ponto de entrada da etapa do Maestro; roda sem parâmetro |
| `testes/teste_inventario.py` | suíte sintética |
| `testes/teste_determinismo_fuso.py` | determinismo entre fusos, migração de schema, as sete provas do §5 da D2 e a guarda sob o schema novo |
| `testes/teste_nome_de_membro_e_anomalia.py` | o nome de membro de container e o campo `anomalia` — a única suíte que constrói `.zip` **no nível do byte** |
| `testes/teste_equivalencia_modulo2.py` | a cópia contra o Módulo 2 |
| `testes/teste_integracao_maestro.py` | os dois handoffs e a ordem da cadeia |
| `.gitignore` | preparado, mas **esta pasta NÃO é repositório Git** — ver D1.4 |

---

## 3. O contrato de saída

`schema_version` = **`3.0.0`**, declarado em `inventario.SCHEMA_VERSION` e gravado no corpo do inventário.

| versão | quando | por que subiu, e é MAIOR |
|---|---|---|
| `1.0.0` | D1 | o contrato nasceu |
| `2.0.0` | D2 | `modificado_em` de arquivo solto mudou de significado e de texto |
| `3.0.0` | D3 | **UMA** subida cobrindo as **duas** correções: `caminho` de membro pode mudar de valor (e entra na identidade do diff), `anomalia` mudou de significado, e o total de anomalia foi renomeado |

**Uma subida só, e não duas**, porque duas custariam **duas** execuções sem diff e uma basta. A guarda da D2 trata a migração sozinha — a D3 **provou** que ela continua valendo, e não a reimplementou.

Por edital: `codigo_edital` (a identidade — o Código ConLicitação existente, no formato `CONLIC-{id}`), `codigo_conlicitacao`, `linha_agenda`, `cidade`, `uf`, `numero_pregao`, `data_limite`, `chave_pasta`, `estado_pasta`, `anomalia`, `pasta_relativa`, `arquivos[]`, `achados[]`.

**`anomalia` significa «NÃO É ROTINA»** — e não «a pasta não existe», que era o significado até a D3:

| estado | natureza | `anomalia` |
|---|---|---|
| `COM_ARQUIVO` | rotina | `False` |
| `VAZIA` | rotina | `False` |
| `AUSENTE` | **anomalia** | `True` |
| `AMBIGUA` | **anomalia** | `True` |

A fonte única é `inventario.ESTADOS_DE_ANOMALIA`. O campo por edital e o total `editais_com_anomalia` leem os dois de lá — é por isso que o total **fecha** com a contagem por estado por construção, e não por coincidência.

Por arquivo: `caminho` (relativo à pasta do edital), `tamanho_bytes`, `modificado_em`, `extensao`, `onde_estava` (`SOLTO_NA_PASTA` ou `DENTRO_DO_CONTAINER`), `container`, `artefato_do_m1`.

**`modificado_em` tem DUAS semânticas, e o próprio valor diz qual é:**

| `onde_estava` | formato | significado |
|---|---|---|
| `SOLTO_NA_PASTA` | `AAAA-MM-DDTHH:MM:SS`**`Z`** | **instante UTC**, derivado do `mtime` do sistema de arquivos |
| `DENTRO_DO_CONTAINER` | `AAAA-MM-DDTHH:MM:SS` (sem `Z`) | **hora de parede sem fuso**, exatamente como o índice do ZIP a registra |

A distinção é **1:1 com `onde_estava`** — nenhum campo novo foi criado para carregá-la. O formato ZIP não guarda fuso; convertê-la para UTC exigiria adivinhar, e adivinhar fuso é inventar metadata. As duas famílias **nunca são comparadas entre si**: o `container` entra na identidade do diff.

**Não há SHA-256 no inventário** — o hash pertence a quem for processar o arquivo.

**Estados da pasta:** `AUSENTE` (anomalia) · `VAZIA` (rotina) · `COM_ARQUIVO` (rotina) · `AMBIGUA` (anomalia, fail-closed).

> ⚠ **ATÉ A D3 ESTA LINHA DIZIA «`AUSENTE` (anomalia) · `VAZIA` (rotina) · `COM_ARQUIVO` · `AMBIGUA` (fail-closed)», e o campo `anomalia` era `estado == ESTADO_AUSENTE`.** O `AMBIGUA` — o mais grave dos quatro — saía marcado como rotina. Ver a anotação de superação em §6, ao lado da D1.

**O nome de membro de container é LIDO POR REGRA DECLARADA, desde a D3.** Quando o bit `0x800` do índice do `.zip` está desligado, o container não declarou a codificação do nome, e pode haver duas leituras possíveis dos mesmos bytes. Ver D3.1. Os dois achados novos:

| achado | quando |
|---|---|
| `ENCODING_NOME_NAO_DECLARADO` | havia **UM** único candidato plausível; ele foi adotado, e o descartado vai escrito no achado |
| `ENCODING_NOME_AMBIGUO` | havia **DOIS**, ou **NENHUM**; o `caminho` fica na leitura cp437, e o achado **não afirma qual é o verdadeiro** |

O corpo do inventário **não carrega relógio, caminho absoluto, máquina nem usuário** — é o que permite compará-lo byte a byte. Esses dados vivem no relatório de execução, ao lado.

**Provado, e não só declarado:** a mesma árvore gerada em `America/Sao_Paulo`, `UTC` e `Asia/Tokyo` produz saída serializada **idêntica byte a byte**, com `modificado_em` dentro da comparação (`testes/teste_determinismo_fuso.py`).

---

## 4. O que a medição encontrou na base real

Medido na D1, **reconfirmado na D2 e reconfirmado na D3** — a base não mudou entre as três: os mesmos 2040/1053/817/170 e as mesmas 4482 entradas, número a número. Somente leitura, sobre `C:\Editais 2026` e `C:\licitacoes\dados\Agenda_Licitacoes.xlsx` (aba `2026`).

| medida | valor | unidade |
|---|---|---|
| linhas da Agenda inventariadas | 2040 | linha da Agenda |
| — `AUSENTE` (anomalia) | 1053 | linha da Agenda |
| — `COM_ARQUIVO` | 817 | linha da Agenda |
| — `VAZIA` (rotina) | 170 | linha da Agenda |
| — `AMBIGUA` | 0 | linha da Agenda |
| pastas de edital em disco | 989 | pasta |
| — associadas a uma linha | 987 | pasta |
| — órfãs (pasta sem linha) | 2 | pasta |
| entradas de arquivo | 4482 | entrada de arquivo |
| — soltas na pasta | 2414 | entrada de arquivo |
| — dentro de container | 2068 | entrada de arquivo |
| — marcadas artefato do M1 | 1558 | entrada de arquivo |
| — de zero byte | 1 | entrada de arquivo |

Os estados somam exatamente 2040; soltas + dentro somam exatamente 4482; 987 + 2 = 989. A conferência campo a campo está em `_rodada_inventariador\execucao_real\conferencia_dos_numeros.txt`.

**`AUSENTE` em 1053 das 2040 linhas (51,6%) é o achado mais pesado da frente.** O Módulo 1 cria a pasta do edital **sempre**, antes do download e de propósito — logo, mais da metade da Agenda aponta para pastas que não estão mais no disco. O Inventariador **registra e segue**; decidir o que fazer com isso não é desta frente.

### Achados declarados

| achado | ocorrências | desde |
|---|---|---|
| `CONTAINER_ANINHADO` | 97 (85 `.zip` dentro de `.zip` + 12 `.rar`/`.7z`) | D1 |
| `SUBPASTA_DENTRO_DO_CONTAINER` | 19 | D1 |
| `MAIS_DE_UM_CONTAINER_NA_PASTA` | 13 | D1 |
| `CONTAINER_NAO_INVENTARIAVEL` | 8 | D1 |
| `SUBPASTA_NA_PASTA_DO_EDITAL` | 3 | D1 |
| `ENCODING_NOME_NAO_DECLARADO` | **1** | **D3** |
| `ENCODING_NOME_AMBIGUO` | **0** | **D3** |

Os cinco primeiros saíram **idênticos** aos da D1 e da D2. Os dois últimos são desta rodada.

### O que a D3 mediu de novo na base real — placar, não alvo

| medida | valor | unidade |
|---|---|---|
| membros com achado de codificação | **1** | membro de container |
| — do tipo `ENCODING_NOME_NAO_DECLARADO` | 1 | membro de container |
| — do tipo `ENCODING_NOME_AMBIGUO` | 0 | membro de container |
| denominador: membros dentro de container | 2068 | membro de container |
| `caminho` de membro que mudaram de valor | **1** | membro de container |
| editais que mudaram de `anomalia` | **0** | linha da Agenda |
| editais que mudaram de estado da pasta | 0 | linha da Agenda |

**1 em 2.068 é 0,05%** — e é o que se esperava de uma falha que só atinge nome **não-ASCII** gravado por zipador que não liga o bit `0x800`. Os outros 2.067 são ASCII ou têm o bit ligado, e não têm como errar. O que torna esse 1 relevante não é o tamanho: é ser **falha silenciosa**, que é a classe que este projeto existe para não ter.

**Zero editais mudaram de `anomalia`, e o zero está explicado:** o §4.2 só muda o valor para editais em `AMBIGUA`, e a base real tem **zero** `AMBIGUA` — medido na D1, reconfirmado na D2, reconfirmado agora. Zero é a **consequência** desse fato, não prova de que a correção não faça nada. A prova de que ela funciona está na suíte, onde a fixture constrói o `AMBIGUA` de propósito. **O risco que ela fecha é de amanhã.**

**Nenhuma divergência com medição anterior.** Os totais, os estados e os cinco achados antigos batem número a número com a D1 e a D2. O detalhe está em `_rodada_fechamento_inventariador\execucao_real\PLACAR_BASE_REAL.txt`.

---

## 5. As suítes

| suíte | provas | desfecho |
|---|---|---|
| `testes/teste_inventario.py` | 115 | todas passaram |
| `testes/teste_determinismo_fuso.py` | 62 | todas passaram |
| `testes/teste_nome_de_membro_e_anomalia.py` | 89 | todas passaram |
| `testes/teste_equivalencia_modulo2.py` | 11 (sobre 12 linhas sintéticas) | todas passaram |
| `testes/teste_integracao_maestro.py` | 54 | todas passaram |
| **total desta frente** | **331** | **todas passaram** |

Eram 165 na D1 e 227 na D2. As **104** novas são da D3: 89 na suíte nova, 14 na de fuso (a guarda sob o schema novo) e 1 na sintética (`AMBIGUA` é anomalia, colada no teste que constrói a ambiguidade).

**Uma asserção foi ATUALIZADA, nenhuma foi removida.** `teste_determinismo_fuso.py` travava `SCHEMA_VERSION == "2.0.0"` — fato que esta rodada mudou. Passou a travar `"3.0.0"`, com o motivo escrito ao lado, preservando a intenção da prova: o número da versão não pode mudar por acidente. É a mesma regra da D1.10.

**Rodar em SÉRIE.** As suítes do Maestro medem relógio e dão falso vermelho sob disputa de CPU.

Equivalência com o Módulo 2 **também medida sobre a base real**: 2040 linhas, 29.547 comparações, **0 divergências** (`_rodada_inventariador\execucao_real\equivalencia_base_real.txt`).

As 13 suítes pré-existentes do Maestro estavam verdes no Gate 0 e continuam verdes no Gate Final — as 13, uma a uma, com código de saída 0.

---

## 6. DECISÕES VIGENTES

### 6.0 — HISTÓRICO: a auditoria independente BLOQUEOU a homologação da D1

**Fato registrado, não apagado.** A auditoria independente recusou homologar a D1 por **um** defeito de contrato, e tinha razão.

O enunciado da D1 exigia: *«Mesma entrada lógica e mesmo conjunto de arquivos → mesmo inventário, byte a byte. Sem depender de ordem do sistema de arquivos, horário, máquina ou usuário.»* A implementação não cumpria:

- `inventario.py` usava `datetime.fromtimestamp(os.path.getmtime(...))`, que depende do fuso da máquina;
- a **D1.9 reconhecia o defeito e o declarava como limite aceitável** — quando o contrato não o permitia;
- a suíte `teste_ordem_deterministica_e_mesmo_conjunto_mesmo_inventario()` substituía `modificado_em` por `"(ignorado)"` antes de comparar. **Um teste que apaga o campo defeituoso antes de olhar não prova nada sobre ele.**

E o argumento escrito na docstring — «gravar UTC de um lado e hora local do outro tornaria os dois incomparáveis» — **era falso, e a refutação estava no próprio código**: `diff_inventario.identidade()` inclui o `container`, então arquivo solto nunca casa com membro de `.zip`, e a comparação cruzada que o argumento temia não existia.

A D2 corrigiu isso. **A D1 não deixou de ter existido, e não foi editada para parecer correta.**

### D1 — 2026-09-14 — Nascimento da frente Inventariador

A primeira decisão desta frente. A numeração `D` daqui é **própria**, começa em `D1`, e **não continua nem referencia** a numeração do Módulo 2 ou do Módulo 3.

**D1.1 — A base do código é o `modulo2/utils.py`, copiado; não o `inventario_ground_truth.py` do Módulo 3.**
Medido: o `_RE_PASTA_PROCESSO` do arquivo do M3 é `^MODALIDADE\s+\d+[-/]\d{4}$`, ancorado no `$` logo depois do ano — a convenção vigente (`PE 35-2026 - CONLIC-19241283`) não casa e cai no *fallback*, que perde número e ano e nunca extrai o código. O que aproveita dele é **doutrina, não código**: nunca `extractall()` na pasta oficial, container aninhado lido do índice, saída determinística, e a própria ideia de versão de formato. O arquivo do M3 **não foi movido, apagado, renomeado nem alterado**.

**D1.2 — A identidade do edital é o Código ConLicitação existente, no formato `CONLIC-{id}`.**
Nenhum ID paralelo, UUID próprio ou segundo código é criado. Medido na base real: 2040 identidades distintas em 2040 registros, todas derivadas só do código da Agenda.

**D1.3 — O diff compara por `(codigo_edital, container, caminho)`, e `ALTERADO` é diferença de `tamanho_bytes` ou `modificado_em`.**
O nome sozinho não basta: a base real tem 13 pastas com mais de um `.zip`, e o mesmo nome de membro aparece dentro de containers diferentes do mesmo edital. `ALTERADO` **não afirma que o conteúdo mudou** — sem SHA-256 não há como afirmar isso. O inventário anterior vem de `PASTA_SAIDA\inventario_atual.json`, preservado como `inventario_anterior.json` no começo de cada execução; sem anterior, o diff sai declarado vazio, e **nenhuma base vazia é fabricada**.
**O diff NUNCA responde «o que falta processar».**

**D1.4 — Esta pasta NÃO foi transformada em repositório Git nesta rodada.**
O enunciado autorizava `git init` «se ela precisar ser repositório». Ela não precisou: nada nesta rodada exigiu versionamento, e nascer como repositório sem commit deixaria uma árvore inteira não rastreada. Virar o quinto repositório do projeto é decisão de arquitetura do Oz, e pede a mesma auditoria de segredo e `.gitignore` que os outros quatro passaram. O `.gitignore` já está escrito, para o dia em que a decisão for tomada.

**D1.5 — Na cadeia do Maestro, o Inventariador é `id=5` na SEGUNDA posição da lista.**
A cadeia executa na **ordem da lista**, não na dos números. Renumerar para 1-2-3-4 deixaria vermelha a suíte pré-existente `teste_etapa9_parada`, que lê a cadeia REAL e cobra que a etapa 2 seja protegida do watchdog — e o Inventariador **pode** ser forçado, porque só lê. O `id=4` segue reservado ao Módulo 3, no bloco comentado do `maestro.py`. O `id` é identidade; quem diz a ordem é o lugar na lista.

**D1.6 — O handoff para o Módulo 2 é de ORQUESTRAÇÃO, não de dados.**
O inventário **não** virou entrada do Módulo 2. Ele continua descobrindo o que processa do mesmo jeito: lendo a Agenda e olhando o disco, sem parâmetro. Mudou **só quem roda antes de quem**. A etapa do Módulo 2 tem o mesmo `id`, `nome`, `cwd`, `script`, `args` (vazios), `log_dir`, `log_sufixo`, `ambiente_extra` e as mesmas proteções do Gate 0 — e `teste_integracao_maestro.py` tranca cada um desses campos contra um retrato do Gate 0.

**D1.7 — `estado_pasta` segue a regra do Módulo 2; a neutralidade do §4.5 vale para a LISTA de arquivos.**
Uma pasta com só `.docx` continua `VAZIA`, porque é isso que `pasta_tem_arquivo_edital()` decide em produção — e é o que mantém a equivalência. Mas o `.docx` **entra** no inventário, como entram `resumo_edital.*` (marcados como artefato do M1), arquivos de zero byte e nomes repetidos em caminhos diferentes. **Lista tudo e marca a origem; quem filtra é o consumidor.**

**D1.8 — Não se desce mais de um nível sem regra escrita.**
Subpasta na pasta do edital, subpasta dentro do container e container aninhado (`.zip` dentro de `.zip`, `.rar`, `.7z`) são **declarados como achado** e **não percorridos**. O `.zip` solto na pasta é aberto pelo índice — esse é o único nível. **Todos** os `.zip` da pasta são abertos, e não só o primeiro: o `listar_arquivos_edital()` do Módulo 2 abre `zips[0]` e para, o que esconderia o conteúdo dos demais em 13 pastas da base real.

**D1.9 — A data de modificação é lida em hora local dos dois lados, e o limite está declarado.**
O índice do ZIP guarda hora local sem fuso; para os dois lados falarem a mesma língua, a data do sistema de arquivos também é lida em hora local. **Consequência declarada:** rodar o mesmo inventário em máquinas com fusos diferentes desloca a data dos arquivos soltos. O determinismo vale **por máquina/volume** — que é onde o diff é usado.

> ⚠ **D1.9 FOI SUPERADA PELA D2.1 em 2026-09-14.** O texto acima fica como foi escrito, e está errado: o contrato da D1 não admitia esse limite, e a auditoria independente bloqueou a homologação por causa dele. O que vale hoje é a D2.1. Esta anotação é registro, não correção do texto original.

**D1.10 — Quatro suítes pré-existentes do Maestro tiveram asserções atualizadas, e nenhuma mudou de desfecho.**
Elas codificavam «a cadeia tem exatamente TRÊS etapas» — fato que a integração autorizada por esta rodada mudou. Foram atualizadas para quatro, com o motivo escrito ao lado, preservando a intenção de cada prova. **Todas as 13 suítes do Maestro estavam verdes no Gate 0 e estão verdes no Gate Final.** O diff completo está no pacote.

---

> ⚠ **ANOTAÇÃO DE SUPERAÇÃO, ESCRITA NA D3 em 2026-09-14 — sobre a definição de `anomalia` que veio da D1.**
>
> **Ela é registro, e fica AO LADO. Nada do texto da D1 acima foi editado, e nada deve ser.**
>
> **ONDE ESSA DECISÃO MORAVA — e a medição é desconfortável:** o ledger da D1 tem dez itens numerados, de D1.1 a D1.10, e **nenhum deles decide sobre o campo `anomalia`.** A definição vivia em dois lugares: no §3 deste documento (a linha «`AUSENTE` (anomalia) · `VAZIA` (rotina)») e no código, como `"anomalia": estado == convencao.ESTADO_AUSENTE`. **Uma decisão de contrato que nunca entrou no ledger é decisão que ninguém revisa** — e foi exatamente essa que envelheceu errada.
>
> **O QUE ESTAVA ERRADO:** o campo chamado `anomalia` significava, literalmente, «a pasta não existe». O `AMBIGUA` — **o mais grave dos quatro estados**, porque significa que não se sabe qual pasta é a do edital — saía com `anomalia: False`, isto é, marcado como rotina.
>
> **A ORIGEM DO DEFEITO ESTÁ DECLARADA, E NÃO É DA IMPLEMENTAÇÃO:** o enunciado da D1 definiu a palavra «anomalia» em cima da dupla `VAZIA`/`AUSENTE`, no §4.7, e **não voltou** para incluir o `AMBIGUA`, que entrou pelo §4.6. **A implementação obedeceu ao que estava escrito.**
>
> **O QUE VALE HOJE É A D3.2.** E, para a mesma omissão não se repetir, a decisão agora está **numerada no ledger**, e a regra tem **fonte única no código** (`ESTADOS_DE_ANOMALIA`).

---

### D2 — 2026-09-14 — Correção do determinismo de `modificado_em`

Rodada **estritamente corretiva**, aberta pelo bloqueio da auditoria descrito em §6.0. O primeiro `D` livre medido no ledger desta frente era `D2`.

**D2.1 — `modificado_em` de arquivo SOLTO passou a ser INSTANTE UTC, com o sufixo `Z`. Supera a D1.9.**
`os.path.getmtime()` já devolvia um instante POSIX, que não depende de fuso nenhum — o defeito estava na renderização, não no dado. `datetime.fromtimestamp(ts)` sem `tz` convertia para a hora de parede da máquina. Com `tz=timezone.utc`, a renderização passou a ser função só do instante.
Medido, para o mesmo instante: `America/Sao_Paulo` dava `2026-09-14T15:31:01`, `UTC` dava `…T18:31:01`, `Asia/Tokyo` dava `2026-09-15T03:31:01`. Hoje os três dão `2026-09-14T18:31:01Z`.

**D2.2 — A data de membro de ZIP NÃO foi convertida, e a ausência do `Z` é o dado.**
O formato ZIP grava data e hora no campo MS-DOS, que é hora de parede **sem fuso registrado**. Converter exigiria adivinhar em que fuso o arquivo foi zipado — e o §4 da rodada proíbe inventar metadata. Ela já era determinística: vem dos bytes do arquivo, não do relógio de quem lê. Foi a única das duas famílias que o defeito nunca atingiu.
**Nenhum campo novo foi criado** para carregar a distinção: ela está no valor (é como a ISO-8601 distingue os dois casos) e é 1:1 com `onde_estava`, que já existia. Um campo a mais seria uma terceira cópia da mesma informação, com uma terceira chance de divergir.

**D2.3 — `schema_version` subiu de `1.0.0` para `2.0.0`, e `comparar()` RECUSA comparar versões diferentes.**
MAIOR pela regra do próprio arquivo: um campo existente mudou de significado e de texto. A recusa sai **pelo mesmo caminho** que já existia para «não há inventário anterior» — diff vazio e declarado, sem fabricar base — com o `motivo` dizendo qual dos dois casos foi.
**Medido na base real:** sem a guarda, a primeira execução depois da correção despejaria **2.414 `ALTERADO`**, um por entrada solta, todos com `campos_diferentes: ["modificado_em"]`, sem que arquivo nenhum tivesse mudado; os 2.068 membros de ZIP sairiam `INALTERADO`. 2.414 + 2.068 = 4.482, o total de entradas.
**A razão não é estética:** um alarme falso do tamanho da base ensina a equipe a ignorar o diff. Um sinal que grita todo dia morre, e depois disso a alteração de verdade passa despercebida. Falha barulhenta é segura uma vez; barulho constante vira falha silenciosa.

**D2.4 — A suíte deixou de mascarar `modificado_em`, e passou a carimbar a metadata factual.**
O teste de determinismo comparava dois inventários depois de substituir `modificado_em` por `"(ignorado)"`. Agora as duas árvores recebem o MESMO `mtime` (`os.utime`) e a MESMA data no índice do ZIP (`ZipInfo.date_time`), e a comparação é **total** — o campo entra nela. Mascarar era o que fazia o teste passar sem provar nada.

**D2.5 — O fuso é trocado por SUBPROCESSO, e a prova de que ele mudou vem junto.**
`time.tzset()` não existe no Windows, mas a variável `TZ` no ambiente do processo funciona. Cada geração roda num subprocesso próprio com `TZ` diferente, e cada um reporta `time.timezone` e `datetime.fromtimestamp(0)` **antes** de gerar: `10800` / `0` / `-32400`, e três épocas diferentes. Sem essa prova, um teste verde não distinguiria «a correção funciona» de «o teste não mede nada». Há ainda uma **contraprova**: a renderização antiga, rodada nos mesmos três fusos, dá três valores diferentes.

**D2.6 — O log da execução passou a dizer o MOTIVO real da ausência de base.**
Ele anunciava «primeira execução» em qualquer caso sem base, e passou a mentir no dia em que apareceu o segundo caso: havia inventário anterior, e o log dizia que não havia. Agora imprime o `motivo` que vem do diff, e as duas versões de schema. **Um log que descreve a causa errada é pior que um log ausente** — e foi encontrado justamente por rodar a correção contra a base real antes de fechar.

---

### D3 — 2026-09-14 — Fechamento: o nome do membro de container e a abrangência de `anomalia`

Rodada **estritamente corretiva**, de **dois** defeitos e de mais nenhum. Aberta porque **as duas auditorias independentes convergiram sobre a D2**, e porque estes eram dois dos três achados que a D2 deixou de fora **de propósito** (§7 da D2). O terceiro — os 8 downloads que gravaram não-zip — **continua fora**, porque é frente do Módulo 1.

O primeiro `D` livre medido no ledger **próprio** desta frente era `D3`: ocupados estavam `D1` (com D1.1 a D1.10) e `D2` (com D2.1 a D2.6).

**D3.1 — O nome de membro de container passou a ser lido por REGRA DECLARADA, e nunca reescrito em silêncio.**

O `.zip` guarda o nome do membro em **bytes**, e o bit `0x800` dos `flag_bits` declara se esses bytes estão em UTF-8. Com o bit desligado, o `zipfile` do Python decodifica como **cp437** — e há zipadores que gravam UTF-8 sem ligar o bit. Todo caractere acentuado sai trocado, **sem erro e sem aviso**.

*Medido na base real:* dos **2.068** membros dentro de container, **1** saía corrompido. É 0,05%, e é **falha silenciosa** — a classe que este projeto existe para não ter.

*Por que a suíte antiga não pegava:* o `zipfile` do Python **sempre** liga o bit `0x800` em nome não-ASCII. O teste de «nomes com acentos» passava **por construção**, e não poderia falhar. Foi por isso que a D3 criou uma suíte que constrói o `.zip` **no nível do byte** — escrevendo com um nome-marcador ASCII de mesmo comprimento e trocando os bytes depois, o que deixa o bit desligado sem deslocar offset nenhum.

**A REGRA, e ela é genérica — não há nome de arquivo, município nem valor em lugar nenhum do código:**

| situação | `caminho` | achado |
|---|---|---|
| bit `0x800` **LIGADO** | inalterado — o índice declarou, e declaração é o que se pede | nenhum |
| nome **ASCII puro** | inalterado — as duas leituras coincidem | nenhum |
| **UM** candidato plausível | esse candidato | `ENCODING_NOME_NAO_DECLARADO`, com a leitura adotada **e a descartada** |
| **DOIS** plausíveis | a leitura **cp437** | `ENCODING_NOME_AMBIGUO`, com **as duas leituras** |
| **NENHUM** plausível | a leitura **cp437** | `ENCODING_NOME_AMBIGUO`, com as duas, se houver duas |

**UTF-8 VÁLIDO NÃO É UTF-8 COMPROVADO.** cp437 é mapeamento **total** — todo byte vira algum caractere —, então a leitura cp437 **existe sempre**. Se os bytes também formarem UTF-8 válido, há **duas** leituras, e adotar UTF-8 só porque ele decodifica seria transformar ambiguidade real em certeza inventada.

**A escolha do `caminho` na ambiguidade é de ESTABILIDADE, não de verdade:** cp437 por ser determinística e igual à da versão anterior — e porque `caminho` entra na identidade do diff, então trocá-la sem necessidade inventaria um REMOVIDO e um ADICIONADO por membro. O achado diz, com todas as letras, que **não afirma qual é o verdadeiro**.

**D3.1.1 — O filtro de plausibilidade é ENUMERADO no código, e as faixas saem de medição.**

`FAIXAS_IMPLAUSIVEIS_EM_NOME`, em `inventario.py`:

| faixa | o que é |
|---|---|
| U+0000–U+001F | caracteres de controle |
| U+007F–U+007F | DEL |
| U+2200–U+22FF | operadores matemáticos |
| **U+2300–U+23FF** | **técnicos diversos — ACRESCENTADA pela D3** |
| U+2500–U+257F | desenho de caixa |
| U+2580–U+259F | elementos de bloco |
| U+25A0–U+25FF | formas geométricas |

*A medição que as justifica, byte a byte:* os bytes que **lideram** sequência UTF-8 de dois bytes são `C2`–`DF`, e é aí que caem **todos** os acentos latinos. Em cp437 esses 30 bytes viram, sem exceção, **desenho de caixa** (25 deles) ou **elementos de bloco** (5). Um nome UTF-8 lido como cp437 **exibe desenho de caixa**, e nome de arquivo não tem desenho de caixa.

*Por que a faixa acrescentada:* exatamente três bytes caem em U+2300–23FF — `0xA9`→`⌐`, `0xF4`→`⌠`, `0xF5`→`⌡` — e o `0xA9` é **byte de continuação**, isto é, aparece em nome UTF-8 mal lido de verdade (`é` = `C3 A9` vira `├⌐`). Nenhum dos três ocorre em nome de arquivo.

*O que fica de fora DE PROPÓSITO:* os líderes de **três** bytes (`E0`–`EF`) viram, em sua maioria, **letra grega**. Grego **não** entra no filtro, porque letra grega ocorre em nome de arquivo. **É exatamente esse vão que torna possível a ambiguidade real** — e fechá-lo por conveniência seria transformar dúvida em certeza. O vão fica aberto, e a ambiguidade é declarada.

**D3.2 — `anomalia` passou a significar «NÃO É ROTINA»: verdadeira para `AUSENTE` e para `AMBIGUA`.**

Supera a definição herdada da D1 — ver a **anotação de superação** escrita ao lado do bloco da D1, que registra também o fato de que aquela decisão **nunca chegou a ser numerada no ledger**.

`ESTADOS_DE_ANOMALIA` é a **fonte única**: o campo por edital e o total do `resumir()` leem os dois dela. É isso que faz o total **fechar** com a contagem por estado **por construção**, e não por coincidência.

**O `AMBIGUA` NÃO foi removido, nem colapsado noutro estado, nem passou a escolher pasta.** O fail-closed da D1 é a garantia mais forte desta frente e ficou **exatamente como estava**: `pasta_relativa` segue `None`, `arquivos` segue vazio, e o achado segue nomeando as candidatas.

*Risco hoje: nenhum* — a base real tem **zero** `AMBIGUA`. *Risco amanhã:* o publicador, um relatório ou a equipe filtrarem por `anomalia` e o caso ambíguo passar como rotina.

**D3.3 — O total `editais_com_anomalia_pasta_ausente` foi RENOMEADO para `editais_com_anomalia`.**

O nome antigo dizia **um** estado e, com a D3.2, passou a contar **dois**. **Um número cujo nome descreve menos do que ele mede é pior que um número ausente: quem lê acredita.**

Escolhida a renomeação, e **não** a quebra por estado, porque a quebra por estado **já existe ao lado**, em `editais_por_estado_da_pasta`. Uma segunda seria a terceira cópia do mesmo fato, com uma terceira chance de divergir — o mesmo argumento que a D2.2 usou para não criar campo novo.

O log da execução também deixou de somar os dois: agora imprime `AUSENTE` e `AMBIGUA` **separados**, porque pedem ações diferentes da equipe.

**D3.4 — `schema_version` subiu de `2.0.0` para `3.0.0`, numa subida SÓ, cobrindo as duas correções.**

MAIOR pela regra do próprio arquivo, por três motivos somados: `caminho` de membro pode mudar de valor e **entra na identidade do diff**; `anomalia` mudou de significado; e um campo publicado sumiu do corpo (o total renomeado).

**Duas subidas custariam DUAS execuções sem diff, e uma basta.** A guarda da D2 trata a migração sozinha — esta rodada **não a reimplementou**, e sim **provou** que ela continua valendo sob a versão nova, nos dois sentidos: `2.0.0 × 3.0.0` sai declarado sem base (`0/0/0/0`), e `3.0.0 × 3.0.0` **continua acusando** `ALTERADO` quando há mudança real, **inclusive quando só a data muda e o tamanho é idêntico**. Essa segunda metade existe porque uma guarda mal feita «resolve» o alarme falso matando o diff inteiro — e **uma guarda que cala o sinal de verdade é pior que o alarme que ela evitou**.

**D3.5 — A medição precede a regra, e a medição está no pacote.**

As faixas do filtro não foram escolhidas por impressão: a tabela dos 256 bytes — o que cada um vira em cp437 e que papel tem em UTF-8 — foi gerada **antes** de a regra ser escrita, e é ela que diz por que desenho de caixa entra e grego não. Está em `_rodada_fechamento_inventariador\provas\MEDICAO_DAS_FAIXAS.txt`. **Regra sem medição ao lado é palpite com aparência de norma.**

**D3.6 — A D3 foi entregue com o Gate Final `BLOQUEADO`, e o bloqueio foi regularizado por autorização expressa do Oz, com a remoção feita MANUALMENTE por ele.**

Este item existe para que o bloqueio **não desapareça da história**. Ele aconteceu, foi declarado, e a regularização veio depois — nessa ordem, e é assim que fica registrado.

**O BLOQUEIO ORIGINAL — o que foi, e de quem foi a culpa**

O Gate Final da D3 saiu **`BLOQUEADO`** por **uma** diferença não autorizada: dois arquivos de bytecode nascidos em `C:\licitacoes\inventariador\__pycache__\`.

| caminho | tamanho | SHA-256 | nascido |
|---|---:|---|---|
| `__pycache__\inventario.cpython-314.pyc` | 33.669 B | `45968854dad0e62149c03333f552527dea56376725e4aef12ea2dbe531fa21fd` | 2026-09-14 18:36:57 |
| `__pycache__\inventariador.cpython-314.pyc` | 16.738 B | `1e59d725efc7c1918df7368de97a7b0e740a42a0f7a033118c8e0c2751721560` | 2026-09-14 18:36:57 |

**A culpa é do instrumento, não do código entregue.** Foi uma invocação auxiliar — `python -B -m py_compile`, usada como conferência de sintaxe depois de aplicar a correção. **Os dois mecanismos do §7 estavam ligados e não bastam:** `python -B` e `PYTHONDONTWRITEBYTECODE=1` desligam a gravação **automática** de bytecode no import, e gravar o `.pyc` é a **função** do `py_compile`. O erro foi escolher a ferramenta, não esquecer o mecanismo.

**A exceção da D41 não cobria**, e não podia: ela é para arquivo de **zero byte**, em `logs/`/`saida/`/`relatorios/`, nascido **de import**. Estes falhavam nos três critérios. Alargá-la para caber neles seria usar uma exceção escrita para outra coisa como desculpa.

**POR QUE A D3 NÃO OS APAGOU SOZINHA**

Apagar arquivo é **irreversível**, e o §2 do enunciado da D3 não autorizava «limpeza, restauração ou normalização do working tree». Havia argumento honesto do outro lado — os arquivos foram criados *pela própria rodada*, e removê-los devolveria o repositório exatamente ao Gate 0 —, mas **declarar é reversível e apagar não é**. Ficaram como estavam, com a identidade registrada, e a decisão foi para o Oz.

**A AUTORIZAÇÃO, E QUEM EXECUTOU**

Oz autorizou **expressamente** e removeu **manualmente** os **dois arquivos acima, e só eles**. Esta frente **não removeu arquivo nenhum** — o papel dela foi medir e provar o estado resultante. **Quem apagou não é quem atesta que apagou**, e a auditoria pode ler as duas coisas separadas.

**A PROVA DE AUSÊNCIA**

Pelo **erro real do sistema de arquivos**, a mesma convenção que a D1 usou em `prova_inexistencia_ledger.txt`:

```
os.stat() -> FileNotFoundError: [WinError 2] O sistema não pode encontrar o arquivo especificado
os.path.exists() -> False
```

para os dois caminhos, mais varredura completa do Inventariador: **0 arquivos `.pyc`**.

**A COMPARAÇÃO QUE PROVA QUE A REMOÇÃO FOI EXCLUSIVA**

Novo Gate Final **×** Gate Final BLOQUEADO da D3, mesmo instrumento: `maestro`, `modulo1`, `modulo2` e `modulo3` **byte-idênticos**, e no Inventariador **exatamente DUAS ausências e mais nada**. Nada foi acrescentado, nada foi alterado, **nenhuma outra limpeza ou restauração ocorreu**.

**O QUE A AUTORIZAÇÃO NÃO ALCANÇOU, E FOI RESPEITADO**

O diretório `__pycache__` ficou, **vazio**, e **não foi removido**: a autorização era exclusiva para os dois `.pyc`, e uma autorização específica não se estica para cobrir o que ficou perto dela. **E ele não afeta medição nenhuma** — o inventário desta casa é por caminho, tamanho e SHA-256 de **arquivo**, e diretório vazio não tem nenhum dos três.

**O RESULTADO DO NOVO GATE FINAL**

**`SEM DIFERENÇA NÃO AUTORIZADA`.** As oito diferenças contra o Gate 0 da D3 são as sete autorizadas pelo enunciado da D3 mais este registro documental; a ausência dos dois `.pyc` é classificada como **regularização expressamente autorizada por Oz**. `.pyc`, `logs/`, `saida/` e `relatorios/` voltaram a bater **idênticos** com o Gate 0 nos cinco repositórios, e os dois logs de zero byte de 12/09 do M3 seguem intocados.

**As suítes NÃO foram rodadas de novo, e o motivo é medido:** nenhum arquivo de código ou de teste mudou desde a D3 — os hashes dos oito arquivos batem byte a byte com os do Gate Final dela. Rodar de novo mediria o mesmo código e não provaria nada que a D3 já não tenha provado.

**D3.7 — Um achado NÃO pedido, encontrado ao repetir a medição da regularização.**

O arquivo `_rodada_fechamento_inventariador\gate0\EFEMEROS_GATE0.txt`, entregue no pacote da D3, está **contaminado — e ainda crescendo**. A causa é um processo órfão que a D3 deixou vivo: o script de shell da primeira tentativa de medir os efêmeros foi interrompido por lentidão, mas a interrupção matou o **shell** e não a cadeia de filhos dele, que seguiu segurando o descritor do arquivo de saída. Quando o script Python o reescreveu, os dois passaram a escrever no mesmo lugar, e o vão entre os dois virou **89.740 bytes NUL**.

**Nenhuma conclusão da D3 depende daquele arquivo.** Ele é uma visão **derivada**; a medição primária são as cinco TSVs `inventario_*_GATE0.tsv`, que estão **limpas, com zero byte NUL**. A visão correta foi **regerada delas**, sem remedir nada, e é a que sustenta as comparações da regularização.

**O órfão não escreve em repositório nenhum** — o comando dele é `find` + `sha256sum` + `stat`, tudo leitura, e a única escrita é no arquivo de saída, fora dos cinco repositórios. A prova está na própria regularização: os quatro repositórios saíram byte-idênticos.

**Duas decisões ficaram pendentes do Oz, e nenhuma foi tomada sem ele:** encerrar o processo órfão, e regerar ou não o arquivo contaminado dentro da evidência da D3.

---

## 7. Onde o trabalho parou

A frente está **construída, testada, integrada à cadeia, com o determinismo corrigido e provado, e com os dois defeitos de contrato fechados**.

Na D3 ela rodou contra a base real duas vezes, encadeadas de propósito, partindo do retrato `2.0.0` que a D2 deixou:

1. `2.0.0` (o que a D2 deixou) contra `3.0.0` → diff **declarado sem base comparável**, `0/0/0/0` — a guarda da D2 fazendo o trabalho dela sob a versão nova;
2. de novo, agora `3.0.0` contra `3.0.0` → diff normal, `0` ADICIONADO · `0` REMOVIDO · `0` ALTERADO · **4.482 INALTERADO**.

A mudança de `caminho` do §4.1 **não aparece no diff, e não deveria**: a guarda recusa comparar schemas diferentes, justamente para a mudança de contrato não virar alarme. Ela foi medida **comparando os dois inventários diretamente** — 1 `caminho` mudou, de 2.068 membros pareados.

**O Maestro NÃO foi reiniciado, nem na D1, nem na D2, nem na D3.** A etapa nova passa a valer na próxima subida do processo (`python maestro.py`) — o `maestro.py` não tem auto-reload.

**Dos três achados que a D2 deixou fora de propósito, dois foram fechados aqui** (nome de membro mal decodificado · `anomalia` não cobrir `AMBIGUA`). **Continua aberto um, e ele não é desta frente:**

> **Os 8 downloads que gravaram não-zip.** É frente do **Módulo 1** — quem grava o arquivo é ele. O Inventariador já os declara, e continua declarando, pelo achado `CONTAINER_NAO_INVENTARIAVEL` (8 ocorrências, o mesmo número desde a D1). **Esta rodada não o tratou, e o enunciado dela o proibia explicitamente.**

**O Gate Final da D3 saiu `BLOQUEADO` e foi REGULARIZADO** — ver D3.6. O estado vigente do working tree é o da regularização: **nenhuma diferença não autorizada**, e `.pyc`/`logs/`/`saida/`/`relatorios/` idênticos ao Gate 0 da D3 nos cinco repositórios.

**Fica ABERTO o achado D3.7** — o processo órfão ainda vivo e o `EFEMEROS_GATE0.txt` contaminado no pacote da D3. Nenhum dos dois afeta código, contrato ou medição primária; ambos esperam decisão do Oz.

**A homologação é da auditoria independente. A frente NÃO está declarada encerrada, e o Inventariador NÃO está homologado.**

---

## 8. O que a D3 NÃO fez

Não implementou o M3 automático · não tratou MRG02 · **não alterou o M1, o M2 nem o M3** · não acrescentou funcionalidade ao Inventariador · não tratou os 1.053 `AUSENTE` · **não tratou os 8 downloads que gravaram não-zip, que são frente do M1** · não mudou schema além do necessário às duas correções · não desceu mais de um nível em container · não abriu `.rar`, `.7z` nem aninhado · **não rodou Git de escrita** · não reiniciou o Maestro · não foi a produção · **não limpou, restaurou nem normalizou o working tree** · não executou o Módulo 3 · não abriu nenhum PDF · não publicou nada.

**E, dentro do próprio escopo, três coisas que ela deliberadamente NÃO fez:**

- **não removeu o `AMBIGUA`, não o colapsou noutro estado, e não fez o Inventariador escolher entre as pastas candidatas.** O fail-closed da D1 ficou exatamente como estava;
- **não fechou o vão do grego no filtro de plausibilidade**, mesmo sendo o que faria a ambiguidade sumir. Fechá-lo transformaria dúvida em certeza inventada;
- **não reimplementou a guarda de schema da D2.** Apenas provou que ela continua valendo.

### E o que a REGULARIZAÇÃO da D3.6 não fez

Não removeu nada · não restaurou nada · não limpou nada · não recompilou nada · **não alterou código** · **não alterou teste** · não alterou M1, M2, M3 nem Maestro · não executou o Módulo 3 · não reiniciou o Maestro · **não rodou as suítes de lógica** (nenhum arquivo de código ou de teste mudou desde a D3 — provado byte a byte) · **não encerrou o processo órfão da D3.7** · **não removeu o `__pycache__` que ficou vazio** · não apagou nem reescreveu o `EFEMEROS_GATE0.txt` contaminado.

**A única coisa que ela escreveu foi documentação:** este arquivo, o sidecar, e o pacote da regularização.

---

## 9. Como atualizar este arquivo

Por **medição do working tree**, ao fechar cada rodada. Nunca por memória, nunca por cópia de versão antiga. Toda decisão do Oz entra em §6 com identificador `D`, data e o que ela decide, **no mesmo fechamento em que foi tomada** — decisão que só existe no histórico de uma conversa é decisão perdida.

Depois de editar: regenerar o sidecar e conferir.

```
cd C:\licitacoes\inventariador
sha256sum ESTADO_ATUAL.md > ESTADO_ATUAL.md.sha256
sha256sum -c ESTADO_ATUAL.md.sha256
```
