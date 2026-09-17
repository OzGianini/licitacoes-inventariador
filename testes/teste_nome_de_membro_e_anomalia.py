# -*- coding: utf-8 -*-
r"""
SUÍTE DO FECHAMENTO — o nome de membro de container (§4.1) e a abrangência do
campo `anomalia` (§4.2).

NUNCA TOCA EM `C:\Editais 2026`. Toda árvore usada aqui nasce num
`tempfile.mkdtemp()` e morre no fim do teste.

POR QUE ESTA SUÍTE EXISTE SEPARADA, EM VEZ DE ENTRAR NA SINTÉTICA
    Porque ela precisa de uma ferramenta que nenhuma outra precisa: um
    construtor de `.zip` **no nível do byte**. O `zipfile` do Python SEMPRE liga
    o bit 0x800 quando o nome do membro não é ASCII — logo ele **não reproduz o
    defeito sozinho**, e um teste escrito só com ele passaria por construção
    sem poder falhar. Era exatamente esse o problema do teste de «nomes com
    acentos» da suíte sintética: ele passava, e não provava nada sobre o defeito.

    Construir o defeito, e não simulá-lo, é o que separa uma prova de um enfeite.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import convencao_edital as convencao  # noqa: E402
import inventario as inv  # noqa: E402

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

_falhas = []
_total = 0


def checar(condicao, descricao, detalhe=""):
    global _total
    _total += 1
    if condicao:
        print(f"  [x] {descricao}")
    else:
        print(f"  [ ] FALHOU: {descricao}" + (f" — {detalhe}" if detalhe else ""))
        _falhas.append(descricao)


def igual(obtido, esperado, descricao):
    checar(obtido == esperado, descricao, f"obtido={obtido!r} esperado={esperado!r}")


# ═══════════════════════════════════════════════════════════════════════════
# ANDAIMES
# ═══════════════════════════════════════════════════════════════════════════

class Area:
    """Uma raiz de editais temporária, apagada no fim."""

    def __enter__(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="inventariador_nome_"))
        return self.raiz

    def __exit__(self, *args):
        shutil.rmtree(self.raiz, ignore_errors=True)
        return False


def linha(cidade="Curitiba", uf="PR", numero="PE/35/2026", codigo="19241283",
          linha_agenda=3):
    return {
        "linha_agenda": linha_agenda,
        "cidade": cidade,
        "uf": uf,
        "numero_pregao": numero,
        "codigo_conlicitacao": codigo,
        "data_limite": "01/10/2026",
    }


def criar_pasta(raiz: Path, linha_agenda: dict) -> Path:
    pasta = raiz / convencao.chave_pasta_edital(linha_agenda)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


DATA_HORA_FIXA = (2026, 9, 14, 18, 31, 0)


def zip_com_bytes_crus_no_nome(caminho: Path, membros: list[tuple[bytes, bytes]]) -> Path:
    r"""
    Um `.zip` cujos nomes de membro são os BYTES pedidos, com o bit 0x800
    **DESLIGADO** — o defeito, construído, não simulado.

    COMO O BIT É DESLIGADO
        Ele não é desligado: ele **nunca é ligado**. O `_encodeFilenameFlags()`
        do `zipfile` só acrescenta `0x800` quando o nome NÃO é ASCII. Escrevendo
        com um nome-marcador **ASCII**, o `zipfile` grava `flag_bits` sem aquele
        bit, e é o próprio arquivo pronto que fica com o bit desligado.

    COMO OS BYTES ENTRAM NO LUGAR
        O marcador tem **exatamente o mesmo comprimento em bytes** que o nome de
        verdade. Trocar bytes por bytes de mesmo tamanho não desloca offset
        nenhum — nem o do diretório central, nem o do cabeçalho local —, então o
        `.zip` continua válido sem precisar recalcular nada. O CRC e os tamanhos
        são do CONTEÚDO, não do nome, e por isso seguem corretos.

        A troca é feita no arquivo inteiro de propósito: o nome aparece DUAS
        vezes (cabeçalho local e diretório central), e os dois têm de casar.

    O MARCADOR É UM CARACTERE REPETIDO, UM DIFERENTE POR MEMBRO
        Um marcador com texto comum ('~MARCADOR0', '~MARCADOR1', …) truncado ao
        comprimento do nome vira PREFIXO dos outros — e aí a troca do primeiro
        acerta os oito lugares errados. Com um caractere distinto por membro,
        nenhum marcador pode ser pedaço de outro, qualquer que seja o
        comprimento. A contagem exata de DUAS ocorrências é conferida antes de
        qualquer troca, e o construtor estoura se não bater.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    alfabeto = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(membros) > len(alfabeto):
        raise ValueError("mais membros do que caracteres de marcador distintos")

    marcadores = []
    with zipfile.ZipFile(caminho, "w") as z:
        for indice, (nome_cru, dados) in enumerate(membros):
            if not nome_cru:
                raise ValueError("nome vazio")
            marcador = bytes([alfabeto[indice]]) * len(nome_cru)
            if marcador in dados:
                raise ValueError("o marcador aparece no conteúdo — trocaria bytes de dados")
            marcadores.append((marcador, nome_cru))
            z.writestr(zipfile.ZipInfo(marcador.decode("ascii"), date_time=DATA_HORA_FIXA),
                       dados)

    brutos = caminho.read_bytes()
    for marcador, nome_cru in marcadores:
        if brutos.count(marcador) != 2:
            raise ValueError("marcador %r aparece %d vezes, esperado 2 (cabeçalho local "
                             "e diretório central)" % (marcador, brutos.count(marcador)))
    for marcador, nome_cru in marcadores:
        brutos = brutos.replace(marcador, nome_cru)
    caminho.write_bytes(brutos)
    return caminho


