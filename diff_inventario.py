# -*- coding: utf-8 -*-
r"""
REINVENTÁRIO E DIFF — «o conjunto de arquivos mudou?». E SÓ ISSO.

O QUE O DIFF NUNCA RESPONDE
    NUNCA «o que falta o Módulo 3 processar?».

    Se o diff virar fonte do que está pendente, passam a existir DUAS VERDADES
    sobre a fila: a do dono da fila e a deste arquivo. É exatamente o que o
    `controle.py` do Módulo 2 já ensinou a não fazer — «o histórico do M1 diz
    "já baixei", não "o M2 já analisou" … dois fatos diferentes, de dois donos
    diferentes, em dois arquivos diferentes».

    O Inventariador não é dono de fila nenhuma. Um arquivo INALTERADO não quer
    dizer "já processado", e um ADICIONADO não quer dizer "processe agora".

AS TRÊS DECISÕES QUE O §4.8 MANDA DECLARAR ANTES DE IMPLEMENTAR

    1. DE ONDE VEM O INVENTÁRIO ANTERIOR
       De um arquivo JSON no formato deste contrato, indicado por caminho.
       Quem o preserva é a pasta de saída do PRÓPRIO Inventariador
       (`PASTA_SAIDA`, fora dos repositórios existentes): cada execução grava
       `inventario_AAAAMMDD_HHMMSS.json` e reescreve `inventario_atual.json`
       apontando para o retrato mais novo. O anterior é o `inventario_atual.json`
       que estava lá ANTES da execução — copiado para
       `inventario_anterior.json` no começo dela.

       Não existindo anterior (primeira execução), NÃO se inventa um vazio para
       ter o que comparar: o diff sai com `sem_base_de_comparacao = True` e
       nenhuma linha de ADICIONADO. Uma base fabricada faria a primeira execução
       declarar 200 mil arquivos "adicionados", que é ruído, não informação.

    2. QUAL IDENTIDADE COMPARA DOIS ARQUIVOS
       A TRIPLA  (codigo_edital, container, caminho).

       NÃO é o nome sozinho, e a medição desta rodada explica por quê: a base
       real tem 13 pastas com mais de um `.zip`, e o mesmo nome de membro
       (`edital_1.zip`, `anexo_1.xlsx`) aparece dentro de containers diferentes
       do MESMO edital. Comparar por nome faria dois arquivos distintos
       passarem por um só, e a diferença entre eles sumiria do diff.

       `container` é None para arquivo solto e o nome do `.zip` para membro —
       o que distingue `edital.pdf` solto de `edital.pdf` dentro do container.

       O TAMANHO E A DATA NÃO ENTRAM NA IDENTIDADE, de propósito: se
       entrassem, um arquivo que mudou apareceria como um REMOVIDO mais um
       ADICIONADO, e `ALTERADO` nunca aconteceria.

    3. O QUE `ALTERADO` SIGNIFICA
       Mesma identidade, e `tamanho_bytes` OU `modificado_em` diferente.

       NÃO é "o conteúdo mudou": sem SHA-256 — e o §4.4 proíbe calculá-lo — não
       há como afirmar isso. `ALTERADO` afirma o que foi medido: os metadados
       que o sistema de arquivos e o índice do ZIP entregam mudaram. Um arquivo
       reescrito com o mesmo tamanho e a mesma data sai como INALTERADO, e isso
       está declarado aqui em vez de ficar subentendido.
"""

from __future__ import annotations

ADICIONADO = "ADICIONADO"
REMOVIDO = "REMOVIDO"
ALTERADO = "ALTERADO"
INALTERADO = "INALTERADO"

# Os campos cuja diferença faz um arquivo ser ALTERADO. Estão numa constante
# para o contrato ser lido, e não deduzido do corpo de uma função.
CAMPOS_COMPARADOS = ("tamanho_bytes", "modificado_em")


def identidade(codigo_edital: str, arquivo: dict) -> tuple:
    """A tripla que identifica um arquivo entre dois inventários. Ver §4.8 acima."""
    return (codigo_edital, arquivo.get("container"), arquivo["caminho"])


def _indexar(inventario: dict) -> dict:
    """{identidade: arquivo} para um inventário inteiro."""
    indice = {}
    for registro in inventario.get("editais", []):
        codigo = registro["codigo_edital"]
        for arquivo in registro.get("arquivos", []):
            indice[identidade(codigo, arquivo)] = arquivo
    return indice


def _estados_por_edital(inventario: dict) -> dict:
    return {r["codigo_edital"]: r["estado_pasta"] for r in inventario.get("editais", [])}


MOTIVO_SEM_ANTERIOR = (
    "não há inventário anterior — esta é a primeira execução, ou o anterior foi "
    "removido. Nada é declarado ADICIONADO: uma base vazia fabricada faria todo "
    "arquivo existente parecer novidade."
)

MOTIVO_SCHEMA_MUDOU = (
    "sem base comparável por mudança de schema — o inventário anterior foi gravado "
    "noutra versão do contrato, e campos comparados podem ter mudado de significado. "
    "Comparar assim mesmo produziria ALTERADO em massa por efeito da própria "
    "mudança, e não de mudança em arquivo nenhum."
)


