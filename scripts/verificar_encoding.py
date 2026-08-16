#!/usr/bin/env python3
"""
Verifica o encoding real de um arquivo (útil pra confirmar se a conversão
para ISO-8859-1 realmente funcionou).

Uso:
    python verificar_encoding.py caminho/do/arquivo.txt
"""

import sys

if len(sys.argv) != 2:
    print("Uso: python verificar_encoding.py caminho/do/arquivo.txt")
    sys.exit(1)

caminho = sys.argv[1]

with open(caminho, "rb") as f:
    raw = f.read()

print(f"Arquivo: {caminho}")
print(f"Tamanho: {len(raw)} bytes")
print()

try:
    raw.decode("utf-8")
    print("Decodifica como UTF-8: SIM")
except UnicodeDecodeError as e:
    print(f"Decodifica como UTF-8: NÃO -> {e}")

try:
    texto = raw.decode("iso-8859-1")
    print("Decodifica como ISO-8859-1: SIM")
    print()
    print("Primeiras linhas do conteúdo (decodificado como ISO-8859-1):")
    print(texto[:300])
except UnicodeDecodeError as e:
    print(f"Decodifica como ISO-8859-1: NÃO -> {e}")