def bit_utf8_de_cada_membro(caminho: Path) -> list[bool]:
    with zipfile.ZipFile(caminho) as z:
        return [bool(i.flag_bits & inv.BIT_UTF8_DO_INDICE) for i in z.infolist()]


def achados_de(registro: dict, tipo: str) -> list[dict]:
    return [a for a in registro["achados"] if a["tipo"] == tipo]


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 — O NOME DO MEMBRO
# ═══════════════════════════════════════════════════════════════════════════

# `especificação` e `anexo çãõ` são palavras GENÉRICAS do domínio. Não há aqui
# nome de arquivo real, município nem valor: se a correção precisasse deles,
# estaria errada por construção.
NOME_ACENTUADO = "especificação técnica.pdf"


def teste_1_o_defeito_real_construido_no_nivel_do_byte():
    print("\n--- (1) O DEFEITO REAL: bytes UTF-8 com o bit 0x800 DESLIGADO ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        crus = NOME_ACENTUADO.encode("utf-8")
        alvo = zip_com_bytes_crus_no_nome(pasta / "pacote.zip", [(crus, b"conteudo")])

        igual(bit_utf8_de_cada_membro(alvo), [False],
              "o bit 0x800 do índice está DESLIGADO — o defeito foi construído")
        with zipfile.ZipFile(alvo) as z:
            entregue = z.infolist()[0].filename
        igual(entregue, "especifica├º├úo t├⌐cnica.pdf",
              "e o `zipfile` do Python entrega o nome decodificado como cp437")

        registro = inv.inventariar_edital(l, raiz)
        membros = [a for a in registro["arquivos"]
                   if a["onde_estava"] == inv.ONDE_NO_CONTAINER]
        igual(len(membros), 1, "há um membro dentro do container")
        igual(membros[0]["caminho"], NOME_ACENTUADO,
              "o inventário gravou o nome UTF-8 — a leitura cp437 é implausível, "
              "logo há UM único candidato")
        igual(membros[0]["extensao"], ".pdf",
              "e a extensão saiu do nome ADOTADO, não do descartado")

        achados = achados_de(registro, inv.ACHADO_ENCODING_NAO_DECLARADO)
        igual(len(achados), 1, "e o achado ENCODING_NOME_NAO_DECLARADO foi declarado")
        detalhe = achados[0]["detalhe"]
        checar("ADOTADA utf-8" in detalhe, "o achado diz qual leitura foi ADOTADA", detalhe)
        checar(NOME_ACENTUADO in detalhe, "e ela aparece escrita por extenso", detalhe)
        checar("DESCARTADA" in detalhe and "├º├ú" in detalhe,
               "e a leitura DESCARTADA também está lá, por extenso", detalhe)
        checar("desenho de caixa" in detalhe,
               "dizendo por qual faixa do filtro ela foi descartada", detalhe)


def teste_2_fixture_adversarial_duas_leituras_plausiveis():
    print("\n--- (2) A FIXTURE ADVERSARIAL: duas leituras plausíveis, sem escolha ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)

        # O SINAL DE EURO, U+20AC = E2 82 AC em UTF-8. É de TRÊS bytes, e é aí
        # que mora o vão: o líder 0xE2 vira Γ (grego) em cp437, e não desenho de
        # caixa; os dois bytes de continuação viram é e ¼, ambos Latin-1. Nenhum
        # dos três cai numa faixa do filtro — então a leitura cp437 é plausível.
        # A leitura UTF-8 também é: '€' é símbolo de moeda, e moeda ocorre em
        # nome de arquivo. DUAS leituras plausíveis, com textos DIFERENTES.
        nome_utf8 = "anexo 1.000€.pdf"
        crus = nome_utf8.encode("utf-8")
        leitura_cp437 = crus.decode("cp437")
        igual(leitura_cp437, "anexo 1.000Γé¼.pdf", "a leitura cp437 destes bytes")
        igual(inv._implausibilidade(nome_utf8), None,
              "a leitura UTF-8 não cai em faixa nenhuma do filtro — é plausível")
        igual(inv._implausibilidade(leitura_cp437), None,
              "a leitura cp437 TAMBÉM não cai — é plausível também")
        checar(leitura_cp437 != nome_utf8, "e os dois textos são diferentes")

        alvo = zip_com_bytes_crus_no_nome(pasta / "pacote.zip", [(crus, b"conteudo")])
        igual(bit_utf8_de_cada_membro(alvo), [False], "o bit 0x800 está DESLIGADO")

        registro = inv.inventariar_edital(l, raiz)
        membros = [a for a in registro["arquivos"]
                   if a["onde_estava"] == inv.ONDE_NO_CONTAINER]
        igual(membros[0]["caminho"], leitura_cp437,
              "o `caminho` ficou na leitura cp437 — determinística, e a mesma que "
              "a versão anterior produzia")

        nenhum = achados_de(registro, inv.ACHADO_ENCODING_NAO_DECLARADO)
        igual(nenhum, [], "NENHUM achado de 'leitura única' — não houve escolha")
        achados = achados_de(registro, inv.ACHADO_ENCODING_AMBIGUO)
        igual(len(achados), 1, "o achado é ENCODING_NOME_AMBIGUO")
        detalhe = achados[0]["detalhe"]
        checar(nome_utf8 in detalhe, "as DUAS leituras estão preservadas: a UTF-8", detalhe)
        checar(leitura_cp437 in detalhe, "e a cp437", detalhe)
        checar("NÃO se afirma qual é o nome verdadeiro" in detalhe,
               "e o achado declara, com todas as letras, que NÃO afirma qual é o "
               "verdadeiro", detalhe)
        checar("ESTABILIDADE, NÃO de verdade" in detalhe,
               "dizendo que a escolha do `caminho` é de estabilidade", detalhe)
        for palavra in ("provavelmente", "deve ser", "o correto é", "o nome real"):
            checar(palavra not in detalhe.lower(),
                   f"e não contém {palavra!r} — nada de afirmação disfarçada")


def teste_3_bit_ligado_nada_muda():
    print("\n--- (3) bit LIGADO e nome acentuado: a correção é INERTE ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        alvo = pasta / "pacote.zip"
        with zipfile.ZipFile(alvo, "w") as z:
            z.writestr(zipfile.ZipInfo(NOME_ACENTUADO, date_time=DATA_HORA_FIXA), b"x")
        igual(bit_utf8_de_cada_membro(alvo), [True],
              "o `zipfile` LIGOU o bit sozinho, porque o nome não é ASCII")

        registro = inv.inventariar_edital(l, raiz)
        membros = [a for a in registro["arquivos"]
                   if a["onde_estava"] == inv.ONDE_NO_CONTAINER]
        igual(membros[0]["caminho"], NOME_ACENTUADO, "o nome sai inalterado")
        igual(achados_de(registro, inv.ACHADO_ENCODING_NAO_DECLARADO), [],
              "e NENHUM achado de codificação é declarado")
        igual(achados_de(registro, inv.ACHADO_ENCODING_AMBIGUO), [],
              "nem de ambiguidade — onde já estava certo, nada acontece")


def teste_4_ascii_com_bit_desligado_nada_muda():
    print("\n--- (4) nome ASCII com o bit desligado: nada a decidir ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        alvo = zip_com_bytes_crus_no_nome(
            pasta / "pacote.zip", [(b"edital_2026.pdf", b"x"), (b"anexo_1.docx", b"y")])
        igual(bit_utf8_de_cada_membro(alvo), [False, False], "os dois com o bit desligado")

        registro = inv.inventariar_edital(l, raiz)
        caminhos = sorted(a["caminho"] for a in registro["arquivos"]
                          if a["onde_estava"] == inv.ONDE_NO_CONTAINER)
        igual(caminhos, ["anexo_1.docx", "edital_2026.pdf"], "os nomes saem inalterados")
        igual(achados_de(registro, inv.ACHADO_ENCODING_NAO_DECLARADO), [], "nenhum achado")
        igual(achados_de(registro, inv.ACHADO_ENCODING_AMBIGUO), [], "nenhum achado")


def teste_5_bytes_que_nao_decodificam_como_utf8():
    print("\n--- (5) bytes que NÃO decodificam como UTF-8: caminho mantido, achado declarado ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)

        # 0xE9 sozinho é líder de sequência de três bytes sem as continuações:
        # UTF-8 inválido. Em cp437 é Θ (grego), que NÃO cai no filtro — então
        # sobra exatamente UM candidato plausível, o cp437.
        so_um = b"anexo \xe9.pdf"
        # 0xFE é UTF-8 inválido também, e em cp437 é ■ (formas geométricas), que
        # CAI no filtro — então não sobra candidato plausível nenhum.
        nenhum = b"anexo \xfe.pdf"
        alvo = zip_com_bytes_crus_no_nome(pasta / "pacote.zip",
                                          [(so_um, b"aaa"), (nenhum, b"bbb")])
        igual(bit_utf8_de_cada_membro(alvo), [False, False], "os dois com o bit desligado")

        registro = inv.inventariar_edital(l, raiz)
        por_caminho = {a["caminho"]: a for a in registro["arquivos"]
                       if a["onde_estava"] == inv.ONDE_NO_CONTAINER}

        igual(sorted(por_caminho), sorted([so_um.decode("cp437"), nenhum.decode("cp437")]),
              "os DOIS `caminho` ficaram na leitura cp437 — mantidos")

        a1 = achados_de(registro, inv.ACHADO_ENCODING_NAO_DECLARADO)
        igual(len(a1), 1, "o de leitura única vira um ENCODING_NOME_NAO_DECLARADO")
        checar("não decodifica como UTF-8" in a1[0]["detalhe"],
               "dizendo que a leitura UTF-8 nem existe", a1[0]["detalhe"])

        a2 = achados_de(registro, inv.ACHADO_ENCODING_AMBIGUO)
        igual(len(a2), 1, "e o sem candidato nenhum vira um ENCODING_NOME_AMBIGUO")
        checar("NENHUMA das leituras é plausível" in a2[0]["detalhe"],
               "declarando que nenhuma leitura é plausível", a2[0]["detalhe"])
        checar("formas geométricas" in a2[0]["detalhe"],
               "e nomeando a faixa que reprovou a cp437", a2[0]["detalhe"])


def teste_6_o_filtro_e_enumerado_no_codigo():
    print("\n--- (6) o filtro de plausibilidade é ENUMERADO, não julgado ---")
    faixas = inv.FAIXAS_IMPLAUSIVEIS_EM_NOME
    checar(isinstance(faixas, tuple) and len(faixas) >= 5,
           f"as faixas são uma tupla no código, com {len(faixas)} entradas")
    for inicio, fim, nome in faixas:
        print(f"      U+{inicio:04X}–U+{fim:04X}  {nome}")

    exigidas = [(0x2500, 0x257F), (0x2580, 0x259F), (0x25A0, 0x25FF),
                (0x2200, 0x22FF), (0x0000, 0x001F)]
    declaradas = [(i, f) for i, f, _ in faixas]
    for faixa in exigidas:
        checar(faixa in declaradas,
               f"a faixa mínima U+{faixa[0]:04X}–U+{faixa[1]:04X} está declarada")

    # A DECISÃO SAI DA TABELA: um ponto de cada faixa é reprovado, e o motivo
    # nomeia a própria faixa.
    for inicio, fim, nome in faixas:
        motivo = inv._implausibilidade(chr(inicio))
        checar(motivo is not None and nome in motivo,
               f"U+{inicio:04X} é reprovado, e o motivo nomeia {nome!r}", str(motivo))

    # E O QUE FICA DE FORA FICA DE FORA: grego é plausível, de propósito.
    for caractere in "αΓπΣΩ€ç漢":
        igual(inv._implausibilidade(caractere), None,
              f"{caractere!r} NÃO é reprovado — o filtro não é uma lista de "
              f"«tudo que não é ASCII»")

    # GENÉRICO: nada do caso conhecido no código.
    fonte = (RAIZ / "inventario.py").read_text(encoding="utf-8").lower()
    for proibido in ("licita+brasil", "comprovante_de_publica", "braganey", "conlic-19241283"):
        checar(proibido not in fonte,
               f"o código NÃO menciona {proibido!r} — a regra é genérica")


def teste_7_determinismo_nos_quatro_caminhos():
    print("\n--- (7) determinismo: a mesma fixture, duas vezes, byte a byte ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        # Um único container com os QUATRO caminhos de decisão dentro, mais o
        # bit ligado ao lado — para o determinismo ser medido em todos juntos.
        zip_com_bytes_crus_no_nome(pasta / "pacote.zip", [
            (b"ascii.pdf", b"a"),                                # nada a decidir
            (NOME_ACENTUADO.encode("utf-8"), b"b"),              # UM plausível
            ("anexo 1.000€.pdf".encode("utf-8"), b"c"),          # DOIS plausíveis
            (b"anexo \xfe.pdf", b"d"),                           # NENHUM plausível
        ])
        with zipfile.ZipFile(pasta / "declarado.zip", "w") as z:
            z.writestr(zipfile.ZipInfo(NOME_ACENTUADO, date_time=DATA_HORA_FIXA), b"e")

        primeira = json.dumps(inv.inventariar_edital(l, raiz), ensure_ascii=False,
                              indent=2, sort_keys=False)
        segunda = json.dumps(inv.inventariar_edital(l, raiz), ensure_ascii=False,
                             indent=2, sort_keys=False)
        igual(len(primeira.encode("utf-8")), len(segunda.encode("utf-8")),
              "as duas leituras têm o mesmo tamanho em bytes")
        checar(primeira == segunda,
               "e são IDÊNTICAS byte a byte, com os quatro caminhos de decisão dentro")

        registro = json.loads(primeira)
        tipos = sorted(a["tipo"] for a in registro["achados"]
                       if a["tipo"].startswith("ENCODING_"))
        igual(tipos, ["ENCODING_NOME_AMBIGUO", "ENCODING_NOME_AMBIGUO",
                      "ENCODING_NOME_NAO_DECLARADO"],
              "os três achados de codificação esperados saíram (o ASCII e o "
              "declarado não geram achado)")
        ordem = [a["detalhe"] for a in registro["achados"]]
        igual(ordem, sorted(ordem, key=lambda d: d), "e os achados saem ordenados")


# ═══════════════════════════════════════════════════════════════════════════
# §4.2 — `anomalia` PASSA A SIGNIFICAR «NÃO É ROTINA»
# ═══════════════════════════════════════════════════════════════════════════

def _montar_os_quatro_estados(raiz: Path) -> list[dict]:
    """Uma Agenda sintética com um edital em CADA um dos quatro estados."""
    com_arquivo = linha(cidade="Curitiba", numero="PE/1/2026", codigo="111", linha_agenda=2)
    (criar_pasta(raiz, com_arquivo) / "edital.pdf").write_bytes(b"x")

    vazia = linha(cidade="Maringa", numero="PE/2/2026", codigo="222", linha_agenda=3)
    criar_pasta(raiz, vazia)

    ausente = linha(cidade="Londrina", numero="PE/3/2026", codigo="333", linha_agenda=4)
    # de propósito, a pasta NÃO é criada

    ambigua = linha(cidade="Cascavel", numero="PE/4/2026", codigo="444", linha_agenda=5)
    cidade = raiz / convencao.nome_pasta_cidade(ambigua["cidade"], ambigua["uf"])
    (cidade / "PE 4-2026 - CONLIC-444").mkdir(parents=True)
    (cidade / "PE 9-2026 - CONLIC-444").mkdir(parents=True)

    return [com_arquivo, vazia, ausente, ambigua]


def teste_8_a_9_a_10_os_quatro_estados_um_a_um():
    print("\n--- (8)(9)(10) `anomalia` nos quatro estados, um a um ---")
    with Area() as raiz:
        linhas = _montar_os_quatro_estados(raiz)
        completo = inv.montar_inventario(linhas, raiz)
        por_codigo = {r["codigo_edital"]: r for r in completo["editais"]}

        esperado = {
            "CONLIC-111": (convencao.ESTADO_COM_ARQUIVO, False, "rotina"),
            "CONLIC-222": (convencao.ESTADO_VAZIA, False, "rotina"),
            "CONLIC-333": (convencao.ESTADO_AUSENTE, True, "anomalia"),
            "CONLIC-444": (convencao.ESTADO_AMBIGUA, True, "anomalia"),
        }
        for codigo, (estado, anomalia, natureza) in esperado.items():
            registro = por_codigo[codigo]
            igual(registro["estado_pasta"], estado, f"{codigo} está em {estado}")
            igual(registro["anomalia"], anomalia,
                  f"  e `anomalia` é {anomalia} — {estado} é {natureza}")

        # (8) o AMBIGUA continua trazendo AS DUAS pastas candidatas.
        ambigua = por_codigo["CONLIC-444"]
        achados = achados_de(ambigua, inv.ACHADO_AMBIGUIDADE)
        igual(len(achados), 1, "(8) o AMBIGUA continua declarando a ambiguidade")
        detalhe = achados[0]["detalhe"]
        checar("PE 4-2026 - CONLIC-444" in detalhe and "PE 9-2026 - CONLIC-444" in detalhe,
               "e o achado continua nomeando AS DUAS candidatas", detalhe)
        checar("nenhuma foi escolhida" in detalhe,
               "e continua dizendo que NENHUMA foi escolhida", detalhe)
        igual(ambigua["pasta_relativa"], None,
              "o fail-closed da D1 continua de pé: nenhuma pasta foi escolhida")
        igual(ambigua["arquivos"], [], "e nenhum arquivo foi atribuído a este edital")


def teste_11_o_total_fecha_com_a_contagem_por_estado():
    print("\n--- (11) o total de anomalias FECHA com a contagem por estado ---")
    with Area() as raiz:
        linhas = _montar_os_quatro_estados(raiz)
        totais = inv.montar_inventario(linhas, raiz)["totais"]

        checar("editais_com_anomalia" in totais,
               "o total se chama `editais_com_anomalia` — o nome diz o que ele mede")
        checar("editais_com_anomalia_pasta_ausente" not in totais,
               "e o nome antigo, que dizia UM estado e contava DOIS, não existe mais")

        por_estado = totais["editais_por_estado_da_pasta"]
        soma = sum(por_estado.get(e, 0) for e in inv.ESTADOS_DE_ANOMALIA)
        igual(totais["editais_com_anomalia"], soma,
              f"{totais['editais_com_anomalia']} = "
              f"{' + '.join(f'{e}:{por_estado.get(e, 0)}' for e in inv.ESTADOS_DE_ANOMALIA)}")
        igual(totais["editais_com_anomalia"], 2, "que aqui são 2 — um AUSENTE e um AMBIGUA")
        igual(sum(por_estado.values()), totais["editais_linhas_da_agenda"],
              "e os quatro estados continuam somando o denominador")

        rotina = sum(por_estado.get(e, 0) for e in inv.ESTADOS_DE_ROTINA)
        igual(rotina + totais["editais_com_anomalia"], totais["editais_linhas_da_agenda"],
              "rotina + anomalia = o denominador, sem sobra e sem falta")


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("FECHAMENTO — nome de membro de container (§4.1) e `anomalia` (§4.2)")
    print("=" * 70)
    for teste in (
        teste_1_o_defeito_real_construido_no_nivel_do_byte,
        teste_2_fixture_adversarial_duas_leituras_plausiveis,
        teste_3_bit_ligado_nada_muda,
        teste_4_ascii_com_bit_desligado_nada_muda,
        teste_5_bytes_que_nao_decodificam_como_utf8,
        teste_6_o_filtro_e_enumerado_no_codigo,
        teste_7_determinismo_nos_quatro_caminhos,
        teste_8_a_9_a_10_os_quatro_estados_um_a_um,
        teste_11_o_total_fecha_com_a_contagem_por_estado,
    ):
        teste()

    print("\n" + "=" * 70)
    if _falhas:
        print(f"RESULTADO (nome de membro e anomalia): {len(_falhas)} de {_total} FALHARAM")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"RESULTADO (nome de membro e anomalia): as {_total} provas passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
