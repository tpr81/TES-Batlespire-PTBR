#!/usr/bin/env python3
"""
Traduz colunas de um CSV de Inglês -> Português (Brasil) usando
o modelo NLLB-200 da Meta, rodando em GPU (otimizado para Colab).

Uso no Colab:
    !python traduzir_csv.py entrada.csv saida.csv --coluna "NPC SAY,PC REPLY" --linha-cabecalho 1

Parâmetros opcionais:
    --coluna 2,5             # índice(s) numérico(s) e/ou nome(s) de cabeçalho, separados por vírgula
    --linha-cabecalho 0       # linha (0-based) com os nomes das colunas, se houver título antes
    --modelo facebook/nllb-200-distilled-1.3B
    --batch-size 32
    --max-length 256
    --remover-acentos         # remove acentos/caracteres especiais da tradução (ASCII puro)
"""

import argparse
import csv
import re
import sys
import time
import unicodedata

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


def carregar_modelo(nome_modelo: str, device: str):
    print(f"Carregando modelo '{nome_modelo}' em {device}...")
    tokenizer = AutoTokenizer.from_pretrained(nome_modelo, src_lang="eng_Latn")
    modelo = AutoModelForSeq2SeqLM.from_pretrained(
        nome_modelo,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device)
    modelo.eval()
    return tokenizer, modelo


_MAPA_PONTUACAO_ESPECIAL = {
    "–": "-", "—": "-",  # travessões -> hífen
    "‘": "'", "’": "'",  # aspas simples curvas
    "“": '"', "”": '"',  # aspas duplas curvas
    "…": "...",
}


def remover_acentos(texto: str) -> str:
    """
    Remove acentos e outros diacríticos, deixando só caracteres ASCII.
    Ex: "traduçao rápida" -> "traducao rapida".
    Pontuação especial comum (travessões, aspas curvas, reticências) é
    convertida para o equivalente ASCII antes de descartar o resto.
    """
    for original, substituto in _MAPA_PONTUACAO_ESPECIAL.items():
        texto = texto.replace(original, substituto)
    forma_decomposta = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in forma_decomposta if not unicodedata.combining(c))
    return sem_acentos.encode("ascii", "ignore").decode("ascii")


def dividir_sentencas(texto: str) -> list[str]:
    """
    Divide um texto em frases. O NLLB é treinado majoritariamente com
    frases isoladas e pode truncar/encerrar cedo quando recebe um texto
    com várias frases de uma vez -- por isso traduzimos frase por frase.
    """
    texto = texto.strip()
    if not texto:
        return []
    partes = re.split(r"(?<=[.!?])\s+", texto)
    return [p for p in partes if p.strip()]


def preparar_sentencas(textos: list[str]):
    """
    Achata a lista de textos (uma célula pode virar várias frases) e
    guarda um mapeamento para remontar cada célula depois da tradução.
    """
    frases_planas = []
    mapeamento = []  # (inicio, fim) no vetor frases_planas, por célula original
    for texto in textos:
        sentencas = dividir_sentencas(texto)
        inicio = len(frases_planas)
        frases_planas.extend(sentencas)
        mapeamento.append((inicio, len(frases_planas)))
    return frases_planas, mapeamento


def traduzir_em_lotes(textos, tokenizer, modelo, device, batch_size, max_length):
    """
    Traduz uma lista de textos em lotes, ordenando por tamanho para
    reduzir padding desnecessário (mais eficiente na GPU).
    """
    # Guarda o índice original para reordenar depois
    indices_ordenados = sorted(range(len(textos)), key=lambda i: len(textos[i]))
    textos_ordenados = [textos[i] for i in indices_ordenados]

    resultados = [None] * len(textos)
    total = len(textos_ordenados)

    # ID do token de português no NLLB
    forced_bos_token_id = tokenizer.convert_tokens_to_ids("por_Latn")

    inicio = time.time()
    with torch.no_grad():
        for i in range(0, total, batch_size):
            lote = textos_ordenados[i : i + batch_size]

            # Trata valores vazios/NaN sem enviar ao modelo
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
                    num_beams=1,  # greedy: mais rápido; use 2-4 se quiser mais qualidade
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
                f"\r{processados}/{total} linhas traduzidas "
                f"({velocidade:.1f} linhas/s)",
                end="",
                flush=True,
            )

    print()  # nova linha ao final
    return resultados


