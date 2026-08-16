#!/usr/bin/env python3
"""
Processa uma pasta inteira de arquivos .txt tabulados (TSV):
  1. Lê cada .txt (detecta encoding automaticamente)
  2. Traduz as colunas indicadas (Inglês -> Português do Brasil)
  3. Escreve o resultado de volta em .txt, mantendo o nome original,
     numa pasta de saída (padrão: "traduzidos")

O modelo é carregado UMA ÚNICA VEZ e todas as frases de todos os
arquivos são traduzidas juntas em lotes grandes, o que é bem mais
rápido do que processar arquivo por arquivo.

Uso no Colab:
    !python processar_pasta.py ./meus_txts --coluna "NPC SAY,PC REPLY" --linha-cabecalho 1

Parâmetros opcionais:
    --pasta-saida traduzidos     # nome/caminho da pasta de saída (padrão: "traduzidos")
    --coluna 2,5                 # índice(s) numérico(s) e/ou nome(s) de cabeçalho, por vírgula
    --linha-cabecalho 0          # linha (0-based) com os nomes das colunas nos arquivos
    --modelo facebook/nllb-200-distilled-1.3B
    --batch-size 32
    --max-length 256
    --remover-acentos            # remove acentos/caracteres especiais da tradução (ASCII puro)
"""

import argparse
import csv
import io
import os
import re
import sys
import time
import unicodedata

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


# --------------------------------------------------------------------------
# Leitura / escrita de arquivos tabulados (TSV)
# --------------------------------------------------------------------------

def detectar_encoding(caminho: str) -> str:
    """Tenta UTF-8 primeiro; se falhar, usa cp1252 (Windows-1252)."""
    with open(caminho, "rb") as f:
        raw = f.read()
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def ler_tsv(caminho: str) -> list[list[str]]:
    encoding = detectar_encoding(caminho)
    with open(caminho, "r", encoding=encoding, newline="") as f:
        linhas_texto = f.read().splitlines()
    return [linha.split("\t") for linha in linhas_texto]


def escrever_tsv(caminho: str, linhas: list[list[str]]):
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        for linha in linhas:
            f.write("\t".join(linha) + "\n")


# --------------------------------------------------------------------------
# Remoção de acentos (opcional)
# --------------------------------------------------------------------------

_MAPA_PONTUACAO_ESPECIAL = {
    "–": "-", "—": "-",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "…": "...",
}


def remover_acentos(texto: str) -> str:
    for original, substituto in _MAPA_PONTUACAO_ESPECIAL.items():
        texto = texto.replace(original, substituto)
    forma_decomposta = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in forma_decomposta if not unicodedata.combining(c))
    return sem_acentos.encode("ascii", "ignore").decode("ascii")


# --------------------------------------------------------------------------
# Divisão em frases (evita truncamento do NLLB em textos com várias frases)
# --------------------------------------------------------------------------

def dividir_sentencas(texto: str) -> list[str]:
    texto = texto.strip()
    if not texto:
        return []
    partes = re.split(r"(?<=[.!?])\s+", texto)
    return [p for p in partes if p.strip()]


# --------------------------------------------------------------------------
# Modelo de tradução
# --------------------------------------------------------------------------

def carregar_modelo(nome_modelo: str, device: str):
    print(f"Carregando modelo '{nome_modelo}' em {device}...")
    tokenizer = AutoTokenizer.from_pretrained(nome_modelo, src_lang="eng_Latn")
    modelo = AutoModelForSeq2SeqLM.from_pretrained(
        nome_modelo,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device)
    modelo.eval()
    return tokenizer, modelo


def traduzir_em_lotes(textos, tokenizer, modelo, device, batch_size, max_length):
    """Traduz uma lista de textos em lotes, ordenando por tamanho para reduzir padding."""
    indices_ordenados = sorted(range(len(textos)), key=lambda i: len(textos[i]))
    textos_ordenados = [textos[i] for i in indices_ordenados]

    resultados = [None] * len(textos)
    total = len(textos_ordenados)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids("por_Latn")

    inicio = time.time()
    with torch.no_grad():
        for i in range(0, total, batch_size):
            lote = textos_ordenados[i : i + batch_size]

            lote_validos_idx = [j for j, t in enumerate(lote) if t.strip()]
            lote_validos = [lote[j] for j in lote_validos_idx]

            traducoes_lote = [""] * len(lote)

            if lote_validos:
                entradas = tokenizer(
                    lote_validos,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                ).to(device)

                saida = modelo.generate(
                    **entradas,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=max_length,
                    num_beams=1,
                )

                textos_traduzidos = tokenizer.batch_decode(saida, skip_special_tokens=True)

                for pos, texto_traduzido in zip(lote_validos_idx, textos_traduzidos):
                    traducoes_lote[pos] = texto_traduzido

            for offset, traducao in enumerate(traducoes_lote):
                resultados[indices_ordenados[i + offset]] = traducao

            processados = min(i + batch_size, total)
            decorrido = time.time() - inicio
            velocidade = processados / decorrido if decorrido > 0 else 0
            print(
                f"\r{processados}/{total} frases traduzidas ({velocidade:.1f} frases/s)",
                end="",
                flush=True,
            )

    print()
    return resultados


