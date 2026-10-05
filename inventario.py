# -*- coding: utf-8 -*-
r"""
O INVENTÁRIO — dado um edital que a cadeia já conhece, quais arquivos existem
AGORA para ele. Nem mais, nem menos.

O QUE ESTE ARQUIVO NÃO FAZ
    Não classifica licitação, não executa o Módulo 3, não abre PDF para extrair,
    não escolhe "o PDF principal", não publica na Agenda, não controla fila do
    que já foi processado, e não altera, move, renomeia, converte ou extrai
    arquivo nenhum. Não corrige a saída do Módulo 1.

    NÃO GUARDA FILA, e a razão é da própria casa — `modulo2/controle.py`:

        «o histórico do M1 diz "já baixei", não "o M2 já analisou". … São dois
         fatos diferentes, de dois donos diferentes, e ficam em dois arquivos
         diferentes.»

    «Que arquivos existem agora» e «o que já foi processado» são dois fatos de
    dois donos. Este arquivo é dono só do primeiro.

SOMENTE LEITURA, SEMPRE
    Nada em `PASTA_EDITAIS` é escrito, renomeado, movido ou excluído. Os `.zip`
    são abertos apenas pelo ÍNDICE (`zipfile.infolist()`), que entrega caminho,
    tamanho e data de modificação sem descomprimir e sem ler o conteúdo — tão
    barato quanto listar um diretório. Nunca há `.read()` de membro, nunca há
    `.extractall()`.

ORDEM DETERMINÍSTICA
    Mesma entrada lógica e mesmo conjunto de arquivos produzem o mesmo
    inventário, byte a byte. Nada aqui depende da ordem em que o sistema de
    arquivos devolve nomes, nem do horário da execução, nem de quem rodou:
    o corpo do inventário NÃO carrega relógio, caminho absoluto, nome de máquina
    nem de usuário. Esses dados vivem no relatório de execução, ao lado.

    `modificado_em` de arquivo solto é INSTANTE UTC desde a correção de
    determinismo — ver `_data_do_sistema_de_arquivos()`. A versão anterior
    gravava hora local da máquina, e a mesma árvore intocada produzia bytes
    diferentes em fusos diferentes. Não há mais limite declarado aqui: o
    contrato vale inteiro, em qualquer máquina.
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import convencao_edital as convencao

# ─── A versão do contrato de saída ─────────────────────────────────────────
#
# Existe para o contrato poder evoluir sem que o antigo seja lido como se fosse
# o novo. Quem consumir um inventário DEVE conferir este campo antes de
# interpretar qualquer outro.
#
#   MAIOR  muda quando um campo existente muda de significado, de tipo ou some
#   MENOR  muda quando um campo novo é acrescentado, sem mexer nos que existem
#   PATCH  muda quando só a descrição/ordenação interna muda
#
# 1.0.0 -> 2.0.0 (correção de determinismo)
#     `modificado_em` de arquivo SOLTO passou de hora local sem marca para
#     INSTANTE UTC, com o sufixo "Z". Mudou o significado E o texto de um campo
#     que já existia — é MAIOR pela regra acima, e não havia escolha: um
#     inventário antigo lido como se fosse novo compararia hora local do Brasil
#     com UTC e acusaria alteração em toda entrada solta.
#
#     `diff_inventario.comparar()` RECUSA comparar versões diferentes. Ver lá.
#
# 2.0.0 -> 3.0.0 (fechamento: nome de membro de container e abrangência de `anomalia`)
#     UMA subida cobrindo as DUAS correções desta rodada, porque as duas mexem
#     em campo publicado e uma execução sem diff basta para as duas juntas:
#
#     · `caminho` de membro de container pode mudar de valor, quando o índice do
#       `.zip` não declarou a codificação do nome e a leitura cp437 do `zipfile`
#       era demonstravelmente a errada. `caminho` entra na identidade do diff
#       (`diff_inventario.identidade()`), então um valor novo aparece como
#       REMOVIDO + ADICIONADO na primeira comparação — é MAIOR pela regra acima.
#
#     · `anomalia` mudou de SIGNIFICADO: era «a pasta não existe» e passou a ser
#       «não é rotina», cobrindo `AUSENTE` e `AMBIGUA`. Um consumidor que filtre
#       por esse campo passa a receber um conjunto diferente. Também MAIOR.
#
#     · e o total `editais_com_anomalia_pasta_ausente` foi RENOMEADO para
#       `editais_com_anomalia` — campo que some do corpo publicado é MAIOR.
#
#     Duas subidas custariam DUAS execuções sem diff, e uma basta. A guarda da
#     D2 (`comparar()` recusa schemas diferentes) trata a migração sozinha, sem
#     nada de novo aqui: esta rodada PROVA que ela continua valendo, não a
#     reimplementa.
SCHEMA_VERSION = "3.0.0"

# ─── Onde o arquivo estava ─────────────────────────────────────────────────
ONDE_SOLTO = "SOLTO_NA_PASTA"
ONDE_NO_CONTAINER = "DENTRO_DO_CONTAINER"

# ─── Achados: o que a amostra do enunciado não tinha ───────────────────────
#
# O §1.4 do enunciado descrevia, a partir de DOIS editais, uma base sem
# subpasta, sem zip aninhado e só com PDF dentro do .zip. A medição desta rodada
# sobre a base inteira desmentiu as três coisas. Achado não é erro: é fato
# medido que precisa aparecer, e sobre o qual o Inventariador NÃO inventa regra.
ACHADO_SUBPASTA_NA_PASTA = "SUBPASTA_NA_PASTA_DO_EDITAL"
ACHADO_SUBPASTA_NO_CONTAINER = "SUBPASTA_DENTRO_DO_CONTAINER"
ACHADO_CONTAINER_ANINHADO = "CONTAINER_ANINHADO"
ACHADO_CONTAINER_ILEGIVEL = "CONTAINER_NAO_INVENTARIAVEL"
ACHADO_MAIS_DE_UM_CONTAINER = "MAIS_DE_UM_CONTAINER_NA_PASTA"
ACHADO_AMBIGUIDADE = "AMBIGUIDADE_DE_IDENTIDADE"
ACHADO_PASTA_ILEGIVEL = "PASTA_NAO_LISTAVEL"

# O índice do container não declarou a codificação do nome do membro, e havia
# UMA só leitura tecnicamente possível — ela foi adotada, e a descartada vai
# escrita no achado. Ver `_ler_nome_de_membro()`.
ACHADO_ENCODING_NAO_DECLARADO = "ENCODING_NOME_NAO_DECLARADO"
# ... e havia DUAS leituras possíveis, ou NENHUMA plausível. O `caminho` fica na
# leitura cp437 por ESTABILIDADE — e o achado NÃO afirma qual é o nome verdadeiro.
ACHADO_ENCODING_AMBIGUO = "ENCODING_NOME_AMBIGUO"

# Extensões que são container e que o Inventariador NÃO abre por não ter regra
# escrita para elas. Entram no inventário como arquivo, com um achado ao lado.
EXTENSOES_CONTAINER_NAO_ABERTO = (".rar", ".7z", ".gz", ".tar", ".tgz")

# ─── A ORIGEM DE CADA ARQUIVO: o manifesto do Módulo 1 (05/10/2026, A3) ────
#
# A pasta do edital é compartilhada com a equipe, que põe lá habilitação,
# certidões, catálogos e a proposta. Desde 05/10 o Módulo 1 grava, na pasta de
# cada edital, o manifesto do que ELE baixou (nome, SHA-256, tamanho e data; e
# os membros, quando o download é um .zip). Cada arquivo do inventário ganha o
# campo `origem`, e o Módulo 3 só manda à porta o que não for da equipe.
#
#   BAIXADO_PELO_M1      está no manifesto (solto: mesmo nome E mesmo tamanho;
#                        dentro de container: o container está no manifesto)
#   ARTEFATO_DO_M1       o manifesto em si e o resumo_edital* que o M1 gera
#   ARQUIVO_DA_EQUIPE    a pasta TEM manifesto e o arquivo não está nele
#   SEM_MANIFESTO_DO_M1  a pasta não tem manifesto (edital anterior a 05/10, ou
#                        manifesto ilegível): comportamento de antes, declarado
#
# NADA é deduzido pelo nome do arquivo, e nada é apagado, movido ou renomeado:
# o Inventariador continua só lendo. O SHA-256 não é recalculado aqui — o
# contrato do §4.4 continua valendo — e por isso o arquivo solto é casado por
# NOME e TAMANHO.
#
# O `schema_version` continua 3.0.0: o campo é ADITIVO, o `diff_inventario`
# compara só tamanho e data, e o Módulo 3 exige o MAIOR 3. DECIDI na rodada de
# 05/10 não subir o número para não declarar «sem base comparável» uma execução
# que é comparável.
NOME_MANIFESTO_M1 = "manifesto_m1.json"   # o mesmo nome do agente_captura.py do M1
ORIGEM_BAIXADO_PELO_M1 = "BAIXADO_PELO_M1"
ORIGEM_ARTEFATO_DO_M1 = "ARTEFATO_DO_M1"
ORIGEM_ARQUIVO_DA_EQUIPE = "ARQUIVO_DA_EQUIPE"
ORIGEM_SEM_MANIFESTO = "SEM_MANIFESTO_DO_M1"
DESCRICAO_DA_ORIGEM = {
    ORIGEM_BAIXADO_PELO_M1: "baixado pelo M1 — documento do edital",
    ORIGEM_ARTEFATO_DO_M1: "gerado pelo M1 (manifesto ou resumo) — não é documento do edital",
    ORIGEM_ARQUIVO_DA_EQUIPE: "arquivo da equipe — fora do M3",
    ORIGEM_SEM_MANIFESTO: "sem manifesto do M1 — origem não declarada; segue o comportamento antigo",
}
ACHADO_MANIFESTO_ILEGIVEL = "MANIFESTO_DO_M1_ILEGIVEL"


# ─── Quais estados são ANOMALIA — a fonte única do §4.2 ─────────────────────
#
# `anomalia` significa **«não é rotina»**, e não «a pasta não existe».
#
# A VERSÃO ANTERIOR ERRAVA, E A ORIGEM DO ERRO ESTÁ DECLARADA
#     O campo nasceu na D1 escrito como `estado == ESTADO_AUSENTE`, porque o
#     enunciado da D1 definiu a palavra «anomalia» em cima da dupla
#     `VAZIA`/`AUSENTE`, no §4.7, e não voltou para incluir o `AMBIGUA`, que
#     entrou pelo §4.6. A implementação obedeceu ao que estava escrito — e o
#     resultado foi o estado MAIS GRAVE dos quatro saindo marcado como rotina.
#
# POR QUE `AMBIGUA` É ANOMALIA, E A MAIS PESADA DELAS
#     `AUSENTE` diz «a pasta sumiu». `AMBIGUA` diz «NÃO SE SABE qual pasta é a
#     deste edital» — duas candidatas, e o fail-closed da D1 recusa escolher.
#     Não saber qual é a pasta é pior que saber que ela não está lá.
#
# ESTA TUPLA É A ÚNICA FONTE
#     O campo por edital e o total do `resumir()` leem os dois daqui. É o que
#     torna «o total fecha com a contagem por estado» uma consequência da
#     estrutura, e não uma coincidência que um dia se desfaz.
ESTADOS_DE_ANOMALIA = (convencao.ESTADO_AUSENTE, convencao.ESTADO_AMBIGUA)
ESTADOS_DE_ROTINA = (convencao.ESTADO_VAZIA, convencao.ESTADO_COM_ARQUIVO)


def eh_anomalia(estado: str) -> bool:
    """`True` para `AUSENTE` e `AMBIGUA`; `False` para `VAZIA` e `COM_ARQUIVO`."""
    return estado in ESTADOS_DE_ANOMALIA


def _data_do_sistema_de_arquivos(caminho: Path) -> str:
    r"""
    A data de modificação de um arquivo solto, como INSTANTE UTC:
    'AAAA-MM-DDTHH:MM:SSZ'. O "Z" é parte do valor, e é ele que diz que a hora
    está em UTC.

    POR QUE UTC, E POR QUE ISSO É CORREÇÃO DE DEFEITO
        `os.path.getmtime()` devolve um instante POSIX — um número de segundos
        desde a época, que NÃO depende de fuso nenhum. O defeito nunca esteve no
        dado: estava na renderização. `datetime.fromtimestamp(ts)` sem `tz`
        converte esse instante para a hora de parede da MÁQUINA, e a mesma
        árvore intocada passava a produzir texto diferente só porque foi
        observada noutro fuso.

        Medido, sobre a mesma árvore e os mesmos bytes:

            America/Sao_Paulo  ->  2026-09-14T15:31:01
            UTC                ->  2026-09-14T18:31:01
            Asia/Tokyo         ->  2026-09-15T03:31:01

        Isso quebrava o contrato do §4.4 — «mesma entrada lógica e mesmo
        conjunto de arquivos -> mesmo inventário, byte a byte. Sem depender de
        ordem do sistema de arquivos, horário, máquina ou usuário». Com `tz` fixo
        em UTC, a renderização passa a ser função só do instante, e a mesma
        árvore dá o mesmo byte em qualquer máquina.

    O ARGUMENTO ANTIGO ERA FALSO, E A REFUTAÇÃO ESTÁ NO PRÓPRIO CÓDIGO
        A versão anterior justificava a hora local dizendo que «gravar UTC de um
        lado e hora local do outro tornaria os dois incomparáveis». Não torna, e
        quem prova é `diff_inventario.identidade()`:

            (codigo_edital, container, caminho)

        O `container` ENTRA na identidade. Arquivo solto tem `container=None` e
        NUNCA casa com membro de `.zip`. Cada data só é comparada com ela mesma
        da execução anterior, dentro da mesma família — a comparação cruzada que
        o argumento temia não existe, e nunca existiu.
    """
    instante = datetime.fromtimestamp(os.path.getmtime(caminho), tz=timezone.utc)
    return instante.strftime("%Y-%m-%dT%H:%M:%SZ")


def _data_do_indice_do_zip(info: zipfile.ZipInfo) -> str:
    """
    A data de modificação registrada no índice do `.zip`, como
    'AAAA-MM-DDTHH:MM:SS' — SEM o "Z", e a ausência é o dado.

    POR QUE NÃO LEVA "Z", E POR QUE NÃO FOI CONVERTIDA PARA UTC
        O formato ZIP guarda data e hora no campo MS-DOS, que é HORA DE PAREDE
        de quem gravou o arquivo, **sem fuso nenhum registrado**. O fuso não está
        lá para ser lido. Converter isso para UTC exigiria ADIVINHAR em que fuso
        o arquivo foi zipado — e adivinhar fuso é exatamente inventar metadata
        que não existe.

        Então esta data não é convertida: é preservada como está no índice, que
        é o fato disponível. Ela já é determinística, porque vem dos bytes do
        arquivo e não do relógio da máquina que lê — foi a única das duas
        famílias que o defeito de fuso nunca atingiu.

    A SEMÂNTICA, ENTÃO, É DIFERENTE DA DO ARQUIVO SOLTO — E O VALOR DIZ QUAL É
        com "Z" no fim  ->  instante UTC, do sistema de arquivos
        sem "Z" no fim  ->  hora de parede sem fuso, do índice do ZIP

        Não foi criado campo novo para carregar essa distinção: ela já está no
        valor (é assim que a ISO-8601 distingue os dois casos) e é redundante com
        um campo que já existia, `onde_estava` — SOLTO_NA_PASTA leva "Z",
        DENTRO_DO_CONTAINER não leva. Um campo a mais seria uma terceira cópia da
        mesma informação, com uma terceira chance de divergir.
    """
    ano, mes, dia, hora, minuto, segundo = info.date_time
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (ano, mes, dia, hora, minuto, segundo)


# ═══════════════════════════════════════════════════════════════════════════
# O NOME DO MEMBRO DE CONTAINER — declarar, nunca adivinhar calado (§4.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# O `.zip` guarda o nome do membro em BYTES. Um bit do índice — o 0x800 dos
# `flag_bits` — declara se esses bytes estão em UTF-8. Quando o bit está
# DESLIGADO, o `zipfile` do Python decodifica como cp437; e há zipadores que
# gravam bytes UTF-8 sem ligar o bit. Aí todo caractere acentuado sai trocado,
# SEM ERRO E SEM AVISO — que é a classe de falha que este projeto existe para
# não ter.
#
# NÃO SE CONSERTA ADIVINHANDO. Consertar em silêncio é tão silencioso quanto
# errar em silêncio: muda só de lado. O que esta regra faz é DECLARAR.
BIT_UTF8_DO_INDICE = 0x800

# ─── O filtro de plausibilidade — objetivo, enumerado, nunca julgado ────────
#
# Um candidato é IMPLAUSÍVEL se contiver QUALQUER ponto de código destas faixas.
# A decisão sai DESTA TABELA, e de mais lugar nenhum: nada aqui é avaliado
# "por impressão", nem caso a caso.
#
# A MEDIÇÃO QUE AS JUSTIFICA — os 256 bytes, um a um:
#
#   Os bytes que LIDERAM sequência UTF-8 de dois bytes são C2-DF, e é aí que
#   caem TODOS os acentos latinos. Em cp437 esses 30 bytes viram, sem exceção:
#
#       C2-DA (25 bytes) -> ┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌   desenho de caixa
#       DB-DF ( 5 bytes) -> █▄▌▐▀                        elementos de bloco
#
#   Um nome UTF-8 lido como cp437 EXIBE DESENHO DE CAIXA. E nome de arquivo não
#   tem desenho de caixa. É isso, e só isso, que torna o filtro objetivo.
#   Medido: 'publicação' em UTF-8, lido como cp437, dá 'publica├º├úo'.
#
#   Entre os bytes de CONTINUAÇÃO (80-BF), que acompanham todo líder, 13 caem em
#   desenho de caixa, 3 em elementos de bloco e 1 (0xA9) em técnicos diversos.
#
# A FAIXA ACRESCENTADA, E O MOTIVO MEDIDO
#   U+2300-23FF (técnicos diversos) não estava no mínimo exigido. Entrou porque
#   a medição mostrou que exatamente três bytes caem nela — 0xA9 -> ⌐, 0xF4 -> ⌠
#   e 0xF5 -> ⌡ — e o 0xA9 é BYTE DE CONTINUAÇÃO, isto é, aparece em nome UTF-8
#   mal lido de verdade ('é' = C3 A9 vira '├⌐'). Nenhum dos três ocorre em nome
#   de arquivo. Deixá-la de fora deixaria passar leitura errada que a medição
#   mostra ser frequente.
#
# O QUE FICA DE FORA DE PROPÓSITO — e é a parte que importa
#   Os líderes de TRÊS bytes (E0-EF) viram, em sua maioria, LETRA GREGA:
#   αΓπΣστΦΘΩδφε. Grego NÃO entra no filtro, porque letra grega ocorre, sim, em
#   nome de arquivo. É exatamente esse vão que torna possível a ambiguidade
#   REAL — duas leituras plausíveis do mesmo nome. Fechá-lo por conveniência
#   seria transformar dúvida em certeza inventada, que é o oposto do que esta
#   regra faz. O vão fica aberto, e a ambiguidade é DECLARADA.
FAIXAS_IMPLAUSIVEIS_EM_NOME = (
    (0x0000, 0x001F, "caracteres de controle"),
    (0x007F, 0x007F, "DEL"),
    (0x2200, 0x22FF, "operadores matemáticos"),
    (0x2300, 0x23FF, "técnicos diversos"),
    (0x2500, 0x257F, "desenho de caixa"),
    (0x2580, 0x259F, "elementos de bloco"),
    (0x25A0, 0x25FF, "formas geométricas"),
)


def _implausibilidade(texto: str) -> str | None:
    """
    O motivo pelo qual `texto` é implausível como nome de arquivo, ou `None`.

    Percorre o texto na ordem e devolve o PRIMEIRO caractere que cai numa das
    faixas declaradas, dizendo qual faixa o pegou. Determinístico por
    construção: a ordem é a do texto, e as faixas são uma tupla fixa.
    """
    for posicao, caractere in enumerate(texto):
        ponto = ord(caractere)
        for inicio, fim, nome_da_faixa in FAIXAS_IMPLAUSIVEIS_EM_NOME:
            if inicio <= ponto <= fim:
                return (f"{caractere!r} (U+{ponto:04X}, {nome_da_faixa}) "
                        f"na posição {posicao}")
    return None


def _ler_nome_de_membro(info: zipfile.ZipInfo) -> tuple[str, dict | None]:
    """
    O nome de um membro de container, e o achado que declara COMO ele foi lido.

    Devolve `(nome_adotado, achado_ou_None)`.

    A REGRA É GENÉRICA. Vale para qualquer container, qualquer nome, qualquer
    zipador. Não há aqui nome de arquivo, de município nem valor algum — só o
    bit do índice, os bytes crus e a tabela de faixas acima.

    QUANDO O BIT ESTÁ LIGADO, CONFIE NELE. O índice DECLAROU UTF-8, e declaração
    é o que se pede. Nada muda — e é a maioria esmagadora dos casos.

    QUANDO ESTÁ DESLIGADO, o container não declarou nada, e existem CANDIDATOS:

        A  a leitura cp437   existe SEMPRE — cp437 é mapeamento total, todo
                             byte vira algum caractere
        B  a leitura UTF-8   existe SÓ se os bytes decodificarem limpo

    UTF-8 VÁLIDO NÃO É UTF-8 COMPROVADO. Como a leitura cp437 existe sempre, uns
    bytes que também formem UTF-8 válido têm DUAS leituras possíveis. Adotar
    UTF-8 só porque ele decodifica seria transformar ambiguidade real em certeza
    inventada. Por isso a escolha só acontece quando há UM ÚNICO candidato
    tecnicamente possível — e, fora disso, a dúvida é o resultado.

        exatamente UM plausível  -> esse candidato   · ENCODING_NOME_NAO_DECLARADO
        DOIS plausíveis          -> a leitura cp437  · ENCODING_NOME_AMBIGUO
        NENHUM plausível         -> a leitura cp437  · ENCODING_NOME_AMBIGUO

    A ESCOLHA DO `caminho` NA AMBIGUIDADE É DE ESTABILIDADE, NÃO DE VERDADE.
    cp437 porque é determinística e é a mesma que a versão anterior produzia —
    e `caminho` entra na identidade do diff (`diff_inventario.identidade()`),
    então trocá-la sem necessidade inventaria um REMOVIDO e um ADICIONADO por
    membro. O achado diz, com todas as letras, que NÃO se afirma qual é o
    verdadeiro. Dizer «não sei» é resultado; escolher no escuro é defeito.

    OS BYTES CRUS SE RECUPERAM DO PRÓPRIO NOME QUE O `zipfile` ENTREGOU,
    re-codificando em cp437 — não é preciso reabrir o arquivo nem inventar
    leitura. E é exato: medido, cp437 é BIJEÇÃO sobre os 256 bytes (256 bytes ->
    256 caracteres distintos, zero colisão), logo `decode` e `encode` são
    inversos perfeitos.
    """
    nome_cp437 = info.filename

    if info.flag_bits & BIT_UTF8_DO_INDICE:
        return nome_cp437, None

    if nome_cp437.isascii():
        # Nada a decidir: os bytes ASCII são os mesmos em cp437 e em UTF-8, e as
        # duas leituras coincidem. É a esmagadora maioria dos membros.
        return nome_cp437, None

    crus = nome_cp437.encode("cp437")

    motivo_cp437 = _implausibilidade(nome_cp437)
    try:
        nome_utf8 = crus.decode("utf-8")
    except UnicodeDecodeError as erro:
        nome_utf8, motivo_utf8 = None, f"não decodifica como UTF-8 ({erro.reason})"
    else:
        motivo_utf8 = _implausibilidade(nome_utf8)

    plausiveis = []
    if motivo_cp437 is None:
        plausiveis.append(("cp437", nome_cp437))
    if nome_utf8 is not None and motivo_utf8 is None:
        plausiveis.append(("utf-8", nome_utf8))

    leitura_cp437 = f"cp437={nome_cp437!r}"
    leitura_utf8 = (f"utf-8={nome_utf8!r}" if nome_utf8 is not None
                    else f"utf-8=(indisponível: {motivo_utf8})")
    nao_declarou = ("o índice do container não declarou a codificação do nome "
                    "(bit 0x800 desligado)")

    if len(plausiveis) == 1:
        rotulo_adotado, adotado = plausiveis[0]
        if rotulo_adotado == "cp437":
            descartada, motivo_descartada = leitura_utf8, motivo_utf8
        else:
            descartada, motivo_descartada = leitura_cp437, motivo_cp437
        return adotado, _achado(
            ACHADO_ENCODING_NAO_DECLARADO,
            f"{nome_cp437!r}: {nao_declarou}; UMA única leitura é tecnicamente "
            f"possível. ADOTADA {rotulo_adotado}={adotado!r}. DESCARTADA "
            f"{descartada} — {motivo_descartada}.")

    # DOIS plausíveis, ou NENHUM: o `caminho` fica em cp437 por ESTABILIDADE, e
    # o achado NÃO diz qual é o verdadeiro.
    if len(plausiveis) == 2:
        situacao = "as DUAS leituras são plausíveis, e têm textos diferentes"
    else:
        situacao = (f"NENHUMA das leituras é plausível "
                    f"(cp437: {motivo_cp437} · utf-8: {motivo_utf8})")
    return nome_cp437, _achado(
        ACHADO_ENCODING_AMBIGUO,
        f"{nome_cp437!r}: {nao_declarou}; {situacao}. LEITURAS POSSÍVEIS: "
        f"{leitura_cp437} · {leitura_utf8}. O `caminho` ficou na leitura cp437 "
        f"por ser determinística e igual à da versão anterior — escolha de "
        f"ESTABILIDADE, NÃO de verdade. NÃO se afirma qual é o nome verdadeiro.")


def _extensao(nome: str) -> str:
    """A extensão derivada do NOME, em minúsculas. Sem extensão vira string vazia."""
    return Path(nome).suffix.lower()


def _entrada_arquivo(caminho: str, tamanho: int, modificado_em: str,
                     onde_estava: str, container: str | None) -> dict:
    """
    Uma entrada do inventário — um arquivo.

    NÃO há SHA-256 aqui, de propósito (§4.4): o hash pertence a quem for
    processar o arquivo, e calculá-lo obrigaria a LER o conteúdo — exatamente o
    que o índice do `.zip` existe para evitar.
    """
    return {
        "caminho": caminho,
        "tamanho_bytes": tamanho,
        "modificado_em": modificado_em,
        "extensao": _extensao(caminho),
        "onde_estava": onde_estava,
        "container": container,
        # `resumo_edital.*` é artefato do MÓDULO 1, não do edital. O Módulo 2 o
        # exclui de propósito; aqui ele ENTRA e é MARCADO. Quem filtra é o
        # consumidor (§4.5).
        "artefato_do_m1": convencao.eh_artefato_do_modulo1(caminho),
    }


def _ordem_do_arquivo(entrada: dict) -> tuple:
    """
    A chave de ordenação — a mesma que dá o determinismo do §4.4.

    Primeiro os soltos, depois os de dentro de container; dentro de cada grupo,
    por container e por caminho. Nada de ordem do sistema de arquivos.

    O tamanho e a data NÃO entram na chave: dois arquivos de mesmo caminho e
    mesmo container não existem (o sistema de arquivos e o índice do ZIP não
    permitem), e incluí-los faria a ordem mudar quando o arquivo mudasse.
    """
    return (0 if entrada["onde_estava"] == ONDE_SOLTO else 1,
            entrada["container"] or "",
            entrada["caminho"])


def _achado(tipo: str, detalhe: str) -> dict:
    return {"tipo": tipo, "detalhe": detalhe}


def _inventariar_container(caminho_zip: Path, nome_zip: str) -> tuple[list[dict], list[dict]]:
    """
    O que há DENTRO de um `.zip`, pelo índice — e os achados do caminho.

    NÃO DESCE MAIS DE UM NÍVEL (§4.6). Um `.zip` dentro do `.zip` é registrado
    como ARQUIVO, com o achado CONTAINER_ANINHADO ao lado, e NÃO é aberto: abrir
    exigiria uma regra escrita sobre até onde descer, e essa regra não existe.
    A medição desta rodada encontrou 85 zips aninhados na base real — é caso
    frequente, não exceção teórica, e por isso é declarado em vez de adivinhado.

    `.zip` ilegível, corrompido ou protegido não bloqueia a cadeia: o container é
    declarado não inventariável e a vida segue.
    """
    arquivos: list[dict] = []
    achados: list[dict] = []
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            infos = z.infolist()
    except Exception as erro:
        achados.append(_achado(
            ACHADO_CONTAINER_ILEGIVEL,
            f"{nome_zip}: {type(erro).__name__}: {erro}"))
        return arquivos, achados

    for info in infos:
        # O NOME VEM DA REGRA DO §4.1, não direto do `info.filename`. Tudo o que
        # vier depois — o teste de subpasta, a extensão, o achado de aninhado e o
        # `caminho` gravado — usa a MESMA leitura adotada. Se cada trecho lesse o
        # nome por conta própria, voltaria a existir a divergência silenciosa que
        # esta correção existe para fechar.
        nome_interno, achado_do_nome = _ler_nome_de_membro(info)
        if achado_do_nome is not None:
            achados.append(achado_do_nome)
        if info.is_dir():
            achados.append(_achado(
                ACHADO_SUBPASTA_NO_CONTAINER, f"{nome_zip} -> {nome_interno}"))
            continue

        # Um membro com "/" no nome ESTÁ em subpasta dentro do container. O
        # índice já entrega o caminho inteiro, então não há descida nenhuma a
        # fazer: o arquivo é listado com o caminho que tem, e o achado é
        # declarado. Zips do Office trazem `_rels/.rels` e `theme/...` assim.
        if "/" in nome_interno:
            achados.append(_achado(
                ACHADO_SUBPASTA_NO_CONTAINER, f"{nome_zip} -> {nome_interno}"))

        extensao = _extensao(nome_interno)
        if extensao == ".zip":
            achados.append(_achado(
                ACHADO_CONTAINER_ANINHADO,
                f"{nome_zip} -> {nome_interno} (registrado como arquivo; NÃO aberto)"))
        elif extensao in EXTENSOES_CONTAINER_NAO_ABERTO:
            achados.append(_achado(
                ACHADO_CONTAINER_ANINHADO,
                f"{nome_zip} -> {nome_interno} (formato de container sem regra escrita; "
                f"registrado como arquivo, NÃO aberto)"))

        arquivos.append(_entrada_arquivo(
            caminho=nome_interno,
            tamanho=info.file_size,
            modificado_em=_data_do_indice_do_zip(info),
            onde_estava=ONDE_NO_CONTAINER,
            container=nome_zip,
        ))

    return arquivos, achados


def _ler_manifesto_m1(pasta_edital: Path) -> tuple[str, set, str]:
    """
    (situação, {(nome, tamanho)} do que o M1 baixou, erro). Situação:
    "PRESENTE", "AUSENTE" ou "ILEGIVEL". Ilegível vale como ausente — a pasta
    segue o comportamento de antes, e o fato vira achado.
    """
    caminho = pasta_edital / NOME_MANIFESTO_M1
    if not caminho.is_file():
        return "AUSENTE", set(), ""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        baixados = {(str(a["nome"]), int(a["tamanho_bytes"]))
                    for a in dados.get("arquivos") or ()}
        return "PRESENTE", baixados, ""
    except Exception as erro:
        return "ILEGIVEL", set(), f"{type(erro).__name__}: {erro}"


def _marcar_origem(pasta_edital: Path, arquivos: list[dict]) -> list[dict]:
    """
    Põe `origem` e `origem_descricao` em cada arquivo da pasta (ver o bloco
    «A ORIGEM DE CADA ARQUIVO»). Devolve os achados do manifesto.
    """
    situacao, baixados, erro = _ler_manifesto_m1(pasta_edital)
    achados: list[dict] = []
    if situacao != "PRESENTE":
        for entrada in arquivos:
            entrada["origem"] = ORIGEM_SEM_MANIFESTO
            entrada["origem_descricao"] = DESCRICAO_DA_ORIGEM[ORIGEM_SEM_MANIFESTO]
        # O aviso «sem manifesto do M1» vai em CADA arquivo (`origem_descricao`),
        # e NÃO como achado: a pasta antiga sai com os mesmos achados de antes de
        # 05/10 — um achado a mais em todo edital antigo seria ruído, e mudaria o
        # inventário de toda pasta que não mudou.
        if situacao == "ILEGIVEL":
            achados.append(_achado(ACHADO_MANIFESTO_ILEGIVEL, f"{NOME_MANIFESTO_M1}: {erro}"))
        return achados

    containers_do_m1 = {e["caminho"] for e in arquivos
                        if e["onde_estava"] == ONDE_SOLTO
                        and (e["caminho"], e["tamanho_bytes"]) in baixados}
    for entrada in arquivos:
        if entrada["onde_estava"] == ONDE_SOLTO:
            if entrada["caminho"] == NOME_MANIFESTO_M1 or entrada["artefato_do_m1"]:
                origem = ORIGEM_ARTEFATO_DO_M1
            elif entrada["caminho"] in containers_do_m1:
                origem = ORIGEM_BAIXADO_PELO_M1
            else:
                origem = ORIGEM_ARQUIVO_DA_EQUIPE
        else:
            origem = (ORIGEM_BAIXADO_PELO_M1 if entrada["container"] in containers_do_m1
                      else ORIGEM_ARQUIVO_DA_EQUIPE)
        entrada["origem"] = origem
        entrada["origem_descricao"] = DESCRICAO_DA_ORIGEM[origem]
    return achados


def _inventariar_pasta(pasta_edital: Path) -> tuple[list[dict], list[dict]]:
    """
    Tudo o que existe na pasta do edital: os arquivos soltos e o conteúdo dos
    containers do primeiro nível.

    LISTA TUDO E MARCA A ORIGEM. NÃO DESCARTA NADA (§4.5):
      · `.docx` e `.xlsx` entram, mesmo que o consumidor de hoje só leia PDF;
      · `resumo_edital.json`/`.docx` entram, MARCADOS como artefato do Módulo 1;
      · arquivo de ZERO BYTE entra, com tamanho zero — não se finge que não existe;
      · dois arquivos de mesmo NOME em caminhos diferentes entram os DOIS, como
        entradas distintas. Não há deduplicação, e nada é apagado.

    Subpasta na pasta do edital é DECLARADA e NÃO percorrida (§4.6) — a mesma
    regra do `pasta_tem_arquivo_edital()` do Módulo 2, que também olha só o
    primeiro nível.
    """
    arquivos: list[dict] = []
    achados: list[dict] = []

    try:
        itens = sorted(pasta_edital.iterdir())
    except OSError as erro:
        achados.append(_achado(
            ACHADO_PASTA_ILEGIVEL, f"{type(erro).__name__}: {erro}"))
        return arquivos, achados

    nomes_zip: list[str] = []
    for item in itens:
        if item.is_dir():
            achados.append(_achado(
                ACHADO_SUBPASTA_NA_PASTA,
                f"{item.name} (declarada; NÃO percorrida — sem regra escrita)"))
            continue
        if not item.is_file():
            continue

        try:
            tamanho = item.stat().st_size
            modificado = _data_do_sistema_de_arquivos(item)
        except OSError as erro:
            achados.append(_achado(
                ACHADO_PASTA_ILEGIVEL, f"{item.name}: {type(erro).__name__}: {erro}"))
            continue

        arquivos.append(_entrada_arquivo(
            caminho=item.name,
            tamanho=tamanho,
            modificado_em=modificado,
            onde_estava=ONDE_SOLTO,
            container=None,
        ))

        extensao = _extensao(item.name)
        if extensao == ".zip":
            nomes_zip.append(item.name)
        elif extensao in EXTENSOES_CONTAINER_NAO_ABERTO:
            achados.append(_achado(
                ACHADO_CONTAINER_ANINHADO,
                f"{item.name} (formato de container sem regra escrita; NÃO aberto)"))

    # TODOS os `.zip` são abertos — não só o primeiro. O
    # `listar_arquivos_edital()` do Módulo 2 abre `zips[0]` e para ali; a medição
    # desta rodada achou 13 pastas com mais de um `.zip`, e nelas aquela regra
    # deixaria o conteúdo dos demais invisível.
    if len(nomes_zip) > 1:
        achados.append(_achado(
            ACHADO_MAIS_DE_UM_CONTAINER,
            f"{len(nomes_zip)} containers: " + ", ".join(nomes_zip)))

    for nome_zip in nomes_zip:
        de_dentro, achados_do_zip = _inventariar_container(pasta_edital / nome_zip, nome_zip)
        arquivos.extend(de_dentro)
        achados.extend(achados_do_zip)

    achados.extend(_marcar_origem(pasta_edital, arquivos))

    arquivos.sort(key=_ordem_do_arquivo)
    achados.sort(key=lambda a: (a["tipo"], a["detalhe"]))
    return arquivos, achados


def inventariar_edital(linha_agenda: dict, raiz_editais: Path) -> dict:
    """
    O inventário de UM edital.

    DOIS ESTADOS SÃO ROTINA, DOIS SÃO ANOMALIA — e os quatro seguem sem parar.

        rotina   COM_ARQUIVO · VAZIA
        anomalia AUSENTE · AMBIGUA

    O campo `anomalia` é essa distinção, e significa «NÃO É ROTINA». Ver
    `ESTADOS_DE_ANOMALIA`, que é a fonte única de onde ele e o total saem.

        VAZIA    a pasta existe e não tem arquivo do edital. É o normal: o portal
                 publicou a licitação sem o arquivo e a equipe pede o documento
                 ao município. Registra e segue, sem destaque.

        AUSENTE  a linha existe na Agenda e a pasta NÃO existe. NÃO deveria
                 acontecer: a docstring do Módulo 1 registra que a pasta do
                 edital é «Criada SEMPRE, mesmo quando não vier arquivo nenhum
                 … Vem antes do download de propósito.» Logo, linha sem pasta
                 significa que a pasta foi apagada, renomeada ou arrastada
                 depois — erro humano, ou problema no volume.

        AMBIGUA  duas ou mais pastas candidatas terminam no código deste
                 edital, e não há regra inequívoca para escolher entre elas.
                 É o MAIS GRAVE dos quatro: `AUSENTE` diz «a pasta sumiu»,
                 `AMBIGUA` diz «NÃO SE SABE qual pasta é a deste edital» — e
                 não saber qual é a pasta é pior que saber que ela não está lá.
                 O fail-closed da D1 recusa escolher, e fica exatamente assim.

    Colapsar os estados apagaria exatamente o sinal que interessa: «chegou
    vazio», «a pasta sumiu» e «não se sabe qual é a pasta» pedem três ações
    diferentes da equipe.

    NENHUM DOS DOIS BLOQUEIA. Um AUSENTE não pode impedir os outros de serem
    inventariados — quem chama registra e passa para o próximo.
    """
    estado, pasta = convencao.estado_pasta_edital(linha_agenda, raiz_editais)
    candidatas = convencao.candidatas_pasta_edital(linha_agenda, raiz_editais)

    registro = {
        # A IDENTIDADE é o código que já existe, reescrito na forma que o Módulo
        # 1 já usa no nome da pasta. Não há ID paralelo, UUID próprio nem
        # segundo código — e não pode haver.
        "codigo_edital": convencao.formatar_codigo_edital(
            linha_agenda.get("codigo_conlicitacao", "")),
        "codigo_conlicitacao": linha_agenda.get("codigo_conlicitacao", ""),
        "linha_agenda": linha_agenda["linha_agenda"],
        "cidade": linha_agenda["cidade"],
        "uf": linha_agenda["uf"],
        "numero_pregao": linha_agenda["numero_pregao"],
        "data_limite": linha_agenda.get("data_limite", ""),
        "chave_pasta": convencao.chave_pasta_edital(linha_agenda),
        "estado_pasta": estado,
        # `anomalia` é «NÃO É ROTINA»: verdadeira para AUSENTE e para AMBIGUA,
        # falsa para VAZIA e COM_ARQUIVO. Lê de `ESTADOS_DE_ANOMALIA`, que é a
        # fonte única — o total do `resumir()` lê da mesma tupla.
        "anomalia": eh_anomalia(estado),
        "pasta_relativa": None,
        "arquivos": [],
        "achados": [],
    }

    if estado == convencao.ESTADO_AMBIGUA:
        # FAIL-CLOSED (§4.6): duas pastas candidatas para a mesma identidade, sem
        # regra inequívoca para escolher entre elas. O Inventariador REGISTRA a
        # ambiguidade e NÃO ESCOLHE. Ausência declarada é sempre melhor que
        # associação errada.
        registro["achados"] = [_achado(
            ACHADO_AMBIGUIDADE,
            f"{len(candidatas)} pastas terminam em "
            f"'{convencao.sufixo_identidade(linha_agenda)}': "
            + ", ".join(sorted(c.name for c in candidatas))
            + " — nenhuma foi escolhida")]
        return registro

    if estado == convencao.ESTADO_AUSENTE:
        return registro

    registro["pasta_relativa"] = pasta.name
    arquivos, achados = _inventariar_pasta(pasta)
    registro["arquivos"] = arquivos
    registro["achados"] = achados
    return registro


def _ordem_do_edital(registro: dict) -> tuple:
    """
    A ordem dos editais no inventário: pelo código, depois pela linha da Agenda.

    O código vem primeiro porque é a identidade; a linha desempata quando o
    mesmo código aparece em duas linhas (o Módulo 1 tem detecção própria para
    isso, e a medição desta rodada não encontrou nenhum caso — mas a ordem não
    pode depender de não haver).
    """
    return (registro["codigo_edital"], registro["linha_agenda"])


def montar_inventario(linhas_agenda: list[dict], raiz_editais: Path) -> dict:
    """
    O inventário completo — um registro por linha da Agenda.

    O corpo devolvido NÃO carrega horário, caminho absoluto, máquina nem
    usuário: é o que permite comparar dois inventários byte a byte. A identidade
    da execução vive no relatório, ao lado.
    """
    raiz_editais = Path(raiz_editais)
    registros = [inventariar_edital(linha, raiz_editais) for linha in linhas_agenda]
    registros.sort(key=_ordem_do_edital)

    return {
        "schema_version": SCHEMA_VERSION,
        "gerado_por": "inventariador",
        "contrato": {
            "identidade_do_edital": "codigo_edital — o Código ConLicitação já existente, "
                                    "no formato CONLIC-{id} que o Módulo 1 usa no nome da "
                                    "pasta. Nenhum identificador é criado aqui.",
            "estados_da_pasta": [convencao.ESTADO_AUSENTE, convencao.ESTADO_VAZIA,
                                 convencao.ESTADO_COM_ARQUIVO, convencao.ESTADO_AMBIGUA],
            "onde_estava": [ONDE_SOLTO, ONDE_NO_CONTAINER],
            "modificado_em": (
                "AAAA-MM-DDTHH:MM:SSZ quando onde_estava=SOLTO_NA_PASTA — instante UTC, "
                "do sistema de arquivos. AAAA-MM-DDTHH:MM:SS (sem Z) quando "
                "onde_estava=DENTRO_DO_CONTAINER — hora de parede SEM FUSO, como o índice "
                "do ZIP a registra; o formato ZIP não guarda fuso, e adivinhá-lo seria "
                "inventar metadata. As duas nunca são comparadas entre si: o container "
                "entra na identidade do diff."
            ),
            "sem_sha256": "o hash pertence a quem for processar o arquivo (§4.4)",
            "origem": DESCRICAO_DA_ORIGEM,
            "profundidade": "um nível — o conteúdo do .zip solto na pasta. "
                            "Subpasta e container aninhado são DECLARADOS e não percorridos.",
        },
        "totais": resumir(registros),
        "editais": registros,
    }


def resumir(registros: list[dict]) -> dict:
    """
    A conta do inventário — cada número dizendo o que mede.

    `editais` é o denominador: linhas da Agenda lidas. Os quatro estados somam
    exatamente `editais`, porque todo edital tem um e só um estado.
    `arquivos` conta ENTRADAS de arquivo, não editais, e por isso não soma com
    os outros.

    O TOTAL DE ANOMALIA MUDOU DE NOME, E O MOTIVO É QUE O NOME ANTIGO MENTIA
        Ele se chamava `editais_com_anomalia_pasta_ausente` — nome de UM estado
        só — e, com o §4.2, passou a contar DOIS. Um número cujo nome descreve
        menos do que ele mede é pior que um número ausente: quem lê acredita.

        Escolhida a RENOMEAÇÃO para `editais_com_anomalia`, e não a quebra por
        estado, porque a quebra por estado JÁ EXISTE ao lado, em
        `editais_por_estado_da_pasta`. Acrescentar uma segunda seria uma terceira
        cópia do mesmo fato, com uma terceira chance de divergir — que é o
        argumento que a D2.2 já usou para não criar campo novo.

        E é por lerem os dois de `ESTADOS_DE_ANOMALIA` que o total FECHA com a
        contagem por estado por construção, e não por coincidência.
    """
    por_estado = {}
    for registro in registros:
        por_estado[registro["estado_pasta"]] = por_estado.get(registro["estado_pasta"], 0) + 1

    achados_por_tipo = {}
    for registro in registros:
        for achado in registro["achados"]:
            achados_por_tipo[achado["tipo"]] = achados_por_tipo.get(achado["tipo"], 0) + 1

    arquivos = sum(len(r["arquivos"]) for r in registros)
    return {
        "editais_linhas_da_agenda": len(registros),
        "editais_por_estado_da_pasta": dict(sorted(por_estado.items())),
        "editais_com_anomalia": sum(1 for r in registros if r["anomalia"]),
        "entradas_de_arquivo": arquivos,
        "entradas_soltas_na_pasta": sum(
            1 for r in registros for a in r["arquivos"] if a["onde_estava"] == ONDE_SOLTO),
        "entradas_dentro_de_container": sum(
            1 for r in registros for a in r["arquivos"] if a["onde_estava"] == ONDE_NO_CONTAINER),
        "entradas_marcadas_artefato_do_m1": sum(
            1 for r in registros for a in r["arquivos"] if a["artefato_do_m1"]),
        "entradas_de_zero_byte": sum(
            1 for r in registros for a in r["arquivos"] if a["tamanho_bytes"] == 0),
        "achados_por_tipo": dict(sorted(achados_por_tipo.items())),
    }
