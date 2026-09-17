# -*- coding: utf-8 -*-
r"""
A INTEGRAÇÃO AO MAESTRO, E OS DOIS HANDOFFS — §5 e §5.1 do enunciado.

    M1 → Inventariador → M2 → Publicador

O QUE ESTA SUÍTE PROVA

    1. HANDOFF M1 → INVENTARIADOR
       O Inventariador acha a pasta que o Módulo 1 cria. A prova não é uma
       afirmação: as funções de convenção são LIDAS DO FONTE REAL do
       `modulo1/agente_captura.py` (por `ast`, sem importar o arquivo — ele
       carrega o Playwright) e usadas para montar a árvore que o Inventariador
       depois tem de encontrar.

    2. HANDOFF INVENTARIADOR → M2 — de ORQUESTRAÇÃO, não de dados
       · a cadeia REAL executa na ordem M1, Inventariador, M2, Publicador —
         provado rodando `maestro._executar_cadeia()` de verdade, com o
         disparo de processo substituído por um gravador de ordem;
       · a etapa do Módulo 2 continua declarada EXATAMENTE como estava:
         mesmo id, mesmo nome, mesmo cwd, mesmo script, args VAZIOS, mesmo
         log, mesmo ambiente_extra, mesmas proteções. Nenhum parâmetro novo,
         nenhum formato de entrada novo, nenhuma API nova;
       · o Inventariador não escreve NADA que o Módulo 2 leia.

    3. AS DECLARAÇÕES DA ETAPA
       `respeita_stop_flag` e `watchdog_pode_forcar` com o motivo escrito,
       `log_dir`/`log_sufixo` próprios, e o ambiente que a etapa precisa.

O MAESTRO NÃO É ALTERADO POR ESTA SUÍTE — ela só lê. Os caminhos de log e a
`stop.flag` são desviados para área temporária enquanto a ordem é medida, para
nenhum arquivo do projeto ser tocado.
"""

from __future__ import annotations

import ast
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

RAIZ = Path(__file__).resolve().parent.parent
MAESTRO_DIR = Path(r"C:\licitacoes\maestro")
MODULO1_FONTE = Path(r"C:\licitacoes\modulo1\agente_captura.py")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(MAESTRO_DIR))

import convencao_edital as convencao  # noqa: E402
import inventario as inv  # noqa: E402
import maestro  # noqa: E402

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


def etapa_do_inventariador() -> dict:
    """A etapa do Inventariador, achada pelo SUFIXO DO LOG — nunca pelo id."""
    for etapa in maestro.ETAPAS:
        if etapa["log_sufixo"] == "inventario":
            return etapa
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# 1. HANDOFF M1 → INVENTARIADOR
# ═══════════════════════════════════════════════════════════════════════════

def convencao_do_modulo1(pasta_destino: Path):
    """
    As funções de convenção de pasta do Módulo 1, lidas do FONTE REAL dele.

    `agente_captura.py` não é importado: ele carrega o Playwright e tem 223 KB
    de coisa que não tem nada a ver com esta prova. O que se faz é achar as
    quatro funções pela árvore sintática e executá-las num espaço isolado.

    O ganho é que a prova acompanha o Módulo 1: se alguém mudar a convenção
    LÁ, esta suíte fica vermelha AQUI, sem ninguém precisar lembrar de copiar a
    mudança.
    """
    fonte = MODULO1_FONTE.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    desejadas = {"remover_acentos", "formatar_num_edital",
                 "formatar_codigo_edital", "caminho_pasta_edital"}
    trechos = [no for no in arvore.body
               if isinstance(no, ast.FunctionDef) and no.name in desejadas]
    if len(trechos) != len(desejadas):
        achadas = {no.name for no in trechos}
        raise RuntimeError(f"funções não achadas no Módulo 1: {desejadas - achadas}")

    import unicodedata
    espaco = {"Path": Path, "unicodedata": unicodedata, "PASTA_DESTINO": pasta_destino}
    exec(compile(ast.Module(body=trechos, type_ignores=[]), str(MODULO1_FONTE), "exec"), espaco)
    return espaco


