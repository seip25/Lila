from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT
from app.helpers.helpers import theme, lang, translate as t
from core.request import Request
from core.responses import HTMLResponse, JSONResponse
from app.helpers.helpers import lang
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
import markdown
import os
import traceback
import sys
from PIL import Image
from pathlib import Path
import rjsmin 
import rcssmin 
import json
import uuid

PROJECT_ROOT = os.getcwd()

jinja_env = Environment(
    loader=minify_loader(
        FileSystemLoader(PATH_TEMPLATES_HTML),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    ),
    auto_reload=DEBUG, 
    autoescape=True,
)

def react(component: str, props: dict = {}) -> str:
    """
    Renders a placeholder div for a React component.
    """
    id_ = 'react-' + uuid.uuid4().hex
    props_json = json.dumps(props).replace('"', '&quot;')
    return f'<div id="{id_}" data-react-component="{component}" data-props="{props_json}"></div>'

def vite_assets() -> str:
    """
    Renders script tags for Vite.
    In DEBUG mode: connects to the Vite dev server.
    In Production: reads manifest.json to serve built assets.
    """
    is_dev = DEBUG
    
    # Check if we are really in dev mode for Vite (can be set independently ideally, but using DEBUG for now)
    # Or check if vite server is reachable? For now, logic as per PHP impl.
    
    if is_dev:
        return """
        <script type="module">
            import RefreshRuntime from "http://localhost:5173/public/build/@react-refresh";
            RefreshRuntime.injectIntoGlobalHook(window);
            window.$RefreshReg$ = () => {};
            window.$RefreshSig$ = () => (type) => type;
            window.__vite_plugin_react_preamble_installed__ = true;
        </script>
        <script type="module" src="http://localhost:5173/public/build/@vite/client"></script>
        <script type="module" src="http://localhost:5173/public/build/react/main.jsx"></script>
        """

    manifest_path = os.path.join(PROJECT_ROOT, 'public', 'build', '.vite', 'manifest.json')
    # fallback
    if not os.path.exists(manifest_path):
         manifest_path = os.path.join(PROJECT_ROOT, 'public', 'build', 'manifest.json')
    
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # entry point name in manifest usually matches input in vite config
        # In CLI implementation later, we'll set entry to 'react/main.jsx'
        entry_key = 'react/main.jsx'
        
        if entry_key in manifest:
            file = manifest[entry_key]['file']
            css_files = manifest[entry_key].get('css', [])
            
            html_parts = []
            html_parts.append(f'<script type="module" src="/public/build/{file}"></script>')
            for css_file in css_files:
                html_parts.append(f'<link rel="stylesheet" href="/public/build/{css_file}">')
            
            return '\n'.join(html_parts)
            
    return '<!-- Vite Manifest not found -->'

jinja_env.globals['react'] = react
jinja_env.globals['vite_assets'] = vite_assets


templates = Jinja2Templates( env=jinja_env)
 

def get_base_context(
    request: Request, files_translate: list[str] = [], lang_default: str = None
) -> dict:
    context = {
        "title": TITLE_PROJECT,
        "version": VERSION_PROJECT,
        "lang": lang_default if lang_default else lang(request),
        "translate": t("translations", request, lang_default=lang_default), 
        "image" :  image,
        "static" : public,
        "public" : public,
        "description" : DESCRIPTION_DEFAULT,
        "keywords" : KEYWORDS_DEFAULT,
        "author" : AUTHOR_DEFAULT,
    }

    for file_name in files_translate:
        context["translate"].update(t(file_name, request, lang_default=lang_default)) 
    return context


