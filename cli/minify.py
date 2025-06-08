from jsmin import jsmin
from cssmin import cssmin
from htmlmin import minify

import os

def main():
    success = "Files minified successfully"
    html_folder = "templates/html"
    public_folder = "static"
    js_folder = f"{public_folder}/js"
    css_folder = f"{public_folder}/css"
    
    for root, _, files in os.walk(js_folder):
        for file in files:
            if file.endswith('.js'):
                file_path = os.path.join(root, file)
                js(file_path)
    
    for root, _, files in os.walk(css_folder):
        for file in files:
            if file.endswith('.css'):
                file_path = os.path.join(root, file)
                css(file_path)
    
    for root, _, files in os.walk(html_folder):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                html(file_path)
    
    
    return success

def js(file_path: str) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as js_file:
            original_content = js_file.read()
        
        minified = jsmin(original_content)
        
        with open(file_path, 'w', encoding='utf-8') as js_file:
            js_file.write(minified)
        
        return True
    except Exception as e:
        print(f"Error minifying JS file {file_path}: {str(e)}")
        return False

def css(file_path: str) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as css_file:
            original_content = css_file.read()
        
        minified = cssmin(original_content)
        
        with open(file_path, 'w', encoding='utf-8') as css_file:
            css_file.write(minified)
        
        return True
    except Exception as e:
        print(f"Error minifying CSS file {file_path}: {str(e)}")
        return False

def html(file_path: str) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as html_file:
            original_content = html_file.read()
        
        minified = minify(original_content, remove_comments=True, remove_empty_space=True)
        
        with open(file_path, 'w', encoding='utf-8') as html_file:
            html_file.write(minified)
        
        return True
    except Exception as e:
        print(f"Error minifying HTML file {file_path}: {str(e)}")
        return False

if __name__ == "__main__":
    result = main()
    print(result)
