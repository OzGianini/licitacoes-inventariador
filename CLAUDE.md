# CLAUDE.md — Instruções Permanentes da Frente (Inventariador)

## 0. Usuário

O nome do usuário é **Osmar Gianini**, conhecido como **Oz**. Sempre se dirija a ele como **Oz**.

## 1. Idioma

Responder sempre **somente em português** (alteração pedida pelo Oz em 2026-07-29; antes disso, cada resposta trazia dois blocos, inglês e depois português).

---

## 2. Contexto — o que esta frente é

O **Inventariador** é uma **frente própria** do projeto "Agente de Licitação", com casa em `C:\licitacoes\inventariador`. Ele não é um dos Módulos 1 a 6.

> **Dado um edital que a cadeia já conhece, diga exatamente quais arquivos existem agora para ele.**
>
> **Nem mais, nem menos.**

Ele roda na cadeia do Maestro **entre o Módulo 1 e o Módulo 2**:

```
M1 (captura)  →  Inventariador  →  M2 (análise)  →  Publicador
```

### O que ele NÃO faz

Não classifica licitação · não executa o Módulo 3 · não abre PDF para extrair · não escolhe «o PDF principal» · não publica na Agenda · **não controla fila do que já foi processado** · não altera, move, renomeia, converte ou extrai qualquer arquivo · não corrige a saída do Módulo 1.

**Por que não guarda fila** — a razão é da própria casa, na docstring do `controle.py` do Módulo 2:

> *«o histórico do M1 diz "já baixei", não "o M2 já analisou". … São dois fatos diferentes, de dois donos diferentes, e ficam em dois arquivos diferentes.»*

«Que arquivos existem agora» e «o que já foi processado» são dois fatos de dois donos. Esta frente é dona só do primeiro.

---

## 3. Regras de segurança — somente leitura, sempre

