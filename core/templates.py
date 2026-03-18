from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT
from app.helpers.translate import lang, translate as t
from core.request import Request
from core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
import markdown
import os
import traceback
import sys
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

MANIFEST_BUILD: dict[str, str] = {}

def react(component: str, props: dict = {}) -> str:
    """
    Generates a mounting point for a React component with serialized props.
    """
    id_ = 'react-' + uuid.uuid4().hex
    props_json = json.dumps(props).replace('"', '&quot;')
    return f'<div id="{id_}" data-react-component="{component}" data-props="{props_json}"></div>'

def renderReact(request: Request, component: str, props: dict = {}, options: dict = {}):
    """
    Renders a base HTML template configured to initialize a React component.
    """
    meta = options.get('meta', [])
    scripts = options.get('scripts', [])
    styles = options.get('styles', [])
    
    meta_tags = '\n'.join([f'<meta name="{m["name"]}" content="{m["content"]}">' for m in meta])
    style_tags = '\n'.join([f'<link rel="stylesheet" href="{s}">' for s in styles])
    script_tags = '\n'.join([f'<script src="{s}"></script>' for s in scripts])
    
    context = {
        "component": component,
        "props": json.dumps(props),
        "title": options.get('title', TITLE_PROJECT),
        "keywords": options.get('keywords', KEYWORDS_DEFAULT),
        "description": options.get('description', DESCRIPTION_DEFAULT),
        "author": options.get('author', AUTHOR_DEFAULT),
        "lang": options.get('lang', LANG_DEFAULT),
        "head": f"{meta_tags}\n{style_tags}\n{script_tags}"
    }
    return render(request=request, template="lila/react_base", context=context)

def vite_assets() -> str:
    """
    Resolves Vite asset tags for development (hot reload) or production (manifest).
    """
    if DEBUG:
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
    
    global MANIFEST_BUILD
    if not MANIFEST_BUILD:
        try:
            from app.build_manifest import manifest
            MANIFEST_BUILD = manifest
        except ImportError:
            Logger.error("Build manifest not found. Run 'npm run build'.")
            return ""

    entry = MANIFEST_BUILD.get("file")
    css = MANIFEST_BUILD.get("css", [])
    
    if not entry:
        return ""

    html_parts = [f'<script type="module" src="/public/build/{entry}"></script>']
    for css_file in css:
        html_parts.append(f'<link rel="stylesheet" href="/public/build/{css_file}">')
        
    return "\n".join(html_parts)

jinja_env.globals['react'] = react
jinja_env.globals['vite_assets'] = vite_assets

templates = Jinja2Templates(env=jinja_env)
markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)

def get_base_context(request: Request, files_translate: list[str] = [], lang_default: str = None) -> dict:
    """
    Constructs the standard context dictionary for all template renders.
    """
    current_lang = lang_default if lang_default else lang(request)
    translations = t("translations", request, lang_default=lang_default)
    
    for file_name in files_translate:
        translations.update(t(file_name, request, lang_default=lang_default))
        
    return {
        "title": TITLE_PROJECT,
        "version": VERSION_PROJECT,
        "lang": current_lang,
        "translate": translations,
        "description": DESCRIPTION_DEFAULT,
        "keywords": KEYWORDS_DEFAULT,
        "author": AUTHOR_DEFAULT,
    }

def render(request: Request, template: str, context: dict = {}, files_translate: list[str] = [], lang_default: str = None):
    """
    Renders an HTML template with unified context and error handling.
    """
    try:
        full_context = get_base_context(request, files_translate, lang_default)
        full_context.update(context)
        return templates.TemplateResponse(request=request, name=f"{template}.html", context=full_context)
    except Exception as e:
        return handle_render_error(template, e)

def handle_render_error(template: str, e: Exception):
    """
    Logs and formats template rendering errors based on the debug environment.
    """
    exc_type, _, exc_tb = sys.exc_info()
    tb_str = traceback.format_exc()
    error_name = exc_type.__name__ if exc_type else "Error"
    
    Logger.error(f"Render error in {template}: {str(e)}")
    print(f"\n{'='*20} TEMPLATE ERROR: {template} {'='*20}\n{tb_str}")

    if DEBUG:
        return HTMLResponse(content=f"<h1>{error_name}</h1><pre>{tb_str}</pre>", status_code=500)
    return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

def renderMarkdown(request: Request, file: str, css_files: list = [], js_files: list = [], lang_default: str = None, translate_files: list[str] = []):
    """
    Converts a markdown file to HTML and wraps it in a layout template.
    """
    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    context = get_base_context(request, translate_files, lang_default)
    
    # Simple Jinja-like replacement for MD
    for key, val in context["translate"].items():
        md_content = md_content.replace(f'{{{{ translate["{key}"] }}}}', str(val))

    html_content = markdown.markdown(md_content)
    context.update({
        "request": request,
        "content": html_content,
        "css_files": css_files,
        "js_files": js_files,
    })

    return markdown_templates.TemplateResponse("layout.html", context)