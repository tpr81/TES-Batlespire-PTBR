import sys
import os
from io import BytesIO
from array import array
from struct import pack

def compress(uncompressed_bytes):
    """Comprime os dados usando o algoritmo LZSS (janela deslizante de 4096 bytes)."""
    window = array('B', (b' ' * 4078) + (b'\x00' * 18))
    pos = 4078
    
    in_stream = BytesIO(uncompressed_bytes)
    out_stream = BytesIO()
    
    while True:
        data = in_stream.read(8) # Lê blocos para formar 1 byte de flags (8 bits)
        if not data:
            break
            
        flags = 0
        block_bytes = BytesIO()
        
        for i, byte in enumerate(data):
            # Para manter o compressor simples e funcional, salvamos os bytes como literais (sem buscar padrões repetidos)
            flags |= (1 << i)
            block_bytes.write(bytes([byte]))
            
            # Atualiza a janela deslizante para manter sincronia
            window[pos] = byte
            pos = (pos + 1) & 0xFFF
            
        out_stream.write(bytes([flags]))
        out_stream.write(block_bytes.getvalue())
        
    return out_stream.getvalue()

def create_bsa(folder_path, output_bsa_path, record_type=0x100, compress_files=True):
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    record_count = len(files)
    
    header = pack("<2H", record_count, record_type)
    
    file_data_blocks = []
    footer_records = []
    
    for name in files:
        file_path = os.path.join(folder_path, name)
        with open(file_path, "rb") as f:
            raw_data = f.read()
            
        if compress_files:
            compressed_data = compress(raw_data)
            is_compressed = 0x01
            final_data = compressed_data
        else:
            is_compressed = 0x00
            final_data = raw_data
            
        file_data_blocks.append(final_data)
        
        # Formata o nome do arquivo truncando/preenchendo para 12 bytes
        name_bytes = name.encode('ascii')[:12].ljust(12, b'\x00')
        footer_records.append((name_bytes, is_compressed, len(final_data)))
        
    with open(output_bsa_path, "wb") as out_bsa:
        # 1. Escreve o Cabeçalho
        out_bsa.write(header)
        
        # 2. Escreve os blocos de dados dos arquivos
        for data in file_data_blocks:
            out_bsa.write(data)
            
        # 3. Escreve o Rodapé (Tabela de Conteúdo)
        struct_fmt = "<12sHI"
        for name_bytes, is_compressed, size in footer_records:
            out_bsa.write(pack(struct_fmt, name_bytes, is_compressed, size))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python pack_bsa.py <pasta_origem> <arquivo_saida.bsa>")
        sys.exit(1)
        
    src_folder = sys.argv[1]
    dst_bsa = sys.argv[2]
    
    create_bsa(src_folder, dst_bsa, compress_files=True)
    print(f"BSA criado com sucesso em: {dst_bsa}")