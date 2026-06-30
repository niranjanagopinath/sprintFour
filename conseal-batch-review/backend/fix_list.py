import os
import glob

def fix_list_typing(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'List[' in content:
                    # Add 'from typing import List' if not present
                    if 'from typing import' in content and 'List' not in content:
                        content = content.replace('from typing import ', 'from typing import List, ')
                    elif 'from typing import' not in content:
                        content = 'from typing import List\n' + content
                        
                    content = content.replace('List[', 'List[')
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
if __name__ == '__main__':
    fix_list_typing(r'C:\Users\niran\OneDrive\Desktop\sprintFour\conseal-batch-review\backend')
