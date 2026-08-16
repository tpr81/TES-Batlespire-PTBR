#!/usr/bin/env python3
"""
Converte um .txt tabulado (colunas separadas por TAB, como planilhas
exportadas do Excel) em .csv, preservando TODAS as colunas e células
vazias -- sem forçar um número fixo de colunas.

Uso básico:
    python tsv_para_csv.py CF1T.TXT CF1T.csv

Se o arquivo não estiver em UTF-8 (comum em exports antigos do Excel,
costuma vir em Windows-1252 / Latin-1):
    python tsv_para_csv.py CF1T.TXT CF1T.csv --encoding-entrada cp1252

Detecção automática de encoding (tenta utf-8, senão cai para cp1252):
    (já é o comportamento padrão, sem precisar passar --encoding-entrada)
"""

import argparse
import csv
import sys


def detectar_encoding(caminho: str) -> str:
    """Tenta UTF-8 primeiro; se falhar, usa cp1252 (Windows-1252)."""
    with open(caminho, "rb") as f:
        raw = f.read()
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def converter(caminho_txt: str, caminho_csv: str, encoding_entrada: str | None):
    if encoding_entrada is None:
        encoding_entrada = detectar_encoding(caminho_txt)
        print(f"Encoding detectado automaticamente: {encoding_entrada}")

    with open(caminho_txt, "r", encoding=encoding_entrada, newline="") as f_in:
        linhas = f_in.read().splitlines()

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        for linha in linhas:
            campos = linha.split("\t")
            writer.writerow(campos)

    print(f"Concluído! {len(linhas)} linha(s) convertida(s) para '{caminho_csv}' (saída em UTF-8).")


def main():
    parser = argparse.ArgumentParser(
        description="Converte um .txt separado por TAB em .csv, sem perder colunas/estrutura."
    )
    parser.add_argument("entrada", help="Caminho do .txt de entrada")
    parser.add_argument("saida", help="Caminho do .csv de saída")
    parser.add_argument(
        "--encoding-entrada",
        default=None,
        help="Encoding do arquivo de entrada (ex: utf-8, cp1252). Se omitido, detecta automaticamente.",
    )
    args = parser.parse_args()

    try:
        converter(args.entrada, args.saida, args.encoding_entrada)
    except FileNotFoundError:
        print(f"Erro: arquivo '{args.entrada}' não encontrado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
