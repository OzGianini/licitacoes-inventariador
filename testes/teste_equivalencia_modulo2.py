# -*- coding: utf-8 -*-
r"""
A PROTEÇÃO CONTRA A CÓPIA QUE ENVELHECE — §4.3 do enunciado.

Roda a implementação do INVENTARIADOR e a do MÓDULO 2 sobre as MESMAS linhas da
Agenda e sobre a MESMA árvore de pastas, e exige resultado IDÊNTICO. Divergindo,
esta suíte quebra.

POR QUE ELA EXISTE
    `inventariador/convencao_edital.py` é cópia de `modulo2/utils.py`. Duas
    cópias da mesma regra é risco MEDIDO neste código — a docstring de
    `nome_pasta_edital()` no Módulo 2 registra o acidente:

        «era repetida em analisador.caminho_saida_edital() e em
         analisador._chave_pasta(), e a segunda cópia ficou para trás na Etapa
         2A (montava a convenção ANTIGA, sem o código)»

    Custa pouco, e é a única coisa que impede a cópia nova de envelhecer em
    silêncio.

O MÓDULO 2 NÃO É ALTERADO POR ESTA SUÍTE
    Ela IMPORTA `modulo2/config.py` e `modulo2/utils.py` e os usa em modo
    leitura, contra uma árvore temporária e uma Agenda temporária apontadas por
    variáveis de ambiente. Nada do Módulo 2 é escrito, e nada em `C:\Editais
    2026` é tocado.

    Roda obrigatoriamente com `python -B` / `PYTHONDONTWRITEBYTECODE=1`, e o
    próprio arquivo liga `sys.dont_write_bytecode` antes do primeiro import:
    importar o Módulo 2 sem isso deixaria `.pyc` novo no repositório dele.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

# ANTES de qualquer import de módulo do projeto: nenhum .pyc nasce por causa
# desta suíte, nem aqui nem no repositório do Módulo 2.
sys.dont_write_bytecode = True

RAIZ = Path(__file__).resolve().parent.parent
MODULO2 = Path(r"C:\licitacoes\modulo2")
sys.path.insert(0, str(RAIZ))

import openpyxl  # noqa: E402

import agenda as agenda_inventariador  # noqa: E402
import convencao_edital as convencao  # noqa: E402

_falhas = []
_total = 0


def checar(condicao, descricao, detalhe=""):
    global _total
    _total += 1
    if condicao:
        print(f"  [x] {descricao}")
    else:
        print(f"  [ ] FALHOU: {descricao}" + (f" - {detalhe}" if detalhe else ""))
        _falhas.append(descricao)


def igual(obtido, esperado, descricao):
    checar(obtido == esperado, descricao, f"inventariador={obtido!r} modulo2={esperado!r}")


# ═══════════════════════════════════════════════════════════════════════════
# OS CASOS — as linhas sobre as quais as DUAS implementações rodam
# ═══════════════════════════════════════════════════════════════════════════
#
# Cada caso é (cidade, uf, numero_pregao, codigo). Estão aqui as bordas que
# separam as duas convenções: acento, caixa, espaço sobrando, barra no número,
# código vazio, código como número, cidade sem UF.
CASOS = [
    ("Curitiba", "PR", "PE/35/2026", "19241283"),
    ("Maringá", "PR", "PE 40-2026", "19339001"),
    ("São José dos Pinhais", "pr", "DL/17/2026", "19241284"),
    ("  Ivaí  ", "PR", "  PE/7/2026  ", "  19241285  "),
    ("Ponte Branca", "MT", "PE 1-2026", ""),
    ("Campo Grande", "ms", "PE 094-2026", "19333040"),
    ("Cascavel", "PR", "PE/55/2026", 19298481),
    ("Foz do Iguaçu", "PR", "PR-14-2026", "19300227"),
    ("Água Clara", "MS", "PE/42/2026", "19290460"),
    ("São João do Triunfo", "PR", "DL/23/2026", "19332780"),
    ("Ubiratã", "PR", "PE/9/2026", "0"),
    ("Xambrê", "PR", "CC/1/2026", "19000000"),
]

# O que cada pasta sintética recebe, para os estados cobrirem os três casos.
CONTEUDO = {
    0: ["edital.zip"],                      # COM_ARQUIVO por .zip
    1: ["edital.pdf"],                      # COM_ARQUIVO por .pdf
    2: [],                                  # VAZIA
    3: ["resumo_edital.json"],              # VAZIA — resumo não conta
    4: ["edital.docx", "planilha.xlsx"],    # VAZIA — nem .docx nem .xlsx contam
    5: None,                                # pasta NÃO criada -> AUSENTE
    6: ["edital.zip", "anexo.pdf", "resumo_edital.docx"],
    7: None,
    8: ["a.zip", "b.zip"],
    9: ["edital.PDF"],                      # extensão em MAIÚSCULA
    10: [],
    11: ["vazio.pdf"],
}


def linha_de(caso, numero_da_linha):
    cidade, uf, numero, codigo = caso
    return {
        "linha_agenda": numero_da_linha,
        "cidade": str(cidade).strip(),
        "uf": str(uf).strip(),
        "numero_pregao": str(numero).strip(),
        "codigo_conlicitacao": convencao.texto_codigo(codigo),
        "data_limite": "",
    }


def montar_arvore(raiz: Path) -> None:
    """A árvore sintética, montada pela convenção do INVENTARIADOR."""
    for indice, caso in enumerate(CASOS):
        arquivos = CONTEUDO[indice]
        if arquivos is None:
            continue
        linha = linha_de(caso, 3 + indice)
        pasta = raiz / convencao.chave_pasta_edital(linha)
        pasta.mkdir(parents=True, exist_ok=True)
        for nome in arquivos:
            (pasta / nome).write_bytes(b"x")


def montar_agenda(caminho: Path) -> None:
    """
    Uma Agenda sintética com TODOS os cabeçalhos que o Módulo 2 lê — os dele são
    um superconjunto dos do Inventariador. Os cabeçalhos ficam na linha 2 e os
    dados a partir da linha 3, como na planilha real.

    As colunas entram EMBARALHADAS de propósito: as duas implementações
    localizam coluna pelo TEXTO DO CABEÇALHO, nunca por posição, e é isso que
    esta montagem prova.
    """
    cabecalhos = [
        "Participou", "Objeto", "CIDADE", "Qtde de Itens da Licitação",
        "Data Limite para Cadastro Proposta", "UF", "NOME DO ÓRGÃO",
        "Horário Limite para Cadastro Proposta", "INFORMAÇÕES EDITAIS",
        "Número do Pregão", "TIPO", "PLATAFORMA PORTAL", "EDITAL Chegou",
        "Código ConLicitação", "Objeto Completo",
    ]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2026"
    ws.cell(row=1, column=1, value="(linha 1 — título, ignorada pelos dois)")
    for coluna, titulo in enumerate(cabecalhos, start=1):
        ws.cell(row=2, column=coluna, value=titulo)

    for indice, caso in enumerate(CASOS):
        cidade, uf, numero, codigo = caso
        valores = {
            "CIDADE": cidade,
            "UF": uf,
            "Número do Pregão": numero,
            "Código ConLicitação": codigo,
            "Data Limite para Cadastro Proposta": "01/10/2026",
            "NOME DO ÓRGÃO": f"Órgão {indice}",
            "Objeto": "Medicamentos",
            "Objeto Completo": "Aquisição de medicamentos diversos",
            "TIPO": "Menor preço",
            "PLATAFORMA PORTAL": "ComprasNet",
            "EDITAL Chegou": "SIM",
            "INFORMAÇÕES EDITAIS": "",
            "Qtde de Itens da Licitação": 10,
            "Horário Limite para Cadastro Proposta": "09:00",
            "Participou": "",
        }
        for coluna, titulo in enumerate(cabecalhos, start=1):
            ws.cell(row=3 + indice, column=coluna, value=valores[titulo])

    # Duas linhas que os DOIS têm de ignorar, pela mesma regra.
    ws.cell(row=3 + len(CASOS), column=cabecalhos.index("CIDADE") + 1, value="")
    ws.cell(row=3 + len(CASOS), column=cabecalhos.index("Número do Pregão") + 1, value="PE/1/2026")
    ws.cell(row=4 + len(CASOS), column=cabecalhos.index("CIDADE") + 1, value="Cidade Sem Numero")
    ws.cell(row=4 + len(CASOS), column=cabecalhos.index("Número do Pregão") + 1, value="")

    wb.save(caminho)
    wb.close()


def importar_modulo2(raiz_editais: Path, caminho_agenda: Path):
    """
    Importa `modulo2/config.py` e `modulo2/utils.py` com o ambiente apontando
    para a árvore e a Agenda sintéticas.

    O `config.py` do Módulo 2 resolve a pasta dos editais na CARGA do módulo,
    então o ambiente tem de estar posto ANTES do import — e o `sys.path` tem de
    trazer o diretório dele, porque `utils.py` faz `import config` simples.
    """
    os.environ["PASTA_DESTINO"] = str(raiz_editais)
    os.environ["PASTA_EDITAIS"] = str(raiz_editais)
    os.environ["CAMINHO_AGENDA"] = str(caminho_agenda)
    os.environ["ABA_AGENDA"] = "2026"

    sys.path.insert(0, str(MODULO2))
    for ja_carregado in ("config", "utils", "pasta_editais"):
        sys.modules.pop(ja_carregado, None)
    import config as config_m2  # noqa: E402
    import utils as utils_m2  # noqa: E402
    return config_m2, utils_m2


class LoggerMudo:
    """O `ler_linhas_agenda()` do Módulo 2 exige um logger. Este não fala nada."""

    def info(self, *a, **k):
        pass

    error = warning = debug = info


# ═══════════════════════════════════════════════════════════════════════════
# AS COMPARAÇÕES
# ═══════════════════════════════════════════════════════════════════════════

def comparar_composicao_de_nomes(utils_m2, linhas):
    print("\n--- a COMPOSIÇÃO do nome da pasta, linha a linha ---")
    divergentes = []
    for linha in linhas:
        pares = [
            ("remover_acentos",
             convencao.remover_acentos(linha["cidade"]),
             utils_m2.remover_acentos(linha["cidade"])),
            ("formatar_num_edital",
             convencao.formatar_num_edital(linha["numero_pregao"]),
             utils_m2.formatar_num_edital(linha["numero_pregao"])),
            ("formatar_codigo_edital",
             convencao.formatar_codigo_edital(linha["codigo_conlicitacao"]),
             utils_m2.formatar_codigo_edital(linha["codigo_conlicitacao"])),
            ("nome_pasta_cidade",
             convencao.nome_pasta_cidade(linha["cidade"], linha["uf"]),
             utils_m2.nome_pasta_cidade(linha["cidade"], linha["uf"])),
            ("nome_pasta_edital",
             convencao.nome_pasta_edital(linha),
             utils_m2.nome_pasta_edital(linha)),
            ("chave_pasta_edital",
             convencao.chave_pasta_edital(linha),
             utils_m2.chave_pasta_edital(linha)),
        ]
        for nome, meu, dele in pares:
            if meu != dele:
                divergentes.append(f"linha {linha['linha_agenda']} · {nome}: "
                                   f"inventariador={meu!r} modulo2={dele!r}")
    checar(not divergentes,
           f"as 6 funções de composição batem nas {len(linhas)} linhas "
           f"({6 * len(linhas)} comparações)",
           " | ".join(divergentes[:5]))


def comparar_localizacao_e_estado(utils_m2, raiz, linhas):
    print("\n--- a LOCALIZAÇÃO da pasta e o ESTADO dela, linha a linha ---")
    divergentes_pasta = []
    divergentes_estado = []
    ambiguas = 0
    for linha in linhas:
        minha = convencao.localizar_pasta_edital(linha, raiz)
        dele = utils_m2.localizar_pasta_edital(linha)
        if minha != dele:
            divergentes_pasta.append(f"linha {linha['linha_agenda']}: {minha!r} != {dele!r}")

        meu_estado, minha_pasta = convencao.estado_pasta_edital(linha, raiz)
        estado_m2, pasta_m2 = utils_m2.estado_pasta_edital(linha)
        if meu_estado == convencao.ESTADO_AMBIGUA:
            # O Módulo 2 escolhe a primeira; o Inventariador declara e não
            # escolhe. É a ÚNICA diferença prevista, e ela é contada à parte.
            ambiguas += 1
            continue
        if convencao.ESTADOS_EQUIVALENTES[meu_estado] != estado_m2:
            divergentes_estado.append(
                f"linha {linha['linha_agenda']}: {meu_estado} != {estado_m2}")
        if minha_pasta != pasta_m2:
            divergentes_estado.append(
                f"linha {linha['linha_agenda']} (pasta): {minha_pasta!r} != {pasta_m2!r}")

    checar(not divergentes_pasta,
           f"localizar_pasta_edital() devolve a MESMA pasta nas {len(linhas)} linhas",
           " | ".join(divergentes_pasta[:5]))
    checar(not divergentes_estado,
           f"estado_pasta_edital() devolve o MESMO estado e a MESMA pasta "
           f"nas {len(linhas) - ambiguas} linhas não ambíguas",
           " | ".join(divergentes_estado[:5]))
    checar(ambiguas == 0,
           "nenhuma linha desta árvore é ambígua — a comparação cobriu todas",
           f"{ambiguas} ambígua(s)")


def comparar_arquivo_do_edital(utils_m2, raiz, linhas):
    print("\n--- pasta_tem_arquivo_edital(): a regra que decide COM_ARQUIVO ---")
    divergentes = []
    conferidas = 0
    for linha in linhas:
        pasta = convencao.localizar_pasta_edital(linha, raiz)
        if pasta is None:
            continue
        conferidas += 1
        if convencao.pasta_tem_arquivo_edital(pasta) != utils_m2.pasta_tem_arquivo_edital(pasta):
            divergentes.append(str(pasta))
    checar(not divergentes,
           f"a regra bate nas {conferidas} pastas que existem em disco",
           " | ".join(divergentes[:5]))


def comparar_leitura_da_agenda(utils_m2, caminho_agenda):
    print("\n--- a LEITURA DA AGENDA: as duas leem as mesmas linhas ---")
    minhas = agenda_inventariador.ler_linhas_agenda(caminho_agenda, "2026")
    dele = utils_m2.ler_linhas_agenda(LoggerMudo())

    igual(len(minhas), len(dele),
          "as duas devolvem o MESMO número de linhas (as sem cidade/número são "
          "ignoradas pela mesma regra)")

    # O Módulo 2 lê mais campos (objeto, tipo, plataforma...). A comparação é
    # sobre os campos que os DOIS leem — que são exatamente os que decidem a
    # identidade e a localização do edital.
    campos = ("linha_agenda", "cidade", "uf", "numero_pregao", "codigo_conlicitacao")
    divergentes = []
    for minha, dela in zip(minhas, dele):
        for campo in campos:
            if minha[campo] != dela[campo]:
                divergentes.append(f"linha {minha['linha_agenda']} · {campo}: "
                                   f"{minha[campo]!r} != {dela[campo]!r}")
    checar(not divergentes,
           f"os 5 campos de identidade batem nas {len(minhas)} linhas "
           f"({5 * len(minhas)} comparações)",
           " | ".join(divergentes[:5]))
    return len(minhas)


def comparar_cabecalho_ausente(utils_m2, caminho_agenda_quebrada):
    print("\n--- cabeçalho ausente: as duas FALHAM, em vez de adivinhar coluna ---")
    from agenda import CabecalhoAgendaAusente as MinhaExcecao

    minha_falhou = False
    try:
        agenda_inventariador.ler_linhas_agenda(caminho_agenda_quebrada, "2026")
    except MinhaExcecao:
        minha_falhou = True

    dele_falhou = False
    guardado = os.environ.get("CAMINHO_AGENDA")
    os.environ["CAMINHO_AGENDA"] = str(caminho_agenda_quebrada)
    try:
        import importlib
        import config as config_m2
        importlib.reload(config_m2)
        utils_m2.config.CAMINHO_AGENDA = config_m2.CAMINHO_AGENDA
        utils_m2.ler_linhas_agenda(LoggerMudo())
    except utils_m2.CabecalhoAgendaAusente:
        dele_falhou = True
    finally:
        if guardado is not None:
            os.environ["CAMINHO_AGENDA"] = guardado

    checar(minha_falhou, "o Inventariador levanta CabecalhoAgendaAusente")
    checar(dele_falhou, "o Módulo 2 levanta CabecalhoAgendaAusente")
    checar(minha_falhou == dele_falhou, "e os dois reagem do MESMO jeito")


def main() -> int:
    print("=" * 70)
    print("EQUIVALÊNCIA COM O MÓDULO 2 — a cópia não pode envelhecer em silêncio")
    print("=" * 70)

    area = Path(tempfile.mkdtemp(prefix="inventariador_equivalencia_"))
    try:
        raiz = area / "Editais"
        raiz.mkdir()
        montar_arvore(raiz)

        caminho_agenda = area / "Agenda_sintetica.xlsx"
        montar_agenda(caminho_agenda)

        quebrada = area / "Agenda_sem_codigo.xlsx"
        wb = openpyxl.load_workbook(caminho_agenda)
        ws = wb["2026"]
        for celula in ws[2]:
            if celula.value == "Código ConLicitação":
                celula.value = "Codigo Que Nao Existe"
        wb.save(quebrada)
        wb.close()

        config_m2, utils_m2 = importar_modulo2(raiz, caminho_agenda)
        print(f"\nMódulo 2 importado de: {MODULO2}")
        print(f"  config.PASTA_EDITAIS  = {config_m2.PASTA_EDITAIS}")
        print(f"  config.CAMINHO_AGENDA = {config_m2.CAMINHO_AGENDA}")
        checar(Path(config_m2.PASTA_EDITAIS) == raiz,
               "o Módulo 2 está olhando para a MESMA árvore sintética")

        quantas = comparar_leitura_da_agenda(utils_m2, caminho_agenda)
        linhas = agenda_inventariador.ler_linhas_agenda(caminho_agenda, "2026")
        comparar_composicao_de_nomes(utils_m2, linhas)
        comparar_localizacao_e_estado(utils_m2, raiz, linhas)
        comparar_arquivo_do_edital(utils_m2, raiz, linhas)
        comparar_cabecalho_ausente(utils_m2, quebrada)

        print(f"\n(equivalência rodada sobre {quantas} linhas da Agenda sintética)")
    finally:
        shutil.rmtree(area, ignore_errors=True)

    print("\n" + "=" * 70)
    if _falhas:
        print(f"RESULTADO (equivalência com o Módulo 2): {len(_falhas)} de {_total} FALHARAM")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"RESULTADO (equivalência com o Módulo 2): as {_total} provas passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