# --------------------------------------------------------------------------
# Pipeline principal
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Traduz colunas de todos os .txt de uma pasta (Inglês -> PT-BR)."
    )
    parser.add_argument("pasta_entrada", help="Pasta com os arquivos .txt de entrada")
    parser.add_argument(
        "--pasta-saida", default="traduzidos", help="Pasta de saída (padrão: 'traduzidos')"
    )
    parser.add_argument(
        "--coluna",
        default="2",
        help="Coluna(s) a traduzir, separadas por vírgula: índice numérico (0-based) "
             "e/ou nome exato do cabeçalho (ex: 'NPC SAY,PC REPLY').",
    )
    parser.add_argument(
        "--linha-cabecalho",
        type=int,
        default=0,
        help="Índice (0-based) da linha com os nomes das colunas, igual em todos os arquivos. Padrão: 0.",
    )
    parser.add_argument(
        "--modelo", default="facebook/nllb-200-distilled-1.3B", help="Modelo NLLB a usar."
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Tamanho do lote (padrão: 32)")
    parser.add_argument("--max-length", type=int, default=256, help="Tamanho máximo em tokens (padrão: 256)")
    parser.add_argument(
        "--remover-acentos",
        action="store_true",
        help="Remove acentos e caracteres especiais da tradução (deixa só ASCII).",
    )
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print(
            "AVISO: GPU não detectada. No Colab, vá em Ambiente de execução > "
            "Alterar tipo de ambiente de execução > GPU.",
            file=sys.stderr,
        )

    if not os.path.isdir(args.pasta_entrada):
        print(f"Erro: pasta '{args.pasta_entrada}' não encontrada.", file=sys.stderr)
        sys.exit(1)

    arquivos = sorted(
        f for f in os.listdir(args.pasta_entrada) if f.lower().endswith(".txt")
    )
    if not arquivos:
        print(f"Nenhum arquivo .txt encontrado em '{args.pasta_entrada}'.", file=sys.stderr)
        sys.exit(1)

    print(f"{len(arquivos)} arquivo(s) .txt encontrado(s): {arquivos}")
    os.makedirs(args.pasta_saida, exist_ok=True)

    nomes_colunas_pedidas = [c.strip() for c in args.coluna.split(",")]

    # ---- Fase 1: lê todos os arquivos e monta um único lote de frases ----
    dados_por_arquivo = {}       # nome_arquivo -> {linhas, cabecalho, dados, indices_colunas}
    frases_planas = []           # todas as frases de todos os arquivos, juntas
    mapeamento_global = {}       # (nome_arquivo, indice_coluna) -> lista de (inicio, fim) por linha

    for nome_arquivo in arquivos:
        caminho = os.path.join(args.pasta_entrada, nome_arquivo)
        linhas = ler_tsv(caminho)

        if args.linha_cabecalho >= len(linhas):
            print(f"AVISO: '{nome_arquivo}' tem menos linhas que --linha-cabecalho; pulando.", file=sys.stderr)
            continue

        cabecalho = linhas[args.linha_cabecalho]
        linhas_titulo = linhas[: args.linha_cabecalho]
        dados = linhas[args.linha_cabecalho + 1 :]

        indices_colunas = []
        for item in nomes_colunas_pedidas:
            if item.isdigit():
                idx = int(item)
            elif item in cabecalho:
                idx = cabecalho.index(item)
            else:
                print(
                    f"AVISO: coluna '{item}' não encontrada em '{nome_arquivo}' "
                    f"(colunas disponíveis: {cabecalho}). Pulando essa coluna neste arquivo.",
                    file=sys.stderr,
                )
                continue
            indices_colunas.append(idx)

        dados_por_arquivo[nome_arquivo] = {
            "linhas_titulo": linhas_titulo,
            "cabecalho": cabecalho,
            "dados": dados,
            "indices_colunas": indices_colunas,
        }

        for indice_coluna in indices_colunas:
            mapeamento_linhas = []
            for linha in dados:
                texto = linha[indice_coluna] if indice_coluna < len(linha) else ""
                sentencas = dividir_sentencas(texto)
                inicio = len(frases_planas)
                frases_planas.extend(sentencas)
                mapeamento_linhas.append((inicio, len(frases_planas)))
            mapeamento_global[(nome_arquivo, indice_coluna)] = mapeamento_linhas

    print(f"\nTotal de frases a traduzir (todos os arquivos juntos): {len(frases_planas)}")

    # ---- Fase 2: carrega o modelo e traduz tudo de uma vez ----
    tokenizer, modelo = carregar_modelo(args.modelo, device)
    frases_traduzidas = traduzir_em_lotes(
        frases_planas, tokenizer, modelo, device, args.batch_size, args.max_length
    )

    # ---- Fase 3: remonta cada arquivo e escreve na pasta de saída ----
    for nome_arquivo, info in dados_por_arquivo.items():
        dados = info["dados"]
        for indice_coluna in info["indices_colunas"]:
            mapeamento_linhas = mapeamento_global[(nome_arquivo, indice_coluna)]
            traducoes = [
                " ".join(frases_traduzidas[inicio:fim]) if fim > inicio else ""
                for inicio, fim in mapeamento_linhas
            ]
            if args.remover_acentos:
                traducoes = [remover_acentos(t) for t in traducoes]

            for linha, traducao in zip(dados, traducoes):
                while len(linha) <= indice_coluna:
                    linha.append("")
                linha[indice_coluna] = traducao

        linhas_finais = info["linhas_titulo"] + [info["cabecalho"]] + dados
        caminho_saida = os.path.join(args.pasta_saida, nome_arquivo)
        escrever_tsv(caminho_saida, linhas_finais)
        print(f"'{nome_arquivo}' -> '{caminho_saida}'")

    print(f"\nConcluído! {len(dados_por_arquivo)} arquivo(s) traduzido(s) em '{args.pasta_saida}'.")


if __name__ == "__main__":
    main()
