# -*- coding: utf-8 -*-
r"""
O INVENTARIADOR — ponto de entrada. É este arquivo que o Maestro executa.

RODA SEM PARÂMETRO, de propósito: é a regra da lista `ETAPAS` do Maestro —
«toda etapa de ETAPAS roda sem parâmetro: o painel clica e o script faz o que
tem de fazer». Tudo o que ele precisa vem do ambiente e do `config.py`.

O QUE ELE FAZ, NESTA ORDEM
    1. lê a Agenda (SOMENTE LEITURA);
    2. para cada linha, olha o disco e monta o inventário;
    3. grava o inventário novo, o diff contra o anterior e o relatório;
    4. sai com 0.

POR QUE SAI COM 0 MESMO ACHANDO ANOMALIA
    `AUSENTE` e `AMBIGUA` são anomalia e merecem destaque — mas não podem parar
    a cadeia. Um edital com a pasta apagada, ou com duas pastas candidatas, não
    pode impedir os outros de serem inventariados, nem impedir o Módulo 2 de
    rodar em seguida. O que o Inventariador faz com uma anomalia é REGISTRAR e
    SEGUIR.

    Código de saída != 0 fica reservado para o que impede o inventário de
    existir: a Agenda ilegível, o cabeçalho que sumiu, as duas variáveis da
    pasta dos editais apontando para lugares diferentes. Nesses casos não há
    inventário parcial nenhum a entregar, e a cadeia deve parar mesmo.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import convencao_edital as convencao
import diff_inventario
from agenda import CabecalhoAgendaAusente, ler_linhas_agenda
from inventario import SCHEMA_VERSION, montar_inventario

CODIGO_OK = 0
CODIGO_FALHA = 1


def montar_logger() -> logging.Logger:
    """
    O log da etapa, no formato que o Maestro já espera de toda etapa:
    `<log_dir>/AAAAMMDD_<sufixo>.log`. Um arquivo por dia.

    O console é reconfigurado para UTF-8 antes de mais nada. Rodando sob o
    Maestro, a saída vai para um PIPE, e no Windows um pipe herda a codificação
    do console (cp1252) — um nome de cidade com acento fora daquela tabela
    derrubaria a etapa com UnicodeEncodeError depois de o inventário já estar
    pronto. `errors="replace"` garante que o log nunca seja o motivo da falha.
    O ARQUIVO de log continua UTF-8 exato; a troca só afeta o console.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

    config.PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    caminho = config.PASTA_LOGS / f"{datetime.now():%Y%m%d}_{config.SUFIXO_LOG}.log"

    logger = logging.getLogger("inventariador")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formato = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
    arquivo = logging.FileHandler(caminho, encoding="utf-8")
    arquivo.setFormatter(formato)
    logger.addHandler(arquivo)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formato)
    logger.addHandler(console)
    return logger