def main():
    parser = argparse.ArgumentParser(description="Traduz coluna(s) de um CSV (Inglês -> PT-BR).")
    parser.add_argument("entrada", help="Caminho do CSV de entrada")
    parser.add_argument("saida", help="Caminho do CSV de saída (com a coluna traduzida)")
    parser.add_argument(
        "--coluna",
        default="2",
        help="Coluna(s) a traduzir, separadas por vírgula: índice numérico (0-based) "
             "e/ou nome exato do cabeçalho (ex: '2' ou 'NPC SAY,PC REPLY').",
    )
    parser.add_argument(
        "--linha-cabecalho",
        type=int,
        default=0,
        help="Índice (0-based) da linha que contém os nomes das colunas. "
             "Use se o arquivo tiver linhas de título antes do cabeçalho real. Padrão: 0.",
    )
    parser.add_argument(
        "--modelo",
        default="facebook/nllb-200-distilled-1.3B",
        help="Modelo NLLB a usar. Padrão: facebook/nllb-200-distilled-1.3B",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Tamanho do lote (padrão: 32)")
    parser.add_argument("--max-length", type=int, default=256, help="Tamanho máximo do texto em tokens (padrão: 256)")
    parser.add_argument(
        "--remover-acentos",
        action="store_true",
        help="Remove acentos e caracteres especiais da tradução, deixando só ASCII "
             "(ex: 'traduçao rápida' -> 'traducao rapida').",
    )
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("AVISO: GPU não detectada. No Colab, vá em Ambiente de execução > "
              "Alterar tipo de ambiente de execução > GPU.", file=sys.stderr)

    # Lê o CSV
    with open(args.entrada, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        linhas = list(reader)

    if not linhas:
        print("CSV vazio.", file=sys.stderr)
        sys.exit(1)

    cabecalho = linhas[args.linha_cabecalho]
    linhas_titulo = linhas[: args.linha_cabecalho]  # linhas de título antes do cabeçalho (preservadas como estão)
    dados = linhas[args.linha_cabecalho + 1 :]

    # Resolve --coluna: aceita lista separada por vírgula, cada item índice numérico ou nome
    indices_colunas = []
    for item in args.coluna.split(","):
        item = item.strip()
        if item.isdigit():
            idx = int(item)
        else:
            if item not in cabecalho:
                print(
                    f"Erro: coluna '{item}' não encontrada. Colunas disponíveis: {cabecalho}",
                    file=sys.stderr,
                )
                sys.exit(1)
            idx = cabecalho.index(item)
        if idx >= len(cabecalho):
            print(f"Erro: coluna {idx} não existe (CSV tem {len(cabecalho)} colunas).", file=sys.stderr)
            sys.exit(1)
        indices_colunas.append(idx)

    tokenizer, modelo = carregar_modelo(args.modelo, device)

    # Traduz cada coluna solicitada, uma de cada vez
    for indice_coluna in indices_colunas:
        textos_originais = [linha[indice_coluna] if indice_coluna < len(linha) else "" for linha in dados]
        print(f"\nColuna '{cabecalho[indice_coluna]}' ({len(textos_originais)} linhas):")

        # Divide cada célula em frases antes de traduzir (evita truncamento do NLLB
        # em textos com múltiplas frases), depois remonta cada célula.
        frases_planas, mapeamento = preparar_sentencas(textos_originais)
        print(f"({len(frases_planas)} frases no total após dividir as {len(textos_originais)} linhas)")

        frases_traduzidas = traduzir_em_lotes(
            frases_planas, tokenizer, modelo, device, args.batch_size, args.max_length
        )

        traducoes = [
            " ".join(frases_traduzidas[inicio:fim]) if fim > inicio else ""
            for inicio, fim in mapeamento
        ]

        if args.remover_acentos:
            traducoes = [remover_acentos(t) for t in traducoes]

        # Substitui a coluna original pela traduzida
        for linha, traducao in zip(dados, traducoes):
            while len(linha) <= indice_coluna:
                linha.append("")
            linha[indice_coluna] = traducao

    with open(args.saida, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(linhas_titulo)
        writer.writerow(cabecalho)
        writer.writerows(dados)

    print(f"Concluído! Arquivo salvo em '{args.saida}'.")


if __name__ == "__main__":
    main()
