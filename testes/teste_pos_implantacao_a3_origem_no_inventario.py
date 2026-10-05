"""
CORRECOES-POS-IMPLANTACAO-20261005 · A3 — a origem de cada arquivo no inventário.

O que estava errado: tudo o que estava na pasta do edital entrava no inventário do mesmo
jeito — habilitação em .zip, certidões, catálogos e a proposta da equipe iam para o M3
como se fossem do edital.

Agora o inventário lê o manifesto do Módulo 1 (`manifesto_m1.json`, na pasta do edital) e
marca cada arquivo com `origem`. Tudo sintético; nada real.

Provas:
  1. pasta COM manifesto: o .zip e o .pdf do M1 saem BAIXADO_PELO_M1; os membros do .zip
     do M1 também (caso negativo pedido: o .zip do M1 continua com o de dentro valendo);
  2. os arquivos da equipe — .zip de habilitação, os membros dele, a certidão e a proposta
     — saem ARQUIVO_DA_EQUIPE, «arquivo da equipe — fora do M3»;
  3. o resumo_edital e o próprio manifesto saem ARTEFATO_DO_M1;
  4. nada na pasta foi apagado, movido ou renomeado (lista e bytes iguais antes e depois);
  5. um arquivo com o NOME do M1 mas tamanho diferente do manifesto é da equipe (a origem
     não é deduzida pelo nome).
Casos negativos:
  N1. pasta SEM manifesto (edital antigo): todos SEM_MANIFESTO_DO_M1, cada um com o aviso
      «sem manifesto do M1» — mesmo os de nome no padrão do M1 (nada é deduzido) — e os
      achados da pasta são os de antes;
  N2. manifesto ilegível vale como ausente, com achado próprio.
"""
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import inventario as inv  # noqa: E402

FALHAS: list[str] = []


def checar(condicao, descricao: str) -> None:
    print(f"  {'OK  ' if condicao else 'FALHA'} {descricao}")
    if not condicao:
        FALHAS.append(descricao)


def zip_com(membros: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in membros.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def foto(pasta: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pasta.iterdir())}


def origens(arquivos: list[dict]) -> dict:
    return {(a["container"], a["caminho"]): a.get("origem") for a in arquivos}


def montar_pasta(raiz: Path, com_manifesto: bool, manifesto_texto: str | None = None) -> Path:
    pasta = raiz / "CIDADE TESTE - PR" / "PE 1-2026 - CONLIC-90000001"
    pasta.mkdir(parents=True)
    do_m1 = {
        "CIDADE-TESTE-PR_PE-1-2026.zip": zip_com({"edital.pdf": b"%PDF-edital", "termo.docx": b"docx"}),
        "CIDADE-TESTE-PR_PE-1-2026.pdf": b"%PDF-unico",
    }
    da_equipe = {
        "habilitacao.zip": zip_com({"certidao.pdf": b"%PDF-cert", "balanco.xlsx": b"xlsx"}),
        "certidao_negativa.pdf": b"%PDF-certidao-da-equipe",
        "proposta.docx": b"docx-proposta",
        # mesmo padrão de nome do M1, mas não é o arquivo que o M1 baixou (tamanho diferente)
        "CIDADE-TESTE-PR_PE-1-2026_1.pdf": b"%PDF-da-equipe-com-nome-parecido",
    }
    for nome, dados in {**do_m1, **da_equipe}.items():
        (pasta / nome).write_bytes(dados)
    (pasta / "resumo_edital.json").write_text("{}", encoding="utf-8")
    if com_manifesto:
        manifesto = {"formato": "manifesto_m1/1", "arquivos": [
            {"nome": n, "sha256": hashlib.sha256(d).hexdigest(), "tamanho_bytes": len(d),
             "data": "2026-10-05T08:31:00"} for n, d in do_m1.items()]}
        # o .pdf de nome parecido: o manifesto registra OUTRO tamanho para esse nome
        manifesto["arquivos"].append({"nome": "CIDADE-TESTE-PR_PE-1-2026_1.pdf", "sha256": "0" * 64,
                                      "tamanho_bytes": 1, "data": "2026-10-05T08:31:00"})
        (pasta / "manifesto_m1.json").write_text(json.dumps(manifesto), encoding="utf-8")
    if manifesto_texto is not None:
        (pasta / "manifesto_m1.json").write_text(manifesto_texto, encoding="utf-8")
    return pasta