- `C:\licitacoes\dados\Agenda_Licitacoes.xlsx`: **somente leitura**, sempre (`openpyxl.load_workbook(..., read_only=True)`). Nunca `.save()`.
- A pasta dos editais (`PASTA_EDITAIS`/`PASTA_DESTINO`, hoje `C:\Editais 2026`): **somente leitura**, sempre. Nunca escrever, renomear, excluir ou sobrescrever nada lá.
- Os `.zip` são abertos **apenas pelo ÍNDICE** (`zipfile.infolist()`). Nunca `.read()` de membro, nunca `.extractall()`.
- `C:\licitacoes\modulo1`, `modulo2`, `modulo3` e `maestro`: o Inventariador **não escreve em nenhum deles**.
- Toda saída vai para `saida\`, `logs\` e `relatorios\` desta casa — e as três são sobrepujáveis por ambiente (`PASTA_SAIDA`, `PASTA_LOGS`, `PASTA_RELATORIOS`), para auditoria poder redirecioná-las para fora dos repositórios.

---

## 4. Arquivos principais

| arquivo | papel |
|---|---|
| `inventariador.py` | ponto de entrada — é o que o Maestro executa. Roda **sem parâmetro**. |
| `inventario.py` | o inventário em si: estado da pasta, arquivos, achados, ordem determinística |
| `convencao_edital.py` | **cópia deliberada** da lógica provada do `modulo2/utils.py` |
| `agenda.py` | leitura somente-leitura da Agenda, por nome de cabeçalho |
| `diff_inventario.py` | reinventário e diff — `ADICIONADO`/`REMOVIDO`/`ALTERADO`/`INALTERADO`, e a recusa de comparar schemas diferentes |
| `inventario._ler_nome_de_membro()` | a leitura do nome de membro de container quando o índice não declara a codificação — ver §6 |
| `config.py` | os caminhos, num lugar só |

---

## 5. A regra mais importante — a cópia não pode envelhecer

`convencao_edital.py` e `agenda.py` são **cópia** de lógica que vive no `modulo2/utils.py`. A cópia é o padrão desta casa (está no `CLAUDE.md` do Módulo 2), e o preço dela é poder divergir.

Duas cópias da mesma regra é risco **medido neste código** — a docstring de `nome_pasta_edital()` no Módulo 2 registra o acidente:

> *«era repetida em `analisador.caminho_saida_edital()` e em `analisador._chave_pasta()`, e a segunda cópia ficou para trás na Etapa 2A (montava a convenção ANTIGA, sem o código)»*

**Quem paga esse preço é `testes/teste_equivalencia_modulo2.py`**: ele roda esta implementação e a do Módulo 2 sobre as MESMAS linhas da Agenda e exige resultado **idêntico**.

> **MEXEU EM `convencao_edital.py` OU EM `agenda.py`? RODE AQUELA SUÍTE.**
> É o único mecanismo que impede a cópia de envelhecer em silêncio.

---

## 6. Como rodar

```
cd C:\licitacoes\inventariador
python -B inventariador.py
```

As suítes (sempre com `python -B`, para nenhum `.pyc` nascer nos repositórios que elas importam):

```
python -B testes\teste_inventario.py                     # sintética, em área temporária
python -B testes\teste_determinismo_fuso.py              # fusos, migração de schema, a guarda
python -B testes\teste_nome_de_membro_e_anomalia.py      # o nome do membro e o campo `anomalia`
python -B testes\teste_equivalencia_modulo2.py           # a cópia contra o Módulo 2
python -B testes\teste_integracao_maestro.py             # os dois handoffs e a ordem da cadeia
```

Nenhuma delas toca em `C:\Editais 2026`.

**Rodar em SÉRIE, nunca em paralelo.** As suítes do Maestro medem relógio e dão
falso vermelho sob disputa de CPU.

### A segunda regra que não se negocia — o determinismo

**`modificado_em` NÃO pode depender da máquina.** O inventário tem de sair byte a byte igual em qualquer fuso, e o campo entra na comparação: nunca o mascare, nunca o substitua por constante, nunca o normalize depois de gerar para esconder diferença. Foi exatamente isso que bloqueou a homologação da D1.

> **MEXEU EM `modificado_em`, NO `schema_version` OU NO `comparar()`? RODE `teste_determinismo_fuso.py`.**

### A terceira regra que não se negocia — declarar, nunca adivinhar calado

**Nome que o container não declarou NÃO é reescrito em silêncio.** O `.zip` guarda o nome do membro em bytes, e o bit `0x800` do índice diz se eles estão em UTF-8. Quando o bit está desligado não há declaração nenhuma, e pode haver **duas leituras possíveis** dos mesmos bytes.

A regra está em `inventario._ler_nome_de_membro()`, e tem três partes que não se negociam:

1. **o filtro de plausibilidade é ENUMERADO no código** (`FAIXAS_IMPLAUSIVEIS_EM_NOME`), nunca julgado caso a caso. Acrescentar faixa exige medição escrita ao lado;
2. **escolher só quando houver UM único candidato tecnicamente possível.** UTF-8 válido **não** é UTF-8 comprovado — a leitura cp437 existe sempre, então bytes que também formem UTF-8 válido têm duas leituras, e adotar uma delas seria inventar certeza;
3. **toda troca de leitura é DECLARADA, com as duas leituras visíveis.** Um nome corrigido sem aviso é tão silencioso quanto o errado: muda só de lado.

Na ambiguidade o `caminho` fica na leitura cp437 — escolha de **ESTABILIDADE, não de verdade**, porque `caminho` entra na identidade do diff.

> **MEXEU EM `_ler_nome_de_membro()`, NAS FAIXAS OU NO CAMPO `anomalia`? RODE `teste_nome_de_membro_e_anomalia.py`.**
> A suíte do Python **não reproduz este defeito sozinha** — o `zipfile` sempre liga o bit `0x800`. Aquela suíte constrói o `.zip` **no nível do byte**, e é o único lugar onde o defeito existe para ser pego.

### `anomalia` significa «NÃO É ROTINA»

Verdadeira para **`AUSENTE`** e para **`AMBIGUA`**; falsa para `VAZIA` e `COM_ARQUIVO`. A fonte única é `inventario.ESTADOS_DE_ANOMALIA` — o campo por edital e o total do `resumir()` leem os dois de lá, e é isso que faz o total **fechar** com a contagem por estado por construção.

---

## 7. Regra de retomada de sessão

**Ao retomar uma sessão, a leitura obrigatória é, nesta ordem, antes de qualquer alteração:**

1. `CLAUDE.md` (este arquivo)
2. `ESTADO_ATUAL.md`

O `ESTADO_ATUAL.md` é o único lugar onde vive o estado técnico corrente e o **ledger de decisões desta frente**. Ele é atualizado **por medição do working tree**, nunca por memória nem por cópia de documento antigo.

**A numeração `D` desta frente é PRÓPRIA.** Ela começa em `D1` e não tem relação nenhuma com os `D` do Módulo 2 ou do Módulo 3 — decisões daquelas frentes ficam onde estão, e não são renumeradas, copiadas nem referenciadas como se fossem daqui.

Este `CLAUDE.md` é deliberadamente **estável**: não carrega contagem de arquivos, hashes, branch, HEAD nem resultado de teste. Esses dados pertencem ao `ESTADO_ATUAL.md`.
