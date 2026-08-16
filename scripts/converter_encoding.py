#!/usr/bin/env python3
"""
Converte todos os .txt de uma pasta de UTF-8 para ISO-8859-1 (Latin-1).

Uso:
    python converter_encoding.py pasta_entrada pasta_saida

Se a pasta de saída não for informada, sobrescreve os arquivos na própria pasta.
    python converter_encoding.py pasta_entrada

Caracteres que não existem em ISO-8859-1 (ex: alguns símbolos, emojis) são
substituídos por "?" por padrão -- use --erro-se-incompativel para travar
o script nesse caso, em vez de substituir silenciosamente.
"""

import argparse
import os
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


def converter_pasta(pasta_entrada: str, pasta_saida: str, sobrescrever: bool, erro_se_incompativel: bool, encoding_entrada: str | None):
    os.makedirs(pasta_saida, exist_ok=True)

    arquivos = sorted(f for f in os.listdir(pasta_entrada) if f.lower().endswith(".txt"))
    if not arquivos:
        print(f"Nenhum .txt encontrado em '{pasta_entrada}'.", file=sys.stderr)
        sys.exit(1)

    erros_handler = "strict" if erro_se_incompativel else "replace"

    for nome_arquivo in arquivos:
        caminho_entrada = os.path.join(pasta_entrada, nome_arquivo)
        caminho_saida = os.path.join(pasta_saida, nome_arquivo)

        encoding_deste_arquivo = encoding_entrada or detectar_encoding(caminho_entrada)

        try:
            with open(caminho_entrada, "r", encoding=encoding_deste_arquivo) as f:
                conteudo = f.read()
        except UnicodeDecodeError as e:
            print(
                f"ERRO ao ler '{nome_arquivo}' como {encoding_deste_arquivo}: {e}. "
                f"Tente passar --encoding-entrada com o encoding correto (ex: cp1252, latin-1).",
                file=sys.stderr,
            )
            continue

        try:
            with open(caminho_saida, "w", encoding="iso-8859-1", errors=erros_handler, newline="") as f:
                f.write(conteudo)
            print(f"OK: '{nome_arquivo}'")
        except UnicodeEncodeError as e:
            print(f"ERRO em '{nome_arquivo}': caractere incompatível com ISO-8859-1 -> {e}", file=sys.stderr)

    print(f"\nConcluído! Arquivos salvos em '{pasta_saida}'.")


def main():
    parser = argparse.ArgumentParser(description="Converte .txt de UTF-8 para ISO-8859-1.")
    parser.add_argument("pasta_entrada", help="Pasta com os .txt em UTF-8")
    parser.add_argument(
        "pasta_saida", nargs="?", default=None,
        help="Pasta de saída (padrão: sobrescreve na mesma pasta de entrada)",
    )
    parser.add_argument(
        "--erro-se-incompativel",
        action="store_true",
        help="Trava o script se algum caractere não existir em ISO-8859-1, em vez de trocar por '?'.",
    )
    parser.add_argument(
        "--encoding-entrada",
        default=None,
        help="Encoding dos .txt de entrada (ex: utf-8, cp1252, latin-1). "
             "Se omitido, detecta automaticamente por arquivo (utf-8 ou cp1252).",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.pasta_entrada):
        print(f"Erro: pasta '{args.pasta_entrada}' não encontrada.", file=sys.stderr)
        sys.exit(1)

    pasta_saida = args.pasta_saida or args.pasta_entrada
    converter_pasta(
        args.pasta_entrada, pasta_saida, pasta_saida == args.pasta_entrada,
        args.erro_se_incompativel, args.encoding_entrada,
    )


if __name__ == "__main__":
    main()