def _sem_base(inventario_anterior: dict | None, inventario_atual: dict, motivo: str) -> dict:
    """
    O diff DECLARADO VAZIO — o mesmo caminho para os dois casos em que não há
    base comparável: não existe anterior, ou o anterior é de outro schema.

    Um só caminho de propósito: quem consome o diff precisa de UMA condição para
    testar (`sem_base_de_comparacao`), e não de duas formas diferentes de dizer
    a mesma coisa. O `motivo` diz qual dos dois casos foi.
    """
    return {
        "schema_version_anterior": (inventario_anterior or {}).get("schema_version"),
        "schema_version_atual": inventario_atual.get("schema_version"),
        "sem_base_de_comparacao": True,
        "motivo": motivo,
        "totais": {ADICIONADO: 0, REMOVIDO: 0, ALTERADO: 0, INALTERADO: 0},
        "arquivos": [],
        "editais_que_mudaram_de_estado": [],
        "nao_e_fila": ("este diff responde 'o conjunto de arquivos mudou?'. "
                       "NUNCA 'o que falta processar?'."),
    }


def comparar(inventario_anterior: dict | None, inventario_atual: dict) -> dict:
    """
    Compara dois inventários e declara ADICIONADO · REMOVIDO · ALTERADO ·
    INALTERADO, por arquivo.

    A ordem da saída é determinística (ordenada pela identidade), pelo mesmo
    motivo do inventário: dois diffs da mesma dupla de inventários têm de sair
    iguais byte a byte.

    DUAS SITUAÇÕES EM QUE ELE NÃO COMPARA, E DECLARA

    1. NÃO HÁ INVENTÁRIO ANTERIOR. Diff vazio e declarado — não se fabrica base.

    2. O ANTERIOR É DE OUTRO `schema_version`. **Também não compara**, e pelo
       mesmo caminho.

       A razão não é estética. Quando `modificado_em` de arquivo solto mudou de
       hora local para instante UTC, o valor passou a ser diferente para TODA
       entrada solta — 2.414 delas na base real — sem que arquivo nenhum tivesse
       mudado. Comparar assim mesmo despejaria milhares de ALTERADO com
       `campos_diferentes: ["modificado_em"]`, por efeito da própria correção.

       **Um alarme falso do tamanho da base ensina a equipe a ignorar o diff.**
       Um sinal que grita todo dia morre, e depois disso a alteração de verdade
       passa despercebida. Falha barulhenta é segura uma vez; barulho constante
       vira falha silenciosa.

       O preço é uma execução sem diff, na primeira vez depois de cada mudança de
       schema. É barato, e é honesto: dizer "não sei comparar" é melhor que
       inventar 2.414 alterações que não aconteceram.
    """
    if inventario_anterior is None:
        return _sem_base(None, inventario_atual, MOTIVO_SEM_ANTERIOR)

    if inventario_anterior.get("schema_version") != inventario_atual.get("schema_version"):
        return _sem_base(inventario_anterior, inventario_atual, MOTIVO_SCHEMA_MUDOU)

    antes = _indexar(inventario_anterior)
    agora = _indexar(inventario_atual)

    linhas = []
    for chave in sorted(set(antes) | set(agora), key=lambda c: (c[0], c[1] or "", c[2])):
        codigo, container, caminho = chave
        a, b = antes.get(chave), agora.get(chave)
        if a is None:
            situacao, mudou = ADICIONADO, []
        elif b is None:
            situacao, mudou = REMOVIDO, []
        else:
            mudou = [campo for campo in CAMPOS_COMPARADOS if a.get(campo) != b.get(campo)]
            situacao = ALTERADO if mudou else INALTERADO

        linha = {
            "situacao": situacao,
            "codigo_edital": codigo,
            "container": container,
            "caminho": caminho,
            "campos_diferentes": mudou,
        }
        for campo in CAMPOS_COMPARADOS:
            linha[f"{campo}_antes"] = a.get(campo) if a else None
            linha[f"{campo}_agora"] = b.get(campo) if b else None
        linhas.append(linha)

    estados_antes = _estados_por_edital(inventario_anterior)
    estados_agora = _estados_por_edital(inventario_atual)
    mudancas_de_estado = [
        {"codigo_edital": codigo,
         "estado_antes": estados_antes.get(codigo),
         "estado_agora": estados_agora.get(codigo)}
        for codigo in sorted(set(estados_antes) | set(estados_agora))
        if estados_antes.get(codigo) != estados_agora.get(codigo)
    ]

    totais = {situacao: 0 for situacao in (ADICIONADO, REMOVIDO, ALTERADO, INALTERADO)}
    for linha in linhas:
        totais[linha["situacao"]] += 1

    return {
        "schema_version_anterior": inventario_anterior.get("schema_version"),
        "schema_version_atual": inventario_atual.get("schema_version"),
        "sem_base_de_comparacao": False,
        "identidade_comparada": "(codigo_edital, container, caminho)",
        "alterado_significa": ("mesma identidade, com tamanho_bytes ou modificado_em "
                               "diferente. NÃO afirma que o conteúdo mudou — sem "
                               "SHA-256 não há como afirmar isso."),
        "totais": totais,
        "arquivos": linhas,
        "editais_que_mudaram_de_estado": mudancas_de_estado,
        "nao_e_fila": ("este diff responde 'o conjunto de arquivos mudou?'. "
                       "NUNCA 'o que falta processar?'."),
    }
