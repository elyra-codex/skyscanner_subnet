import os
from pathlib import Path

def gather_files_content(root_dir, output_file):
    root_path = Path(root_dir)
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for file_path in root_path.rglob('*.*'):
            if file_path.is_file() and file_path != Path(output_file):
                try:
                    out_f.write('-' * 75 + '\n')
                    out_f.write(f'{file_path.relative_to(root_path)}\n')
                    out_f.write('-' * 75 + '\n')
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as in_f:
                        out_f.write(in_f.read())
                    out_f.write('\n')
                    
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
    print(f"All files written to {output_file}")

if __name__ == '__main__':
    directory = input("Enter directory to scan (or '.' for current): ") or '.'
    output_filename = 'all_files_content.txt'
    gather_files_content(directory, output_filename)