#!/usr/bin/env python3
"""
Verifica o encoding real de todos os .txt de uma pasta.

Usa a biblioteca 'chardet' para dar um palpite confiável de encoding
(instale com: pip install chardet) e mostra uma prévia do texto
decodificado, pra você confirmar visualmente se não virou "mojibake"
(caracteres tipo "Ã©" no lugar de "é").

Uso:
    python verificar_encoding_pasta.py caminho/da/pasta
"""

import argparse
import os
import sys

try:
    import chardet
except ImportError:
    print("Biblioteca 'chardet' não encontrada. Instale com: pip install chardet", file=sys.stderr)
    sys.exit(1)


def verificar_arquivo(caminho: str):
    with open(caminho, "rb") as f:
        raw = f.read()

    deteccao = chardet.detect(raw)
    encoding_detectado = deteccao["encoding"] or "desconhecido"
    confianca = deteccao["confidence"] or 0.0

    decodifica_utf8 = True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        decodifica_utf8 = False

    # Prévia com o encoding detectado (o palpite mais confiável)
    try:
        texto_previa = raw.decode(encoding_detectado, errors="replace")
    except (LookupError, TypeError):
        texto_previa = raw.decode("latin1", errors="replace")

    trecho = texto_previa[:80].replace("\n", " ").replace("\t", " | ")

    return {
        "tamanho": len(raw),
        "decodifica_utf8": decodifica_utf8,
        "encoding_detectado": encoding_detectado,
        "confianca": confianca,
        "trecho": trecho,
    }


def main():
    parser = argparse.ArgumentParser(description="Verifica o encoding de todos os .txt de uma pasta.")
    parser.add_argument("pasta", help="Pasta com os arquivos .txt a verificar")
    args = parser.parse_args()

    if not os.path.isdir(args.pasta):
        print(f"Erro: pasta '{args.pasta}' não encontrada.", file=sys.stderr)
        sys.exit(1)

    arquivos = sorted(f for f in os.listdir(args.pasta) if f.lower().endswith(".txt"))
    if not arquivos:
        print(f"Nenhum .txt encontrado em '{args.pasta}'.", file=sys.stderr)
        sys.exit(1)

    print(f"{len(arquivos)} arquivo(s) encontrado(s) em '{args.pasta}'\n")

    contagem_utf8 = 0
    contagem_nao_utf8 = 0

    for nome_arquivo in arquivos:
        caminho = os.path.join(args.pasta, nome_arquivo)
        info = verificar_arquivo(caminho)

        utf8_str = "SIM" if info["decodifica_utf8"] else "NÃO"
        if info["decodifica_utf8"]:
            contagem_utf8 += 1
        else:
            contagem_nao_utf8 += 1

        print(f"[{nome_arquivo}]")
        print(f"  É UTF-8 válido?     {utf8_str}")
        print(f"  Palpite de encoding: {info['encoding_detectado']} (confiança: {info['confianca']*100:.0f}%)")
        print(f"  Prévia do texto:     {info['trecho']}")
        print()

    print("-" * 70)
    print(f"Resumo: {contagem_utf8} arquivo(s) ainda são UTF-8 válido | "
          f"{contagem_nao_utf8} arquivo(s) NÃO são UTF-8 (provavelmente já convertidos)")
    print(
        "\nDica: olhe a 'Prévia do texto' de cada um. Se aparecer algo como "
        "'traduÃ§Ã£o' em vez de 'tradução', o arquivo está sendo lido com o "
        "encoding errado -- confira o 'Palpite de encoding' daquela linha."
    )


if __name__ == "__main__":
    main()