def render(
    request: Request,
    template: str,
    context: dict = {},
    files_translate: list[str] = [],
    lang_default: str = None,
    templates=templates,
):
    try:
        template_file = f"{template}.html"
        default_context = get_base_context(
            request=request, files_translate=files_translate, lang_default=lang_default
        )
        context.update(default_context)
        return templates.TemplateResponse(
            request=request, name=template_file, context=context
        )
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        
        error_info = {
            'error_type': exc_type.__name__ if exc_type else 'Unknown',
            'error_message': str(e),
            'template': template,
            'traceback': traceback.format_exc(),
            'file': '',
            'line': 0,
            'function': ''
        }
         
        if exc_tb:
            frame = exc_tb.tb_frame
            error_info['file'] = frame.f_code.co_filename
            error_info['line'] = exc_tb.tb_lineno
            error_info['function'] = frame.f_code.co_name

            Logger.error(f"Render error in {error_info['file']}:{error_info['line']} "
                        f"({error_info['function']}): {error_info['error_message']}")
        else:
            Logger.error(f"Render error: {error_info['error_message']}") 

        # Always print to terminal for debugging
        print(f"\n{'='*80}")
        print(f"TEMPLATE RENDER ERROR")
        print(f"{'='*80}")
        print(f"Template: {template}")
        print(f"Error Type: {error_info['error_type']}")
        print(f"Error Message: {error_info['error_message']}")
        if error_info['file']:
            print(f"File: {error_info['file']}:{error_info['line']}")
            print(f"Function: {error_info['function']}")
        print(f"\nTraceback:\n{error_info['traceback']}")
        print(f"{'='*80}\n")
        
        # Return detailed error page in DEBUG mode, generic error otherwise
        if DEBUG:
            # HTML error page for better readability
            error_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Template Error - {error_info['error_type']}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #252526;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: #d32f2f;
            color: white;
            padding: 20px 30px;
            border-bottom: 3px solid #b71c1c;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 14px;
        }}
        .content {{
            padding: 30px;
        }}
        .error-section {{
            margin-bottom: 25px;
            background: #2d2d30;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #d32f2f;
        }}
        .error-section h2 {{
            margin: 0 0 15px 0;
            font-size: 18px;
            color: #569cd6;
        }}
        .error-section p {{
            margin: 8px 0;
            font-size: 14px;
        }}
        .error-section strong {{
            color: #4ec9b0;
        }}
        .traceback {{
            background: #1e1e1e;
            padding: 20px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
            border: 1px solid #3e3e42;
        }}
        .traceback pre {{
            margin: 0;
            color: #ce9178;
        }}
        .label {{
            display: inline-block;
            background: #3e3e42;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 10px;
            color: #d4d4d4;
        }}
        .value {{
            color: #dcdcaa;
        }}
        .footer {{
            background: #2d2d30;
            padding: 15px 30px;
            text-align: center;
            font-size: 12px;
            color: #858585;
            border-top: 1px solid #3e3e42;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 Template Rendering Error</h1>
            <p>An error occurred while rendering the template. Check the details below.</p>
        </div>
        <div class="content">
            <div class="error-section">
                <h2>📄 Template Information</h2>
                <p><span class="label">Template</span><span class="value">{template}.html</span></p>
                <p><span class="label">Error Type</span><span class="value">{error_info['error_type']}</span></p>
            </div>
            
            <div class="error-section">
                <h2>💬 Error Message</h2>
                <p>{error_info['error_message']}</p>
            </div>
            
            {f'''<div class="error-section">
                <h2>📍 Location</h2>
                <p><span class="label">File</span><span class="value">{error_info['file']}</span></p>
                <p><span class="label">Line</span><span class="value">{error_info['line']}</span></p>
                <p><span class="label">Function</span><span class="value">{error_info['function']}</span></p>
            </div>''' if error_info['file'] else ''}
            
            <div class="error-section">
                <h2>🔍 Full Traceback</h2>
                <div class="traceback">
                    <pre>{error_info['traceback']}</pre>
                </div>
            </div>
        </div>
        <div class="footer">
            <p>💡 This detailed error page is only shown when DEBUG=True in your configuration</p>
        </div>
    </div>
</body>
</html>
"""
            return HTMLResponse(error_html, status_code=500)
        else:
            # Production mode: generic error
            return JSONResponse(
                {"success": False, "message": "Internal server error"},
                status_code=500,
            )
 
markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)


def renderMarkdown(
    request: Request,
    file: str,
    css_files: list = [],
    js_files: list = [], 
    lang_default: str = None,
    translate_files: list[str] = [],
):
    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        not_found_path = os.path.join(PATH_TEMPLATES_HTML, "lila/404.html")
        if os.path.exists(not_found_path):
            return templates.TemplateResponse(
                request=request,
                name="lila/404.html",
                context={"request": request},
                status_code=404,
            )
        else:
            return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    context_translate = t("translations", request, lang_default)
    for file_name in translate_files:
        context_translate.update(t(file_name, request, lang_default)) 

    for key, val in context_translate.items():
        md_content = md_content.replace(f'{{{{ translate["{key}"] }}}}', val)

    html_content = markdown.markdown(md_content)

    context = {
        "request": request,
        "content": html_content,
        "title": TITLE_PROJECT,
        "lang": lang_default if lang_default else lang(request), 
        "css_files": css_files,
        "js_files": js_files,
    }

    return markdown_templates.TemplateResponse("layout.html", context)


def image(file_path: str) -> str:
    extension = file_path.split(".")[-1].lower()
    file_path_webp = file_path.replace(f".{extension}", ".webp")
    if (os.path.exists(os.path.join("public",file_path_webp))==False):
        optimize_image(os.path.join("public",file_path))
    return f"/public/{file_path_webp}"


def optimize_image(file_path,  max_width=1920, quality=75) -> Path:
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    img = Image.open(file_path)
     

    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    optimized_filename = f"{file_path.stem}.webp"
    optimized_path = file_path.parent / optimized_filename
    img.save(optimized_path, format="WEBP", optimize=True, quality=quality)

    return optimized_path

def public(file_path: str) -> str:
    new_file_path = file_path
    extension = file_path.split(".")[-1].lower()
    if (extension in [ "css","js"]):
        exists_min= os.path.exists(os.path.join("public",file_path.replace(f".{extension}", ".min.{extension}")))
        if (exists_min==False):
            with open(os.path.join("public",file_path), "r", encoding="utf-8") as f:
                content = f.read()
            if (extension == "css"):
                minified_content = rcssmin.cssmin(content)
            else:
                minified_content = rjsmin.jsmin(content)
            with open(os.path.join("public",file_path.replace(f".{extension}", f".min.{extension}")), "w", encoding="utf-8") as f:
                f.write(minified_content)
            new_file_path = file_path.replace(f".{extension}", f".min.{extension}")
    if(extension in ["png", "jpg", "jpeg", "gif", "webp"]):
        optimize_image(os.path.join("public",file_path))
        new_file_path = file_path.replace(f".{extension}", ".webp")
    return f"/public/{new_file_path}"
