#!/usr/bin/env python3
import sys
import re
from struct import pack

def decode_text(text_repr):
    # Remove os delimitadores b'...' ou b"..." das bordas
    if (text_repr.startswith("b'") and text_repr.endswith("'")) or \
       (text_repr.startswith('b"') and text_repr.endswith('"')):
        text_repr = text_repr[2:-1]

    # Função para substituir sequências de escape manualmente
    def replace_escape(match):
        seq = match.group(0)
        if seq.startswith('\\x'):
            # Converte coisas como \xfc ou \x00 para o caractere real
            return chr(int(seq[2:], 16))
        elif seq == "\\'": return "'"
        elif seq == '\\"': return '"'
        elif seq == '\\n': return '\n'
        elif seq == '\\r': return '\r'
        elif seq == '\\t': return '\t'
        elif seq == '\\\\': return '\\'
        return seq

    # Busca por \xNN ou escapes comuns (\', \", \n) e substitui
    text_repr = re.sub(r'\\x[0-9a-fA-F]{2}|\\[\'"nrt\\]', replace_escape, text_repr)
    
    # Converte o texto final para bytes (latin-1 mapeia 1:1 para binários de jogos antigos)
    return text_repr.encode('latin-1', errors='replace')

def main():
    if len(sys.argv) < 3:
        print("Uso: python3 txt_to_rsc.py textos.txt NEW.RSC")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    entries = []

    # 1. Lê e extrai os dados do arquivo .txt
    with open(input_file, 'r', encoding="utf-8") as f:
        lines = f.read().strip().split('\n')

    # Ignora a primeira linha se for o cabeçalho das colunas
    start_idx = 1 if lines and lines[0].startswith("Id\t") else 0

    for line in lines[start_idx:]:
        if not line.strip():
            continue
        
        parts = line.split('\t')
        if len(parts) >= 4:
            item_id = int(parts[0])
            
            # Junta novamente caso o texto traduzido contenha uma tabulação real no meio
            text_repr = "\t".join(parts[3:])
            
            text_bytes = decode_text(text_repr)
            entries.append((item_id, text_bytes))

    # 2. Calcula a estrutura e os offsets do arquivo
    num_entries = len(entries)
    
    # O cabeçalho tem 6 bytes por entrada (4 do offset + 2 do id)
    header_size = num_entries * 6
    
    # O valor inicial lido pelo unpack_from("<I", data, 0) no extrator original
    length_value = header_size + 6 
    
    # Onde o texto de fato começa: os 4 bytes iniciais + tamanho do cabeçalho + 2 bytes de gap/padding
    text_start_offset = header_size + 8

    header_bytes = bytearray()
    text_bytes_array = bytearray()

    current_offset = text_start_offset

    # 3. Monta os bytes dinamicamente
    for item_id, t_bytes in entries:
        # Empacota o offset (4 bytes) e o id (2 bytes)
        header_bytes.extend(pack("<IH", current_offset, item_id))
        
        # Adiciona o texto e o byte terminador (0xFE)
        text_bytes_array.extend(t_bytes)
        text_bytes_array.append(0xFE)
        
        # Atualiza o offset para a próxima entrada
        current_offset += len(t_bytes) + 1

    # 4. Escreve tudo no novo arquivo binário
    with open(output_file, 'wb') as f:
        f.write(pack("<I", length_value))
        f.write(header_bytes)
        f.write(b'\x00\x00') # 2 bytes de padding após o cabeçalho
        f.write(text_bytes_array)
        
    print(f"Arquivo gerado com sucesso: {output_file} com {num_entries} entradas.")

if __name__ == "__main__":
    main()