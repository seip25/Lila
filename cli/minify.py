import os
import rjsmin
import rcssmin

def main():
    success = "Files minified successfully"
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
 
    return success


def js(file_path: str) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as js_file:
            original_content = js_file.read()
        
        minified = rjsmin.jsmin(original_content)
        
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
        
        minified = rcssmin.cssmin(original_content)
        
        with open(file_path, 'w', encoding='utf-8') as css_file:
            css_file.write(minified)
        
        return True
    except Exception as e:
        print(f"Error minifying CSS file {file_path}: {str(e)}")
        return False


if __name__ == "__main__":
    result = main()
    print(result)
