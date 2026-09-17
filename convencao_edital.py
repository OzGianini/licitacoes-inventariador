# -*- coding: utf-8 -*-
r"""
A CONVENÇÃO DE PASTA DO EDITAL — cópia deliberada da lógica provada do Módulo 2.

DE ONDE VEIO, E POR QUE COPIADA
    Todo o conteúdo funcional deste arquivo é cópia de `C:\licitacoes\modulo2\utils.py`,
    que roda em produção três vezes por dia e já resolve, no formato vigente, o
    problema que o Inventariador precisa resolver: dada uma linha da Agenda,
    QUAL pasta em disco é a desta linha, e em que estado ela está.

    A cópia é o padrão desta casa, e está escrito no CLAUDE.md do Módulo 2:
    «onde precisa da mesma lógica (ex: convenção de nome de pasta), a lógica é
    REPLICADA de forma enxuta, com comentário explícito de que precisa continuar
    em sincronia». Import cruzado amarraria o Inventariador ao `config.py` do
    Módulo 2 e, por tabela, ao `openpyxl`/`pypdf`/`gspread` daquele repositório.

    O Módulo 2 NÃO foi alterado. Ele continua usando o `utils.py` dele.

O PREÇO DA CÓPIA, E O QUE PAGA ESSE PREÇO
    Duas cópias da mesma regra é risco medido NESTE código. A docstring de
    `nome_pasta_edital()` no Módulo 2 registra o acidente:

        «era repetida em analisador.caminho_saida_edital() e em
         analisador._chave_pasta(), e a segunda cópia ficou para trás na
         Etapa 2A (montava a convenção ANTIGA, sem o código)»

    Quem paga o preço aqui é `testes/teste_equivalencia_modulo2.py`: ele roda
    ESTA implementação e a do Módulo 2 sobre as MESMAS linhas da Agenda e exige
    resultado IDÊNTICO. Divergindo, a suíte fica vermelha antes de a divergência
    poder morder.

    ALTERAR ESTE ARQUIVO SEM RODAR AQUELA SUÍTE É O DEFEITO QUE ELA EXISTE PARA
    IMPEDIR.

O QUE MUDOU EM RELAÇÃO AO ORIGINAL, E POR QUÊ
    1. A raiz dos editais entra por PARÂMETRO (`raiz_editais`), em vez de vir de
       `config.PASTA_EDITAIS`. É o que permite a suíte sintética rodar as duas
       implementações lado a lado sobre a MESMA árvore temporária, sem tocar na
       base real.
    2. Os nomes dos estados são os do contrato do Inventariador
       (AUSENTE/VAZIA/COM_ARQUIVO). A correspondência com os nomes do Módulo 2
       (PASTA_AUSENTE/PASTA_VAZIA/COM_ARQUIVO) está em ESTADOS_EQUIVALENTES, e a
       suíte de equivalência compara PELO MAPA, nunca pelo texto.
    3. `candidatas_pasta_edital()` é NOVA — não existe no Módulo 2. Ela devolve
       TODAS as pastas que casam com o código, para o Inventariador poder
       declarar ambiguidade em vez de escolher (§4.6 do enunciado). O Módulo 2
       escolhe a primeira em ordem, e continua escolhendo: esta função não muda
       o comportamento de `localizar_pasta_edital()`, que segue idêntico ao dele.

O QUE NÃO FOI COPIADO, E POR QUÊ
    `listar_arquivos_edital()` do Módulo 2 NÃO foi copiada. Ela abre apenas o
    PRIMEIRO .zip da pasta (`zips[0]`) e exclui de propósito `resumo_edital.*` —
    duas decisões certas para o Módulo 2 e erradas para o Inventariador, que
    lista tudo e marca a origem (§4.5). A medição desta rodada encontrou 13
    pastas com mais de um .zip na base real: usar a função do Módulo 2 aqui
    esconderia o conteúdo dos demais containers.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

# ─── Estados da pasta do edital, verificados EM DISCO ──────────────────────
#
# Cópia da regra do Módulo 2, com os nomes do contrato do Inventariador:
#
#   AUSENTE      a pasta não existe            -> ANOMALIA (o M1 cria SEMPRE)
#   VAZIA        existe, sem .zip/.pdf         -> rotina (arquivo não veio)
#   COM_ARQUIVO  existe, com .zip ou .pdf      -> tem arquivo do edital
#   AMBIGUA      duas ou mais pastas candidatas para a MESMA identidade
#
# AMBIGUA não existe no Módulo 2 e é exclusiva do Inventariador: é o fail-closed
# do §4.6 — ausência declarada é melhor que associação errada.
ESTADO_AUSENTE = "AUSENTE"
ESTADO_VAZIA = "VAZIA"
ESTADO_COM_ARQUIVO = "COM_ARQUIVO"
ESTADO_AMBIGUA = "AMBIGUA"

# O mapa que a suíte de equivalência usa para comparar os dois vocabulários.
# AMBIGUA não aparece aqui de propósito: não tem correspondente no Módulo 2.
ESTADOS_EQUIVALENTES = {
    ESTADO_AUSENTE: "PASTA_AUSENTE",
    ESTADO_VAZIA: "PASTA_VAZIA",
    ESTADO_COM_ARQUIVO: "COM_ARQUIVO",
}

# Extensões que contam como "arquivo do edital" — cópia de
# utils.EXTENSOES_ARQUIVO_EDITAL. Note que é uma lista CURTA de propósito: ela
# decide o ESTADO da pasta, não o que entra no inventário. O inventário lista
# tudo (§4.5); só o estado usa esta regra, para continuar idêntico ao do M2.
EXTENSOES_ARQUIVO_EDITAL = (".zip", ".pdf")

# Prefixo dos artefatos que o Módulo 1 gera a partir do card do portal — não são
# o documento publicado pela prefeitura. O Módulo 2 os EXCLUI; o Inventariador os
# INCLUI e MARCA (§4.5). Aqui o prefixo serve só para a regra de estado.
PREFIXO_ARTEFATO_M1 = "resumo_edital"


def texto_codigo(valor) -> str:
    """
    Código ConLicitação como texto ('19241283'), venha ele como string (o
    normal — é assim que o Módulo 1 grava) ou como número, caso o Excel tenha
    convertido a célula em algum momento.

    Cópia de utils._texto_codigo().
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def remover_acentos(texto: str) -> str:
    """Cópia de utils.remover_acentos()."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def formatar_num_edital(num: str) -> str:
    """'DL/17/2026' -> 'DL 17-2026'. Cópia de utils.formatar_num_edital()."""
    num = num.strip()
    partes = num.split("/", 1)
    if len(partes) == 2:
        return partes[0] + " " + partes[1].replace("/", "-")
    return num.replace("/", "-")


def formatar_codigo_edital(id_con: str) -> str:
    """
    '19241283' -> 'CONLIC-19241283'. Cópia de utils.formatar_codigo_edital().

    Esta função é a IDENTIDADE do edital para o Inventariador. Ela não cria
    código nenhum: reescreve o que já existe na Agenda no formato que o Módulo 1
    já usa no nome da pasta. Não há ID paralelo, UUID nem segundo código.
    """
    codigo = (id_con or "").strip()
    if not codigo:
        return "CONLIC-SEM-CODIGO"
    return f"CONLIC-{codigo}"


def nome_pasta_cidade(cidade: str, uf: str) -> str:
    """Cópia de utils.nome_pasta_cidade()."""
    cidade_limpa = remover_acentos(cidade.strip()).upper() if cidade else "SEM-CIDADE"
    uf_limpo = uf.strip().upper() if uf else "XX"
    return f"{cidade_limpa} - {uf_limpo}"


def nome_pasta_edital(linha_agenda: dict) -> str:
    """
    Nome da pasta do edital (segundo nível): "{Nº formatado} - {CÓDIGO}".
    Ex: "PE 35-2026 - CONLIC-19241283".

    Cópia de utils.nome_pasta_edital() — a função cuja própria docstring registra
    que uma segunda cópia desta composição já ficou para trás uma vez.
    """
    return (
        f"{formatar_num_edital(linha_agenda['numero_pregao'])} - "
        f"{formatar_codigo_edital(linha_agenda.get('codigo_conlicitacao', ''))}"
    )


def chave_pasta_edital(linha_agenda: dict) -> str:
    """
    "CIDADE - UF/Nº EDITAL - CONLIC-código" — o caminho relativo da pasta do
    edital dentro da raiz, com "/" como separador.

    Cópia de utils.chave_pasta_edital().
    """
    return (
        f"{nome_pasta_cidade(linha_agenda['cidade'], linha_agenda['uf'])}/"
        f"{nome_pasta_edital(linha_agenda)}"
    )


def sufixo_identidade(linha_agenda: dict) -> str:
    """
    O sufixo " - CONLIC-xxxxx" pelo qual a pasta é reconhecida.

    Extraído para função própria porque `localizar_pasta_edital()` e
    `candidatas_pasta_edital()` precisam do MESMO sufixo — e a segunda é nova
    aqui. Duas montagens do sufixo seriam a mesma armadilha da Etapa 2A, dentro
    deste arquivo.
    """
    return f" - {formatar_codigo_edital(linha_agenda.get('codigo_conlicitacao', ''))}"


def candidatas_pasta_edital(linha_agenda: dict, raiz_editais: Path) -> list[Path]:
    """
    TODAS as pastas cujo nome termina no código desta linha, em ordem.

    NÃO existe no Módulo 2 — é o insumo do fail-closed do §4.6. Com mais de uma
    candidata, o Inventariador declara ambiguidade e NÃO escolhe.

    Duas pastas podem terminar no mesmo código dentro da mesma cidade quando o
    número do pregão difere: "PE 35-2026 - CONLIC-X" e "PE 36-2026 - CONLIC-X".
    O código é a chave única do EDITAL, não do nome da pasta.
    """
    pasta_cidade = Path(raiz_editais) / nome_pasta_cidade(
        linha_agenda["cidade"], linha_agenda["uf"]
    )
    if not pasta_cidade.is_dir():
        return []

    sufixo = sufixo_identidade(linha_agenda)
    try:
        return [c for c in sorted(pasta_cidade.iterdir())
                if c.name.endswith(sufixo) and c.is_dir()]
    except OSError:
        return []


def localizar_pasta_edital(linha_agenda: dict, raiz_editais: Path) -> Path | None:
    """
    A pasta do edital, achada pelo SUFIXO " - CONLIC-xxxxx".

    Cópia de utils.localizar_pasta_edital(), COM O MESMO fail-closed de
    identidade da docstring original:

        «uma pasta cujo nome não termine no código desta linha NÃO é aceita como
         sendo deste edital, mesmo que cidade e número batam»

    A busca é pelo SUFIXO (e não pelo nome inteiro) porque o número do pregão
    registrado na Agenda pode ser corrigido depois que a pasta foi criada; o
    código, não.

    Devolve a PRIMEIRA em ordem quando há mais de uma — exatamente como o Módulo
    2 faz, para a equivalência valer. Quem não escolhe diante de ambiguidade é o
    inventário, por `candidatas_pasta_edital()`; esta função é a cópia fiel.
    """
    candidatas = candidatas_pasta_edital(linha_agenda, raiz_editais)
    return candidatas[0] if candidatas else None


def pasta_tem_arquivo_edital(pasta_edital: Path) -> bool:
    """
    True se a pasta contém pelo menos um arquivo DO EDITAL — .zip ou .pdf solto
    na pasta, excluído `resumo_edital.*`.

    Cópia de utils.pasta_tem_arquivo_edital(). Olha SÓ O PRIMEIRO NÍVEL, que é
    onde o Módulo 1 grava o que baixa: um arquivo enterrado em subpasta criada à
    mão não conta, e o edital segue aparecendo como sem arquivo — comportamento
    seguro, e o mesmo dos dois lados.
    """
    try:
        for item in pasta_edital.iterdir():
            if not item.is_file():
                continue
            if item.name.startswith(PREFIXO_ARTEFATO_M1):
                continue
            if item.suffix.lower() in EXTENSOES_ARQUIVO_EDITAL:
                return True
    except OSError:
        return False
    return False


def estado_pasta_edital(linha_agenda: dict, raiz_editais: Path) -> tuple[str, Path | None]:
    """
    Estado da pasta do edital em disco, no vocabulário do Inventariador, junto
    com o Path da pasta (None quando ausente ou ambígua).

    Cópia de utils.estado_pasta_edital(), com UMA adição declarada: o estado
    AMBIGUA, quando `candidatas_pasta_edital()` devolve mais de uma. O Módulo 2
    nunca devolve AMBIGUA — ele escolhe a primeira. A suíte de equivalência
    compara os dois SÓ nos casos não ambíguos e cobra, à parte, que o
    Inventariador tenha declarado a ambiguidade nos demais.
    """
    candidatas = candidatas_pasta_edital(linha_agenda, raiz_editais)
    if not candidatas:
        return ESTADO_AUSENTE, None
    if len(candidatas) > 1:
        return ESTADO_AMBIGUA, None
    pasta = candidatas[0]
    if pasta_tem_arquivo_edital(pasta):
        return ESTADO_COM_ARQUIVO, pasta
    return ESTADO_VAZIA, pasta


def eh_artefato_do_modulo1(nome_arquivo: str) -> bool:
    """
    `resumo_edital.json` / `resumo_edital.docx` são gerados pelo Módulo 1 a
    partir do card do portal — não são o documento publicado pela prefeitura.

    O Módulo 2 os EXCLUI da lista; o Inventariador os INCLUI e os MARCA (§4.5).
    Quem filtra é o consumidor.
    """
    return Path(nome_arquivo).name.startswith(PREFIXO_ARTEFATO_M1)
