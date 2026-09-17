# -*- coding: utf-8 -*-
r"""
SUÍTE DO INVENTARIADOR — sintética, em área temporária.

NUNCA TOCA EM `C:\Editais 2026`. Toda árvore usada aqui nasce num
`tempfile.mkdtemp()` e morre no fim do teste. A base real é lida, nesta rodada,
apenas pela medição de topologia e pela execução real — nunca por esta suíte.

Cobre o §6 do enunciado: pasta com um arquivo · pasta com vários PDFs · PDF +
DOCX + XLSX · subpasta · pasta vazia · pasta inexistente · arquivo de zero byte ·
nomes com espaços · nomes com acentos · mesmo nome em caminhos distintos ·
arquivos repetidos preservados como entradas distintas · ordem determinística ·
mesmo conjunto -> mesmo inventário · arquivo dentro de `.zip` · `.zip` vazio ·
`.zip` corrompido · adicionado/removido/alterado no diff · `schema_version`
presente · identidade do edital preservada · nenhum ID paralelo criado ·
nenhum arquivo inventariado é alterado · ambiguidade falha de modo fechado.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import convencao_edital as convencao  # noqa: E402
import diff_inventario  # noqa: E402
import inventario as inv  # noqa: E402

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

def linha(cidade="Curitiba", uf="PR", numero="PE/35/2026", codigo="19241283",
          linha_agenda=3):
    """Uma linha da Agenda no formato que `ler_linhas_agenda()` devolve."""
    return {
        "linha_agenda": linha_agenda,
        "cidade": cidade,
        "uf": uf,
        "numero_pregao": numero,
        "codigo_conlicitacao": codigo,
        "data_limite": "01/10/2026",
    }


def criar_pasta(raiz: Path, linha_agenda: dict) -> Path:
    """Cria a pasta do edital seguindo a convenção do Módulo 1."""
    pasta = raiz / convencao.chave_pasta_edital(linha_agenda)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


# Um instante FIXO para carimbar a metadata factual dos arquivos soltos quando
# o teste precisa que duas árvores tenham a MESMA metadata, e não só os mesmos
# bytes. 2026-09-14T18:31:01Z, o exemplo que a auditoria usou.
#
# Existe porque o contrato do §4.4 é sobre "mesma entrada lógica e mesmo
# conjunto de arquivos", e duas árvores criadas em momentos diferentes NÃO têm a
# mesma entrada lógica — têm mtimes diferentes, legitimamente. Carimbar é o que
# torna a comparação honesta: sem isso, a única saída seria mascarar o campo, e
# mascarar é justamente o que não prova nada.
#
# DERIVADO do instante, e não digitado: um número de época escrito à mão erra
# calado, e o teste passaria a provar outra data que não a declarada ao lado.
INSTANTE_UTC_FIXO = datetime(2026, 9, 14, 18, 31, 1, tzinfo=timezone.utc)
INSTANTE_FIXO = INSTANTE_UTC_FIXO.timestamp()
TEXTO_ESPERADO_SOLTO = "2026-09-14T18:31:01Z"


def escrever(caminho: Path, conteudo: bytes = b"conteudo",
             instante: float | None = None) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    if instante is not None:
        os.utime(caminho, (instante, instante))
    return caminho


# A data de um membro de .zip vem do ZipInfo, não do relógio: passar `data_hora`
# fixa a data factual gravada no índice, que é exatamente o que o Inventariador
# lê. Sem isso, dois zips criados em segundos diferentes trariam datas diferentes
# — diferença legítima, mas que não é o que o teste de determinismo mede.
DATA_HORA_FIXA_NO_ZIP = (2026, 9, 14, 18, 31, 0)


def criar_zip(caminho: Path, membros: list[tuple[str, bytes]],
              data_hora: tuple | None = None) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho, "w") as z:
        for nome, dados in membros:
            if data_hora is None:
                z.writestr(nome, dados)
            else:
                z.writestr(zipfile.ZipInfo(nome, date_time=data_hora), dados)
    return caminho


def arquivos_por_caminho(registro: dict) -> dict:
    return {(a["container"], a["caminho"]): a for a in registro["arquivos"]}


class Area:
    """Uma raiz de editais temporária, apagada no fim."""

    def __enter__(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="inventariador_teste_"))
        return self.raiz

    def __exit__(self, *args):
        shutil.rmtree(self.raiz, ignore_errors=True)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# ESTADO DA PASTA — dois estados são rotina (COM_ARQUIVO, VAZIA) e dois são
# anomalia (AUSENTE, AMBIGUA). O campo `anomalia` é essa distinção.
# ═══════════════════════════════════════════════════════════════════════════

def teste_pasta_inexistente_e_anomalia_e_nao_bloqueia():
    print("\n--- pasta inexistente: AUSENTE, com destaque, e a cadeia segue ---")
    with Area() as raiz:
        presente = linha(codigo="111", linha_agenda=3)
        sumida = linha(cidade="Maringá", codigo="222", linha_agenda=4)
        depois = linha(cidade="Londrina", codigo="333", linha_agenda=5)
        escrever(criar_pasta(raiz, presente) / "edital.pdf")
        criar_pasta(raiz, depois)

        completo = inv.montar_inventario([presente, sumida, depois], raiz)
        por_codigo = {r["codigo_edital"]: r for r in completo["editais"]}

        igual(por_codigo["CONLIC-222"]["estado_pasta"], convencao.ESTADO_AUSENTE,
              "a linha sem pasta em disco sai AUSENTE")
        checar(por_codigo["CONLIC-222"]["anomalia"] is True,
               "e AUSENTE é marcado como ANOMALIA")
        igual(por_codigo["CONLIC-222"]["arquivos"], [],
              "sem pasta não há arquivo a listar")

        igual(por_codigo["CONLIC-111"]["estado_pasta"], convencao.ESTADO_COM_ARQUIVO,
              "o edital ANTES do ausente foi inventariado")
        igual(por_codigo["CONLIC-333"]["estado_pasta"], convencao.ESTADO_VAZIA,
              "e o edital DEPOIS do ausente também — um AUSENTE não para os outros")
        igual(len(completo["editais"]), 3, "os três entraram no inventário")


def teste_pasta_vazia_e_rotina():
    print("\n--- pasta vazia: VAZIA, rotina, sem destaque ---")
    with Area() as raiz:
        l = linha()
        criar_pasta(raiz, l)
        registro = inv.inventariar_edital(l, raiz)
        igual(registro["estado_pasta"], convencao.ESTADO_VAZIA, "pasta sem arquivo sai VAZIA")
        checar(registro["anomalia"] is False, "VAZIA NÃO é anomalia — é o normal")
        igual(registro["arquivos"], [], "e não há arquivo nenhum")


def teste_pasta_so_com_resumo_do_m1_e_vazia_mas_lista_o_artefato():
    print("\n--- só resumo_edital.*: VAZIA, mas os artefatos do M1 ENTRAM marcados ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "resumo_edital.json", b"{}")
        escrever(pasta / "resumo_edital.docx")
        registro = inv.inventariar_edital(l, raiz)

        igual(registro["estado_pasta"], convencao.ESTADO_VAZIA,
              "resumo_edital.* não é arquivo do edital — a pasta continua VAZIA")
        igual(len(registro["arquivos"]), 2,
              "mas os dois artefatos ENTRAM no inventário (o M2 exclui; aqui se marca)")
        checar(all(a["artefato_do_m1"] for a in registro["arquivos"]),
               "e os dois vêm marcados como artefato do Módulo 1")


# ═══════════════════════════════════════════════════════════════════════════
# O QUE EXISTE NA PASTA — neutralidade quanto ao consumidor
# ═══════════════════════════════════════════════════════════════════════════

def teste_pasta_com_um_arquivo():
    print("\n--- pasta com UM arquivo ---")
    with Area() as raiz:
        l = linha()
        escrever(criar_pasta(raiz, l) / "edital.pdf", b"%PDF-1.4 fake")
        registro = inv.inventariar_edital(l, raiz)
        igual(registro["estado_pasta"], convencao.ESTADO_COM_ARQUIVO, "estado COM_ARQUIVO")
        igual(len(registro["arquivos"]), 1, "uma entrada")
        a = registro["arquivos"][0]
        igual(a["caminho"], "edital.pdf", "o caminho é relativo à pasta do edital")
        igual(a["extensao"], ".pdf", "a extensão vem do nome")
        igual(a["onde_estava"], inv.ONDE_SOLTO, "e ele estava SOLTO na pasta")
        igual(a["container"], None, "sem container")
        igual(a["tamanho_bytes"], len(b"%PDF-1.4 fake"), "o tamanho é o do sistema de arquivos")
        checar(len(a["modificado_em"]) == 20 and a["modificado_em"][10] == "T"
               and a["modificado_em"].endswith("Z"),
               "a data de arquivo SOLTO vem como instante UTC, AAAA-MM-DDTHH:MM:SSZ",
               a["modificado_em"])
        checar("sha256" not in json.dumps(registro).lower(),
               "NÃO há SHA-256 no inventário — o hash é de quem processa")


def teste_pasta_com_varios_pdfs():
    print("\n--- pasta com VÁRIOS PDFs ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        for nome in ("anexo_2.pdf", "anexo_1.pdf", "edital.pdf"):
            escrever(pasta / nome)
        registro = inv.inventariar_edital(l, raiz)
        igual([a["caminho"] for a in registro["arquivos"]],
              ["anexo_1.pdf", "anexo_2.pdf", "edital.pdf"],
              "os três entram, em ordem determinística por caminho")


def teste_pdf_docx_xlsx_entram_todos():
    print("\n--- PDF + DOCX + XLSX: lista tudo, não descarta nada ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "edital.pdf")
        escrever(pasta / "termo.docx")
        escrever(pasta / "planilha.xlsx")
        registro = inv.inventariar_edital(l, raiz)
        igual(sorted(a["extensao"] for a in registro["arquivos"]),
              [".docx", ".pdf", ".xlsx"],
              ".docx e .xlsx entram, mesmo que o consumidor de hoje só leia PDF")
        checar(not any(a["artefato_do_m1"] for a in registro["arquivos"]),
               "e nenhum deles é artefato do Módulo 1")


def teste_arquivo_de_zero_byte_entra():
    print("\n--- arquivo de ZERO BYTE entra, com tamanho zero ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "vazio.pdf", b"")
        escrever(pasta / "cheio.pdf", b"x")
        registro = inv.inventariar_edital(l, raiz)
        por_nome = {a["caminho"]: a for a in registro["arquivos"]}
        checar("vazio.pdf" in por_nome, "o arquivo de zero byte NÃO é fingido inexistente")
        igual(por_nome["vazio.pdf"]["tamanho_bytes"], 0, "e sai com tamanho zero")


def teste_nomes_com_espacos_e_acentos():
    print("\n--- nomes com espaços e com acentos ---")
    with Area() as raiz:
        l = linha(cidade="São José dos Pinhais", uf="pr", numero="PE/7/2026", codigo="99")
        pasta = criar_pasta(raiz, l)
        checar(pasta.parent.name == "SAO JOSE DOS PINHAIS - PR",
               "a pasta da cidade é sem acento e maiúscula", pasta.parent.name)
        escrever(pasta / "edital com espaço.pdf")
        escrever(pasta / "anexo — atenção.pdf")
        criar_zip(pasta / "pacote do edital.zip", [("anexo çãõ.pdf", b"x")])
        registro = inv.inventariar_edital(l, raiz)
        caminhos = [a["caminho"] for a in registro["arquivos"]]
        checar("edital com espaço.pdf" in caminhos, "nome com espaço preservado")
        checar("anexo — atenção.pdf" in caminhos, "nome com acento preservado")
        checar("anexo çãõ.pdf" in caminhos, "acento preservado também dentro do .zip")


def teste_mesmo_nome_em_caminhos_distintos_entra_duas_vezes():
    print("\n--- mesmo nome em caminhos distintos: DUAS entradas, sem deduplicar ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "edital.pdf", b"solto")
        criar_zip(pasta / "pacote_a.zip", [("edital.pdf", b"dentro de A")])
        criar_zip(pasta / "pacote_b.zip", [("edital.pdf", b"dentro de B, outro tamanho")])
        registro = inv.inventariar_edital(l, raiz)

        com_esse_nome = [a for a in registro["arquivos"] if a["caminho"] == "edital.pdf"]
        igual(len(com_esse_nome), 3,
              "três arquivos chamados edital.pdf entram como TRÊS entradas distintas")
        igual(sorted(a["container"] or "(solto)" for a in com_esse_nome),
              ["(solto)", "pacote_a.zip", "pacote_b.zip"],
              "e o que as distingue é o container de cada uma")
        checar(len({a["tamanho_bytes"] for a in com_esse_nome}) == 3,
               "os três têm tamanhos diferentes — nada foi colapsado")


def teste_arquivos_repetidos_identicos_preservados():
    print("\n--- arquivos repetidos IDÊNTICOS continuam sendo entradas distintas ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "pacote_a.zip", [("igual.pdf", b"mesmo conteudo")])
        criar_zip(pasta / "pacote_b.zip", [("igual.pdf", b"mesmo conteudo")])
        registro = inv.inventariar_edital(l, raiz)
        iguais = [a for a in registro["arquivos"] if a["caminho"] == "igual.pdf"]
        igual(len(iguais), 2, "dois membros idênticos em containers diferentes = duas entradas")


# ═══════════════════════════════════════════════════════════════════════════
# CONTAINERS
# ═══════════════════════════════════════════════════════════════════════════

def teste_arquivo_dentro_de_zip():
    print("\n--- arquivo dentro de .zip: lido pelo ÍNDICE, sem descomprimir ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "pacote.zip", [("edital.pdf", b"x" * 100),
                                         ("anexo.docx", b"y" * 50)])
        registro = inv.inventariar_edital(l, raiz)
        por = arquivos_por_caminho(registro)

        checar((None, "pacote.zip") in por, "o próprio .zip entra como arquivo solto")
        checar(("pacote.zip", "edital.pdf") in por, "e o membro entra marcado com o container")
        igual(por[("pacote.zip", "edital.pdf")]["onde_estava"], inv.ONDE_NO_CONTAINER,
              "onde_estava diz DENTRO_DO_CONTAINER")
        igual(por[("pacote.zip", "edital.pdf")]["tamanho_bytes"], 100,
              "o tamanho vem do índice do .zip (tamanho descomprimido)")
        igual(por[("pacote.zip", "anexo.docx")]["extensao"], ".docx",
              ".docx dentro do zip entra igual")


def teste_zip_vazio():
    print("\n--- .zip vazio ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "vazio.zip", [])
        registro = inv.inventariar_edital(l, raiz)
        igual(registro["estado_pasta"], convencao.ESTADO_COM_ARQUIVO,
              "um .zip solto já faz a pasta ser COM_ARQUIVO, mesmo vazio por dentro")
        igual(len(registro["arquivos"]), 1, "só o próprio .zip entra — ele não tem membro")
        igual(registro["achados"], [], "e um zip vazio não é achado nenhum")


def teste_zip_corrompido_nao_bloqueia():
    print("\n--- .zip corrompido: declarado não inventariável, e a cadeia segue ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "quebrado.zip", b"isto nao e um zip")
        criar_zip(pasta / "bom.zip", [("edital.pdf", b"x")])
        registro = inv.inventariar_edital(l, raiz)

        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_CONTAINER_ILEGIVEL in tipos,
               "o container ilegível é DECLARADO")
        por = arquivos_por_caminho(registro)
        checar((None, "quebrado.zip") in por,
               "o arquivo corrompido continua no inventário, como arquivo solto")
        checar(("bom.zip", "edital.pdf") in por,
               "e o OUTRO container foi inventariado normalmente — não bloqueou")


def teste_todos_os_zips_sao_abertos():
    print("\n--- TODOS os .zip da pasta são abertos, não só o primeiro ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "a.zip", [("de_a.pdf", b"x")])
        criar_zip(pasta / "b.zip", [("de_b.pdf", b"y")])
        criar_zip(pasta / "c.zip", [("de_c.pdf", b"z")])
        registro = inv.inventariar_edital(l, raiz)
        caminhos = {a["caminho"] for a in registro["arquivos"]}
        checar({"de_a.pdf", "de_b.pdf", "de_c.pdf"} <= caminhos,
               "o conteúdo dos três containers aparece "
               "(o listar_arquivos_edital do M2 abriria só o primeiro)")
        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_MAIS_DE_UM_CONTAINER in tipos,
               "e a pasta com mais de um container é declarada")


def teste_zip_aninhado_e_declarado_e_nao_aberto():
    print("\n--- zip dentro de zip: DECLARADO e NÃO aberto (não desce mais de um nível) ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        interno = Path(tempfile.mkdtemp()) / "interno.zip"
        criar_zip(interno, [("escondido.pdf", b"nao deve aparecer")])
        criar_zip(pasta / "externo.zip", [("interno.zip", interno.read_bytes()),
                                          ("visivel.pdf", b"x")])
        shutil.rmtree(interno.parent, ignore_errors=True)

        registro = inv.inventariar_edital(l, raiz)
        caminhos = {a["caminho"] for a in registro["arquivos"]}
        checar("interno.zip" in caminhos, "o zip aninhado ENTRA como arquivo")
        checar("escondido.pdf" not in caminhos,
               "mas o que está DENTRO dele NÃO é inventariado — sem regra escrita, não se desce")
        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_CONTAINER_ANINHADO in tipos, "e o aninhamento é DECLARADO")


def teste_subpasta_na_pasta_do_edital():
    print("\n--- subpasta na pasta do edital: DECLARADA e NÃO percorrida ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "edital.pdf")
        escrever(pasta / "anexos" / "escondido.pdf")
        registro = inv.inventariar_edital(l, raiz)

        caminhos = {a["caminho"] for a in registro["arquivos"]}
        checar("edital.pdf" in caminhos, "o arquivo do primeiro nível entra")
        checar("escondido.pdf" not in caminhos,
               "o de dentro da subpasta NÃO entra — não se desce sem regra escrita")
        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_SUBPASTA_NA_PASTA in tipos, "e a subpasta é DECLARADA")


def teste_subpasta_dentro_do_zip():
    print("\n--- subpasta DENTRO do .zip: o índice já dá o caminho, e o achado é declarado ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "pacote.zip", [("sub/edital.pdf", b"x"), ("raiz.pdf", b"y")])
        registro = inv.inventariar_edital(l, raiz)
        caminhos = {a["caminho"] for a in registro["arquivos"]}
        checar("sub/edital.pdf" in caminhos,
               "o membro em subpasta entra com o caminho INTEIRO que o índice dá")
        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_SUBPASTA_NO_CONTAINER in tipos, "e o achado é declarado")


# ═══════════════════════════════════════════════════════════════════════════
# FAIL-CLOSED
# ═══════════════════════════════════════════════════════════════════════════

def teste_ambiguidade_falha_de_modo_fechado():
    print("\n--- duas pastas candidatas: registra a ambiguidade e NÃO escolhe ---")
    with Area() as raiz:
        l = linha(numero="PE/35/2026", codigo="19241283")
        pasta_cidade = raiz / convencao.nome_pasta_cidade(l["cidade"], l["uf"])
        (pasta_cidade / "PE 35-2026 - CONLIC-19241283").mkdir(parents=True)
        (pasta_cidade / "PE 36-2026 - CONLIC-19241283").mkdir(parents=True)
        escrever(pasta_cidade / "PE 35-2026 - CONLIC-19241283" / "edital.pdf")
        escrever(pasta_cidade / "PE 36-2026 - CONLIC-19241283" / "outro.pdf")

        registro = inv.inventariar_edital(l, raiz)
        igual(registro["estado_pasta"], convencao.ESTADO_AMBIGUA,
              "o estado é AMBIGUA — ausência declarada é melhor que associação errada")
        # AMBIGUA É ANOMALIA. Ficou marcado como rotina desde a D1, porque o
        # enunciado daquela rodada definiu a palavra em cima de VAZIA/AUSENTE e
        # não voltou para incluir este estado, que entrou por outro parágrafo.
        # A asserção mora AQUI, colada no teste que constrói a ambiguidade, para
        # que uma regressão não precise de suíte nova para ser vista.
        checar(registro["anomalia"] is True,
               "e AMBIGUA É ANOMALIA — é o mais grave dos quatro estados: não é "
               "«a pasta sumiu», é «NÃO SE SABE qual pasta é a deste edital»")
        igual(registro["pasta_relativa"], None, "NENHUMA pasta foi escolhida")
        igual(registro["arquivos"], [], "e nenhum arquivo foi atribuído a este edital")
        tipos = [a["tipo"] for a in registro["achados"]]
        checar(inv.ACHADO_AMBIGUIDADE in tipos, "a ambiguidade é registrada")
        detalhe = registro["achados"][0]["detalhe"]
        checar("PE 35-2026 - CONLIC-19241283" in detalhe
               and "PE 36-2026 - CONLIC-19241283" in detalhe,
               "e o achado nomeia as duas candidatas", detalhe)


def teste_pasta_de_outro_codigo_nao_e_aceita():
    print("\n--- fail-closed de identidade: cidade e número batem, código não ---")
    with Area() as raiz:
        certa = linha(numero="PE/35/2026", codigo="19241283")
        outra = linha(numero="PE/35/2026", codigo="19339001")
        escrever(criar_pasta(raiz, certa) / "edital.pdf")

        registro = inv.inventariar_edital(outra, raiz)
        igual(registro["estado_pasta"], convencao.ESTADO_AUSENTE,
              "uma pasta cujo nome não termina NESTE código não é aceita como sendo dele")


# ═══════════════════════════════════════════════════════════════════════════
# IDENTIDADE E CONTRATO
# ═══════════════════════════════════════════════════════════════════════════

def teste_schema_version_presente():
    print("\n--- schema_version presente no inventário ---")
    with Area() as raiz:
        completo = inv.montar_inventario([linha()], raiz)
        checar("schema_version" in completo, "o inventário declara schema_version")
        igual(completo["schema_version"], inv.SCHEMA_VERSION, "e é a versão do contrato")
        checar("contrato" in completo, "e traz o contrato descrito junto")


def teste_identidade_preservada_e_sem_id_paralelo():
    print("\n--- identidade do edital preservada; NENHUM ID paralelo criado ---")
    with Area() as raiz:
        l = linha(codigo="19241283")
        criar_pasta(raiz, l)
        registro = inv.inventariar_edital(l, raiz)
        igual(registro["codigo_edital"], "CONLIC-19241283",
              "a identidade é o código existente, no formato do Módulo 1")
        igual(registro["codigo_conlicitacao"], "19241283",
              "o código cru da Agenda viaja junto, sem transformação")

        texto = json.dumps(inv.montar_inventario([l], raiz))
        for proibido in ("uuid", "guid", "id_interno", "id_proprio", "inventario_id"):
            checar(proibido not in texto.lower(), f"nenhum campo {proibido!r} foi criado")

    with Area() as raiz:
        sem = linha(codigo="")
        criar_pasta(raiz, sem)
        registro = inv.inventariar_edital(sem, raiz)
        igual(registro["codigo_edital"], "CONLIC-SEM-CODIGO",
              "sem código na Agenda, a identidade é a que o Módulo 1 dá à pasta — "
              "e continua não sendo um ID inventado")
        igual(registro["estado_pasta"], convencao.ESTADO_VAZIA,
              "e a pasta 'CONLIC-SEM-CODIGO' é encontrada normalmente")


def teste_ordem_deterministica_e_mesmo_conjunto_mesmo_inventario():
    """
    Mesma entrada lógica -> mesmo inventário, BYTE A BYTE, com `modificado_em`
    dentro da comparação.

    A versão anterior deste teste substituía `modificado_em` por "(ignorado)"
    antes de comparar — e, por isso, NÃO provava o contrato que dizia provar. A
    auditoria independente apontou exatamente isso, e foi o que bloqueou a D1.

    O jeito certo não é mascarar o campo: é fazer as duas árvores terem de fato
    a MESMA metadata factual, com `os.utime()` e com a data fixa no índice do
    ZIP. Aí a comparação pode ser total, e é.
    """
    print("\n--- determinismo: mesmo conjunto -> MESMO inventário, byte a byte ---")
    linhas = [linha(cidade="Zebra", codigo="999", linha_agenda=10),
              linha(cidade="Abelha", codigo="111", linha_agenda=5),
              linha(cidade="Meio", codigo="555", linha_agenda=7)]

    def montar_em(raiz, ordem):
        for l in linhas:
            pasta = criar_pasta(raiz, l)
            for nome in ordem:
                escrever(pasta / nome, nome.encode(), instante=INSTANTE_FIXO)
            criar_zip(pasta / "pacote.zip", [(n, n.encode()) for n in ordem],
                      data_hora=DATA_HORA_FIXA_NO_ZIP)
            os.utime(pasta / "pacote.zip", (INSTANTE_FIXO, INSTANTE_FIXO))
        return inv.montar_inventario(list(reversed(linhas)), raiz)

    def serializar(documento):
        return json.dumps(documento, ensure_ascii=False, indent=2)

    with Area() as raiz_a, Area() as raiz_b:
        a = montar_em(raiz_a, ["c.pdf", "a.pdf", "b.pdf"])
        b = montar_em(raiz_b, ["b.pdf", "c.pdf", "a.pdf"])

        checar(all(x["modificado_em"] for r in a["editais"] for x in r["arquivos"]),
               "toda entrada tem `modificado_em` preenchido — nada foi removido")
        igual(serializar(a), serializar(b),
              "duas árvores com a mesma entrada lógica dão o MESMO inventário, "
              "byte a byte, COM `modificado_em` na comparação")

        igual([r["codigo_edital"] for r in a["editais"]],
              ["CONLIC-111", "CONLIC-555", "CONLIC-999"],
              "os editais saem ordenados pelo código, não pela ordem de entrada")
        igual([x["caminho"] for x in a["editais"][0]["arquivos"]],
              ["a.pdf", "b.pdf", "c.pdf", "pacote.zip", "a.pdf", "b.pdf", "c.pdf"],
              "e os arquivos saem soltos primeiro, depois os do container, "
              "cada grupo em ordem de caminho")


def teste_as_duas_familias_de_data():
    """
    Arquivo solto leva "Z" (instante UTC); membro de ZIP não leva (hora de
    parede sem fuso, como o índice a registra). A distinção é 1:1 com
    `onde_estava`, e nenhum campo novo foi criado para carregá-la.
    """
    print("\n--- as duas famílias de data, e o que cada uma significa ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "solto.pdf", b"x", instante=INSTANTE_FIXO)
        criar_zip(pasta / "pacote.zip", [("dentro.pdf", b"y")],
                  data_hora=DATA_HORA_FIXA_NO_ZIP)
        registro = inv.inventariar_edital(l, raiz)
        por = arquivos_por_caminho(registro)

        solto = por[(None, "solto.pdf")]
        dentro = por[("pacote.zip", "dentro.pdf")]

        igual(solto["modificado_em"], TEXTO_ESPERADO_SOLTO,
              "o arquivo solto sai como INSTANTE UTC, com Z")
        igual(dentro["modificado_em"], "2026-09-14T18:31:00",
              "o membro do ZIP sai como a data do índice, SEM Z e sem conversão")
        checar(solto["onde_estava"] == inv.ONDE_SOLTO and solto["modificado_em"].endswith("Z"),
               "a marca Z é 1:1 com onde_estava=SOLTO_NA_PASTA")
        checar(dentro["onde_estava"] == inv.ONDE_NO_CONTAINER
               and not dentro["modificado_em"].endswith("Z"),
               "e a ausência dela é 1:1 com onde_estava=DENTRO_DO_CONTAINER")
        checar("modificado_em" in inv.montar_inventario([l], raiz)["contrato"],
               "e o contrato publicado no inventário explica as duas semânticas")


def teste_diff_recusa_comparar_schemas_diferentes():
    """
    A migração: um inventário de outro `schema_version` NÃO é comparado, e o
    diff sai declarado sem base — pelo mesmo caminho do «não há anterior».
    """
    print("\n--- diff entre schemas diferentes: recusa, e declara ---")
    with Area() as raiz:
        l = linha()
        escrever(criar_pasta(raiz, l) / "edital.pdf", b"x", instante=INSTANTE_FIXO)
        atual = inv.montar_inventario([l], raiz)

        antigo = json.loads(json.dumps(atual))
        antigo["schema_version"] = "1.0.0"
        # Como era na versão antiga: hora local, sem Z.
        for registro in antigo["editais"]:
            for arquivo in registro["arquivos"]:
                arquivo["modificado_em"] = "2026-09-14T15:31:01"

        d = diff_inventario.comparar(antigo, atual)
        checar(d["sem_base_de_comparacao"] is True,
               "o diff declara que não há base comparável")
        igual(d["schema_version_anterior"], "1.0.0", "e diz de qual versão era o anterior")
        igual(d["schema_version_atual"], inv.SCHEMA_VERSION, "e de qual é o atual")
        checar("schema" in d["motivo"].lower(), "o motivo nomeia a mudança de schema", d["motivo"])
        igual(d["arquivos"], [], "nenhuma linha de arquivo é emitida")
        igual(d["totais"], {"ADICIONADO": 0, "REMOVIDO": 0, "ALTERADO": 0, "INALTERADO": 0},
              "e os quatro totais são zero — nenhum ALTERADO em massa")

        # E a prova de que a recusa está fazendo trabalho de verdade: com o
        # schema forçado para igual, a MESMA dupla produziria ALTERADO.
        forcado = json.loads(json.dumps(antigo))
        forcado["schema_version"] = inv.SCHEMA_VERSION
        sem_guarda = diff_inventario.comparar(forcado, atual)
        checar(sem_guarda["totais"]["ALTERADO"] > 0,
               "sem a guarda, a mesma dupla acusaria ALTERADO — é isso que ela evita",
               str(sem_guarda["totais"]))
        igual([x["campos_diferentes"] for x in sem_guarda["arquivos"]],
              [["modificado_em"]],
              "e o campo acusado seria exatamente `modificado_em`")


def teste_nenhum_arquivo_inventariado_e_alterado():
    print("\n--- nada do que foi inventariado muda: nem bytes, nem data ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "edital.pdf", b"conteudo original")
        escrever(pasta / "resumo_edital.json", b"{}")
        criar_zip(pasta / "pacote.zip", [("anexo.pdf", b"dentro")])
        escrever(pasta / "quebrado.zip", b"nao e zip")
        escrever(pasta / "sub" / "escondido.pdf", b"fundo")

        def retrato():
            saida = {}
            for caminho in sorted(pasta.rglob("*")):
                if caminho.is_file():
                    st = caminho.stat()
                    saida[str(caminho.relative_to(pasta))] = (
                        st.st_size, st.st_mtime_ns, caminho.read_bytes())
            return saida

        antes = retrato()
        inv.inventariar_edital(l, raiz)
        inv.inventariar_edital(l, raiz)
        depois = retrato()

        igual(sorted(depois), sorted(antes), "nenhum arquivo foi criado nem apagado")
        checar(antes == depois,
               "e nenhum teve bytes, tamanho ou data de modificação alterados")


# ═══════════════════════════════════════════════════════════════════════════
# DIFF — e ele NÃO é fila
# ═══════════════════════════════════════════════════════════════════════════

def teste_diff_adicionado_removido_alterado_inalterado():
    print("\n--- diff: ADICIONADO · REMOVIDO · ALTERADO · INALTERADO ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        escrever(pasta / "fica_igual.pdf", b"xxx")
        escrever(pasta / "vai_sumir.pdf", b"yyy")
        escrever(pasta / "vai_mudar.pdf", b"zzz")
        antes = inv.montar_inventario([l], raiz)

        os.remove(pasta / "vai_sumir.pdf")
        escrever(pasta / "vai_mudar.pdf", b"zzz MUITO maior agora")
        escrever(pasta / "nasceu.pdf", b"novo")
        agora = inv.montar_inventario([l], raiz)

        d = diff_inventario.comparar(antes, agora)
        por_caminho = {x["caminho"]: x for x in d["arquivos"]}
        igual(por_caminho["nasceu.pdf"]["situacao"], diff_inventario.ADICIONADO, "ADICIONADO")
        igual(por_caminho["vai_sumir.pdf"]["situacao"], diff_inventario.REMOVIDO, "REMOVIDO")
        igual(por_caminho["vai_mudar.pdf"]["situacao"], diff_inventario.ALTERADO, "ALTERADO")
        igual(por_caminho["fica_igual.pdf"]["situacao"], diff_inventario.INALTERADO, "INALTERADO")
        checar("tamanho_bytes" in por_caminho["vai_mudar.pdf"]["campos_diferentes"],
               "e o ALTERADO diz QUAL campo mudou")
        igual(d["totais"], {"ADICIONADO": 1, "REMOVIDO": 1, "ALTERADO": 1, "INALTERADO": 1},
              "os quatro totais somam os quatro arquivos")


def teste_diff_identidade_nao_e_o_nome_sozinho():
    print("\n--- a identidade do diff é (edital, container, caminho) — não o nome ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        criar_zip(pasta / "a.zip", [("igual.pdf", b"x" * 10)])
        criar_zip(pasta / "b.zip", [("igual.pdf", b"x" * 10)])
        antes = inv.montar_inventario([l], raiz)

        os.remove(pasta / "b.zip")
        criar_zip(pasta / "b.zip", [("igual.pdf", b"x" * 999)])
        agora = inv.montar_inventario([l], raiz)

        d = diff_inventario.comparar(antes, agora)
        membros = [x for x in d["arquivos"] if x["caminho"] == "igual.pdf"]
        igual(len(membros), 2, "os dois membros homônimos são comparados SEPARADAMENTE")
        por_container = {x["container"]: x["situacao"] for x in membros}
        igual(por_container["a.zip"], diff_inventario.INALTERADO,
              "o do container A não mudou")
        igual(por_container["b.zip"], diff_inventario.ALTERADO,
              "e o do container B mudou — comparar pelo nome sozinho esconderia isso")
        igual(d["identidade_comparada"], "(codigo_edital, container, caminho)",
              "e a identidade está declarada no próprio diff")


def teste_diff_sem_base_nao_fabrica_base():
    print("\n--- sem inventário anterior: nada é declarado ADICIONADO ---")
    with Area() as raiz:
        l = linha()
        escrever(criar_pasta(raiz, l) / "edital.pdf")
        d = diff_inventario.comparar(None, inv.montar_inventario([l], raiz))
        checar(d["sem_base_de_comparacao"] is True, "o diff declara que não tem base")
        igual(d["arquivos"], [], "e não inventa um ADICIONADO por arquivo existente")
        igual(d["totais"]["ADICIONADO"], 0, "o total de ADICIONADO é zero")


def teste_diff_declara_que_nao_e_fila():
    print("\n--- o diff declara, no próprio corpo, que NÃO é fila ---")
    with Area() as raiz:
        l = linha()
        criar_pasta(raiz, l)
        for d in (diff_inventario.comparar(None, inv.montar_inventario([l], raiz)),
                  diff_inventario.comparar(inv.montar_inventario([l], raiz),
                                           inv.montar_inventario([l], raiz))):
            checar("nao_e_fila" in d, "o campo nao_e_fila existe")
            checar("NUNCA" in d["nao_e_fila"] and "processar" in d["nao_e_fila"],
                   "e diz que o diff nunca responde o que falta processar")
        texto = json.dumps(diff_inventario.comparar(None, inv.montar_inventario([l], raiz)))
        for proibido in ("pendente", "fila", "processados", "tentativas"):
            checar(f'"{proibido}"' not in texto.lower(),
                   f"não há campo {proibido!r} no diff")


def teste_diff_mudanca_de_estado_da_pasta():
    print("\n--- o diff também mostra o edital que mudou de ESTADO ---")
    with Area() as raiz:
        l = linha()
        pasta = criar_pasta(raiz, l)
        antes = inv.montar_inventario([l], raiz)
        escrever(pasta / "edital.pdf")
        agora = inv.montar_inventario([l], raiz)
        d = diff_inventario.comparar(antes, agora)
        igual(d["editais_que_mudaram_de_estado"],
              [{"codigo_edital": "CONLIC-19241283",
                "estado_antes": convencao.ESTADO_VAZIA,
                "estado_agora": convencao.ESTADO_COM_ARQUIVO}],
              "de VAZIA para COM_ARQUIVO, declarado")


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("INVENTARIADOR — suíte sintética")
    print("=" * 70)
    for teste in (
        teste_pasta_inexistente_e_anomalia_e_nao_bloqueia,
        teste_pasta_vazia_e_rotina,
        teste_pasta_so_com_resumo_do_m1_e_vazia_mas_lista_o_artefato,
        teste_pasta_com_um_arquivo,
        teste_pasta_com_varios_pdfs,
        teste_pdf_docx_xlsx_entram_todos,
        teste_arquivo_de_zero_byte_entra,
        teste_nomes_com_espacos_e_acentos,
        teste_mesmo_nome_em_caminhos_distintos_entra_duas_vezes,
        teste_arquivos_repetidos_identicos_preservados,
        teste_arquivo_dentro_de_zip,
        teste_zip_vazio,
        teste_zip_corrompido_nao_bloqueia,
        teste_todos_os_zips_sao_abertos,
        teste_zip_aninhado_e_declarado_e_nao_aberto,
        teste_subpasta_na_pasta_do_edital,
        teste_subpasta_dentro_do_zip,
        teste_ambiguidade_falha_de_modo_fechado,
        teste_pasta_de_outro_codigo_nao_e_aceita,
        teste_schema_version_presente,
        teste_identidade_preservada_e_sem_id_paralelo,
        teste_ordem_deterministica_e_mesmo_conjunto_mesmo_inventario,
        teste_as_duas_familias_de_data,
        teste_diff_recusa_comparar_schemas_diferentes,
        teste_nenhum_arquivo_inventariado_e_alterado,
        teste_diff_adicionado_removido_alterado_inalterado,
        teste_diff_identidade_nao_e_o_nome_sozinho,
        teste_diff_sem_base_nao_fabrica_base,
        teste_diff_declara_que_nao_e_fila,
        teste_diff_mudanca_de_estado_da_pasta,
    ):
        teste()

    print("\n" + "=" * 70)
    if _falhas:
        print(f"RESULTADO (suíte sintética): {len(_falhas)} de {_total} provas FALHARAM")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"RESULTADO (suíte sintética): as {_total} provas passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
