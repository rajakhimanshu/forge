from tools.llm_router import safe_print
import os
import re

backend_dir = r'W:\The Office\Currently Working\FORGE\backend'
exclude_file = os.path.join('tools', 'llm_router.py')
exclude_dir = 'venv'

def patch_file(file_path):
    if exclude_file in file_path:
        return
    if f'{os.sep}{exclude_dir}{os.sep}' in file_path:
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return

    # Check if safe_print( exists as a function call
    has_print = re.search(r'\bprint\(', content)
    
    if not has_print and 'safe_print(' not in content:
        return

    # Replace safe_print( with safe_print(
    new_content = re.sub(r'\bprint\(', 'safe_print(', content)
    
    # Ensure safe_print is imported at the top level
    # We look for a top-level (no indentation) import
    has_global_import = re.search(r'^from tools\.llm_router import.*safe_print', new_content, re.MULTILINE)
    
    if 'safe_print(' in new_content and not has_global_import:
        # Check if there is ANY top-level import from tools.llm_router
        existing_top_import = re.search(r'^from tools\.llm_router import\s+([^\n]+)', new_content, re.MULTILINE)
        if existing_top_import:
            # Add safe_print to it
            def add_to_import(match):
                imported = match.group(1)
                if 'safe_print' in imported:
                    return match.group(0)
                if '(' in imported:
                    return match.group(0).replace('(', '(safe_print, ', 1)
                else:
                    return f'from tools.llm_router import safe_print, {imported}'
            new_content = re.sub(r'^from tools\.llm_router import\s+([^\n]+)', add_to_import, new_content, flags=re.MULTILINE)
        else:
            # Add a new global import
            lines = new_content.splitlines()
            inserted = False
            for i, line in enumerate(lines):
                # Insert before first non-comment, non-docstring, non-empty line, 
                # or before first import
                if line.startswith('import ') or line.startswith('from '):
                    lines.insert(i, 'from tools.llm_router import safe_print')
                    inserted = True
                    break
            if not inserted:
                # Find the first line that isn't a docstring or comment
                for i, line in enumerate(lines):
                    if line.strip() and not line.strip().startswith('#') and '"""' not in line and "'''" not in line:
                        lines.insert(i, 'from tools.llm_router import safe_print')
                        inserted = True
                        break
            if not inserted:
                lines.insert(0, 'from tools.llm_router import safe_print')
            new_content = '\n'.join(lines)

    if new_content != content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            pass

def unpatch_venv(venv_path):
    if not os.path.exists(venv_path):
        return
    for root, dirs, files in os.walk(venv_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if 'safe_print(' in content:
                        new_content = content.replace('safe_print(', 'safe_print(')
                        # Remove added imports
                        new_content = re.sub(r'^from tools\.llm_router import safe_print\n?', '', new_content, flags=re.MULTILINE)
                        # If it was added to an existing list, it's harder to undo perfectly with regex 
                        # but in venv it's unlikely tools.llm_router was already there.
                        if new_content != content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                except:
                    pass

if __name__ == "__main__":
    unpatch_venv(os.path.join(backend_dir, 'venv'))
    for root, dirs, files in os.walk(backend_dir):
        if exclude_dir in dirs:
            dirs.remove(exclude_dir)
        for file in files:
            if file.endswith('.py'):
                patch_file(os.path.join(root, file))