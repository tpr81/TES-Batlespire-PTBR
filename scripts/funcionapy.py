import sys
import os

def fix_line(line_str):
    line_str = line_str.strip("\r\n")
    if not line_str:
        return None
    
    # Se a linha não usa TABs, tenta converter sequências de espaços em TABs
    if "\t" not in line_str:
        parts = [p for p in line_str.split("  ") if p]
        line_str = "\t".join(parts)
        
    return line_str

def process_folder(input_folder, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = [f for f in os.listdir(input_folder) if f.lower().endswith('.txt')]
    
    if not files:
        print("Nenhum ficheiro .TXT encontrado na pasta de origem.")
        return

    for filename in files:
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        
        with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        fixed_lines = []
        for line in lines:
            fixed = fix_line(line)
            if fixed is not None:
                fixed_lines.append(fixed)

        # Grava com quebras de linha CRLF (DOS) e codificação Latin-1 sem caracteres inválidos
        with open(output_path, "wb") as f:
            content = "\r\n".join(fixed_lines) + "\r\n"
            f.write(content.encode("latin-1", errors="replace"))

        print(f"Corrigido: {filename}")

    print("\nProcesso concluído com sucesso!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python fix_folder.py <pasta_origem> <pasta_destino>")
        sys.exit(1)

    src_dir = sys.argv[1]
    dst_dir = sys.argv[2]

    process_folder(src_dir, dst_dir)