def main() -> int:
    raiz = Path(tempfile.mkdtemp(prefix="a3_inv_"))

    print("\n--- 1 a 5: pasta COM manifesto do M1 ---")
    pasta = montar_pasta(raiz / "com", com_manifesto=True)
    antes = foto(pasta)
    arquivos, achados = inv._inventariar_pasta(pasta)
    o = origens(arquivos)
    M1, EQ, ART = "BAIXADO_PELO_M1", "ARQUIVO_DA_EQUIPE", "ARTEFATO_DO_M1"
    checar(o.get((None, "CIDADE-TESTE-PR_PE-1-2026.zip")) == M1, "o .zip do M1 é BAIXADO_PELO_M1")
    checar(o.get((None, "CIDADE-TESTE-PR_PE-1-2026.pdf")) == M1, "o .pdf do M1 é BAIXADO_PELO_M1")
    checar(o.get(("CIDADE-TESTE-PR_PE-1-2026.zip", "edital.pdf")) == M1
           and o.get(("CIDADE-TESTE-PR_PE-1-2026.zip", "termo.docx")) == M1,
           "NEGATIVO pedido: os membros do .zip do M1 são BAIXADO_PELO_M1")
    for chave in [(None, "habilitacao.zip"), ("habilitacao.zip", "certidao.pdf"),
                  ("habilitacao.zip", "balanco.xlsx"), (None, "certidao_negativa.pdf"),
                  (None, "proposta.docx")]:
        checar(o.get(chave) == EQ, f"{chave[1]}{' (dentro de ' + chave[0] + ')' if chave[0] else ''} é ARQUIVO_DA_EQUIPE")
    descricoes = {a.get("origem_descricao") for a in arquivos if a.get("origem") == EQ}
    checar(descricoes == {"arquivo da equipe — fora do M3"},
           "e o arquivo da equipe aparece como «arquivo da equipe — fora do M3»")
    checar(o.get((None, "resumo_edital.json")) == ART and o.get((None, "manifesto_m1.json")) == ART,
           "o resumo_edital e o manifesto são ARTEFATO_DO_M1")
    checar(o.get((None, "CIDADE-TESTE-PR_PE-1-2026_1.pdf")) == EQ,
           "o .pdf com nome no padrão do M1 mas tamanho diferente do manifesto é da EQUIPE")
    checar(not any("MANIFESTO" in a["tipo"] for a in achados), "sem achado de manifesto")
    checar(foto(pasta) == antes, "nada foi apagado, movido, renomeado ou alterado na pasta")

    print("\n--- NEGATIVO N1: pasta SEM manifesto (edital antigo) ---")
    pasta = montar_pasta(raiz / "sem", com_manifesto=False)
    antes = foto(pasta)
    arquivos, achados = inv._inventariar_pasta(pasta)
    checar(arquivos and all(a.get("origem") == "SEM_MANIFESTO_DO_M1" for a in arquivos),
           "TODOS os arquivos saem SEM_MANIFESTO_DO_M1 — inclusive os de nome no padrão do M1")
    checar(all("sem manifesto do M1" in (a.get("origem_descricao") or "") for a in arquivos),
           "e cada arquivo traz o aviso «sem manifesto do M1»")
    checar(not any("MANIFESTO" in a["tipo"] for a in achados),
           "sem achado novo: os achados da pasta antiga são os de antes")
    checar(foto(pasta) == antes, "nada foi alterado na pasta")

    print("\n--- NEGATIVO N2: manifesto ilegível vale como ausente ---")
    pasta = montar_pasta(raiz / "ilegivel", com_manifesto=False, manifesto_texto="{isto não é json")
    arquivos, achados = inv._inventariar_pasta(pasta)
    checar(all(a.get("origem") == "SEM_MANIFESTO_DO_M1" for a in arquivos),
           "todos SEM_MANIFESTO_DO_M1 — o comportamento antigo")
    checar(any(a["tipo"] == "MANIFESTO_DO_M1_ILEGIVEL" for a in achados), "com o achado do manifesto ilegível")

    print()
    if FALHAS:
        print(f"RESULTADO: {len(FALHAS)} FALHA(S)")
        for falha in FALHAS:
            print(f"  - {falha}")
        return 1
    print("RESULTADO: todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
