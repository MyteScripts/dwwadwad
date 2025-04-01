import os
import re

def remove_comments_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        new_content = re.sub(r'^\s*#.*$|^#.*$', '', content, flags=re.MULTILINE)

        new_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', new_content)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)
        
        return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def process_python_files():

    python_files = [f for f in os.listdir('.') if f.endswith('.py')]
    
    success_count = 0
    total_files = len(python_files)
    
    print(f"Found {total_files} Python files.")
    
    for file_name in python_files:
        file_path = os.path.join('.', file_name)
        if remove_comments_from_file(file_path):
            success_count += 1
            print(f"Processed: {file_name}")
    
    print(f"Comments removed from {success_count} out of {total_files} files.")

if __name__ == "__main__":
    process_python_files()