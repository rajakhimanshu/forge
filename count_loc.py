import os

def count_lines(directory, extensions=('.py', '.tsx', '.ts', '.css', '.txt', '.md')):
    total_lines = 0
    file_counts = {}
    
    for root, dirs, files in os.walk(directory):
        if 'node_modules' in dirs:
            dirs.remove('node_modules')
        if 'venv' in dirs:
            dirs.remove('venv')
        if '.next' in dirs:
            dirs.remove('.next')
        if '.git' in dirs:
            dirs.remove('.git')
            
        for file in files:
            if file.endswith(extensions):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = len(f.readlines())
                        total_lines += lines
                        ext = os.path.splitext(file)[1]
                        file_counts[ext] = file_counts.get(ext, 0) + lines
                except Exception:
                    pass
    return total_lines, file_counts

backend_total, backend_exts = count_lines('backend')
frontend_total, frontend_exts = count_lines('frontend')
root_total, root_exts = count_lines('.', extensions=('.md', '.txt'))

print(f"=== LINE COUNT REPORT ===")
print(f"BACKEND:  {backend_total} lines")
for ext, count in backend_exts.items():
    print(f"  {ext}: {count}")

print(f"\nFRONTEND: {frontend_total} lines")
for ext, count in frontend_exts.items():
    print(f"  {ext}: {count}")

print(f"\nROOT:     {root_total} lines")
print(f"\nTOTAL SYSTEM: {backend_total + frontend_total + root_total} lines")
