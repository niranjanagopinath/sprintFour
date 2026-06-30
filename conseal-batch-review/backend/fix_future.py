                # Check if 'from __future__ import annotations' is present but not the first non-docstring/comment statement
import os
import glob
import re

def fix_future_imports(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'from __future__ import annotations' in content:
                    lines = content.splitlines()
                    new_lines = []
                    future_idx = -1
                    for i, line in enumerate(lines):
                        if 'from __future__ import annotations' in line:
                            future_idx = i
                            break
                    
                    if future_idx > 0:
                        # Extract the future import line
                        future_line = lines.pop(future_idx)
                        
                        # Find where to insert it. Usually at index 0 or after the docstring.
                        # For simplicity, if index 0 is not a future import, insert it at 0, or just after the docstring.
                        # To be safe, put it at index 0, and if there's a docstring at 0, we can push it after.
                        # But Python allows __future__ BEFORE docstrings as well (though convention is after).
                        # Actually, wait. The easiest way is to put it at line 0, but if there's a docstring, Python might complain if docstring is not the very first statement? No, docstring is allowed after __future__. 
                        # Wait, a docstring MUST be the first statement for it to be recognized as a module docstring.
                        # If we put __future__ before the docstring, the docstring is no longer a docstring but just a string literal.
                        
                        # Let's find the first non-string, non-comment, non-empty line.
                        insert_idx = 0
                        in_multiline_string = False
                        string_char = None
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if in_multiline_string:
                                if stripped.endswith(string_char * 3):
                                    in_multiline_string = False
                                    insert_idx = i + 1
                                continue
                            
                            if stripped.startswith('"""') or stripped.startswith("'''"):
                                if not stripped[3:].endswith(stripped[:3]) or len(stripped) < 6:
                                    in_multiline_string = True
                                    string_char = stripped[0]
                                else:
                                    # single line multiline string
                                    insert_idx = i + 1
                                continue
                                
                            if stripped == '' or stripped.startswith('#'):
                                continue
                                
                            # If we get here, it's actual code. Insert before this.
                            insert_idx = i
                            break
                            
                        lines.insert(insert_idx, future_line)
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(lines))
                            
if __name__ == '__main__':
    fix_future_imports(r'C:\Users\niran\OneDrive\Desktop\sprintFour\conseal-batch-review\backend')