def teste_handoff_m1_para_o_inventariador():
    print("\n--- handoff M1 -> Inventariador: ele acha a pasta que o M1 cria ---")
    area = Path(tempfile.mkdtemp(prefix="inventariador_handoff_m1_"))
    try:
        destino = area / "Editais 2026"
        m1 = convencao_do_modulo1(destino)

        casos = [
            ("Curitiba", "PR", "PE/35/2026", "19241283"),
            ("São José dos Pinhais", "PR", "DL/17/2026", "19241284"),
            ("Ponte Branca", "MT", "PE 1-2026", ""),        # -> CONLIC-SEM-CODIGO
            ("Maringá", "PR", "PE/1154/2026", "19316489"),
        ]
        linhas = []
        for indice, (cidade, uf, numero, codigo) in enumerate(casos):
            # A PASTA É CRIADA PELA FUNÇÃO DO MÓDULO 1, não pela do Inventariador.
            pasta = m1["caminho_pasta_edital"](cidade, uf, numero, codigo)
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "edital.pdf").write_bytes(b"x")
            linhas.append({
                "linha_agenda": 3 + indice, "cidade": cidade, "uf": uf,
                "numero_pregao": numero, "codigo_conlicitacao": codigo,
                "data_limite": "",
            })

        completo = inv.montar_inventario(linhas, destino)
        estados = {r["codigo_edital"]: r["estado_pasta"] for r in completo["editais"]}
        igual(sorted(estados.values()), [convencao.ESTADO_COM_ARQUIVO] * len(casos),
              "o Inventariador achou TODAS as pastas criadas pela função do Módulo 1")

        # E o caminho montado pelos dois lados é o MESMO, caractere a caractere.
        divergentes = []
        for linha, (cidade, uf, numero, codigo) in zip(linhas, casos):
            do_m1 = m1["caminho_pasta_edital"](cidade, uf, numero, codigo)
            do_inv = destino / convencao.chave_pasta_edital(linha)
            if do_m1 != do_inv:
                divergentes.append(f"{do_m1} != {do_inv}")
        checar(not divergentes,
               f"e o caminho montado pelos dois é idêntico nos {len(casos)} casos",
               " | ".join(divergentes))

        # O código no FIM do nome é o que torna a chave única — a razão de ser
        # da convenção. Duas linhas com cidade e número iguais e códigos
        # diferentes têm de cair em pastas DIFERENTES.
        a = m1["caminho_pasta_edital"]("Curitiba", "PR", "PE/35/2026", "19241283")
        b = m1["caminho_pasta_edital"]("Curitiba", "PR", "PE/35/2026", "19339001")
        checar(a != b,
               "cidade e número iguais com códigos diferentes dão pastas diferentes "
               "(a colisão que a convenção existe para impedir)")
    finally:
        shutil.rmtree(area, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# 2. A ORDEM DA CADEIA — provada executando a cadeia REAL
# ═══════════════════════════════════════════════════════════════════════════

def teste_ordem_real_da_cadeia():
    print("\n--- a cadeia REAL executa M1 -> Inventariador -> M2 -> Publicador ---")
    ordem = []

    def gravar_ordem(etapa):
        ordem.append(etapa["nome"])
        return 0, maestro.STATUS_CONCLUIDO

    area = Path(tempfile.mkdtemp(prefix="inventariador_ordem_"))
    guardado = (maestro._rodar_etapa, maestro.PASTA_LOGS, maestro.STOP_FLAG)
    try:
        # O disparo de processo é substituído por um gravador: o que se mede é a
        # ORDEM que `_executar_cadeia()` percorre, não o que cada script faz.
        maestro._rodar_etapa = gravar_ordem
        maestro.PASTA_LOGS = area
        maestro.STOP_FLAG = area / "stop.flag"
        maestro._executar_cadeia("pipeline", maestro.ids_das_etapas())
    finally:
        maestro._rodar_etapa, maestro.PASTA_LOGS, maestro.STOP_FLAG = guardado
        shutil.rmtree(area, ignore_errors=True)

    igual(ordem,
          ["Módulo 1 — captura",
           "Inventariador — arquivos por edital",
           "Módulo 2 — análise",
           "Publicador — Agenda/Sheets"],
          "as quatro etapas rodaram nessa ordem, na cadeia real")

    igual(maestro.ids_das_etapas(), [1, 5, 2, 3],
          "a ordem é a da LISTA, não a dos números — e é isso que põe o "
          "Inventariador entre a captura e a análise")

    posicoes = [e["log_sufixo"] for e in maestro.ETAPAS]
    igual(posicoes.index("inventario"), 1, "o Inventariador é a SEGUNDA entrada da lista")
    checar(posicoes.index("captura") < posicoes.index("inventario") < posicoes.index("analise"),
           "depois da captura e antes da análise")


# ═══════════════════════════════════════════════════════════════════════════
# 3. O CONTRATO DO MÓDULO 2, INTACTO
# ═══════════════════════════════════════════════════════════════════════════

# O retrato da etapa do Módulo 2 como ela estava ANTES desta rodada, medido no
# Gate 0. Esta suíte existe para que qualquer alteração nesses campos — um
# parâmetro novo, um formato de entrada novo, um ambiente diferente — apareça
# como falha, e não como "ajuste para a integração caber".
CONTRATO_M2_NO_GATE_0 = {
    "id": 2,
    "modulo_id": 2,
    "nome": "Módulo 2 — análise",
    "cwd": r"C:\licitacoes\modulo2",
    "script": r"C:\licitacoes\modulo2\analisador.py",
    "args": [],
    "log_dir": r"C:\licitacoes\modulo2\logs",
    "log_sufixo": "analise",
    "watchdog_pode_forcar": False,
    "respeita_stop_flag": False,
    "ambiente_extra_chaves": [
        "FILTRO_DATA_ATE", "FILTRO_DATA_DE", "FILTRO_MODALIDADE",
        "FILTRO_MUNICIPIOS", "FILTRO_UF", "LISTA_EDITAIS_TESTE",
        "MODO_TESTE", "PASTA_DESTINO", "PASTA_EDITAIS",
    ],
}

CONTRATO_PUBLICADOR_NO_GATE_0 = {
    "id": 3,
    "nome": "Publicador — Agenda/Sheets",
    "args": [],
    "log_sufixo": "publicacao",
    "ambiente_extra_chaves": ["MODO_SIMULACAO", "PASTA_DESTINO", "PASTA_EDITAIS"],
}


def teste_contrato_do_modulo2_intacto():
    print("\n--- o Módulo 2 é chamado com o contrato ATUAL dele, byte a byte ---")
    etapa = maestro.etapa_por_id(2)
    esperado = CONTRATO_M2_NO_GATE_0
    igual(etapa["id"], esperado["id"], "o id da etapa do Módulo 2 não mudou")
    igual(etapa["modulo_id"], esperado["modulo_id"], "o modulo_id não mudou")
    igual(etapa["nome"], esperado["nome"], "o nome não mudou")
    igual(str(etapa["cwd"]), esperado["cwd"], "o cwd não mudou")
    igual(str(etapa["script"]), esperado["script"], "o script não mudou")
    igual(etapa["args"], esperado["args"],
          "os args continuam VAZIOS — nenhum parâmetro novo foi acrescentado")
    igual(str(etapa["log_dir"]), esperado["log_dir"], "o log_dir não mudou")
    igual(etapa["log_sufixo"], esperado["log_sufixo"], "o log_sufixo não mudou")
    igual(etapa["watchdog_pode_forcar"], esperado["watchdog_pode_forcar"],
          "a proteção do watchdog não mudou")
    igual(etapa["respeita_stop_flag"], esperado["respeita_stop_flag"],
          "a declaração da stop.flag não mudou")
    igual(sorted(etapa["ambiente_extra"]), esperado["ambiente_extra_chaves"],
          "o ambiente que ele recebe não mudou")

    publicador = maestro.etapa_por_id(3)
    igual(publicador["id"], CONTRATO_PUBLICADOR_NO_GATE_0["id"], "o id do Publicador não mudou")
    igual(publicador["nome"], CONTRATO_PUBLICADOR_NO_GATE_0["nome"], "o nome não mudou")
    igual(publicador["args"], CONTRATO_PUBLICADOR_NO_GATE_0["args"], "os args continuam vazios")
    igual(sorted(publicador["ambiente_extra"]),
          CONTRATO_PUBLICADOR_NO_GATE_0["ambiente_extra_chaves"],
          "e o ambiente do Publicador não mudou")


def teste_o_inventario_nao_e_entrada_do_modulo2():
    print("\n--- o handoff é de ORQUESTRAÇÃO: o inventário não vira entrada do M2 ---")
    etapa_m2 = maestro.etapa_por_id(2)
    etapa_inv = etapa_do_inventariador()

    igual(etapa_m2["args"], [],
          "o Módulo 2 não recebe caminho de inventário por linha de comando")
    checar(not any("INVENTARIO" in chave.upper() for chave in etapa_m2["ambiente_extra"]),
           "nem por variável de ambiente")
    checar(Path(etapa_inv["log_dir"]) != Path(etapa_m2["log_dir"]),
           "e as duas etapas nem compartilham pasta de log")

    import config as config_inventariador
    saidas = [config_inventariador.PASTA_SAIDA,
              config_inventariador.PASTA_LOGS,
              config_inventariador.PASTA_RELATORIOS]
    fora = [str(p) for p in saidas
            if Path(r"C:\licitacoes\modulo2") in Path(p).parents
            or Path(r"C:\licitacoes\modulo1") in Path(p).parents
            or Path(r"C:\licitacoes\modulo3") in Path(p).parents]
    checar(not fora,
           "nenhuma saída do Inventariador cai dentro do M1, do M2 ou do M3",
           " | ".join(fora))


# ═══════════════════════════════════════════════════════════════════════════
# 4. AS DECLARAÇÕES DA ETAPA NOVA
# ═══════════════════════════════════════════════════════════════════════════

def teste_declaracoes_da_etapa_do_inventariador():
    print("\n--- a etapa do Inventariador declara tudo o que o §5 manda ---")
    etapa = etapa_do_inventariador()
    checar(bool(etapa), "a cadeia tem uma etapa de inventário")

    igual(str(etapa["cwd"]), r"C:\licitacoes\inventariador", "cwd é a casa da frente")
    igual(str(etapa["script"]), r"C:\licitacoes\inventariador\inventariador.py",
          "o script é o ponto de entrada da frente")
    igual(etapa["args"], [], "roda SEM parâmetro, como toda etapa da lista")
    igual(str(etapa["log_dir"]), r"C:\licitacoes\inventariador\logs", "log_dir próprio")
    igual(etapa["log_sufixo"], "inventario", "log_sufixo próprio")
    checar(str(maestro.caminho_log_etapa(etapa)).endswith("_inventario.log"),
           "e o log sai no formato <log_dir>/AAAAMMDD_inventario.log",
           str(maestro.caminho_log_etapa(etapa)))

    checar(etapa["respeita_stop_flag"] is False,
           "respeita_stop_flag=False — só o Módulo 1 lê a stop.flag; aqui um "
           "código != 0 significa erro de verdade, não parada a pedido")
    checar(etapa["watchdog_pode_forcar"] is True,
           "watchdog_pode_forcar=True — o Inventariador só lê")
    checar(len(etapa["motivo_watchdog"]) > 40 and "lê" in etapa["motivo_watchdog"],
           "e o motivo está ESCRITO, como o padrão do Maestro exige",
           etapa["motivo_watchdog"])

    igual(sorted(etapa["ambiente_extra"]), ["PASTA_DESTINO", "PASTA_EDITAIS"],
          "recebe a pasta dos editais sob os dois nomes, como as outras etapas")
    checar("MODO_SIMULACAO" not in etapa["ambiente_extra"],
           "e NÃO declara MODO_SIMULACAO — essa é da etapa que grava")

    declaram_simulacao = [e["id"] for e in maestro.ETAPAS
                          if "MODO_SIMULACAO" in (e.get("ambiente_extra") or {})]
    igual(declaram_simulacao, [3],
          "MODO_SIMULACAO continua declarada por UMA etapa só: a que publica")


def teste_o_painel_enxerga_a_etapa_nova():
    print("\n--- o painel mostra a etapa nova, e o mapa dos módulos não some ---")
    etapas = maestro._etapas_para_painel()
    igual(len(etapas), 4, "o painel lista as quatro etapas")
    nomes = [e["nome"] for e in etapas]
    igual(nomes.index("Inventariador — arquivos por edital"), 1,
          "e a mostra na segunda posição")
    igual([e["ordem"] for e in etapas], [1, 2, 3, 4],
          "a ordem exibida é 1..4, mesmo com os ids sendo 1, 5, 2, 3")

    por_id = {m["id"]: m for m in maestro.MODULOS}
    checar(7 in por_id, "o Inventariador está no mapa dos módulos do painel")
    checar(por_id[7]["implementado"] is True, "e aparece como implementado")
    igual(maestro.status_do_modulo(7)[0], maestro.status_do_modulo(7)[0],
          "e status_do_modulo() responde por ele sem estourar")
    for numero in (1, 2, 3, 4, 5, 6):
        checar(numero in por_id, f"o Módulo {numero} continua no mapa")


def teste_id_4_continua_reservado_para_o_modulo3():
    print("\n--- o id 4 continua reservado ao Módulo 3, no bloco comentado ---")
    fonte = (MAESTRO_DIR / "maestro.py").read_text(encoding="utf-8")
    checar("#         id=4, modulo_id=3," in fonte,
           "o bloco comentado da integração automática do Módulo 3 continua lá")
    checar(maestro.etapa_por_id(4) is None,
           "e nenhuma etapa REAL usa o id 4 — ele segue livre para o Módulo 3")
    ids = [e["id"] for e in maestro.ETAPAS]
    igual(len(ids), len(set(ids)), "nenhum id se repete na cadeia")


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("INTEGRAÇÃO AO MAESTRO — M1 -> Inventariador -> M2 -> Publicador")
    print("=" * 70)
    for teste in (
        teste_handoff_m1_para_o_inventariador,
        teste_ordem_real_da_cadeia,
        teste_contrato_do_modulo2_intacto,
        teste_o_inventario_nao_e_entrada_do_modulo2,
        teste_declaracoes_da_etapa_do_inventariador,
        teste_o_painel_enxerga_a_etapa_nova,
        teste_id_4_continua_reservado_para_o_modulo3,
    ):
        teste()

    print("\n" + "=" * 70)
    if _falhas:
        print(f"RESULTADO (integração ao Maestro): {len(_falhas)} de {_total} FALHARAM")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print(f"RESULTADO (integração ao Maestro): as {_total} provas passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
