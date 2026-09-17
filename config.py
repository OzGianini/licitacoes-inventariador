# -*- coding: utf-8 -*-
r"""
OS CAMINHOS DO INVENTARIADOR — todos resolvidos num lugar só.

A PASTA DOS EDITAIS
    É a MESMA pasta física do resto da cadeia, sob os mesmos dois nomes:

        Módulo 1   PASTA_DESTINO   GRAVA os editais baixados do portal
        Módulo 2   PASTA_EDITAIS   LÊ os editais para analisar
        aqui       (lê os dois)    LÊ, e só lê

    POR QUE ESTE ARQUIVO NÃO É UMA TERCEIRA CÓPIA DE `pasta_editais.py`
        O `pasta_editais.py` existe hoje DUAS vezes, idêntico byte a byte, em
        `modulo1\` e em `modulo2\`, e as suítes `teste_etapa12_pasta_editais`
        dos DOIS módulos o comparam byte a byte justamente para a cópia não
        divergir. Uma terceira cópia entraria nesse pacto sem estar naquelas
        suítes — seria a cópia que ninguém compara, que é o pior lugar possível.

        Por isso aqui não há cópia daquele arquivo: há a LEITURA das mesmas duas
        variáveis, com o MESMO padrão versionado, e a recusa explícita de
        escolher entre valores divergentes. A regra de quem manda continua sendo
        a daqueles dois — e, na cadeia, quem propaga as duas variáveis para toda
        etapa é o Maestro (`pasta_editais_da_cadeia()`), que é quem enxerga os
        dois lados.

AS PASTAS DE SAÍDA
    `saida/`, `logs/` e `relatorios/` são do PRÓPRIO Inventariador, dentro da
    casa dele. Todas sobrepujáveis por ambiente, porque a auditoria roda com
    elas redirecionadas para fora dos repositórios — proibir `.pyc` e arquivo
    novo em pasta de saída sem oferecer o mecanismo que os evita foi o que gerou
    desvio em rodadas anteriores.

    NADA é escrito em `PASTA_EDITAIS`, na Agenda, no Módulo 1, no Módulo 2 nem
    no Módulo 3. Nunca.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ─── A Agenda: a fonte, SOMENTE LEITURA ────────────────────────────────────
CAMINHO_AGENDA = Path(os.getenv(
    "CAMINHO_AGENDA", r"C:\licitacoes\dados\Agenda_Licitacoes.xlsx"))
# Mesma convenção do Módulo 1 e do Módulo 2 — atualizar na virada do ano.
ABA_AGENDA = os.getenv("ABA_AGENDA", "2026")

# ─── A pasta dos editais ───────────────────────────────────────────────────
# O padrão é o MESMO do código versionado dos Módulos 1 e 2. Não há nome de
# usuário no caminho de propósito: um padrão com perfil de usuário apontaria,
# noutro servidor, para uma conta que não existe.
PASTA_EDITAIS_PADRAO = r"C:\Editais 2026"
VARIAVEL_MODULO1 = "PASTA_DESTINO"
VARIAVEL_MODULO2 = "PASTA_EDITAIS"
VARIAVEIS_PASTA_EDITAIS = (VARIAVEL_MODULO1, VARIAVEL_MODULO2)


class PastasDeEditaisDivergentes(RuntimeError):
    """
    `PASTA_DESTINO` e `PASTA_EDITAIS` apontam para pastas diferentes.

    Erro explícito de propósito, e é a mesma decisão do `pasta_editais.py`:
    escolher uma às escondidas significaria inventariar uma pasta e a cadeia
    trabalhar noutra — a falha silenciosa que custou, até 18/08, o Módulo 2
    inteiro rodando contra pasta vazia, sem erro e com código de saída 0.
    """


def resolver_pasta_editais(ambiente: dict | None = None) -> Path:
    """
    A pasta dos editais, pela mesma regra dos Módulos 1 e 2.

    Nenhuma das duas definidas -> o padrão versionado.
    Uma definida                -> ela.
    As duas, concordando        -> ela.
    As duas, divergindo         -> PastasDeEditaisDivergentes, nomeando as duas
                                   variáveis e os dois valores.
    """
    ambiente = os.environ if ambiente is None else ambiente
    definidas = {nome: ambiente.get(nome, "").strip()
                 for nome in VARIAVEIS_PASTA_EDITAIS
                 if ambiente.get(nome, "").strip()}
    if not definidas:
        return Path(PASTA_EDITAIS_PADRAO)
    valores = {Path(v) for v in definidas.values()}
    if len(valores) > 1:
        detalhe = " e ".join(f"{nome}={valor!r}" for nome, valor in sorted(definidas.items()))
        raise PastasDeEditaisDivergentes(
            f"As duas variáveis da pasta dos editais apontam para lugares "
            f"diferentes: {detalhe}. O Inventariador não escolhe entre elas — "
            f"corrija para que apontem para a mesma pasta."
        )
    return next(iter(valores))


# NÃO há `PASTA_EDITAIS = resolver_pasta_editais()` aqui, e a ausência é
# deliberada. O `config.py` do Módulo 2 resolve a pasta na CARGA do módulo, e lá
# isso é correto: quem importa aquele config já está dentro de uma execução. Um
# ponto de ENTRADA é diferente — resolver no import faria a divergência de
# variáveis estourar como traceback antes de qualquer `try`, e a etapa do
# Maestro mostraria um rastro de pilha no lugar da frase que diz qual variável
# aponta para onde. Quem chama, chama `resolver_pasta_editais()` e trata.

# ─── As pastas do próprio Inventariador ────────────────────────────────────
PASTA_SAIDA = Path(os.getenv("PASTA_SAIDA", str(BASE_DIR / "saida")))
PASTA_LOGS = Path(os.getenv("PASTA_LOGS", str(BASE_DIR / "logs")))
PASTA_RELATORIOS = Path(os.getenv("PASTA_RELATORIOS", str(BASE_DIR / "relatorios")))

# O retrato mais novo e o anterior — os dois lados do diff do §4.8.
NOME_INVENTARIO_ATUAL = "inventario_atual.json"
NOME_INVENTARIO_ANTERIOR = "inventario_anterior.json"
NOME_DIFF = "diff_inventario.json"

# Sufixo do log, casado com o que a etapa do Maestro declara.
SUFIXO_LOG = "inventario"