def _gravar_json(caminho: Path, conteudo: dict) -> None:
    """
    JSON determinístico: indentação fixa, `ensure_ascii=False` e SEM
    `sort_keys` — a ordem das chaves é a ordem em que o contrato as declara, e
    a ordem das listas já foi decidida em `inventario.py`. Quebra de linha
    "\\n" explícita, para o arquivo não mudar de bytes por causa do sistema
    operacional.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n"
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)


def _ler_json(caminho: Path) -> dict | None:
    if not caminho.exists():
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def executar(logger: logging.Logger | None = None) -> int:
    logger = logger or montar_logger()

    try:
        raiz_editais = config.resolver_pasta_editais()
    except config.PastasDeEditaisDivergentes as erro:
        logger.error(str(erro))
        return CODIGO_FALHA

    logger.info("=" * 70)
    logger.info("INVENTARIADOR — que arquivos existem AGORA para cada edital")
    logger.info("=" * 70)
    logger.info(f"schema_version do contrato de saída: {SCHEMA_VERSION}")
    logger.info(f"Agenda (somente leitura): {config.CAMINHO_AGENDA} · aba {config.ABA_AGENDA!r}")
    logger.info(f"Pasta dos editais (somente leitura): {raiz_editais}")
    logger.info(f"Saída: {config.PASTA_SAIDA}")

    if not raiz_editais.is_dir():
        # NÃO é anomalia de um edital: é a base inteira fora do lugar. Sem ela,
        # todo edital sairia AUSENTE e o inventário anunciaria uma catástrofe
        # que não aconteceu. Melhor parar dizendo o que faltou.
        logger.error(f"A pasta dos editais não existe: {raiz_editais}")
        logger.error("Sem ela, TODO edital sairia AUSENTE — o que seria um retrato falso. "
                     "Nada foi gravado.")
        return CODIGO_FALHA

    try:
        linhas = ler_linhas_agenda(config.CAMINHO_AGENDA, config.ABA_AGENDA)
    except (FileNotFoundError, CabecalhoAgendaAusente) as erro:
        logger.error(f"Agenda ilegível: {type(erro).__name__}: {erro}")
        return CODIGO_FALHA

    logger.info(f"Agenda lida: {len(linhas)} linha(s) com Cidade + Nº do Pregão")

    inventario = montar_inventario(linhas, raiz_editais)
    totais = inventario["totais"]

    logger.info("-" * 70)
    logger.info(f"editais (linhas da Agenda) ........: {totais['editais_linhas_da_agenda']}")
    for estado, quantidade in totais["editais_por_estado_da_pasta"].items():
        logger.info(f"  estado da pasta {estado:<12} ...: {quantidade}")
    logger.info(f"entradas de arquivo ..............: {totais['entradas_de_arquivo']}")
    logger.info(f"  soltas na pasta ................: {totais['entradas_soltas_na_pasta']}")
    logger.info(f"  dentro de container ............: {totais['entradas_dentro_de_container']}")
    logger.info(f"  marcadas artefato do M1 ........: {totais['entradas_marcadas_artefato_do_m1']}")
    logger.info(f"  de zero byte ...................: {totais['entradas_de_zero_byte']}")

    # ANOMALIA COM DESTAQUE — e a cadeia segue.
    #
    # `anomalia` é «NÃO É ROTINA», e cobre DOIS estados. O log os separa em vez
    # de somar, porque eles pedem ações diferentes da equipe — e porque o total
    # sozinho não diz qual dos dois apareceu.
    anomalias = totais["editais_com_anomalia"]
    if anomalias:
        por_estado = totais["editais_por_estado_da_pasta"]
        ausentes = por_estado.get(convencao.ESTADO_AUSENTE, 0)
        ambiguas = por_estado.get(convencao.ESTADO_AMBIGUA, 0)
        logger.warning("!" * 70)
        logger.warning(f"ANOMALIA — {anomalias} edital(is) fora da rotina "
                       f"({ausentes} AUSENTE · {ambiguas} AMBIGUA).")
        if ausentes:
            logger.warning(f"  {ausentes} com a pasta AUSENTE. O Módulo 1 cria a pasta "
                           "SEMPRE, antes do download. Linha na Agenda sem pasta em disco "
                           "significa pasta apagada, renomeada ou arrastada depois — erro "
                           "humano, ou problema no volume.")
        if ambiguas:
            # O MAIS GRAVE DOS QUATRO estados, e o que ficou marcado como rotina
            # até esta rodada: não é «a pasta sumiu», é «NÃO SE SABE qual é a
            # pasta deste edital». O fail-closed da D1 recusa escolher, e o
            # `achados` traz as candidatas pelo nome.
            logger.warning(f"  {ambiguas} AMBIGUA — mais de uma pasta candidata para a "
                           "mesma identidade. NENHUMA foi escolhida: ausência declarada é "
                           "melhor que associação errada. As candidatas estão nos achados "
                           "de cada edital.")
        logger.warning("NÃO bloqueia: os demais editais foram inventariados normalmente.")
        logger.warning("!" * 70)

    if totais["achados_por_tipo"]:
        logger.info("-" * 70)
        logger.info("ACHADOS declarados (nada foi adivinhado, nada foi aberto além de um nível):")
        for tipo, quantidade in totais["achados_por_tipo"].items():
            logger.info(f"  {tipo:<32} {quantidade}")

    # ─── Gravação: o retrato novo, o anterior preservado, e o diff ──────────
    config.PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    caminho_atual = config.PASTA_SAIDA / config.NOME_INVENTARIO_ATUAL
    caminho_anterior = config.PASTA_SAIDA / config.NOME_INVENTARIO_ANTERIOR

    anterior = _ler_json(caminho_atual)
    if anterior is not None:
        _gravar_json(caminho_anterior, anterior)

    carimbo = f"{datetime.now():%Y%m%d_%H%M%S}"
    _gravar_json(config.PASTA_SAIDA / f"inventario_{carimbo}.json", inventario)
    _gravar_json(caminho_atual, inventario)

    diferencas = diff_inventario.comparar(anterior, inventario)
    _gravar_json(config.PASTA_SAIDA / config.NOME_DIFF, diferencas)

    logger.info("-" * 70)
    if diferencas["sem_base_de_comparacao"]:
        # O MOTIVO vem do diff, e não de um texto fixo aqui. A versão anterior
        # deste log anunciava "primeira execução" em qualquer caso sem base — e
        # passou a mentir no dia em que apareceu o segundo caso, o da mudança de
        # schema: havia inventário anterior, e o log dizia que não havia.
        # Um log que descreve a causa errada é pior que um log ausente.
        logger.info(f"DIFF: sem base de comparação — {diferencas['motivo']}")
        if diferencas["schema_version_anterior"] is not None:
            logger.info(f"      o anterior era schema_version "
                        f"{diferencas['schema_version_anterior']}, e este é "
                        f"{diferencas['schema_version_atual']}.")
    else:
        t = diferencas["totais"]
        logger.info(f"DIFF (identidade comparada: {diferencas['identidade_comparada']})")
        logger.info(f"  ADICIONADO .: {t['ADICIONADO']}")
        logger.info(f"  REMOVIDO ...: {t['REMOVIDO']}")
        logger.info(f"  ALTERADO ...: {t['ALTERADO']}")
        logger.info(f"  INALTERADO .: {t['INALTERADO']}")
        if diferencas["editais_que_mudaram_de_estado"]:
            logger.info(f"  editais que mudaram de estado: "
                        f"{len(diferencas['editais_que_mudaram_de_estado'])}")
    logger.info("O diff responde 'o conjunto de arquivos mudou?'. NUNCA "
                "'o que falta processar?' — o Inventariador não é dono de fila.")

    _gravar_relatorio(inventario, diferencas, raiz_editais, logger)

    logger.info("=" * 70)
    logger.info("INVENTARIADOR concluído. Nenhum arquivo inventariado foi alterado, "
                "movido, renomeado ou extraído. Nenhum PDF foi aberto.")
    logger.info("=" * 70)
    return CODIGO_OK


def _gravar_relatorio(inventario: dict, diferencas: dict, raiz_editais,
                      logger: logging.Logger) -> None:
    """
    O relatório de execução — e é AQUI que moram o relógio, o caminho absoluto e
    a máquina.

    O inventário não os carrega de propósito: é o que permite comparar dois
    retratos byte a byte. Quem precisa saber quando e onde a leitura foi feita
    lê este arquivo, ao lado.
    """
    config.PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
    caminho = config.PASTA_RELATORIOS / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.json"
    _gravar_json(caminho, {
        "schema_version_do_inventario": inventario["schema_version"],
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "agenda": str(config.CAMINHO_AGENDA),
        "aba": config.ABA_AGENDA,
        "raiz_editais": str(raiz_editais),
        "pasta_saida": str(config.PASTA_SAIDA),
        "totais": inventario["totais"],
        "diff_totais": diferencas["totais"],
        "sem_base_de_comparacao": diferencas["sem_base_de_comparacao"],
    })
    logger.info(f"Relatório de execução: {caminho}")


def main() -> int:
    return executar()


if __name__ == "__main__":
    raise SystemExit(main())
