# -*- coding: utf-8 -*-
r"""
DETERMINISMO ENTRE FUSOS — a prova que faltava, e que bloqueou a D1.

O CONTRATO QUE ISTO PROVA
    «Mesma entrada lógica e mesmo conjunto de arquivos → mesmo inventário, byte
    a byte. Sem depender de ordem do sistema de arquivos, horário, máquina ou
    usuário.»

POR QUE A SUÍTE ANTIGA NÃO PROVAVA ISSO
    `teste_ordem_deterministica_e_mesmo_conjunto_mesmo_inventario()` substituía
    `modificado_em` por `"(ignorado)"` antes de comparar os dois inventários.
    Um teste que apaga o campo defeituoso antes de olhar não prova nada sobre
    ele. A auditoria independente apontou exatamente isso.

COMO ESTA SUÍTE PROVA DE VERDADE
    O fuso vale NA HORA DE GERAR, e não numa normalização depois:

    1. uma árvore sintética é montada UMA vez, com metadata factual carimbada
       (`os.utime` nos soltos, `date_time` fixo no índice do ZIP);
    2. o inventário é gerado em SUBPROCESSOS, um por fuso, cada um com `TZ`
       diferente no ambiente;
    3. cada subprocesso reporta `time.timezone` e `datetime.fromtimestamp(0)`
       ANTES de gerar — é a prova de que o ambiente dele realmente mudou;
    4. os JSON serializados voltam e são comparados BYTE A BYTE, com
       `modificado_em` dentro da comparação.

    Se a correção fosse desfeita, o passo 4 quebra. Foi verificado: com
    `datetime.fromtimestamp()` sem `tz`, os três fusos dão três saídas
    diferentes.

POR QUE SUBPROCESSO, E NÃO MONKEYPATCH
    Porque o requisito é sobre o AMBIENTE da geração. Trocar uma função por
    outra dentro do mesmo processo provaria que a função trocada funciona, não
    que o programa é indiferente à máquina em que roda. O subprocesso é o único
    jeito de o fuso valer para o interpretador inteiro — inclusive para
    `os.path.getmtime` e para o `zipfile`.

    (`time.tzset()` não existe no Windows; a variável `TZ` no ambiente do
    processo, sim, e `time.timezone` prova que ela pegou.)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

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
        print(f"  [ ] FALHOU: {descricao}" + (f" - {detalhe}" if detalhe else ""))
        _falhas.append(descricao)


def igual(obtido, esperado, descricao):
    checar(obtido == esperado, descricao, f"obtido={obtido!r} esperado={esperado!r}")


# ═══════════════════════════════════════════════════════════════════════════
# OS FUSOS, E A ÁRVORE
# ═══════════════════════════════════════════════════════════════════════════

# Formato POSIX que o runtime C do Windows entende na variável TZ:
# "<sigla><deslocamento>", com o SINAL INVERTIDO em relação ao usual — TZ=JST-9
# é UTC+9. Os três valores abaixo foram medidos nesta máquina: `time.timezone`
# devolve 10800, 0 e -32400 respectivamente, o que prova que pegaram.
FUSOS = [
    ("America/Sao_Paulo", "BRT3"),     # UTC-3
    ("UTC", "UTC0"),                   # UTC+0
    ("Asia/Tokyo", "JST-9"),           # UTC+9
]

INSTANTE_UTC_FIXO = datetime(2026, 9, 14, 18, 31, 1, tzinfo=timezone.utc)
INSTANTE_FIXO = INSTANTE_UTC_FIXO.timestamp()
DATA_HORA_FIXA_NO_ZIP = (2026, 9, 14, 18, 31, 0)

# O gerador que roda DENTRO do subprocesso. Imprime a prova do ambiente numa
# primeira linha, e o inventário serializado no resto.
GERADOR = r'''
import json, sys, time
from datetime import datetime
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import inventario as inv

prova = {
    "time_timezone": time.timezone,
    "fromtimestamp_zero": datetime.fromtimestamp(0).isoformat(),
    "TZ": __import__("os").environ.get("TZ"),
}
linhas = json.loads(sys.argv[3])
documento = inv.montar_inventario(linhas, sys.argv[2])
sys.stdout.write(json.dumps(prova) + "\n@@@\n" + json.dumps(documento, ensure_ascii=False, indent=2))
'''


def linha(cidade="Curitiba", uf="PR", numero="PE/35/2026", codigo="19241283",
          linha_agenda=3):
    return {
        "linha_agenda": linha_agenda, "cidade": cidade, "uf": uf,
        "numero_pregao": numero, "codigo_conlicitacao": codigo, "data_limite": "",
    }


LINHAS = [
    linha(codigo="111", linha_agenda=3),
    linha(cidade="Maringá", codigo="222", numero="PE/40/2026", linha_agenda=4),
    linha(cidade="São José dos Pinhais", codigo="333", numero="DL/17/2026", linha_agenda=5),
]


def montar_arvore(raiz: Path) -> None:
    """
    A árvore sintética, com a metadata factual CARIMBADA.

    Carimbar é o que torna a comparação honesta. O contrato fala em «mesma
    entrada lógica e mesmo conjunto de arquivos» — e é isso que se garante aqui:
    mesmos bytes, mesmo mtime, mesma data no índice do ZIP. O que sobra para
    variar entre as execuções é SÓ o fuso do ambiente, que é o que se mede.
    """
    for l in LINHAS:
        pasta = raiz / convencao.chave_pasta_edital(l)
        pasta.mkdir(parents=True, exist_ok=True)
        for nome in ("edital.pdf", "anexo com espaço.pdf", "resumo_edital.json"):
            alvo = pasta / nome
            alvo.write_bytes(nome.encode("utf-8"))
            os.utime(alvo, (INSTANTE_FIXO, INSTANTE_FIXO))
        caminho_zip = pasta / "pacote.zip"
        with zipfile.ZipFile(caminho_zip, "w") as z:
            for nome in ("dentro_a.pdf", "sub/dentro_b.docx"):
                z.writestr(zipfile.ZipInfo(nome, date_time=DATA_HORA_FIXA_NO_ZIP),
                           nome.encode("utf-8"))
        os.utime(caminho_zip, (INSTANTE_FIXO, INSTANTE_FIXO))


def gerar_no_fuso(raiz: Path, tz: str) -> tuple[dict, str]:
    """Roda o gerador num subprocesso com `TZ` no ambiente. Devolve (prova, json)."""
    ambiente = dict(os.environ)
    ambiente["TZ"] = tz
    ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
    ambiente["PYTHONIOENCODING"] = "utf-8"
    resultado = subprocess.run(
        [sys.executable, "-B", "-c", GERADOR, str(RAIZ), str(raiz), json.dumps(LINHAS)],
        capture_output=True, text=True, encoding="utf-8", env=ambiente, check=True)
    prova_bruta, _, documento = resultado.stdout.partition("\n@@@\n")
    return json.loads(prova_bruta), documento


# ═══════════════════════════════════════════════════════════════════════════
# A PROVA DOS DOIS (TRÊS) FUSOS
# ═══════════════════════════════════════════════════════════════════════════

def teste_mesma_arvore_em_fusos_diferentes():
    print("\n--- a MESMA árvore, gerada em três fusos, byte a byte igual ---")
    area = Path(tempfile.mkdtemp(prefix="inventariador_fuso_"))
    try:
        raiz = area / "Editais"
        raiz.mkdir()
        montar_arvore(raiz)

        resultados = {}
        for nome, tz in FUSOS:
            prova, documento = gerar_no_fuso(raiz, tz)
            resultados[nome] = (prova, documento)
            print(f"      {nome:<22} TZ={tz:<6} time.timezone={prova['time_timezone']:>7} "
                  f"fromtimestamp(0)={prova['fromtimestamp_zero']}")

        # 1. O AMBIENTE REALMENTE MUDOU — sem isto, a comparação abaixo não vale
        deslocamentos = {n: p["time_timezone"] for n, (p, _) in resultados.items()}
        igual(len(set(deslocamentos.values())), 3,
              "os três subprocessos rodaram com deslocamentos de fuso DIFERENTES",
              )
        igual(deslocamentos["UTC"], 0, "o de UTC ficou em 0")
        checar(deslocamentos["America/Sao_Paulo"] > 0 > deslocamentos["Asia/Tokyo"],
               "e os outros dois ficaram de lados opostos do meridiano",
               str(deslocamentos))
        zeros = {n: p["fromtimestamp_zero"] for n, (p, _) in resultados.items()}
        igual(len(set(zeros.values())), 3,
              "e a época de cada um caiu num horário diferente — o ambiente mudou "
              "DE FATO, na hora de gerar", )

        # 2. E MESMO ASSIM A SAÍDA É A MESMA, BYTE A BYTE
        documentos = {n: d for n, (_, d) in resultados.items()}
        primeiro = documentos["America/Sao_Paulo"]
        for nome in ("UTC", "Asia/Tokyo"):
            igual(len(documentos[nome]), len(primeiro),
                  f"{nome}: mesmo tamanho serializado que America/Sao_Paulo")
            checar(documentos[nome] == primeiro,
                   f"{nome}: inventário IDÊNTICO byte a byte ao de America/Sao_Paulo")

        # 3. E `modificado_em` CONTINUA LÁ, com o valor esperado
        documento = json.loads(primeiro)
        soltos = [a for r in documento["editais"] for a in r["arquivos"]
                  if a["onde_estava"] == inv.ONDE_SOLTO]
        no_zip = [a for r in documento["editais"] for a in r["arquivos"]
                  if a["onde_estava"] == inv.ONDE_NO_CONTAINER]
        checar(soltos and no_zip, "há entradas das duas famílias no inventário")
        checar(all(a["modificado_em"] == "2026-09-14T18:31:01Z" for a in soltos),
               f"as {len(soltos)} entradas soltas saíram como instante UTC, com Z")
        checar(all(a["modificado_em"] == "2026-09-14T18:31:00" for a in no_zip),
               f"e as {len(no_zip)} de dentro do ZIP mantiveram a data FACTUAL do índice, sem Z")
    finally:
        shutil.rmtree(area, ignore_errors=True)


def teste_o_defeito_antigo_realmente_quebrava():
    """
    A contraprova: com a renderização ANTIGA, a mesma árvore dá saídas
    diferentes nos três fusos.

    Sem esta prova, um teste verde poderia significar «a correção funciona» ou
    «o teste não mede nada». Ela separa os dois casos.
    """
    print("\n--- contraprova: a renderização ANTIGA quebraria nos mesmos três fusos ---")
    gerador_antigo = r'''
import json, sys, os
from datetime import datetime
sys.dont_write_bytecode = True
# A renderização como era ANTES da correção: hora local, sem fuso.
print(datetime.fromtimestamp(float(sys.argv[1])).strftime("%Y-%m-%dT%H:%M:%S"))
'''
    saidas = {}
    for nome, tz in FUSOS:
        ambiente = dict(os.environ)
        ambiente["TZ"] = tz
        ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run([sys.executable, "-B", "-c", gerador_antigo, str(INSTANTE_FIXO)],
                           capture_output=True, text=True, env=ambiente, check=True)
        saidas[nome] = r.stdout.strip()
        print(f"      {nome:<22} -> {saidas[nome]}")
    igual(len(set(saidas.values())), 3,
          "a renderização antiga dava TRÊS valores diferentes para o MESMO instante")
    igual(saidas["UTC"], "2026-09-14T18:31:01",
          "e nenhum deles carregava marca de fuso — daí o defeito ser silencioso")


# ═══════════════════════════════════════════════════════════════════════════
# A PROVA DA MIGRAÇÃO — §5.1
# ═══════════════════════════════════════════════════════════════════════════

def teste_migracao_reinventariar_a_mesma_arvore_intocada():
    """
    §5.1 — inventariar uma árvore, aplicar a correção, reinventariar a MESMA
    árvore intocada, e provar que o diff sai DECLARADO SEM BASE, e não com N
    `ALTERADO`.

    A "aplicação da correção" é simulada do único jeito honesto possível depois
    que o código já está corrigido: montando o inventário ANTERIOR exatamente
    como a versão 1.0.0 o teria gravado — `schema_version` "1.0.0" e as datas
    dos soltos em hora local. Os arquivos em disco NÃO são tocados entre as duas
    leituras; é literalmente a mesma árvore.
    """
    print("\n--- §5.1 migração: mesma árvore intocada, antes e depois da correção ---")
    area = Path(tempfile.mkdtemp(prefix="inventariador_migracao_"))
    try:
        raiz = area / "Editais"
        raiz.mkdir()
        montar_arvore(raiz)

        # DEPOIS: o inventário de hoje, do código corrigido.
        depois = inv.montar_inventario(LINHAS, raiz)

        # ANTES: o mesmo inventário como a versão 1.0.0 o teria gravado.
        # Hora local de São Paulo para o mesmo instante: 15:31:01, sem Z.
        antes = json.loads(json.dumps(depois))
        antes["schema_version"] = "1.0.0"
        convertidas = 0
        for registro in antes["editais"]:
            for arquivo in registro["arquivos"]:
                if arquivo["onde_estava"] == inv.ONDE_SOLTO:
                    arquivo["modificado_em"] = "2026-09-14T15:31:01"
                    convertidas += 1
        checar(convertidas > 0,
               f"o inventário 'antigo' tem {convertidas} entradas soltas com data local")

        # A ÁRVORE NÃO FOI TOCADA entre as duas leituras — prova disso:
        retrato = sorted((str(p.relative_to(raiz)), p.stat().st_size, p.stat().st_mtime_ns)
                         for p in raiz.rglob("*") if p.is_file())
        de_novo = inv.montar_inventario(LINHAS, raiz)
        retrato_depois = sorted((str(p.relative_to(raiz)), p.stat().st_size, p.stat().st_mtime_ns)
                                for p in raiz.rglob("*") if p.is_file())
        igual(retrato_depois, retrato, "a árvore continua intocada entre as duas leituras")
        igual(json.dumps(de_novo), json.dumps(depois),
              "e reinventariar dá exatamente o mesmo inventário")

        # O DIFF: tem de sair DECLARADO SEM BASE.
        d = diff_inventario.comparar(antes, de_novo)
        checar(d["sem_base_de_comparacao"] is True,
               "o diff sai DECLARADO SEM BASE COMPARÁVEL")
        igual(d["totais"]["ALTERADO"], 0,
              "e com ZERO ALTERADO — nenhum alarme falso por efeito da correção")
        igual(d["totais"], {"ADICIONADO": 0, "REMOVIDO": 0, "ALTERADO": 0, "INALTERADO": 0},
              "os quatro totais são zero")
        igual(d["arquivos"], [], "e nenhuma linha de arquivo é emitida")
        igual(d["schema_version_anterior"], "1.0.0", "o diff diz de qual versão era o anterior")
        igual(d["schema_version_atual"], inv.SCHEMA_VERSION, "e de qual é o atual")
        checar("schema" in d["motivo"].lower(),
               "e o motivo nomeia a mudança de schema", d["motivo"])

        # O TAMANHO DO ALARME QUE FOI EVITADO — a guarda fazendo trabalho real.
        forcado = json.loads(json.dumps(antes))
        forcado["schema_version"] = inv.SCHEMA_VERSION
        sem_guarda = diff_inventario.comparar(forcado, de_novo)
        alterados = sem_guarda["totais"]["ALTERADO"]
        checar(alterados == convertidas,
               f"sem a guarda seriam {alterados} ALTERADO — um por entrada solta, "
               f"e nenhum arquivo mudou", f"{alterados} != {convertidas}")
        checar(all(x["campos_diferentes"] == ["modificado_em"]
                   for x in sem_guarda["arquivos"] if x["situacao"] == "ALTERADO"),
               "todos acusando exatamente `modificado_em` — o ruído que a guarda evita")
    finally:
        shutil.rmtree(area, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# A GUARDA DA D2 CONTINUA VALENDO SOB A VERSÃO NOVA
# ═══════════════════════════════════════════════════════════════════════════

def teste_a_guarda_da_d2_continua_valendo_no_schema_novo():
    """
    O fechamento subiu o `schema_version` de `2.0.0` para `3.0.0`. Esta prova
    NÃO reimplementa a guarda da D2 — ela mostra que a guarda continua fazendo
    o trabalho dela **sob a versão nova**, nos dois sentidos:

      (12) versão ANTERIOR × versão NOVA -> diff DECLARADO SEM BASE, 0/0/0/0;
      (13) versão NOVA × versão NOVA, com mudança REAL -> o diff CONTINUA
           ACUSANDO `ALTERADO` — inclusive quando só a DATA muda e o tamanho é
           idêntico byte a byte.

    A (13) existe porque uma guarda mal feita «resolve» o alarme falso matando o
    diff inteiro. Uma guarda que cala o sinal de verdade é pior que o alarme que
    ela evitou: o alarme falso irrita, o silêncio esconde.
    """
    print("\n--- a guarda da D2 sob o schema novo: (12) migra e (13) ainda acusa ---")
    area = Path(tempfile.mkdtemp(prefix="inventariador_guarda_"))
    try:
        raiz = area / "Editais"
        raiz.mkdir()
        montar_arvore(raiz)
        novo = inv.montar_inventario(LINHAS, raiz)
        igual(novo["schema_version"], "3.0.0", "o inventário de hoje é 3.0.0")

        # ── (12) o 2.0.0 que a D2 deixou, contra o 3.0.0 de hoje ───────────
        # O «anterior» é montado como a versão 2.0.0 o teria gravado: mesma
        # árvore, mesmas datas — só o `schema_version` e o nome do total que
        # aquela versão usava.
        anterior = json.loads(json.dumps(novo))
        anterior["schema_version"] = "2.0.0"
        anterior["totais"]["editais_com_anomalia_pasta_ausente"] = \
            anterior["totais"].pop("editais_com_anomalia")

        d = diff_inventario.comparar(anterior, novo)
        checar(d["sem_base_de_comparacao"] is True,
               "(12) 2.0.0 × 3.0.0 sai DECLARADO SEM BASE COMPARÁVEL")
        igual(d["totais"], {"ADICIONADO": 0, "REMOVIDO": 0, "ALTERADO": 0, "INALTERADO": 0},
              "com os quatro totais em zero — 0/0/0/0")
        igual(d["arquivos"], [], "e nenhuma linha de arquivo emitida")
        igual(d["schema_version_anterior"], "2.0.0", "o diff diz de qual versão era o anterior")
        igual(d["schema_version_atual"], "3.0.0", "e de qual é o atual")
        checar("schema" in d["motivo"].lower(),
               "e o motivo nomeia a mudança de schema", d["motivo"])

        # ── (13) a guarda NÃO matou o diff: mudança real continua acusada ──
        alvo = raiz / convencao.chave_pasta_edital(LINHAS[0]) / "edital.pdf"
        tamanho_antes = alvo.stat().st_size
        # SÓ A DATA muda. O conteúdo é reescrito com os MESMOS bytes, de
        # propósito: é o caso em que um diff preguiçoso — que comparasse só
        # tamanho — deixaria passar.
        alvo.write_bytes(alvo.read_bytes())
        os.utime(alvo, (INSTANTE_FIXO + 7200, INSTANTE_FIXO + 7200))
        igual(alvo.stat().st_size, tamanho_antes,
              "o arquivo foi reescrito com o MESMO tamanho em bytes")

        depois = inv.montar_inventario(LINHAS, raiz)
        d2 = diff_inventario.comparar(novo, depois)
        checar(d2["sem_base_de_comparacao"] is False,
               "(13) 3.0.0 × 3.0.0 COMPARA — a guarda não atrapalha versões iguais")
        alterados = [x for x in d2["arquivos"] if x["situacao"] == "ALTERADO"]
        igual(len(alterados), 1, "e exatamente um arquivo aparece como ALTERADO")
        igual(alterados[0]["caminho"], "edital.pdf", "e é o que realmente mudou")
        igual(alterados[0]["campos_diferentes"], ["modificado_em"],
              "acusando SÓ `modificado_em` — o tamanho é idêntico")
        igual(alterados[0]["tamanho_bytes_antes"], alterados[0]["tamanho_bytes_agora"],
              "os dois tamanhos batem, e mesmo assim o diff acusou")
        checar(alterados[0]["modificado_em_antes"] != alterados[0]["modificado_em_agora"],
               "porque a data mudou")
    finally:
        shutil.rmtree(area, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# AS SETE PROVAS DO §5 QUE NÃO SÃO O FUSO
# ═══════════════════════════════════════════════════════════════════════════

def teste_as_sete_provas_do_paragrafo_5():
    print("\n--- §5: as sete provas que acompanham a correção ---")
    area = Path(tempfile.mkdtemp(prefix="inventariador_sete_"))
    try:
        raiz = area / "Editais"
        raiz.mkdir()
        montar_arvore(raiz)
        antes = inv.montar_inventario(LINHAS, raiz)

        # (1) modificado_em continua presente
        todas = [a for r in antes["editais"] for a in r["arquivos"]]
        checar(todas and all("modificado_em" in a and a["modificado_em"] for a in todas),
               f"(1) `modificado_em` continua presente e preenchido nas {len(todas)} entradas")

        # (4) ZIP mantém a data factual do índice
        no_zip = [a for a in todas if a["onde_estava"] == inv.ONDE_NO_CONTAINER]
        checar(all(a["modificado_em"] == "2026-09-14T18:31:00" for a in no_zip),
               f"(4) as {len(no_zip)} entradas de ZIP mantêm a data do índice, sem conversão")

        # (2) arquivo realmente alterado continua ALTERADO
        alvo = raiz / convencao.chave_pasta_edital(LINHAS[0]) / "edital.pdf"
        alvo.write_bytes(b"conteudo bem maior agora, com mais bytes")
        os.utime(alvo, (INSTANTE_FIXO + 3600, INSTANTE_FIXO + 3600))
        depois = inv.montar_inventario(LINHAS, raiz)
        d = diff_inventario.comparar(antes, depois)
        mudados = [x for x in d["arquivos"] if x["situacao"] == "ALTERADO"]
        igual(len(mudados), 1, "(2) exatamente um arquivo aparece como ALTERADO")
        igual(mudados[0]["caminho"], "edital.pdf", "e é o que foi realmente alterado")
        igual(sorted(mudados[0]["campos_diferentes"]), ["modificado_em", "tamanho_bytes"],
              "com os dois campos acusados")
        igual(mudados[0]["modificado_em_agora"], "2026-09-14T19:31:01Z",
              "e a data nova continua sendo instante UTC")

        # (3) arquivo inalterado continua INALTERADO
        inalterados = [x for x in d["arquivos"] if x["situacao"] == "INALTERADO"]
        igual(len(inalterados), len(todas) - 1,
              f"(3) as outras {len(todas) - 1} entradas continuam INALTERADO")

        # (5) determinismo de ordem continua
        igual([r["codigo_edital"] for r in depois["editais"]],
              ["CONLIC-111", "CONLIC-222", "CONLIC-333"],
              "(5) os editais continuam saindo ordenados pelo código")
        igual([a["caminho"] for a in depois["editais"][0]["arquivos"]],
              ["anexo com espaço.pdf", "edital.pdf", "pacote.zip", "resumo_edital.json",
               "dentro_a.pdf", "sub/dentro_b.docx"],
              "e os arquivos, soltos primeiro e depois os do container")

        # (6) schema_version coerente
        igual(depois["schema_version"], inv.SCHEMA_VERSION,
              "(6) o inventário declara o schema_version do código")
        # ASSERÇÃO ATUALIZADA, NÃO REMOVIDA — e o motivo fica escrito ao lado,
        # que é a regra da D1.10. Ela codificava «a versão é 2.0.0», fato que o
        # fechamento mudou ao subir para 3.0.0 pelas duas correções daquela
        # rodada. A INTENÇÃO da prova é outra, e é preservada inteira: o número
        # da versão não pode mudar por acidente, sem ninguém notar.
        igual(inv.SCHEMA_VERSION, "3.0.0",
              "que é 3.0.0 — 1.0.0 na D1, 2.0.0 na D2 (determinismo), e 3.0.0 no "
              "fechamento (nome de membro + abrangência de `anomalia`), numa subida só")
        igual(d["schema_version_anterior"], d["schema_version_atual"],
              "e a comparação só aconteceu porque as duas versões batem")

        # (7) nenhuma identidade nova, nenhuma fila
        texto = json.dumps(depois)
        for proibido in ("uuid", "guid", "id_interno", "id_proprio", "inventario_id"):
            checar(proibido not in texto.lower(), f"(7) nenhum campo {proibido!r} foi criado")
        checar(all(r["codigo_edital"] == "CONLIC-" + r["codigo_conlicitacao"]
                   for r in depois["editais"]),
               "a identidade continua derivada só do código da Agenda")
        texto_diff = json.dumps(d).lower()
        for proibido in ("pendente", "fila", "processados", "tentativas"):
            checar(f'"{proibido}"' not in texto_diff, f"e nenhum campo {proibido!r} no diff")
        checar("nao_e_fila" in d, "o diff continua declarando que não é fila")
    finally:
        shutil.rmtree(area, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("DETERMINISMO ENTRE FUSOS, MIGRAÇÃO E AS SETE PROVAS DO §5")
    print("=" * 70)
    for teste in (
        teste_mesma_arvore_em_fusos_diferentes,
        teste_o_defeito_antigo_realmente_quebrava,
        teste_migracao_reinventariar_a_mesma_arvore_intocada,
        teste_a_guarda_da_d2_continua_valendo_no_schema_novo,
        teste_as_sete_provas_do_paragrafo_5,
    ):
        teste()

    print("\n" + "=" * 70)
    if _falhas:
        print(f"RESULTADO (determinismo entre fusos): {len(_falhas)} de {_total} FALHARAM")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"RESULTADO (determinismo entre fusos): as {_total} provas passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
